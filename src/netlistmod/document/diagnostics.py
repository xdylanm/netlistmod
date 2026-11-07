"""Non-fatal findings about a netlist, delivered as data (architecture §8, §17).

Diagnostics are computed once when a :class:`~netlistmod.document.Netlist` is built and are
never raised. Their codes and severities are fixed by decision 0006.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from netlistmod.dialects import Dialect
from netlistmod.document.index import Index, Reference, Scope, definition_scope, walk_nodes
from netlistmod.document.models import allowed_model_types, model_type_allowed
from netlistmod.document.names import instance_name, is_automatic_global, is_ground
from netlistmod.model.nodes import (
    Cccs,
    Ccvs,
    Component,
    CurrentSwitch,
    GlobalDirective,
    Inductor,
    ModelStatement,
    StepDirective,
    SubcktDefinition,
    SubcktInstance,
    UnknownDirective,
    Vcvs,
    VoltageSource,
    element_phrase,
)
from netlistmod.model.values import Formula, NumericValue
from netlistmod.source import SourceText, Span

Severity = Literal["warning", "info"]


class DiagnosticCode(StrEnum):
    """The code of a diagnostic (architecture §17)."""

    UNRESOLVED_MODEL = "UNRESOLVED_MODEL"
    UNRESOLVED_SUBCKT = "UNRESOLVED_SUBCKT"
    UNRESOLVED_PARAM = "UNRESOLVED_PARAM"
    UNRESOLVED_ELEMENT = "UNRESOLVED_ELEMENT"
    DUPLICATE_DEFINITION = "DUPLICATE_DEFINITION"
    DUPLICATE_ELEMENT = "DUPLICATE_ELEMENT"
    SUBCKT_PORT_MISMATCH = "SUBCKT_PORT_MISMATCH"
    PARAM_USED_BEFORE_DEFINITION = "PARAM_USED_BEFORE_DEFINITION"
    MODEL_TYPE_MISMATCH = "MODEL_TYPE_MISMATCH"
    ENDS_NAME_MISMATCH = "ENDS_NAME_MISMATCH"
    DIALECT_GATED_SYNTAX = "DIALECT_GATED_SYNTAX"
    RKM_SOLVER_MISMATCH = "RKM_SOLVER_MISMATCH"
    UNTYPED_DIRECTIVE_PRESERVED = "UNTYPED_DIRECTIVE_PRESERVED"
    NODE_INTO_INSTANCE = "NODE_INTO_INSTANCE"
    CONTROL_SOURCE_MISMATCH = "CONTROL_SOURCE_MISMATCH"
    UNRESOLVED_NODE = "UNRESOLVED_NODE"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One finding: its code, severity, a message, and where it is (1-based line and column)."""

    code: DiagnosticCode
    severity: Severity
    message: str
    span: Span
    line: int
    column: int


_UNRESOLVED: dict[str, tuple[DiagnosticCode, str]] = {
    "model": (DiagnosticCode.UNRESOLVED_MODEL, "model"),
    "subckt": (DiagnosticCode.UNRESOLVED_SUBCKT, "subcircuit"),
    "param": (DiagnosticCode.UNRESOLVED_PARAM, "parameter"),
    "element": (DiagnosticCode.UNRESOLVED_ELEMENT, "element"),
    "node": (DiagnosticCode.UNRESOLVED_NODE, "node"),
}
_ORDER = {code: position for position, code in enumerate(DiagnosticCode)}
# The solver version whose behaviour a message states (validated_on of the rule tables).
_SOLVER: dict[Dialect, str] = {Dialect.NGSPICE: "ngspice 47", Dialect.LTSPICE: "LTspice 26.1.1"}


