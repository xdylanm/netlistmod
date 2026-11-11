"""Source operations: DC and AC parts and functions (decisions 0007 and 0013)."""

from __future__ import annotations

from dataclasses import fields

from netlistmod.dialects import Dialect
from netlistmod.document import Netlist, ScopePath
from netlistmod.edit import conventions
from netlistmod.edit._ops_common import (
    _DISTORTION_NAMES,
    _FUNCTION,
    _SOURCES,
    _VALUE,
    UpsertTarget,
    _element,
    _insert,
    _kind,
    _spans,
    upsert_target,
)
from netlistmod.edit.plan import Edit, SlotCheck
from netlistmod.errors import EditError
from netlistmod.model.nodes import (
    CurrentSource,
    SourceSpec,
    VoltageSource,
)
from netlistmod.model.values import (
    AcSpec,
)
from netlistmod.source import Span


def stimulus_target(netlist: Netlist, scope: ScopePath, designator: str, text: str) -> UpsertTarget:
    """The target of a ``set_stimulus`` that was accepted: the function, or one distortion input."""
    return upsert_target(netlist, "set_stimulus", scope, designator, _distortion_name(text) or "")


def set_dc(
    netlist: Netlist,
    designator: str,
    value: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Replace a source's DC value, or add ``DC value`` after its nodes."""
    element = _source(netlist, designator, scope, in_definition)
    reason = f"set_dc {designator}"
    if element.dc is not None:
        return [Edit(element.dc.span, value, reason, (_VALUE,))]
    text = conventions.field(f"{conventions.DC_KEYWORD}{conventions.field(value)}")
    start = len(text) - len(value)
    return [_insert(element.nodes[-1].span.end, text, reason, _VALUE, start)]


def set_ac(
    netlist: Netlist,
    designator: str,
    magnitude: str,
    phase: str | None = None,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Replace a source's AC magnitude (and phase, if given), or add ``AC mag [phase]``."""
    element = _source(netlist, designator, scope, in_definition)
    reason = f"set_ac {designator}"
    ac = element.ac
    if ac is not None:
        edits = [Edit(ac.magnitude.span, magnitude, reason, (_VALUE,))]
        if phase is not None and ac.phase is not None:
            edits.append(Edit(ac.phase.span, phase, reason, (_VALUE,)))
        elif phase is not None:
            point = ac.magnitude.span.end
            edits.append(_insert(point, conventions.field(phase), reason, _VALUE, 1))
        return edits
    point = element.dc.span.end if element.dc is not None else element.nodes[-1].span.end
    spec = f"{conventions.AC_KEYWORD}{conventions.field(magnitude)}"
    if phase is not None:
        spec += conventions.field(phase)
    check = SlotCheck((AcSpec,), "an AC specification")
    return [_insert(point, conventions.field(spec), reason, check, 1)]


def _source(
    netlist: Netlist, designator: str, scope: ScopePath, in_definition: bool
) -> VoltageSource | CurrentSource:
    element = _element(netlist, designator, scope, in_definition)
    if not isinstance(element, _SOURCES):
        raise EditError(f"`{designator}` is a {_kind(element)} line, not an independent source")
    return element


def set_stimulus(
    netlist: Netlist,
    designator: str,
    text: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Replace a source's function, or add one after its DC and AC parts; they stay as they are
    (decision 0013). ``DISTOF1`` and ``DISTOF2`` text addresses that distortion input instead."""
    element = _source(netlist, designator, scope, in_definition)
    reason = f"set_stimulus {designator}"
    if "\n" in text or "\r" in text:
        raise EditError(f"{reason}: a source function's text must be one line, got {text!r}")
    name = _distortion_name(text)
    current = element.stimulus if name is None else _distortion(element, name)
    if current is not None:
        return [Edit(current.span, text, reason, (_FUNCTION,))]
    return [_insert(_function_point(element, name), conventions.field(text), reason, _FUNCTION, 1)]


def set_stimulus_arg(
    netlist: Netlist,
    designator: str,
    key: int | str,
    value: str,
    *,
    function: str | None = None,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Set one argument of a source's function, by 0-based position or written name.

    A position one past the end appends, and a further one is refused, because filling the gap
    would mean inventing defaults. A name not yet written is added after the function.
    ``function`` names a distortion input (``"DISTOF1"``) instead of the source function.
    """
    element = _source(netlist, designator, scope, in_definition)
    reason = f"set_stimulus_arg {designator} {key}"
    spec = _stimulus_of(element, function, designator)
    if isinstance(key, str):
        fold = netlist.scope(scope).fold
        for param in (*spec.params, *element.params):
            if fold(param.name) == fold(key):
                return [Edit(param.value.span, value, reason, (_VALUE,))]
        text = conventions.field(f"{key}={value}")
        return [_insert(spec.span.end, text, reason, _VALUE, len(text) - len(value))]
    if not 0 <= key <= len(spec.args):
        raise EditError(
            f"`{spec.name}` of `{designator}` has {len(spec.args)} argument(s), so position {key} "
            "cannot be set: only an existing position or the next one can"
        )
    if key < len(spec.args):
        return [Edit(spec.args[key].span, value, reason, (_VALUE,))]
    if not spec.args:
        raise EditError(f"`{spec.name}` of `{designator}` has no argument list to add to")
    text = _next_arg(netlist, spec, value)
    return [_insert(spec.args[-1].span.end, text, reason, _VALUE, len(text) - len(value))]


def remove_stimulus(
    netlist: Netlist,
    designator: str,
    *,
    function: str | None = None,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Remove a source's function, or the distortion input ``function`` names, and the separator
    before it. DC and AC parts and comments outside the function stay."""
    element = _source(netlist, designator, scope, in_definition)
    spec = _stimulus_of(element, function, designator)
    if (
        netlist.dialect is Dialect.LTSPICE
        and isinstance(element, CurrentSource)
        and element.dc is None
        and element.ac is None
    ):
        raise EditError(
            f"`{designator}` would have no value, and an LTspice I line needs one; use set_dc first"
        )
    return [Edit(_with_separator(netlist, element, spec), "", f"remove_stimulus {designator}")]


def _with_separator(
    netlist: Netlist, element: VoltageSource | CurrentSource, spec: SourceSpec
) -> Span:
    """The function's span and the gap before it: blanks, a comma or a continuation. A gap after
    a comment stays if text follows on the function's line, since that text would join the
    comment; then the blanks after the function go instead."""
    text = netlist.source.text
    before = [
        span
        for field in fields(element)
        if field.name != "span"
        for span in _spans(getattr(element, field.name))
        if span.end <= spec.span.start
    ]
    previous = max(before, key=lambda span: span.end)
    line_end = spec.span.end
    while line_end < len(text) and text[line_end] not in "\r\n":
        line_end += 1
    if previous in element.trailing_comments and text[spec.span.end : line_end].strip():
        end = spec.span.end
        while text[end] in " \t":
            end += 1
        return Span(spec.span.start, end)
    return Span(previous.end, spec.span.end)


def _distortion_name(text: str) -> str | None:
    """``DISTOF1`` or ``DISTOF2`` if the caller's function text starts with one."""
    head = text.lstrip()[:7].upper()
    return head if head in _DISTORTION_NAMES else None


def _distortion(element: VoltageSource | CurrentSource, name: str) -> SourceSpec | None:
    return next((spec for spec in element.distortion if spec.name.upper() == name), None)


def _stimulus_of(
    element: VoltageSource | CurrentSource, function: str | None, designator: str
) -> SourceSpec:
    spec = element.stimulus if function is None else _distortion(element, function.upper())
    if spec is None:
        what = "source function" if function is None else f"`{function}`"
        raise EditError(f"`{designator}` has no {what}; use set_stimulus to add one")
    return spec


def _function_point(element: VoltageSource | CurrentSource, distortion: str | None) -> int:
    """Where an added function goes: after the DC and AC parts, and a distortion input after any
    function, keeping DISTOF1 before DISTOF2."""
    parts: list[Span] = [element.nodes[-1].span]
    parts += [part.span for part in (element.dc, element.ac) if part is not None]
    if distortion is not None:
        if element.stimulus is not None:
            parts.append(element.stimulus.span)
        parts += [spec.span for spec in element.distortion if spec.name.upper() < distortion]
    return max(span.end for span in parts)


def _next_arg(netlist: Netlist, spec: SourceSpec, value: str) -> str:
    """A new last argument, with a comma if the list's last separator has one."""
    if len(spec.args) > 1:
        gap = netlist.source.text[spec.args[-2].span.end : spec.args[-1].span.start]
        if "," in gap:
            return f", {value}"
    return conventions.field(value)
