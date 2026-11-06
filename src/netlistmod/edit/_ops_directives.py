"""Directive operations and ``.include`` (architecture §7.3, §7.9; decision 0007)."""

from __future__ import annotations

from netlistmod.document import Line, Netlist
from netlistmod.edit import conventions
from netlistmod.edit._ops_common import (
    _DIRECTIVE_LINES,
    _ITEM_NAMES,
    _TOPOLOGY_ITEMS,
    SINGLETON_DIRECTIVES,
    DirectiveText,
    UpsertTarget,
    _kind,
    resolve_line,
)
from netlistmod.edit.placement import Placement, insertion_point
from netlistmod.edit.plan import Edit, SlotCheck
from netlistmod.errors import EditError, ParseError, TopologyError, UnsupportedConstruct
from netlistmod.model.nodes import (
    Component,
    End,
    ModelStatement,
    OpaqueBlock,
    OpaqueStatement,
    ParamStatement,
    StepDirective,
    TopLevelItem,
)
from netlistmod.model.transform import parse
from netlistmod.source import SourceText, Span


def directive_target(netlist: Netlist, text: DirectiveText) -> UpsertTarget:
    """The target of a ``directives.set`` that was accepted: its kind, or a ``.step``'s
    quantity."""
    item = classify_text(netlist, _physical_lines(text, "directives.set"), "directives.set")
    if isinstance(item, StepDirective):
        label = f"directives.set `.step` of `{item.name}`"
        return UpsertTarget(("directives.set", *_step_quantity(netlist, item)), label)
    kind = type(item).__name__
    return UpsertTarget(("directives.set", kind), f"directives.set {kind}")


def _physical_lines(text: DirectiveText, what: str) -> tuple[str, ...]:
    lines = (text,) if isinstance(text, str) else tuple(text)
    if not lines:
        raise EditError(f"{what}: no text")
    return lines


def _show(lines: tuple[str, ...]) -> str:
    return f"`{lines[0]}`" + (f" (+{len(lines) - 1} lines)" if len(lines) > 1 else "")


def classify_text(netlist: Netlist, lines: tuple[str, ...], what: str) -> TopLevelItem:
    """Parse ``lines`` as the body of a probe netlist and return the one item they hold.

    ``EditError`` if they do not parse, or are not exactly one item on exactly these physical
    lines (an element of ``lines`` may not hold a line break); a single topology item is
    returned whatever its length, for the caller to reject.
    """
    newline = conventions.DEFAULT_TERMINATOR
    probe = SourceText(f"probe{newline}{newline.join(lines)}{newline}.end{newline}")
    try:
        items = parse(probe, netlist.dialect, rkm=netlist.rkm).items
    except (ParseError, UnsupportedConstruct) as error:
        raise EditError(
            f"{what}: {_show(lines)} does not parse as a netlist line: {error}"
        ) from error
    body = [item for item in items[1:] if not isinstance(item, End)]
    if len(body) == 1 and isinstance(body[0], _TOPOLOGY_ITEMS):
        return body[0]  # rejected by the caller as topology, whatever its length
    last = len(lines) + 1  # the probe's title is line 1
    if (
        len(body) != 1
        or probe.line_count != last + 1
        or probe.position(body[0].span.end - 1)[0] != last
    ):
        hint = (
            "; pass a list of physical lines for a continued statement or a block"
            if len(lines) == 1
            else ""
        )
        raise EditError(f"{what}: {_show(lines)} must be exactly one statement or block{hint}")
    return body[0]


def _addable(netlist: Netlist, lines: tuple[str, ...], what: str) -> TopLevelItem:
    """The item ``lines`` hold, if directive operations may write it: a directive, an unknown
    dot-command, a whole ``.control``, ``.if`` or ``.lib`` block or a ``.lib`` statement."""
    item = classify_text(netlist, lines, what)
    if isinstance(item, _TOPOLOGY_ITEMS):
        raise TopologyError(
            f"{what}: {_show(lines)} is a {_describe_item(item)}, which is topology; only "
            "directives and whole opaque items can be added or replaced"
        )
    if isinstance(item, OpaqueStatement) and item.kind == "include":
        raise EditError(f"{what}: add an `.include` with add_include")
    if not isinstance(item, _DIRECTIVE_LINES):
        raise EditError(
            f"{what}: {_show(lines)} is a {_describe_item(item)}, not a directive"
            + _property_hint(item)
        )
    return item


def _property_hint(item: TopLevelItem) -> str:
    if isinstance(item, ParamStatement):
        return "; use params.set"
    if isinstance(item, ModelStatement):
        return "; a `.model` line cannot be added, and set_model_param edits an existing one"
    return ""


def _is_property(item: TopLevelItem) -> bool:
    return isinstance(item, ModelStatement | ParamStatement)


def _describe_item(item: object) -> str:
    if isinstance(item, Component):
        return f"{_kind(item)} line (an element)"
    if isinstance(item, OpaqueStatement):
        return f"`.{item.kind}` statement"
    if isinstance(item, OpaqueBlock):
        return f"`.{item.kind}` block"
    return _ITEM_NAMES.get(type(item), type(item).__name__)


