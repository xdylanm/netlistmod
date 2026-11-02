"""Batches, plans, save and handles (M6 T6; decision 0007 items 1, 8 and 10)."""

from __future__ import annotations

from collections.abc import Callable
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
from tests.support.dialects import current_dialect, ltspice_only

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


_UPSERTS_TEXT = (
    "upserts\n"
    ".model dm D\n"
    ".subckt s p\n"
    ".param k=1\n"
    "Ra p 0 1k\n"
    ".ends\n"
    "V1 a 0\n"
    "R1 a 0 1k\n"
    "D1 a 0 dm\n"
    "X1 a s\n"
    ".end\n"
)

Upsert = Callable[[Batch, str], object]

# Each operation with the name of its target.
_REPEATED_UPSERTS: list[tuple[str, Upsert, str]] = [
    ("set_param", lambda b, v: b.set_param("R1", "m", v), "set_param R1 m"),
    ("set_model_param", lambda b, v: b.set_model_param("dm", "n", v), "set_model_param dm n"),
    ("set_instance_param", lambda b, v: b.set_instance_param("X1", "k", v), "set_instance_param"),
    ("params.set", lambda b, v: b.params.set("x", v), "params.set x"),
    ("set_ac", lambda b, v: b.set_ac("V1", v), "set_ac V1"),
    ("set_dc", lambda b, v: b.set_dc("V1", v), "set_dc V1"),
]


@pytest.mark.parametrize(
    ("upsert", "target"),
    [case[1:] for case in _REPEATED_UPSERTS],
    ids=[case[0] for case in _REPEATED_UPSERTS],
)
def test_a_repeated_upsert_of_a_new_target_is_an_error_on_submission(
    upsert: Upsert, target: str
) -> None:
    netlist = _netlist(_UPSERTS_TEXT)
    with pytest.raises(EditError, match=f"{target}.*already sets this target"):
        with netlist.batch() as batch:
            upsert(batch, "1")
            upsert(batch, "2")
    assert netlist.text == _UPSERTS_TEXT


def test_a_target_spelled_with_another_case_is_the_same_target() -> None:
    with pytest.raises(EditError, match="set_param r1 M.*already sets this target"):
        with _netlist(_UPSERTS_TEXT).batch() as batch:
            batch.set_param("R1", "m", "1")
            batch.set_param("r1", "M", "2")
    with pytest.raises(EditError, match="params.set X.*already sets this target"):
        with _netlist(_UPSERTS_TEXT).batch() as batch:
            batch.params.set("x", "1")
            batch.params.set("X", "2")


@pytest.mark.parametrize(
    ("first", "second", "target"),
    [
        (".tran 1u 1m", ".tran 2u 2m", "TranDirective"),
        (".op", ".op", "OpDirective"),
    ],
    ids=["tran", "op"],
)
def test_a_repeated_directive_upsert_is_an_error_on_submission(
    first: str, second: str, target: str
) -> None:
    with pytest.raises(EditError, match=f"directives.set {target}.*already sets this target"):
        with _netlist(_UPSERTS_TEXT).batch() as batch:
            batch.directives.set(first)
            batch.directives.set(second)


def test_a_repeated_include_is_an_error_on_submission() -> None:
    with pytest.raises(EditError, match="add_include `m.lib`.*already sets this target"):
        with _netlist(_UPSERTS_TEXT).batch() as batch:
            batch.add_include("m.lib")
            batch.add_include("m.lib")


@ltspice_only
def test_a_repeated_step_of_one_quantity_is_an_error_but_another_quantity_is_not() -> None:
    with pytest.raises(EditError, match="`.step` of `X`.*already sets this target"):
        with _netlist(_UPSERTS_TEXT).batch() as batch:
            batch.directives.set(".step param x 1 2 1")
            batch.directives.set(".step param X 1 3 1")
    with _netlist(_UPSERTS_TEXT).batch() as batch:
        batch.directives.set(".step param x 1 2 1")
        batch.directives.set(".step param y 1 2 1")
    assert batch.result.text.endswith(".step param x 1 2 1\n.step param y 1 2 1\n.end\n")


def test_a_repeated_upsert_of_an_existing_target_is_refused_on_submission() -> None:
    text = "t\n.param x=1\nV1 a 0 DC 1 AC 1\nR1 a 0 1k m=1\n.tran 1u 1m\n.end\n"
    for upsert in (
        lambda b, v: b.set_param("R1", "m", v),
        lambda b, v: b.params.set("x", v),
        lambda b, v: b.set_dc("V1", v),
        lambda b, v: b.set_ac("V1", v),
        lambda b, v: b.directives.set(f".tran {v}u 1m"),
    ):
        with _netlist(text).batch() as batch:
            upsert(batch, "2")
            with pytest.raises(EditError, match="already sets this target"):
                upsert(batch, "3")
            assert len(batch.plan) == 1


def test_a_refused_upsert_leaves_the_batch_usable() -> None:
    with _netlist(_UPSERTS_TEXT).batch() as batch:
        batch.set_param("R1", "m", "1")
        with pytest.raises(EditError, match="already sets this target"):
            batch.set_param("R1", "m", "2")
    assert "R1 a 0 1k m=1\n" in batch.result.text


def test_different_targets_in_one_batch_stay_valid() -> None:
    with _netlist(_UPSERTS_TEXT).batch() as batch:
        batch.set_param("R1", "m", "1")
        batch.set_param("R1", "tc1", "2")
        batch.set_model_param("dm", "n", "1")
        batch.set_model_param("dm", "rs", "2")
        batch.set_instance_param("X1", "k", "1")
        batch.set_instance_param("X1", "j", "2")
        batch.params.set("x", "1")
        batch.params.set("y", "2")
        batch.directives.set(".tran 1u 1m")
        batch.directives.set(".op")
        batch.add_include("a.lib")
        batch.add_include("b.lib")
    result = batch.result.text
    assert "R1 a 0 1k m=1 tc1=2\n" in result
    assert ".model dm D n=1 rs=2\n" in result
    assert "X1 a s k=1 j=2\n" in result
    assert ".param x=1\n.param y=2\n" in result
    assert ".tran 1u 1m\n.op\n.end\n" in result


def test_one_name_in_two_scopes_is_two_targets() -> None:
    with _netlist(_UPSERTS_TEXT).batch() as batch:
        batch.params.set("k", "1")
        batch.params.set("k", "2", scope=("s",), in_definition=True)
    assert ".param k=1\n" in batch.result.text
    assert ".param k=2\n" in batch.result.text


def test_repeated_upserts_outside_a_batch_each_see_the_last_result() -> None:
    netlist = _netlist(_UPSERTS_TEXT).set_param("R1", "m", "1").set_param("R1", "m", "2")
    assert "R1 a 0 1k m=2\n" in netlist.text


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
