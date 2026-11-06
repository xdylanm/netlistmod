"""Edits of E, F, G, H, S and W, and the exit's negative test (M14 T8, decision 0015 item 10)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from netlistmod import Edit, EditError, Netlist, TopologyViolation
from tests.support.dialects import current_dialect

_CIRCUIT = (
    "t\nV1 in 0 2\nVs in a 0\nV2 a b 0\nR1 b 0 1k\n"
    "E1 eo 0 a 0 2\nG1 0 go a 0 1m\nF1 0 fo Vs 2\nH1 ho 0 Vs 1k\n"
    ".model sm SW\n.model s2 SW\n.model cm CSW\n"
    "S1 so 0 a 0 sm off ; trip\nW1 wo 0 Vs cm\n.op\n.end\n"
)


def _netlist(text: str = _CIRCUIT) -> Netlist:
    return Netlist.from_text(text, dialect=current_dialect())


def _line(netlist: Netlist, designator: str) -> str:
    return next(line for line in netlist.text.splitlines() if line.startswith(designator + " "))


@pytest.mark.parametrize("designator", ["E1", "G1", "F1", "H1"])
def test_the_gain_is_the_value(designator: str) -> None:
    edited = _netlist().set_value(designator, "3")
    assert _line(edited, designator).split()[-1] == "3"
    assert _line(edited.set_formula(designator, "k*2"), designator).split()[-1] == "{k*2}"


@pytest.mark.ngspice_only
@pytest.mark.parametrize("designator", ["G1", "F1"])
def test_an_ngspice_f_or_g_takes_m(designator: str) -> None:
    assert _line(_netlist().set_param(designator, "m", "2"), designator).endswith(" m=2")


@pytest.mark.parametrize("designator", ["E1", "H1", "S1", "W1"])
def test_other_letters_take_no_parameter(designator: str) -> None:
    with pytest.raises(EditError, match=f"`{designator}` takes no parameter `m`"):
        _netlist().set_param(designator, "m", "2")


@pytest.mark.ltspice_only
def test_ltspice_takes_no_m_on_f_or_g() -> None:
    with pytest.raises(EditError, match="`G1` takes no parameter `m`$"):
        _netlist().set_param("G1", "m", "2")


def test_set_model_on_a_switch_checks_the_type() -> None:
    assert _line(_netlist().set_model("S1", "s2"), "S1") == "S1 so 0 a 0 s2 off ; trip"
    with pytest.raises(EditError, match="takes a model of type `CSW`"):
        _netlist().set_model("W1", "sm")


@pytest.mark.parametrize(
    ("designator", "state", "line"),
    [
        ("S1", "on", "S1 so 0 a 0 sm on ; trip"),
        ("S1", None, "S1 so 0 a 0 sm ; trip"),
        ("W1", "OFF", "W1 wo 0 Vs cm OFF"),
        ("W1", None, "W1 wo 0 Vs cm"),
    ],
)
def test_set_switch_state(designator: str, state: str | None, line: str) -> None:
    assert _line(_netlist().set_switch_state(designator, state), designator) == line


@pytest.mark.ltspice_only
def test_a_state_with_a_value_is_replaced_whole() -> None:
    netlist = _netlist(_CIRCUIT.replace("sm off ;", "sm off=1 ;"))
    assert _line(netlist.set_switch_state("S1", "on"), "S1") == "S1 so 0 a 0 sm on ; trip"


def test_set_switch_state_refuses_other_lines_and_states() -> None:
    with pytest.raises(EditError, match="has no switch state"):
        _netlist().set_switch_state("E1", "on")
    with pytest.raises(EditError, match="not 'closed'"):
        _netlist().set_switch_state("S1", "closed")


def test_a_second_state_edit_in_a_batch_is_refused() -> None:
    netlist = _netlist()
    with pytest.raises(EditError, match="set_switch_state S1"):
        with netlist.batch() as batch:
            batch.set_switch_state("S1", "on")
            batch.set_switch_state("S1", "off")


# The exit: changing any control node or controlling source is a TopologyViolation.
@pytest.mark.parametrize(
    ("designator", "field", "text"),
    [
        ("E1", 4, "b"),
        ("G1", 3, "b"),
        ("S1", 3, "b"),
        ("E1", 3, "in"),
        ("F1", 3, "V2"),
        ("H1", 3, "V2"),
        ("W1", 3, "V2"),
    ],
)
def test_a_changed_control_is_a_topology_violation(designator: str, field: int, text: str) -> None:
    netlist = _netlist()
    line = next(
        line for line in netlist.lines if getattr(line.item, "designator", "") == designator
    )
    item = line.item
    controls = getattr(item, "control_nodes", None)
    span = controls[field - 3].span if controls else item.control.span
    with pytest.raises(TopologyViolation):
        netlist.apply([Edit(span, text, f"rewire {designator}")])


_EDITS = st.sampled_from(
    [
        lambda n: n.set_value("E1", "4"),
        lambda n: n.set_formula("G1", "gm"),
        lambda n: n.set_value("F1", "5"),
        lambda n: n.set_value("H1", "2k"),
        lambda n: n.set_model("S1", "s2"),
        lambda n: n.set_switch_state("S1", "on"),
        lambda n: n.set_switch_state("S1", None),
        lambda n: n.set_switch_state("W1", "off"),
        lambda n: n.set_switch_state("W1", None),
    ]
)


@settings(max_examples=60, deadline=None)
@given(st.lists(_EDITS, min_size=1, max_size=6))
def test_no_sequence_of_edits_changes_the_signature(
    steps: list[Callable[[Netlist], Netlist]],
) -> None:
    netlist = _netlist()
    signature = netlist.signature()
    for step in steps:
        edited = step(netlist)
        assert edited.signature() == signature
        assert step(edited).to_bytes() == edited.to_bytes()
        netlist = edited
