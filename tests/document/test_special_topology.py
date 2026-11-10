"""The special and mixed-signal devices' topology: nodes, ports, controlling and node references
(M17 T4, T6 and T7; decision 0020 items 2, 4, 6, 7 and 8)."""

from __future__ import annotations

import pytest

from netlistmod import (
    CodeModelDevice,
    DiagnosticCode,
    Dialect,
    Edit,
    FrequencyAnalyzer,
    Netlist,
    Span,
    TopologyViolation,
)
from tests.support.dialects import ltspice_only, ngspice_only

_CODE = (
    "V1 in 0 1\nVs in x 0\nRx x 0 1k\n"
    "a1 [in null] %v(out) sum\n"
    "a2 %vd [in 0 x 0] %i out2 sum\n"
    "a3 %vnam Vs ~d dig\n"
    "N1 in out rmod w=1u\n"
    ".model sum summer\n.model dig d_inverter\n.model rmod r2_cmc\n"
)
_LT = (
    "V1 in 0 1\nA1 in 0 0 0 0 nq q 0 BUF Vhigh=5\n"
    "@1 in out fstart=1k refnode=q intnode=out\n&1 out 0 in 0\n"
)


def _ng(body: str = _CODE) -> Netlist:
    return Netlist.from_text(f"title\n{body}.end\n", dialect=Dialect.NGSPICE)


def _lt(body: str = _LT) -> Netlist:
    return Netlist.from_text(f"title\n{body}.end\n", dialect=Dialect.LTSPICE)


def _violates(netlist: Netlist, edits: list[Edit]) -> None:
    with pytest.raises(TopologyViolation):
        netlist.apply(edits)


@ngspice_only
def test_every_code_model_node_is_a_connection_without_null_or_the_source() -> None:
    netlist = _ng()
    assert [c.net.name for c in netlist.connections("a1")] == ["in", "out"]
    assert [c.net.name for c in netlist.connections("a2")] == ["in", "0", "x", "0", "out2"]
    assert [c.net.name for c in netlist.connections("a3")] == ["d"]
    assert "vs" not in {net.name for net in netlist.nets()}
    assert "a1" in [e.designator for e in netlist.elements_on_net("out")]
    entries = netlist.signature().entries
    assert ("element", (), "a1", "CodeModelDevice", ("in", "out")) in entries
    assert ("control", (), "a3", "Vs") in entries


@ngspice_only
def test_the_signature_records_each_port_and_connection() -> None:
    entries = _ng().signature().entries
    ports = {entry[2]: entry[3] for entry in entries if entry[0] == "ports"}
    assert ports["a1"] == (
        (0, True, None, ((None, ("in",), False), (None, (), True))),
        (1, False, None, (("%v", ("out",), False),)),
    )
    assert ports["a2"][0] == (
        0,
        True,
        "%vd",
        ((None, ("in", "0"), False), (None, ("x", "0"), False)),
    )
    # `~` inverts a value, not a connection, so it is not in the signature.
    assert ports["a3"][1] == (1, False, None, ((None, ("d",), False),))


@ngspice_only
@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("a1 [in null] %v(out) sum", "a1 [null in] %v(out) sum"),  # a node and null swapped
        ("a1 [in null] %v(out) sum", "a1 [in] null %v(out) sum"),  # a node moved between ports
        ("a1 [in null] %v(out) sum", "a1 [in null] %i(out) sum"),  # a port type changed
        ("a2 %vd [in 0 x 0] %i out2 sum", "a2 %v [in 0 x 0] %i out2 sum"),  # the vector's type
        ("a3 %vnam Vs ~d dig", "a3 %vnam V1 ~d dig"),  # the %vnam source
        ("a3 %vnam Vs ~d dig", "a3 %vnam Vs ~e dig"),  # a node
    ],
)
def test_changing_a_port_or_its_source_is_a_topology_violation(old: str, new: str) -> None:
    netlist = _ng()
    start = netlist.source.text.index(old)
    _violates(netlist, [Edit(_span(start, len(old)), new, "rewire")])


@ngspice_only
def test_changing_any_node_of_each_line_is_a_topology_violation() -> None:
    netlist = _ng()
    for designator in ("a1", "a2", "a3", "N1"):
        for node in netlist.element(designator).nodes:
            _violates(netlist, [Edit(node.span, "zz", f"rewire {designator}")])
    item = netlist.element("a3")
    assert isinstance(item, CodeModelDevice)
    _violates(netlist, [Edit(item.control[0].span, "V1", "another source")])


