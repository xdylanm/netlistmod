"""Plan builders for the restricted edit operations (architecture §7.2, decision 0007).

Each function looks up its target in a netlist and returns the edits that make the change,
with the slot checks that verify where they land; it never applies them. Spans come from the
typed nodes and text is composed by :mod:`netlistmod.edit.conventions`; nothing scans source
text for syntax (P13). :mod:`netlistmod.edit.api` exposes these as methods.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, fields, is_dataclass
from dataclasses import field as dataclass_field

from netlistmod.dialects import Dialect
from netlistmod.document import Line, Netlist, Scope, ScopePath
from netlistmod.document.models import allowed_model_types, model_type_allowed
from netlistmod.edit import conventions
from netlistmod.edit.placement import Placement, insertion_point
from netlistmod.edit.plan import Edit, SlotCheck
from netlistmod.errors import EditError, ParseError, TopologyError, UnsupportedConstruct
from netlistmod.model.nodes import (
    AcDirective,
    BlankLine,
    Capacitor,
    CommentLine,
    Component,
    CurrentSource,
    DcDirective,
    Diode,
    Directive,
    End,
    GlobalDirective,
    Inductor,
    ModelStatement,
    MutualCoupling,
    OpaqueBlock,
    OpaqueStatement,
    OpDirective,
    ParamStatement,
    Resistor,
    StepDirective,
    SubcktDefinition,
    SubcktInstance,
    TempDirective,
    Title,
    TitleDirective,
    TopLevelItem,
    TranDirective,
    UnknownDirective,
    VoltageSource,
)
from netlistmod.model.transform import parse
from netlistmod.model.values import (
    AcSpec,
    Flag,
    Formula,
    Identifier,
    ModelReference,
    NumericValue,
    ParamAssignment,
    ValueList,
)
from netlistmod.source import SourceText, Span

_VALUE = SlotCheck((NumericValue, Formula, ValueList, Identifier), "a value")
_MODEL = SlotCheck((ModelReference,), "a model name")
_TWO_TERMINAL = (Resistor, Capacitor, Inductor)
_SOURCES = (VoltageSource, CurrentSource)

# The keywords that name the value of an R, C or L line (`r=1k`; NG-RES-001, NG-CAP-001,
# NG-IND-001). set_param routes them to the value slot rather than adding a parameter.
_VALUE_KEYWORDS: dict[type[Component], frozenset[str]] = {
    Resistor: frozenset({"r", "resistance"}),
    Capacitor: frozenset({"c", "capacitance"}),
    Inductor: frozenset({"l", "inductance"}),
}

# Directive kinds that `directives.set` upserts (decision 0007 item 7). `directives.add` writes
# a second line of one when asked, because ngspice runs two .ac or .dc lines (decision 0012).
SINGLETON_DIRECTIVES: tuple[type[Directive], ...] = (
    TranDirective,
    AcDirective,
    DcDirective,
    OpDirective,
    TempDirective,
)

# LTspice has no R, C or L .model type, so the semiconductor form does not exist (review R6).
_NO_LTSPICE_MODEL = "LTspice has no R, C or L model"

# The name of an LTspice diode's positional area, which set_param routes to its slot.
_POSITIONAL_AREA = "area"

# Topology items (§7.1): directive operations never add, replace or remove them.
_TOPOLOGY_ITEMS = (Component, SubcktDefinition, GlobalDirective)

# What directive operations write and remove: directives, and whole opaque items, whose
# contents are never edited (review round 1). `.include` is added with add_include.
_DIRECTIVE_LINES = (Directive, UnknownDirective, OpaqueBlock, OpaqueStatement)


# Addressing.


def resolve_scope(netlist: Netlist, scope: ScopePath, in_definition: bool) -> Scope:
    """The scope an edit addresses; a non-empty ``scope`` needs ``in_definition=True`` (P11)."""
    try:
        found = netlist.scope(scope)
    except KeyError:
        raise EditError(f"no subcircuit definition scope {tuple(scope)!r}") from None
    if scope and not in_definition:
        raise EditError(
            f"scope {tuple(scope)!r} edits the definition of {found.describe()}, which changes "
            "every instance of it; pass in_definition=True to confirm, or use "
            "set_instance_param on an X line to change one instance"
        )
    return found


def _element(netlist: Netlist, designator: str, scope: ScopePath, in_definition: bool) -> Component:
    found = resolve_scope(netlist, scope, in_definition)
    elements = found.elements.get(found.fold(designator), ())
    if not elements:
        raise EditError(f"no element `{designator}` in {found.describe()}")
    if len(elements) > 1:
        raise EditError(
            f"designator `{designator}` is repeated in {found.describe()} "
            "(DUPLICATE_ELEMENT); the edit has no single target"
        )
    return elements[0]


_ELEMENT_NAMES: dict[type[Component], str] = {
    Resistor: "resistor",
    Capacitor: "capacitor",
    Inductor: "inductor",
    MutualCoupling: "coupling",
    VoltageSource: "voltage source",
    CurrentSource: "current source",
    Diode: "diode",
    SubcktInstance: "subcircuit call",
}

_ITEM_NAMES: dict[type, str] = {
    SubcktDefinition: "subcircuit definition",
    GlobalDirective: "`.global` line",
    ParamStatement: "`.param` line",
    ModelStatement: "`.model` line",
    Title: "title line",
    TitleDirective: "`.title` line",
    End: "`.end` line",
    BlankLine: "blank line",
    CommentLine: "comment line",
}


def _kind(element: Component) -> str:
    return _ELEMENT_NAMES.get(type(element), type(element).__name__)


def resolve_line(netlist: Netlist, target: Line | object) -> Line:
    """The line of ``netlist`` that is ``target`` or holds it; ``EditError`` for a stale one."""
    for line in netlist.lines.walk():
        if line is target or line.item is target:
            return line
    raise EditError(
        "the line or node does not belong to this netlist (each edit returns a new netlist; "
        "look the line up again in the netlist being edited)"
    )


# Upsert targets (decision 0010 item 5).


@dataclass(frozen=True, slots=True)
class UpsertTarget:
    """What an upsert writes to, by operation family, scope and folded names; a batch takes
    one upsert of each. ``label`` names the target as the caller wrote it, for the message."""

    key: tuple[object, ...]
    label: str = dataclass_field(compare=False)


def upsert_target(netlist: Netlist, family: str, scope: ScopePath, *names: str) -> UpsertTarget:
    """The target of an operation that has already resolved ``scope``."""
    found = netlist.scope(scope)
    key = (family, found.path, *(found.fold(name) for name in names))
    return UpsertTarget(key, f"{family} {' '.join(names)} in {found.describe()}")


def include_target(path: str) -> UpsertTarget:
    """The target of ``add_include``; a path is compared as written, like the statement text
    the operation already compares."""
    return UpsertTarget(("add_include", path), f"add_include `{path}`")


def directive_target(netlist: Netlist, text: DirectiveText) -> UpsertTarget:
    """The target of a ``directives.set`` that was accepted: its kind, or a ``.step``'s
    quantity."""
    item = classify_text(netlist, _physical_lines(text, "directives.set"), "directives.set")
    if isinstance(item, StepDirective):
        label = f"directives.set `.step` of `{item.name}`"
        return UpsertTarget(("directives.set", *_step_quantity(netlist, item)), label)
    kind = type(item).__name__
    return UpsertTarget(("directives.set", kind), f"directives.set {kind}")


# Element operations.


def set_value(
    netlist: Netlist,
    designator: str,
    value: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
    reason: str = "",
) -> list[Edit]:
    """Replace the value of an R, C or L line, or add one after the nodes; or replace a
    source's DC value (never adding one or a ``DC`` keyword)."""
    element = _element(netlist, designator, scope, in_definition)
    reason = reason or f"set_value {designator}"
    if isinstance(element, _TWO_TERMINAL):
        if element.value is not None:
            return [Edit(element.value.span, value, reason, (_VALUE,))]
        point = element.nodes[-1].span.end
        return [_insert(point, conventions.field(value), reason, _VALUE, 1)]
    if isinstance(element, _SOURCES):
        if element.dc is None:
            raise EditError(f"`{designator}` has no DC value to replace; use set_dc to add one")
        return [Edit(element.dc.span, value, reason, (_VALUE,))]
    if isinstance(element, MutualCoupling):
        raise EditError(f"`{designator}` is a coupling; use set_coupling to set its value")
    raise EditError(f"`{designator}` is a {_kind(element)} line and has no value slot")


