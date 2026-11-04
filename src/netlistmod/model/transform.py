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
``params:``, bare ``.param`` expressions, reserved parameter names, a port named ``0``, the
statements not allowed in a subcircuit and, in LTspice, a bare name for a value, the nonlinear
inductor forms and ``.machine``) raise here, at the position of their token (P13 (c)).

Typed dot-commands (decision 0005) use the same field rules, with the keyword in the place of
the designator. A subcircuit definition is an item whose body items tile the text between its
header and its ``.ends`` line.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, Literal, NoReturn, TypeVar

from lark import Token, Transformer, v_args
from lark.exceptions import VisitError
from lark.tree import Meta

from netlistmod.dialects import Dialect
from netlistmod.errors import ParseError, UnsupportedConstruct
from netlistmod.grammar.loader import parse_tree
from netlistmod.model.nodes import (
    AcDirective,
    BlankLine,
    BodyItem,
    Capacitor,
    CommentLine,
    CurrentSource,
    DcDirective,
    DcSweep,
    Diode,
    End,
    EndsLine,
    GlobalDirective,
    IcDirective,
    Inductor,
    MeasureDirective,
    ModelStatement,
    MutualCoupling,
    Node,
    NodeCondition,
    NodesetDirective,
    OpaqueBlock,
    OpaqueStatement,
    OpDirective,
    OptionItem,
    OptionsDirective,
    OutputVector,
    ParamStatement,
    ParseResult,
    Resistor,
    SaveDirective,
    SourceSpec,
    StepDirective,
    SubcktDefinition,
    SubcktInstance,
    TempDirective,
    Title,
    TitleDirective,
    TopLevelItem,
    TranDirective,
    UnknownDirective,
    VoltageSource,
)
from netlistmod.model.values import (
    AcSpec,
    ElementReference,
    Flag,
    Formula,
    Identifier,
    ModelReference,
    NumericValue,
    ParamAssignment,
    SubcktReference,
    Value,
    ValueList,
)
from netlistmod.source import SourceText, Span

_T = TypeVar("_T")

_FORMULA_DELIMITERS: dict[str, Literal["{", "'", '"']] = {
    "BRACE_FORMULA": "{",
    "QUOTE_FORMULA": "'",
    "STRING_VALUE": '"',
}
_RKM_TERMINALS = frozenset({"RKM_R", "RKM_R_MEGA", "RKM_R_MILLI", "RKM_C", "RKM_C_FARAD"})
_EMBEDDED = "EMBEDDED"  # the LTspice embedded decimal, always LTspice's own reading
_BARE_FORMULA = "BARE_FORMULA"
# Which function takes each fn_param (ngspice manual §4.1.4, §4.1.9; LTspice reference, WAV File).
_FN_PARAM_OWNERS = {"r": "pwl", "td": "pwl", "m": "external", "chan": "wavefile"}
# Text kept as a value and never read: the value of mfg, pn or type, the only parameters whose
# grammar offers WORD; a file's path; a trigger expression.
_TEXT_VALUES = frozenset({"WORD", "FILE_PATH", "TRIGGER_EXPR"})
_MODEL_BARE = "MODEL_BARE"
_STEP_VARIATIONS = frozenset({"DEC_KW", "OCT_KW", "LIN_KW"})
# RKM terminals that ngspice reads differently from IEC 60062 (decision 0004).
_RKM_SOLVER_MISMATCH = frozenset({"RKM_R_MEGA", "RKM_C_FARAD"})
# Field tokens: the token of a field rule that is neither a separator nor a comment.
_GAP_TERMINALS = frozenset({"SEP", "CSEP", "BS_CONT", "TRAILING_COMMENT", "EQ"})
# Names that §2.11.1 reserves and a .param assignment may not define.
_RESERVED_PARAMS = frozenset({"TIME_KW", "TEMPER_KW", "HERTZ_KW"})
_BARE_EXPRESSION = (
    "bare expression in `.param`: write the expression in braces (`{...}`) or single quotes"
)


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
class _ListKeyword:
    """The ``list`` keyword of an LTspice ``.ac``, ``.dc`` or ``.step``."""

    span: Span


@dataclass(frozen=True, slots=True)
class _FileArgument:
    """``file=name`` of an LTspice ``.ac``, ``.dc`` or ``.step``."""

    keyword: Token
    name: Identifier


@dataclass(frozen=True, slots=True)
class _ParamsMarker:
    """An LTspice ``params:``, which adds nothing to the node."""


@dataclass(frozen=True, slots=True)
class _StepItem:
    """The swept quantity of ``.step param name`` or ``.step temp``."""

    kind: Literal["param", "temp"]
    token: Token


@dataclass(frozen=True, slots=True)
class _StepModelRef:
    """``2N2222(VAF)``: one token holding the model name and the parameter."""

    name: str
    span: Span
    model: ModelReference


