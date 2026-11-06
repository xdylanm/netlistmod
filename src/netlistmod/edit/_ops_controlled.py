"""Switch operations: the initial state of an S or W line (decision 0015 item 10)."""

from __future__ import annotations

from netlistmod.document import Netlist, ScopePath
from netlistmod.edit import conventions
from netlistmod.edit._ops_common import _element, _insert, _kind
from netlistmod.edit.plan import Edit, SlotCheck
from netlistmod.errors import EditError
from netlistmod.model.nodes import Switch
from netlistmod.model.values import Flag
from netlistmod.source import Span

_STATES = ("on", "off")
_STATE = SlotCheck((Flag,), "a switch state")


def set_switch_state(
    netlist: Netlist,
    designator: str,
    state: str | None,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Set the initial state of an S or W line to ``on`` or ``off``, or remove it (``None``).

    An existing state is replaced, with any LTspice value (``off=1``); a new one goes right
    after the model. Removing takes the gap before the keyword too. Removing a state the line
    does not write changes nothing.
    """
    element = _element(netlist, designator, scope, in_definition)
    if not isinstance(element, Switch):
        raise EditError(f"`{designator}` is a {_kind(element)} line and has no switch state")
    if state is not None and state.lower() not in _STATES:
        raise EditError(f"a switch state is `on`, `off` or None, not {state!r}")
    reason = f"set_switch_state {designator}"
    current = element.flags[0] if element.flags else None
    if state is None:
        if current is None:
            return []
        return [Edit(_with_gap(netlist, element, current), "", reason)]
    if current is not None:
        return [Edit(current.span, state, reason, (_STATE,))]
    return [_insert(element.model.span.end, conventions.field(state), reason, _STATE, 1)]


def _with_gap(netlist: Netlist, element: Switch, flag: Flag) -> Span:
    """The state's span and the gap before it, back to the model. If a comment stands between
    them, the gap stays (the next text would join the comment) and the blanks after go."""
    text = netlist.source.text
    if any(
        element.model.span.end <= span.start < flag.span.start for span in element.trailing_comments
    ):
        end = flag.span.end
        while end < len(text) and text[end] in " \t":
            end += 1
        return Span(flag.span.start, end)
    return Span(element.model.span.end, flag.span.end)
