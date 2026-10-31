"""Non-fatal findings about a netlist, delivered as data (architecture §8, §17).

Diagnostics are computed once when a :class:`~netlistmod.document.Netlist` is built and are
never raised. Their codes and severities are fixed by decision 0006.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from netlistmod.document.index import Index, Reference, Scope, walk_nodes
from netlistmod.document.models import allowed_model_types, model_type_allowed
from netlistmod.document.names import fold
from netlistmod.model.nodes import (
    Component,
    ModelStatement,
    SubcktDefinition,
    SubcktInstance,
    UnknownDirective,
)
from netlistmod.model.values import NumericValue
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
    UNKNOWN_DIRECTIVE_PRESERVED = "UNKNOWN_DIRECTIVE_PRESERVED"


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
}
_ORDER = {code: position for position, code in enumerate(DiagnosticCode)}


def collect_diagnostics(index: Index, source: SourceText) -> tuple[Diagnostic, ...]:
    """Compute every diagnostic of a netlist, in source order (decision 0006 items 7 and 8)."""
    found: list[tuple[DiagnosticCode, Severity, str, Span]] = []
    for reference in index.references:
        found.extend(_reference_findings(index, reference))
    for scope in index.scopes:
        found.extend(_duplicate_findings(scope))
    for line in index.lines.walk():
        item = line.item
        if isinstance(item, SubcktDefinition) and item.ends.name is not None:
            if fold(item.ends.name) != fold(item.name):
                assert item.ends.name_span is not None
                found.append(
                    (
                        DiagnosticCode.ENDS_NAME_MISMATCH,
                        "info",
                        f"`.ends {item.ends.name}` closes subcircuit `{item.name}`; ngspice "
                        "does not check the name (§2.6.2)",
                        item.ends.name_span,
                    )
                )
        if isinstance(item, UnknownDirective):
            span = item.name_span or item.span
            found.append(
                (
                    DiagnosticCode.UNKNOWN_DIRECTIVE_PRESERVED,
                    "info",
                    f"`{item.name}` is not typed by the library and is preserved verbatim",
                    span,
                )
            )
        # Bodies are walked as their own lines, so a definition contributes only its header.
        for value in walk_nodes(item, NumericValue, bodies=False):
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
        searched = (scope,) if reference.kind == "element" else tuple(scope.chain())
        where = ", ".join(candidate.describe() for candidate in searched)
        message = f"{noun} `{reference.name}` is not defined (searched: {where})"
        severity: Severity = "warning"
        if any(candidate.has_opaque_include for candidate in searched):
            severity = "info"
            message += "; it may be defined in an `.include` or `.lib` file, which is not read"
        findings.append((code, severity, message, reference.span))
    if reference in index.late_param_uses:
        findings.append(
            (
                DiagnosticCode.PARAM_USED_BEFORE_DEFINITION,
                "warning",
                f"parameter `{reference.name}` is used before its `.param` definition "
                "(§2.11.1); ngspice 47 still resolves it",
                reference.span,
            )
        )
    owner = reference.owner
    target = reference.target
    if (
        reference.kind == "model"
        and isinstance(target, ModelStatement)
        and isinstance(owner, Component)
        and not model_type_allowed(owner, target.model_type)
    ):
        allowed = ", ".join(f"`{kind.upper()}`" for kind in sorted(allowed_model_types(owner)))
        findings.append(
            (
                DiagnosticCode.MODEL_TYPE_MISMATCH,
                "warning",
                f"`{owner.designator}` refers to model `{target.name}` of type "
                f"`{target.model_type}`, but a {type(owner).__name__.lower()} takes a model of "
                f"type {allowed} (§2.5)",
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


def _duplicate_findings(scope: Scope) -> list[tuple[DiagnosticCode, Severity, str, Span]]:
    findings: list[tuple[DiagnosticCode, Severity, str, Span]] = []
    where = scope.describe()
    tables: tuple[tuple[Mapping[str, tuple[object, ...]], str, Severity], ...] = (
        (scope.params, "parameter", "info"),
        (scope.models, "model", "warning"),
        (scope.subckts, "subcircuit", "warning"),
    )
    for table, noun, severity in tables:
        for definitions in table.values():
            for repeated in definitions[1:]:
                name, span = _name_of(repeated)
                rule = (
                    "the last assignment is used"
                    if noun == "parameter"
                    else "ngspice uses the first definition"
                )
                findings.append(
                    (
                        DiagnosticCode.DUPLICATE_DEFINITION,
                        severity,
                        f"{noun} `{name}` is defined again in {where}; {rule}",
                        span,
                    )
                )
    for elements in scope.elements.values():
        for repeated in elements[1:]:
            findings.append(
                (
                    DiagnosticCode.DUPLICATE_ELEMENT,
                    "warning",
                    f"element `{repeated.designator}` repeats a designator in {where} "
                    "(case-insensitive); ngspice 47 stops with an error",
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
                "mode (decision 0004)",
                value.span,
            )
        )
    if value.solver_mismatch:
        findings.append(
            (
                DiagnosticCode.RKM_SOLVER_MISMATCH,
                "warning",
                f"`{value.text}` is read per IEC 60062, but ngspice reads it differently "
                "(decision 0004)",
                value.span,
            )
        )
    return findings