def collect_diagnostics(index: Index, source: SourceText) -> tuple[Diagnostic, ...]:
    """Compute every diagnostic of a netlist, in source order (decision 0006 items 7 and 8)."""
    found: list[tuple[DiagnosticCode, Severity, str, Span]] = []
    for reference in index.references:
        found.extend(_reference_findings(index, reference))
    for scope in index.scopes:
        found.extend(_duplicate_findings(scope))
        if index.dialect is Dialect.LTSPICE:
            found.extend(_instance_node_findings(index, scope))
    for line in index.lines.walk():
        item = line.item
        if isinstance(item, SubcktDefinition) and item.ends.name is not None:
            if index.root.fold(item.ends.name) != index.root.fold(item.name):
                assert item.ends.name_span is not None
                checks = (
                    "ngspice does not check the name (ngspice manual §2.6.2)"
                    if index.dialect is Dialect.NGSPICE
                    else f"{_SOLVER[index.dialect]} does not check the name"
                )
                found.append(
                    (
                        DiagnosticCode.ENDS_NAME_MISMATCH,
                        "info",
                        f"`.ends {item.ends.name}` closes subcircuit `{item.name}`; {checks}",
                        item.ends.name_span,
                    )
                )
        if isinstance(item, UnknownDirective):
            span = item.name_span or item.span
            found.append(
                (
                    DiagnosticCode.UNTYPED_DIRECTIVE_PRESERVED,
                    "info",
                    f"`{item.name}` is not typed by the library and is preserved verbatim",
                    span,
                )
            )
        # Bodies are walked as their own lines, so a definition contributes only its header.
        for value in walk_nodes(item, NumericValue, bodies=False):
            if index.dialect is Dialect.NGSPICE:
                found.extend(_value_findings(value))
    found.sort(key=lambda entry: (entry[3].start, entry[3].end, _ORDER[entry[0]]))
    diagnostics = []
    for code, severity, message, span in found:
        line_number, column = source.position(span.start)
        diagnostics.append(Diagnostic(code, severity, message, span, line_number, column))
    return tuple(diagnostics)


def _reference_findings(
    index: Index, reference: Reference
) -> list[tuple[DiagnosticCode, Severity, str, Span]]:
    findings: list[tuple[DiagnosticCode, Severity, str, Span]] = []
    scope = index.scope(reference.scope)
    if reference.target is None and reference.kind in _UNRESOLVED:
        code, noun = _UNRESOLVED[reference.kind]
        searched = (scope,) if reference.kind in ("element", "node") else tuple(scope.chain())
        where = ", ".join(candidate.describe() for candidate in searched)
        message = f"{noun} `{reference.name}` is not defined (searched: {where})"
        severity: Severity = "warning"
        into = _into_instance(index, scope, reference)
        if into is not None:
            severity = "info"
            what = "a node" if reference.kind == "node" else "a source"
            message += (
                f"; it names {what} inside instance `{into}`, which {_SOLVER[index.dialect]} "
                "reads and the library does not resolve"
            )
        elif any(candidate.may_define_elsewhere for candidate in searched):
            severity = "info"
            message += (
                "; it may be defined in an `.include` or `.lib` file or an opaque block, which "
                "is not read"
            )
        findings.append((code, severity, message, reference.span))
    if reference in index.late_param_uses:
        findings.append(
            (
                DiagnosticCode.PARAM_USED_BEFORE_DEFINITION,
                "warning",
                f"parameter `{reference.name}` is used before its `.param` definition"
                f"{' (ngspice manual §2.11.1)' if index.dialect is Dialect.NGSPICE else ''}; "
                f"{_SOLVER[index.dialect]} still resolves it",
                reference.span,
            )
        )
    owner = reference.owner
    target = reference.target
    if (
        reference.kind == "model"
        and isinstance(target, ModelStatement)
        and isinstance(owner, Component)
        and not model_type_allowed(owner, target.model_type, index.dialect)
    ):
        allowed = ", ".join(
            f"`{kind.upper()}`" for kind in sorted(allowed_model_types(owner, index.dialect))
        )
        cited = " (ngspice manual §2.5)" if index.dialect is Dialect.NGSPICE else ""
        findings.append(
            (
                DiagnosticCode.MODEL_TYPE_MISMATCH,
                "warning",
                f"`{owner.designator}` refers to model `{target.name}` of type "
                f"`{target.model_type}`, but {element_phrase(owner)} takes a model of "
                f"type {allowed}{cited}",
                reference.span,
            )
        )
    if (
        reference.kind == "element"
        and isinstance(owner, Cccs | Ccvs | CurrentSwitch)
        and owner.control is not None
        and reference.span == owner.control.span
        and target is not None
        and isinstance(target, Component)
        and not isinstance(target, VoltageSource)
    ):
        findings.append(
            (
                DiagnosticCode.CONTROL_SOURCE_MISMATCH,
                "warning",
                f"`{owner.designator}` is controlled by `{reference.name}`, "
                f"{element_phrase(target)}, but the {_reference_for(owner, index.dialect)} "
                f"names an independent voltage source (`V`); "
                f"{_control_outcome(target, reference.name, index.dialect)}",
                reference.span,
            )
        )
    if (
        reference.kind == "subckt"
        and isinstance(reference.target, SubcktDefinition)
        and isinstance(owner, SubcktInstance)
        and len(owner.nodes) != len(reference.target.ports)
    ):
        findings.append(
            (
                DiagnosticCode.SUBCKT_PORT_MISMATCH,
                "warning",
                f"`{owner.designator}` connects {len(owner.nodes)} nodes, but subcircuit "
                f"`{reference.target.name}` has {len(reference.target.ports)} ports",
                reference.span,
            )
        )
    return findings


