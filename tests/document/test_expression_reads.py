"""What an expression reads: the scan, the query and the diagnostics (M15 T6, T7; decision 0016)."""

from __future__ import annotations

import pytest

from netlistmod import Component, DiagnosticCode, Net, Netlist
from tests.support.dialects import current_dialect, is_ltspice

C = DiagnosticCode


def _netlist(body: str) -> Netlist:
    return Netlist.from_text(f"title\n{body}\n.end\n", dialect=current_dialect())


def _codes(netlist: Netlist) -> list[tuple[DiagnosticCode, str, str]]:
    return [(d.code, d.severity, netlist.slice(d.span)) for d in netlist.diagnostics]


_CIRCUIT = "V1 a 0 1\nVs a b 0\nR1 b 0 1k\nB1 o 0 V=2*v(a)+v(b,0)+1k*i(Vs)\nR2 o 0 1k"


def test_expression_reads_lists_nets_and_sources() -> None:
    netlist = _netlist(_CIRCUIT)
    reads = netlist.expression_reads("B1")
    assert [(read.kind, read.name) for read in reads] == [
        ("node", "a"),
        ("node", "b"),
        ("node", "0"),
        ("source", "Vs"),
    ]
    assert all(netlist.slice(read.span) == read.name for read in reads)
    assert isinstance(reads[0].target, Net) and reads[0].target.name == "a"
    assert isinstance(reads[3].target, Component) and reads[3].target.designator == "Vs"
    assert _codes(netlist) == []


def test_reads_are_not_topology() -> None:
    netlist = _netlist(_CIRCUIT)
    assert [c.node.name for c in netlist.connections("B1")] == ["o", "0"]
    assert "B1" not in [e.designator for e in netlist.elements_on_net("a")]


def test_an_element_without_an_expression_reads_nothing() -> None:
    netlist = _netlist(_CIRCUIT + "\nF1 0 p Vs 2\nR3 p 0 1k")
    assert netlist.expression_reads("R1") == ()
    assert netlist.expression_reads("F1") == ()  # its controlling source is topology, not a read
    with pytest.raises(KeyError):
        netlist.expression_reads("B9")


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("R1 a 0 1k\nB1 o 0 V=v(nonode)", [(C.UNRESOLVED_NODE, "warning", "nonode")]),
        ("R1 a 0 1k\nB1 o 0 V=v(nonode)\n.include x.lib", [(C.UNRESOLVED_NODE, "info", "nonode")]),
        ("R1 a 0 1k\nB1 o 0 V=1k*i(Vnone)", [(C.UNRESOLVED_ELEMENT, "warning", "Vnone")]),
        ("R1 a 0 1k\nB1 o 0 V=v(0)+v(gnd)", []),
        (
            "R1 top 0 1\n.subckt s o\nB1 o 0 V=v(top)\n.ends\nX1 n s",
            [(C.UNRESOLVED_NODE, "warning", "top")],
        ),
        (".global vdd\nR1 vdd 0 1\n.subckt s o\nB1 o 0 V=v(vdd)\n.ends\nX1 n s", []),
        ("R1 a 0 1k\nB1 o 0 V=1k*i(R1)", []),  # any device has a current (manual 5.1)
    ],
)
def test_reads_are_diagnosed(body: str, expected: list[tuple[DiagnosticCode, str, str]]) -> None:
    assert _codes(_netlist(body)) == expected


def test_braces_inside_a_bare_expression_are_read() -> None:
    netlist = _netlist(".param Vlow=0.4\nR1 a 0 1\nB1 o 0 V = v(a) < {Vlow} ? {Vlow} : v(a)")
    assert [(r.kind, r.name) for r in netlist.references if r.kind == "param"] == [
        ("param", "Vlow"),
        ("param", "Vlow"),
    ]
    assert _codes(netlist) == []


@pytest.mark.ltspice_only
def test_ltspice_time_and_x_are_the_simulation_s_in_an_expression() -> None:
    # M8 found that .param time=3k is the parameter in R={time}; in B it is the simulation time.
    netlist = _netlist(
        ".param time=3k\nB1 o 0 V=time\nR1 o 0 {time}\nC1 o 0 Q=1u*x\nL1 o n Flux=1m*x\nR2 n 0 1"
    )
    params = [netlist.slice(r.span) for r in netlist.references if r.kind == "param"]
    assert params == ["time"]  # R1's only
    assert [ref.span.start for ref in netlist.references if ref.kind == "param"] == [
        netlist.text.index("{time}") + 1
    ]


@pytest.mark.ltspice_only
def test_ltspice_x_outside_charge_and_flux_is_a_parameter() -> None:
    assert _codes(_netlist("B1 o 0 V=x*2")) == [(C.UNRESOLVED_PARAM, "warning", "x")]


@pytest.mark.ltspice_only
def test_a_source_inside_an_instance_is_info() -> None:
    netlist = _netlist(".subckt s a\nVq a b 0\nRq b 0 1k\n.ends\nX1 vx s\nB1 o 0 V=2k*I(X1:Vq)")
    assert _codes(netlist) == [(C.UNRESOLVED_ELEMENT, "info", "X1:Vq")]


def test_value_forms_read_their_sources() -> None:
    body = (
        "V1 a 0 1\nVs a b 0\nR1 b 0 1k\nF1 0 o value={2*I(Vs)}\nR2 o 0 1k"
        if is_ltspice()
        else "V1 a 0 1\nR1 a 0 1k\nE1 o 0 vol='2*v(a)'\nR2 o 0 1k"
    )
    netlist = _netlist(body)
    designator = "F1" if is_ltspice() else "E1"
    expected = [("source", "Vs")] if is_ltspice() else [("node", "a")]
    assert [(r.kind, r.name) for r in netlist.expression_reads(designator)] == expected
    assert _codes(netlist) == []
