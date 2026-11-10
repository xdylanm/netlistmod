"""Transmission-line nodes are topology, and their models resolve (M16 T6, decision 0019)."""

from __future__ import annotations

import pytest

from netlistmod import DiagnosticCode, Edit, Netlist, TopologyViolation
from tests.support.dialects import current_dialect, ngspice_only

_BOTH = (
    "V1 in 0 1\nR1 in a 50\nT1 a 0 b 0 Z0=50 TD=1n\nO1 a 0 c 0 lmod\nU1 a d 0 umod L=5\n"
    ".model lmod LTRA(R=1 L=50n C=20p len=1)\n.model umod URC(Rperl=10 Cperl=1p)\n"
)
_NGSPICE = (
    "Y1 a 0 e 0 ymod\nP1 a f 0 g h 0 pmod\n.model ymod TXL R=1 L=50n G=0 C=20p length=1\n"
    ".model pmod CPL length=1\n+R=1 0 1\n+L=50n 5n 50n\n+G=0 0 0\n+C=20p -2p 20p\n"
)


def _netlist(body: str) -> Netlist:
    return Netlist.from_text(f"title\n{body}.end\n", dialect=current_dialect())


@pytest.mark.parametrize(
    ("designator", "kind", "nets"),
    [
        ("T1", "LosslessLine", ["a", "0", "b", "0"]),
        ("O1", "LossyLine", ["a", "0", "c", "0"]),
        ("U1", "RcLine", ["a", "d", "0"]),
    ],
)
def test_every_node_is_a_connection_and_in_the_signature(
    designator: str, kind: str, nets: list[str]
) -> None:
    netlist = _netlist(_BOTH)
    assert [c.net.name for c in netlist.connections(designator)] == nets
    for name in nets:
        assert designator in [e.designator for e in netlist.elements_on_net(name)]
    nodes = tuple(node.name for node in netlist.element(designator).nodes)
    assert ("element", (), designator, kind, nodes) in netlist.signature().entries
    assert {net.name for net in netlist.nets()} >= set(nets)


@ngspice_only
@pytest.mark.parametrize(
    ("designator", "kind", "nets"),
    [
        ("Y1", "TxlLine", ["a", "0", "e", "0"]),
        ("P1", "CoupledLine", ["a", "f", "0", "g", "h", "0"]),
    ],
)
def test_y_and_p_nodes_are_topology(designator: str, kind: str, nets: list[str]) -> None:
    netlist = _netlist(_BOTH + _NGSPICE)
    assert [c.net.name for c in netlist.connections(designator)] == nets
    nodes = tuple(node.name for node in netlist.element(designator).nodes)
    assert ("element", (), designator, kind, nodes) in netlist.signature().entries


def _rewire(netlist: Netlist, designator: str, terminal: int) -> None:
    node = netlist.element(designator).nodes[terminal]
    with pytest.raises(TopologyViolation):
        netlist.apply([Edit(node.span, "zz", f"rewire {designator}")])


@pytest.mark.parametrize(("designator", "count"), [("T1", 4), ("O1", 4), ("U1", 3)])
def test_changing_any_node_is_a_topology_violation(designator: str, count: int) -> None:
    netlist = _netlist(_BOTH)
    for terminal in range(count):
        _rewire(netlist, designator, terminal)


@ngspice_only
@pytest.mark.parametrize(("designator", "count"), [("Y1", 4), ("P1", 6)])
def test_changing_any_y_or_p_node_is_a_topology_violation(designator: str, count: int) -> None:
    netlist = _netlist(_BOTH + _NGSPICE)
    for terminal in range(count):
        node = netlist.element(designator).nodes[terminal]
        # A reference node must stay ground, so it is renamed to the other ground spelling.
        text = "gnd" if node.name == "0" else "zz"
        with pytest.raises(TopologyViolation):
            netlist.apply([Edit(node.span, text, f"rewire {designator}")])


@ngspice_only
def test_changing_the_line_count_of_p_is_a_topology_violation() -> None:
    netlist = _netlist(_BOTH + _NGSPICE)
    item = netlist.element("P1")
    with pytest.raises(TopologyViolation):
        netlist.apply(
            [
                Edit(item.nodes[2].span, "x2 0", "add a line"),
                Edit(item.nodes[5].span, "y2 0", "add a line"),
            ]
        )


def test_models_resolve_and_a_wrong_type_is_a_mismatch() -> None:
    netlist = _netlist(_BOTH)
    assert not [d for d in netlist.diagnostics if d.code is DiagnosticCode.UNRESOLVED_MODEL]
    swapped = _netlist(_BOTH.replace("O1 a 0 c 0 lmod", "O1 a 0 c 0 umod"))
    mismatches = [d for d in swapped.diagnostics if d.code is DiagnosticCode.MODEL_TYPE_MISMATCH]
    assert len(mismatches) == 1 and "`LTRA`" in mismatches[0].message
    missing = _netlist(_BOTH.replace("U1 a d 0 umod", "U1 a d 0 nomod"))
    assert [d.code for d in missing.diagnostics].count(DiagnosticCode.UNRESOLVED_MODEL) == 1


@ngspice_only
def test_y_and_p_take_their_own_model_types() -> None:
    netlist = _netlist(_BOTH + _NGSPICE)
    codes = [d.code for d in netlist.diagnostics]
    assert DiagnosticCode.MODEL_TYPE_MISMATCH not in codes
    swapped = _netlist(_BOTH + _NGSPICE.replace("Y1 a 0 e 0 ymod", "Y1 a 0 e 0 pmod"))
    mismatches = [d for d in swapped.diagnostics if d.code is DiagnosticCode.MODEL_TYPE_MISMATCH]
    assert len(mismatches) == 1 and "`TXL`" in mismatches[0].message


def test_a_t_line_reads_parameters_from_its_formulas() -> None:
    netlist = _netlist(".param z=50\n" + _BOTH.replace("Z0=50", "Z0={z}"))
    assert not [d for d in netlist.diagnostics if d.code is DiagnosticCode.UNRESOLVED_PARAM]
    undefined = _netlist(_BOTH.replace("Z0=50", "Z0={zz}"))
    assert DiagnosticCode.UNRESOLVED_PARAM in [d.code for d in undefined.diagnostics]
