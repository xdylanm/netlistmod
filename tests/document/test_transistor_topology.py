"""Transistor nodes reach the topology as written (M13 review R8, decision 0014 item 3)."""

from __future__ import annotations

import pytest

from netlistmod import Netlist
from tests.support.dialects import current_dialect


def _netlist(body: str) -> Netlist:
    return Netlist.from_text(f"title\n{body}\n.end\n", dialect=current_dialect())


def test_a_source_written_twice_is_two_connections_to_one_net() -> None:
    # LTspice's export of a 3-pin VDMOS symbol writes the source twice.
    netlist = _netlist("MQ8 d g OUT OUT nm\nR1 OUT 0 1k\n.model nm VDMOS")
    assert [element.designator for element in netlist.elements_on_net("OUT")] == ["MQ8", "R1"]
    connections = netlist.connections("MQ8")
    assert [(c.terminal, c.node.name) for c in connections] == [
        (0, "d"),
        (1, "g"),
        (2, "OUT"),
        (3, "OUT"),
    ]
    assert connections[2].net == connections[3].net


def test_a_three_node_q_gains_no_ground_connection() -> None:
    netlist = _netlist("Q1 c b e qn\nR1 c 0 1k\n.model qn NPN")
    assert [c.net.name for c in netlist.connections("Q1")] == ["c", "b", "e"]
    assert [element.designator for element in netlist.elements_on_net("0")] == ["R1"]
    entries = netlist.signature().entries
    assert ("element", (), "Q1", "BipolarTransistor", ("c", "b", "e")) in entries


@pytest.mark.ngspice_only
def test_a_five_node_q_lists_all_five_nets() -> None:
    netlist = _netlist("Q1 c b e s tj qv\n.model qv NPN level=4")
    assert [c.net.name for c in netlist.connections("Q1")] == ["c", "b", "e", "s", "tj"]
    assert [net.name for net in netlist.nets()] == ["c", "b", "e", "s", "tj"]
    for name in ("c", "b", "e", "s", "tj"):
        assert [element.designator for element in netlist.elements_on_net(name)] == ["Q1"]
