"""The document layer on xyce element lines (X-M1 B6): nets into an instance (decision X-D2,
decision 0027 item 4), K's CORE model, function calls, and the R, C and L words that Xyce sorts
by lookup (xm1-tasks 5.1 point 9)."""

from __future__ import annotations

import pytest

from netlistmod import DiagnosticCode, Dialect, Netlist
from netlistmod.dialects import _XYCE

_DIV = ".subckt div a b\nR1 a m 1\nR2 m b 1\n.ends\n"


def _netlist(body: str) -> Netlist:
    return Netlist.from_text(f"t\n{body}.end\n", dialect=_XYCE)


def _codes(netlist: Netlist) -> list[tuple[int, DiagnosticCode, str]]:
    return [(d.line, d.code, d.severity) for d in netlist.diagnostics]


def test_a_netlist_with_elements_builds_its_topology() -> None:
    netlist = _netlist(
        "V1 1 0 1\nR1 1 2 rmod 1k\nC1 2 0 1p\nL1 2 3 1u\nL2 3 0 1u\nK1 L1 L2 0.5\n"
        "D1 3 0 dm\nX1 1 0 div\n.model rmod R\n.model dm D\n" + _DIV
    )
    assert netlist.diagnostics == ()
    assert {net.name for net in netlist.nets()} >= {"0", "1", "2", "3"}
    assert [c.designator for c in netlist.elements_on_net("2")] == ["R1", "C1", "L1"]
    assert (
        netlist.signature()
        == _netlist(
            "V1 1 0 2\nR1 1 2 rmod 2k\nC1 2 0 1p\nL1 2 3 1u\nL2 3 0 1u\nK1 L1 L2 0.9\n"
            "D1 3 0 dm\nX1 1 0 div\n.model rmod R\n.model dm D\n" + _DIV
        ).signature()
    )


@pytest.mark.parametrize("node", ["X1:m", "x1:M"])
def test_a_path_to_an_internal_node_is_reported(node: str) -> None:
    # [xyce-ref] §2.3.1.2 p182: Xyce joins it to the instance's node (xd1, xd1c probes).
    netlist = _netlist(f"V1 1 0 1\nX1 1 0 div\n{_DIV}R3 {node} 0 1\n")
    (finding,) = netlist.diagnostics
    assert (finding.code, finding.severity, finding.line) == (
        DiagnosticCode.NODE_INTO_INSTANCE,
        "warning",
        8,
    )
    assert "connects it to that node inside the instance" in finding.message
    assert "§2.3.1.2" in finding.message
    # The library keeps the path as a net of its own (§7.8).
    assert {net.name for net in netlist.nets()} >= {"x1:m"}


def test_a_path_written_before_the_instance_is_reported() -> None:
    netlist = _netlist(f"V1 1 0 1\nR3 X1:m 0 1\nX1 1 0 div\n{_DIV}")
    assert _codes(netlist) == [(3, DiagnosticCode.NODE_INTO_INSTANCE, "warning")]


@pytest.mark.parametrize(
    "node",
    [
        "X1:a",  # a port: Xyce keeps a net of its own (xd2)
        "X1:zz",  # no such node (xd3)
        "X7:m",  # no such instance (xd3b)
        "X1:0",
        "X1:$Gvdd",
        "X1:vdd",  # a `.global` node
        "R1:m",  # not an instance
    ],
)
def test_other_paths_are_nets_of_their_own_without_a_finding(node: str) -> None:
    body = f"V1 1 0 1\nX1 1 0 div\n.global vdd\n{_DIV}R3 {node} 0 1\nR4 vdd 0 1\n"
    body = body.replace(".subckt div a b\nR1 a m 1\n", ".subckt div a b\nR1 a m 1\nR9 vdd 0 1\n")
    assert _netlist(body).diagnostics == ()


def test_a_nested_path_reaches_through_each_instance() -> None:
    # dp1 and dp2: `X1:X2:m` at the top level and `X2:m` in `top`'s body are both joined.
    netlist = _netlist(
        "V1 1 0 1\nX1 1 0 top\n.subckt top p q\nX2 p q div\nR3 X2:m q 1\n.ends\n"
        + _DIV
        + "R4 X1:X2:m 0 1\n"
    )
    assert _codes(netlist) == [
        (6, DiagnosticCode.NODE_INTO_INSTANCE, "warning"),
        (12, DiagnosticCode.NODE_INTO_INSTANCE, "warning"),
    ]


def test_a_path_is_read_from_the_scope_it_is_written_in() -> None:
    # dp3: `X1` is a top-level instance, not one of `top2`, so Xyce makes a net of its own.
    netlist = _netlist(
        "V1 1 0 1\nX1 1 0 div\nX9 1 0 top2\n.subckt top2 p q\nR3 X1:m q 1\n.ends\n" + _DIV
    )
    assert netlist.diagnostics == ()


