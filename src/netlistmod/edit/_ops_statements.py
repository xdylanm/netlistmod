"""Statement operations: ``.param`` and ``.model`` parameters (decision 0007 item 7)."""

from __future__ import annotations

from netlistmod.document import Netlist, ScopePath
from netlistmod.edit import conventions
from netlistmod.edit._ops_common import (
    _VALUE,
    _comment_inside,
    _insert,
    _refuse_over_comment,
    resolve_scope,
)
from netlistmod.edit._ops_elements import _assign
from netlistmod.edit.placement import Placement, insertion_point
from netlistmod.edit.plan import Edit, SlotCheck
from netlistmod.errors import EditError, ParseError, UnsupportedConstruct
from netlistmod.model.nodes import (
    ModelStatement,
    ParamStatement,
)
from netlistmod.model.transform import parse
from netlistmod.model.values import (
    ParamAssignment,
    ValueList,
)
from netlistmod.source import SourceText, Span


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
    """Set or add a parameter of the ``.model`` named ``model`` defined in ``scope``.

    A CPL list with a comment inside it (over ``+`` lines) is set value for value when ``value``
    holds as many values, so the comment stays; another count is refused (review R3, after
    decision 0017 item 6)."""
    found = resolve_scope(netlist, scope, in_definition)
    definitions = found.models.get(found.fold(model))
    if not definitions:
        raise EditError(f"no model `{model}` in {found.describe()}")
    statement = definitions[0]  # ngspice uses the first definition (decision 0006)
    reason = f"set_model_param {model} {name}"
    matches = [param for param in statement.params if found.fold(param.name) == found.fold(name)]
    if len(matches) == 1 and isinstance(matches[0].value, ValueList):
        old = matches[0].value
        comment = _comment_inside(statement, old.span)
        if comment is not None:
            new = _list_values(netlist, statement.model_type, matches[0].name, value)
            if len(new) != len(old.values):
                raise _refuse_over_comment(
                    netlist,
                    comment,
                    f"`{matches[0].name}=` of model `{model}` has {len(old.values)} values, not "
                    f"{len(new)}, and",
                )
            return [
                Edit(was.span, text, reason, (_VALUE,))
                for was, text in zip(old.values, new, strict=True)
            ]
    if statement.params:
        after = statement.params[-1].span.end  # inside the parentheses, if any
        return _assign(statement.params, statement, name, value, reason, after, folded=found.fold)
    if statement.flags:
        # Only a flag, `(pchan)` or `vdmos pchan`: the parameter goes after the last one.
        after = statement.flags[-1].span.end
        return _assign((), statement, name, value, reason, after, folded=found.fold)
    if statement.open_paren_span is not None:
        # Empty parentheses: `d()` -> `d(n=1.5)`, right after the `(` token.
        text = conventions.assignment(name, value)
        check = SlotCheck((ParamAssignment,), "a parameter")
        return [_insert(statement.open_paren_span.end, text, reason, check, 0)]
    # `.model dm d` -> `.model dm d n=1.5`.
    point = statement.model_type_span.end
    return _assign((), statement, name, value, reason, point, folded=found.fold)


def _list_values(netlist: Netlist, model_type: str, name: str, value: str) -> list[str]:
    """The values of ``value`` as the grammar reads them in ``name=`` of a ``model_type`` model:
    a one-line probe is parsed, so the edit never scans the text itself (P13)."""
    newline = conventions.DEFAULT_TERMINATOR
    probe = SourceText(
        f"probe{newline}.model probe {model_type} {name}={value}{newline}.end{newline}"
    )
    try:
        items = parse(probe, netlist.dialect, rkm=netlist.rkm).items
    except (ParseError, UnsupportedConstruct) as error:
        raise EditError(f"`{name}={value}` does not parse as a list of values: {error}") from error
    statement = next(item for item in items if isinstance(item, ModelStatement))
    parsed = statement.params[0].value
    values = parsed.values if isinstance(parsed, ValueList) else (parsed,)
    return [probe.text[v.span.start : v.span.end] for v in values]
