"""Plan builders for the restricted edit operations (architecture §7.2, decision 0007).

Each function looks up its target in a netlist and returns the edits that make the change,
with the slot checks that verify where they land; it never applies them. Spans come from the
typed nodes and text is composed by :mod:`netlistmod.edit.conventions`; nothing scans source
text for syntax (P13). :mod:`netlistmod.edit.api` exposes these as methods.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import fields, is_dataclass

from netlistmod.document import Line, Netlist, Scope, ScopePath, fold
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
from netlistmod.model.values import AcSpec, Formula, ModelReference, NumericValue, ParamAssignment
from netlistmod.source import SourceText, Span

_VALUE = SlotCheck((NumericValue, Formula), "a value")
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

# Directive kinds that `directives.set` upserts (decision 0007 item 7): ngspice 47 runs a
# repeated .tran/.op again and uses the last .temp, so a second line is never what is meant.
SINGLETON_DIRECTIVES: tuple[type[Directive], ...] = (
    TranDirective,
    AcDirective,
    DcDirective,
    OpDirective,
    TempDirective,
)

# Items that are topology or opaque (§7.1): directive operations never add, replace or remove
# them.
_TOPOLOGY_ITEMS = (Component, SubcktDefinition, GlobalDirective, OpaqueStatement, OpaqueBlock)


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
            "set_instance_param on an X line to change one instance (architecture §7.4)"
        )
    return found


def _element(netlist: Netlist, designator: str, scope: ScopePath, in_definition: bool) -> Component:
    found = resolve_scope(netlist, scope, in_definition)
    elements = found.elements.get(fold(designator), ())
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
    """Set or add an instance parameter of an R, C, L or D line."""
    element = _element(netlist, designator, scope, in_definition)
    reason = f"set_param {designator} {name}"
    if isinstance(element, SubcktInstance):
        raise EditError(f"`{designator}` is a subcircuit call; use set_instance_param")
    if not isinstance(element, (*_TWO_TERMINAL, Diode)):
        raise EditError(f"`{designator}` is a {_kind(element)} line and takes no parameters")
    if isinstance(element, _TWO_TERMINAL) and fold(name) in _VALUE_KEYWORDS[type(element)]:
        if element.value_keyword is None or element.value is None:
            raise EditError(
                f"`{name}` names the value of `{designator}`, which is not written as "
                f"`{name}=…`; use set_value"
            )
        return [Edit(element.value.span, value, reason, (_VALUE,))]
    return _assign(element.params, element, name, value, reason)


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
    return _assign(element.params, element, name, value, f"set_instance_param {designator} {name}")


def _assign(
    params: tuple[ParamAssignment, ...],
    owner: object,
    name: str,
    value: str,
    reason: str,
) -> list[Edit]:
    """Replace the value of parameter ``name`` or add ``name=value`` after the last field."""
    matches = [param for param in params if fold(param.name) == fold(name)]
    if len(matches) > 1:
        raise EditError(f"{reason}: parameter `{name}` is repeated; the edit has no single target")
    if matches:
        return [Edit(matches[0].value.span, value, reason, (_VALUE,))]
    point = _last_field_end(owner)
    text = conventions.field(conventions.assignment(name, value))
    return [_insert(point, text, reason, SlotCheck((ParamAssignment,), "a parameter"), 1)]


def set_model(
    netlist: Netlist,
    designator: str,
    model: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
    allow_external: bool = False,
) -> list[Edit]:
    """Replace the model name of an R, C, L or D line (decision 0007 item 3)."""
    element = _element(netlist, designator, scope, in_definition)
    if not isinstance(element, (*_TWO_TERMINAL, Diode)):
        raise EditError(f"`{designator}` is a {_kind(element)} line and has no model")
    if element.model is None:
        raise EditError(
            f"`{designator}` has no model name to replace; adding a model is not supported"
        )
    chain = tuple(netlist.scope(scope).chain())
    definition = next(
        (found.models[fold(model)][0] for found in chain if fold(model) in found.models), None
    )
    if definition is not None:
        if not model_type_allowed(element, definition.model_type):
            allowed = ", ".join(
                f"`{kind.upper()}`" for kind in sorted(allowed_model_types(element))
            )
            raise EditError(
                f"model `{model}` has type `{definition.model_type}`, but `{designator}` "
                f"takes a model of type {allowed} (architecture §7.2)"
            )
    else:
        searched = ", ".join(found.describe() for found in chain)
        include = any(found.has_opaque_include for found in chain)
        if not include:
            raise EditError(f"model `{model}` is not defined (searched: {searched})")
        if not allow_external:
            raise EditError(
                f"model `{model}` is not defined (searched: {searched}); it may be defined in "
                "an `.include` or `.lib` file, which is not read: pass allow_external=True to "
                "set it without a type check"
            )
    return [Edit(element.model.span, model, f"set_model {designator}", (_MODEL,))]


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
    assignments = found.params.get(fold(name))
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
    definitions = found.models.get(fold(model))
    if not definitions:
        raise EditError(f"no model `{model}` in {found.describe()}")
    statement = definitions[0]  # ngspice uses the first definition (decision 0006)
    reason = f"set_model_param {model} {name}"
    if not statement.params and statement.parenthesized:
        raise EditError(
            f"{reason}: `.model {statement.name}` has empty parentheses, so there is no "
            "parameter to add after; write one parameter in the file first"
        )
    # Without parameters the last field is the model type: `.model dm d` -> `.model dm d n=1`.
    return _assign(statement.params, statement, name, value, reason)


# Directive operations.


def classify_line(netlist: Netlist, text: str, what: str) -> TopLevelItem:
    """Parse ``text`` as one line of a probe netlist and return its item.

    ``EditError`` if it does not parse or is not exactly one physical line; a single
    topology or opaque item is returned whatever its length, for the caller to reject.
    """
    newline = conventions.DEFAULT_TERMINATOR
    probe = SourceText(f"probe{newline}{text}{newline}.end{newline}")
    try:
        items = parse(probe, netlist.dialect, rkm=netlist.rkm).items
    except (ParseError, UnsupportedConstruct) as error:
        raise EditError(f"{what}: `{text}` does not parse as a netlist line: {error}") from error
    body = [item for item in items[1:] if not isinstance(item, End)]
    if len(body) == 1 and isinstance(body[0], _TOPOLOGY_ITEMS):
        return body[0]  # rejected by the caller as topology, whatever its length
    if len(body) != 1 or probe.position(body[0].span.end - 1)[0] != 2:
        raise EditError(f"{what}: `{text}` must be exactly one line")
    return body[0]


def _directive(netlist: Netlist, text: str, what: str) -> Directive | UnknownDirective:
    item = classify_line(netlist, text, what)
    if isinstance(item, OpaqueStatement):
        raise TopologyError(
            f"{what}: `{text}` is an `.{item.kind}` statement; add a harness include with "
            "add_include (architecture §7.9)"
        )
    if isinstance(item, _TOPOLOGY_ITEMS):
        raise TopologyError(
            f"{what}: `{text}` is a {_describe_item(item)}, which is topology or opaque; only "
            "directives can be added or replaced (architecture §7.3)"
        )
    if not isinstance(item, (Directive, UnknownDirective)):
        raise EditError(
            f"{what}: `{text}` is a {_describe_item(item)}, not a directive"
            + ("; use params.set or set_model_param" if _is_property(item) else "")
        )
    return item


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
    netlist: Netlist, text: str, placement: Placement = Placement.BEFORE_END
) -> list[Edit]:
    """Insert one directive line at ``placement`` (top level)."""
    item = _directive(netlist, text, "directives.add")
    return [_line_insertion(netlist, text, type(item), placement, "directives.add")]


def replace_directive(netlist: Netlist, target: Line | object, text: str) -> list[Edit]:
    """Replace a whole directive line with one directive line."""
    line = _directive_line(netlist, target, "directives.replace")
    item = _directive(netlist, text, "directives.replace")
    terminator = conventions.terminator_before(netlist.source, line.span.end)
    check = SlotCheck((type(item),), f"one `{type(item).__name__}` line")
    return [Edit(line.span, text + terminator, "directives.replace", (check,))]


def remove_directive(netlist: Netlist, target: Line | object) -> list[Edit]:
    """Remove a whole directive line."""
    line = _directive_line(netlist, target, "directives.remove")
    return [Edit(line.span, "", "directives.remove")]


def set_directive(netlist: Netlist, text: str) -> list[Edit]:
    """Upsert a singleton directive (decision 0007 item 7)."""
    item = _directive(netlist, text, "directives.set")
    kind = type(item)
    if not issubclass(kind, SINGLETON_DIRECTIVES):
        raise EditError(
            f"directives.set: `{text}` is a repeatable directive ({kind.__name__}); use "
            "directives.add, replace or remove"
        )
    existing = netlist.lines.find_all(kind)
    if len(existing) > 1:
        raise EditError(
            f"directives.set: the netlist has {len(existing)} {kind.__name__} lines, so the "
            "line to replace is ambiguous; use directives.replace(line, …)"
        )
    if existing:
        return replace_directive(netlist, existing[0], text)
    return [_line_insertion(netlist, text, kind, Placement.BEFORE_END, "directives.set")]


def _directive_line(netlist: Netlist, target: Line | object, what: str) -> Line:
    line = resolve_line(netlist, target)
    item = line.item
    if isinstance(item, _TOPOLOGY_ITEMS):
        raise TopologyError(
            f"{what}: line {line.first_line} is a {_describe_item(item)}, which is topology or "
            "opaque and cannot be replaced or removed (architecture §7.3)"
        )
    if not isinstance(item, (Directive, UnknownDirective)):
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
    text = conventions.include_statement(path)
    item = classify_line(netlist, text, "add_include")
    assert isinstance(item, OpaqueStatement)  # one line starting `.include` or a parse error
    for line in netlist.lines.walk():
        if isinstance(line.item, OpaqueStatement) and line.item.raw == item.raw:
            raise EditError(f"add_include: line {line.first_line} already includes `{path}`")
    return [_line_insertion(netlist, text, OpaqueStatement, placement, "add_include")]


def _line_insertion(
    netlist: Netlist, text: str, kind: type, placement: Placement, reason: str
) -> Edit:
    point = insertion_point(placement, netlist)
    terminator = conventions.terminator_before(netlist.source, point)
    check = SlotCheck((kind,), f"one `{kind.__name__}` line")
    return Edit(Span(point, point), text + terminator, reason, (check,))


# Helpers.


def _insert(point: int, text: str, reason: str, check: SlotCheck, start: int) -> Edit:
    slot = SlotCheck(check.kinds, check.description, start, check.end)
    return Edit(Span(point, point), text, reason, (slot,))


def _last_field_end(node: object) -> int:
    """The end of the last field of an element or ``.model`` line (its span and comments
    excluded): where an added parameter goes (decision 0007 item 5)."""
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
