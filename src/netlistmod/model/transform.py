"""Convert the strict grammar's parse into typed nodes with source spans.

Syntax is defined by the Lark grammar (architecture P13). This module only maps each grammar
rule to a node: one transformer method per rule, no regular expressions and no re-scanning of
source lines. Raw statement text is a slice of the source by span.

The builder transforms the positioned tree after the whole source has parsed, so a syntax error
anywhere is reported before a form this module rejects. An item's end is the end of its last
token; every top-level rule ends with one.

Element fields are rules that start with their separator (a "gap"). A field method returns a
:class:`_Field` holding the field's node and the end-of-line comments of its gap; each element
method collects its slots by node type (architecture §6.3 rule 11). Forms the grammar
recognises only to reject them (RKM without the option, stimulus functions, ``q=``,
``params:``) raise here, at the position of their token (P13 (c)).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, Literal, NoReturn, TypeVar

from lark import Token, Transformer
from lark.exceptions import VisitError

from netlistmod.dialects import Dialect
from netlistmod.errors import ParseError, UnsupportedConstruct
from netlistmod.grammar.loader import parse_tree
from netlistmod.model.nodes import (
    BlankLine,
    Capacitor,
    CommentLine,
    CurrentSource,
    Diode,
    End,
    Inductor,
    MutualCoupling,
    Node,
    OpaqueBlock,
    OpaqueStatement,
    ParseResult,
    Resistor,
    SubcktInstance,
    Title,
    TitleDirective,
    TopLevelItem,
    UnknownDirective,
    VoltageSource,
)
from netlistmod.model.values import (
    AcSpec,
    ElementReference,
    Flag,
    Formula,
    ModelReference,
    NumericValue,
    ParamAssignment,
    SubcktReference,
    Value,
)
from netlistmod.source import SourceText, Span

_T = TypeVar("_T")

_FORMULA_DELIMITERS: dict[str, Literal["{", "'", '"']] = {
    "BRACE_FORMULA": "{",
    "QUOTE_FORMULA": "'",
    "STRING_VALUE": '"',
}
_RKM_TERMINALS = frozenset({"RKM_R", "RKM_R_MEGA", "RKM_R_MILLI", "RKM_C", "RKM_C_FARAD"})
# RKM terminals that ngspice reads differently from IEC 60062 (decision 0004).
_RKM_SOLVER_MISMATCH = frozenset({"RKM_R_MEGA", "RKM_C_FARAD"})
# Field tokens: the token of a field rule that is neither a separator nor a comment.
_GAP_TERMINALS = frozenset({"SEP", "CSEP", "BS_CONT", "TRAILING_COMMENT", "EQ"})


@dataclass(frozen=True, slots=True)
class _Item:
    """A top-level item waiting for its span.

    Whitespace between items is ignored by the grammar and has no token, so an item's span
    runs from the end of the previous item to ``end``. That keeps the spans contiguous.
    """

    end: int
    build: Callable[[Span], TopLevelItem]


@dataclass(frozen=True, slots=True)
class _Rest:
    """Where a statement's text ends, and its end-of-line comments in source order."""

    text_end: int | None
    comments: tuple[Span, ...]


@dataclass(frozen=True, slots=True)
class _Field:
    """One element field: its node, and the comments of the gap in front of it."""

    node: object
    comments: tuple[Span, ...]


@dataclass(frozen=True, slots=True)
class _KeywordValue:
    """A value written with its keyword (``r=1k``)."""

    keyword: str
    value: Value


@dataclass(frozen=True, slots=True)
class _Dc:
    value: Value
    keyword: bool


@dataclass(frozen=True, slots=True)
class _DcKeyword:
    pass


@dataclass(frozen=True, slots=True)
class _AcMagnitude:
    value: Value
    start: int


@dataclass(frozen=True, slots=True)
class _XRest:
    """The part of an ``X`` line after its first node."""

    nodes: tuple[Node, ...]
    subckt: SubcktReference
    params: tuple[ParamAssignment, ...]
    comments: tuple[Span, ...]
    end: int


