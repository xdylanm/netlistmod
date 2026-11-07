"""Rules for the linear dependent sources and switches, E, F, G, H, S and W (decision 0015)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NoReturn

from lark import Token

from netlistmod.dialects import Dialect
from netlistmod.model._rules_elements import ElementsRules
from netlistmod.model._tree import _common, _Element, _Field, _field_token, _Item, _span
from netlistmod.model.nodes import (
    Cccs,
    Ccvs,
    CurrentSwitch,
    Node,
    Vccs,
    Vcvs,
    VoltageSwitch,
)
from netlistmod.model.values import ElementReference, Flag, ModelReference


@dataclass(frozen=True, slots=True)
class _Form:
    """The keyword of an expression form of E, F, G or H."""

    token: Token


class ControlledRules(ElementsRules):
    """Rules for E, F, G, H, S and W lines."""

    def ctl_ref(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: ElementReference(str(token), _span(token)))

    def sw_state(self, children: list[Any]) -> _Field:
        return self.flag(children)

    def ctl_m(self, children: list[Any]) -> _Field:
        return self.param(children)

    def nonlinear_form(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        form = str(keyword).strip().lower()
        raise self._unsupported(
            keyword, f"{self._dialect.display_name} nonlinear dependent source form ({form})"
        )

    cc_form = nonlinear_form
    ctl_form = nonlinear_form

    # The gain forms a solver runs and the library refuses, each with its own message (decision
    # 0015 item 6). The column is the offending token's.

    def gain_keyword(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        where = (
            "the ngspice manual §4.2"
            if self._dialect is Dialect.NGSPICE
            else "the LTspice reference"
        )
        raise self._parse_error(
            keyword,
            f"`gain=` is not a form of {where}: write the gain positionally, as the value after "
            "the nodes (`E1 out 0 in 0 2`) or after the controlling source (`F1 out 0 Vs 2`)",
        )

    def second_value(self, children: list[Any]) -> NoReturn:
        value = _field_token(children)
        raise self._parse_error(
            value, f"`{value}` is a second value: a dependent source takes one gain"
        )

    def unset_gain(self, children: list[Any]) -> NoReturn:
        word = _field_token(children)
        raise self._parse_error(
            word,
            f"`{word}` is not a gain: the gain is not set. LTspice writes the symbol's name in "
            "the gain's place when a symbol's value was never set; set it to a number or a "
            "`{...}` expression",
        )

    def vcvs(self, children: list[Any]) -> _Item:
        return self._voltage_controlled(Vcvs, _Element(children), children)

    def vccs(self, children: list[Any]) -> _Item:
        return self._voltage_controlled(Vccs, _Element(children), children)

    def cccs(self, children: list[Any]) -> _Item:
        return self._current_controlled(Cccs, _Element(children), children)

    def ccvs(self, children: list[Any]) -> _Item:
        return self._current_controlled(Ccvs, _Element(children), children)

    def vswitch(self, children: list[Any]) -> _Item:
        element = _Element(children)
        model = element.all(ModelReference)[0]
        return _Item(
            element.end,
            lambda span: VoltageSwitch(
                **_common(element, span), model=model, flags=element.all(Flag)
            ),
        )

    def cswitch(self, children: list[Any]) -> _Item:
        element = _Element(children)
        model = element.all(ModelReference)[0]
        control = element.all(ElementReference)[0]
        return _Item(
            element.end,
            lambda span: CurrentSwitch(
                **_common(element, span), model=model, flags=element.all(Flag), control=control
            ),
        )

    # The expression forms (decision 0016 item 3): ngspice E vol=, G cur= and value; LTspice value=.

    def e_form(self, children: list[Any]) -> _Field:
        return self._field(children, _Form)

    g_form = e_form
    value_form = e_form

    table_form = nonlinear_form

    def bare_expression(self, children: list[Any]) -> NoReturn:
        piece = _field_token(children)
        raise self._parse_error(
            piece,
            f"`{piece}`: ngspice reads the expression of `vol=`, `cur=` and `value` only in "
            "quotes or braces (ngspice manual §5.2.1); write `{...}` or `'...'`",
        )

    def unclosed_expression(self, children: list[Any]) -> NoReturn:
        opening = next(child for child in children if isinstance(child, Token))
        raise self._parse_error(
            opening,
            "a braced or quoted expression must close on its line; join the lines, or write the "
            "expression bare (B only)",
        )

    def value_word(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        solver = "ngspice" if self._dialect is Dialect.NGSPICE else "LTspice"
        raise self._parse_error(
            keyword,
            f"`{keyword}` here is the keyword of the expression form, and {solver} reads it so; "
            "write the expression after `value=` in braces, or give the net or source another "
            "name",
        )

    def _voltage_controlled(
        self, kind: type[Vcvs | Vccs], element: _Element, children: list[Any]
    ) -> _Item:
        if self._dialect is Dialect.NGSPICE:
            # ngspice replaces the word `value` with `vol=` or `cur=` wherever it stands on an E
            # or G line, so a net of that name stops it in any node position (review R6).
            for node in element.all(Node):
                if node.name.lower() == "value":
                    raise self._error_at(
                        node.span.start,
                        f"`{node.name}`: ngspice reads `value` on an E or G line as the keyword "
                        "of the expression form, in any node position; give the net another name",
                    )
        fields = self._gain_or_expression(element, children)
        return _Item(element.end, lambda span: kind(**_common(element, span), **fields))

    def _current_controlled(
        self, kind: type[Cccs | Ccvs], element: _Element, children: list[Any]
    ) -> _Item:
        fields = self._gain_or_expression(element, children)
        control = element.optional(ElementReference)
        return _Item(
            element.end,
            lambda span: kind(**_common(element, span), control=control, **fields),
        )

    def _gain_or_expression(self, element: _Element, children: list[Any]) -> dict[str, Any]:
        form = element.optional(_Form)
        if form is None:
            return {"value": element.values()[0]}
        keyword = str(form.token).strip().lower()
        return {"expression": self._expression(children), "form": keyword}
