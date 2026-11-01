"""Batches, plans, save and handles (M6 T6; decision 0007 items 1, 8 and 10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import (
    Batch,
    Edit,
    EditError,
    EditPlan,
    EncodingError,
    Netlist,
    OpDirective,
    Placement,
    SourceText,
    TopologyViolation,
)
from tests.support.dialects import current_dialect

_TEXT = "divider\nV1 in 0 DC 3\nR1 in out 1k\nR2 out 0 1k\n.op\n.end\n"


def _netlist(text: str = _TEXT) -> Netlist:
    return Netlist.from_text(text, dialect=current_dialect())


def test_a_batch_applies_one_plan() -> None:
    netlist = _netlist()
    with netlist.batch() as batch:
        assert isinstance(batch, Batch)
        assert batch.set_formula("R1", "Rx") is None
        batch.params.set("Rx", "2k")
        batch.directives.set(".tran 1u 1m")
        batch.set_ac("V1", "1")
        assert len(batch.plan) == 4
        assert "rx" not in batch.params  # the batch reads the netlist it was opened on
    assert batch.result.text == (
        "divider\n.param Rx=2k\nV1 in 0 DC 3 AC 1\nR1 in out {Rx}\nR2 out 0 1k\n.op\n"
        ".tran 1u 1m\n.end\n"
    )
    assert netlist.text == _TEXT


def test_a_failing_batch_changes_nothing() -> None:
    netlist = _netlist()
    with pytest.raises(EditError, match="no element `R9`"):
        with netlist.batch() as batch:
            batch.set_value("R1", "2k")
            batch.params.set("Rx", "3k")
            batch.set_value("R9", "1")
    with pytest.raises(EditError, match="has not been applied"):
        batch.result
    assert netlist.text == _TEXT


def test_two_edits_of_one_span_in_a_batch_are_an_error() -> None:
    with pytest.raises(EditError, match="overlapping edits: set_value R1"):
        with _netlist().batch() as batch:
            batch.set_value("R1", "2k")
            batch.set_value("R1", "3k")


@pytest.mark.ngspice_only
def test_a_batch_that_fails_verification_changes_nothing() -> None:
    netlist = _netlist()
    with pytest.raises(EditError, match="does not re-parse"):
        with netlist.batch() as batch:
            batch.set_value("R1", "2k")
            batch.set_value("R2", "1k 2k")
    assert netlist.text == _TEXT


def test_insertions_at_one_point_keep_their_order_in_a_batch() -> None:
    with _netlist().batch() as batch:
        batch.directives.add(".save v(in)")
        batch.directives.add(".save v(out)")
    assert batch.result.text.endswith(".op\n.save v(in)\n.save v(out)\n.end\n")


def test_a_closed_batch_takes_no_more_operations() -> None:
    with _netlist().batch() as batch:
        batch.set_value("R1", "2k")
    with pytest.raises(EditError, match="closed"):
        batch.set_value("R2", "2k")


def test_apply_takes_a_plan_or_edits_and_verifies() -> None:
    netlist = _netlist()
    value = netlist.element("R2").value
    assert value is not None
    assert (
        netlist.apply([Edit(value.span, "2k")]).element("R2").value
        == netlist.apply(EditPlan([Edit(value.span, "2k")])).element("R2").value
    )
    designator = netlist.element("R2").designator_span
    with pytest.raises(TopologyViolation):
        netlist.apply([Edit(designator, "R3")])


def test_a_stale_line_is_an_edit_error() -> None:
    netlist = _netlist()
    edited = netlist.set_value("R1", "2k")
    old = netlist.lines.find(OpDirective)
    assert old is not None
    with pytest.raises(EditError, match="does not belong to this netlist"):
        edited.directives.remove(old)
    with pytest.raises(EditError, match="does not belong to this netlist"):
        edited.directives.replace(old.item, ".op")
    with pytest.raises(EditError, match="not a line of the top level of this netlist"):
        edited.directives.add(".save v(out)", Placement.before(old))
    current = edited.lines.find(OpDirective)
    assert current is not None
    assert edited.directives.remove(current).lines.find(OpDirective) is None


def test_save_writes_the_edited_bytes_atomically(tmp_path: Path) -> None:
    path = tmp_path / "divider.cir"
    path.write_bytes(_TEXT.replace("\n", "\r\n").encode("utf-8"))
    netlist = Netlist.load(path, dialect=current_dialect())
    assert netlist.path == path
    edited = netlist.set_value("R2", "2k")
    assert edited.path == path
    edited.save()
    assert path.read_bytes() == _TEXT.replace("\n", "\r\n").replace("out 0 1k", "out 0 2k").encode()
    copy = tmp_path / "copy.cir"
    edited.save(copy)
    assert copy.read_bytes() == path.read_bytes()
    assert [entry.name for entry in tmp_path.iterdir() if entry.suffix == ".tmp"] == []


def test_an_unedited_save_writes_the_original_bytes(tmp_path: Path) -> None:
    original = "﻿title µ\r\nR1 a 0 1k   \n\tR2 a 0 2k\n.end".encode("utf-8-sig")
    path = tmp_path / "odd.cir"
    path.write_bytes(original)
    target = tmp_path / "out.cir"
    Netlist.load(path, dialect=current_dialect()).save(target)
    assert target.read_bytes() == original


def test_save_needs_a_path() -> None:
    with pytest.raises(EditError, match="needs a path"):
        _netlist().save()


def test_an_unencodable_edit_fails_before_anything_is_written(tmp_path: Path) -> None:
    path = tmp_path / "latin.cir"
    path.write_bytes("t\xe9\nR1 a 0 1k\n.end\n".encode("cp1252"))
    netlist = Netlist.load(path, dialect=current_dialect())
    assert netlist.source.encoding == "cp1252"
    edited = netlist.directives.add(".save v(a) ; 漢")
    target = tmp_path / "out.cir"
    with pytest.raises(EncodingError, match="cp1252"):
        edited.save(target)
    assert not target.exists()
    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["latin.cir"]


def test_save_re_verifies_against_the_load_baseline(tmp_path: Path) -> None:
    netlist = _netlist()
    tampered = Netlist(
        SourceText(_TEXT.replace("R2 out 0", "R2 out 1")),
        Netlist.from_text(
            _TEXT.replace("R2 out 0", "R2 out 1"), dialect=current_dialect()
        ).parse_result,
        dialect=current_dialect(),
        rkm=False,
        baseline=netlist.baseline,
    )
    target = tmp_path / "out.cir"
    with pytest.raises(TopologyViolation):
        tampered.save(target)
    assert not target.exists()


def test_the_read_only_netlist_has_no_edit_methods() -> None:
    from netlistmod.document import Netlist as ReadOnly

    read_only = ReadOnly.from_text(_TEXT, dialect=current_dialect())
    assert not hasattr(read_only, "set_value")
    assert not hasattr(read_only, "save")
