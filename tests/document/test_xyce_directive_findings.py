"""The document layer on xyce directives (X-M2 B5; decision 0028 items 2, 4, 6, 8 and 9;
xm2-tasks 5.1 points 5, 10, 14 to 16, 21 and 24 to 27): sweep targets resolved as Xyce resolves
them, `DATA=` references, the nodes of initial conditions, and the warnings about what Xyce runs.

Every claim about Xyce in a message is evidenced by the solver tests of X-M2 B6."""

from __future__ import annotations

import pytest

from netlistmod import DiagnosticCode, Dialect, Netlist, ParseError
from netlistmod.dialects import _XYCE
from netlistmod.document.index import step_quantity
from netlistmod.model.nodes import (
    Component,
    DataTable,
    DcDirective,
    ModelStatement,
    StepDirective,
)
from netlistmod.model.values import ParamAssignment

_CIRCUIT = (
    "V1 1 0 1\nI1 0 1 1m\nR2 1 2 1k\nC1 2 0 1p\nL1 2 3 1u\nR3 3 0 1k\n.model dm D\nD1 3 0 dm\n"
)
_DIV = ".subckt div a b\nR1 a m 1\nC1 m b 1p\n.ends\n"


def _netlist(body: str) -> Netlist:
    return Netlist.from_text(f"t\n{_CIRCUIT}{body}.end\n", dialect=_XYCE)


def _codes(netlist: Netlist) -> list[tuple[int, DiagnosticCode, str]]:
    return [(d.line, d.code, d.severity) for d in netlist.diagnostics]


def _only(netlist: Netlist, code: DiagnosticCode) -> list[str]:
    return [d.message for d in netlist.diagnostics if d.code is code]


# --- Sweep targets (decision 0028 item 4; points 12 and 14) ---


@pytest.mark.parametrize(
    ("directive", "kind", "name", "target"),
    [
        (".dc V1 0 1 0.5", "element", "V1", Component),
        (".dc R2 1k 2k 1k", "element", "R2", Component),
        (".dc R2:R 1k 2k 1k", "element", "R2", Component),
        (".dc dm:IS 1e-14 1e-13 1e-14", "model", "dm", ModelStatement),
        (".dc p 0 1 0.5", "param", "p", ParamAssignment),
        (".dc g 0 1 0.5", "param", "g", ParamAssignment),
        (".step R2 1k 2k 1k", "element", "R2", Component),
        (".step R2:R LIST 1k 2k", "element", "R2", Component),
        (".step dm:IS 1e-14 1e-13 1e-14", "model", "dm", ModelStatement),
        (".step p 1 2 1", "param", "p", ParamAssignment),
        (".step X1:R1:R 1 2 1", "element", "X1:R1", Component),
    ],
)
def test_a_sweep_target_resolves_as_xyce_resolves_it(
    directive: str, kind: str, name: str, target: type
) -> None:
    netlist = _netlist(f".param p=1\n.global_param g=1\nX1 1 0 div\n{_DIV}{directive}\n.op\n")
    (reference,) = [
        r for r in netlist.references if isinstance(r.owner, StepDirective | DcDirective)
    ]
    assert (reference.kind, reference.name) == (kind, name)
    assert isinstance(reference.target, target)
    assert netlist.slice(reference.span) == name
    assert not [d for d in netlist.diagnostics if d.code.name.startswith("UNRESOLVED")]


def test_a_parameter_comes_before_an_element_of_the_same_name() -> None:
    netlist = _netlist(".param R2=5\n.step R2 1 2 1\n.tran 1n 2n\n")
    (reference,) = [r for r in netlist.references if isinstance(r.owner, StepDirective)]
    assert reference.kind == "param"
    assert isinstance(reference.target, ParamAssignment)


def test_a_repeated_parameter_target_is_the_first_assignment() -> None:
    netlist = _netlist(".param p=1\n.param p=2\n.dc p 0 1 0.5\n")
    (reference,) = [r for r in netlist.references if r.name == "p" and r.kind == "param"]
    assert isinstance(reference.target, ParamAssignment)
    assert netlist.slice(reference.target.span) == "p=1"


def test_temp_is_no_reference() -> None:
    netlist = _netlist(".step TEMP 0 100 50\n.dc temp 0 100 50\n")
    assert [r for r in netlist.references if r.name.lower() == "temp"] == []
    assert _codes(netlist) == []


@pytest.mark.parametrize(
    ("directive", "code", "noun"),
    [
        (".dc zz 0 1 0.5", DiagnosticCode.UNRESOLVED_PARAM, "parameter or element `zz`"),
        (".step zz 1 2 1", DiagnosticCode.UNRESOLVED_PARAM, "parameter or element `zz`"),
        (".dc zz:R 0 1 0.5", DiagnosticCode.UNRESOLVED_ELEMENT, "element or model `zz`"),
        (".step zz:IS 1 2 1", DiagnosticCode.UNRESOLVED_ELEMENT, "element or model `zz`"),
        (".step X1:R9:R 1 2 1", DiagnosticCode.UNRESOLVED_ELEMENT, "element `X1:R9`"),
        (".step X7:R1:R 1 2 1", DiagnosticCode.UNRESOLVED_ELEMENT, "element `X7:R1`"),
        (".step R2:R1:R 1 2 1", DiagnosticCode.UNRESOLVED_ELEMENT, "element `R2:R1`"),
    ],
)
def test_an_unresolved_sweep_target_is_a_warning(
    directive: str, code: DiagnosticCode, noun: str
) -> None:
    netlist = _netlist(f"X1 1 0 div\n{_DIV}{directive}\n.op\n")
    (finding,) = [d for d in netlist.diagnostics if d.code.name.startswith("UNRESOLVED")]
    assert (finding.code, finding.severity) == (code, "warning")
    assert finding.message.startswith(f"{noun} is not defined (searched: top level)")
    assert "Xyce 7.10 stops on it" in finding.message


def test_an_unresolved_target_with_an_include_is_info() -> None:
    netlist = _netlist('.include "more.lib"\n.step zz 1 2 1\n.dc yy:R 0 1 1\n')
    found = [(d.code, d.severity) for d in netlist.diagnostics if d.code.name.startswith("UNRES")]
    assert found == [
        (DiagnosticCode.UNRESOLVED_PARAM, "info"),
        (DiagnosticCode.UNRESOLVED_ELEMENT, "info"),
    ]
    assert all("stops" not in message for message in _only(netlist, found[0][0]))


def test_a_path_into_an_included_definition_is_info() -> None:
    netlist = _netlist('.include "div.lib"\nX1 1 0 div\n.step X1:R1:R 1 2 1\n')
    (finding,) = [d for d in netlist.diagnostics if d.code is DiagnosticCode.UNRESOLVED_ELEMENT]
    assert "inside an instance whose definition may be in an `.include`" in finding.message
    assert finding.severity == "info"


