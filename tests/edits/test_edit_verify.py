"""Write-time verification (M6 T2, architecture §7.6, decision 0007 item 8)."""

from __future__ import annotations

import pytest

from netlistmod import (
    Edit,
    EditError,
    EditPlan,
    Netlist,
    NumericValue,
    ParseError,
    SlotCheck,
    Span,
    TopologySignature,
    TopologyViolation,
)
from netlistmod.edit.verify import check_outside, check_signature, check_slots
from tests.support.dialects import current_dialect


def _netlist(body: str, *, rkm: bool = False) -> Netlist:
    return Netlist.from_text(f"title\n{body}\n.end\n", dialect=current_dialect(), rkm=rkm)


def test_a_faulty_plan_that_edits_a_node_span_is_a_topology_violation() -> None:
    netlist = _netlist("R1 a b 1k\nR2 b 0 1k")
    node = netlist.element("R2").nodes[0]
    with pytest.raises(TopologyViolation) as raised:
        netlist.apply([Edit(node.span, "c", "faulty")])
    message = str(raised.value)
    assert "signature entry 1" in message
    assert "('b', '0')" in message and "('c', '0')" in message
    assert "nothing was written" in message


def test_a_case_only_change_is_caught() -> None:
    netlist = _netlist("R1 a GND 1k")
    node = netlist.element("R1").nodes[1]
    with pytest.raises(TopologyViolation, match="'GND'"):
        netlist.apply([Edit(node.span, "gnd")])


def test_added_and_removed_entries_are_named() -> None:
    netlist = _netlist("R1 a 0 1k")
    end = netlist.lines[-1].span.start
    with pytest.raises(TopologyViolation, match=r"entry 1: expected \('global'.*'R2'"):
        netlist.apply([Edit(Span(end, end), "R2 a 0 1k\n")])
    with pytest.raises(TopologyViolation, match=r"entry 0: expected \('element', \(\), 'R1'"):
        netlist.apply([Edit(netlist.lines[1].span, "")])
    shorter = TopologySignature(netlist.baseline.entries[1:])
    longer = TopologySignature((*netlist.baseline.entries, ("extra",)))
    with pytest.raises(TopologyViolation, match=r"adds topology: signature entry 2 \('extra',\)"):
        check_signature(netlist.baseline, longer)
    with pytest.raises(TopologyViolation, match="removes topology: signature entry 1"):
        check_signature(TopologySignature((*shorter.entries, ("x",))), shorter)


def test_a_parse_failure_is_an_edit_error_carrying_the_parse_error() -> None:
    netlist = _netlist("R1 a b 1k")
    value = netlist.element("R1")
    with pytest.raises(EditError, match="does not parse \\(why\\)") as raised:
        netlist.apply([Edit(value.span, "R1 a b\n", "why")])
    assert isinstance(raised.value.__cause__, ParseError)


@pytest.mark.ngspice_only
def test_rkm_text_names_the_option() -> None:
    with pytest.raises(EditError, match=r"rkm=True") as raised:
        _netlist("R1 a b 1k").set_value("R1", "2k7")
    assert isinstance(raised.value.__cause__, ParseError)
    assert _netlist("R1 a b 1k", rkm=True).set_value("R1", "2k7").element("R1").value is not None


@pytest.mark.ngspice_only
def test_the_slot_check_rejects_text_that_lands_as_more_than_the_slot() -> None:
    netlist = _netlist("R1 a b 1k")
    with pytest.raises(EditError, match="`1k 2k` does not re-parse as a value"):
        netlist.set_value("R1", "1k 2k")


def test_slot_checks_follow_shifted_positions() -> None:
    netlist = _netlist("R1 a b 1k\nR2 b 0 1k")
    first, second = netlist.element("R1").value, netlist.element("R2").value
    assert first is not None and second is not None
    check = (SlotCheck((NumericValue,), "a value"),)
    plan = EditPlan([Edit(first.span, "10k", "a", check), Edit(second.span, "220", "b", check)])
    edited = netlist.apply(plan)
    assert edited.text == "title\nR1 a b 10k\nR2 b 0 220\n.end\n"
    bad = EditPlan([Edit(first.span, "10k", "a", (SlotCheck((NumericValue,), "x", 0, 2),))])
    with pytest.raises(EditError, match="a: `10` does not re-parse as x"):
        netlist.apply(bad)


def test_check_outside_detects_a_change_between_edits() -> None:
    plan = EditPlan([Edit(Span(1, 2), "X")])
    check_outside("abc", "aXc", plan)
    with pytest.raises(TopologyViolation, match="outside the edited spans"):
        check_outside("abc", "aXd", plan)
    with pytest.raises(TopologyViolation, match="unexpected length"):
        check_outside("abc", "aXcc", plan)


def test_check_signature_and_slots_accept_matching_input() -> None:
    netlist = _netlist("R1 a b 1k")
    check_signature(netlist.baseline, netlist.signature())
    check_slots(netlist.text, netlist.parse_result, EditPlan())


def test_verify_and_an_empty_plan() -> None:
    netlist = _netlist("R1 a b 1k")
    netlist.verify()
    assert netlist.apply(EditPlan()) is netlist
    assert netlist.apply([]) is netlist


def test_derived_netlists_keep_the_load_baseline() -> None:
    netlist = _netlist("R1 a b 1k")
    edited = netlist.set_value("R1", "2k").set_value("R1", "3k")
    assert edited.baseline == netlist.baseline
    assert edited.baseline is netlist.baseline
