"""Rules for the linear dependent sources and switches, E, F, G, H, S and W (decision 0015)."""

from __future__ import annotations

from typing import Any, NoReturn

from netlistmod.model._rules_elements import ElementsRules
from netlistmod.model._tree import _common, _Element, _Field, _field_token, _Item, _span
from netlistmod.model.nodes import (
    Cccs,
    Ccvs,
    CurrentSwitch,
    Vccs,
    Vcvs,
    VoltageSwitch,
)
from netlistmod.model.values import ElementReference, Flag, ModelReference


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

    def vcvs(self, children: list[Any]) -> _Item:
        return self._voltage_controlled(Vcvs, _Element(children))

    def vccs(self, children: list[Any]) -> _Item:
        return self._voltage_controlled(Vccs, _Element(children))

    def cccs(self, children: list[Any]) -> _Item:
        return self._current_controlled(Cccs, _Element(children))

    def ccvs(self, children: list[Any]) -> _Item:
        return self._current_controlled(Ccvs, _Element(children))

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

    def _voltage_controlled(self, kind: type[Vcvs | Vccs], element: _Element) -> _Item:
        value = element.values()[0]
        return _Item(element.end, lambda span: kind(**_common(element, span), value=value))

    def _current_controlled(self, kind: type[Cccs | Ccvs], element: _Element) -> _Item:
        value = element.values()[0]
        control = element.all(ElementReference)[0]
        return _Item(
            element.end,
            lambda span: kind(**_common(element, span), value=value, control=control),
        )