def test_a_nested_path_reaches_through_each_instance() -> None:
    inner = ".subckt top p q\nX2 p q div\n.ends\n"
    netlist = _netlist(f"X1 1 0 top\n{inner}{_DIV}.step X1:X2:R1:R 1 2 1\n")
    (reference,) = [r for r in netlist.references if isinstance(r.owner, StepDirective)]
    assert isinstance(reference.target, Component)
    assert reference.target.designator == "R1"
    assert _codes(netlist) == []


@pytest.mark.parametrize(
    ("directive", "target"),
    [
        (".step X1:R1 1 2 1", "X1:R1"),
        (".dc X1:R1 1 2 1", "X1:R1"),
        (".step x1:c1 1p 2p 1p", "x1:c1"),
        (".step X3:X2:R1 1 2 1", "X3:X2:R1"),
    ],
)
def test_a_path_to_a_device_without_its_parameter_is_unresolved(
    directive: str, target: str
) -> None:
    # R1 review gap 1: Xyce stops on `X1:R5` ("X1:R5 is not defined"); `X1:R5:R` runs.
    inner = ".subckt top p q\nX2 p q div\n.ends\n"
    netlist = _netlist(f"X1 1 0 div\nX3 1 0 top\n{inner}{_DIV}{directive}\n.op\n")
    (reference,) = [
        r for r in netlist.references if isinstance(r.owner, StepDirective | DcDirective)
    ]
    assert (reference.kind, reference.name, reference.target) == ("element", target, None)
    assert netlist.slice(reference.span) == target
    (finding,) = [d for d in netlist.diagnostics if d.code.name.startswith("UNRESOLVED")]
    assert (finding.code, finding.severity) == (DiagnosticCode.UNRESOLVED_ELEMENT, "warning")
    head, _, device = target.rpartition(":")
    assert finding.message == (
        f"element parameter `{target}` is not defined (searched: top level); it names device "
        f"`{device}` inside instance `{head}`, not one of its parameters; Xyce 7.10 stops on "
        f"it; write `{target}:<param>`"
    )


def test_a_path_to_a_device_stays_a_warning_with_an_include() -> None:
    netlist = _netlist(f'.include "more.lib"\nX1 1 0 div\n{_DIV}.step X1:R1 1 2 1\n')
    (finding,) = [d for d in netlist.diagnostics if d.code is DiagnosticCode.UNRESOLVED_ELEMENT]
    assert finding.severity == "warning"
    assert "Xyce 7.10 stops on it" in finding.message


def test_a_path_to_a_device_keeps_the_part_after_the_last_colon() -> None:
    # The form alone cannot tell `X1:R1` from `R2:R`, so `parameter` is `R1` (N4).
    netlist = _netlist(f"X1 1 0 div\n{_DIV}.step X1:R1 1 2 1\n.op\n")
    (step,) = [line.item for line in netlist.lines if isinstance(line.item, StepDirective)]
    assert (step.kind, step.name, step.parameter) == ("qualified", "X1:R1", "R1")


def test_the_other_dialects_keep_their_dc_targets() -> None:
    # ngspice and LTspice: a `.dc` target is an element (LTspice's `.step` says what it sweeps).
    for dialect in (Dialect.NGSPICE, Dialect.LTSPICE):
        netlist = Netlist.from_text(
            "t\n.param p=1\nV1 1 0 1\n.dc p 0 1 0.5\n.end\n", dialect=dialect
        )
        (reference,) = netlist.references
        assert (reference.kind, reference.target) == ("element", None)


# --- DATA= (decision 0028 item 8; point 27) ---

_TABLE = ".data tab r2:r\n+ 1k\n+ 2k\n.enddata\n"


@pytest.mark.parametrize(
    "directive", [".ac DATA=tab", ".dc DATA=tab", ".step DATA=tab", ".step data = TAB"]
)
def test_a_data_field_refers_to_its_table(directive: str) -> None:
    netlist = _netlist(f"{directive}\n{_TABLE}")
    (reference,) = [r for r in netlist.references if r.kind == "data"]
    assert isinstance(reference.target, DataTable)
    assert reference.target.name.name == "tab"
    assert netlist.slice(reference.span).lower() == "tab"
    assert not _only(netlist, DiagnosticCode.UNRESOLVED_DATA)


def test_a_repeated_table_resolves_to_the_last_and_is_a_warning() -> None:
    netlist = _netlist(f"{_TABLE}.ac DATA=tab\n{_TABLE.replace('tab', 'TAB')}")
    (reference,) = [r for r in netlist.references if r.kind == "data"]
    assert isinstance(reference.target, DataTable)
    assert reference.target.name.name == "TAB"
    (finding,) = [d for d in netlist.diagnostics if d.code is DiagnosticCode.DUPLICATE_DEFINITION]
    assert finding.severity == "warning"
    assert finding.message == (
        "`.DATA` table `TAB` is defined again; Xyce 7.10 uses the last definition"
    )


def test_an_unknown_table_is_a_warning() -> None:
    netlist = _netlist(".ac DATA=nope\n")
    (finding,) = netlist.diagnostics
    assert (finding.code, finding.severity, finding.line) == (
        DiagnosticCode.UNRESOLVED_DATA,
        "warning",
        10,
    )
    assert finding.message == (
        "`.DATA` table `nope` is not defined (searched: top level); Xyce 7.10 stops on it"
    )


def test_an_unknown_table_with_an_include_is_info() -> None:
    netlist = _netlist('.include "t.lib"\n.dc DATA=nope\n')
    (finding,) = _only(netlist, DiagnosticCode.UNRESOLVED_DATA)
    assert "may be defined in an `.include`" in finding


def test_a_table_is_found_wherever_it_stands() -> None:
    assert _codes(_netlist(f"{_TABLE}.step DATA=tab\n.tran 1n 2n\n")) == []


# --- The .TRAN schedule (decision 0028 item 3) ---


def test_the_schedule_is_no_function_reference_but_its_arguments_are_read() -> None:
    netlist = _netlist(".param tmax=1n\n.tran 1n 10n {schedule(0, tmax, 5n, 2n)}\n")
    assert [(r.kind, r.name) for r in netlist.references] == [("model", "dm"), ("param", "tmax")]
    assert _codes(netlist) == []


def test_an_undefined_parameter_in_the_schedule_is_reported() -> None:
    netlist = _netlist(".tran 1n 10n {SCHEDULE(0, tmax, 5n, 2n)}\n")
    assert _codes(netlist) == [(10, DiagnosticCode.UNRESOLVED_PARAM, "warning")]


