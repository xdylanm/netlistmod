"""Expression operations: the expression of a behavioural line (decision 0016 item 7)."""

from __future__ import annotations

from netlistmod.document import Netlist, ScopePath
from netlistmod.edit._ops_common import _TWO_TERMINAL, _element, _kind
from netlistmod.edit.plan import Edit, SlotCheck
from netlistmod.errors import EditError
from netlistmod.model.nodes import (
    BehavioralSource,
    Capacitor,
    Component,
    ControlledSource,
    Inductor,
)
from netlistmod.model.values import Formula

_CLOSING = {"{": "}", "'": "'", "": ""}


def set_expression(
    netlist: Netlist,
    designator: str,
    text: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Replace the text of a line's expression, keeping its delimiters as written (braces,
    quotes or none).

    The expression is a B line's, the expression form of an E, F, G or H line, a C line's
    charge (``q=``, ``Q=``), an LTspice L line's ``Flux=``, or an R, C or L value written as a
    formula. The quantity (``V=``) and the form (``vol=``) are not changed. Text that would
    change the delimiter is refused: a brace or quote that closes it early, or a whole
    ``{...}`` or ``'...'`` in place of a bare expression.
    """
    element = _element(netlist, designator, scope, in_definition)
    formula = _expression_of(element, designator)
    replacement = f"{formula.delimiter}{text}{_CLOSING[formula.delimiter]}"
    slot = SlotCheck((Formula,), "an expression", delimiter=formula.delimiter)
    return [Edit(formula.span, replacement, f"set_expression {designator}", (slot,))]


def _expression_of(element: Component, designator: str) -> Formula:
    if isinstance(element, BehavioralSource):
        return element.expression
    if isinstance(element, ControlledSource):
        if element.expression is None:
            raise EditError(f"`{designator}` has a gain, not an expression; use set_value")
        return element.expression
    if isinstance(element, Capacitor) and element.charge is not None:
        return element.charge
    if isinstance(element, Inductor) and element.flux is not None:
        return element.flux
    if isinstance(element, _TWO_TERMINAL) and isinstance(element.value, Formula):
        return element.value
    if isinstance(element, _TWO_TERMINAL):
        raise EditError(
            f"`{designator}` has no expression: its value is not a formula; use set_formula"
        )
    raise EditError(f"`{designator}` is a {_kind(element)} line and has no expression")