# What each solver does with a controlling source that is not a V (decision 0015 item 5).
_MANUAL_SECTION: dict[type, str] = {Cccs: "4.2.3", Ccvs: "4.2.4", CurrentSwitch: "3.3.15"}


def _reference_for(owner: Component, dialect: Dialect) -> str:
    if dialect is Dialect.LTSPICE:
        return "LTspice reference"
    return f"ngspice manual §{_MANUAL_SECTION[type(owner)]}"


_CONTROL_RUNS: dict[Dialect, tuple[type, ...]] = {
    Dialect.NGSPICE: (Vcvs, Ccvs),
    Dialect.LTSPICE: (Vcvs, Ccvs, Inductor),
}


def _control_outcome(target: Component, name: str, dialect: Dialect) -> str:
    """What the dialect's solver does with this controlling source (review R2)."""
    if isinstance(target, _CONTROL_RUNS[dialect]):
        return f"{_SOLVER[dialect]} runs it, with the current through `{name}`"
    return f"{_SOLVER[dialect]} stops on it"


def _into_instance(index: Index, scope: Scope, reference: Reference) -> str | None:
    """The instance of the scope that an unresolved name reaches into, if it names one.

    Both solvers read such a name and the library keeps it as text, a known limit (§7.8;
    decision 0016 item 6):

    - LTspice: ``X1:Vq`` for any element reference (a controlling source, an ``I()`` read, a
      ``K`` inductor, a ``.save I(...)``), and ``X1:n`` for a node an expression reads;
    - ngspice: ``x1.n`` for a node an expression reads, and ``v.x1.vq`` (the device letter, the
      instance, the name) for a source it reads. ngspice stops on ``i(x1.vq)``, so that one
      stays a warning.
    """
    if reference.kind not in ("element", "node"):
        return None
    if index.dialect is Dialect.LTSPICE:
        head, colon, _ = reference.name.partition(":")
        if not colon:
            return None
    elif reference.kind == "node":
        head, dot, _ = reference.name.partition(".")
        if not dot:
            return None
    else:
        parts = reference.name.split(".")
        if len(parts) < 3 or len(parts[0]) != 1 or reference.owner is None:
            return None
        if not _is_expression_read(reference):
            return None
        head = parts[1]
    instance = next(iter(scope.elements.get(scope.fold(head), ())), None)
    return head if isinstance(instance, SubcktInstance) else None


def _is_expression_read(reference: Reference) -> bool:
    """Whether an element reference is an ``i()`` read in a behavioural expression."""
    owner = reference.owner
    formulas = [
        getattr(owner, "expression", None),
        getattr(owner, "charge", None),
        getattr(owner, "flux", None),
        getattr(owner, "value", None),
    ]
    return any(
        isinstance(formula, Formula)
        and formula.span.start <= reference.span.start < formula.span.end
        for formula in formulas
    )


def _instance_node_findings(
    index: Index, scope: Scope
) -> list[tuple[DiagnosticCode, Severity, str, Span]]:
    """LTspice nodes named ``<instance>:<node>``, which the library keeps as nets of their own."""
    findings: list[tuple[DiagnosticCode, Severity, str, Span]] = []
    solver = _SOLVER[scope.dialect]
    for elements in scope.elements.values():
        for element in elements:
            for node in element.nodes:
                reading = _reading_of_instance_node(index, scope, node.name)
                if reading == "joined":
                    severity: Severity = "warning"
                    rule = f"{solver} connects it to that node inside the instance"
                elif reading == "unknown":
                    severity = "info"
                    rule = f"{solver} connects it to a node of that name in the included definition"
                elif reading == "stopped":
                    severity = "warning"
                    rule = f"{solver} stops: the part after the instance is not a local node"
                else:
                    continue
                findings.append(
                    (
                        DiagnosticCode.NODE_INTO_INSTANCE,
                        severity,
                        f"node `{node.name}` names an instance; {rule}, and the library keeps it "
                        "as a separate net",
                        node.span,
                    )
                )
    return findings