def test_schedule_elsewhere_is_an_unknown_function() -> None:
    netlist = _netlist("R9 3 0 {schedule(1)}\n")
    assert _codes(netlist) == [(10, DiagnosticCode.UNRESOLVED_PARAM, "warning")]


# --- Nodes of initial conditions (decision 0028 items 2 and 6; points 5 and 25) ---


@pytest.mark.parametrize(
    "line",
    [".ic V(2)=1", ".dcvolt 2 1", ".nodeset v(2)=1", ".ic V(0)=0", ".ic V($G1)=1"],
)
def test_a_connected_node_resolves(line: str) -> None:
    netlist = _netlist(f"{line}\n")
    (reference,) = [r for r in netlist.references if r.kind == "node"]
    assert reference.target is not None
    assert _codes(netlist) == []


def test_a_global_node_resolves() -> None:
    netlist = Netlist.from_text("t\n.global vdd\nR1 vdd 0 1\n.ic V(VDD)=1\n.end\n", dialect=_XYCE)
    assert _codes(netlist) == []


def test_an_unconnected_node_is_a_warning() -> None:
    netlist = _netlist(".ic V(nope)=1\n.nodeset nope2 1\n")
    found = [(d.code, d.severity) for d in netlist.diagnostics]
    assert found[:1] == [(DiagnosticCode.UNRESOLVED_NODE, "warning")]
    assert found[1] == (DiagnosticCode.IC_WITH_NODESET, "warning")
    assert found[2] == (DiagnosticCode.UNRESOLVED_NODE, "warning")
    assert _only(netlist, DiagnosticCode.UNRESOLVED_NODE)[0] == (
        "node `nope` is not connected to anything in top level; Xyce 7.10 ignores the `.ic` "
        "condition on it, with a warning"
    )


def test_an_unconnected_node_with_an_include_is_info() -> None:
    netlist = _netlist('.include "x.lib"\n.ic V(nope)=1\n')
    (finding,) = [d for d in netlist.diagnostics if d.code is DiagnosticCode.UNRESOLVED_NODE]
    assert finding.severity == "info"
    assert "may be connected in an `.include`" in finding.message


def test_a_body_condition_resolves_in_its_definition() -> None:
    # A port and an internal node of the body; a top-level net is not visible there.
    body = ".subckt div a b\nR1 a m 1\nC1 m b 1p\n.ic V(a)=1 V(m)=0.5 V(2)=1\n.ends\n"
    netlist = _netlist(f"X1 1 0 div\n{body}")
    assert _codes(netlist) == [(14, DiagnosticCode.UNRESOLVED_NODE, "warning")]
    assert "in subcircuit `div`" in netlist.diagnostics[0].message


@pytest.mark.parametrize("node", ["X1:m", "x1:M"])
def test_a_path_to_an_internal_node_is_node_into_instance(node: str) -> None:
    netlist = _netlist(f"X1 1 0 div\n{_DIV}.ic V({node})=1\n")
    (finding,) = netlist.diagnostics
    assert (finding.code, finding.severity) == (DiagnosticCode.NODE_INTO_INSTANCE, "warning")
    assert finding.message == (
        f"node `{node}` names an instance; Xyce 7.10 applies the `.ic` condition to that node "
        "inside the instance (Xyce reference manual §2.3.1.2 p182), and the library does not "
        "resolve it"
    )


def test_a_path_into_an_included_definition_is_info_on_a_condition() -> None:
    netlist = _netlist('.include "div.lib"\nX1 1 0 div\n.nodeset X1:m 1\n')
    (finding,) = [d for d in netlist.diagnostics if d.code is DiagnosticCode.NODE_INTO_INSTANCE]
    assert finding.severity == "info"


@pytest.mark.parametrize("node", ["X1:a", "X1:zz", "X7:m"])
def test_a_path_that_reaches_no_internal_node_is_unresolved(node: str) -> None:
    # A port, a missing node or a missing instance: a net of its own, which nothing connects.
    netlist = _netlist(f"X1 1 0 div\n{_DIV}.ic V({node})=1\n")
    assert _codes(netlist) == [(15, DiagnosticCode.UNRESOLVED_NODE, "warning")]


def test_a_path_an_element_line_connects_is_a_net_of_its_own() -> None:
    netlist = _netlist(f"X1 1 0 div\n{_DIV}R9 X1:a 0 1\n.ic V(X1:a)=1\n")
    assert _codes(netlist) == []


@pytest.mark.parametrize(
    ("node", "netlist_head"),
    [("$Gn", ""), ("VDD", ".global vdd\n")],
)
def test_a_global_node_in_a_body_condition_is_ignored(node: str, netlist_head: str) -> None:
    body = f".subckt s p\nC1 {node} 0 1p\nR1 {node} p 1k\n.ic V({node})=1\n.ends\n"
    netlist = Netlist.from_text(
        f"t\n{netlist_head}X1 a s\nR9 a 0 1\n{body}.tran 1n 2n\n.end\n", dialect=_XYCE
    )
    (finding,) = netlist.diagnostics
    assert (finding.code, finding.severity) == (DiagnosticCode.CONDITION_IGNORED, "warning")
    assert finding.message == (
        f"node `{node}` is global, and Xyce 7.10 ignores a `.ic` condition on a global node in a "
        "subcircuit body (subcircuit `s`), with a warning; move the condition to the top level"
    )


def test_ground_in_a_body_condition_is_not_reported() -> None:
    body = ".subckt s p\nC1 p 0 1p\n.ic V(0)=0\n.ends\n"
    assert _codes(Netlist.from_text(f"t\nX1 a s\nR9 a 0 1\n{body}.end\n", dialect=_XYCE)) == []


def test_the_other_dialects_make_no_condition_node_references() -> None:
    for dialect in (Dialect.NGSPICE, Dialect.LTSPICE):
        netlist = Netlist.from_text("t\nR1 1 0 1\n.ic v(nope)=1\n.end\n", dialect=dialect)
        assert netlist.references == ()
        assert netlist.diagnostics == ()


@pytest.mark.parametrize("dialect", [Dialect.NGSPICE, Dialect.LTSPICE])
@pytest.mark.parametrize("line", [".ic v(1)={v(1)}", ".nodeset v(1)={v(1)*2}"])
def test_a_node_read_in_a_condition_value_loads_on_the_other_dialects(
    dialect: Dialect, line: str
) -> None:
    # R1 review B1: a node that an expression in the value reads is an expression node, not a
    # condition node, so the condition checks never see it on ngspice and LTspice.
    netlist = Netlist.from_text(
        f"t\nV1 1 0 1\nR1 1 0 1k\n{line}\n.tran 1n 10n\n.end\n", dialect=dialect
    )
    (reference,) = netlist.references
    assert (reference.kind, reference.name) == ("node", "1")
    assert reference.target is not None
    assert netlist.diagnostics == ()