@dataclass(frozen=True, slots=True)
class _Eol:
    end: int
    comments: tuple[Span, ...]


def _span(token: Token) -> Span:
    if token.start_pos is None or token.end_pos is None:
        raise ValueError(f"Lark did not propagate positions for {token.type}")
    return Span(token.start_pos, token.end_pos)


def _end(children: list[Any]) -> int:
    """The end of the last token: every top-level rule ends with one."""
    for child in reversed(children):
        if isinstance(child, Token) and child.end_pos is not None:
            return child.end_pos
    raise ValueError("Lark did not propagate statement positions")


def _comment_spans(children: list[Any]) -> tuple[Span, ...]:
    return tuple(
        _span(child)
        for child in children
        if isinstance(child, Token) and child.type == "TRAILING_COMMENT"
    )


def _field_token(children: list[Any]) -> Token:
    return next(c for c in children if isinstance(c, Token) and c.type not in _GAP_TERMINALS)


class _Element:
    """The fields of one element line, in source order, with all of their comments."""

    def __init__(self, children: list[Any]) -> None:
        self.designator: Token = children[0]
        self.fields: list[object] = []
        comments: list[Span] = []
        end = 0
        for child in children[1:]:
            if isinstance(child, _Field):
                self.fields.append(child.node)
                comments.extend(child.comments)
            elif isinstance(child, _Eol):
                comments.extend(child.comments)
                end = child.end
            elif isinstance(child, _XRest):
                self.fields.append(child)
                comments.extend(child.comments)
                end = child.end
        self.comments = tuple(comments)
        self.end = end or _end(children)

    def all(self, kind: type[_T]) -> tuple[_T, ...]:
        return tuple(node for node in self.fields if isinstance(node, kind))

    def optional(self, kind: type[_T]) -> _T | None:
        return next((node for node in self.fields if isinstance(node, kind)), None)

    def values(self) -> tuple[Value, ...]:
        """The positional values (a keyword value, a DC value or a parameter is wrapped)."""
        return tuple(node for node in self.fields if isinstance(node, NumericValue | Formula))


