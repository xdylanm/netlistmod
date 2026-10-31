"""Topology view and signature (M5 T5): nets, connections, ports, and the signature properties."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from netlistmod import Dialect, Net, Netlist, Resistor, SubcktInstance


def _netlist(body: str) -> Netlist:
    return Netlist.from_text(f"title\n{body}\n.end\n", dialect=Dialect.NGSPICE)


def _names(nets: tuple[Net, ...]) -> list[tuple[str, tuple[str, ...]]]:
    return [(net.name, net.scope) for net in nets]


def test_nets_fold_case_and_merge_ground_aliases() -> None:
    netlist = _netlist("V1 IN 0 DC 3\nR1 in OUT 1k\nR2 out GND 1k\nR3 out gnd 1k\nR4 out 00 1")
    nets = netlist.nets()
    assert _names(nets) == [("in", ()), ("0", ()), ("out", ()), ("00", ())]
    assert nets[0].spellings == ("IN", "in")
    assert nets[1].spellings == ("0", "GND", "gnd")
    assert nets[1].global_ and not nets[3].global_
    assert [e.designator for e in netlist.elements_on_net("IN")] == ["V1", "R1"]
    assert [e.designator for e in netlist.elements_on_net(nets[1])] == ["V1", "R2", "R3"]
    assert netlist.topology.net("Gnd") == nets[1]
    with pytest.raises(KeyError, match="no net"):
        netlist.topology.net("nowhere")


def test_local_nets_ports_and_global_nodes() -> None:
    netlist = _netlist(
        ".global VCC\nV1 vcc 0 3\nX1 in out div\nR9 mid 0 1\n"
        ".subckt div a b\nR1 a mid 1k\nR2 mid b 1k\nR3 vcc 0 1\n.ends"
    )
    top = netlist.nets()
    assert _names(top) == [("vcc", ()), ("0", ()), ("in", ()), ("out", ()), ("mid", ())]
    local = netlist.nets(("div",))
    assert _names(local) == [
        ("a", ("div",)),
        ("b", ("div",)),
        ("mid", ("div",)),
        ("vcc", ()),
        ("0", ()),
    ]
    assert top[0] is local[3]
    assert top[0].global_ and top[0].spellings == ("VCC", "vcc")
    assert netlist.elements_on_net("mid") == (netlist.element("R9"),)
    assert [e.designator for e in netlist.elements_on_net("mid", ("div",))] == ["R1", "R2"]
    assert _names(netlist.ports("DIV")) == [("a", ("div",)), ("b", ("div",))]
    assert netlist.ports("div", ("div",)) == netlist.ports("div")
    with pytest.raises(KeyError, match="no subcircuit 'nope'"):
        netlist.ports("nope")


def test_global_nodes_are_shared_across_scopes() -> None:
    netlist = _netlist(
        ".global vdd\n.subckt a x\nR1 x vdd 1\n.ends\n.subckt b y\nR1 y VDD 1\n.ends"
    )
    (shared,) = [net for net in netlist.nets(("a",)) if net.name == "vdd"]
    assert shared in netlist.nets(("b",))
    assert shared.scope == () and shared.global_
    assert shared.spellings == ("vdd", "VDD")


def test_connections_list_each_terminal() -> None:
    netlist = _netlist("X1 in OUT 0 amp\nk1 l1 l2 1\nL1 a 0 1\nL2 b 0 1\n.subckt amp p q r\n.ends")
    connections = netlist.connections("x1")
    assert [(c.terminal, c.node.name, c.net.name) for c in connections] == [
        (0, "in", "in"),
        (1, "OUT", "out"),
        (2, "0", "0"),
    ]
    assert isinstance(connections[0].element, SubcktInstance)
    assert netlist.connections("K1") == ()
    with pytest.raises(KeyError, match="no element"):
        netlist.connections("R1")


def test_elements_in_opaque_blocks_are_not_seen() -> None:
    netlist = _netlist(".if (1)\nR1 hidden 0 1\n.endif\nR2 a 0 1")
    assert _names(netlist.nets()) == [("a", ()), ("0", ())]


def test_signature_uses_exact_text_and_has_a_stable_digest() -> None:
    netlist = _netlist(
        ".global vcc\nX1 in out div\nK1 L1 L2 0.5\nL1 a 0 1\nL2 b 0 1\n"
        ".subckt div a b\nR1 a b 1k\n.ends\nR1 in GND 1k"
    )
    signature = netlist.signature()
    assert signature.entries == (
        ("instance", (), "X1", ("in", "out"), "div"),
        ("coupling", (), "K1", ("L1", "L2")),
        ("element", (), "L1", "Inductor", ("a", "0")),
        ("element", (), "L2", "Inductor", ("b", "0")),
        ("subckt", (), "div", ("a", "b")),
        ("element", ("div",), "R1", "Resistor", ("a", "b")),
        ("element", (), "R1", "Resistor", ("in", "GND")),
        ("global", ("vcc",)),
    )
    assert len(signature.digest()) == 64
    assert signature.digest() == netlist.signature().digest()
    assert hash(signature) == hash(netlist.signature())
    case_only = _netlist(netlist.text[6:-6].replace("GND", "gnd"))
    assert case_only.nets() == netlist.nets()
    assert case_only.signature() != signature


# Hypothesis: a generator that knows the topology it renders (T9, T5 a-c).

_NODES = ["in", "OUT", "out2", "n1", "/v", "gnd", "0", "00", "N_3"]
_VALUES = ["1k", "{rx}", "2.2e3", "'rx*2'", "10"]


@dataclass(frozen=True)
class _Element:
    letter: str
    designator: str
    nodes: tuple[str, str]


@dataclass(frozen=True)
class _Circuit:
    globals: tuple[str, ...]
    ports: tuple[str, ...]
    local: tuple[_Element, ...]
    top: tuple[_Element, ...]
    instances: tuple[tuple[str, ...], ...]
    coupling: bool


@dataclass(frozen=True)
class _Style:
    blank: str
    comments: bool
    continuation: str
    value: str
    directives: bool
    param_line: bool


@st.composite
def _elements(draw: st.DrawFn, prefix: str) -> tuple[_Element, ...]:
    count = draw(st.integers(min_value=1, max_value=4))
    elements = []
    for index in range(count):
        letter = draw(st.sampled_from("RCLV"))
        nodes = (draw(st.sampled_from(_NODES)), draw(st.sampled_from(_NODES)))
        elements.append(_Element(letter, f"{letter}{prefix}{index}", nodes))
    return tuple(elements)


@st.composite
def _circuits(draw: st.DrawFn) -> _Circuit:
    ports = tuple(draw(st.lists(st.sampled_from(["p", "q", "r", "in"]), min_size=1, max_size=3)))
    instances = tuple(
        tuple(draw(st.sampled_from(_NODES)) for _ in ports)
        for _ in range(draw(st.integers(min_value=0, max_value=2)))
    )
    return _Circuit(
        globals=tuple(draw(st.lists(st.sampled_from(["vcc", "n1", "VDD"]), max_size=2))),
        ports=ports,
        local=draw(_elements("a")),
        top=draw(_elements("t")),
        instances=instances,
        coupling=draw(st.booleans()),
    )


_STYLES = st.builds(
    _Style,
    blank=st.sampled_from([" ", "  ", "\t", " \t "]),
    comments=st.booleans(),
    continuation=st.sampled_from(["", "+", "\\\\"]),
    value=st.sampled_from(_VALUES),
    directives=st.booleans(),
    param_line=st.booleans(),
)


def _element_line(element: _Element, style: _Style) -> str:
    gap = style.blank
    value = style.value if element.letter != "V" else "DC 1"
    if element.letter == "C" and style.value == "{rx}":
        value = "1p"
    first = f"{element.designator}{gap}{element.nodes[0]}{gap}{element.nodes[1]}"
    if style.continuation == "+":
        line = f"{first}\n+{gap}{value}"
    elif style.continuation:
        line = f"{first}{gap}{style.continuation}\n{value}"
    else:
        line = f"{first}{gap}{value}"
    return line + (" ; note" if style.comments else "")


def _render(circuit: _Circuit, style: _Style) -> str:
    lines = ["generated"]
    if style.param_line:
        lines.append(f".param rx={style.value if style.value[0].isdigit() else '1k'}")
    else:
        lines.append(".param rx=1k")
    if circuit.globals:
        lines.append(".global " + style.blank.join(circuit.globals))
    if style.comments:
        lines.append("* a comment line")
    lines.append(f".subckt sub {' '.join(circuit.ports)}")
    lines.extend(_element_line(element, style) for element in circuit.local)
    lines.append(".ends")
    if style.directives:
        lines.extend(["", ".op", ".options reltol=1e-3"])
    lines.extend(_element_line(element, style) for element in circuit.top)
    for index, nodes in enumerate(circuit.instances):
        lines.append(f"X{index}{style.blank}{style.blank.join(nodes)}{style.blank}sub")
    inductors = [e.designator for e in circuit.top if e.letter == "L"]
    if circuit.coupling and len(inductors) >= 2:
        lines.append(f"K1 {inductors[0]} {inductors[1]} 0.5")
    lines.append(".end")
    return "\n".join(lines) + "\n"


def _load(circuit: _Circuit, style: _Style) -> Netlist:
    return Netlist.from_text(_render(circuit, style), dialect=Dialect.NGSPICE)


@settings(max_examples=150, deadline=None)
@given(_circuits(), _STYLES, _STYLES)
def test_signature_ignores_formatting_values_and_directives(
    circuit: _Circuit, first: _Style, second: _Style
) -> None:
    one, two = _load(circuit, first), _load(circuit, second)
    assert one.signature() == two.signature()
    assert one.signature().digest() == two.signature().digest()


def _mutations(circuit: _Circuit) -> list[_Circuit]:
    head = circuit.top[0]
    mutated = [
        replace(
            circuit,
            top=(replace(head, nodes=(head.nodes[0] + "x", head.nodes[1])),) + circuit.top[1:],
        ),
        replace(circuit, top=(replace(head, designator=head.designator + "9"),) + circuit.top[1:]),
        replace(circuit, globals=(*circuit.globals, "extra")),
        replace(circuit, ports=(*circuit.ports, "s"), instances=()),
        replace(circuit, local=circuit.local + (_Element("R", "Rnew", ("p", "q")),)),
    ]
    if head.nodes[0].swapcase() != head.nodes[0]:
        # A case-only change: the queries see the same net, the signature does not.
        nodes = (head.nodes[0].swapcase(), head.nodes[1])
        mutated.append(replace(circuit, top=(replace(head, nodes=nodes), *circuit.top[1:])))
    if len(circuit.top) > 1:
        mutated.append(replace(circuit, top=(circuit.top[1], circuit.top[0], *circuit.top[2:])))
    for index, nodes in enumerate(circuit.instances):
        changed = (nodes[0] + "y", *nodes[1:])
        mutated.append(
            replace(
                circuit,
                instances=circuit.instances[:index] + (changed,) + circuit.instances[index + 1 :],
            )
        )
    return mutated


@settings(max_examples=100, deadline=None)
@given(_circuits(), _STYLES)
def test_signature_changes_with_any_topology_token(circuit: _Circuit, style: _Style) -> None:
    signature = _load(circuit, style).signature()
    for mutated in _mutations(circuit):
        assert _load(mutated, style).signature() != signature, _render(mutated, style)


def _oracle(circuit: _Circuit, scope: tuple[str, ...]) -> list[tuple[str, tuple[str, ...]]]:
    shared = {name.lower() for name in circuit.globals}

    def key(name: str) -> tuple[str, tuple[str, ...]]:
        canonical = "0" if name.lower() in {"0", "gnd"} else name.lower()
        return (canonical, () if canonical == "0" or canonical in shared else scope)

    if scope:
        names = [*circuit.ports, *(n for e in circuit.local for n in e.nodes)]
    else:
        names = [
            *circuit.globals,
            *(n for e in circuit.top for n in e.nodes),
            *(n for nodes in circuit.instances for n in nodes),
        ]
    return list(dict.fromkeys(key(name) for name in names))


@settings(max_examples=150, deadline=None)
@given(_circuits(), _STYLES)
def test_nets_agree_with_the_generator(circuit: _Circuit, style: _Style) -> None:
    netlist = _load(circuit, style)
    assert _names(netlist.nets()) == _oracle(circuit, ())
    assert _names(netlist.nets(("sub",))) == _oracle(circuit, ("sub",))
    for element in circuit.top:
        found = netlist.element(element.designator)
        assert [c.node.name for c in netlist.connections(element.designator)] == list(element.nodes)
        assert isinstance(found, Resistor) == (element.letter == "R")