@pytest.mark.parametrize("dialect", [Dialect.NGSPICE, Dialect.LTSPICE])
def test_an_unconnected_node_read_in_a_condition_value_is_an_expression_node(
    dialect: Dialect,
) -> None:
    netlist = Netlist.from_text(
        "t\nV1 1 0 1\nR1 1 0 1k\n.ic v(1)={v(99)}\n.tran 1n 10n\n.end\n", dialect=dialect
    )
    assert [d.message for d in netlist.diagnostics] == [
        "node `99` is not defined (searched: top level)"
    ]


def test_a_node_read_in_a_condition_value_is_an_expression_node_on_xyce() -> None:
    netlist = _netlist(".ic V(2)={V(99)}\n")
    (finding,) = netlist.diagnostics
    assert (finding.code, finding.severity) == (DiagnosticCode.UNRESOLVED_NODE, "warning")
    assert finding.message == "node `99` is not defined (searched: top level)"


def test_a_path_read_in_a_condition_value_is_an_expression_path_on_xyce() -> None:
    netlist = _netlist(f"X1 1 0 div\n{_DIV}.ic V(2)={{V(X1:m)}}\n")
    (finding,) = netlist.diagnostics
    assert (finding.code, finding.severity) == (DiagnosticCode.UNRESOLVED_NODE, "info")
    assert finding.message == (
        "node `X1:m` is not defined (searched: top level); it names a node inside instance "
        "`X1`, which Xyce 7.10 reads and the library does not resolve"
    )


# --- ANALYSIS_IGNORED (point 15) ---


def test_only_the_last_analysis_runs() -> None:
    netlist = _netlist(".tran 1n 2n\n.ac dec 1 1 10\n.op\n.tran 1n 3n\n")
    assert _codes(netlist) == [
        (10, DiagnosticCode.ANALYSIS_IGNORED, "warning"),
        (11, DiagnosticCode.ANALYSIS_IGNORED, "warning"),
        (12, DiagnosticCode.ANALYSIS_IGNORED, "warning"),
    ]
    messages = _only(netlist, DiagnosticCode.ANALYSIS_IGNORED)
    assert messages[0] == (
        "Xyce 7.10 runs only the last analysis line, `.tran` on line 13, and ignores this `.tran`"
    )
    assert messages[1].endswith("and ignores this `.ac`")
    assert messages[2] == (
        "Xyce 7.10 ignores `.op` when the netlist has another analysis, and runs `.tran` (line 13)"
    )


def test_every_dc_line_joins_the_first() -> None:
    netlist = _netlist(".DC V1 0 1 0.5\n.tran 1n 2n\n.dc R2 1k 2k 1k\n")
    assert _codes(netlist) == [
        (11, DiagnosticCode.ANALYSIS_IGNORED, "warning"),
        (12, DiagnosticCode.ANALYSIS_IGNORED, "warning"),
    ]
    assert _only(netlist, DiagnosticCode.ANALYSIS_IGNORED)[1] == (
        "this `.dc` line joins the `.DC` on line 10 into one nested sweep: Xyce 7.10 runs every "
        "`.DC` line as one analysis, the sweeps of the earlier lines innermost"
    )


def test_dc_lines_before_another_analysis_are_ignored() -> None:
    netlist = _netlist(".dc V1 0 1 0.5\n.dc R2 1k 2k 1k\n.ac dec 1 1 10\n")
    messages = _only(netlist, DiagnosticCode.ANALYSIS_IGNORED)
    assert [m.endswith("ignores this `.dc`") for m in messages] == [True, True]


def test_noise_takes_part_in_the_last_line_rule() -> None:
    netlist = _netlist(".tran 1n 2n\n.noise v(2) V1 dec 1 1 10\n")
    assert _codes(netlist) == [
        (10, DiagnosticCode.ANALYSIS_IGNORED, "warning"),
        (11, DiagnosticCode.UNTYPED_DIRECTIVE_PRESERVED, "info"),
    ]


@pytest.mark.parametrize(
    ("body", "ignored", "runs"),
    [
        (".tran 1n 2n\n.hb 1k\n", ".tran", ".hb"),
        (".hb 1k\n.tran 1n 2n\n", ".hb", ".tran"),
        (".ac dec 1 1 10\n.hb 1k\n", ".ac", ".hb"),
        (".hb 1k\n.ac dec 1 1 10\n", ".hb", ".ac"),
        (".dc V1 0 1 1\n.hb 1k\n", ".dc", ".hb"),
        (".hb 1k\n.dc V1 0 1 1\n", ".hb", ".dc"),
        (".noise v(2) V1 dec 1 1 10\n.hb 1k\n", ".noise", ".hb"),
        (".hb 1k\n.noise v(2) V1 dec 1 1 10\n", ".hb", ".noise"),
        (".HB 1k\n.hb 2k\n", ".HB", ".hb"),
    ],
)
def test_hb_takes_part_in_the_last_line_rule(body: str, ignored: str, runs: str) -> None:
    """`.HB`, an untyped line, overrides the others and gives way to them (the X-M2.1 probes)."""
    netlist = _netlist(body)
    (finding,) = [d for d in netlist.diagnostics if d.code is DiagnosticCode.ANALYSIS_IGNORED]
    assert (finding.line, finding.severity) == (10, "warning")
    assert finding.message == (
        f"Xyce 7.10 runs only the last analysis line, `{runs}` on line 11, and ignores this "
        f"`{ignored}`"
    )
    assert netlist.slice(finding.span) == ignored


@pytest.mark.parametrize(
    ("body", "op", "hb"), [(".op\n.hb 1k\n", 10, 11), (".hb 1k\n.op\n", 11, 10)]
)
def test_op_gives_way_to_hb(body: str, op: int, hb: int) -> None:
    netlist = _netlist(body)
    (finding,) = [d for d in netlist.diagnostics if d.code is DiagnosticCode.ANALYSIS_IGNORED]
    assert finding.line == op
    assert finding.message == (
        f"Xyce 7.10 ignores `.op` when the netlist has another analysis, and runs `.hb` (line {hb})"
    )


def test_dc_lines_around_hb_join() -> None:
    netlist = _netlist(".dc V1 0 1 1\n.hb 1k\n.dc R2 1k 2k 1k\n")
    messages = _only(netlist, DiagnosticCode.ANALYSIS_IGNORED)
    assert len(messages) == 2
    assert messages[0].endswith("and ignores this `.hb`")
    assert messages[1].startswith("this `.dc` line joins the `.DC` on line 10")


def _elsewhere(text: str, dialect: Dialect) -> set[DiagnosticCode]:
    """The codes of ``text`` on ngspice, which keeps `.hb` and `.print` untyped; LTspice refuses
    both, as before X-M2.1, so its set is empty once the refusal is checked."""
    if dialect is Dialect.LTSPICE:
        with pytest.raises(ParseError, match="is not an LTspice dot-command"):
            Netlist.from_text(text, dialect=dialect)
        return set()
    return {d.code for d in Netlist.from_text(text, dialect=dialect).diagnostics}


