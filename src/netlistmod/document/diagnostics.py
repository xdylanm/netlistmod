"""Non-fatal findings about a netlist, delivered as data (architecture §8, §17).

Diagnostics are computed once when a :class:`~netlistmod.document.document.Netlist` is built and are
never raised. Their codes and severities are fixed by decision 0006.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from netlistmod.dialects import _XYCE, Dialect
from netlistmod.document.index import (
    _SWEEP_LOOKUP,
    Index,
    Reference,
    Scope,
    definition_scope,
    step_quantity,
    walk_nodes,
)
from netlistmod.document.lines import Line
from netlistmod.document.models import model_type_allowed, model_type_requirement
from netlistmod.document.names import instance_name, is_automatic_global, is_ground, net_name
from netlistmod.model._numbers import reads_as_number
from netlistmod.model.nodes import (
    AcDirective,
    Capacitor,
    Cccs,
    Ccvs,
    Component,
    CurrentSwitch,
    DataTable,
    DcDirective,
    FraProbe,
    FrequencyAnalyzer,
    GlobalDirective,
    GlobalParamStatement,
    IcDirective,
    IndentedLine,
    Inductor,
    LibCall,
    MeasureDirective,
    ModelStatement,
    NodesetDirective,
    OpDirective,
    OptionsDirective,
    Resistor,
    StepDirective,
    SubcktDefinition,
    SubcktInstance,
    TopLevelItem,
    TranDirective,
    UnknownDirective,
    Vcvs,
    VoltageSource,
    element_phrase,
)
from netlistmod.model.values import Formula, NumericValue
from netlistmod.source import SourceText, Span

Severity = Literal["warning", "info"]
# Whether an untyped `.PREPROCESS` line is xyce's `.PREPROCESS ADDRESISTORS` (decision 0028 item
# 1), the grammar's only untyped form of it, which `UNTYPED_DIRECTIVE_PRESERVED` names so; on
# ngspice and LTspice a `.preprocess` line is any unknown directive.
_UNTYPED_PREPROCESS: dict[Dialect, bool] = {
    Dialect.NGSPICE: False,
    Dialect.LTSPICE: False,
    _XYCE: True,
}


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
    FRA_PROBE_IN_IMPEDANCE_MODE = "FRA_PROBE_IN_IMPEDANCE_MODE"
    FRA_RANGE_MISSING = "FRA_RANGE_MISSING"
    INDENTED_LINE_IGNORED = "INDENTED_LINE_IGNORED"
    LIB_EXTRA_ENTRIES = "LIB_EXTRA_ENTRIES"
    NUMERIC_MODEL_NAME = "NUMERIC_MODEL_NAME"
    UNRESOLVED_DATA = "UNRESOLVED_DATA"
    ANALYSIS_IGNORED = "ANALYSIS_IGNORED"
    STEPPED_ANALYSIS_FIELD = "STEPPED_ANALYSIS_FIELD"
    STEP_IGNORED = "STEP_IGNORED"
    STEPS_WITH_OP = "STEPS_WITH_OP"
    IC_WITH_NODESET = "IC_WITH_NODESET"
    MEASURE_MODE_MISMATCH = "MEASURE_MODE_MISMATCH"
    CONDITION_IGNORED = "CONDITION_IGNORED"


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
    # An xyce call of a user-defined function is reported as a parameter is: a `.FUNC` is
    # scoped like a `.PARAM` (scoping.md S8), and Xyce stops on an unknown one (X-M1 B6).
    "function": (DiagnosticCode.UNRESOLVED_PARAM, "function"),
    # An xyce `DATA=` field (decision 0028 item 8); Xyce stops on an unknown table.
    "data": (DiagnosticCode.UNRESOLVED_DATA, "`.DATA` table"),
}
# The reference kinds looked up in their own scope only.
_OWN_SCOPE = frozenset({"element", "node", "data"})
_ORDER = {code: position for position, code in enumerate(DiagnosticCode)}
# The solver version whose behaviour a message states (validated_on of the rule tables).
_SOLVER: dict[Dialect, str] = {
    Dialect.NGSPICE: "ngspice 47",
    Dialect.LTSPICE: "LTspice 26.1.1",
    _XYCE: "Xyce 7.10",
}
# The rules below are looked up only when a netlist has what they judge, so a dialect without an
# entry (xyce, until its milestone defines the construct) fails loudly instead of reading as
# another dialect.


@dataclass(frozen=True, slots=True)
class _InstanceNodeRule:
    """How a node named ``<instance>:<node>`` reaches into an instance: LTspice (``names.md``
    N11) and Xyce (decision 0027 item 4; ``[xyce-ref]`` §2.3.1.2 p182-183)."""

    # Whether a port of the definition is reached too (LTspice joins it; Xyce keeps a net of its
    # own, as for a missing node).
    ports: bool
    # Whether the solver stops on a path to ground, a global or nothing (LTspice); Xyce reads it
    # as a net of its own.
    stops_on_global: bool
    # Where the rule is documented, for the message.
    cited: str


# Whether, and how, a node named `<instance>:<node>` reaches into an instance; ngspice: never.
_INSTANCE_NODES: dict[Dialect, _InstanceNodeRule | None] = {
    Dialect.NGSPICE: None,
    Dialect.LTSPICE: _InstanceNodeRule(ports=True, stops_on_global=True, cited=""),
    _XYCE: _InstanceNodeRule(
        ports=False, stops_on_global=False, cited=" (Xyce reference manual §2.3.1.2 p182)"
    ),
}
# The separator of an instance path in a name an expression reads (decision 0016 item 6):
# ngspice `x1.n` and `v.x1.vq`; LTspice and Xyce `X1:n` and `X1:Vq`.
_EXPRESSION_PATHS: dict[Dialect, str] = {Dialect.NGSPICE: ".", Dialect.LTSPICE: ":", _XYCE: ":"}
# What the solver does with a `.ends` that names another subcircuit.
_ENDS_NAME_RULE: dict[Dialect, str] = {
    Dialect.NGSPICE: "ngspice does not check the name (ngspice manual §2.6.2)",
    Dialect.LTSPICE: f"{_SOLVER[Dialect.LTSPICE]} does not check the name",
    _XYCE: f"{_SOLVER[_XYCE]} does not check the name",
}
# Whether a numeric value is checked against the dialect's number rules (ngspice only).
_VALUE_CHECKS: dict[Dialect, bool] = {Dialect.NGSPICE: True, Dialect.LTSPICE: False, _XYCE: False}
# What a repeated `.param`, `.model`, `.subckt` or (xyce) function in one scope stops the solver.
_REPEAT_STOPS: dict[Dialect, frozenset[str]] = {
    Dialect.NGSPICE: frozenset(),
    Dialect.LTSPICE: frozenset({"parameter", "model", "subcircuit"}),
    _XYCE: frozenset({"model", "subcircuit", "function"}),
}
# Whether the solver sorts the words of an R, C or L line by looking names up (xyce; decision
# 0027 item 5): a word in the model's place that names no model but a parameter is the value to
# Xyce, and a `.model` whose name reads as a number is taken as the model.
_LOOKUP_SORTS: dict[Dialect, bool] = {Dialect.NGSPICE: False, Dialect.LTSPICE: False, _XYCE: True}
# The severity and the rule of a repeated parameter where the solver runs on.
# What the solver does with two `.step` lines of one quantity (ngspice reads no `.step`).
_STEP_REPEATS: dict[Dialect, str | None] = {
    Dialect.NGSPICE: None,
    Dialect.LTSPICE: f"{_SOLVER[Dialect.LTSPICE]} stops with an error",
    # xm2-tasks 5.1 point 16 (observed).
    _XYCE: f"{_SOLVER[_XYCE]} nests the two sweeps of one quantity, silently",
}
# Whether the netlist's directives are checked against what the solver runs (decision 0028 item
# 9): repeated analyses, steps and their tables, options, conditions and measurements. The
# checks are Xyce's; ngspice and LTspice keep their findings unchanged.
_DIRECTIVE_CHECKS: dict[Dialect, bool] = {
    Dialect.NGSPICE: False,
    Dialect.LTSPICE: False,
    _XYCE: True,
}
_PARAM_REPEATS: dict[Dialect, tuple[Severity, str]] = {
    Dialect.NGSPICE: ("info", "the last assignment is used"),
    # Not reached: a repeated parameter stops LTspice (`_REPEAT_STOPS`); the entry keeps the table
    # whole, so a change there cannot fall through to another dialect's rule.
    Dialect.LTSPICE: ("warning", f"{_SOLVER[Dialect.LTSPICE]} stops with an error"),
    _XYCE: (
        "warning",
        "Xyce 7.10 uses the first definition, as its own warning says (the Xyce reference manual "
        "§2.1.26 p120 says the last)",
    ),
}


def collect_diagnostics(
    index: Index, source: SourceText, *, indented: tuple[Span, ...] = ()
) -> tuple[Diagnostic, ...]:
    """Compute every diagnostic of a netlist, in source order (decision 0006 items 7 and 8).

    ``indented`` holds the xyce indented lines inside continued statements (the parse's
    ``indented_comments``), which are reported as an :class:`IndentedLine` is."""
    found: list[tuple[DiagnosticCode, Severity, str, Span]] = []
    for reference in index.references:
        found.extend(_reference_findings(index, reference))
    for scope in index.scopes:
        found.extend(_duplicate_findings(scope))
        if scope.elements and _INSTANCE_NODES[index.dialect] is not None:
            found.extend(_instance_node_findings(index, scope))
    for line in index.lines.walk():
        item = line.item
        if isinstance(item, SubcktDefinition) and item.ends.name is not None:
            if index.root.fold(item.ends.name) != index.root.fold(item.name):
                assert item.ends.name_span is not None
                checks = _ENDS_NAME_RULE[index.dialect]
                found.append(
                    (
                        DiagnosticCode.ENDS_NAME_MISMATCH,
                        "info",
                        f"`.ends {item.ends.name}` closes subcircuit `{item.name}`; {checks}",
                        item.ends.name_span,
                    )
                )
        if isinstance(item, LibCall) and len(item.entries) > 1:
            found.append(
                (
                    DiagnosticCode.LIB_EXTRA_ENTRIES,
                    "info",
                    f"this `.LIB` call names {len(item.entries)} entries; "
                    f"{_SOLVER[index.dialect]} loads only the first, `{item.entries[0].name}`, "
                    "and ignores the rest with a warning",
                    Span(item.entries[1].span.start, item.entries[-1].span.end),
                )
            )
        if isinstance(item, ModelStatement):
            found.extend(_numeric_model_findings(index, item))
        if isinstance(item, IndentedLine):
            found.append(
                _indented_finding(index, Span(item.span.start, item.span.start + len(item.text)))
            )
        if isinstance(item, UnknownDirective):
            span = item.name_span or item.span
            named = item.name
            if _UNTYPED_PREPROCESS[index.dialect] and index.root.fold(item.name) == ".preprocess":
                # Only this form is untyped: REPLACEGROUND is a `PreprocessDirective`.
                named = ".PREPROCESS ADDRESISTORS"
            found.append(
                (
                    DiagnosticCode.UNTYPED_DIRECTIVE_PRESERVED,
                    "info",
                    f"`{named}` is not typed by the library and is preserved verbatim",
                    span,
                )
            )
        # Bodies are walked as their own lines, so a definition contributes only its header.
        for value in walk_nodes(item, NumericValue, bodies=False):
            if _VALUE_CHECKS[index.dialect]:
                found.extend(_value_findings(value))
    found.extend(_indented_finding(index, span) for span in indented)
    if index.dialect is Dialect.LTSPICE:
        found.extend(_fra_range_findings(index))
    if _DIRECTIVE_CHECKS[index.dialect]:
        found.extend(_directive_findings(index))
    found.sort(key=lambda entry: (entry[3].start, entry[3].end, _ORDER[entry[0]]))
    diagnostics = []
    for code, severity, message, span in found:
        line_number, column = source.position(span.start)
        diagnostics.append(Diagnostic(code, severity, message, span, line_number, column))
    return tuple(diagnostics)


def _indented_finding(index: Index, span: Span) -> tuple[DiagnosticCode, Severity, str, Span]:
    """An xyce indented line (decision 0027 item 1): on its own, an :class:`IndentedLine`, or
    between a statement and its `+` line, where it is one of the statement's comments."""
    return (
        DiagnosticCode.INDENTED_LINE_IGNORED,
        "warning",
        f"this line begins with blanks, so {_SOLVER[index.dialect]} reads it as a comment and "
        "ignores it (Xyce users' manual §4.1.3.1 p43); remove the indentation if it is meant as "
        "a statement",
        span,
    )