def test_a_path_into_an_included_definition_is_info() -> None:
    netlist = _netlist(".include 'x.lib'\nX1 1 0 ext\nR3 X1:m 0 1\n")
    found = [d for d in netlist.diagnostics if d.code is DiagnosticCode.NODE_INTO_INSTANCE]
    assert [(d.line, d.severity) for d in found] == [(4, "info")]
    assert "if the included definition has it as an internal node" in found[0].message


def test_an_expression_read_into_an_instance_is_info() -> None:
    netlist = _netlist(f"V1 1 0 1\nX1 1 0 div\n{_DIV}R3 b 0 {{V(X1:m)*1k}}\nR4 b 0 1\n")
    (finding,) = netlist.diagnostics
    assert (finding.code, finding.severity) == (DiagnosticCode.UNRESOLVED_NODE, "info")
    assert "inside instance `X1`" in finding.message


def test_ltspice_keeps_its_reading_of_a_port_path() -> None:
    # LTspice joins a port too (names.md N11); the xyce rule leaves it alone.
    text = f"t\nX1 1 0 div\n{_DIV}R3 X1:a 0 1\n.end\n"
    (finding,) = Netlist.from_text(text, dialect=Dialect.LTSPICE).diagnostics
    assert finding.code is DiagnosticCode.NODE_INTO_INSTANCE


def test_k_refers_to_its_core_model() -> None:
    netlist = _netlist("L1 a 0 1u\nL2 b 0 1u\nK1 L1 L2 0.9 kc\n.model kc CORE\n")
    assert netlist.diagnostics == ()
    (reference,) = [r for r in netlist.references if r.kind == "model"]
    assert reference.name == "kc"
    assert netlist.resolve(reference) is netlist.lines[4].item


def test_an_unresolved_or_mistyped_core_model_is_reported() -> None:
    netlist = _netlist("L1 a 0 1u\nL2 b 0 1u\nK1 L1 L2 0.9 km\nK2 L1 L2 0.9 nomodel\n.model km D\n")
    assert _codes(netlist) == [
        (4, DiagnosticCode.MODEL_TYPE_MISMATCH, "warning"),
        (5, DiagnosticCode.UNRESOLVED_MODEL, "warning"),
    ]
    assert "a model of type `CORE`" in netlist.diagnostics[0].message


def test_an_unresolved_function_is_reported_as_a_parameter_is() -> None:
    netlist = _netlist(".func g(x) {x*2}\nR1 a 0 {f(2)}\nR2 a 0 {g(1)}\n")
    (finding,) = netlist.diagnostics
    assert (finding.code, finding.severity, finding.line) == (
        DiagnosticCode.UNRESOLVED_PARAM,
        "warning",
        3,
    )
    assert finding.message.startswith("function `f` is not defined")


def test_an_unresolved_function_with_an_include_is_info() -> None:
    netlist = _netlist(".include 'f.inc'\nR1 a 0 {f(2)}\n")
    (finding,) = netlist.diagnostics
    assert (finding.code, finding.severity) == (DiagnosticCode.UNRESOLVED_PARAM, "info")


def test_a_builtin_function_is_not_a_reference() -> None:
    assert _netlist("R1 a 0 {sqrt(4)*1k}\n").diagnostics == ()


def test_a_model_place_word_naming_a_parameter_says_xyce_reads_a_value() -> None:
    # xm1-tasks 5.1 point 9(b).
    netlist = _netlist(".param rv=2k\nR1 a 0 rv 1k\nR2 a 0 rmod 1k\n")
    first, second = netlist.diagnostics
    assert (first.code, first.severity, first.line) == (
        DiagnosticCode.UNRESOLVED_MODEL,
        "warning",
        3,
    )
    assert "a parameter `rv` is visible" in first.message
    assert "reads the word as the value" in first.message
    assert second.code is DiagnosticCode.UNRESOLVED_MODEL
    assert "parameter" not in second.message


def test_a_parameter_in_an_enclosing_scope_counts_for_the_note() -> None:
    netlist = _netlist(".param rv=2k\nX1 a 0 s\n.subckt s p q\nC1 p q rv 1p\n.ends\n")
    (finding,) = netlist.diagnostics
    assert "a parameter `rv` is visible" in finding.message


def test_a_model_name_that_reads_as_a_number_is_a_warning() -> None:
    # xm1-tasks 5.1 point 9(c): the library reads `2k` on R1 as the value; Xyce as the model.
    netlist = _netlist(".model 2k R\n.model 1e3 RES\n.model r1k R\nR1 a 0 2k\n")
    assert _codes(netlist) == [
        (2, DiagnosticCode.NUMERIC_MODEL_NAME, "warning"),
        (3, DiagnosticCode.NUMERIC_MODEL_NAME, "warning"),
    ]
    assert "reads as a number" in netlist.diagnostics[0].message


def test_the_other_dialects_keep_their_model_findings() -> None:
    text = "t\n.param rv=2k\nR1 a 0 1k rv\n.end\n"
    (finding,) = Netlist.from_text(text, dialect=Dialect.NGSPICE).diagnostics
    assert finding.code is DiagnosticCode.UNRESOLVED_MODEL
    assert "parameter" not in finding.message