@pytest.mark.parametrize("dialect", [Dialect.NGSPICE, Dialect.LTSPICE])
def test_the_other_dialects_have_no_last_line_rule_for_hb(dialect: Dialect) -> None:
    text = "t\nV1 1 0 1\nR1 1 0 1k\n.tran 1n 2n\n.hb 1k\n.end\n"
    assert DiagnosticCode.ANALYSIS_IGNORED not in _elsewhere(text, dialect)


def test_one_analysis_and_repeated_op_are_not_reported() -> None:
    assert _codes(_netlist(".op\n.op\n")) == []
    assert _codes(_netlist(".dc V1 0 1 0.5\n")) == []


# --- .STEP (points 10 and 16) ---


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("R2", "R2:R"),
        ("r2:r", "R2"),
        ("V1", "V1:DCV0"),
        ("I1", "i1:dcv0"),
        ("C1", "C1:C"),
        ("L1", "L1:L"),
        ("p", "P"),
        ("dm:IS", "DM:is"),
        ("TEMP", "temp"),
        ("D1:AREA", "d1:area"),
    ],
)
def test_a_repeated_quantity_is_a_warning(first: str, second: str) -> None:
    netlist = _netlist(
        f".param p=1\n.step {first} LIST 1 2\n.step {second} LIST 1 2\n.tran 1n 2n\n"
    )
    (finding,) = netlist.diagnostics
    assert (finding.code, finding.severity, finding.line) == (
        DiagnosticCode.DUPLICATE_DEFINITION,
        "warning",
        12,
    )
    assert finding.message == (
        f"`.step` sweeps `{second}` again; line 11 sweeps it already; Xyce 7.10 nests the two "
        "sweeps of one quantity, silently"
    )


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("D1", "D1:AREA"),  # D has no primary parameter in the key
        ("R2", "R3"),
        ("R2:R", "R2:TC1"),
        ("q", "q:R"),  # no device `q`: not folded
    ],
)
def test_different_quantities_are_not_repeats(first: str, second: str) -> None:
    netlist = _netlist(f".step {first} LIST 1 2\n.step {second} LIST 1 2\n.tran 1n 2n\n")
    assert DiagnosticCode.DUPLICATE_DEFINITION not in {d.code for d in netlist.diagnostics}


def test_a_parameter_named_as_a_device_is_not_folded() -> None:
    # Xyce looks the name up as a parameter first, so `R2` is the parameter, not `R2:R`.
    netlist = _netlist(".param R2=1\n.step R2 LIST 1 2\n.step R2:R LIST 1 2\n.tran 1n 2n\n")
    assert _codes(netlist) == []


def test_the_quantity_key() -> None:
    netlist = _netlist(".param p=1\n")
    root = netlist.scope()

    def key(target: str) -> tuple[str, ...]:
        step = (
            Netlist.from_text(f"t\n{_CIRCUIT}.param p=1\n.step {target}\n.end\n", dialect=_XYCE)
            .lines[-2]
            .item
        )
        assert isinstance(step, StepDirective)
        return step_quantity(root, step)

    assert key("R2 1 2 1") == key("R2:R LIST 1 2") == ("target", "r2", "r")
    assert key("V1 1 2 1") == ("target", "v1", "dcv0")
    assert key("p 1 2 1") == ("target", "p")
    assert key("TEMP 1 2 1") == ("temp",)
    assert key("DATA=Tab") == ("data", "tab")


def test_a_data_step_drops_the_others() -> None:
    netlist = _netlist(f"{_TABLE}.step R2 1k 2k 1k\n.step data=tab\n.step V1 1 2 1\n.tran 1n 2n\n")
    assert _codes(netlist) == [
        (14, DiagnosticCode.STEP_IGNORED, "warning"),
        (16, DiagnosticCode.STEP_IGNORED, "warning"),
    ]
    assert _only(netlist, DiagnosticCode.STEP_IGNORED)[0] == (
        "Xyce 7.10 drops this `.step` line: a `.STEP DATA=` line (line 15) makes it ignore every "
        "other `.STEP` line"
    )


def test_several_steps_with_op_are_a_warning() -> None:
    netlist = _netlist(".step R2 1k 2k 1k\n.step R3 1k 2k 1k\n.OP\n")
    assert _codes(netlist) == [(12, DiagnosticCode.STEPS_WITH_OP, "warning")]
    assert netlist.diagnostics[0].message == (
        "Xyce 7.10 aborts on an `.OP` analysis with 2 `.STEP` lines; one `.STEP` line, or "
        "another analysis, runs"
    )


@pytest.mark.parametrize(
    "body",
    [
        ".step R2 1k 2k 1k\n.op\n",  # one step
        ".step R2 1k 2k 1k\n.step R3 1k 2k 1k\n.op\n.tran 1n 2n\n",  # .OP gives way
        ".step R2 1k 2k 1k\n.step R3 1k 2k 1k\n.hb 1k\n.op\n",  # to `.HB` too
    ],
)
def test_steps_with_op_that_runs_are_not_reported(body: str) -> None:
    netlist = _netlist(body)
    assert DiagnosticCode.STEPS_WITH_OP not in {d.code for d in netlist.diagnostics}


@pytest.mark.parametrize(
    ("analysis", "outcome"),
    [
        (".tran {tstep} 10n", "reads this `.tran` field once, so the sweep does not change it"),
        (
            ".ac dec {tstep} 1 10",
            "stops on this `.ac` field: it cannot evaluate a stepped parameter there",
        ),
        (
            ".dc V1 0 {tstep} 0.5",
            "stops on this `.dc` field: it cannot evaluate a stepped parameter there",
        ),
        (
            ".tran 1n 10n {schedule(0, tstep, 5n, 2n)}",
            "reads this `.tran` field once, so the sweep does not change it",
        ),
    ],
)
def test_a_stepped_parameter_in_an_analysis_field_is_a_warning(analysis: str, outcome: str) -> None:
    # R1 review S1: Xyce reads a `.TRAN` field once and stops on an `.AC` or `.DC` one.
    netlist = _netlist(f".param tstep=1n\n.step tstep 1n 2n 1n\n{analysis}\n")
    (finding,) = [d for d in netlist.diagnostics if d.code is DiagnosticCode.STEPPED_ANALYSIS_FIELD]
    assert finding.severity == "warning"
    assert finding.message == (
        f"parameter `tstep` is swept by the `.STEP` on line 11, but Xyce 7.10 {outcome}"
    )
    assert netlist.slice(finding.span) == "tstep"