def _reference_findings(
    index: Index, reference: Reference
) -> list[tuple[DiagnosticCode, Severity, str, Span]]:
    findings: list[tuple[DiagnosticCode, Severity, str, Span]] = []
    scope = index.scope(reference.scope)
    if reference in index.condition_nodes:
        return _condition_findings(index, scope, reference)
    if reference.target is None and reference.kind in _UNRESOLVED:
        code, noun = _UNRESOLVED[reference.kind]
        sweep = index.sweep_targets.get(reference)
        if sweep is not None:
            noun = sweep.noun
        searched = (scope,) if reference.kind in _OWN_SCOPE else tuple(scope.chain())
        where = ", ".join(candidate.describe() for candidate in searched)
        message = f"{noun} `{reference.name}` is not defined (searched: {where})"
        severity: Severity = "warning"
        into = _into_instance(index, scope, reference) if sweep is None else None
        if sweep is not None and sweep.device:
            # The device is found, so an include changes nothing: Xyce stops on the path.
            head, _, device = reference.name.rpartition(":")
            message += (
                f"; it names device `{device}` inside instance `{head}`, not one of its parameters"
            )
        elif sweep is not None and sweep.included:
            severity = "info"
            message += (
                "; it names an element inside an instance whose definition may be in an "
                "`.include` or `.lib` file, which is not read"
            )
        elif into is not None:
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
        message += _model_place_note(index, scope, reference)
        if severity == "warning" and (sweep is not None or reference.kind == "data"):
            # Observed (X-M2 B5 probes): an undefined sweep target or table stops Xyce 7.10.
            message += f"; {_SOLVER[index.dialect]} stops on it"
        if sweep is not None and sweep.device:
            message += f"; write `{reference.name}:<param>`"
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
        cited = " (ngspice manual §2.5)" if index.dialect is Dialect.NGSPICE else ""
        findings.append(
            (
                DiagnosticCode.MODEL_TYPE_MISMATCH,
                "warning",
                f"`{owner.designator}` refers to model `{target.name}` of type "
                f"`{target.model_type}`, but {element_phrase(owner)} takes "
                f"{model_type_requirement(owner, index.dialect)}{cited}",
                reference.span,
            )
        )
    if (
        reference.kind == "element"
        and isinstance(owner, Cccs | Ccvs | CurrentSwitch)
        and any(reference.span == source.span for source in owner.control)
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
        reference.kind == "element"
        and isinstance(owner, FraProbe)
        and isinstance(target, FrequencyAnalyzer)
        and target.impedance is not None
    ):
        findings.append(
            (
                DiagnosticCode.FRA_PROBE_IN_IMPEDANCE_MODE,
                "warning",
                f"`{owner.designator}` probes for `{target.designator}`, which measures an "
                f"impedance (`{target.impedance.name}`); {_SOLVER[index.dialect]} stops on a probe "
                'in that mode ("FRA Probe not supported")',
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


def _model_place_note(index: Index, scope: Scope, reference: Reference) -> str:
    """On xyce, what Xyce does with an R, C or L word in the model's place that names no model
    but a visible parameter: it reads it as the value (xm1-tasks 5.1 point 9(b))."""
    owner = reference.owner
    if (
        reference.kind != "model"
        or not _LOOKUP_SORTS[index.dialect]
        or not isinstance(owner, Resistor | Capacitor | Inductor)
    ):
        return ""
    key = scope.fold(reference.name)
    if not any(key in candidate.params for candidate in scope.chain()):
        return ""
    return (
        f"; a parameter `{reference.name}` is visible, and {_SOLVER[index.dialect]} reads the word "
        "as the value (and stops if the line gives another one); write it in braces, "
        f"`{{{reference.name}}}`, if it is meant as the value"
    )


def _numeric_model_findings(
    index: Index, item: ModelStatement
) -> list[tuple[DiagnosticCode, Severity, str, Span]]:
    """On xyce, a `.model` whose name reads as a number (xm1-tasks 5.1 point 9(c)): the library
    reads such a word in an R, C or L line as the value, never a model (decision 0024 item 7),
    while Xyce takes it as this model."""
    if not _LOOKUP_SORTS[index.dialect] or not reads_as_number(item.name):
        return []
    return [
        (
            DiagnosticCode.NUMERIC_MODEL_NAME,
            "warning",
            f"model name `{item.name}` reads as a number: the library reads `{item.name}` on an "
            f"element line as a value, while {_SOLVER[index.dialect]} takes it as this model; "
            "rename the model so it begins with a letter",
            item.name_span,
        )
    ]


# The parameters every enabled LTspice `@` needs in a `.fra` run; `flist=` does not replace them.
_FRA_RANGE = ("fstart", "fend")


def _fra_range_findings(index: Index) -> list[tuple[DiagnosticCode, Severity, str, Span]]:
    """Each ``@`` without ``fstart=`` or ``fend=``, when the netlist runs ``.fra`` (top level
    only): LTspice stops on it ("Missing parameter"). An ``@`` with ``enabled=`` is left alone,
    since the library does not read the value; LTspice skips a disabled one."""
    root = index.root
    if not any(
        isinstance(line.item, UnknownDirective) and root.fold(line.item.name) == ".fra"
        for line in root.lines
    ):
        return []
    findings: list[tuple[DiagnosticCode, Severity, str, Span]] = []
    for line in index.lines.walk():
        item = line.item
        if not isinstance(item, FrequencyAnalyzer):
            continue
        given = {root.fold(param.name) for param in item.params}
        if "enabled" in given:
            continue
        missing = [f"`{name}=`" for name in _FRA_RANGE if name not in given]
        if missing:
            findings.append(
                (
                    DiagnosticCode.FRA_RANGE_MISSING,
                    "warning",
                    f"`{item.designator}` has no {' and no '.join(missing)}; "
                    f'{_SOLVER[index.dialect]} stops on it in a `.fra` run ("Missing '
                    'parameter"), and `flist=` does not replace them',
                    item.designator_span,
                )
            )
    return findings


# What each solver does with a controlling source that is not a V (decision 0015 item 5): where
# the dialect's manual describes the F, H or W line.
_CONTROL_REFERENCES: dict[Dialect, dict[type, str]] = {
    Dialect.NGSPICE: {
        Cccs: "ngspice manual §4.2.3",
        Ccvs: "ngspice manual §4.2.4",
        CurrentSwitch: "ngspice manual §3.3.15",
    },
    Dialect.LTSPICE: {
        Cccs: "LTspice reference",
        Ccvs: "LTspice reference",
        CurrentSwitch: "LTspice reference",
    },
    _XYCE: {
        Cccs: "Xyce reference manual §2.3.13 p234",
        Ccvs: "Xyce reference manual §2.3.15 p237",
        CurrentSwitch: "Xyce reference manual §2.3.22 p762",
    },
}


def _reference_for(owner: Component, dialect: Dialect) -> str:
    return _CONTROL_REFERENCES[dialect][type(owner)]


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
      ``K`` inductor, a ``.save I(...)``), and ``X1:n`` for a node an expression reads; Xyce
      the same, ``V(X1:n)`` (decision 0027 item 4);
    - ngspice: ``x1.n`` for a node an expression reads, and ``v.x1.vq`` (the device letter, the
      instance, the name) for a source it reads. ngspice stops on ``i(x1.vq)``, so that one
      stays a warning.
    """
    if reference.kind not in ("element", "node"):
        return None
    if _EXPRESSION_PATHS[index.dialect] == ":":
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
    """LTspice and Xyce nodes named ``<instance>:<node>``, which the library keeps as nets of
    their own."""
    findings: list[tuple[DiagnosticCode, Severity, str, Span]] = []
    solver = _SOLVER[scope.dialect]
    rule_of = _INSTANCE_NODES[scope.dialect]
    assert rule_of is not None
    for elements in scope.elements.values():
        for element in elements:
            for node in element.nodes:
                reading = _reading_of_instance_node(index, scope, node.name, rule_of)
                if reading == "joined":
                    severity: Severity = "warning"
                    rule = f"{solver} connects it to that node inside the instance{rule_of.cited}"
                elif reading == "unknown":
                    severity = "info"
                    rule = (
                        f"{solver} connects it to a node of that name in the included definition"
                        if rule_of.ports
                        else f"{solver} connects it to that node inside the instance if the "
                        "included definition has it as an internal node"
                    )
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
    index: Index, scope: Scope, name: str, rule: _InstanceNodeRule
) -> Literal["joined", "unknown", "stopped"] | None:
    """How the solver reads ``<instance>:<node>`` from ``scope``, if it names an instance there:
    LTspice ``names.md`` N11; Xyce decision 0027 item 4, where only an internal node of the
    definition (a node of a body element that is not a port, ground or a global) is joined, and
    a port, a global, ground or a missing node is a net of its own."""
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
        return "stopped" if rule.stops_on_global else None
    if child is None:
        included = any(candidate.may_define_elsewhere for candidate in scope.chain())
        return "unknown" if included else None
    if ":" in rest:
        return _reading_of_instance_node(index, child, rest, rule)
    assert child.definition is not None
    ports = {child.fold(port.name) for port in child.definition.ports}
    local = {
        child.fold(node.name)
        for elements in child.elements.values()
        for element in elements
        for node in element.nodes
    }
    local = local | ports if rule.ports else local - ports
    return "joined" if child.fold(rest) in local else None


def _is_global(index: Index, name: str) -> bool:
    """Whether a node name means the same net everywhere: ground or a global node."""
    grounded = is_ground(name, index.dialect, replace_ground=index.replace_ground)
    if grounded or is_automatic_global(name, index.dialect):
        return True
    return any(
        isinstance(line.item, GlobalDirective)
        and any(index.root.fold(node.name) == index.root.fold(name) for node in line.item.nodes)
        for line in index.lines
    )


def _duplicate_findings(scope: Scope) -> list[tuple[DiagnosticCode, Severity, str, Span]]:
    findings: list[tuple[DiagnosticCode, Severity, str, Span]] = []
    where = scope.describe()
    tables: tuple[tuple[Mapping[str, tuple[object, ...]], str], ...] = (
        (scope.params, "parameter"),
        (scope.models, "model"),
        (scope.subckts, "subcircuit"),
        (scope._functions, "function"),
    )
    defaults = {id(p) for p in (scope.definition.params if scope.definition is not None else ())}
    global_params = {
        id(assignment)
        for line in scope.lines
        if isinstance(line.item, GlobalParamStatement)
        for assignment in line.item.assignments
    }
    for table, noun in tables:
        for definitions in table.values():
            for repeated in definitions[1:]:
                name, span = _name_of(repeated)
                fatal = noun in _REPEAT_STOPS[scope.dialect]
                severity: Severity = "warning"
                if fatal:
                    rule = f"{_SOLVER[scope.dialect]} stops with an error"
                    if scope.dialect is Dialect.LTSPICE and noun == "model":
                        rule += " if an element uses it and the definitions differ"
                    elif scope.dialect is Dialect.LTSPICE and noun == "subcircuit":
                        rule += " if an instance uses it"
                elif noun == "parameter":
                    severity, rule = _PARAM_REPEATS[scope.dialect]
                    if scope.dialect is _XYCE and id(definitions[0]) in defaults:
                        rule = (
                            "Xyce 7.10 uses the `PARAMS:` default, or an instance's value, so "
                            "this `.param` is shadowed"
                        )
                    elif (
                        scope.dialect is _XYCE
                        and id(repeated) in global_params
                        and id(definitions[0]) not in global_params
                    ):
                        rule = "Xyce 7.10 uses the `.param`, not the `.global_param`"
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
    seen: dict[tuple[str, ...], Line] = {}
    for line in scope.lines:
        if isinstance(line.item, StepDirective):
            step = line.item
            quantity = (
                step_quantity(scope, step)
                if _SWEEP_LOOKUP[scope.dialect]
                else (step.kind, scope.fold(step.name))
            )
            if quantity in seen:
                repeat = _STEP_REPEATS[scope.dialect]
                assert repeat is not None  # only LTspice and xyce read `.step`
                if _SWEEP_LOOKUP[scope.dialect]:
                    repeat = f"line {seen[quantity].first_line} sweeps it already; {repeat}"
                findings.append(
                    (
                        DiagnosticCode.DUPLICATE_DEFINITION,
                        "warning",
                        f"`.step` sweeps `{step.name}` again; {repeat}",
                        step.name_span,
                    )
                )
            seen.setdefault(quantity, line)
    if _DIRECTIVE_CHECKS[scope.dialect]:
        findings.extend(_directive_repeat_findings(scope))
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


# --- xyce directives (decision 0028 item 9; xm2-tasks 5.1 points 10, 15, 16, 21, 24, 26, 27) ---

# The analyses of which Xyce runs only the last line (point 15, observed; `.NOISE`, an untyped
# line, takes part as the B5 probes show), and the one that gives way to any of them.
_LAST_WINS = ("tran", "ac", "dc", "noise")
# What Xyce 7.10 does with a field of each analysis that reads a stepped parameter (point 10;
# the R1 review's probes): it reads a `.TRAN` field once, and stops on an `.AC` or `.DC` one
# ("Attempt to evaluate expression {p}, which contains unknowns").
_STEPPED_FIELD: dict[type, str] = {
    TranDirective: "reads this `{keyword}` field once, so the sweep does not change it",
    AcDirective: "stops on this `{keyword}` field: it cannot evaluate a stepped parameter there",
    DcDirective: "stops on this `{keyword}` field: it cannot evaluate a stepped parameter there",
}

Finding = tuple[DiagnosticCode, Severity, str, Span]


def _analysis_kind(item: TopLevelItem, root: Scope) -> str | None:
    if isinstance(item, TranDirective):
        return "tran"
    if isinstance(item, AcDirective):
        return "ac"
    if isinstance(item, DcDirective):
        return "dc"
    if isinstance(item, OpDirective):
        return "op"
    if isinstance(item, UnknownDirective) and root.fold(item.name) == ".noise":
        return "noise"
    return None


def _keyword(item: TopLevelItem) -> tuple[str, Span]:
    if isinstance(item, UnknownDirective):
        return item.name, item.name_span or item.span
    keyword: str = getattr(item, "keyword")
    span: Span = getattr(item, "keyword_span")
    return keyword, span


def _directive_findings(index: Index) -> list[Finding]:
    """The xyce findings about what Xyce 7.10 runs: analyses it ignores, `.STEP` lines that do not
    act as written, `.IC` beside `.NODESET`, and `.MEAS` modes without their analysis."""
    root = index.root
    solver = _SOLVER[index.dialect]
    analyses = [(line, kind) for line in root.lines if (kind := _analysis_kind(line.item, root))]
    ranked = [(line, kind) for line, kind in analyses if kind in _LAST_WINS]
    runs: tuple[Line, str] | None = ranked[-1] if ranked else None
    if runs is None:
        runs = next(((line, kind) for line, kind in analyses if kind == "op"), None)
    findings: list[Finding] = []
    if runs is not None:
        findings.extend(_ignored_analyses(analyses, runs, solver))
    steps = [line for line in root.lines if isinstance(line.item, StepDirective)]
    findings.extend(_step_findings(index, steps, runs, solver))
    findings.extend(_ic_nodeset_findings(index, solver))
    findings.extend(_measure_findings(index, runs, solver))
    return findings


def _ignored_analyses(
    analyses: list[tuple[Line, str]], runs: tuple[Line, str], solver: str
) -> list[Finding]:
    """`ANALYSIS_IGNORED`: of `.TRAN`, `.AC`, `.DC` and `.NOISE` Xyce runs the last line's
    analysis; `.OP` gives way to any of them; every `.DC` line joins the first into one nested
    sweep, the first line innermost (point 15; the B5 probes)."""
    last, kind = runs
    last_keyword = _keyword(last.item)[0]
    first_dc = next((line for line, found in analyses if found == "dc"), None)
    findings: list[Finding] = []
    for line, found in analyses:
        keyword, span = _keyword(line.item)
        if found == "dc" and kind == "dc":
            if line is first_dc:
                continue
            assert first_dc is not None
            message = (
                f"this `{keyword}` line joins the `.DC` on line {first_dc.first_line} into one "
                f"nested sweep: {solver} runs every `.DC` line as one analysis, the sweeps of the "
                "earlier lines innermost"
            )
        elif line is last or (found == "op" and kind == "op"):
            continue
        elif found == "op":
            message = (
                f"{solver} ignores `{keyword}` when the netlist has another analysis, and runs "
                f"`{last_keyword}` (line {last.first_line})"
            )
        else:
            message = (
                f"{solver} runs only the last analysis line, `{last_keyword}` on line "
                f"{last.first_line}, and ignores this `{keyword}`"
            )
        findings.append((DiagnosticCode.ANALYSIS_IGNORED, "warning", message, span))
    return findings


def _step_findings(
    index: Index, steps: list[Line], runs: tuple[Line, str] | None, solver: str
) -> list[Finding]:
    """`STEPPED_ANALYSIS_FIELD` (point 10), `STEP_IGNORED` and `STEPS_WITH_OP` (point 16)."""
    findings: list[Finding] = []
    lines = {id(line.item): line for line in index.lines}
    stepped = {
        id(reference.target): lines[id(reference.owner)]
        for reference in index.sweep_targets
        if isinstance(reference.owner, StepDirective)
        and reference.kind == "param"
        and reference.target is not None
    }
    for reference in index.references:
        owner = reference.owner
        if (
            reference.kind == "param"
            and reference not in index.sweep_targets
            and isinstance(owner, TranDirective | AcDirective | DcDirective)
            and id(reference.target) in stepped
        ):
            findings.append(
                (
                    DiagnosticCode.STEPPED_ANALYSIS_FIELD,
                    "warning",
                    f"parameter `{reference.name}` is swept by the `.STEP` on line "
                    f"{stepped[id(reference.target)].first_line}, but {solver} "
                    + _STEPPED_FIELD[type(owner)].format(keyword=owner.keyword),
                    reference.span,
                )
            )
    tables = [line for line in steps if isinstance(line.item, StepDirective) and line.item.data]
    if tables:
        for line in steps:
            if line not in tables:
                keyword, span = _keyword(line.item)
                findings.append(
                    (
                        DiagnosticCode.STEP_IGNORED,
                        "warning",
                        f"{solver} drops this `{keyword}` line: a `.STEP DATA=` line (line "
                        f"{tables[0].first_line}) makes it ignore every other `.STEP` line",
                        span,
                    )
                )
    if len(steps) > 1 and runs is not None and runs[1] == "op":
        keyword, span = _keyword(runs[0].item)
        findings.append(
            (
                DiagnosticCode.STEPS_WITH_OP,
                "warning",
                f"{solver} aborts on an `{keyword}` analysis with {len(steps)} `.STEP` lines; "
                "one `.STEP` line, or another analysis, runs",
                span,
            )
        )
    return findings


def _ic_nodeset_findings(index: Index, solver: str) -> list[Finding]:
    """`IC_WITH_NODESET` (point 24): Xyce aborts on `.IC` or `.DCVOLT` with `.NODESET`, in any
    scope."""
    ics = [line for line in index.lines.walk() if isinstance(line.item, IcDirective)]
    if not ics:
        return []
    keyword = _keyword(ics[0].item)[0]
    findings: list[Finding] = []
    for line in index.lines.walk():
        if isinstance(line.item, NodesetDirective):
            findings.append(
                (
                    DiagnosticCode.IC_WITH_NODESET,
                    "warning",
                    f"the netlist has `{keyword}` (line {ics[0].first_line}) and "
                    f"`{line.item.keyword}`; {solver} aborts when both stand in one netlist",
                    line.item.keyword_span,
                )
            )
    return findings


def _measure_findings(index: Index, runs: tuple[Line, str] | None, solver: str) -> list[Finding]:
    """`MEASURE_MODE_MISMATCH` (point 26): a `.MEAS` mode whose analysis Xyce does not run, or
    FFT without a `.FFT` line (the B5 probes)."""
    root = index.root
    fft = any(
        isinstance(line.item, UnknownDirective) and root.fold(line.item.name) == ".fft"
        for line in root.lines
    )
    findings: list[Finding] = []
    for line in root.lines:
        item = line.item
        if not isinstance(item, MeasureDirective) or item.analysis is None:
            continue
        assert item.analysis_span is not None
        mode = root.fold(item.analysis)
        if mode == "fft":
            if not fft:
                message = (
                    f"`{item.analysis}` measures a `.FFT` line, and the netlist has none; "
                    f'{solver} stops ("No .FFT statement in netlist")'
                )
                findings.append(
                    (DiagnosticCode.MEASURE_MODE_MISMATCH, "warning", message, item.analysis_span)
                )
            continue
        # A mode needs the analysis of its name (point 26); FFT is handled above.
        needed = mode.removesuffix("_cont")
        assert needed in _LAST_WINS, mode
        if runs is not None and runs[1] == needed:
            continue
        if runs is None:
            ran = "the netlist has no analysis"
        else:
            ran = f"{solver} runs `{_keyword(runs[0].item)[0]}` (line {runs[0].first_line})"
        if needed == "dc" and runs is not None and runs[1] == "op":
            outcome = "it reports the measurement as FAILED"
        else:
            outcome = "it stops: the analysis and the measure mode do not agree"
        findings.append(
            (
                DiagnosticCode.MEASURE_MODE_MISMATCH,
                "warning",
                f"`{item.analysis}` needs a `.{needed.upper()}` analysis, but {ran}; {outcome}",
                item.analysis_span,
            )
        )
    return findings


def _condition_findings(index: Index, scope: Scope, reference: Reference) -> list[Finding]:
    """The node of an xyce `.IC`, `.DCVOLT` or `.NODESET` condition (decision 0028 items 2 and
    6; points 5, 24 and 25): a path into an instance is `NODE_INTO_INSTANCE`, as on a device line
    (decision 0027 item 4); a node nothing in the scope connects is `UNRESOLVED_NODE`, since Xyce
    ignores its condition; a global node in a body's condition is `CONDITION_IGNORED`."""
    owner = reference.owner
    assert isinstance(owner, IcDirective | NodesetDirective)
    solver = _SOLVER[index.dialect]
    name = reference.name
    rule = _INSTANCE_NODES[index.dialect]
    assert rule is not None  # only xyce makes condition nodes references
    reading = _reading_of_instance_node(index, scope, name, rule)
    if reading == "joined":
        return [
            (
                DiagnosticCode.NODE_INTO_INSTANCE,
                "warning",
                f"node `{name}` names an instance; {solver} applies the `{owner.keyword}` "
                f"condition to that node inside the instance{rule.cited}, and the library does "
                "not resolve it",
                reference.span,
            )
        ]
    if reading == "unknown":
        return [
            (
                DiagnosticCode.NODE_INTO_INSTANCE,
                "info",
                f"node `{name}` names an instance; {solver} applies the `{owner.keyword}` "
                "condition to that node inside the instance if the included definition has it as "
                "an internal node, and the library does not resolve it",
                reference.span,
            )
        ]
    if reference.target is None:
        severity: Severity = "warning"
        message = (
            f"node `{name}` is not connected to anything in {scope.describe()}; {solver} ignores "
            f"the `{owner.keyword}` condition on it, with a warning"
        )
        if scope.may_define_elsewhere:
            severity = "info"
            message += (
                "; it may be connected in an `.include` or `.lib` file or an opaque block, "
                "which is not read"
            )
        return [(DiagnosticCode.UNRESOLVED_NODE, severity, message, reference.span)]
    grounded = is_ground(name, index.dialect, replace_ground=index.replace_ground)
    if scope.definition is not None and not grounded and _is_global(index, name):
        return [
            (
                DiagnosticCode.CONDITION_IGNORED,
                "warning",
                f"node `{name}` is global, and {solver} ignores a `{owner.keyword}` condition on "
                f"a global node in a subcircuit body ({scope.describe()}), with a warning; move "
                "the condition to the top level",
                reference.span,
            )
        ]
    return []


def _directive_repeat_findings(scope: Scope) -> list[Finding]:
    """`DUPLICATE_DEFINITION` for repeated xyce options, conditions, measurements and tables,
    saying which one Xyce 7.10 uses (points 21, 24, 26 and 27)."""
    solver = _SOLVER[scope.dialect]
    where = scope.describe()
    findings: list[Finding] = []
    options: set[tuple[str, str]] = set()
    conditions: dict[type, set[str]] = {IcDirective: set(), NodesetDirective: set()}
    results: set[str] = set()
    for line in scope.lines:
        item = line.item
        if isinstance(item, OptionsDirective):
            # `.OPTION SCALE=`, the one item without a package, is PARSER's SCALE (observed).
            package = scope.fold(item.package.name) if item.package is not None else "parser"
            # Two OUTPUT lines both apply (point 21, observed), so they are not repeats.
            if package == "output":
                continue
            for option in item.options:
                option_key = (package, scope.fold(option.name))
                if option_key in options:
                    named = f" of package `{item.package.name}`" if item.package else ""
                    findings.append(
                        (
                            DiagnosticCode.DUPLICATE_DEFINITION,
                            "warning",
                            f"option `{option.name}`{named} is set again; {solver} uses the "
                            "first value, with a warning",
                            option.name_span,
                        )
                    )
                options.add(option_key)
        elif isinstance(item, IcDirective | NodesetDirective):
            seen = conditions[type(item)]
            for condition in item.conditions:
                if condition.node is None:
                    continue
                net = net_name(
                    condition.node.name, scope.dialect, replace_ground=scope._replace_ground
                )
                if net in seen:
                    what = (
                        "a `.NODESET` value"
                        if isinstance(item, NodesetDirective)
                        else ("an initial condition (`.IC` or `.DCVOLT`)")
                    )
                    findings.append(
                        (
                            DiagnosticCode.DUPLICATE_DEFINITION,
                            "warning",
                            f"node `{condition.node.name}` is given {what} again in {where}; "
                            f"{solver} uses the last value",
                            condition.node.span,
                        )
                    )
                seen.add(net)
        elif isinstance(item, MeasureDirective):
            key = scope.fold(item.result)
            if key in results:
                findings.append(
                    (
                        DiagnosticCode.DUPLICATE_DEFINITION,
                        "warning",
                        f"measurement `{item.result}` is defined again; {solver} uses the last "
                        "definition, with a warning",
                        item.result_span,
                    )
                )
            results.add(key)
    for tables in scope._data.values():
        for table in tables[1:]:
            assert isinstance(table, DataTable)
            findings.append(
                (
                    DiagnosticCode.DUPLICATE_DEFINITION,
                    "warning",
                    f"`.DATA` table `{table.name.name}` is defined again; {solver} uses the last "
                    "definition",
                    table.name.span,
                )
            )
    return findings