def set_param(
    netlist: Netlist,
    designator: str,
    name: str,
    value: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Set or add an instance parameter of an R, C, L or D line, or of an LTspice V or I line."""
    element = _element(netlist, designator, scope, in_definition)
    reason = f"set_param {designator} {name}"
    found_fold = netlist.scope(scope).fold
    folded = found_fold(name)
    ltspice = netlist.dialect is Dialect.LTSPICE
    if isinstance(element, SubcktInstance):
        raise EditError(f"`{designator}` is a subcircuit call; use set_instance_param")
    takes_params = (*_TWO_TERMINAL, Diode, *(_SOURCES if ltspice else ()))
    if not isinstance(element, takes_params):
        raise EditError(f"`{designator}` is a {_kind(element)} line and takes no parameters")
    if (
        isinstance(element, _TWO_TERMINAL)
        and not ltspice
        and folded in _VALUE_KEYWORDS[type(element)]
    ):
        if element.value_keyword is None or element.value is None:
            raise EditError(
                f"`{name}` names the value of `{designator}`, which is not written as "
                f"`{name}=…`; use set_value"
            )
        return [Edit(element.value.span, value, reason, (_VALUE,))]
    for flag in getattr(element, "flags", ()):
        # A flag takes its value in place: `noiseless=1` -> `noiseless=0`, `off` -> `off=1`.
        if found_fold(flag.name) == folded:
            if flag.value is not None:
                return [Edit(flag.value.span, value, reason, (_VALUE,))]
            text = f"={value}"
            return [_insert(flag.span.end, text, reason, _VALUE, 1)]
    if isinstance(element, Diode) and ltspice and folded == _POSITIONAL_AREA:
        # LTspice's area is positional, right after the model, unless it is written `area=`.
        if any(found_fold(param.name) == folded for param in element.params):
            return _assign(element.params, element, name, value, reason, folded=found_fold)
        if element.area is not None:
            return [Edit(element.area.span, value, reason, (_VALUE,))]
        return [_insert(element.model.span.end, conventions.field(value), reason, _VALUE, 1)]
    return _assign(element.params, element, name, value, reason, folded=found_fold)


def set_instance_param(
    netlist: Netlist,
    designator: str,
    name: str,
    value: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Set or add a parameter override on an X line (the per-instance edit of §7.4)."""
    element = _element(netlist, designator, scope, in_definition)
    if not isinstance(element, SubcktInstance):
        raise EditError(f"`{designator}` is not a subcircuit call; use set_param")
    reason = f"set_instance_param {designator} {name}"
    return _assign(element.params, element, name, value, reason, folded=netlist.scope(scope).fold)


def _assign(
    params: tuple[ParamAssignment, ...],
    owner: object,
    name: str,
    value: str,
    reason: str,
    after: int | None = None,
    *,
    folded: Callable[[str], str],
) -> list[Edit]:
    """Replace the value of parameter ``name`` or add ``name=value`` after the last field
    (or after offset ``after``); ``folded`` is the dialect's name comparison."""
    matches = [param for param in params if folded(param.name) == folded(name)]
    if len(matches) > 1:
        raise EditError(f"{reason}: parameter `{name}` is repeated; the edit has no single target")
    if matches:
        return [Edit(matches[0].value.span, value, reason, (_VALUE,))]
    point = _last_field_end(owner) if after is None else after
    text = conventions.field(conventions.assignment(name, value))
    # A flag's keyword may be written with a value too (LTspice), which parses as a Flag.
    return [_insert(point, text, reason, SlotCheck((ParamAssignment, Flag), "a parameter"), 1)]


def set_model(
    netlist: Netlist,
    designator: str,
    model: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
    allow_external: bool = False,
) -> list[Edit]:
    """Replace the model name of an R, C, L or D line, or add one after the value of an R, C
    or L line that has none (decision 0007 item 3; review round 1)."""
    element = _element(netlist, designator, scope, in_definition)
    if not isinstance(element, (*_TWO_TERMINAL, Diode)):
        raise EditError(f"`{designator}` is a {_kind(element)} line and has no model")
    if netlist.dialect is Dialect.LTSPICE and isinstance(element, _TWO_TERMINAL):
        raise EditError(f"`{designator}` takes no model: {_NO_LTSPICE_MODEL}")
    if element.model is None and element.value_keyword is not None:
        raise EditError(
            f"`{designator}` writes its value as `{element.value_keyword}=…`, a form that takes "
            "no model; use set_value to write a positional value first"
        )
    chain = tuple(netlist.scope(scope).chain())
    key = chain[0].fold(model)
    definition = next((found.models[key][0] for found in chain if key in found.models), None)
    if definition is not None:
        if not model_type_allowed(element, definition.model_type):
            allowed = ", ".join(
                f"`{kind.upper()}`" for kind in sorted(allowed_model_types(element))
            )
            raise EditError(
                f"model `{model}` has type `{definition.model_type}`, but `{designator}` "
                f"takes a model of type {allowed}"
            )
    else:
        searched = ", ".join(found.describe() for found in chain)
        include = any(found.may_define_elsewhere for found in chain)
        if not include:
            raise EditError(f"model `{model}` is not defined (searched: {searched})")
        if not allow_external:
            raise EditError(
                f"model `{model}` is not defined (searched: {searched}); it may be defined in "
                "an `.include` or `.lib` file or an opaque block, which is not read: pass "
                "allow_external=True to "
                "set it without a type check"
            )
    reason = f"set_model {designator}"
    if element.model is not None:
        return [Edit(element.model.span, model, reason, (_MODEL,))]
    # Without a model the grammar requires a value; the model goes right after it.
    assert isinstance(element, _TWO_TERMINAL) and element.value is not None
    return [_insert(element.value.span.end, conventions.field(model), reason, _MODEL, 1)]


def remove_value(
    netlist: Netlist,
    designator: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Remove the value of an R, C or L line that also names a model, so the model's geometry
    applies (review round 1). The separator before the value stays."""
    element = _element(netlist, designator, scope, in_definition)
    if not isinstance(element, _TWO_TERMINAL):
        raise EditError(f"`{designator}` is a {_kind(element)} line; only R, C and L have a value")
    if netlist.dialect is Dialect.LTSPICE:
        raise EditError(f"`{designator}` needs its value: {_NO_LTSPICE_MODEL}")
    if element.value is None:
        raise EditError(f"`{designator}` has no value to remove")
    if element.model is None:
        raise EditError(
            f"`{designator}` has no model, so it needs its value; add a model with set_model first"
        )
    return [Edit(element.value.span, "", f"remove_value {designator}")]


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


def set_coupling(
    netlist: Netlist,
    designator: str,
    value: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Replace the coupling value of a ``K`` line."""
    element = _element(netlist, designator, scope, in_definition)
    if not isinstance(element, MutualCoupling):
        raise EditError(f"`{designator}` is a {_kind(element)} line, not a coupling")
    return [Edit(element.value.span, value, f"set_coupling {designator}", (_VALUE,))]


# Statement operations.


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


# Directive operations.

DirectiveText = str | Sequence[str]
"""One physical line, or a sequence of physical lines (a continued statement or a block)."""


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


# Helpers.


def _insert(point: int, text: str, reason: str, check: SlotCheck, start: int) -> Edit:
    slot = SlotCheck(check.kinds, check.description, start, check.end)
    return Edit(Span(point, point), text, reason, (slot,))


def _last_field_end(node: object) -> int:
    """The end of the last field of an element line (its span and comments excluded): where an
    added parameter goes (decision 0007 item 5)."""
    assert is_dataclass(node) and not isinstance(node, type)
    end = 0
    for field in fields(node):
        if field.name in {"span", "trailing_comments"}:
            continue
        for span in _spans(getattr(node, field.name)):
            end = max(end, span.end)
    return end


def _spans(value: object) -> Iterator[Span]:
    if isinstance(value, Span):
        yield value
    elif isinstance(value, tuple):
        for element in value:
            yield from _spans(element)
    elif is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            yield from _spans(getattr(value, field.name))