def test_an_unstepped_parameter_in_an_analysis_field_is_not_reported() -> None:
    netlist = _netlist(".param tstep=1n\n.param q=1\n.step q 1 2 1\n.tran {tstep} 10n\n")
    assert _codes(netlist) == []


def test_a_dc_sweep_of_a_parameter_is_not_a_stepped_field() -> None:
    netlist = _netlist(".param p=1\n.step p 1 2 1\n.dc p 0 1 0.5\n")
    assert DiagnosticCode.STEPPED_ANALYSIS_FIELD not in {d.code for d in netlist.diagnostics}


# --- Repeated options, conditions and measurements (points 21, 24 and 26) ---


def test_a_repeated_option_uses_the_first_value() -> None:
    netlist = _netlist(
        ".options timeint reltol=1e-3 method=gear\n.OPTIONS TIMEINT RELTOL=1e-4\n"
        ".options device temp=27\n.option scale=1\n.option scale=2\n.tran 1n 2n\n"
    )
    assert _codes(netlist) == [
        (11, DiagnosticCode.DUPLICATE_DEFINITION, "warning"),
        (14, DiagnosticCode.DUPLICATE_DEFINITION, "warning"),
    ]
    assert _only(netlist, DiagnosticCode.DUPLICATE_DEFINITION) == [
        "option `RELTOL` of package `TIMEINT` is set again; Xyce 7.10 uses the first value, "
        "with a warning",
        "option `scale` is set again; Xyce 7.10 uses the first value, with a warning",
    ]


def test_an_item_of_another_package_or_output_is_not_a_repeat() -> None:
    netlist = _netlist(
        ".options timeint reltol=1e-3\n.options nonlin reltol=1e-3\n"
        ".options output initial_interval=1n\n.options output initial_interval=2n\n.tran 1n 2n\n"
    )
    assert _codes(netlist) == []


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        (
            ".option scale=1\n.options parser scale=2\n",
            "option `scale` of package `parser` is set again; Xyce 7.10 uses the first value, "
            "with a warning",
        ),
        (
            ".options parser scale=2\n.option scale=1\n",
            "option `scale` is set again; Xyce 7.10 uses the first value, with a warning",
        ),
    ],
)
def test_option_scale_is_parsers_scale(lines: str, message: str) -> None:
    # R1 review gap 2: Xyce reads the package-less `.OPTION SCALE=` as PARSER's SCALE.
    netlist = _netlist(f"{lines}.tran 1n 2n\n")
    assert _only(netlist, DiagnosticCode.DUPLICATE_DEFINITION) == [message]


def test_a_repeated_condition_uses_the_last_value() -> None:
    netlist = _netlist(".ic V(2)=1 V(3)=0\n.DCVOLT 2 0.5\n.ic v(3)=1\n")
    assert _codes(netlist) == [
        (11, DiagnosticCode.DUPLICATE_DEFINITION, "warning"),
        (12, DiagnosticCode.DUPLICATE_DEFINITION, "warning"),
    ]
    assert _only(netlist, DiagnosticCode.DUPLICATE_DEFINITION)[0] == (
        "node `2` is given an initial condition (`.IC` or `.DCVOLT`) again in top level; "
        "Xyce 7.10 uses the last value"
    )


def test_a_repeated_nodeset_value_uses_the_last() -> None:
    netlist = _netlist(".nodeset V(2)=1 V(2)=0.5\n")
    assert _only(netlist, DiagnosticCode.DUPLICATE_DEFINITION) == [
        "node `2` is given a `.NODESET` value again in top level; Xyce 7.10 uses the last value"
    ]


def test_conditions_repeat_per_scope() -> None:
    body = ".subckt div a b\nR1 a m 1\nC1 m b 1p\n.ic V(m)=1\n.ends\n"
    netlist = _netlist(f"X1 1 2 div\n{body}.ic V(2)=1\n")
    assert _codes(netlist) == []


def test_a_repeated_measurement_uses_the_last() -> None:
    netlist = _netlist(".tran 1n 2n\n.meas tran m1 max v(2)\n.MEAS TRAN M1 min v(2)\n")
    assert _codes(netlist) == [(12, DiagnosticCode.DUPLICATE_DEFINITION, "warning")]
    assert netlist.diagnostics[0].message == (
        "measurement `M1` is defined again; Xyce 7.10 uses the last definition, with a warning"
    )


# --- IC_WITH_NODESET (point 24) ---


def test_ic_with_nodeset_is_a_warning() -> None:
    body = ".subckt div a b\nR1 a m 1\nC1 m b 1p\n.nodeset V(m)=1\n.ends\n"
    netlist = _netlist(f".DCVOLT V(2)=1\nX1 1 2 div\n{body}")
    assert _codes(netlist) == [(15, DiagnosticCode.IC_WITH_NODESET, "warning")]
    assert netlist.diagnostics[0].message == (
        "the netlist has `.DCVOLT` (line 10) and `.nodeset`; Xyce 7.10 aborts when both stand in "
        "one netlist"
    )


def test_ic_or_nodeset_alone_is_not_reported() -> None:
    assert _codes(_netlist(".ic V(2)=1\n.ic V(3)=1\n")) == []
    assert _codes(_netlist(".nodeset V(2)=1\n")) == []


# --- MEASURE_MODE_MISMATCH (point 26) ---


@pytest.mark.parametrize(
    ("analyses", "mode"),
    [
        (".tran 1n 2n", "tran"),
        (".tran 1n 2n", "TRAN_CONT"),
        (".ac dec 1 1 10", "ac"),
        (".ac dec 1 1 10", "ac_cont"),
        (".dc V1 0 1 1", "dc"),
        (".dc V1 0 1 1", "dc_cont"),
        (".op", "dc"),  # not a mismatch for Xyce's stop; reported below
        (".noise v(2) V1 dec 1 1 10", "noise"),
        (".noise v(2) V1 dec 1 1 10", "noise_cont"),
        (".tran 1n 2n\n.fft v(2)", "fft"),
        (".ac dec 1 1 10\n.tran 1n 2n\n.fft v(2)", "fft"),  # `.TRAN` runs (X-M2.1 R1)
        (".hb 1k\n.tran 1n 2n\n.fft v(2)", "fft"),
        (".op\n.tran 1n 2n\n.fft v(2)", "FFT"),
        (".hb 1k\n.tran 1n 2n", "tran"),  # the last line runs, `.HB` taking part
        (".hb 1k\n.ac dec 1 1 10", "ac_cont"),
        (".hb 1k\n.dc V1 0 1 1", "dc"),
        (".hb 1k\n.noise v(2) V1 dec 1 1 10", "noise"),
    ],
)
def test_a_mode_with_its_analysis_is_not_reported(analyses: str, mode: str) -> None:
    netlist = _netlist(f"{analyses}\n.meas {mode} m1 max v(2)\n")
    codes = {d.code for d in netlist.diagnostics}
    if analyses == ".op":
        assert _only(netlist, DiagnosticCode.MEASURE_MODE_MISMATCH) == [
            "`dc` needs a `.DC` analysis, but Xyce 7.10 runs `.op` (line 10); it reports the "
            "measurement as FAILED"
        ]
    else:
        assert DiagnosticCode.MEASURE_MODE_MISMATCH not in codes