def _reading_of_instance_node(
    index: Index, scope: Scope, name: str
) -> Literal["joined", "unknown", "stopped"] | None:
    """How LTspice reads ``<instance>:<node>`` from ``scope`` (``names.md`` N11), if it is one."""
    head, colon, rest = name.partition(":")
    if not colon:
        return None
    key = scope.fold(head)
    instance = next(
        (
            element
            for elements in scope.elements.values()
            for element in elements
            if isinstance(element, SubcktInstance)
            and instance_name(element.designator, scope.dialect) == key
        ),
        None,
    )
    if instance is None:
        return None
    child = definition_scope(scope, instance.subckt.name)
    if ":" not in rest and (not rest or _is_global(index, rest)):
        return "stopped"
    if child is None:
        included = any(candidate.may_define_elsewhere for candidate in scope.chain())
        return "unknown" if included else None
    if ":" in rest:
        return _reading_of_instance_node(index, child, rest)
    assert child.definition is not None
    local = {child.fold(port.name) for port in child.definition.ports}
    local.update(
        child.fold(node.name)
        for elements in child.elements.values()
        for element in elements
        for node in element.nodes
    )
    return "joined" if child.fold(rest) in local else None


def _is_global(index: Index, name: str) -> bool:
    """Whether a node name means the same net everywhere: ground or a global node."""
    if is_ground(name, index.dialect) or is_automatic_global(name, index.dialect):
        return True
    return any(
        isinstance(line.item, GlobalDirective)
        and any(index.root.fold(node.name) == index.root.fold(name) for node in line.item.nodes)
        for line in index.lines
    )


def _duplicate_findings(scope: Scope) -> list[tuple[DiagnosticCode, Severity, str, Span]]:
    findings: list[tuple[DiagnosticCode, Severity, str, Span]] = []
    where = scope.describe()
    fatal = scope.dialect is Dialect.LTSPICE
    tables: tuple[tuple[Mapping[str, tuple[object, ...]], str, Severity], ...] = (
        # LTspice stops at a repeated .param; ngspice uses the last one silently.
        (scope.params, "parameter", "warning" if fatal else "info"),
        (scope.models, "model", "warning"),
        (scope.subckts, "subcircuit", "warning"),
    )
    for table, noun, severity in tables:
        for definitions in table.values():
            for repeated in definitions[1:]:
                name, span = _name_of(repeated)
                if fatal:
                    rule = f"{_SOLVER[scope.dialect]} stops with an error"
                    if noun == "model":
                        rule += " if an element uses it and the definitions differ"
                    elif noun == "subcircuit":
                        rule += " if an instance uses it"
                elif noun == "parameter":
                    rule = "the last assignment is used"
                else:
                    rule = "ngspice uses the first definition"
                findings.append(
                    (
                        DiagnosticCode.DUPLICATE_DEFINITION,
                        severity,
                        f"{noun} `{name}` is defined again in {where}; {rule}",
                        span,
                    )
                )
    seen: set[tuple[str, str]] = set()
    for line in scope.lines:
        if isinstance(line.item, StepDirective):
            quantity = (line.item.kind, scope.fold(line.item.name))
            if quantity in seen:
                findings.append(
                    (
                        DiagnosticCode.DUPLICATE_DEFINITION,
                        "warning",
                        f"`.step` sweeps `{line.item.name}` again; {_SOLVER[scope.dialect]} stops "
                        "with an error",
                        line.item.name_span,
                    )
                )
            seen.add(quantity)
    for elements in scope.elements.values():
        for repeated in elements[1:]:
            findings.append(
                (
                    DiagnosticCode.DUPLICATE_ELEMENT,
                    "warning",
                    f"element `{repeated.designator}` repeats a designator in {where} "
                    f"(case-insensitive); {_SOLVER[scope.dialect]} stops with an error",
                    repeated.designator_span,
                )
            )
    return findings


def _name_of(definition: object) -> tuple[str, Span]:
    name: str = getattr(definition, "name")
    span: Span = getattr(definition, "name_span")
    return name, span


def _value_findings(value: NumericValue) -> list[tuple[DiagnosticCode, Severity, str, Span]]:
    findings: list[tuple[DiagnosticCode, Severity, str, Span]] = []
    if value.notation == "rkm":
        findings.append(
            (
                DiagnosticCode.DIALECT_GATED_SYNTAX,
                "info",
                f"`{value.text}` is RKM notation, which ngspice reads only in LT compatibility "
                "mode",
                value.span,
            )
        )
    if value.solver_mismatch:
        findings.append(
            (
                DiagnosticCode.RKM_SOLVER_MISMATCH,
                "warning",
                f"`{value.text}` is read per IEC 60062, but ngspice reads it differently",
                value.span,
            )
        )
    return findings