@dataclass(frozen=True, slots=True)
class _StepSweep:
    """The sweep of a ``.step``: a range, a list, or a file."""

    values: tuple[Value, ...]
    listed: bool
    file: Identifier | None


@dataclass(frozen=True, slots=True)
class _FnList:
    """The list of a source function: its values, where it ends, and its comments."""

    args: tuple[Value, ...]
    end: int
    comments: tuple[Span, ...]


@dataclass(frozen=True, slots=True)
class _Forever:
    """``FOREVER`` in a PWL repeat."""

    span: Span


@dataclass(frozen=True, slots=True)
class _SpecParam:
    """A parameter of the source function before it, not of the line."""

    param: ParamAssignment


@dataclass(frozen=True, slots=True)
class _DistortionHead:
    """``DISTOF1`` or ``DISTOF2``; the plain values after it are its magnitude and phase."""

    token: Token


@dataclass(frozen=True, slots=True)
class _Eol:
    end: int
    comments: tuple[Span, ...]


@dataclass(frozen=True, slots=True)
class _Tail:
    """A last field whose rule also holds the end of the statement."""

    field: _Field
    end: int
    comments: tuple[Span, ...]


@dataclass(frozen=True, slots=True)
class _Bare:
    """A bare ``.param`` expression, recognised only to be rejected; ``span`` covers its text."""

    span: Span


@dataclass(frozen=True, slots=True)
class _ModelParams:
    """The parenthesized parameter list of a ``.model`` line and its parenthesis tokens."""

    params: tuple[ParamAssignment, ...]
    open_span: Span
    close_span: Span


@dataclass(frozen=True, slots=True)
class _RParen:
    span: Span


@dataclass(frozen=True, slots=True)
class _MeasBody:
    text: str
    span: Span


@dataclass(frozen=True, slots=True)
class _Header:
    """A ``.subckt`` line: its fields and comments, and where it ends."""

    element: _Element


@dataclass(frozen=True, slots=True)
class _Ends:
    name: Token | None
    comments: tuple[Span, ...]
    end: int


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


