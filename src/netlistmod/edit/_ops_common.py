"""Shared parts of the edit operations: addressing, upsert targets, constants and helpers."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, fields, is_dataclass
from dataclasses import field as dataclass_field

from netlistmod.dialects import _XYCE, Dialect
from netlistmod.document import Line, Scope, ScopePath
from netlistmod.document.document import Netlist
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
    Diode,
    Directive,
    End,
    FrequencyAnalyzer,
    FuncStatement,
    GlobalDirective,
    GlobalParamStatement,
    IndentedLine,
    Inductor,
    Jfet,
    Mesfet,
    ModelStatement,
    Mosfet,
    OpaqueBlock,
    OpaqueStatement,
    OpDirective,
    ParamStatement,
    PreprocessDirective,
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
    element_phrase,
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


# The parameters a V line takes where the dialect reads only its port parameters: ngspice's RF
# port (manual §4.1.11); Xyce's V and I take none in X-M1 (decision 0027 item 6). LTspice's V and
# I take their own parameters (`_LTSPICE_FORMS`).
_PORT_PARAMS: dict[Dialect, frozenset[str]] = {
    Dialect.NGSPICE: frozenset({"portnum", "z0"}),
    Dialect.LTSPICE: frozenset({"portnum", "z0"}),
    _XYCE: frozenset(),
}


# Whether the dialect writes LTspice's element forms, which set_param and remove_param treat on
# their own: `Laplace=` and B's `laplace=`, V and I parameters, an R, C or L value keyword that is
# an ordinary parameter. ngspice and xyce take the other path.
_LTSPICE_FORMS: dict[Dialect, bool] = {
    Dialect.NGSPICE: False,
    Dialect.LTSPICE: True,
    _XYCE: False,
}


@dataclass(frozen=True, slots=True)
class _RclForm:
    """How a dialect writes the model of an R, C or L line (decision 0027 item 5)."""

    # Why R, C and L take no model, or None if they take one.
    no_model: str | None
    # Whether the model comes right after the nodes, before the value (xyce), rather than after
    # the value (ngspice); a value written `R=`, `C=` or `L=` may then stand beside a model.
    model_first: bool


# LTspice has no R, C or L .model type, so the semiconductor form does not exist (review R6).
_NO_LTSPICE_MODEL = "LTspice has no R, C or L model"
_RCL_FORMS: dict[Dialect, _RclForm] = {
    Dialect.NGSPICE: _RclForm(no_model=None, model_first=False),
    Dialect.LTSPICE: _RclForm(no_model=_NO_LTSPICE_MODEL, model_first=False),
    _XYCE: _RclForm(no_model=None, model_first=True),
}


# The name of a positional area, which set_param routes to its slot.
_POSITIONAL_AREA = "area"
# The elements whose area is positional, right after the model, unless it is written `area=`:
# LTspice's D and Q, J and Z on ngspice and LTspice, and Xyce's D (decision 0027 item 6; Xyce's Q,
# J and Z come with X-M4). An ngspice D and Q write `area=` only.
_POSITIONAL_AREAS: dict[Dialect, tuple[type[Component], ...]] = {
    Dialect.NGSPICE: (Jfet, Mesfet),
    Dialect.LTSPICE: (Diode, BipolarTransistor, Jfet, Mesfet),
    _XYCE: (Diode,),
}


# Whether the edit of an element field keeps comments over emptied `+` lines on the line of the
# last field (LTspice stops on a statement whose last `+` line holds only a comment; M18 D2 and
# D7b). ngspice and Xyce run it (xm1-tasks 5.1 point 3), so they take the plain removal.
_JOIN_TRAILING_COMMENTS: dict[Dialect, bool] = {
    Dialect.NGSPICE: False,
    Dialect.LTSPICE: True,
    _XYCE: False,
}


# Topology items (§7.1): directive operations never add, replace or remove them. An xyce
# `.PREPROCESS REPLACEGROUND` changes net identity, so it is topology too (P4; decision 0027
# item 3).
_TOPOLOGY_ITEMS = (Component, SubcktDefinition, GlobalDirective, PreprocessDirective)


# What directive operations write and remove: directives, and whole opaque items, whose
# contents are never edited (review round 1). `.include` is added with add_include.
_DIRECTIVE_LINES = (Directive, UnknownDirective, OpaqueBlock, OpaqueStatement)


def resolve_scope(netlist: Netlist, scope: ScopePath, in_definition: bool) -> Scope:
    """The scope an edit addresses; a non-empty ``scope`` needs ``in_definition=True``, and
    ``in_definition=True`` needs a non-empty ``scope`` (P11). A ``str`` or a ``Scope`` given as
    ``scope`` is the ``TypeError`` of ``Netlist.scope``."""
    try:
        found = netlist.scope(scope)
    except KeyError:
        raise EditError(f"no subcircuit definition scope {tuple(scope)!r}") from None
    if in_definition and not scope:
        raise EditError(
            "in_definition=True needs a definition scope, and scope=() is the top level; pass "
            "scope=(<subcircuit name>, ...) to edit a definition, or leave in_definition out"
        )
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
    GlobalParamStatement: "`.global_param` line",
    FuncStatement: "`.func` line",
    PreprocessDirective: "`.preprocess` line",
    IndentedLine: "indented line, which Xyce reads as a comment",
    ModelStatement: "`.model` line",
    Title: "title line",
    TitleDirective: "`.title` line",
    End: "`.end` line",
    BlankLine: "blank line",
    CommentLine: "comment line",
}


def _kind(element: Component) -> str:
    return element_name(element)


def _a_kind(element: Component) -> str:
    """:func:`_kind` with its article, for messages: ``an OSDI device``, ``a diode``."""
    return element_phrase(element)


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


def _removal_edit(
    netlist: Netlist, owner: Component | ModelStatement, removed: Span, reason: str
) -> Edit:
    """The edit that removes ``removed`` from ``owner``'s statement. On LTspice, when no field
    follows it and what stays after the statement's last field is comments over ``+`` lines,
    those comments join that field's line, separated by one blank, and the emptied ``+`` lines
    go: LTspice stops on a statement whose last ``+`` line holds only a comment (M18 D2 and
    D7b). ngspice runs it, so there the removal is only the span."""
    plain = Edit(removed, "", reason)
    if not _JOIN_TRAILING_COMMENTS[netlist.dialect]:
        return plain
    spans = [
        span
        for field in fields(owner)
        if field.name not in {"span", "trailing_comments"}
        for span in _spans(getattr(owner, field.name))
    ]
    if any(span.start >= removed.end for span in spans):
        return plain
    kept = max(span.end for span in spans if span.end <= removed.start)
    comments = [span for span in owner.trailing_comments if span.start >= kept]
    end = max((span.end for span in comments), default=removed.end)
    text = netlist.source.text
    rest = text[kept : removed.start] + text[removed.end : end]
    if not comments or "\n" not in rest:
        return plain
    first, *later = rest.split("\n")
    joined = [first.rstrip(" \t\r")]
    for line in later:
        content = line.lstrip(" \t")
        if not content.startswith("+"):
            return plain  # a line that is not a `+` line: left to verification
        content = content[1:].strip(" \t\r")
        if content:
            joined.append(content)
    return Edit(Span(kept, max(end, removed.end)), " ".join(joined), reason)


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


def _charge_is_not_a_param(element: Capacitor, name: str) -> EditError:
    """``q`` on an xyce C (decision 0027 item 5): the charge is a form of the line, not a
    parameter, so ``set_param`` and ``remove_param`` refuse it and point to ``set_expression``,
    which changes the charge of a line written ``Q=…``."""
    designator = element.designator
    if element.charge is not None:
        return EditError(
            f"`{name}` names the charge of `{designator}` (`Q=…`), not a parameter; use "
            "set_expression to change it"
        )
    return EditError(
        f"`{name}` names the charge form of an xyce C (`Q=…`), not a parameter, and "
        f"`{designator}` has no charge; a charge replaces the capacitance, so edit the line by "
        "hand to write one"
    )
