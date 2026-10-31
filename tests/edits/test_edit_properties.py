"""Edit invariants over generated netlists (M6 T9, T5 tier, Hypothesis).

The circuits and formatting styles are the M5 generators of ``tests/document/test_topology.py``
(blanks, tabs, comments, ``+`` and ``\\\\`` continuations, directives, a subcircuit).
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from netlistmod import Dialect, EditPlan, Netlist, Placement, apply_edits
from netlistmod.edit import operations
from netlistmod.edit.verify import check_outside
from tests.document.test_topology import _STYLES, _Circuit, _circuits, _render, _Style

Operation = Callable[[Netlist], Netlist]
_VALUES = ["2k", "{rx*2}", "'rx+1'", "4.7e3", "1"]


def _load(circuit: _Circuit, style: _Style) -> Netlist:
    return Netlist.from_text(_render(circuit, style), dialect=Dialect.NGSPICE)


@st.composite
def _operations(draw: st.DrawFn, circuit: _Circuit) -> tuple[str, Operation]:
    """One allowed operation on ``circuit`` (described for failure messages)."""
    choices: list[tuple[str, Operation]] = []
    value = draw(st.sampled_from(_VALUES))
    for element in circuit.top:
        name = element.designator
        if element.letter == "V":
            choices.append((f"set_dc {name}", lambda n, d=name: n.set_dc(d, "2")))
            choices.append((f"set_ac {name}", lambda n, d=name: n.set_ac(d, "1", "90")))
        else:
            safe = value if element.letter != "C" or value[0].isdigit() else "1p"
            choices.append((f"set_value {name}", lambda n, d=name, v=safe: n.set_value(d, v)))
            choices.append((f"set_param {name}", lambda n, d=name: n.set_param(d, "tc1", "1m")))
    for element in circuit.local:
        if element.letter != "V":
            name = element.designator
            choices.append(
                (
                    f"set_value {name} in sub",
                    lambda n, d=name: n.set_value(d, "3k", scope=("sub",), in_definition=True),
                )
            )
    for index in range(len(circuit.instances)):
        choices.append((f"X{index} k", lambda n, d=f"X{index}": n.set_instance_param(d, "k", "2")))
    choices += [
        ("params.set rx", lambda n: n.params.set("rx", "5k")),
        ("params.set ry", lambda n: n.params.set("ry", "{rx}")),
        (
            "params.set sub",
            lambda n: n.params.set("k", "1", scope=("sub",), in_definition=True),
        ),
        ("directives.set .tran", lambda n: n.directives.set(".tran 1u 1m")),
        ("directives.set .temp", lambda n: n.directives.set(".temp 50")),
    ]
    return draw(st.sampled_from(choices))


@st.composite
def _cases(draw: st.DrawFn) -> tuple[_Circuit, _Style, list[tuple[str, Operation]]]:
    circuit = draw(_circuits())
    style = draw(_STYLES)
    steps = draw(st.lists(_operations(circuit), min_size=1, max_size=5))
    return circuit, style, steps


@settings(max_examples=120, deadline=None)
@given(_cases())
def test_any_sequence_of_allowed_edits_preserves_the_signature(
    case: tuple[_Circuit, _Style, list[tuple[str, Operation]]],
) -> None:
    circuit, style, steps = case
    netlist = _load(circuit, style)
    for _, operation in steps:
        netlist = operation(netlist)
        assert netlist.signature() == netlist.baseline
    fresh = Netlist.from_text(netlist.text, dialect=Dialect.NGSPICE)
    assert fresh.signature() == _load(circuit, style).signature()


@settings(max_examples=120, deadline=None)
@given(_cases())
def test_each_operation_is_idempotent(
    case: tuple[_Circuit, _Style, list[tuple[str, Operation]]],
) -> None:
    circuit, style, steps = case
    netlist = _load(circuit, style)
    for description, operation in steps:
        once = operation(netlist)
        assert operation(once).text == once.text, description
        netlist = once


@settings(max_examples=60, deadline=None)
@given(_circuits(), _STYLES)
def test_an_empty_plan_returns_identical_bytes(circuit: _Circuit, style: _Style) -> None:
    netlist = _load(circuit, style)
    assert netlist.apply(EditPlan()).to_bytes() == netlist.to_bytes()
    with netlist.batch():
        pass


@settings(max_examples=120, deadline=None)
@given(_circuits(), _STYLES, st.sampled_from(_VALUES))
def test_text_outside_the_edited_spans_is_unchanged(
    circuit: _Circuit, style: _Style, value: str
) -> None:
    netlist = _load(circuit, style)
    element = next(e for e in circuit.top)
    edits = (
        operations.set_dc(netlist, element.designator, "5")
        if element.letter == "V"
        else operations.set_param(netlist, element.designator, "tc2", "0")
    )
    edits += operations.set_param_statement(netlist, "rnew", value)
    edits += operations.add_directive(netlist, ".save all", Placement.AFTER_TITLE)
    plan = EditPlan(edits)
    edited = netlist.apply(plan)
    assert edited.text == apply_edits(netlist.text, plan)
    check_outside(netlist.text, edited.text, plan)
    first = min(edit.span.start for edit in plan)
    last = max(edit.span.end for edit in plan)
    assert edited.text[:first] == netlist.text[:first]
    assert edited.text.endswith(netlist.text[last:])


@settings(max_examples=60, deadline=None)
@given(_cases())
def test_save_then_load_gives_the_same_items(
    case: tuple[_Circuit, _Style, list[tuple[str, Operation]]],
) -> None:
    circuit, style, steps = case
    netlist = _load(circuit, style)
    for _, operation in steps:
        netlist = operation(netlist)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "edited.cir"
        netlist.save(path)
        loaded = Netlist.load(path, dialect=Dialect.NGSPICE)
    assert loaded.parse_result == netlist.parse_result
    assert loaded.to_bytes() == netlist.to_bytes()
    assert loaded.signature() == netlist.baseline
