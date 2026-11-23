"""Rules for element fields and the element lines of every letter but V and I."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NoReturn

from lark import Token

from netlistmod.dialects import _XYCE, Dialect
from netlistmod.model._numbers import reads_as_number
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

# The tokens an expression is written with: a brace or quoted formula, or the pieces of a bare
# expression, one per physical line (decision 0016 item 2).
_EXPRESSION_TOKENS = frozenset({"BRACE_FORMULA", "QUOTE_FORMULA", "B_PIECE"})
# The tokens of a transistor's name field that are numbers: ngspice's FIELD_NUMBER (t_number) and
# xyce's NUMBER (xt_number). LTspice reads its positional area as t_area, never as a name.
_NUMBER_NAMES = frozenset({"FIELD_NUMBER", "NUMBER"})
# Whether a number after a Q's model is its positional area: on xyce it is (decision 0031 item 3);
# an ngspice Q writes `area=` only, so the number is refused (decision 0014 item 5).
_POSITIONAL_Q_AREA: dict[Dialect, bool] = {
    Dialect.NGSPICE: False,
    Dialect.LTSPICE: False,
    _XYCE: True,
}
# The keywords a transistor's model name cannot be, by dialect and kind; a kind not listed takes
# `off` only (decision 0014 item 4; decision 0031 item 2, whose `tnodeout` on M comes with M).
_OFF = frozenset({"off"})
_MODEL_KEYWORDS: dict[Dialect, dict[type, frozenset[str]]] = {
    Dialect.NGSPICE: {Mosfet: frozenset({"off", "thermal"})},
    Dialect.LTSPICE: {Mosfet: frozenset({"off", "thermal"})},
    _XYCE: {},
}


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

    params_first = param

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
        inductors = element.all(ElementReference)
        # Only an xyce K has a model, after the coupling, and only it may name one inductor
        # ([xyce-ref] §2.3.6 p194; decision 0027 item 6).
        model = element.optional(ModelReference)
        if model is not None:
            model = self._model_not_number(model, "the name after the coupling")
        elif len(inductors) == 1:
            raise self._error_at(
                inductors[0].span.start,
                "a K line with one inductor needs a CORE model after the coupling (Xyce "
                "reference manual §2.3.6 p194); without one there is nothing to couple",
            )
        return _Item(
            element.end,
            lambda span: MutualCoupling(
                **_common(element, span, nodes=()),
                inductors=inductors,
                value=value,
                model=model,
            ),
        )

    def diode(self, children: list[Any]) -> _Item:
        element = _Element(children)
        model = self._model_not_number(
            element.all(ModelReference)[0], "the name after the two nodes"
        )
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
        names = list(element.all(_Name))
        area = next(iter(element.values()), None)
        last = names[-1].token
        if last.type in _NUMBER_NAMES:
            # Only a Q has a number after its model in the tree (review R2): an ngspice Q writes
            # its area `area=` only; on xyce the number is the positional area (decision 0031).
            if not _POSITIONAL_Q_AREA[self._dialect]:
                raise self._parse_error(
                    last,
                    f"`{last}` after the model is a positional area, and an ngspice Q writes its "
                    f"area as `area={last}`",
                )
            area = self._value(last)
            names.pop()
            last = names[-1].token
        if (
            kind is BipolarTransistor
            and self._dialect is Dialect.NGSPICE
            and len(names) > 1
            and reads_as_number(str(last), any_letter=True)
        ):
            # A number with a letter outside ngspice's NUMBER (1μ, 2Ω): ngspice 47 runs it as an
            # area and ignores the letters, so it is the area message, not the model's (M18 A1-4).
            raise self._parse_error(
                last,
                f"`{last}` after the model is a positional area, and an ngspice Q writes its "
                "area as `area=` and a number; ngspice ignores the letters after a number that "
                "are not its scale factors, such as `μ` (U+03BC) and `Ω`",
            )
        self._check_model_name(kind, last)
        nodes = (
            *element.all(Node),
            *(Node(str(name.token), _span(name.token)) for name in names[:-1]),
        )
        model = ModelReference(str(last), _span(last))
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
        """Refuse a model name the grammar could only lex as a name (decision 0014, items 1 and 4;
        decision 0031 item 2).

        Where only a name may follow, the lexer reads ``2`` or ``off`` as a name, so the grammar
        cannot refuse them as the model; the solvers would look the name up instead.
        """
        text = str(token)
        if reads_as_number(text, any_letter=True):
            raise self._parse_error(
                token,
                f"`{text}` is in the model's place (the last name before any area, flag or "
                "parameter), and a model name cannot be a number",
            )
        if token.type == "NODE_WORD" and ":" in text:
            # On xyce every name of a transistor line is a node field until the last (X-D2).
            raise self._parse_error(
                token,
                f"`{text}` is in the model's place (the last name before any area, flag or "
                "parameter), and a model name cannot hold `:`",
            )
        keywords = _MODEL_KEYWORDS[self._dialect].get(kind, _OFF)
        if text.lower() in keywords:
            raise self._parse_error(
                token,
                f"`{text}` is in the model's place (the last name before any area, flag or "
                f"parameter), and a model name cannot be the keyword `{text.lower()}`",
            )

    def _model_not_number(self, model: ModelReference, place: str) -> ModelReference:
        """Refuse a number as the model of a D, S, W, or ngspice R, C or L line (decision 0021
        item 1, decision 0024).

        Where only a name may follow, the lexer reads ``2`` or ``4093`` as a name, so the grammar
        cannot refuse it as the model (as for Q, decision 0014 item 1). A field that reads as a
        number (digits, then letters only) is never a model name; ``1n4148`` and ``2N2222`` are.
        """
        if reads_as_number(model.model_name, any_letter=True):
            raise self._error_at(
                model.span.start,
                f"`{model.model_name}` is in the model's place ({place}), and a model name "
                "cannot be a number",
            )
        return model

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
        if name.type == "NODE_WORD" and ":" in name:
            # On xyce every name of an X line is a node field until the last (decision X-D2).
            raise self._parse_error(
                name,
                f"`{name}` is in the subcircuit's place (the last name before the parameters), "
                "and a subcircuit name cannot hold `:`",
            )
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
        if model is not None:
            # Only an ngspice R, C or L has a model (decision 0024).
            place = "the name after the value" if value is not None else "the name after the nodes"
            model = self._model_not_number(model, place)
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
