"""`set_stimulus`, `set_stimulus_arg` and `remove_stimulus` (M12 T6; decision 0013)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from netlistmod import Dialect, EditError, Netlist, ParseError, TopologyViolation
from tests.support.dialects import current_dialect


def _netlist(line: str) -> Netlist:
    return Netlist.from_text(f"t\n{line}\nR1 a 0 1k\n.end\n", dialect=current_dialect())


def _line(netlist: Netlist) -> str:
    return netlist.source.text.split("\n", 1)[1].rsplit("\nR1 a 0 1k", 1)[0]


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("V1 a 0", "V1 a 0 PULSE(0 1)"),
        ("V1 a 0 1", "V1 a 0 1 PULSE(0 1)"),
        ("V1 a 0 DC 1", "V1 a 0 DC 1 PULSE(0 1)"),
        ("V1 a 0 AC 1", "V1 a 0 AC 1 PULSE(0 1)"),
        ("V1 a 0 AC 1 45", "V1 a 0 AC 1 45 PULSE(0 1)"),
        ("V1 a 0 DC 1 AC 1 ; c", "V1 a 0 DC 1 AC 1 PULSE(0 1) ; c"),
        ("V1 a 0 SIN(0 1 1k)", "V1 a 0 PULSE(0 1)"),
        ("V1 a 0 DC 1 SIN(0 1 1k) AC 1", "V1 a 0 DC 1 PULSE(0 1) AC 1"),
        ("V1 a 0 SIN(0 1\n+ 1k) AC 1", "V1 a 0 PULSE(0 1) AC 1"),
    ],
)
def test_set_stimulus_positions(before: str, after: str) -> None:
    assert _line(_netlist(before).set_stimulus("V1", "PULSE(0 1)")) == after


def test_set_stimulus_leaves_dc_and_ac_alone() -> None:
    edited = _netlist("V1 a 0 DC 2 AC 3 45 SIN(0 1)").set_stimulus("V1", "EXP(0 1)")
    source = edited.lines.find_all(type(edited.lines[1].item))[0].item
    assert source.dc.text == "2"
    assert source.ac.magnitude.text == "3"
    assert source.ac.phase.text == "45"


def test_set_dc_and_set_ac_work_beside_a_function() -> None:
    netlist = _netlist("V1 a 0 SIN(0 1)")
    assert _line(netlist.set_dc("V1", "2")) == "V1 a 0 DC 2 SIN(0 1)"
    assert _line(netlist.set_ac("V1", "3")) == "V1 a 0 AC 3 SIN(0 1)"
    assert _line(_netlist("V1 a 0 SIN(0 1) DC 2").set_value("V1", "5")) == "V1 a 0 SIN(0 1) DC 5"
    assert _line(_netlist("V1 a 0 SIN(0 1) AC 2").set_ac("V1", "5")) == "V1 a 0 SIN(0 1) AC 5"


def test_a_function_changes_no_topology() -> None:
    netlist = _netlist("V1 a 0 DC 1")
    assert netlist.set_stimulus("V1", "PULSE(0 1)").signature() == netlist.signature()


@pytest.mark.parametrize(
    "text",
    [
        "SIN(0 1) AC 1",
        "SIN(0 1)\nR2 a 0 1k",
        "SIN(0 1) ; comment",
        "3",
        "",
        "SIN(0 1) PULSE(0 1)",
    ],
)
def test_set_stimulus_takes_one_function_only(text: str) -> None:
    with pytest.raises(
        (EditError, ParseError, TopologyViolation),
        match=r"does not re-parse|Parse error|one line",
    ):
        _netlist("V1 a 0 SIN(0 1)").set_stimulus("V1", text)


@pytest.mark.parametrize(
    ("key", "value", "after"),
    [
        (0, "9", "V1 a 0 PULSE(9 1 1u)"),
        (2, "{x}", "V1 a 0 PULSE(0 1 {x})"),
        (3, "2u", "V1 a 0 PULSE(0 1 1u 2u)"),
    ],
)
def test_set_stimulus_arg_by_position(key: int, value: str, after: str) -> None:
    assert _line(_netlist("V1 a 0 PULSE(0 1 1u)").set_stimulus_arg("V1", key, value)) == after


def test_an_appended_argument_after_one_argument_uses_a_blank() -> None:
    assert _line(_netlist("V1 a 0 PULSE(0)").set_stimulus_arg("V1", 1, "1")) == "V1 a 0 PULSE(0 1)"


def test_an_appended_argument_matches_a_comma_list() -> None:
    edited = _netlist("V1 a 0 PULSE(0, 1)").set_stimulus_arg("V1", 2, "1u")
    assert _line(edited) == "V1 a 0 PULSE(0, 1, 1u)"


@pytest.mark.parametrize("key", [4, 99, -1])
def test_a_position_past_the_end_is_refused(key: int) -> None:
    with pytest.raises(EditError, match="only an existing position or the next one"):
        _netlist("V1 a 0 PULSE(0 1 1u)").set_stimulus_arg("V1", key, "9")


def test_an_argument_must_be_a_value() -> None:
    with pytest.raises(EditError, match="does not re-parse"):
        _netlist("V1 a 0 PULSE(0 1)").set_stimulus_arg("V1", 0, "9 8")


def test_no_stimulus_to_edit() -> None:
    netlist = _netlist("V1 a 0 DC 1")
    with pytest.raises(EditError, match="use set_stimulus"):
        netlist.set_stimulus_arg("V1", 0, "1")
    with pytest.raises(EditError, match="use set_stimulus"):
        netlist.remove_stimulus("V1")


def test_not_a_source() -> None:
    netlist = _netlist("V1 a 0 DC 1")
    for call in (
        lambda: netlist.set_stimulus("R1", "SIN(0 1)"),
        lambda: netlist.set_stimulus_arg("R1", 0, "1"),
        lambda: netlist.remove_stimulus("R1"),
    ):
        with pytest.raises(EditError, match="not an independent source"):
            call()


def test_no_such_designator() -> None:
    with pytest.raises(EditError, match="no element `V9`"):
        _netlist("V1 a 0 SIN(0 1)").set_stimulus("V9", "SIN(0 1)")


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("V1 a 0 SIN(0 1)", "V1 a 0"),
        ("V1 a 0 DC 1 SIN(0 1) AC 1", "V1 a 0 DC 1 AC 1"),
        ("V1 a 0 SIN(0 1) ; c", "V1 a 0 ; c"),
    ],
)
def test_remove_stimulus(before: str, after: str) -> None:
    assert _line(_netlist(before).remove_stimulus("V1")) == after


def test_a_subcircuit_definition_needs_in_definition() -> None:
    text = "t\nX1 a s\n.subckt s p\nV2 p 0 SIN(0 1)\n.ends\n.end\n"
    netlist = Netlist.from_text(text, dialect=current_dialect())
    with pytest.raises(EditError, match="in_definition"):
        netlist.set_stimulus("V2", "EXP(0 1)", scope=("s",))
    edited = netlist.set_stimulus("V2", "EXP(0 1)", scope=("s",), in_definition=True)
    assert "V2 p 0 EXP(0 1)\n" in edited.source.text


def test_a_batch_takes_one_upsert_of_each() -> None:
    netlist = _netlist("V1 a 0")
    with pytest.raises(EditError, match="set_stimulus V1"), netlist.batch() as batch:
        batch.set_stimulus("V1", "SIN(0 1)")
        batch.set_stimulus("V1", "EXP(0 1)")
    other = _netlist("V1 a 0 PULSE(0 1)")
    with pytest.raises(EditError, match="set_stimulus_arg V1"), other.batch() as batch:
        batch.set_stimulus_arg("V1", 0, "1")
        batch.set_stimulus_arg("V1", 0, "2")


def test_a_batch_edits_different_arguments() -> None:
    netlist = _netlist("V1 a 0 PULSE(0 1)")
    with netlist.batch() as batch:
        batch.set_stimulus_arg("V1", 0, "5")
        batch.set_stimulus_arg("V1", 1, "6")
    assert _line(batch.result) == "V1 a 0 PULSE(5 6)"


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("V1 a 0 DC 1\n+ PULSE(0 1 1u)", "V1 a 0 DC 1"),
        ("V1 a 0\n+ SIN(0 1)\n+ AC 1", "V1 a 0\n+ AC 1"),
        ("V1 a 0 DC 1 ; c\n+ PULSE(0 1)", "V1 a 0 DC 1 ; c"),
        ("V1 a 0 ; c\n+ SIN(0 1) AC 1", "V1 a 0 ; c\n+ AC 1"),
        ("V1 a 0 ; c\n+ SIN(0 1) ; d", "V1 a 0 ; c\n+ ; d"),
        ("V1 a 0\n+ SIN(0 1) ; d", "V1 a 0 ; d"),
    ],
)
def test_remove_stimulus_takes_its_separator(before: str, after: str) -> None:
    edited = _netlist(before).remove_stimulus("V1")
    assert _line(edited) == after
    assert edited.lines[1].item.ac is not None or "AC" not in before


@pytest.mark.parametrize("text", ["PULSE(0\n+ 1)", "PULSE(0\r\n+ 1)", "PULSE(0 1)\n"])
def test_set_stimulus_refuses_a_line_break(text: str) -> None:
    with pytest.raises(EditError, match="one line"):
        _netlist("V1 a 0 SIN(0 1)").set_stimulus("V1", text)


def test_a_crlf_file_stays_crlf() -> None:
    netlist = Netlist.from_text("t\r\nV1 a 0 SIN(0 1)\r\n.end\r\n", dialect=current_dialect())
    assert b"\n" not in netlist.set_stimulus("V1", "EXP(0 1)").to_bytes().replace(b"\r\n", b"")


@given(st.integers(min_value=0, max_value=2), st.sampled_from(["5", "1k", "{x}", "'x*2'", "-1e-3"]))
def test_an_argument_edit_changes_only_its_slot(position: int, value: str) -> None:
    for dialect in (Dialect.NGSPICE, Dialect.LTSPICE):
        text = "t\nV1 a 0 PULSE(0 1 2) AC 1\nR1 a 0 1k\n.end\n"
        netlist = Netlist.from_text(text, dialect=dialect)
        edited = netlist.set_stimulus_arg("V1", position, value)
        args = ["0", "1", "2"]
        args[position] = value
        assert edited.source.text == text.replace("0 1 2", " ".join(args))
        assert edited.signature() == netlist.signature()


@pytest.mark.ngspice_only
class TestNgspice:
    def test_named_parameters(self) -> None:
        netlist = _netlist("V1 a 0 PWL(0 0 1 1) r=0")
        assert _line(netlist.set_stimulus_arg("V1", "R", "1")) == "V1 a 0 PWL(0 0 1 1) r=1"
        assert _line(netlist.set_stimulus_arg("V1", "td", "2")) == "V1 a 0 PWL(0 0 1 1) r=0 td=2"

    def test_a_named_parameter_the_function_does_not_take_is_refused(self) -> None:
        with pytest.raises(EditError, match="applies only to `PWL`"):
            _netlist("V1 a 0 PULSE(0 1)").set_stimulus_arg("V1", "td", "2")

    def test_set_stimulus_replaces_named_parameters_too(self) -> None:
        edited = _netlist("V1 a 0 PWL(0 0 1 1) r=0 td=1 AC 1").set_stimulus("V1", "SIN(0 1)")
        assert _line(edited) == "V1 a 0 SIN(0 1) AC 1"

    def test_external_has_no_list_to_add_to(self) -> None:
        with pytest.raises(EditError, match="no argument list"):
            _netlist("V1 a 0 dc 0 external").set_stimulus_arg("V1", 0, "1")

    def test_distortion_inputs(self) -> None:
        netlist = _netlist("V1 a 0 SIN(0 1) DISTOF1 0.1 2 DISTOF2 0.2")
        assert (
            _line(netlist.set_stimulus_arg("V1", 1, "9", function="distof1"))
            == "V1 a 0 SIN(0 1) DISTOF1 0.1 9 DISTOF2 0.2"
        )
        assert (
            _line(netlist.set_stimulus("V1", "DISTOF2 0.5"))
            == "V1 a 0 SIN(0 1) DISTOF1 0.1 2 DISTOF2 0.5"
        )
        assert (
            _line(netlist.remove_stimulus("V1", function="DISTOF1"))
            == "V1 a 0 SIN(0 1) DISTOF2 0.2"
        )
        assert _line(netlist.remove_stimulus("V1")) == "V1 a 0 DISTOF1 0.1 2 DISTOF2 0.2"

    def test_adding_distortion_inputs_keeps_their_order(self) -> None:
        assert (
            _line(_netlist("V1 a 0 DC 1 SIN(0 1)").set_stimulus("V1", "DISTOF1 0.1"))
            == "V1 a 0 DC 1 SIN(0 1) DISTOF1 0.1"
        )
        assert (
            _line(_netlist("V1 a 0 DISTOF2 0.2").set_stimulus("V1", "DISTOF1 0.1"))
            == "V1 a 0 DISTOF1 0.1 DISTOF2 0.2"
        )
        assert (
            _line(_netlist("V1 a 0 DISTOF1 0.1").set_stimulus("V1", "DISTOF2 0.2"))
            == "V1 a 0 DISTOF1 0.1 DISTOF2 0.2"
        )

    @pytest.mark.parametrize(
        ("before", "after"),
        [
            ("V1 a 0 DC 1, SIN(0 1)", "V1 a 0 DC 1"),
            ("V1 a 0, SIN(0 1)", "V1 a 0"),
            ("V1 a 0 DC 1 \\\\\nSIN(0 1)", "V1 a 0 DC 1"),
            ("V1 a 0 DC 1, SIN(0 1) AC 1", "V1 a 0 DC 1 AC 1"),
        ],
    )
    def test_remove_stimulus_takes_a_comma_or_a_backslash(self, before: str, after: str) -> None:
        assert _line(_netlist(before).remove_stimulus("V1")) == after

    def test_remove_a_distortion_input_takes_its_separator(self) -> None:
        netlist = _netlist("V1 a 0 DC 1, DISTOF1 0.1\n+ DISTOF2 0.2")
        assert _line(netlist.remove_stimulus("V1", function="DISTOF1")) == (
            "V1 a 0 DC 1\n+ DISTOF2 0.2"
        )
        assert _line(netlist.remove_stimulus("V1", function="DISTOF2")) == (
            "V1 a 0 DC 1, DISTOF1 0.1"
        )

    def test_a_distortion_input_it_does_not_have(self) -> None:
        with pytest.raises(EditError, match="no `DISTOF2`"):
            _netlist("V1 a 0 DISTOF1").set_stimulus_arg("V1", 0, "1", function="DISTOF2")

    def test_rf_port_parameters_use_set_param(self) -> None:
        netlist = _netlist("V1 a 0 dc 0 ac 1 portnum 1")
        assert _line(netlist.set_param("V1", "portnum", "2")) == "V1 a 0 dc 0 ac 1 portnum 2"
        assert _line(netlist.set_param("V1", "z0", "75")) == "V1 a 0 dc 0 ac 1 portnum 1 z0=75"

    def test_other_parameters_on_a_source_stay_refused(self) -> None:
        with pytest.raises(EditError, match="takes no parameters"):
            _netlist("V1 a 0 dc 0").set_param("V1", "rser", "2")


@pytest.mark.ltspice_only
class TestLtspice:
    def test_a_scale_factor_before_a_file_is_edited_by_name(self) -> None:
        netlist = _netlist("V1 a 0 PWL VALUE_SCALE_FACTOR=3 FILE=x.txt")
        assert _line(netlist.set_stimulus_arg("V1", "value_scale_factor", "4")) == (
            "V1 a 0 PWL VALUE_SCALE_FACTOR=4 FILE=x.txt"
        )

    def test_a_trigger_is_edited_or_added_by_name(self) -> None:
        netlist = _netlist("V1 a 0 PULSE(0 1) Trigger=V(a)>0")
        edited = netlist.set_stimulus_arg("V1", "trigger", "V(a)>1")
        assert _line(edited) == "V1 a 0 PULSE(0 1) Trigger=V(a)>1"
        added = _netlist("V1 a 0 PULSE(0 1)").set_stimulus_arg("V1", "Trigger", "V(a)>1")
        assert _line(added) == "V1 a 0 PULSE(0 1) Trigger=V(a)>1"

    def test_set_stimulus_goes_before_rser(self) -> None:
        assert (
            _line(_netlist("V1 a 0 1 Rser=1").set_stimulus("V1", "SIN(0 1)"))
            == "V1 a 0 1 SIN(0 1) Rser=1"
        )

    def test_set_stimulus_keeps_line_parameters(self) -> None:
        edited = _netlist("V1 a 0 SINE(0 1 60k) Rser=1").set_stimulus("V1", "PULSE(0 1)")
        assert _line(edited) == "V1 a 0 PULSE(0 1) Rser=1"

    def test_an_i_line_needs_a_value_after_removal(self) -> None:
        with pytest.raises(EditError, match="use set_dc first"):
            _netlist("I1 a 0 PULSE(0 1)").remove_stimulus("I1")
        assert _line(_netlist("I1 a 0 1 PULSE(0 1)").remove_stimulus("I1")) == "I1 a 0 1"

    def test_a_file_path_and_channel(self) -> None:
        netlist = _netlist("V1 a 0 wavefile=x.wav chan=0")
        assert _line(netlist.set_stimulus_arg("V1", "chan", "1")) == "V1 a 0 wavefile=x.wav chan=1"
        assert _line(netlist.set_stimulus_arg("V1", "wavefile", "y.wav")) == (
            "V1 a 0 wavefile=y.wav chan=0"
        )

    def test_a_table_and_a_repeat_count(self) -> None:
        table = _netlist("I1 a 0 tbl=(0 0, 1 1)").set_stimulus_arg("I1", 3, "2")
        assert _line(table) == "I1 a 0 tbl=(0 0, 1 2)"
        repeat = _netlist("V1 a 0 PWL REPEAT FOR 2 (0 0 1u 0) ENDREPEAT")
        assert _line(repeat.set_stimulus_arg("V1", "for", "3")) == (
            "V1 a 0 PWL REPEAT FOR 3 (0 0 1u 0) ENDREPEAT"
        )