@pytest.mark.parametrize(
    ("analyses", "mode", "ran"),
    [
        (".ac dec 1 1 10", "tran", "Xyce 7.10 runs `.ac` (line 10)"),
        (".tran 1n 2n\n.ac dec 1 1 10", "tran", "Xyce 7.10 runs `.ac` (line 11)"),
        (".op", "ac", "Xyce 7.10 runs `.op` (line 10)"),
        (".tran 1n 2n", "dc_cont", "Xyce 7.10 runs `.tran` (line 10)"),
        (".noise v(2) V1 dec 1 1 10\n.tran 1n 2n", "noise", "Xyce 7.10 runs `.tran` (line 11)"),
        ("", "tran", "the netlist has no analysis"),
        # No mode is `.HB`'s (the X-M2.1 probes): every one stops Xyce when `.HB` runs.
        (".hb 1k", "tran", "Xyce 7.10 runs `.hb` (line 10)"),
        (".hb 1k", "ac", "Xyce 7.10 runs `.hb` (line 10)"),
        (".hb 1k", "noise", "Xyce 7.10 runs `.hb` (line 10)"),
        (".hb 1k\n.op", "dc", "Xyce 7.10 runs `.hb` (line 10)"),  # stops, not FAILED
        (".op\n.HB 1k", "dc_cont", "Xyce 7.10 runs `.HB` (line 11)"),
        (".tran 1n 2n\n.hb 1k", "tran", "Xyce 7.10 runs `.hb` (line 11)"),
        (".ac dec 1 1 10\n.hb 1k", "ac", "Xyce 7.10 runs `.hb` (line 11)"),
        (".dc V1 0 1 1\n.hb 1k", "dc", "Xyce 7.10 runs `.hb` (line 11)"),
    ],
)
def test_a_mode_whose_analysis_does_not_run_is_a_warning(
    analyses: str, mode: str, ran: str
) -> None:
    head = f"{analyses}\n" if analyses else ""
    netlist = _netlist(f"{head}.meas {mode} m1 max v(2)\n")
    (finding,) = [d for d in netlist.diagnostics if d.code is DiagnosticCode.MEASURE_MODE_MISMATCH]
    needed = mode.upper().removesuffix("_CONT")
    assert finding.severity == "warning"
    assert finding.message == (
        f"`{mode}` needs a `.{needed}` analysis, but {ran}; it stops: the analysis and the "
        "measure mode do not agree"
    )
    assert netlist.slice(finding.span) == mode


@pytest.mark.parametrize(
    ("analyses", "ran"),
    [
        # FFT needs a `.TRAN` that runs, a `.FFT` line or not (the X-M2.1 R1 probes).
        (".hb 1k\n.fft v(2)", "Xyce 7.10 runs `.hb` (line 10)"),
        (".hb 1k", "Xyce 7.10 runs `.hb` (line 10)"),
        (".ac dec 1 1 10\n.fft v(2)", "Xyce 7.10 runs `.ac` (line 10)"),
        (".ac dec 1 1 10", "Xyce 7.10 runs `.ac` (line 10)"),
        (".op\n.fft v(2)", "Xyce 7.10 runs `.op` (line 10)"),
        (".dc V1 0 1 1\n.fft v(2)", "Xyce 7.10 runs `.dc` (line 10)"),
        (".noise v(2) V1 dec 1 1 10\n.fft v(2)", "Xyce 7.10 runs `.noise` (line 10)"),
        (".tran 1n 2n\n.ac dec 1 1 10\n.fft v(2)", "Xyce 7.10 runs `.ac` (line 11)"),
        (".tran 1n 2n\n.hb 1k\n.fft v(2)", "Xyce 7.10 runs `.hb` (line 11)"),
        (".fft v(2)", "the netlist has no analysis"),
    ],
)
def test_fft_without_a_tran_that_runs_is_a_warning(analyses: str, ran: str) -> None:
    netlist = _netlist(f"{analyses}\n.meas fft m1 find vm(2) at=1k\n")
    assert _only(netlist, DiagnosticCode.MEASURE_MODE_MISMATCH) == [
        f"`fft` needs a `.TRAN` analysis, but {ran}; it stops: the analysis and the measure mode "
        "do not agree"
    ]


def test_fft_without_an_fft_line_is_a_warning() -> None:
    netlist = _netlist(".tran 1n 2n\n.meas FFT m1 enob v(2)\n")
    (finding,) = netlist.diagnostics
    assert (finding.code, finding.severity) == (DiagnosticCode.MEASURE_MODE_MISMATCH, "warning")
    assert finding.message == (
        '`FFT` measures a `.FFT` line, and the netlist has none; Xyce 7.10 stops ("No .FFT '
        'statement in netlist")'
    )


# --- PRINT_TYPE_MISMATCH (X-M2.1 C3; decision 0029 item 5) ---

_TRAN, _AC, _DC = ".tran 1n 2n", ".ac dec 1 1 10", ".dc V1 0 1 1"
_NOISE, _HB = ".noise v(2) V1 dec 1 1 10", ".hb 1k"


@pytest.mark.parametrize(
    ("analyses", "kind"),
    [
        (_TRAN, "tran"),
        (_AC, "AC"),
        (f"{_AC}\n.op", "ac_ic"),
        (_DC, "dc"),
        (".op", "DC"),
        (_NOISE, "noise"),
        (_HB, "hb"),
        (_HB, "HB_FD"),
        (_HB, "hb_td"),
        (".op", "hb_startup"),
        (".op", "tran"),  # agrees with `.OP`; writes nothing, reported below
        (_TRAN, "sens"),
        (_HB, "homotopy"),
        (_TRAN, "tranadjoint"),
        (_DC, "es"),
        (_TRAN, "pce"),
        (f".op\n{_TRAN}", "tran"),
        (f"{_AC}\n{_TRAN}", "ac"),  # agrees with the first line; writes nothing, reported below
        ("", "ac"),
    ],
)
def test_a_type_that_agrees_with_the_first_analysis_does_not_stop(analyses: str, kind: str) -> None:
    head = f"{analyses}\n" if analyses else ""
    messages = _only(_netlist(f"{head}.print {kind} v(2)\n"), DiagnosticCode.PRINT_TYPE_MISMATCH)
    assert not any("stops" in message for message in messages)


