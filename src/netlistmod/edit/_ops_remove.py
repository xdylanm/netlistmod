"""Removal operations: a named parameter of an element line or of a ``.model`` (decision 0019).

The removed span is chosen from where the field sits on its physical line (review R1): after
another field, the separator before it goes; first on its line with more after it, the separator
after it; alone on its line, the line break before it, so that a comment after it moves to the
end of the line before. A comment only ends a physical line, so no removal takes one, except
from inside a CPL list over ``+`` lines, which is refused (review R3).
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass

from netlistmod.dialects import Dialect
from netlistmod.document import Netlist, ScopePath
from netlistmod.edit._ops_common import (
    _TRANSISTORS,
    _TWO_TERMINAL,
    _VALUE_KEYWORDS,
    _comment_inside,
    _element,
    _kind,
    _refuse_over_comment,
    _spans,
    resolve_scope,
)
from netlistmod.edit.plan import Edit
from netlistmod.errors import EditError
from netlistmod.model.nodes import (
    BehavioralSource,
    BipolarTransistor,
    CodeModelDevice,
    Component,
    ControlledSource,
    CurrentSource,
    Diode,
    FrequencyAnalyzer,
    Jfet,
    LosslessLine,
    LossyLine,
    Mesfet,
    ModelStatement,
    OsdiDevice,
    SpecialFunction,
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
    if isinstance(element, CodeModelDevice):
        raise EditError(
            f"`{designator}` is a code model and takes no parameter on its line; a code model's "
            "parameters are on its `.model` line (use remove_model_param)"
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
        OsdiDevice,
        SpecialFunction,
        FrequencyAnalyzer,
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
    return [Edit(_removal(netlist, element, matches[0]), "", reason)]


def remove_model_param(
    netlist: Netlist,
    model: str,
    name: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Remove parameter ``name`` of the ``.model`` named ``model`` defined in ``scope``. A CPL
    matrix goes whole, and is refused when a comment lies inside it (review R3); flags are not
    removable."""
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
    return [Edit(_removal(netlist, statement, matches[0]), "", reason)]


def _removal(
    netlist: Netlist,
    owner: Component | ModelStatement,
    param: ParamAssignment,
) -> Span:
    """The text a removed field takes with it, chosen from where the field sits on its physical
    line (decision 0019 item 11, review R1). A comment can only end a physical line, so none of
    these spans holds one, unless the field itself does: a CPL list over ``+`` lines with a
    comment inside it is refused (review R3).

    1. after another field (or a ``.model``'s ``(``) on its line: the separator before it and the
       field; first inside ``(``, the field and the separator after it, when a field or the
       ``)`` follows on the line;
    2. first on its line, with a later field or the ``)`` on that line: the field and the
       separator after it;
    3. alone on its line: from the line break that ends the line before (with a ``\\``
       continuation's backslashes and the blanks before them) to the end of the field, so that
       what followed the field, a comment say, moves to the end of the line before.
    """
    comment = _comment_inside(owner, param.span)
    if comment is not None:
        where = (
            f"model `{owner.name}`"
            if isinstance(owner, ModelStatement)
            else f"`{owner.designator}`"
        )
        raise _refuse_over_comment(netlist, comment, f"`{param.name}=` of {where}")
    text = netlist.source.text
    spans = _field_spans(owner)
    before = max(span.end for span in spans if span.end <= param.span.start)
    # The next field or the closing parenthesis, whichever comes first.
    after = min((span.start for span in spans if span.start >= param.span.end), default=None)
    followed = after is not None and "\n" not in text[param.span.end : after]
    if "\n" not in text[before : param.span.start]:
        opened = (
            isinstance(owner, ModelStatement)
            and owner.open_paren_span is not None
            and before == owner.open_paren_span.end
        )
        if opened and followed and after is not None:
            return Span(param.span.start, after)
        return Span(before, param.span.end)
    if followed and after is not None:
        return Span(param.span.start, after)
    start = text.rfind("\n", before, param.span.start)
    if start > before and text[start - 1] == "\r":
        start -= 1
    if text[start - 1 : start] == "\\":
        # A `\\` continuation: its backslashes and the blanks before them go with it. A comment
        # never ends in a backslash continuation, so this never cuts into one.
        while start > before and text[start - 1] == "\\":
            start -= 1
        while start > before and text[start - 1] in " \t":
            start -= 1
    return Span(start, param.span.end)


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
