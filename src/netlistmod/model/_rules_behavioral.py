"""Rules for the behavioural forms: B lines and their expressions (decision 0016)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NoReturn

from lark import Token

from netlistmod.model._rules_elements import ElementsRules
from netlistmod.model._tree import (
    _common,
    _Element,
    _Field,
    _field_token,
    _Item,
    _Laplace,
    _span,
)
from netlistmod.model.nodes import BehavioralSource
from netlistmod.model.values import ParamAssignment
from netlistmod.source import Span


@dataclass(frozen=True, slots=True)
class _Quantity:
    """The quantity keyword of a B line (``V``, ``I``, and on LTspice ``R`` or ``P``)."""

    token: Token


class BehavioralRules(ElementsRules):
    """Rules for B lines."""

    def b_quantity(self, children: list[Any]) -> _Field:
        return self._field(children, _Quantity)

    def b_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    def b_second_quantity(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        raise self._parse_error(
            keyword, f"`{keyword}=` is a second quantity: a B source takes one, with one expression"
        )

    def b_lt_quantity(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        raise self._parse_error(
            keyword,
            f"`{keyword}=` is an LTspice form: an ngspice B source takes `v=` or `i=` "
            "(ngspice manual §5.1)",
        )

    def behavioral(self, children: list[Any]) -> _Item:
        element = _Element(children)
        quantity = element.all(_Quantity)[0]
        expression = self._expression(children)
        kind = str(quantity.token).lower()
        for param in element.all(ParamAssignment):
            if param.name.lower() == "rpar" and kind in ("v", "p"):
                # LTspice stops on it: "only allowed for behavioral current sources".
                raise self._error_at(
                    (param.name_span or param.span).start,
                    f"`Rpar=` is a parameter of a current B source (`I=` or `R=`), "
                    f"not of `{quantity.token}=`",
                )
        params = element.all(ParamAssignment)
        laplace = element.optional(_Laplace)
        if laplace is not None:
            if kind not in ("v", "i"):
                # LTspice runs it on R= and P=, but its reference shows it on V= and I= only.
                raise self._parse_error(
                    laplace.keyword,
                    f"`laplace=` follows `V=` or `I=` in the LTspice reference; LTspice runs it "
                    f"after `{quantity.token}=` but the library refuses what the reference "
                    "does not show",
                )
            keyword = laplace.keyword
            name_span = _span(keyword)
            name = str(keyword).strip().rstrip("=").strip()
            params = (
                *params,
                ParamAssignment(
                    name,
                    laplace.formula,
                    Span(name_span.start, laplace.formula.span.end),
                    Span(name_span.start, name_span.start + len(name)),
                ),
                *laplace.params,
            )
        return _Item(
            element.end,
            lambda span: BehavioralSource(
                **_common(element, span, params=params),
                quantity=kind,
                expression=expression,
            ),
        )