class _NodeBuilder(Transformer[Token, ParseResult]):
    """Build nodes for one parse; every grammar rule has exactly one method."""

    def __init__(self, source: SourceText, *, rkm: bool = False) -> None:
        super().__init__()
        self._source = source
        self._rkm = rkm

    def __default__(self, data: Any, children: Any, meta: Any) -> NoReturn:
        raise TypeError(f"Unhandled grammar rule {data!r}")

    def start(self, children: list[Any]) -> ParseResult:
        items: list[TopLevelItem] = []
        cursor = 0
        for child in children:
            for item in child if isinstance(child, tuple) else (child,):
                items.append(item.build(Span(cursor, item.end)))
                cursor = item.end
        # Ignored whitespace after the last token (for example ``.end`` plus spaces and no
        # newline) belongs to the last item.
        text = self._source.text
        if cursor < len(text):
            items[-1] = replace(items[-1], span=Span(items[-1].span.start, len(text)))
        return ParseResult(tuple(items))

    def explicit_title(self, children: list[Token]) -> _Item:
        text = next((str(token) for token in children if token.type == "TITLE_ARG"), "")
        return _Item(_end(children), lambda span: Title(text, True, span))

    def implicit_title(self, children: list[Token]) -> _Item:
        text = str(children[0])
        return _Item(_end(children), lambda span: Title(text, False, span))

    def empty_title(self, children: list[Token]) -> _Item:
        return _Item(_end(children), lambda span: Title("", False, span))

    def blank_line(self, children: list[Token]) -> _Item:
        return _Item(_end(children), BlankLine)

    def comment_line(self, children: list[Token]) -> _Item:
        text = str(children[0])
        return _Item(_end(children), lambda span: CommentLine(text, span))

    def title_stmt(self, children: list[Token]) -> _Item:
        text = next((str(token) for token in children if token.type == "TITLE_ARG"), "")
        return _Item(_end(children), lambda span: TitleDirective(text, span))

    def rest(self, children: list[Token]) -> _Rest:
        parts = [token for token in children if token.type in {"TEXT", "QUOTED"}]
        text_end = parts[-1].end_pos if parts else None
        return _Rest(text_end, _comment_spans(children))

    line_rest = rest

    def unknown_stmt(self, children: list[Any]) -> _Item:
        name, raw, comments = self._statement(children)
        return _Item(_end(children), lambda span: UnknownDirective(name, raw, span, comments))

    def include_stmt(self, children: list[Any]) -> _Item:
        _, raw, comments = self._statement(children)
        return _Item(_end(children), lambda span: OpaqueStatement("include", raw, span, comments))

    def lib_stmt(self, children: list[Any]) -> _Item:
        _, raw, comments = self._statement(children)
        return _Item(_end(children), lambda span: OpaqueStatement("lib", raw, span, comments))

    def control_block(self, children: list[Any]) -> _Item:
        return _Item(_end(children), lambda span: OpaqueBlock("control", span))

    def if_block(self, children: list[Any]) -> _Item:
        return _Item(_end(children), lambda span: OpaqueBlock("if", span))

    def control_line(self, children: list[Any]) -> None:
        return None

    def if_line(self, children: list[Any]) -> None:
        return None

    def end(self, children: list[Any]) -> tuple[_Item, ...]:
        end_item = _Item(_end(children), End)
        trailer_items = tuple(child for child in children if isinstance(child, _Item))
        return (end_item, *trailer_items)

    # Lark prefixes aliases that come from an imported grammar with the module name.
    core__explicit_title = explicit_title
    core__implicit_title = implicit_title
    core__empty_title = empty_title
    core__blank_line = blank_line
    core__comment_line = comment_line
    core__end = end

    # Element fields (decision 0004). Each is "gap, then field"; a longer gap nests the field.

    def node(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: Node(str(token), _span(token)))

    def r_value(self, children: list[Any]) -> _Field:
        return self._field(children, self._value)

    c_value = r_value
    value = r_value

    def param(self, children: list[Any]) -> _Field:
        def build(name: Token) -> ParamAssignment:
            # [gap] WORD EQ value: the value is the last token.
            value = self._value(children[-1])
            name_span = _span(name)
            return ParamAssignment(
                str(name), value, Span(name_span.start, value.span.end), name_span
            )

        return self._field(children, build)

    x_param = param

    def model(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: ModelReference(str(token), _span(token)))

    def flag(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: Flag(str(token), _span(token)))

    def inductor_ref(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: ElementReference(str(token), _span(token)))

    def x_name(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: token)

    def r_keyword_value(self, children: list[Any]) -> _Field:
        def build(keyword: Token) -> _KeywordValue:
            return _KeywordValue(str(keyword), self._value(children[-1]))

        return self._field(children, build)

    c_keyword_value = r_keyword_value
    l_keyword_value = r_keyword_value

    def dc_keyword(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _DcKeyword())

    def dc_spec(self, children: list[Any]) -> _Field:
        keyword = children[0] if len(children) == 2 else None
        value: _Field = children[-1]
        assert isinstance(value.node, NumericValue | Formula)
        comments = (*(keyword.comments if keyword else ()), *value.comments)
        return _Field(_Dc(value.node, keyword is not None), comments)

    def ac_spec(self, children: list[Any]) -> _Field:
        # [gap] AC_KW value, or a gap token and a nested ac_spec; both end in a _Field.
        inner: _Field = children[-1]
        comments = (*_comment_spans(children), *inner.comments)
        if isinstance(inner.node, _AcMagnitude):
            return _Field(inner.node, comments)
        assert isinstance(inner.node, NumericValue | Formula)
        keyword = _field_token(children)
        return _Field(_AcMagnitude(inner.node, _span(keyword).start), comments)

    def eol(self, children: list[Any]) -> _Eol:
        inner = children[-1]
        if isinstance(inner, _Eol):
            return _Eol(inner.end, (*_comment_spans(children), *inner.comments))
        return _Eol(_end(children), _comment_spans(children))

    # Forms that are recognised only to be rejected (NG-UNS-001).

    def stimulus(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        name = str(keyword).upper()
        kind = "distortion input" if name.startswith("DISTOF") else "function"
        raise self._unsupported(keyword, f"ngspice {name} source {kind}")

    def charge(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        raise self._unsupported(keyword, "ngspice behavioral capacitor charge form (q=)")

    def params_keyword(self, children: list[Any]) -> NoReturn:
        raise self._parse_error(
            _field_token(children),
            "`params:` is not ngspice syntax for a subcircuit call; write the parameters as "
            "name=value after the subcircuit name",
        )

    # Elements.

    def resistor(self, children: list[Any]) -> _Item:
        return self._two_terminal(Resistor, _Element(children))

    def capacitor(self, children: list[Any]) -> _Item:
        return self._two_terminal(Capacitor, _Element(children))

    def inductor(self, children: list[Any]) -> _Item:
        return self._two_terminal(Inductor, _Element(children))

    def mutual_coupling(self, children: list[Any]) -> _Item:
        element = _Element(children)
        value = element.values()[0]
        return _Item(
            element.end,
            lambda span: MutualCoupling(
                **_common(element, span, nodes=()),
                inductors=element.all(ElementReference),
                value=value,
            ),
        )

    def voltage_source(self, children: list[Any]) -> _Item:
        return self._source_item(VoltageSource, _Element(children))

    def current_source(self, children: list[Any]) -> _Item:
        return self._source_item(CurrentSource, _Element(children))

    def diode(self, children: list[Any]) -> _Item:
        element = _Element(children)
        model = element.all(ModelReference)[0]
        return _Item(
            element.end,
            lambda span: Diode(**_common(element, span), model=model, flags=element.all(Flag)),
        )

    def subckt_instance(self, children: list[Any]) -> _Item:
        element = _Element(children)
        rest = element.all(_XRest)[0]
        nodes = (*element.all(Node), *rest.nodes)
        return _Item(
            element.end,
            lambda span: SubcktInstance(
                **_common(element, span, nodes=nodes, params=rest.params),
                subckt=rest.subckt,
            ),
        )

    def x_node(self, children: list[Any]) -> _XRest:
        name: _Field = children[0]
        assert isinstance(name.node, Token)
        rest: _XRest = children[-1]
        return _XRest(
            (Node(str(name.node), _span(name.node)), *rest.nodes),
            rest.subckt,
            rest.params,
            (*name.comments, *rest.comments),
            rest.end,
        )

    def x_last(self, children: list[Any]) -> _XRest:
        element = _Element([None, *children])
        name = element.fields[0]
        assert isinstance(name, Token)
        subckt = SubcktReference(str(name), _span(name))
        return _XRest((), subckt, element.all(ParamAssignment), element.comments, element.end)

    # Helpers.

    def _field(self, children: list[Any], build: Callable[[Token], object]) -> _Field:
        if len(children) == 2 and isinstance(children[1], Token):
            # The common case: one separator, then the field token.
            return _Field(build(children[1]), ())
        comments = _comment_spans(children)
        inner = children[-1]
        if isinstance(inner, _Field):
            return _Field(inner.node, (*comments, *inner.comments))
        return _Field(build(_field_token(children)), comments)

    def _value(self, token: Token) -> Value:
        if token.type in _FORMULA_DELIMITERS:
            span = _span(token)
            # The grammar guarantees exactly one delimiter character at each end of the token.
            text = self._source.text[span.start + 1 : span.end - 1]
            return Formula(text, _FORMULA_DELIMITERS[token.type], span)
        if token.type in _RKM_TERMINALS:
            return self._rkm_value(token)
        return NumericValue(str(token), _span(token))

    def _rkm_value(self, token: Token) -> NumericValue:
        if token.type == "RKM_R_MILLI":
            raise self._parse_error(
                token,
                f"`{token}`: lowercase `m` is not an RKM code for a resistor; write `L` for "
                "milli (for example `4L7`) or use standard notation",
            )
        if not self._rkm:
            raise self._parse_error(
                token,
                f"`{token}` is RKM notation, which is accepted only with parse(..., rkm=True); "
                "ngspice reads it only in LT compatibility mode",
            )
        return NumericValue(str(token), _span(token), "rkm", token.type in _RKM_SOLVER_MISMATCH)

    def _two_terminal(
        self, kind: type[Resistor | Capacitor | Inductor], element: _Element
    ) -> _Item:
        keyword_value = element.optional(_KeywordValue)
        value: Value | None
        keyword: str | None
        if keyword_value is not None:
            value, keyword = keyword_value.value, keyword_value.keyword
        else:
            value = next(iter(element.values()), None)
            keyword = None
        model = element.optional(ModelReference)
        return _Item(
            element.end,
            lambda span: kind(
                **_common(element, span),
                value=value,
                value_keyword=keyword,
                model=model,
            ),
        )

    def _source_item(self, kind: type[VoltageSource | CurrentSource], element: _Element) -> _Item:
        dc = element.optional(_Dc)
        magnitude = element.optional(_AcMagnitude)
        ac = None
        if magnitude is not None:
            # A plain value after the AC magnitude is its phase (the grammar allows no other).
            phase = next(iter(element.values()), None)
            end = (phase or magnitude.value).span.end
            ac = AcSpec(magnitude.value, phase, Span(magnitude.start, end))
        return _Item(
            element.end,
            lambda span: kind(
                **_common(element, span, params=()),
                dc=dc.value if dc is not None else None,
                dc_keyword=dc.keyword if dc is not None else False,
                ac=ac,
            ),
        )

    def _parse_error(self, token: Token, reason: str) -> ParseError:
        source = self._source
        offset = _span(token).start
        line, column = source.position(offset)
        return ParseError(line, column, source.excerpt(offset), (), reason)

    def _unsupported(self, token: Token, construct: str) -> UnsupportedConstruct:
        source = self._source
        offset = _span(token).start
        line, column = source.position(offset)
        return UnsupportedConstruct(construct, line, column, source.excerpt(offset))

    def _statement(self, children: list[Any]) -> tuple[str, str, tuple[Span, ...]]:
        name, rest = children[0], children[1]
        raw = self._source.text[name.start_pos : rest.text_end or name.end_pos]
        return str(name), raw, rest.comments


def _common(
    element: _Element,
    span: Span,
    *,
    nodes: tuple[Node, ...] | None = None,
    params: tuple[ParamAssignment, ...] | None = None,
) -> dict[str, Any]:
    return {
        "designator": str(element.designator),
        "designator_span": _span(element.designator),
        "nodes": element.all(Node) if nodes is None else nodes,
        "params": element.all(ParamAssignment) if params is None else params,
        "span": span,
        "trailing_comments": element.comments,
    }


def parse(source: SourceText, dialect: Dialect, *, rkm: bool = False) -> ParseResult:
    """Parse ``source`` with the strict grammar of ``dialect``.

    The dialect is required: there is no default and no auto-detection. An empty source, a
    missing ``.end`` or any syntax the grammar does not accept raises ``ParseError``. An element
    letter that is not supported yet, a source stimulus function, ``DISTOF`` and the charge form
    ``q=`` of a capacitor raise ``UnsupportedConstruct``.

    ``rkm=True`` accepts RKM values (``2k7``, ``4R7``, ``4p7``) for resistors and capacitors,
    read per IEC 60062; without it they raise ``ParseError``. The option does not change the
    grammar, and standard notation parses the same either way (decision 0004).

    The whole source is parsed first, so a syntax error anywhere is reported before an RKM
    value, an unsupported form or ``params:`` that the transformer rejects.
    """
    tree = parse_tree(source, dialect)
    try:
        return _NodeBuilder(source, rkm=rkm).transform(tree)
    except VisitError as error:
        if isinstance(error.orig_exc, ParseError | UnsupportedConstruct):
            raise error.orig_exc from None
        raise