@pytest.mark.parametrize(
    ("analyses", "kind", "first", "which"),
    [
        (_TRAN, "ac", ".tran (line 10)", "the first analysis but `.OP`"),
        (f"{_TRAN}\n{_AC}", "AC", ".tran (line 10)", "the first analysis but `.OP`"),
        (f".op\n{_TRAN}", "dc", ".tran (line 11)", "the first analysis but `.OP`"),
        (f"{_TRAN}\n.op", "dc", ".tran (line 10)", "the first analysis but `.OP`"),
        (_AC, "tran", ".ac (line 10)", "the first analysis but `.OP`"),
        (_DC, "noise", ".dc (line 10)", "the first analysis but `.OP`"),
        (_NOISE, "homotopy", ".noise (line 10)", "the first analysis but `.OP`"),
        (_HB, "sens", ".hb (line 10)", "the first analysis but `.OP`"),
        (f"{_HB}\n{_TRAN}", "tran", ".hb (line 10)", "the first analysis but `.OP`"),
        (_AC, "es", ".ac (line 10)", "the first analysis but `.OP`"),
        (_DC, "tranadjoint", ".dc (line 10)", "the first analysis but `.OP`"),
        (".op", "TranAdjoint", ".op (line 10)", "the only analysis"),
    ],
)
def test_a_type_that_disagrees_with_the_first_analysis_is_a_warning(
    analyses: str, kind: str, first: str, which: str
) -> None:
    netlist = _netlist(f"{analyses}\n.print {kind} v(2)\n")
    (finding,) = [d for d in netlist.diagnostics if d.code is DiagnosticCode.PRINT_TYPE_MISMATCH]
    keyword, line = first.split(" ", 1)
    analysis = keyword.lstrip(".").upper()
    assert finding.severity == "warning"
    assert finding.message == (
        f"print type `{kind}` does not agree with `{keyword}` {line}, {which}: Xyce 7.10 checks "
        f'every `.PRINT` type against that line, and stops ("Analysis type {analysis} and print '
        f'type {kind.upper()} are inconsistent")'
    )
    assert netlist.slice(finding.span) == kind


@pytest.mark.parametrize(
    ("analyses", "kind", "names", "runs"),
    [
        (f"{_TRAN}\n{_AC}", "tran", "a `.TRAN` analysis", ".ac` (line 11)"),
        (f"{_AC}\n{_TRAN}", "ac", "an `.AC` analysis", ".tran` (line 11)"),
        (f"{_AC}\n{_NOISE}", "ac", "an `.AC` analysis", ".noise` (line 11)"),
        (f"{_DC}\n{_TRAN}", "dc", "a `.DC` or `.OP` analysis", ".tran` (line 11)"),
        (f"{_NOISE}\n{_TRAN}", "noise", "a `.NOISE` analysis", ".tran` (line 11)"),
        (f"{_HB}\n{_TRAN}", "hb", "an `.HB` analysis", ".tran` (line 11)"),
        (f"{_TRAN}\n{_HB}", "tran", "a `.TRAN` analysis", ".hb` (line 11)"),
        (".op", "tran", "a `.TRAN` analysis", ".op` (line 10)"),
        (".op", "ac_ic", "an `.AC` analysis", ".op` (line 10)"),
        (".op", "noise", "a `.NOISE` analysis", ".op` (line 10)"),
        (".op", "hb_fd", "an `.HB` analysis", ".op` (line 10)"),
    ],
)
def test_a_type_whose_analysis_does_not_run_is_a_warning(
    analyses: str, kind: str, names: str, runs: str
) -> None:
    netlist = _netlist(f"{analyses}\n.print {kind} v(2)\n")
    (finding,) = [d for d in netlist.diagnostics if d.code is DiagnosticCode.PRINT_TYPE_MISMATCH]
    assert finding.severity == "warning"
    assert finding.message == (
        f"print type `{kind}` writes the results of {names}, but Xyce 7.10 runs `{runs}, and "
        "writes nothing for this line"
    )


def test_a_dc_type_under_op_and_the_other_commands_types_are_not_reported_when_they_run() -> None:
    body = ".op\n.print dc v(2)\n.print sens v(2)\n.print es v(2)\n.print homotopy v(2)\n"
    assert _only(_netlist(body), DiagnosticCode.PRINT_TYPE_MISMATCH) == []


def test_each_print_line_is_checked() -> None:
    netlist = _netlist(f"{_AC}\n{_TRAN}\n.print ac v(2)\n.print tran v(2)\n.print dc v(2)\n")
    found = [
        (d.line, "stops" in d.message)
        for d in netlist.diagnostics
        if d.code is DiagnosticCode.PRINT_TYPE_MISMATCH
    ]
    assert found == [(12, False), (13, True), (14, True)]


def test_every_print_type_has_a_rule() -> None:
    from netlistmod.document.diagnostics import _PRINT_RULES
    from tests.grammar.xyce.test_xyce_print import PRINT_TYPES

    rules = _PRINT_RULES[_XYCE]
    assert rules is not None
    assert sorted(rules) == sorted(kind.lower() for kind in PRINT_TYPES)
    assert _PRINT_RULES[Dialect.NGSPICE] is None and _PRINT_RULES[Dialect.LTSPICE] is None


@pytest.mark.parametrize("dialect", [Dialect.NGSPICE, Dialect.LTSPICE])
def test_the_other_dialects_do_not_check_a_print_type(dialect: Dialect) -> None:
    text = "t\nV1 1 0 1\nR1 1 0 1k\n.tran 1n 2n\n.print ac v(1)\n.end\n"
    assert DiagnosticCode.PRINT_TYPE_MISMATCH not in _elsewhere(text, dialect)


# --- The other dialects keep their findings (decision 0026 item 6) ---


def test_ngspice_and_ltspice_directives_are_not_checked_the_xyce_way() -> None:
    text = "t\nV1 1 0 1\nR1 1 0 1k\n.tran 1n 2n\n.ac dec 1 1 10\n.op\n.meas tran m1 max v(1)\n"
    text += ".options reltol=1e-3\n.options reltol=1e-4\n.ic v(1)=1\n.nodeset v(1)=1\n.end\n"
    for dialect in (Dialect.NGSPICE, Dialect.LTSPICE):
        assert Netlist.from_text(text, dialect=dialect).diagnostics == ()


def test_ltspice_keeps_its_step_repeat_message() -> None:
    netlist = Netlist.from_text(
        "t\nV1 1 0 1\nR1 1 0 1k\n.step V1 1 2 1\n.step V1 1 3 1\n.tran 1n\n.end\n",
        dialect=Dialect.LTSPICE,
    )
    (finding,) = netlist.diagnostics
    assert finding.message == "`.step` sweeps `V1` again; LTspice 26.1.1 stops with an error"