def _statement_end(terminator: Token | _Eol) -> tuple[int, tuple[Span, ...]]:
    """Where a statement ends and the comments of its end, from its NL token or ``eol``."""
    if isinstance(terminator, _Eol):
        return terminator.end, terminator.comments
    return _end([terminator]), ()


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
            elif isinstance(child, _Tail):
                self.fields.append(child.field.node)
                comments.extend((*child.field.comments, *child.comments))
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

    def __init__(self, source: SourceText, dialect: Dialect, *, rkm: bool = False) -> None:
        super().__init__()
        self._source = source
        self._dialect = dialect
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
        return ParseResult(tuple(items), self._dialect)

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
        name_span = _span(children[0])
        return _Item(
            _end(children), lambda span: UnknownDirective(name, raw, span, comments, name_span)
        )

    top_unknown_stmt = unknown_stmt

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

    def lib_block(self, children: list[Any]) -> _Item:
        return _Item(_end(children), lambda span: OpaqueBlock("lib", span))

    def control_line(self, children: list[Any]) -> None:
        return None

    def if_line(self, children: list[Any]) -> None:
        return None

    def lib_line(self, children: list[Any]) -> None:
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
            value = self._param_value(children[-1])
            name_span = _span(name)
            return ParamAssignment(
                str(name), value, Span(name_span.start, value.span.end), name_span
            )

        return self._field(children, build)

    x_param = param
    r_param = param
    c_param = param
    l_param = param
    v_param = param
    port_param = param
    trigger_param = param
    d_param = param
    resistive_load = param

    def tc_param(self, children: list[Any]) -> _Field:
        def build(name: Token) -> ParamAssignment:
            # [gap] TC_KW EQ value (CSEP value)*: every token after the name is a value.
            values = tuple(self._value(token) for token in _field_tokens(children)[1:])
            name_span = _span(name)
            span = Span(values[0].span.start, values[-1].span.end)
            return ParamAssignment(
                str(name),
                ValueList(self._source.text[span.start : span.end], values, span),
                Span(name_span.start, span.end),
                name_span,
            )

        return self._field(children, build)

    def params_marker(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _ParamsMarker())

    def load_flag(self, children: list[Any]) -> _Field:
        return self.flag(children)

    noiseless_flag = load_flag

    def model(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: ModelReference(str(token), _span(token)))

    def flag(self, children: list[Any]) -> _Field:
        def build(name: Token) -> Flag:
            # [gap] keyword, or (LTspice) [gap] keyword EQ value.
            tokens = _field_tokens(children)
            if len(tokens) == 1:
                return Flag(str(name), _span(name))
            value = self._value(tokens[-1])
            return Flag(str(name), Span(_span(name).start, value.span.end), value)

        return self._field(children, build)

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
        # [gap] AC_KW value, or a gap token and a nested ac_spec; both end in a _Field. LTspice
        # also has [gap] AC_KW EQ value, which ends in the value's token.
        if isinstance(children[-1], Token):
            magnitude = self._value(children[-1])
            start = _span(_field_token(children)).start
            return _Field(_AcMagnitude(magnitude, start), _comment_spans(children))
        inner: _Field = children[-1]
        comments = (*_comment_spans(children), *inner.comments)
        if isinstance(inner.node, _AcMagnitude):
            return _Field(inner.node, comments)
        assert isinstance(inner.node, NumericValue | Formula)
        keyword = _field_token(children)
        return _Field(_AcMagnitude(inner.node, _span(keyword).start), comments)

    dc_after = dc_spec

    def eol(self, children: list[Any]) -> _Eol:
        inner = children[-1]
        if isinstance(inner, _Eol):
            return _Eol(inner.end, (*_comment_spans(children), *inner.comments))
        return _Eol(_end(children), _comment_spans(children))

    # Source functions (decision 0013).

    def stimulus(self, children: list[Any]) -> _Field:
        inner = children[-1]
        if isinstance(inner, _Field) and isinstance(inner.node, SourceSpec):
            return _Field(inner.node, (*_comment_spans(children), *inner.comments))
        name = _field_token(children)
        args: tuple[Value, ...] = ()
        params: list[ParamAssignment] = []
        comments = list(_comment_spans(children))
        end = _span(name).end
        forever = False
        for child in children:
            if isinstance(child, _FnList):
                args, end = child.args, child.end
                comments.extend(child.comments)
            elif isinstance(child, _Field):
                comments.extend(child.comments)
                if isinstance(child.node, ParamAssignment):
                    params.append(child.node)
                    end = child.node.span.end
                elif isinstance(child.node, _Forever):
                    forever = True
                    end = child.node.span.end
                elif isinstance(child.node, _RParen):
                    end = child.node.span.end
        return _Field(
            SourceSpec(
                str(name), _span(name), args, tuple(params), Span(_span(name).start, end), forever
            ),
            tuple(comments),
        )

    pwl_stimulus = stimulus
    table_stimulus = stimulus
    step_stimulus = stimulus

    def wave_stimulus(self, children: list[Any]) -> _Field:
        inner = children[-1]
        if isinstance(inner, _Field):
            return _Field(inner.node, (*_comment_spans(children), *inner.comments))
        name, path = _field_tokens(children)
        value = self._param_value(path)
        span = Span(_span(name).start, value.span.end)
        assignment = ParamAssignment(str(name), value, span, _span(name))
        return _Field(
            SourceSpec(str(name), _span(name), (), (assignment,), span), _comment_spans(children)
        )

    def fn_list(self, children: list[Any]) -> _FnList:
        inner = children[-1]
        if isinstance(inner, _FnList):
            return _FnList(inner.args, inner.end, (*_comment_spans(children), *inner.comments))
        fields = [child for child in children if isinstance(child, _Field)]
        close = fields[-1].node
        assert isinstance(close, _RParen)
        comments = tuple(comment for field in fields for comment in field.comments)
        args = tuple(field.node for field in fields[:-1])
        return _FnList(args, close.span.end, comments)  # type: ignore[arg-type]

    def fn_first(self, children: list[Any]) -> _Field:
        return self._field(children, self._value)

    fn_arg = fn_first

    def pwl_factor(self, children: list[Any]) -> _Field:
        return self.param(children)

    pwl_file = pwl_factor

    def pwl_repeat(self, children: list[Any]) -> _Field:
        inner = children[-1]
        if isinstance(inner, _Field):
            return _Field(inner.node, (*_comment_spans(children), *inner.comments))
        tokens = _field_tokens(children)
        if tokens[-1].type == "FOREVER_KW":
            return _Field(_Forever(_span(tokens[-1])), _comment_spans(children))
        keyword, value_token = tokens[-2:]
        value = self._value(value_token)
        span = Span(_span(keyword).start, value.span.end)
        return _Field(
            ParamAssignment(str(keyword), value, span, _span(keyword)), _comment_spans(children)
        )

    def pwl_endrepeat(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _RParen(_span(token)))

    def fn_param(self, children: list[Any]) -> _Field:
        inner = children[-1]
        if isinstance(inner, _Field):
            return _Field(inner.node, (*_comment_spans(children), *inner.comments))
        field = self.param(children)
        assert isinstance(field.node, ParamAssignment)
        return _Field(_SpecParam(field.node), field.comments)

    def external_kw(self, children: list[Any]) -> _Field:
        return self._field(
            children,
            lambda token: SourceSpec(str(token), _span(token), (), (), _span(token)),
        )

    def distof1_kw(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _DistortionHead(token))

    distof2_kw = distof1_kw

    # Forms that are recognised only to be rejected (NG-UNS-001).

    def charge(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        construct = f"{self._dialect.display_name} behavioral capacitor charge form (q=)"
        raise self._unsupported(keyword, construct)

    def params_keyword(self, children: list[Any]) -> NoReturn:
        raise self._parse_error(
            _field_token(children),
            "`params:` is not ngspice syntax for subcircuit parameters; write them as "
            "name=value without `params:`",
        )

    def bare_name(self, children: list[Any]) -> NoReturn:
        name = _field_token(children)
        raise self._parse_error(
            name,
            f"`{name}` is not an LTspice value: LTspice reads a bare name as a model, and R, C "
            "and L take no model. Write a number or a brace expression (`{...}`)",
        )

    def nonlinear_inductor(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        raise self._unsupported(keyword, f"LTspice nonlinear inductor form ({keyword}=)")

    def machine_block(self, children: list[Any]) -> NoReturn:
        raise self._unsupported(children[0], "LTspice .machine state machine")

    def machine_line(self, children: list[Any]) -> None:
        return None

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
        area = next(iter(element.values()), None)
        return _Item(
            element.end,
            lambda span: Diode(
                **_common(element, span), model=model, flags=element.all(Flag), area=area
            ),
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

    # Statements and directives (decision 0005). The keyword stands where an element has its
    # designator, so `_Element` collects their fields too.

    def param_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        assignments = element.all(ParamAssignment)
        bare = element.optional(_Bare)
        if bare is not None:
            raise self._error_at(assignments[-1].value.span.start, _BARE_EXPRESSION)
        return _Item(
            element.end,
            lambda span: ParamStatement(**_dot(element, span), assignments=assignments),
        )

    def param_def(self, children: list[Any]) -> _Field:
        def build(name: Token) -> ParamAssignment:
            if name.type in _RESERVED_PARAMS:
                raise self._parse_error(
                    name,
                    f"`{name}` is a reserved name (time, temper, hertz) and cannot be a parameter",
                )
            value = children[-1]
            if isinstance(value, _Bare):
                raise self._error_at(value.span.start, _BARE_EXPRESSION)
            built = self._value(value)
            name_span = _span(name)
            return ParamAssignment(
                str(name), built, Span(name_span.start, built.span.end), name_span
            )

        return self._field(children, build)

    def bare_value(self, children: list[Token]) -> _Bare:
        return _Bare(Span(_span(children[0]).start, _span(children[-1]).end))

    def bare_tail(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _Bare(_span(token)))

    def model_ako(self, children: list[Any]) -> _Field:
        def build(token: Token) -> ModelReference:
            # AKO_REF is "ako:" and the base model name, one token.
            prefix = len("ako:")
            start = _span(token).start + prefix
            return ModelReference(str(token)[prefix:], Span(start, _span(token).end))

        return self._field(children, build)

    def model_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        name, model_type = element.all(Token)[:2]
        ako = element.optional(ModelReference)
        paren = element.optional(_ModelParams)
        params = paren.params if paren is not None else element.all(ParamAssignment)
        return _Item(
            element.end,
            lambda span: ModelStatement(
                **_dot(element, span),
                name=str(name),
                name_span=_span(name),
                model_type=str(model_type),
                model_type_span=_span(model_type),
                params=params,
                parenthesized=paren is not None,
                open_paren_span=paren.open_span if paren is not None else None,
                close_paren_span=paren.close_span if paren is not None else None,
                ako=ako,
            ),
        )

    def model_paren(self, children: list[Any]) -> _Field:
        fields = [child for child in children if isinstance(child, _Field)]
        comments = (*_comment_spans(children), *(c for f in fields for c in f.comments))
        inner = fields[-1].node
        if isinstance(inner, _ModelParams):
            # A gap before the parenthesis: the list is the nested field.
            return _Field(inner, comments)
        params = tuple(f.node for f in fields if isinstance(f.node, ParamAssignment))
        assert isinstance(inner, _RParen)  # the grammar ends the list with rparen
        open_paren = next(c for c in children if isinstance(c, Token) and c.type == "LPAR")
        return _Field(_ModelParams(params, _span(open_paren), inner.span), comments)

    model_param_first = param

    def rparen(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _RParen(_span(token)))

    def subckt_def(self, children: list[Any]) -> _Item:
        header: _Header = children[0]
        items: list[_Item] = children[1:-1]
        ends: _Ends = children[-1]
        element = header.element
        name = element.all(Token)[0]

        def build(span: Span) -> SubcktDefinition:
            body: list[BodyItem] = []
            cursor = element.end
            for item in items:
                built = item.build(Span(cursor, item.end))
                assert not isinstance(built, Title | TitleDirective | End)
                body.append(built)  # type: ignore[arg-type]
                cursor = item.end
            ends_name = ends.name
            return SubcktDefinition(
                **_dot(element, span),
                name=str(name),
                name_span=_span(name),
                ports=element.all(Node),
                params=element.all(ParamAssignment),
                body=tuple(body),
                ends=EndsLine(
                    str(ends_name) if ends_name is not None else None,
                    _span(ends_name) if ends_name is not None else None,
                    Span(cursor, ends.end),
                    ends.comments,
                ),
                header_span=Span(span.start, element.end),
            )

        return _Item(ends.end, build)

    def subckt_header(self, children: list[Any]) -> _Header:
        return _Header(_Element(children))

    def subckt_port(self, children: list[Any]) -> _Field:
        def build(token: Token) -> Node:
            if token.type == "ZERO_PORT":
                raise self._parse_error(
                    token, "a subcircuit port cannot be `0` (ground); ports are external nodes"
                )
            return Node(str(token), _span(token))

        return self._field(children, build)

    @v_args(meta=True)
    def not_in_subckt(self, meta: Meta, children: list[Any]) -> NoReturn:
        keyword = str(children[0]) if isinstance(children[0], Token) else ".control"
        raise self._error_at(
            meta.start_pos,
            f"`{keyword}` is not allowed inside a subcircuit definition (`.subckt` ... `.ends`)",
        )

    def ends_line(self, children: list[Any]) -> _Ends:
        element = _Element(children)
        return _Ends(element.optional(Token), element.comments, element.end)

    def tran_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        values = element.values()
        # LTspice's `.tran 1m` holds only tstop; the grammar requires both otherwise.
        tstep, tstop = (None, values[0]) if len(values) == 1 else (values[0], values[1])
        return _Item(
            element.end,
            lambda span: TranDirective(
                **_dot(element, span),
                tstep=tstep,
                tstop=tstop,
                tstart=values[2] if len(values) > 2 else None,
                tmax=values[3] if len(values) > 3 else None,
                uic=element.optional(Flag),
                modifiers=element.all(OptionItem),
            ),
        )

    uic = flag

    def tran_modifier(self, children: list[Any]) -> _Field:
        def build(name: Token) -> OptionItem:
            tokens = _field_tokens(children)
            value = self._value(tokens[-1]) if len(tokens) > 1 else None
            name_span = _span(name)
            end = value.span.end if value is not None else name_span.end
            return OptionItem(str(name), name_span, value, Span(name_span.start, end))

        return self._field(children, build)

    def ac_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        file = element.optional(_FileArgument)
        listed = element.optional(_ListKeyword)
        values = element.values()
        if file is not None:
            variation_span = _span(file.keyword)
        elif listed is not None:
            variation_span = listed.span
        else:
            variation_span = _span(element.all(Token)[0])
        variation = self._source.text[variation_span.start : variation_span.end]
        ranged = file is None and listed is None
        return _Item(
            element.end,
            lambda span: AcDirective(
                **_dot(element, span),
                variation=variation,
                variation_span=variation_span,
                points=values[0] if ranged else None,
                fstart=values[1] if ranged else None,
                fstop=values[2] if ranged else None,
                frequencies=values if listed is not None else (),
                file=file.name if file is not None else None,
            ),
        )

    def ac_variation(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: token)

    def list_keyword(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _ListKeyword(_span(token)))

    def file_argument(self, children: list[Any]) -> _Field:
        def build(keyword: Token) -> _FileArgument:
            name: Token = children[-1]
            return _FileArgument(keyword, Identifier(str(name), _span(name)))

        return self._field(children, build)

    meas_analysis = ac_variation

    def dc_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        sweeps = element.all(DcSweep)
        return _Item(element.end, lambda span: DcDirective(**_dot(element, span), sweeps=sweeps))

    def dc_sweep(self, children: list[_Field]) -> _Field:
        tokens = [child.node for child in children if isinstance(child.node, Token)]
        variation = tokens[0] if len(tokens) == 2 else None
        source = tokens[-1]
        assert isinstance(source, Token)
        values = tuple(
            child.node for child in children if isinstance(child.node, NumericValue | Formula)
        )
        listed = any(isinstance(child.node, _ListKeyword) for child in children)
        file = next((c.node.name for c in children if isinstance(c.node, _FileArgument)), None)
        ranged = not listed and file is None
        last = file if file is not None else values[-1]
        sweep = DcSweep(
            str(source),
            _span(source),
            values[0] if ranged else None,
            values[1] if ranged else None,
            values[2] if ranged else None,
            Span(_span(source).start, last.span.end),
            str(variation) if variation is not None else None,
            values if listed else (),
            file,
        )
        return _Field(sweep, tuple(c for child in children for c in child.comments))

    def dc_list_sweep(self, children: list[Any]) -> _Tail:
        # The statement's end is part of this rule: a value list is not delimited (LALR).
        return _Tail(self.dc_sweep(children[:-1]), *_statement_end(children[-1]))

    def op_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        return _Item(element.end, lambda span: OpDirective(**_dot(element, span)))

    def options_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        options = element.all(OptionItem)
        return _Item(
            element.end, lambda span: OptionsDirective(**_dot(element, span), options=options)
        )

    def option_item(self, children: list[Any]) -> _Field:
        def build(name: Token) -> OptionItem:
            tokens = _field_tokens(children)
            value: Value | Identifier | None = None
            if len(tokens) > 1:
                token = tokens[-1]
                value = (
                    Identifier(str(token), _span(token))
                    if token.type == "WORD"
                    else self._value(token)
                )
            name_span = _span(name)
            end = value.span.end if value is not None else name_span.end
            return OptionItem(str(name), name_span, value, Span(name_span.start, end))

        return self._field(children, build)

    def temp_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        values = element.values()
        return _Item(
            element.end,
            lambda span: TempDirective(**_dot(element, span), value=values[0], others=values[1:]),
        )

    def ic_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        conditions = element.all(NodeCondition)
        return _Item(
            element.end, lambda span: IcDirective(**_dot(element, span), conditions=conditions)
        )

    def nodeset_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        conditions = element.all(NodeCondition)
        return _Item(
            element.end,
            lambda span: NodesetDirective(**_dot(element, span), conditions=conditions),
        )

    def node_condition(self, children: list[Any]) -> _Field:
        def build(opener: Token) -> NodeCondition:
            # v( node ) = value: the node is the second field token, the value the last.
            tokens = _field_tokens(children)
            value = self._value(tokens[-1])
            node = Node(str(tokens[1]), _span(tokens[1])) if opener.type == "V_OPEN" else None
            return NodeCondition(node, value, Span(_span(opener).start, value.span.end))

        return self._field(children, build)

    nodeset_all = node_condition

    def current_condition(self, children: list[Any]) -> _Field:
        def build(opener: Token) -> NodeCondition:
            # i( L_REF ) = value: the inductor is the second field token, the value the last.
            tokens = _field_tokens(children)
            value = self._value(tokens[-1])
            current = ElementReference(str(tokens[1]), _span(tokens[1]))
            span = Span(_span(opener).start, value.span.end)
            return NodeCondition(None, value, span, current)

        return self._field(children, build)

    def save_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        vectors = element.all(OutputVector)
        return _Item(
            element.end, lambda span: SaveDirective(**_dot(element, span), vectors=vectors)
        )

    def output_vector(self, children: list[Any]) -> _Field:
        inner = children[-1]
        if isinstance(inner, OutputVector):
            # [gap] voltage_vector or current_vector: one separator, no comments.
            return _Field(inner, ())
        return self._field(children, lambda token: OutputVector(str(token), _span(token)))

    def voltage_vector(self, children: list[Token]) -> OutputVector:
        opener, *names = _field_tokens(children)[:-1]
        span = Span(_span(opener).start, _span(children[-1]).end)
        return OutputVector(
            self._source.text[span.start : span.end],
            span,
            function=str(opener)[:-1],
            nodes=tuple(Node(str(name), _span(name)) for name in names),
        )

    def current_vector(self, children: list[Token]) -> OutputVector:
        opener, *names = _field_tokens(children)[:-1]
        function = str(opener)[:-1]
        if names[0].type == "SAVE_PATTERN":
            # A wildcard or hierarchical name (LTspice) refers to no single element.
            span = Span(_span(opener).start, _span(children[-1]).end)
            return OutputVector(self._source.text[span.start : span.end], span, function=function)
        if opener.type == "CURRENT_VARIANT_OPEN":
            raise self._parse_error(
                opener,
                f"`{function}(...)` is not implemented in ngspice (ngspice manual §11.6.2); "
                "save `i(...)` instead",
            )
        if len(names) > 1:
            raise self._parse_error(names[1], "`i(...)` takes one source name")
        span = Span(_span(opener).start, _span(children[-1]).end)
        return OutputVector(
            self._source.text[span.start : span.end],
            span,
            function=function,
            source=ElementReference(str(names[0]), _span(names[0])),
        )

    def meas_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        tokens = element.all(Token)
        analysis, result = (None, tokens[0]) if len(tokens) == 1 else tokens[:2]
        body = element.all(_MeasBody)[0]
        return _Item(
            element.end,
            lambda span: MeasureDirective(
                **_dot(element, span),
                analysis=str(analysis) if analysis is not None else None,
                analysis_span=_span(analysis) if analysis is not None else None,
                result=str(result),
                result_span=_span(result),
                body_text=body.text,
                body_span=body.span,
            ),
        )

    def meas_body(self, children: list[Any]) -> _Field:
        inner = children[-1]
        comments = _comment_spans(children)
        if isinstance(inner, _Field):
            return _Field(inner.node, (*comments, *inner.comments))
        # [gap] first text token, then the statement text.
        first: Token = children[-2]
        rest: _Rest = inner
        span = Span(_span(first).start, rest.text_end or _span(first).end)
        body = _MeasBody(self._source.text[span.start : span.end], span)
        return _Field(body, (*comments, *rest.comments))

    def global_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        nodes = element.all(Node)
        return _Item(element.end, lambda span: GlobalDirective(**_dot(element, span), nodes=nodes))

    def step_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        tokens = element.all(Token)
        variation = next((t for t in tokens if t.type in _STEP_VARIATIONS), None)
        item = element.optional(_StepItem)
        source = next((t for t in tokens if t.type not in _STEP_VARIATIONS), None)
        model_ref = element.optional(_StepModelRef)
        sweep = element.all(_StepSweep)[0]
        if sweep.listed and variation is not None:
            raise self._parse_error(
                variation, f"`{variation}` cannot be combined with `list` in `.step` (reference)"
            )
        name = item.token if item is not None else source
        assert name is not None
        kind: Literal["param", "source", "temp", "model"]
        if item is not None:
            kind = item.kind
        else:
            kind = "model" if model_ref is not None else "source"
        ranged = not sweep.listed and sweep.file is None
        return _Item(
            element.end,
            lambda span: StepDirective(
                **_dot(element, span),
                kind=kind,
                name=str(model_ref.name) if model_ref is not None else str(name),
                name_span=model_ref.span if model_ref is not None else _span(name),
                model_type=(Identifier(str(name), _span(name)) if model_ref is not None else None),
                model=model_ref.model if model_ref is not None else None,
                variation=str(variation) if variation is not None else None,
                variation_span=_span(variation) if variation is not None else None,
                start=sweep.values[0] if ranged else None,
                stop=sweep.values[1] if ranged else None,
                increment=sweep.values[2] if ranged else None,
                values=sweep.values if sweep.listed else (),
                file=sweep.file,
            ),
        )

    def step_param(self, children: list[Any]) -> _Field:
        comments = _comment_spans(children)
        inner: _Field = children[-1]
        if isinstance(inner.node, _StepItem):
            return _Field(inner.node, (*comments, *inner.comments))
        assert isinstance(inner.node, Token)
        return _Field(_StepItem("param", inner.node), (*comments, *inner.comments))

    def step_temp(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _StepItem("temp", token))

    def step_model_ref(self, children: list[Any]) -> _Field:
        def build(token: Token) -> _StepModelRef:
            # STEP_MODEL_REF is name(parameter), one token, so the model name is its head.
            span = _span(token)
            head = str(token).partition("(")[0]
            model = ModelReference(head, Span(span.start, span.start + len(head)))
            return _StepModelRef(str(token), span, model)

        return self._field(children, build)

    def step_sweep(self, children: list[Any]) -> _Tail:
        # The statement's end is part of this rule: a value list is not delimited (LALR).
        fields: list[_Field] = children[:-1]
        values = tuple(c.node for c in fields if isinstance(c.node, NumericValue | Formula))
        listed = any(isinstance(c.node, _ListKeyword) for c in fields)
        file = next((c.node.name for c in fields if isinstance(c.node, _FileArgument)), None)
        comments = tuple(comment for child in fields for comment in child.comments)
        sweep = _Field(_StepSweep(values, listed, file), comments)
        return _Tail(sweep, *_statement_end(children[-1]))

    step_value = r_value

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
        if token.type == _BARE_FORMULA:
            return Formula(str(token), "", _span(token))
        if token.type == _EMBEDDED:
            return NumericValue(str(token), _span(token), "rkm")
        if token.type in _RKM_TERMINALS:
            return self._rkm_value(token)
        return NumericValue(str(token), _span(token))

    def _param_value(self, token: Token) -> Value | Identifier:
        """A parameter value; an LTspice bare word stays a name, never a formula (review R8)."""
        if token.type in _TEXT_VALUES:
            return Identifier(str(token), _span(token))
        if token.type == _MODEL_BARE:
            raise self._parse_error(
                token,
                f"`{token}`: LTspice reads a bare word in this `.model` parameter as a parameter "
                f"reference; write `{{{token}}}`. Only `mfg` and `type` take a bare word",
            )
        return self._value(token)

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
                flags=element.all(Flag),
            ),
        )

    def _source_item(self, kind: type[VoltageSource | CurrentSource], element: _Element) -> _Item:
        dc = element.optional(_Dc)
        ac, stimulus, distortion = self._source_parts(element, kind)
        return _Item(
            element.end,
            lambda span: kind(
                **_common(element, span),
                dc=dc.value if dc is not None else None,
                dc_keyword=dc.keyword if dc is not None else False,
                ac=ac,
                flags=element.all(Flag),
                stimulus=stimulus,
                distortion=distortion,
            ),
        )

    def _source_parts(
        self, element: _Element, kind: type[VoltageSource | CurrentSource]
    ) -> tuple[AcSpec | None, SourceSpec | None, tuple[SourceSpec, ...]]:
        """A source line's AC part, function and distortion inputs. A plain value belongs to the
        AC magnitude or distortion keyword before it. A function's named parameter must follow it
        directly and be one that function takes, and RF port parameters are for V only: fn_param
        and port_param are one rule wherever a line allows them, so these are checked here."""
        magnitude: _AcMagnitude | None = None
        phase: Value | None = None
        stimulus: SourceSpec | None = None
        distortion: list[SourceSpec] = []
        in_ac = False
        previous: object = None
        for node in element.fields:
            if isinstance(node, _AcMagnitude):
                magnitude, in_ac = node, True
            elif isinstance(node, _DistortionHead):
                token = node.token
                distortion.append(SourceSpec(str(token), _span(token), (), (), _span(token)))
                in_ac = False
            elif isinstance(node, NumericValue | Formula):
                if in_ac:
                    phase = node
                else:
                    last = distortion[-1]
                    span = Span(last.span.start, node.span.end)
                    distortion[-1] = replace(last, args=(*last.args, node), span=span)
            elif isinstance(node, SourceSpec):
                stimulus, in_ac = node, False
            elif isinstance(node, _SpecParam):
                stimulus = self._with_param(stimulus, node.param, previous)
                in_ac = False
            elif isinstance(node, ParamAssignment):
                in_ac = False
                if self._dialect is Dialect.NGSPICE and kind is CurrentSource:
                    raise self._error_at(
                        node.name_span.start, f"`{node.name}` is for a V line (RF port parameters)"
                    )
            else:
                in_ac = False
            previous = node
        ac = None
        if magnitude is not None:
            end = (phase or magnitude.value).span.end
            ac = AcSpec(magnitude.value, phase, Span(magnitude.start, end))
        return ac, stimulus, tuple(distortion)

    def _with_param(
        self, stimulus: SourceSpec | None, param: ParamAssignment, previous: object
    ) -> SourceSpec:
        name = param.name.lower()
        function = stimulus.name.lower() if stimulus is not None else ""
        owner = _FN_PARAM_OWNERS[name]
        if stimulus is None or function != owner:
            raise self._error_at(
                param.name_span.start, f"`{param.name}=` applies only to `{owner.upper()}`"
            )
        if not isinstance(previous, SourceSpec | _SpecParam):
            raise self._error_at(
                param.name_span.start,
                f"`{param.name}=` must follow `{stimulus.name}` directly",
            )
        span = Span(stimulus.span.start, param.span.end)
        return replace(stimulus, params=(*stimulus.params, param), span=span)

    def _parse_error(self, token: Token, reason: str) -> ParseError:
        return self._error_at(_span(token).start, reason)

    def _error_at(self, offset: int, reason: str) -> ParseError:
        source = self._source
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


def _dot(element: _Element, span: Span) -> dict[str, Any]:
    """The fields of a typed dot-command; its keyword stands where an element's designator is."""
    return {
        "keyword": str(element.designator),
        "keyword_span": _span(element.designator),
        "span": span,
        "trailing_comments": element.comments,
    }


def _field_tokens(children: list[Any]) -> list[Token]:
    """The tokens of a field rule that are neither separators, comments nor ``=``."""
    return [c for c in children if isinstance(c, Token) and c.type not in _GAP_TERMINALS]


def parse(source: SourceText, dialect: Dialect, *, rkm: bool = False) -> ParseResult:
    """Parse ``source`` with the strict grammar of ``dialect``.

    The dialect is required: there is no default and no auto-detection. An empty source, a
    missing ``.end`` or any syntax the grammar does not accept raises ``ParseError``. An element
    letter that is not supported yet, a source stimulus function, ``DISTOF`` and the charge form
    ``q=`` of a capacitor raise ``UnsupportedConstruct``.

    ``rkm=True`` accepts RKM values (``2k7``, ``4R7``, ``4p7``) for ngspice resistors and
    capacitors, read per IEC 60062; without it they raise ``ParseError``. The option does not
    change the grammar, and standard notation parses the same either way (decision 0004). LTspice
    reads its embedded decimal natively, so ``rkm=True`` with ``Dialect.LTSPICE`` is a
    ``ValueError`` (decision 0009).

    The whole source is parsed first, so a syntax error anywhere is reported before an RKM
    value, an unsupported form or ``params:`` that the transformer rejects.
    """
    if not isinstance(source, SourceText):
        raise TypeError(f"parse takes a SourceText, not {type(source).__name__}")
    if rkm and dialect is Dialect.LTSPICE:
        raise ValueError(
            "rkm=True applies only to ngspice: LTspice reads its embedded decimal natively"
        )
    tree = parse_tree(source, dialect)
    try:
        return _NodeBuilder(source, dialect, rkm=rkm).transform(tree)
    except VisitError as error:
        if isinstance(error.orig_exc, ParseError | UnsupportedConstruct):
            raise error.orig_exc from None
        raise
