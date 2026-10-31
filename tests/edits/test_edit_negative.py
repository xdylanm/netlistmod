"""Forbidden and misused operations (M6 T10, T6 tier; architecture §7.3).

Topology has no setter, so each forbidden operation is attempted with a crafted plan through
``apply(plan)``, which must raise ``TopologyViolation`` and return nothing. API misuse raises
``TopologyError`` or ``EditError`` before any plan is applied.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from netlistmod import (
    Dialect,
    Edit,
    EditError,
    Netlist,
    OpaqueBlock,
    OpaqueStatement,
    Placement,
    Resistor,
    Span,
    SubcktDefinition,
    TopologyError,
    TopologyViolation,
)

_TEXT = (
    "negative\n"
    ".global vcc\n"
    ".param rx=1k\n"
    "V1 in 0 DC 3\n"
    "R1 in out {rx}\n"
    "R2 out 0 1k\n"
    "L1 a 0 1u\n"
    "L2 b 0 1u\n"
    "K1 L1 L2 0.9\n"
    "X1 in out div\n"
    ".subckt div p q\n"
    "Ra p q 1k\n"
    ".ends\n"
    ".include models.lib\n"
    ".control\n"
    "run\n"
    ".endc\n"
    ".if (1)\n"
    "Rc out 0 1k\n"
    ".endif\n"
    ".op\n"
    ".end\n"
)


def _netlist() -> Netlist:
    return Netlist.from_text(_TEXT, dialect=Dialect.NGSPICE)


def _span(netlist: Netlist, text: str, occurrence: int = 0) -> Span:
    """The span of the ``occurrence``-th ``text`` in the fixture (test-side lookup only)."""
    start = -1
    for _ in range(occurrence + 1):
        start = netlist.text.index(text, start + 1)
    return Span(start, start + len(text))


def _line(netlist: Netlist, kind: type, index: int = 0) -> Span:
    return netlist.lines.find_all(kind, recursive=True)[index].span


def _point(netlist: Netlist, text: str) -> Span:
    start = _span(netlist, text).start
    return Span(start, start)


Crafted = Callable[[Netlist], list[Edit]]

_CRAFTED: list[tuple[str, Crafted]] = [
    ("add an element", lambda n: [Edit(_point(n, ".op\n"), "R9 out 0 1k\n")]),
    ("remove an element", lambda n: [Edit(_line(n, Resistor, 1), "")]),
    (
        "reorder elements",
        lambda n: [
            Edit(_line(n, Resistor, 0), n.slice(_line(n, Resistor, 1))),
            Edit(_line(n, Resistor, 1), n.slice(_line(n, Resistor, 0))),
        ],
    ),
    ("change a node", lambda n: [Edit(n.element("R2").nodes[0].span, "mid")]),
    ("change a node's case", lambda n: [Edit(n.element("R2").nodes[0].span, "OUT")]),
    ("change a type", lambda n: [Edit(n.element("R2").designator_span, "C2")]),
    ("change a designator", lambda n: [Edit(n.element("R2").designator_span, "R3")]),
    (
        "rename a net",
        lambda n: [
            Edit(n.element("R1").nodes[1].span, "o"),
            Edit(n.element("R2").nodes[0].span, "o"),
        ],
    ),
    ("change a coupling target", lambda n: [Edit(_span(n, "L2 0.9"), "L1 0.9")]),
    ("change a subcircuit call", lambda n: [Edit(_span(n, "div\n.subckt"), "dv\n.subckt")]),
    ("change subcircuit ports", lambda n: [Edit(_span(n, "p q\nRa"), "p q r\nRa")]),
    ("remove a subcircuit", lambda n: [Edit(_line(n, SubcktDefinition), "")]),
    (
        "add a subcircuit",
        lambda n: [Edit(_point(n, ".op\n"), ".subckt extra a\nRz a 0 1\n.ends\n")],
    ),
    ("remove .global", lambda n: [Edit(_span(n, ".global vcc\n"), "")]),
    ("edit a .control block", lambda n: [Edit(_span(n, "run"), "tran 1u 1m")]),
    ("insert into a .control block", lambda n: [Edit(_point(n, "run"), "op\n")]),
    ("cut a .control block in half", lambda n: [Edit(_span(n, ".control\nrun\n"), "")]),
    ("change an .include", lambda n: [Edit(_span(n, "models.lib"), "other.lib")]),
    ("edit inside an .if block", lambda n: [Edit(_span(n, "Rc out 0 1k"), "Rc out 0 2k")]),
]

# Whole opaque items may be added, removed or replaced (review round 1): what they contain is
# not verified (architecture §7.8), so these are allowed even though they may change the circuit.
_WHOLE_OPAQUE: list[tuple[str, Crafted]] = [
    ("remove a .control block", lambda n: [Edit(_line(n, OpaqueBlock), "")]),
    ("remove an .if block", lambda n: [Edit(_line(n, OpaqueBlock, 1), "")]),
    ("remove an .include", lambda n: [Edit(_line(n, OpaqueStatement), "")]),
    ("add an .include", lambda n: [Edit(_point(n, ".op\n"), ".include harness.cir\n")]),
    ("add a .lib", lambda n: [Edit(_point(n, ".op\n"), ".lib models.lib tt\n")]),
    (
        "add a conditional block",
        lambda n: [Edit(_point(n, ".op\n"), ".if (1)\nR9 out 0 1k\n.endif\n")],
    ),
    (
        "replace a .control block",
        lambda n: [Edit(_line(n, OpaqueBlock), ".control\ntran 1u 1m\n.endc\n")],
    ),
    (
        "remove a directive and the block after it",
        lambda n: [Edit(_line(n, OpaqueStatement).hull(_line(n, OpaqueBlock)), "")],
    ),
]


@pytest.mark.parametrize(
    "craft", [case[1] for case in _CRAFTED], ids=[case[0] for case in _CRAFTED]
)
def test_crafted_plans_that_change_topology_raise(craft: Crafted, tmp_path: Path) -> None:
    netlist = _netlist()
    with pytest.raises(TopologyViolation, match="nothing was written"):
        netlist.apply(craft(netlist))
    with pytest.raises(TopologyViolation):
        with netlist.batch() as batch:
            batch.set_dc("V1", "5")
            batch._edits.extend(craft(netlist))
    assert netlist.text == _TEXT
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "craft", [case[1] for case in _WHOLE_OPAQUE], ids=[case[0] for case in _WHOLE_OPAQUE]
)
def test_whole_opaque_items_may_be_added_or_removed(craft: Crafted) -> None:
    netlist = _netlist()
    edited = netlist.apply(craft(netlist))
    assert edited.signature() == netlist.signature()
    assert edited.text != netlist.text


Misuse = Callable[[Netlist], object]

_TOPOLOGY_ERRORS: list[tuple[str, Misuse]] = [
    ("replace an element line", lambda n: n.directives.replace(n.lines.find(Resistor), ".op")),
    ("remove an element line", lambda n: n.directives.remove(n.lines.find(Resistor))),
    ("add an element as a directive", lambda n: n.directives.add("R9 a 0 1k")),
    ("add an element as a list", lambda n: n.directives.add(["R9 a 0", "+ 1k"])),
    ("add a .subckt as a directive", lambda n: n.directives.add(".subckt s a\n.ends")),
    ("remove .global", lambda n: n.directives.remove(n.lines[1])),
    ("remove a subcircuit", lambda n: n.directives.remove(n.lines.find(SubcktDefinition))),
]


@pytest.mark.parametrize(
    "misuse", [c[1] for c in _TOPOLOGY_ERRORS], ids=[c[0] for c in _TOPOLOGY_ERRORS]
)
def test_directive_api_rejects_topology(misuse: Misuse) -> None:
    with pytest.raises(TopologyError):
        misuse(_netlist())


_EDIT_ERRORS: list[tuple[str, Misuse, str]] = [
    ("set_value on a diode", lambda n: _diode(n).set_value("D1", "1"), "no value slot"),
    ("set_model on a source", lambda n: n.set_model("V1", "dm"), "has no model"),
    (
        "unresolved model",
        lambda n: _diode(n, ".model dm d").set_model("D1", "nope"),
        "allow_external",
    ),
    (
        "wrong model type",
        lambda n: _diode(n, ".model dm d\n.model q npn").set_model("D1", "q"),
        "type `npn`",
    ),
    (
        "scope without in_definition",
        lambda n: n.set_value("Ra", "2k", scope=("div",)),
        "in_definition",
    ),
    (
        "ambiguous directives.set",
        lambda n: n.directives.add(".op").directives.set(".op"),
        "ambiguous",
    ),
    (
        "stale handle",
        lambda n: n.set_value("R2", "2k").directives.remove(n.lines[-2]),
        "does not belong",
    ),
    ("overlapping edits", lambda n: _overlap(n), "overlapping"),
    ("anchor in another netlist", lambda n: _foreign_anchor(n), "not a line of the top level"),
]


def _diode(netlist: Netlist, models: str = "") -> Netlist:
    text = netlist.text.replace(
        ".op\n", f"D1 out 0 dm\n{models}\n.op\n" if models else "D1 out 0 dm\n.op\n"
    )
    return Netlist.from_text(text, dialect=Dialect.NGSPICE)


def _overlap(netlist: Netlist) -> object:
    with netlist.batch() as batch:
        batch.set_value("R2", "2k")
        batch.set_formula("R2", "rx")
    return batch.result


def _foreign_anchor(netlist: Netlist) -> object:
    other = _netlist()
    return netlist.directives.add(".save all", Placement.before(other.lines[-1]))


@pytest.mark.parametrize(
    ("misuse", "message"),
    [c[1:] for c in _EDIT_ERRORS],
    ids=[c[0] for c in _EDIT_ERRORS],
)
def test_misuse_is_an_edit_error(misuse: Misuse, message: str) -> None:
    with pytest.raises(EditError, match=message):
        misuse(_netlist())
