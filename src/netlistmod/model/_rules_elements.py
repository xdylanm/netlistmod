"""Rules for element fields and the element lines of every letter but V and I."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NoReturn

from lark import Token

from netlistmod.model._rules_base import _Rules
from netlistmod.model._tree import (
    _comment_spans,
    _common,
    _Element,
    _end,
    _Eol,
    _Field,
    _field_token,
    _field_tokens,
    _Item,
    _KeywordValue,
    _Name,
    _ParamsMarker,
    _span,
    _XRest,
)
from netlistmod.model.nodes import (
    BipolarTransistor,
    Capacitor,
    Diode,
    Inductor,
    Jfet,
    Mesfet,
    Mosfet,
    MutualCoupling,
    Node,
    Resistor,
    SubcktInstance,
)
from netlistmod.model.values import (
    ElementReference,
    Flag,
    Formula,
    ModelReference,
    ParamAssignment,
    SubcktReference,
    Value,
    ValueList,
)
from netlistmod.source import Span

_DIGITS = frozenset("0123456789")
_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZµ")


def _reads_as_number(text: str) -> bool:
    """Whether ``text`` is core.lark's FIELD_NUMBER: a number, then letters only (``2``, ``1k``)."""
    i = 1 if text[:1] in ("+", "-") else 0
    start = i
    while i < len(text) and text[i] in _DIGITS:
        i += 1
    digits = i - start
    if i < len(text) and text[i] == ".":
        i += 1
        while i < len(text) and text[i] in _DIGITS:
            i += 1
            digits += 1
    if digits == 0:
        return False
    if i < len(text) and text[i] in "eE":
        j = i + 1 + (text[i + 1 : i + 2] in ("+", "-"))
        if j < len(text) and text[j] in _DIGITS:
            i = j
            while i < len(text) and text[i] in _DIGITS:
                i += 1
    return all(char in _LETTERS for char in text[i:])


# The tokens an expression is written with: a brace or quoted formula, or the pieces of a bare
# expression, one per physical line (decision 0016 item 2).
_EXPRESSION_TOKENS = frozenset({"BRACE_FORMULA", "QUOTE_FORMULA", "B_PIECE"})


@dataclass(frozen=True, slots=True)
class _Charge:
    """The keyword of a C charge form (q=, Q=) or of LTspice's L Flux=."""

    token: Token


class ElementsRules(_Rules):
    """Rules for element fields and the element lines of every letter but V and I."""

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

    def eol(self, children: list[Any]) -> _Eol:
        inner = children[-1]
        if isinstance(inner, _Eol):
            return _Eol(inner.end, (*_comment_spans(children), *inner.comments))
        return _Eol(_end(children), _comment_spans(children))

    def c_charge(self, children: list[Any]) -> _Field:
        return self._field(children, _Charge)

    def l_flux(self, children: list[Any]) -> _Field:
        return self._field(children, _Charge)

    def hysteretic_param(self, children: list[Any]) -> _Field:
        return self.param(children)

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

    def resistor(self, children: list[Any]) -> _Item:
        return self._two_terminal(Resistor, _Element(children))

    def capacitor(self, children: list[Any]) -> _Item:
        element = _Element(children)
        if element.optional(_Charge) is None:
            return self._two_terminal(Capacitor, element)
        return self._two_terminal(Capacitor, element, charge=self._expression(children))

    def inductor(self, children: list[Any]) -> _Item:
        element = _Element(children)
        if element.optional(_Charge) is None:
            return self._two_terminal(Inductor, element)
        return self._two_terminal(Inductor, element, flux=self._expression(children))

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

    # Transistors (decision 0014).

    def t_name(self, children: list[Any]) -> _Field:
        return self._field(children, _Name)

    t_number = t_name

    def t_area(self, children: list[Any]) -> _Field:
        return self._field(children, self._value)

    def ic_param(self, children: list[Any]) -> _Field:
        # IC_COMMA carries the blanks around the comma, so it is a separator, not a value.
        return self.tc_param(
            [c for c in children if not (isinstance(c, Token) and c.type == "IC_COMMA")]
        )

    def q_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    m_param = q_param
    j_param = q_param
    z_param = q_param

    def thermal_flag(self, children: list[Any]) -> _Field:
        return self.flag(children)

    def bjt(self, children: list[Any]) -> _Item:
        return self._transistor(BipolarTransistor, _Element(children))

    def mosfet(self, children: list[Any]) -> _Item:
        return self._transistor(Mosfet, _Element(children))

    def jfet(self, children: list[Any]) -> _Item:
        return self._transistor(Jfet, _Element(children))

    def mesfet(self, children: list[Any]) -> _Item:
        return self._transistor(Mesfet, _Element(children))

    def _transistor(
        self, kind: type[BipolarTransistor | Mosfet | Jfet | Mesfet], element: _Element
    ) -> _Item:
        names = element.all(_Name)
        last = names[-1].token
        if last.type == "FIELD_NUMBER":
            # Only an ngspice Q has a number after its model in the tree (review R2).
            raise self._parse_error(
                last,
                f"`{last}` after the model is a positional area, and an ngspice Q writes its "
                f"area as `area={last}`",
            )
        self._check_model_name(kind, last)
        nodes = (
            *element.all(Node),
            *(Node(str(name.token), _span(name.token)) for name in names[:-1]),
        )
        model = ModelReference(str(names[-1].token), _span(names[-1].token))
        area = next(iter(element.values()), None)
        return _Item(
            element.end,
            lambda span: kind(
                **_common(element, span, nodes=nodes),
                model=model,
                flags=element.all(Flag),
                area=area,
            ),
        )

    def _check_model_name(self, kind: type, token: Token) -> None:
        """Refuse a model name the grammar could only lex as a name (decision 0014, items 1 and 4).

        Where only a name may follow, the lexer reads ``2`` or ``off`` as a name, so the grammar
        cannot refuse them as the model; both solvers would look the name up instead.
        """
        text = str(token)
        if _reads_as_number(text):
            raise self._parse_error(
                token,
                f"`{text}` is in the model's place (the last name before any area, flag or "
                "parameter), and a model name cannot be a number",
            )
        keywords = {"off", "thermal"} if kind is Mosfet else {"off"}
        if text.lower() in keywords:
            raise self._parse_error(
                token,
                f"`{text}` is in the model's place (the last name before any area, flag or "
                f"parameter), and a model name cannot be the keyword `{text.lower()}`",
            )

    def _expression(self, children: list[Any]) -> Formula:
        """An expression written directly in a rule: a delimited formula, or a bare one over
        its pieces, whose text runs across their continuation lines as written."""
        tokens = [c for c in children if isinstance(c, Token) and c.type in _EXPRESSION_TOKENS]
        if tokens[0].type != "B_PIECE":
            value = self._value(tokens[0])
            assert isinstance(value, Formula)
            return value
        span = Span(_span(tokens[0]).start, _span(tokens[-1]).end)
        return Formula(self._source.text[span.start : span.end], "", span)

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

    model_param_first = param

    uic = flag

    step_value = r_value

    def _two_terminal(
        self, kind: type[Resistor | Capacitor | Inductor], element: _Element, **extra: Any
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
                **extra,
            ),
        )
