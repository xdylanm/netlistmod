"""Source operations: DC and AC parts and functions (decisions 0007 and 0013)."""

from __future__ import annotations

from dataclasses import fields

from netlistmod.dialects import _XYCE, Dialect
from netlistmod.document import ScopePath
from netlistmod.document.document import Netlist
from netlistmod.edit import conventions
from netlistmod.edit._ops_common import (
    _DISTORTION_NAMES,
    _FUNCTION,
    _SOURCES,
    _VALUE,
    UpsertTarget,
    _a_kind,
    _element,
    _insert,
    _removal_edit,
    _spans,
    upsert_target,
)
from netlistmod.edit.plan import Edit, SlotCheck
from netlistmod.errors import EditError
from netlistmod.model.nodes import (
    CurrentSource,
    PortSource,
    SourceSpec,
    VoltageSource,
)
from netlistmod.model.values import (
    AcSpec,
)
from netlistmod.source import Span

# The independent sources the source edits address (P on xyce; decision 0030 item 6).
_Source = VoltageSource | CurrentSource | PortSource

# The source kinds whose line needs a value, so that remove_stimulus keeps one (decision 0026 item
# 6; decision 0030 item 8): LTspice's I; none on ngspice or xyce, where a bare source runs as 0.
_NEEDS_VALUE: dict[Dialect, tuple[type[_Source], ...]] = {
    Dialect.NGSPICE: (),
    Dialect.LTSPICE: (CurrentSource,),
    _XYCE: (),
}

# The names a function takes after its list, by folded function name, where the dialect checks
# them before set_stimulus_arg adds one (xyce: PWL's `TD=` and `R=`, PAT's `R=`; decision 0030
# items 3 to 5); None where the dialect does not (ngspice and LTspice).
# Whether the dialect's sources have distortion inputs (ngspice's DISTOF1 and DISTOF2), which
# set_stimulus addresses by their text; where they do not (xyce; LTspice keeps its re-parse
# check), DISTOF text is refused before any edit.
_NO_DISTORTION: dict[Dialect, bool] = {
    Dialect.NGSPICE: False,
    Dialect.LTSPICE: False,
    _XYCE: True,
}

_NAMED_ARGS: dict[Dialect, dict[str, frozenset[str]] | None] = {
    Dialect.NGSPICE: None,
    Dialect.LTSPICE: None,
    _XYCE: {"pwl": frozenset({"td", "r"}), "pat": frozenset({"r"})},
}


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
    point = max(span.end for span in _before_ac(element))
    spec = f"{conventions.AC_KEYWORD}{conventions.field(magnitude)}"
    if phase is not None:
        spec += conventions.field(phase)
    check = SlotCheck((AcSpec,), "an AC specification")
    return [_insert(point, conventions.field(spec), reason, check, 1)]


def _before_ac(element: _Source) -> list[Span]:
    """The parts an AC part goes after: the nodes and the DC part, and a P line's `port=` and
    `Z0=`, which stand between the DC and AC parts (decision 0030 item 6)."""
    parts = [element.nodes[-1].span]
    if element.dc is not None:
        parts.append(element.dc.span)
    if isinstance(element, PortSource):
        parts += [param.span for param in element.params]
    return parts


def _source(netlist: Netlist, designator: str, scope: ScopePath, in_definition: bool) -> _Source:
    element = _element(netlist, designator, scope, in_definition)
    if not isinstance(element, _SOURCES):
        raise EditError(f"`{designator}` is {_a_kind(element)} line, not an independent source")
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
    if name is not None and _NO_DISTORTION[netlist.dialect]:
        raise EditError(
            f"{reason}: {netlist.dialect.display_name} sources have no distortion input, so "
            f"`{name}` cannot be set"
        )
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
        # A P line's `port=` and `Z0=` are the line's, which set_param edits.
        line = () if isinstance(element, PortSource) else element.params
        for param in (*spec.params, *line):
            if fold(param.name) == fold(key):
                return [Edit(param.value.span, value, reason, (_VALUE,))]
        if isinstance(element, PortSource) and fold(key) in {fold("port"), fold("z0")}:
            raise EditError(
                f"`port=` and `Z0=` are the P line's, not its function's: use set_param to set "
                f"`{key}` of `{designator}`"
            )
        _check_named_arg(netlist, spec, key, designator)
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
        isinstance(element, _NEEDS_VALUE[netlist.dialect])
        and element.dc is None
        and element.ac is None
    ):
        raise EditError(
            f"`{designator}` would have no value, and an {netlist.dialect.display_name} "
            f"{designator[0].upper()} line needs one; use set_dc first"
        )
    removed = _with_separator(netlist, element, spec)
    return [_removal_edit(netlist, element, removed, f"remove_stimulus {designator}")]


def _with_separator(netlist: Netlist, element: _Source, spec: SourceSpec) -> Span:
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


def _check_named_arg(netlist: Netlist, spec: SourceSpec, key: str, designator: str) -> None:
    """Refuse a name the function does not take after its list, where the dialect checks it:
    on xyce only PWL's `TD=` and `R=` and PAT's `R=` (decision 0030 items 3 to 5); a PWL's
    `FILE` replaces its pairs, so it is written whole with set_stimulus."""
    table = _NAMED_ARGS[netlist.dialect]
    if table is None:
        return
    function = spec.name.lower()
    folded = key.lower()
    if function == "pwl" and folded == "file":
        raise EditError(
            f"`{designator}`: `FILE name` takes the place of the PWL's pairs; write the whole "
            'function with set_stimulus (`PWL FILE "name"`)'
        )
    taken = table.get(function, frozenset())
    if folded not in taken:
        names = " and ".join(f"`{name.upper()}=`" for name in sorted(taken, reverse=True))
        only = f"; it takes only {names} after its list" if names else ""
        raise EditError(
            f"`{spec.name}` of `{designator}` takes its arguments by position on "
            f"{netlist.dialect.display_name}, so `{key}=` cannot be added{only}"
        )


def _distortion_name(text: str) -> str | None:
    """``DISTOF1`` or ``DISTOF2`` if the caller's function text starts with one."""
    head = text.lstrip()[:7].upper()
    return head if head in _DISTORTION_NAMES else None


def _distortion(element: _Source, name: str) -> SourceSpec | None:
    return next((spec for spec in element.distortion if spec.name.upper() == name), None)


def _stimulus_of(element: _Source, function: str | None, designator: str) -> SourceSpec:
    spec = element.stimulus if function is None else _distortion(element, function.upper())
    if spec is None:
        what = "source function" if function is None else f"`{function}`"
        raise EditError(f"`{designator}` has no {what}; use set_stimulus to add one")
    return spec


def _function_point(element: _Source, distortion: str | None) -> int:
    """Where an added function goes: after the DC and AC parts, and a distortion input after any
    function, keeping DISTOF1 before DISTOF2."""
    parts: list[Span] = _before_ac(element)
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
