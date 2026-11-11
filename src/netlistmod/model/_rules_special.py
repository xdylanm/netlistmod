"""Rules for the special and mixed-signal devices (decision 0020): ngspice's code models (A) and
OSDI devices (N), a code model's ``.model`` values, and LTspice's special functions (A), frequency
response analyzer (``@``) and its probe (``&``)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal, NoReturn

from lark import Token

from netlistmod.model._rules_elements import _reads_as_number
from netlistmod.model._rules_lines import LinesRules
from netlistmod.model._tree import (
    _CodeParam,
    _comment_spans,
    _common,
    _Element,
    _Field,
    _field_token,
    _Item,
    _Name,
    _span,
)
from netlistmod.model.nodes import (
    CodeModelConnection,
    CodeModelDevice,
    CodeModelPort,
    FraProbe,
    FrequencyAnalyzer,
    Node,
    OsdiDevice,
    SpecialFunction,
)
from netlistmod.model.values import (
    ElementReference,
    Flag,
    Formula,
    Identifier,
    ModelReference,
    NumericValue,
    ParamAssignment,
    Value,
    ValueList,
)
from netlistmod.source import Span

# The analyzer parameters that take a list (reference, "@ — Frequency Response Analyzer").
_FRA_LISTS = frozenset({"flist", "pp", "nmax", "ac"})
# A comma on an LTspice A or `@` line (decision 0020 item 7, review R1): refused like a comma on
# any other LTspice element line (decision 0009). `ac=`'s magnitude and phase are the exception.
_LT_COMMA = (
    "a comma as a separator: LTspice element lines separate their fields with blanks, "
    "and the reference writes no comma on an A or `@` line; only `ac=` writes "
    "its magnitude and phase with one, `ac=1,0` (LTspice runs the comma)"
)
# The ports types of Table 8.1 whose connection is a pair of nodes.
_DIFFERENTIAL = frozenset({"%vd", "%id", "%gd", "%hd"})
# The 13 special function names, and the reference's symbols that write one of them (decision
# 0020 item 3), for the message about a name LTspice stops on.
_FUNCTIONS = (
    "BUF, AND, OR, XOR, SCHMITT, DFLOP, SRFLOP, VARISTOR, MODULATOR, OTA, PHASEDET, COUNTER and "
    "SAMPLEHOLD"
)
_SYMBOL_NAMES = {
    "inv": "BUF",
    "buf1": "BUF",
    "schmtbuf": "SCHMITT",
    "schmtinv": "SCHMITT",
    "modulate": "MODULATOR",
    "modulate2": "MODULATOR",
    "phidet": "PHASEDET",
    "sample": "SAMPLEHOLD",
    "mota": "OTA",
    "ota2": "OTA",
}


@dataclass(frozen=True, slots=True)
class _ANet:
    """One node of a code-model connection, ``null``, or a ``~`` and a node."""

    name: Token
    inverted: bool
    start: int
    comma: Token | None = None


@dataclass(frozen=True, slots=True)
class _AParen:
    """The names of a parenthesised connection, ``(in)`` or ``(in 0)``, and its span."""

    names: tuple[Token, ...]
    span: Span


@dataclass(frozen=True, slots=True)
class _AConn:
    """A code-model connection and the comments inside it."""

    connection: CodeModelConnection
    comments: tuple[Span, ...]
    comma: Token | None = None


@dataclass(frozen=True, slots=True)
class _AVector:
    """A code-model vector port and the comments inside it."""

    connections: tuple[CodeModelConnection, ...]
    span: Span
    comments: tuple[Span, ...]


@dataclass(frozen=True, slots=True)
class _MVector:
    """A code model's vector value, its span with the brackets, and the comments inside it."""

    values: tuple[Value, ...]
    span: Span
    comments: tuple[Span, ...]


@dataclass(frozen=True, slots=True)
class _ASource:
    """The source of a ``%vnam`` connection, and where the connection ends."""

    reference: ElementReference
    end: int


@dataclass(frozen=True, slots=True)
class _FraValue:
    """A value after an analyzer parameter's value: the next value of its list."""

    value: Value
    comma: Token | None = None


@dataclass(frozen=True, slots=True)
class _FraNet:
    """``refnode=`` or ``intnode=``, and the net it names."""

    param: ParamAssignment
    node: Node