def add_directive(
    netlist: Netlist, text: DirectiveText, placement: Placement = Placement.BEFORE_END
) -> list[Edit]:
    """Insert one directive, a whole ``.control``, ``.if`` or ``.lib`` block or a ``.lib``
    statement at ``placement`` (top level), even if a line of its kind exists (decision 0012)."""
    lines = _physical_lines(text, "directives.add")
    item = _addable(netlist, lines, "directives.add")
    return [_line_insertion(netlist, lines, type(item), placement, "directives.add")]


def replace_directive(netlist: Netlist, target: Line | object, text: DirectiveText) -> list[Edit]:
    """Replace a whole directive or opaque line with one directive, block or ``.lib``."""
    line = _directive_line(netlist, target, "directives.replace")
    lines = _physical_lines(text, "directives.replace")
    item = _addable(netlist, lines, "directives.replace")
    terminator = conventions.terminator_before(netlist.source, line.span.end)
    check = SlotCheck((type(item),), f"one `{type(item).__name__}` item")
    return [Edit(line.span, _joined(lines, terminator), "directives.replace", (check,))]


def remove_directive(netlist: Netlist, target: Line | object) -> list[Edit]:
    """Remove a whole directive line, opaque block or ``.include``/``.lib`` statement."""
    line = _directive_line(netlist, target, "directives.remove")
    return [Edit(line.span, "", "directives.remove")]


def set_directive(netlist: Netlist, text: DirectiveText) -> list[Edit]:
    """Upsert a singleton directive (decision 0007 item 7)."""
    lines = _physical_lines(text, "directives.set")
    item = _addable(netlist, lines, "directives.set")
    kind = type(item)
    if isinstance(item, StepDirective):
        return _set_step(netlist, item, lines)
    if not issubclass(kind, SINGLETON_DIRECTIVES):
        raise EditError(
            f"directives.set: {_show(lines)} is a repeatable directive or an opaque item "
            f"({kind.__name__}); use directives.add, replace or remove"
        )
    existing = netlist.lines.find_all(kind)
    if len(existing) > 1:
        raise EditError(
            f"directives.set: the netlist has {len(existing)} {kind.__name__} lines, so the "
            "line to replace is ambiguous; use directives.replace(line, …)"
        )
    if existing:
        return replace_directive(netlist, existing[0], lines)
    return [_line_insertion(netlist, lines, kind, Placement.BEFORE_END, "directives.set")]


def _set_step(netlist: Netlist, step: StepDirective, lines: tuple[str, ...]) -> list[Edit]:
    """Upsert a ``.step``: replace the line that sweeps the same quantity, or add one (decision
    0009). Nested ``.step`` lines sweep different quantities, so they are not a repeated kind."""
    same = [
        line
        for line in netlist.lines.find_all(StepDirective)
        if isinstance(line.item, StepDirective)
        and _step_quantity(netlist, line.item) == _step_quantity(netlist, step)
    ]
    if len(same) > 1:
        raise EditError(
            f"directives.set: {len(same)} `.step` lines sweep `{step.name}`, so the line to "
            "replace is ambiguous; use directives.replace(line, …)"
        )
    if same:
        return replace_directive(netlist, same[0], lines)
    return [_line_insertion(netlist, lines, StepDirective, Placement.BEFORE_END, "directives.set")]


def _step_quantity(netlist: Netlist, step: StepDirective) -> tuple[str, str, str]:
    fold = netlist.scope().fold
    model_type = step.model_type.name if step.model_type is not None else ""
    return (step.kind, fold(model_type), fold(step.name))


def _directive_line(netlist: Netlist, target: Line | object, what: str) -> Line:
    line = resolve_line(netlist, target)
    item = line.item
    if isinstance(item, _TOPOLOGY_ITEMS):
        raise TopologyError(
            f"{what}: line {line.first_line} is a {_describe_item(item)}, which is topology and "
            "cannot be replaced or removed"
        )
    if not isinstance(item, _DIRECTIVE_LINES):
        raise EditError(
            f"{what}: line {line.first_line} is a {_describe_item(item)}, not a directive"
            + ("; parameters and models are edited, not removed" if _is_property(item) else "")
        )
    if line.scope:
        raise EditError(f"{what}: line {line.first_line} is inside a subcircuit definition")
    return line


def add_include(
    netlist: Netlist, path: str, placement: Placement = Placement.AFTER_TITLE
) -> list[Edit]:
    """Insert ``.include "path"`` (architecture §7.9); the path is never read."""
    lines = (conventions.include_statement(path),)
    item = classify_text(netlist, lines, "add_include")
    assert isinstance(item, OpaqueStatement)  # one line starting `.include` or a parse error
    for line in netlist.lines.walk():
        if isinstance(line.item, OpaqueStatement) and line.item.raw == item.raw:
            raise EditError(f"add_include: line {line.first_line} already includes `{path}`")
    return [_line_insertion(netlist, lines, OpaqueStatement, placement, "add_include")]


def _line_insertion(
    netlist: Netlist, lines: tuple[str, ...], kind: type, placement: Placement, reason: str
) -> Edit:
    point = insertion_point(placement, netlist)
    terminator = conventions.terminator_before(netlist.source, point)
    check = SlotCheck((kind,), f"one `{kind.__name__}` item")
    return Edit(Span(point, point), _joined(lines, terminator), reason, (check,))


def _joined(lines: tuple[str, ...], terminator: str) -> str:
    """The physical lines, each ended by ``terminator`` (decision 0007 item 4)."""
    return "".join(line + terminator for line in lines)
