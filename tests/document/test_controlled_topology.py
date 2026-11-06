"""Controls are topology, and controlling sources resolve (M14 T7; decision 0015 items 2-5)."""

from __future__ import annotations

import pytest

from netlistmod import DiagnosticCode, Netlist
from tests.support.dialects import current_dialect, is_ltspice

C = DiagnosticCode
_CIRCUIT = (
    "V1 in 0 2\nVs in a 0\nR1 a 0 1k\n"
    "E1 eo 0 a 0 2\nG1 0 go a 0 1m\nF1 0 fo Vs 2\nH1 ho 0 Vs 1k\n"
    ".model sm SW\n.model cm CSW\nS1 so 0 a 0 sm\nW1 wo 0 Vs cm"
)


def _netlist(body: str) -> Netlist:
    return Netlist.from_text(f"title\n{body}\n.end\n", dialect=current_dialect())


def _codes(netlist: Netlist) -> list[tuple[DiagnosticCode, str, str]]:
    return [(d.code, d.severity, netlist.slice(d.span)) for d in netlist.diagnostics]


def test_control_nodes_are_connections() -> None:
    netlist = _netlist(_CIRCUIT)
    assert [e.designator for e in netlist.elements_on_net("a")] == ["Vs", "R1", "E1", "G1", "S1"]
    assert [c.node.name for c in netlist.connections("E1")] == ["eo", "0", "a", "0"]
    assert [c.node.name for c in netlist.connections("W1")] == ["wo", "0"]
    assert "a" in [net.name for net in netlist.nets()]


def test_the_signature_holds_each_controlling_source() -> None:
    entries = _netlist(_CIRCUIT).signature().entries
    assert ("element", (), "E1", "Vcvs", ("eo", "0", "a", "0")) in entries
    assert ("element", (), "F1", "Cccs", ("0", "fo")) in entries
    assert [entry for entry in entries if entry[0] == "control"] == [
        ("control", (), "F1", "Vs"),
        ("control", (), "H1", "Vs"),
        ("control", (), "W1", "Vs"),
    ]


def test_a_changed_controlling_source_changes_the_signature() -> None:
    before = _netlist(_CIRCUIT).signature()
    after = _netlist(_CIRCUIT.replace("F1 0 fo Vs 2", "F1 0 fo V1 2")).signature()
    assert before != after


def test_a_resolved_circuit_has_no_diagnostics() -> None:
    assert _codes(_netlist(_CIRCUIT)) == []


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("R1 a 0 1k\nF1 0 o Vnope 2", [(C.UNRESOLVED_ELEMENT, "warning", "Vnope")]),
        ("R1 a 0 1k\nF1 0 o Vnope 2\n.include s.lib", [(C.UNRESOLVED_ELEMENT, "info", "Vnope")]),
        # Only the element's own scope is searched, as both solvers do (decision 0015 item 4).
        (
            "V1 a 0 1\n.subckt s o\nF1 o 0 V1 2\n.ends\nX1 b s",
            [(C.UNRESOLVED_ELEMENT, "warning", "V1")],
        ),
        ("V1 a 0 1\n.subckt s o\nVq o 0 0\nH1 o 0 Vq 1k\n.ends\nX1 b s", []),
        ("Vz a 0 0\nF1 0 o vz 2", []),
        ("F1 0 o Vz 2\nVz a 0 0", []),
        ("R1 a 0 1k\nF1 0 o R1 2", [(C.CONTROL_SOURCE_MISMATCH, "warning", "R1")]),
        ("E1 b 0 a 0 1\nH1 o 0 E1 1k", [(C.CONTROL_SOURCE_MISMATCH, "warning", "E1")]),
        ("I1 a 0 1m\n.model cm CSW\nW1 o 0 I1 cm", [(C.CONTROL_SOURCE_MISMATCH, "warning", "I1")]),
        (".model cm CSW\nS1 o 0 a 0 cm", [(C.MODEL_TYPE_MISMATCH, "warning", "cm")]),
        ("V1 a 0 0\n.model sm SW\nW1 o 0 V1 sm", [(C.MODEL_TYPE_MISMATCH, "warning", "sm")]),
        ("S1 o 0 a 0 sm", [(C.UNRESOLVED_MODEL, "warning", "sm")]),
    ],
)
def test_controlling_sources_and_switch_models_are_checked(
    body: str, expected: list[tuple[DiagnosticCode, str, str]]
) -> None:
    assert _codes(_netlist(body)) == expected


def test_a_mismatch_says_what_each_solver_does() -> None:
    (diagnostic,) = _netlist("R1 a 0 1k\nF1 0 o R1 2").diagnostics
    assert "`F1` is controlled by `R1`, a resistor" in diagnostic.message
    also = "an E, H or L" if is_ltspice() else "an E or H source"
    assert f"also reads {also} here and stops on other elements" in diagnostic.message


@pytest.mark.ltspice_only
def test_a_source_inside_an_instance_is_info_on_ltspice() -> None:
    netlist = _netlist(".subckt s a\nVq a b 0\nRq b 0 1k\n.ends\nX1 n s\nH1 o 0 X1:Vq 1k")
    (diagnostic,) = netlist.diagnostics
    assert (diagnostic.code, diagnostic.severity) == (C.UNRESOLVED_ELEMENT, "info")
    assert "names a source inside instance `X1`" in diagnostic.message
