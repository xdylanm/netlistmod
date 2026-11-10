"""Removal operations: a named parameter of an element line or of a ``.model`` (decision 0019).

A field goes with the separator before it, so the line keeps its other fields as written. Where
that separator starts a ``+`` line that holds more fields, the separator after it goes instead,
so the other fields stay on their line. A comment beside the field refuses the edit, since the
text after the removal could join it.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass

from netlistmod.dialects import Dialect
from netlistmod.document import Netlist, ScopePath
from netlistmod.edit._ops_common import (
    _TRANSISTORS,
    _TWO_TERMINAL,
    _VALUE_KEYWORDS,
    _element,
    _kind,
    _spans,
    resolve_scope,
)
from netlistmod.edit.plan import Edit
from netlistmod.errors import EditError
from netlistmod.model.nodes import (
    BehavioralSource,
    BipolarTransistor,
    Component,
    ControlledSource,
    CurrentSource,
    Diode,
    Jfet,
    LosslessLine,
    LossyLine,
    Mesfet,
    ModelStatement,
    SubcktInstance,
    TransmissionLine,
    VoltageSource,
)
from netlistmod.model.values import ParamAssignment
from netlistmod.source import Span

_IMPEDANCE = ("z0", "zo")


def remove_param(
    netlist: Netlist,
    designator: str,
    name: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Remove the named parameter ``name`` of an element line: every line on which
    :func:`~netlistmod.edit._ops_elements.set_param` sets one. ``z0`` and ``zo`` name one
    parameter of a T line."""
    element = _element(netlist, designator, scope, in_definition)
    reason = f"remove_param {designator} {name}"
    fold = netlist.scope(scope).fold
    folded = fold(name)
    ltspice = netlist.dialect is Dialect.LTSPICE
    if isinstance(element, SubcktInstance):
        raise EditError(
            f"`{designator}` is a subcircuit call: its instance parameters cannot be removed "
            "(set_instance_param sets them)"
        )
    if isinstance(element, LossyLine):
        raise EditError(
            f"`{designator}` is a lossy transmission line and takes no parameter; its values are "
            "in its LTRA model (use remove_model_param)"
        )
    takes = (
        *_TWO_TERMINAL,
        Diode,
        *_TRANSISTORS,
        BehavioralSource,
        ControlledSource,
        TransmissionLine,
        VoltageSource,
        CurrentSource,
    )
    if not isinstance(element, takes):
        raise EditError(f"`{designator}` is a {_kind(element)} line and takes no parameters")
    if (
        isinstance(element, _TWO_TERMINAL)
        and not ltspice
        and folded in _VALUE_KEYWORDS[type(element)]
        and element.value_keyword is not None
    ):
        raise EditError(
            f"`{name}` names the value of `{designator}` (`{element.value_keyword}=…`), not a "
            "parameter; use remove_value"
        )
    for flag in getattr(element, "flags", ()):
        if fold(flag.name) == folded:
            raise EditError(
                f"`{flag.name}` is a flag of `{designator}`, not a parameter; flags are not "
                "removable"
            )
    names = {folded}
    if isinstance(element, LosslessLine) and folded in _IMPEDANCE:
        names = set(_IMPEDANCE)
    matches = [param for param in element.params if fold(param.name) in names]
    if (
        not matches
        and folded == "area"
        and isinstance(element, Diode | BipolarTransistor | Jfet | Mesfet)
        and element.area is not None
    ):
        raise EditError(
            f"the area of `{designator}` is positional, not a named parameter; set it with "
            "set_param"
        )
    if not matches:
        raise EditError(f"`{designator}` has no parameter `{name}`")
    if len(matches) > 1:
        raise EditError(f"{reason}: parameter `{name}` is repeated; the edit has no single target")
    return [Edit(_removal(netlist, element, matches[0], reason), "", reason)]


def remove_model_param(
    netlist: Netlist,
    model: str,
    name: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Remove parameter ``name`` of the ``.model`` named ``model`` defined in ``scope``. A CPL
    matrix goes whole; flags are not removable."""
    found = resolve_scope(netlist, scope, in_definition)
    definitions = found.models.get(found.fold(model))
    if not definitions:
        raise EditError(f"no model `{model}` in {found.describe()}")
    statement = definitions[0]  # ngspice uses the first definition (decision 0006)
    reason = f"remove_model_param {model} {name}"
    folded = found.fold(name)
    if any(found.fold(flag.name) == folded for flag in statement.flags):
        raise EditError(f"`{name}` is a flag of model `{model}`; flags are not removable")
    matches = [param for param in statement.params if found.fold(param.name) == folded]
    if not matches:
        raise EditError(f"model `{model}` has no parameter `{name}`")
    if len(matches) > 1:
        raise EditError(f"{reason}: parameter `{name}` is repeated; the edit has no single target")
    return [Edit(_removal(netlist, statement, matches[0], reason), "", reason)]


def _removal(
    netlist: Netlist,
    owner: Component | ModelStatement,
    param: ParamAssignment,
    reason: str,
) -> Span:
    """The text a removed field takes with it: the field and the separator before it, or the
    one after it when the field is first inside parentheses or starts a ``+`` line that holds
    more fields."""
    text = netlist.source.text
    spans = _field_spans(owner)
    close = owner.close_paren_span if isinstance(owner, ModelStatement) else None
    before = max(span.end for span in spans if span.end <= param.span.start)
    # The next field, and the next field or the closing parenthesis.
    after_field = min(
        (span.start for span in spans if span.start >= param.span.end and span != close),
        default=None,
    )
    after = after_field if close is None else min(after_field or close.start, close.start)
    line_start = text.rfind("\n", 0, param.span.start) + 1
    continued = text[line_start : param.span.start].lstrip(" \t").startswith("+")
    for comment in owner.trailing_comments:
        between = before <= comment.start < param.span.start
        same_line = (
            comment.start >= param.span.end and "\n" not in text[param.span.end : comment.start]
        )
        # A comment after the line's last field stays where it is, unless the field is on a +
        # line, which the comment would then hold alone.
        if between or (same_line and (after is not None or continued)):
            raise EditError(
                f"{reason}: a comment stands beside the field, and the text after the removal "
                "could join it; remove the field by hand"
            )
    opened = (
        isinstance(owner, ModelStatement)
        and owner.open_paren_span is not None
        and before == owner.open_paren_span.end
    )
    if opened and after is not None:
        return Span(param.span.start, after)
    starts_line = "\n" in text[before : param.span.start]
    if starts_line and after_field is not None and "\n" not in text[param.span.end : after_field]:
        return Span(param.span.start, after_field)
    return Span(before, param.span.end)


def _field_spans(owner: Component | ModelStatement) -> list[Span]:
    """The spans of a line's fields, its designator or keyword among them; not its own span or
    its comments."""
    assert is_dataclass(owner)
    found: list[Span] = []
    for field in fields(owner):
        if field.name in {"span", "trailing_comments"}:
            continue
        found.extend(_spans(getattr(owner, field.name)))
    return found
