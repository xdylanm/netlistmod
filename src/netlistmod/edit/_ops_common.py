"""Shared parts of the edit operations: addressing, upsert targets, constants and helpers."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, fields, is_dataclass
from dataclasses import field as dataclass_field

from netlistmod.document import Line, Netlist, Scope, ScopePath
from netlistmod.edit.plan import Edit, SlotCheck
from netlistmod.errors import EditError
from netlistmod.model.nodes import (
    AcDirective,
    BipolarTransistor,
    BlankLine,
    Capacitor,
    CommentLine,
    Component,
    CurrentSource,
    DcDirective,
    Directive,
    End,
    FrequencyAnalyzer,
    GlobalDirective,
    Inductor,
    Jfet,
    Mesfet,
    ModelStatement,
    Mosfet,
    OpaqueBlock,
    OpaqueStatement,
    OpDirective,
    ParamStatement,
    Resistor,
    SourceSpec,
    SubcktDefinition,
    TempDirective,
    Title,
    TitleDirective,
    TranDirective,
    UnknownDirective,
    VoltageSource,
    element_name,
)
from netlistmod.model.values import (
    Formula,
    Identifier,
    ModelReference,
    NumericValue,
    ValueList,
)
from netlistmod.source import Span


def _refuse_impedance_flag(element: FrequencyAnalyzer, name: str) -> None:
    """``zm`` on an ``@`` line is a flag that neither ``set_param`` nor ``remove_param`` edits
    (decision 0020 item 9; review R2 of M17)."""
    flag = element.impedance
    if flag is not None and flag.name.lower() == name.lower():
        raise EditError(
            f"`{flag.name}` of `{element.designator}` is a flag, which is not editable; "
            "edit the line by hand to add or remove it"
        )


_VALUE = SlotCheck((NumericValue, Formula, ValueList, Identifier), "a value")


_MODEL = SlotCheck((ModelReference,), "a model name")


_FUNCTION = SlotCheck((SourceSpec,), "a source function")


_TWO_TERMINAL = (Resistor, Capacitor, Inductor)


_TRANSISTORS = (BipolarTransistor, Mosfet, Jfet, Mesfet)


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


_DISTORTION_NAMES = frozenset({"DISTOF1", "DISTOF2"})


# The parameters an ngspice V line takes (RF port, manual §4.1.11).
_PORT_PARAMS = frozenset({"portnum", "z0"})


# LTspice has no R, C or L .model type, so the semiconductor form does not exist (review R6).
_NO_LTSPICE_MODEL = "LTspice has no R, C or L model"


# The name of an LTspice diode's positional area, which set_param routes to its slot.
_POSITIONAL_AREA = "area"


# Topology items (§7.1): directive operations never add, replace or remove them.
_TOPOLOGY_ITEMS = (Component, SubcktDefinition, GlobalDirective)


# What directive operations write and remove: directives, and whole opaque items, whose
# contents are never edited (review round 1). `.include` is added with add_include.
_DIRECTIVE_LINES = (Directive, UnknownDirective, OpaqueBlock, OpaqueStatement)


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
    return element_name(element)


def resolve_line(netlist: Netlist, target: Line | object) -> Line:
    """The line of ``netlist`` that is ``target`` or holds it; ``EditError`` for a stale one."""
    for line in netlist.lines.walk():
        if line is target or line.item is target:
            return line
    raise EditError(
        "the line or node does not belong to this netlist (each edit returns a new netlist; "
        "look the line up again in the netlist being edited)"
    )


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


DirectiveText = str | Sequence[str]
"""One physical line, or a sequence of physical lines (a continued statement or a block)."""


def _insert(point: int, text: str, reason: str, check: SlotCheck, start: int) -> Edit:
    slot = SlotCheck(check.kinds, check.description, start, check.end)
    return Edit(Span(point, point), text, reason, (slot,))


def _last_field_end(node: object, before: int | None = None) -> int:
    """The end of the last field of an element line (its span and comments excluded): where an
    added parameter goes (decision 0007 item 5). With ``before``, the end of the last field
    that ends at or before that offset."""
    assert is_dataclass(node) and not isinstance(node, type)
    end = 0
    for field in fields(node):
        if field.name in {"span", "trailing_comments"}:
            continue
        for span in _spans(getattr(node, field.name)):
            if before is None or span.end <= before:
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


def _comment_inside(owner: object, span: Span) -> Span | None:
    """The first end-of-line comment of ``owner`` that lies inside ``span``: only a CPL list
    over ``+`` lines can hold one (review R3)."""
    comments: tuple[Span, ...] = getattr(owner, "trailing_comments", ())
    return next((c for c in comments if span.start <= c.start < span.end), None)


def _refuse_over_comment(netlist: Netlist, comment: Span, what: str) -> EditError:
    """The refusal of an edit that would replace ``what`` across ``comment`` (decision 0017
    item 6, review R3)."""
    text = netlist.source.text[comment.start : comment.end]
    line = netlist.source.text.count("\n", 0, comment.start) + 1
    return EditError(
        f"{what} holds the comment `{text}` (line {line}); the edit would lose it. Edit the "
        "line by hand, or remove the comment first"
    )
