"""xyce `.TRAN`, `.AC`, `.DC`, `.OP` and `.STEP` (X-M2 B2; decision 0028 items 3 and 4;
xm2-tasks 5.1 points 7 to 17)."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    AcDirective,
    DcDirective,
    DcSweep,
    End,
    Flag,
    Formula,
    Identifier,
    NumericValue,
    OpDirective,
    ParseError,
    SourceText,
    Span,
    StepDirective,
    Title,
    TranDirective,
    parse,
)
from netlistmod.dialects import _XYCE


def _parse(text: str) -> Any:
    return parse(SourceText(text), _XYCE)


def _item(line: str) -> Any:
    """The one statement of a netlist holding `line`; the items tile the source."""
    text = f"t\n{line}\n.END\n"
    items = _parse(text).items
    position = 0
    for item in items:
        assert item.span.start == position
        position = item.span.end
    assert position == len(text)
    assert isinstance(items[0], Title) and isinstance(items[-1], End)
    (statement,) = items[1:-1]
    assert text[statement.span.start : statement.span.end].rstrip("\n") == line
    return statement


def _error(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        _parse(f"t\n{line}\n.END\n")
    return captured.value


def _at(line: str, piece: str, start: int = 0) -> Span:
    """The span of `piece` in the netlist `_item` builds (the line starts at offset 2)."""
    offset = line.index(piece, start)
    return Span(2 + offset, 2 + offset + len(piece))


def _number(line: str, text: str, start: int = 0) -> NumericValue:
    return NumericValue(text, _at(line, text, start))


# .TRAN


@pytest.mark.parametrize(
    ("line", "fields"),
    [
        (".tran 1n 1u", ["1n", "1u", None, None]),
        (".TRAN 1ns 10us 0 1ns", ["1ns", "10us", "0", "1ns"]),
        (".tran 1n 1u 100n", ["1n", "1u", "100n", None]),
    ],
)
def test_tran_takes_two_to_four_numbers(line: str, fields: list[str | None]) -> None:
    tran = _item(line)
    assert isinstance(tran, TranDirective)
    assert tran.keyword == line.split()[0]
    found = [tran.tstep, tran.tstop, tran.tstart, tran.tmax]
    assert [value.text if value is not None else None for value in found] == fields
    assert (tran.uic, tran.noop, tran.schedule, tran.modifiers) == (None, None, None, ())
    assert tran.tstop.span == _at(line, fields[1] or "", 7)


def test_tran_values_are_device_numbers_or_delimited_expressions() -> None:
    line = ".tran {tstep} 'tstop*2' 10meghz 1kohm"
    tran = _item(line)
    assert tran.tstep == Formula("tstep", "{", _at(line, "{tstep}"))
    assert tran.tstop == Formula("tstop*2", "'", _at(line, "'tstop*2'"))
    assert tran.tstart == _number(line, "10meghz")
    assert tran.tmax == _number(line, "1kohm")


@pytest.mark.parametrize("flags", ["NOOP", "uic", "noop UIC", "UIC NoOp"])
def test_tran_takes_noop_and_uic_after_the_numbers(flags: str) -> None:
    line = f".tran 1n 1u {flags}"
    tran = _item(line)
    written = {word.lower(): word for word in flags.split()}
    for name in ("noop", "uic"):
        flag = getattr(tran, name)
        if name in written:
            assert flag == Flag(written[name], _at(line, written[name], 11))
        else:
            assert flag is None


@pytest.mark.parametrize(
    ("schedule", "delimiter"),
    [
        ("{schedule(0.5e-3, 0, 1.0e-3, 1.0e-6)}", "{"),
        ("{ SCHEDULE( 0, 0 ) }", "{"),
        ("{schedule (0, 0)}", "{"),
        ("'Schedule(0, 1n)'", "'"),
    ],
)
def test_tran_takes_a_schedule_last(schedule: str, delimiter: str) -> None:
    line = f".tran 0 2m {schedule}"
    tran = _item(line)
    assert tran.schedule == Formula(schedule[1:-1], delimiter, _at(line, schedule))
    assert tran.tstart is None


def test_tran_takes_the_manuals_whole_form() -> None:
    # tstart and tmax with the schedule, as the manual writes it (point 9, decided (a)); Xyce 7.10
    # stops on a schedule after tstart, a discrepancies.md row.
    line = ".tran 1n 1u 0 10n uic NOOP {schedule(0, 1n)}"
    tran = _item(line)
    assert [tran.tstart.text, tran.tmax.text] == ["0", "10n"]
    assert tran.uic == Flag("uic", _at(line, "uic"))
    assert tran.noop == Flag("NOOP", _at(line, "NOOP"))
    assert tran.schedule is not None and tran.schedule.text == "schedule(0, 1n)"


def test_tran_continues_across_plus_comment_and_indented_lines() -> None:
    text = "t\n.tran 1n ; first\n* between\n  indented\n+ 1u\n+ noop\n.END\n"
    (tran,) = _parse(text).items[1:-1]
    assert isinstance(tran, TranDirective)
    assert tran.tstop.text == "1u" and tran.noop is not None
    assert [text[c.start : c.end] for c in tran.trailing_comments] == [
        "; first",
        "* between",
        "  indented",
    ]


@pytest.mark.parametrize(
    "line",
    [
        ".tran",
        ".tran 1n",
        ".tran 1n 1u 0 10n 1n",
        ".tran 1n,1u",
        ".tran 1n 1u startup",
        ".tran 1n 1u uic 0",
        ".tran 1n uic 1u",
        ".tran 1n 1u {schedule(0, 1n)} uic",
        ".tran 1n 1u {schedule(0, 1n)} {schedule(0, 2n)}",
        ".tran 1j 1u",
        ".tran 1n 1u 0 10n NOOP UIC {schedule(0)} extra",
    ],
)
def test_malformed_tran_is_rejected(line: str) -> None:
    assert _error(line).line == 2


@pytest.mark.parametrize("flags", ["uic UIC", "noop noop", "NOOP uic noop"])
def test_a_repeated_tran_flag_is_rejected(flags: str) -> None:
    error = _error(f".tran 1n 1u {flags}")
    assert "is written twice" in error.reason


@pytest.mark.parametrize("line", [".tran {schedule(0, 1n)} 1u", ".tran 1n { schedule (0,1)} 1u"])
def test_a_schedule_in_a_numbers_place_is_rejected(line: str) -> None:
    assert "a schedule stands after the numbers" in _error(line).reason


# .AC


@pytest.mark.parametrize("variation", ["dec", "OCT", "Lin"])
def test_ac_takes_a_variation_and_three_values(variation: str) -> None:
    line = f".ac {variation} 10 1hz {{fstop}}"
    ac = _item(line)
    assert isinstance(ac, AcDirective)
    assert (ac.variation, ac.variation_span) == (variation, _at(line, variation))
    assert ac.points == _number(line, "10")
    assert ac.fstart == _number(line, "1hz")
    assert ac.fstop == Formula("fstop", "{", _at(line, "{fstop}"))
    assert (ac.frequencies, ac.file, ac.data) == ((), None, None)


@pytest.mark.parametrize("data", ["DATA=table1", "data = table1", "Data =table1"])
def test_ac_takes_a_data_table(data: str) -> None:
    line = f".ac {data}"
    ac = _item(line)
    keyword = data.split("=")[0].rstrip()
    assert (ac.variation, ac.variation_span) == (keyword, _at(line, keyword))
    assert ac.data == Identifier("table1", _at(line, "table1"))
    assert (ac.points, ac.fstart, ac.fstop) == (None, None, None)


@pytest.mark.parametrize(
    "line",
    [
        ".ac 10 1 1k",
        ".ac dec 10 1",
        ".ac dec 10 1 1k 2k",
        ".ac list 1 2 3",
        ".ac file=freqs.txt",
        ".ac data=t dec 10 1 1k",
        ".ac data=",
        ".ac dec 10 1 1k data=t",
    ],
)
def test_malformed_ac_is_rejected(line: str) -> None:
    assert _error(line).line == 2


# .DC


def test_dc_takes_one_sweep() -> None:
    line = ".dc V1 0 5 0.5"
    dc = _item(line)
    assert isinstance(dc, DcDirective)
    assert dc.sweeps == (
        DcSweep(
            "V1",
            _at(line, "V1"),
            _number(line, "0"),
            _number(line, "5"),
            _number(line, "0.5"),
            Span(_at(line, "V1").start, _at(line, "0.5").end),
        ),
    )
    assert dc.data is None


def test_dc_takes_any_number_of_sweeps_each_with_its_own_form() -> None:
    line = (
        ".DC LIN V1 0 1 0.5 dec R2:R 1 100 2 TEMP LIST 0 27 50 dm:IS list {a} 1e-14"
        " X1:R5:R 1k 2k 1k OCT p 1 8 1"
    )
    dc = _item(line)
    assert [sweep.source for sweep in dc.sweeps] == [
        "V1",
        "R2:R",
        "TEMP",
        "dm:IS",
        "X1:R5:R",
        "p",
    ]
    assert [sweep.variation for sweep in dc.sweeps] == ["LIN", "dec", None, None, None, "OCT"]
    temp, model = dc.sweeps[2], dc.sweeps[3]
    assert [value.text for value in temp.values] == ["0", "27", "50"]
    assert (temp.start, temp.stop, temp.increment) == (None, None, None)
    assert temp.span == Span(_at(line, "TEMP").start, _at(line, "50").end)
    assert model.values[0] == Formula("a", "{", _at(line, "{a}"))
    assert dc.sweeps[1].start == _number(line, "1", line.index("R2:R"))
    assert dc.sweeps[5].increment is not None and dc.sweeps[5].span.end == len(line) + 2


@pytest.mark.parametrize("line", [".dc v1 list 1 2 v2 0 1 1", ".dc v1 list 1 2 lin v2 0 1 1"])
def test_a_dc_list_may_be_followed_by_another_sweep(line: str) -> None:
    first, second = _item(line).sweeps
    assert [value.text for value in first.values] == ["1", "2"]
    assert second.source == "v2" and second.stop is not None


def test_a_dc_target_named_like_a_keyword_part_is_a_name() -> None:
    dc = _item(".dc data 0 1 1 listx 0 1 1")
    assert [sweep.source for sweep in dc.sweeps] == ["data", "listx"]


@pytest.mark.parametrize("data", ["data=resistorValues", "DATA = resistorValues"])
def test_dc_takes_a_data_table_alone(data: str) -> None:
    line = f".dc {data}"
    dc = _item(line)
    assert dc.sweeps == ()
    assert dc.data == Identifier("resistorValues", _at(line, "resistorValues"))


@pytest.mark.parametrize(
    "line",
    [
        ".dc",
        ".dc V1 0 1",
        ".dc V1 0 1 0.1 V2 0 1",
        ".dc V1 list 1",
        ".dc V1 list",
        ".dc lin V1 list 1 2",
        ".dc V1 lin 0 1 0.1",
        ".dc data=t V1 0 1 0.1",
        ".dc V1 0 1 0.1 data=t",
        ".dc V1 0,1,0.1",
        ".dc V1 0 1 1j",
    ],
)
def test_malformed_dc_is_rejected(line: str) -> None:
    assert _error(line).line == 2


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        (".dc 1 0 1 0.1", "a target is a name"),
        (".dc 1k 0 1 0.1", "a target is a name"),
        (".dc R2: 0 1 0.1", "empty part"),
        (".dc :R 0 1 0.1", "empty part"),
        (".step X1::R 1 2 1", "empty part"),
    ],
)
def test_a_target_that_is_not_a_name_is_rejected(line: str, reason: str) -> None:
    assert reason in _error(line).reason


# .OP


@pytest.mark.parametrize("line", [".op", ".OP", ".op ; comment"])
def test_op_takes_no_fields(line: str) -> None:
    op = _item(line)
    assert isinstance(op, OpDirective)
    assert op.keyword == line.split()[0]


@pytest.mark.parametrize("line", [".op 1", ".op all", ".OP {x}"])
def test_op_with_fields_is_rejected(line: str) -> None:
    error = _error(line)
    assert (error.line, error.column) == (2, 5)


# .STEP


@pytest.mark.parametrize(
    ("line", "kind", "name", "parameter"),
    [
        (".step R1 45 50 5", "name", "R1", None),
        (".STEP v1_val 20 10 -1", "name", "v1_val", None),
        (".step TEMP -45 -55 -10", "temp", "TEMP", None),
        (".step C101:C 45 50 5", "qualified", "C101:C", "C"),
        (".step DLEAK:IS 1.0e-12 1.0e-11 1.0e-12", "qualified", "DLEAK:IS", "IS"),
        (".step X1:R5:R 1k 2k 1k", "qualified", "X1:R5:R", "R"),
        (".step param 1 2 1", "name", "param", None),
        (".step data 1 2 1", "name", "data", None),
    ],
)
def test_step_takes_a_range(line: str, kind: str, name: str, parameter: str | None) -> None:
    step = _item(line)
    assert isinstance(step, StepDirective)
    assert (step.kind, step.name, step.parameter) == (kind, name, parameter)
    assert step.name_span == _at(line, name)
    fields = line.split()[2:]
    assert [step.start, step.stop, step.increment] == [
        _number(line, fields[0], step.name_span.end - 2),
        _number(line, fields[1], step.name_span.end - 2 + len(fields[0]) + 1),
        _number(line, fields[2], len(line) - len(fields[2])),
    ]
    assert (step.variation, step.values, step.data, step.model, step.model_type, step.file) == (
        None,
        (),
        None,
        None,
        None,
        None,
    )


@pytest.mark.parametrize("variation", ["LIN", "dec", "Oct"])
def test_step_takes_a_variation(variation: str) -> None:
    line = f".step {variation} V1 1 100 10"
    step = _item(line)
    assert (step.variation, step.variation_span) == (variation, _at(line, variation))
    assert step.kind == "name" and step.name == "V1"


def test_step_takes_a_list() -> None:
    line = ".step r1 LIST 1k 2k 5k"
    step = _item(line)
    assert step.values == (_number(line, "1k"), _number(line, "2k"), _number(line, "5k"))
    assert (step.start, step.stop, step.increment, step.variation) == (None, None, None, None)


@pytest.mark.parametrize("data", ["data=table", "DATA = table"])
def test_step_takes_a_data_table(data: str) -> None:
    line = f".step {data}"
    step = _item(line)
    assert step.kind == "data"
    assert step.data == Identifier("table", _at(line, "table"))
    assert (step.name, step.name_span) == ("table", _at(line, "table"))
    assert (step.start, step.values, step.parameter) == (None, (), None)


def test_step_continues_across_plus_lines() -> None:
    text = "t\n.step R1\n* c\n+ list 1\n+ 2 ; end\n.END\n"
    (step,) = _parse(text).items[1:-1]
    assert [value.text for value in step.values] == ["1", "2"]
    assert [text[c.start : c.end] for c in step.trailing_comments] == ["* c", "; end"]


@pytest.mark.parametrize(
    "line",
    [
        ".step",
        ".step R1 1 2",
        ".step R1 {1} 2 1",
        ".step R1 1 '2' 1",
        ".step R1 list 1",
        ".step R1 list 1 {2}",
        ".step lin R1 list 1 2",
        ".step R1 lin 1 2 1",
        ".step R1 1 2 1 3",
        ".step data=t R1 1 2 1",
        ".step R1 1,2,1",
        ".step R1 1 2 1j",
    ],
)
def test_malformed_step_is_rejected(line: str) -> None:
    assert _error(line).line == 2


@pytest.mark.parametrize("line", [".step param x 1 2 1", ".STEP PARAM x list 1 2"])
def test_the_param_keyword_is_rejected_with_a_hint(line: str) -> None:
    error = _error(line)
    assert (error.line, error.column) == (2, 7)
    assert "takes no `" in error.reason and "name the parameter directly" in error.reason


@pytest.mark.parametrize(
    "line", [".step R1 1 2 1 R2 1 2 1", ".step R1 list 1 2 R2 list 1 2", ".step data=t R2 1 2 1"]
)
def test_a_second_sweep_on_one_step_line_is_rejected(line: str) -> None:
    error = _error(line)
    assert error.column == line.index("R2") + 1
    assert "one `.STEP` line per sweep" in error.reason


# Place


@pytest.mark.parametrize(
    "line", [".tran 1n 1u", ".ac dec 10 1 1k", ".dc V1 0 1 1", ".op", ".step R1 1 2 1"]
)
def test_analyses_and_step_are_refused_in_a_body(line: str) -> None:
    # Xyce silently ignores them in a body (decision 0028 item 2).
    with pytest.raises(ParseError) as captured:
        _parse(f"t\n.subckt s a\n{line}\n.ends\n.END\n")
    error = captured.value
    assert (error.line, error.column) == (3, 1)
    assert "not allowed inside a subcircuit definition" in error.reason
    assert "silently ignores it there" in error.reason


def test_several_analyses_are_read() -> None:
    # Which one Xyce runs is the document layer's (point 15, B5).
    text = "t\n.op\n.tran 1n 1u\n.ac dec 1 1 1k\n.dc V1 0 1 1\n.step R1 1 2 1\n.END\n"
    kinds = [type(item).__name__ for item in _parse(text).items[1:-1]]
    assert kinds == ["OpDirective", "TranDirective", "AcDirective", "DcDirective", "StepDirective"]
