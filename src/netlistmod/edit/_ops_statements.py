"""Statement operations: ``.param`` and ``.model`` parameters (decision 0007 item 7)."""

from __future__ import annotations

from netlistmod.document import Netlist, ScopePath
from netlistmod.edit import conventions
from netlistmod.edit._ops_common import (
    _VALUE,
    _insert,
    resolve_scope,
)
from netlistmod.edit._ops_elements import _assign
from netlistmod.edit.placement import Placement, insertion_point
from netlistmod.edit.plan import Edit, SlotCheck
from netlistmod.errors import EditError
from netlistmod.model.nodes import (
    ParamStatement,
)
from netlistmod.model.values import (
    ParamAssignment,
)
from netlistmod.source import Span


def set_param_statement(
    netlist: Netlist,
    name: str,
    value: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
    placement: Placement | None = None,
) -> list[Edit]:
    """Upsert a parameter (decision 0007 item 7): replace the effective assignment of ``name``
    in ``scope`` (defaults count), or add a ``.param`` line by placement."""
    found = resolve_scope(netlist, scope, in_definition)
    reason = f"params.set {name}"
    assignments = found.params.get(found.fold(name))
    if assignments:
        return [Edit(assignments[-1].value.span, value, reason, (_VALUE,))]
    point = insertion_point(placement or Placement.AFTER_LAST_PARAM, netlist, found.path)
    terminator = conventions.terminator_before(netlist.source, point)
    text = conventions.param_line(name, value, terminator)
    start = len(conventions.PARAM_KEYWORD) + len(conventions.FIELD_SEPARATOR)
    end = len(text) - len(terminator)
    slots = (
        SlotCheck((ParamStatement,), "one `.param` line"),
        SlotCheck((ParamAssignment,), "a parameter assignment", start, end),
        SlotCheck(_VALUE.kinds, "a parameter value", end - len(value), end),
    )
    return [Edit(Span(point, point), text, reason, slots)]


def set_model_param(
    netlist: Netlist,
    model: str,
    name: str,
    value: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Set or add a parameter of the ``.model`` named ``model`` defined in ``scope``."""
    found = resolve_scope(netlist, scope, in_definition)
    definitions = found.models.get(found.fold(model))
    if not definitions:
        raise EditError(f"no model `{model}` in {found.describe()}")
    statement = definitions[0]  # ngspice uses the first definition (decision 0006)
    reason = f"set_model_param {model} {name}"
    if statement.params:
        after = statement.params[-1].span.end  # inside the parentheses, if any
        return _assign(statement.params, statement, name, value, reason, after, folded=found.fold)
    if statement.open_paren_span is not None:
        # Empty parentheses: `d()` -> `d(n=1.5)`, right after the `(` token.
        text = conventions.assignment(name, value)
        check = SlotCheck((ParamAssignment,), "a parameter")
        return [_insert(statement.open_paren_span.end, text, reason, check, 0)]
    # `.model dm d` -> `.model dm d n=1.5`.
    point = statement.model_type_span.end
    return _assign((), statement, name, value, reason, point, folded=found.fold)
