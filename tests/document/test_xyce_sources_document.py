"""The document layer on xyce's transient functions and the P port (X-M3 B4; decision 0030
items 5, 6 and 8)."""

from __future__ import annotations

from netlistmod import Netlist
from netlistmod.dialects import _XYCE
from netlistmod.model.nodes import PortSource


def _netlist(body: str) -> Netlist:
    return Netlist.from_text(f"title\n{body}.end\n", dialect=_XYCE)


def test_a_function_argument_and_a_port_field_reference_parameters() -> None:
    netlist = _netlist(
        ".param hi=1 n=1 zz=50 r=0\nV1 a 0 PULSE(0 {hi})\nP1 b 0 port={n} Z0={zz} "
        "PAT(5 0 0 1n 1n 5n b01) R={r}\nR1 a b 1k\n"
    )
    names = sorted(r.name for r in netlist.references if r.kind == "param")
    assert names == ["hi", "n", "r", "zz"]
    assert all(r.target is not None for r in netlist.references if r.kind == "param")


def test_pwl_file_makes_no_reference_and_is_never_read() -> None:
    # Xyce resolves the path against the working directory, so there is nothing to resolve.
    netlist = _netlist('V1 a 0 PWL FILE "missing.csv" TD=1n\nR1 a 0 1k\n')
    assert netlist.references == ()
    assert netlist.diagnostics == ()


def test_a_port_is_an_element_of_its_scope_and_connects_its_nets() -> None:
    netlist = _netlist("P1 a 0 port=1\nR1 a 0 50\n")
    port = netlist.element("p1")
    assert isinstance(port, PortSource)
    assert [connection.net.name for connection in netlist.connections("P1")] == ["a", "0"]