@ngspice_only
def test_tilde_is_not_topology() -> None:
    netlist = _ng()
    start = netlist.source.text.index("~d")
    edited = netlist.apply([Edit(_span(start, 1), "", "drop the inversion")])
    assert edited.signature() == netlist.signature()


@ngspice_only
def test_an_osdi_device_has_its_nodes_and_its_model() -> None:
    netlist = _ng()
    assert [c.net.name for c in netlist.connections("N1")] == ["in", "out"]
    assert ("element", (), "N1", "OsdiDevice", ("in", "out")) in netlist.signature().entries
    assert not [d for d in netlist.diagnostics if d.code is DiagnosticCode.UNRESOLVED_MODEL]


@ngspice_only
@pytest.mark.parametrize("line", ["a9 in out dm", "N9 in out dm"])
def test_a_built_in_model_type_is_a_mismatch(line: str) -> None:
    netlist = _ng(f"{line}\n.model dm d\n")
    found = [d for d in netlist.diagnostics if d.code is DiagnosticCode.MODEL_TYPE_MISMATCH]
    assert len(found) == 1 and "not a built-in SPICE type" in found[0].message


@ngspice_only
def test_a_missing_vnam_source_is_unresolved() -> None:
    netlist = _ng("a1 %vnam Vnone out amp\n.model amp gain\n")
    found = [d for d in netlist.diagnostics if d.code is DiagnosticCode.UNRESOLVED_ELEMENT]
    assert [d.message.split()[1] for d in found] == ["`Vnone`"]


@ltspice_only
def test_special_function_and_probe_nodes_are_connections() -> None:
    netlist = _lt()
    assert [c.net.name for c in netlist.connections("A1")] == ["in", *["0"] * 4, "nq", "q", "0"]
    assert [c.net.name for c in netlist.connections("&1")] == ["out", "0", "in", "0"]
    assert [c.net.name for c in netlist.connections("@1")] == ["in", "out"]
    entries = netlist.signature().entries
    assert ("element", (), "@1", "FrequencyAnalyzer", ("in", "out")) in entries


@ltspice_only
def test_changing_any_node_is_a_topology_violation_on_lt_lines() -> None:
    netlist = _lt()
    for designator in ("A1", "@1", "&1"):
        for node in netlist.element(designator).nodes:
            _violates(netlist, [Edit(node.span, "zz", f"rewire {designator}")])


@ltspice_only
def test_refnode_and_intnode_are_node_references_not_terminals() -> None:
    netlist = _lt()
    analyzer = netlist.element("@1")
    assert isinstance(analyzer, FrequencyAnalyzer)
    assert analyzer.reference_net is not None and analyzer.reference_net.name == "q"
    assert [c.net.name for c in netlist.connections("@1")] == ["in", "out"]
    edited = netlist.set_param("@1", "refnode", "in")
    assert edited.signature() == netlist.signature()
    missing = _lt(_LT.replace("refnode=q", "refnode=nowhere"))
    found = [d for d in missing.diagnostics if d.code is DiagnosticCode.UNRESOLVED_NODE]
    assert len(found) == 1 and "`nowhere`" in found[0].message


@ltspice_only
@pytest.mark.parametrize(
    ("body", "unresolved"),
    [
        ("@1 a b\n&1 a 0 b 0\n", False),
        ("@A a b\n&a a 0 b 0\n", False),  # the suffix compares in any case
        ("@1 a b\n&2 a 0 b 0\n", False),  # the scope's only @ (LTspice runs it)
        ("&1 a 0 b 0\n", True),  # no @
        ("@1 a b\n@3 c d\n&2 a 0 b 0\n", True),  # two @ and no match
        ("@1 a b\n.subckt s a b\n&1 a 0 b 0\n.ends\n", True),  # @1 is in another scope
    ],
)
def test_a_probe_finds_its_analyzer(body: str, unresolved: bool) -> None:
    netlist = _lt(body)
    found = [d for d in netlist.diagnostics if d.code is DiagnosticCode.UNRESOLVED_ELEMENT]
    assert bool(found) == unresolved


def _span(start: int, length: int) -> Span:
    return Span(start, start + length)