class SpecialRules(LinesRules):
    """Rules for the code models, OSDI devices, special functions and frequency analysis."""

    # ngspice A (decision 0020 item 4).

    def a_net(self, children: list[Any]) -> _ANet:
        first = children[0]
        if first.type == "A_NOT_BLANK":
            raise self._parse_error(
                first,
                f"`~` before a blank: write the inversion against its node, `~{children[-1]}` "
                "(ngspice runs it with the blank, but the manual writes none)",
            )
        name = children[-1]
        inverted = first.type == "A_NOT"
        if self._is_null(name) and inverted:
            raise self._parse_error(first, "`~null`: an unconnected port has nothing to invert")
        return _ANet(name, inverted, _span(first).start)

    def a_net_gap(self, children: list[Any]) -> _Field:
        inner = children[-1]
        comments = _comment_spans(children)
        if isinstance(inner, _Field):
            return _Field(inner.node, (*comments, *inner.comments))
        comma = next((c for c in children if isinstance(c, Token) and c.type == "CSEP"), None)
        return _Field(replace(inner, comma=comma), comments)

    def a_paren(self, children: list[Any]) -> _AParen:
        comma = next((c for c in children if c.type == "A_PCOMMA"), None)
        if comma is not None:
            raise self._parse_error(
                comma,
                "a comma inside a connection's parentheses: write its nodes with blanks, "
                "`%vd(a b)` (ngspice runs the comma, but the manual writes blanks)",
            )
        names = tuple(c for c in children if c.type == "WORD")
        return _AParen(names, Span(_span(children[0]).start, _span(children[-1]).end))

    def a_conn(self, children: list[Any]) -> _AConn:
        first = children[0]
        port_type = (
            first if isinstance(first, Token) and first.type in ("A_TYPE", "A_DTYPE") else None
        )
        comments: list[Span] = []
        nets: list[_ANet] = []
        paren: _AParen | None = None
        for child in children:
            if isinstance(child, _Field):
                assert isinstance(child.node, _ANet)
                nets.append(child.node)
                comments.extend(child.comments)
            elif isinstance(child, _ANet):
                nets.append(child)
            elif isinstance(child, _AParen):
                paren = child
        if paren is not None:
            names = paren.names
            start, end = paren.span.start, paren.span.end
        else:
            names = tuple(net.name for net in nets)
            start, end = nets[0].start, _span(names[-1]).end
        if port_type is not None:
            start = _span(port_type).start
            self._check_count(str(port_type), len(names), start)
        null = any(self._is_null(name) for name in names)
        if null and (port_type is not None or paren is not None or len(names) > 1):
            where = f"after `{port_type}`" if port_type is not None else "in a connection"
            raise self._error_at(
                start,
                f"`null` {where}: an unconnected port is written `null` alone, with no port type",
            )
        connection = CodeModelConnection(
            port_type=None if port_type is None else str(port_type),
            nodes=() if null else tuple(Node(str(name), _span(name)) for name in names),
            inverted=any(net.inverted for net in nets),
            null=null,
            source=None,
            span=Span(start, end),
        )
        comma = next((net.comma for net in nets if net.comma is not None), None)
        return _AConn(connection, tuple(comments), comma)

    a_dconn = a_conn

    def a_source(self, children: list[Any]) -> _Field:
        if isinstance(children[0], Token) and children[0].type == "LPAR":
            name = children[1]
            reference = ElementReference(str(name), _span(name))
            return _Field(_ASource(reference, _span(children[-1]).end), ())

        def build(token: Token) -> _ASource:
            return _ASource(ElementReference(str(token), _span(token)), _span(token).end)

        return self._field(children, build)

    def a_vnam(self, children: list[Any]) -> _AConn:
        keyword, source = children
        assert isinstance(source, _Field) and isinstance(source.node, _ASource)
        connection = CodeModelConnection(
            port_type=str(keyword),
            nodes=(),
            inverted=False,
            null=False,
            source=source.node.reference,
            span=Span(_span(keyword).start, source.node.end),
        )
        return _AConn(connection, source.comments)

    def a_member(self, children: list[Any]) -> _Field:
        inner = children[-1]
        comments = _comment_spans(children)
        if isinstance(inner, _Field):
            return _Field(inner.node, (*comments, *inner.comments))
        comma = next((c for c in children if isinstance(c, Token) and c.type == "CSEP"), None)
        assert isinstance(inner, _AConn)
        return _Field(replace(inner, comma=comma or inner.comma), comments)

    a_dmember = a_member

    def a_vector(self, children: list[Any]) -> _AVector:
        members: list[_AConn] = []
        comments: list[Span] = []
        for child in children[1:-1]:
            conn = child.node if isinstance(child, _Field) else child
            assert isinstance(conn, _AConn)
            if isinstance(child, _Field):
                comments.extend(child.comments)
            comments.extend(conn.comments)
            if conn.comma is not None:
                raise self._parse_error(
                    conn.comma,
                    "a comma inside a vector: separate its connections with blanks, `[a b]` "
                    "(ngspice runs the comma, but the manual writes blanks)",
                )
            if conn.connection.source is not None:
                raise self._error_at(
                    conn.connection.span.start,
                    '`%vnam` inside a vector: ngspice stops on it ("unknown controlling '
                    'source"); write the source as a port of its own',
                )
            members.append(conn)
        span = Span(_span(children[0]).start, _span(children[-1]).end)
        return _AVector(tuple(m.connection for m in members), span, tuple(comments))

    a_dvector = a_vector

    def a_port(self, children: list[Any]) -> _Field:
        inner = children[-1]
        comments = _comment_spans(children)
        if isinstance(inner, _Field):
            return _Field(inner.node, (*comments, *inner.comments))
        if isinstance(inner, _AConn):
            connection = inner.connection
            if connection.port_type is None and not connection.null:
                self._check_count(None, len(connection.nodes), connection.span.start)
            port = CodeModelPort(False, (connection,), connection.span)
            return _Field(port, (*comments, *inner.comments))
        assert isinstance(inner, _AVector)
        typed = next(
            (c for c in children if isinstance(c, Token) and c.type in ("A_TYPE", "A_DTYPE")),
            None,
        )
        default = None if typed is None else str(typed)
        for connection in inner.connections:
            if connection.port_type is None and not connection.null:
                self._check_count(default, len(connection.nodes), connection.span.start)
        span = inner.span if typed is None else Span(_span(typed).start, inner.span.end)
        port = CodeModelPort(True, inner.connections, span, default)
        return _Field(port, (*comments, *inner.comments))

    def _check_count(self, port_type: str | None, count: int, start: int) -> None:
        """A connection holds one node, or two for a differential type (Table 8.1)."""
        want = 2 if port_type is not None and port_type.lower() in _DIFFERENTIAL else 1
        if count != want:
            kind = f"a `{port_type}` connection" if port_type is not None else "a connection"
            raise self._error_at(
                start,
                f"{kind} takes {'two nodes' if want == 2 else 'one node'}, and this one has "
                f"{count}",
            )

    def a_param(self, children: list[Any]) -> NoReturn:
        name = _field_token(children)
        raise self._parse_error(
            name,
            f"`{name}=` on an A line: a code model takes its parameters on its `.model` line, and "
            "ngspice stops on one here",
        )

    def code_model(self, children: list[Any]) -> _Item:
        element = _Element(children)
        ports = element.all(CodeModelPort)
        last = ports[-1]
        model_name = self._model_name_of(last)
        if model_name is None:
            raise self._error_at(
                last.span.start,
                "an A line ends with its model, a plain name, after its ports",
            )
        if _reads_as_number(model_name.name, any_letter=True):
            raise self._error_at(
                model_name.span.start,
                f"`{model_name.name}` is in the model's place (the last name on an A line), and "
                "a model name cannot be a number",
            )
        if len(ports) < 2:
            raise self._error_at(
                model_name.span.start,
                f"`{model_name.name}` is the model, and the line has no ports before it",
            )
        ports = ports[:-1]
        model = ModelReference(model_name.name, model_name.span)
        nodes = tuple(node for port in ports for c in port.connections for node in c.nodes)
        return _Item(
            element.end,
            lambda span: CodeModelDevice(
                **_common(element, span, nodes=nodes, params=()), model=model, ports=ports
            ),
        )

    def _model_name_of(self, port: CodeModelPort) -> Node | None:
        """The name a port is when it is the last one: a lone untyped node."""
        if port.vector or len(port.connections) != 1:
            return None
        connection = port.connections[0]
        if (
            connection.port_type is not None
            or connection.inverted
            or connection.null
            or len(connection.nodes) != 1
            or connection.span != connection.nodes[0].span
        ):
            return None
        return connection.nodes[0]

    def _is_null(self, name: Token) -> bool:
        return str(name).lower() == "null"

    # ngspice N (decision 0020 item 6).

    def osdi_device(self, children: list[Any]) -> _Item:
        element = _Element(children)
        names = [name.token for name in element.all(_Name)]
        last = names[-1]
        if _reads_as_number(str(last), any_letter=True):
            raise self._parse_error(
                last,
                f"`{last}` is in the model's place (the last name before any parameter), and a "
                "model name cannot be a number; an N line takes no positional value after its "
                "model (ngspice stops on one)",
            )
        if str(last).lower() == "off":
            raise self._parse_error(last, "`off`: an N line takes no flag (ngspice stops on it)")
        model = ModelReference(str(last), _span(last))
        nodes = tuple(Node(str(token), _span(token)) for token in names[:-1])
        return _Item(
            element.end,
            lambda span: OsdiDevice(**_common(element, span, nodes=nodes), model=model),
        )

    # Code-model .model values (decision 0020 item 5).

    def model_code(self, children: list[Any]) -> _Field:
        inner = children[-1]
        if isinstance(inner, _Field):
            return _Field(inner.node, (*_comment_spans(children), *inner.comments))
        name = next(c for c in children if isinstance(c, Token) and c.type == "WORD")
        param, comments = self._code_param(name, inner)
        return _Field(param, (*_comment_spans(children), *comments))

    def model_param_first(self, children: list[Any]) -> _Field:
        value = children[-1]
        # LTspice's mfg= and type= take a quoted string too: there it stays an ordinary value.
        coded = isinstance(value, _MVector) or (
            isinstance(value, Token)
            and (
                value.type == "BOOL_KW" or value.type == "STRING_VALUE" and _name_is_word(children)
            )
        )
        if not coded:
            return self.param(children)
        name = next(c for c in children if isinstance(c, Token) and c.type == "WORD")
        param, comments = self._code_param(name, value)
        return _Field(param, comments)

    def m_element(self, children: list[Any]) -> _Field:
        inner = children[-1]
        if isinstance(inner, _Field):
            return _Field(inner.node, (*_comment_spans(children), *inner.comments))
        comma = next((c for c in children if isinstance(c, Token) and c.type == "CSEP"), None)
        if comma is not None:
            raise self._parse_error(
                comma,
                "a comma between a vector's values: write them with blanks, `[2.0 1.0]` "
                "(ngspice runs the comma, but the manual writes blanks)",
            )
        return self._field(children, self._value)

    def m_vector(self, children: list[Any]) -> _MVector:
        values: list[Value] = [self._value(children[1])]
        comments: list[Span] = []
        for child in children[2:-1]:
            assert isinstance(child, _Field) and isinstance(child.node, NumericValue | Formula)
            values.append(child.node)
            comments.extend(child.comments)
        span = Span(_span(children[0]).start, _span(children[-1]).end)
        return _MVector(tuple(values), span, tuple(comments))

    def _code_param(
        self, name: Token, value: Token | _MVector
    ) -> tuple[_CodeParam, tuple[Span, ...]]:
        name_span = _span(name)
        built: ValueList | Identifier | Value
        comments: tuple[Span, ...] = ()
        form: Literal["vector", "boolean", "string"]
        if isinstance(value, _MVector):
            # The vector's span takes its brackets; its text is the whole source slice.
            text = self._source.text[value.span.start : value.span.end]
            built = ValueList(text, value.values, value.span)
            form = "vector"
            comments = value.comments
        elif value.type == "BOOL_KW":
            built = Identifier(str(value), _span(value))
            form = "boolean"
        else:
            built = self._value(value)
            form = "string"
        param = ParamAssignment(str(name), built, Span(name_span.start, built.span.end), name_span)
        return _CodeParam(param, form), comments

    # LTspice A (decision 0020 items 3 and 7).

    def sf_function(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: Identifier(str(token), _span(token)))

    def sf_other(self, children: list[Any]) -> NoReturn:
        name = _field_token(children)
        symbol = _SYMBOL_NAMES.get(str(name).lower())
        hint = f"; the {str(name).upper()} symbol writes `{symbol}`" if symbol else ""
        raise self._parse_error(
            name,
            f'`{name}` is not a special function name: LTspice stops on it ("Expected valid '
            f'special function name"). An A line writes one of {_FUNCTIONS}{hint}',
        )

    def _refuse_comma(self, children: list[Any]) -> None:
        comma = next((c for c in children if isinstance(c, Token) and c.type == "CSEP"), None)
        if comma is not None:
            raise self._parse_error(comma, _LT_COMMA)

    def sf_param(self, children: list[Any]) -> _Field:
        self._refuse_comma(children)
        return self.t_param(children)

    def sf_extra(self, children: list[Any]) -> NoReturn:
        token = _field_token(children)
        if token.type == "OFF_KW":
            raise self._parse_error(token, f"`{token}`: an A line takes no flag (LTspice stops)")
        raise self._parse_error(
            token,
            f"`{token}` after the function: an A line takes named parameters only, and LTspice "
            "stops on a positional value",
        )

    def special_function(self, children: list[Any]) -> _Item:
        element = _Element(children)
        function = element.all(Identifier)[0]
        return _Item(
            element.end,
            lambda span: SpecialFunction(**_common(element, span), function=function),
        )

    # LTspice @ and & (decision 0020 items 7 and 8).

    def fra_param(self, children: list[Any]) -> _Field:
        self._refuse_comma(children)
        return self.t_param(children)

    def fra_net(self, children: list[Any]) -> _Field:
        self._refuse_comma(children)

        def build(keyword: Token) -> _FraNet:
            word = children[-1]
            value = Identifier(str(word), _span(word))
            name_span = _span(keyword)
            param = ParamAssignment(
                str(keyword), value, Span(name_span.start, value.span.end), name_span
            )
            return _FraNet(param, Node(str(word), _span(word)))

        return self._field(children, build)

    def fra_more(self, children: list[Any]) -> _Field:
        comma = next((c for c in children if isinstance(c, Token) and c.type == "CSEP"), None)
        field = self._field(children, lambda token: _FraValue(self._value(token)))
        if comma is None:
            return field
        assert isinstance(field.node, _FraValue)
        return replace(field, node=replace(field.node, comma=comma))

    def fra_zm(self, children: list[Any]) -> _Field:
        self._refuse_comma(children)
        return self._field(children, lambda token: Flag(str(token), _span(token)))

    def fra_unlisted(self, children: list[Any]) -> NoReturn:
        name = _field_token(children)
        raise self._parse_error(
            name,
            f"`{name}=` is not a parameter of the frequency response analyzer, and LTspice stops "
            "on it. The reference lists delay, fstart, fend, oct, fcoarse, flist, nmax, pp0, "
            "pp1, f0, f1, pp, tavgmin, tsettle, rpar, acmag, acphase, ac, enabled, refnode and "
            "intnode",
        )

    def frequency_analyzer(self, children: list[Any]) -> _Item:
        element = _Element(children)
        params: list[ParamAssignment] = []
        extra: list[Value] = []
        impedance: Flag | None = None
        nets: dict[str, Node] = {}
        previous: object = None
        for node in (*element.fields, None):
            if isinstance(node, _FraValue):
                last = previous if isinstance(previous, ParamAssignment) else None
                if last is None:
                    raise self._error_at(
                        node.value.span.start,
                        "a value without a name: an `@` line takes named parameters and `zm`",
                    )
                if last.name.lower() not in _FRA_LISTS:
                    raise self._error_at(
                        node.value.span.start,
                        f"a second value for `{last.name}=`: only flist=, pp=, nmax= and ac= "
                        "take a list",
                    )
                if node.comma is not None and last.name.lower() != "ac":
                    raise self._parse_error(node.comma, _LT_COMMA)
                extra.append(node.value)
                continue
            if isinstance(node, Node):
                previous = node
                continue
            if extra:
                params[-1] = self._joined(params[-1], extra)
                extra = []
            previous = node
            if isinstance(node, Flag):
                if impedance is not None:
                    raise self._error_at(
                        node.span.start,
                        f"a second `{node.name}`: the analyzer measures an impedance once "
                        "(LTspice runs it)",
                    )
                impedance = node
            elif isinstance(node, _FraNet):
                params.append(node.param)
                nets[node.param.name.lower()] = node.node
                previous = node.param
            elif isinstance(node, ParamAssignment):
                params.append(node)
        terminals = element.all(Node)
        return _Item(
            element.end,
            lambda span: FrequencyAnalyzer(
                **_common(element, span, nodes=terminals, params=tuple(params)),
                impedance=impedance,
                reference_net=nets.get("refnode"),
                intermediate_net=nets.get("intnode"),
            ),
        )

    def _joined(self, param: ParamAssignment, extra: list[Value]) -> ParamAssignment:
        assert not isinstance(param.value, ValueList | Identifier)
        values = (param.value, *extra)
        span = Span(values[0].span.start, values[-1].span.end)
        return ParamAssignment(
            param.name,
            ValueList(self._source.text[span.start : span.end], values, span),
            Span(param.span.start, span.end),
            param.name_span,
        )

    def fra_probe(self, children: list[Any]) -> _Item:
        element = _Element(children)
        designator = element.designator
        analyzer = ElementReference("@" + str(designator)[1:], _span(designator))
        return _Item(
            element.end,
            lambda span: FraProbe(**_common(element, span), analyzer=analyzer),
        )


def _name_is_word(children: list[Any]) -> bool:
    """Whether a parameter is named by a WORD: an LTspice ``mfg=`` is ``MODEL_TEXT_KW``."""
    return any(isinstance(c, Token) and c.type == "WORD" for c in children)
