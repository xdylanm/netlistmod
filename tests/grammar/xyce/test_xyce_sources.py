"""xyce transient source functions: PULSE, SIN, EXP, SFFM, PAT and PWL (X-M3 B2; decision 0030
items 1 to 5; xm3-tasks 5.1 points 1 to 14)."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    CurrentSource,
    Formula,
    Identifier,
    NumericValue,
    ParseError,
    SourceSpec,
    SourceText,
    Span,
    VoltageSource,
    parse,
)
from netlistmod.dialects import _XYCE, Dialect


def _source(line: str) -> Any:
    text = f"t\n{line}\n.END\n"
    items = parse(SourceText(text), _XYCE).items
    position = 0
    for item in items:
        assert item.span.start == position
        position = item.span.end
    assert position == len(text)
    source = items[1]
    assert isinstance(source, VoltageSource | CurrentSource)
    return source


def _stimulus(line: str) -> SourceSpec:
    stimulus = _source(line).stimulus
    assert isinstance(stimulus, SourceSpec)
    text = f"t\n{line}\n.END\n"
    assert text[stimulus.name_span.start : stimulus.name_span.end] == stimulus.name
    return stimulus


def _error(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"t\n{line}\n.END\n"), _XYCE)
    return captured.value


def _texts(spec: SourceSpec) -> list[str]:
    return [arg.text for arg in spec.args]


# The forms read


def test_a_pulse_with_its_list_in_parentheses() -> None:
    spec = _stimulus("V1 a 0 PULSE(0 1 1n 1n 1n 5n 10n)")
    assert spec.name == "PULSE" and spec.name_span == Span(9, 14)
    assert spec.args[0] == NumericValue("0", Span(15, 16))
    assert _texts(spec) == ["0", "1", "1n", "1n", "1n", "5n", "10n"]
    assert spec.params == () and spec.span == Span(9, 35)


@pytest.mark.parametrize(
    ("line", "args"),
    [
        ("V1 a 0 sin 0 1 1k", ["0", "1", "1k"]),
        ("V1 a 0 SIN (0 1 1k 0 0 90)", ["0", "1", "1k", "0", "0", "90"]),
        ("V1 a 0 Sin( 0 1 1k )", ["0", "1", "1k"]),
        ("V1 a 0 EXP(0 1)", ["0", "1"]),
        ("V1 a 0 exp 0 1 2n 1n 10n 2n", ["0", "1", "2n", "1n", "10n", "2n"]),
        ("V1 a 0 SFFM (0 1 100meg 2 10meg)", ["0", "1", "100meg", "2", "10meg"]),
        ("V1 a 0 sffm 0 1", ["0", "1"]),
        ("V1 a 0 PULSE(1)", ["1"]),
        ("V1 a 0 PULSE({lo} 'hi*2' 1ns)", ["lo", "hi*2", "1ns"]),
        ("V1 a 0 PULSE(0\n+ 1 1n)", ["0", "1", "1n"]),
        ("V1 a 0 PULSE 0 1 ; a comment", ["0", "1"]),
        ("I1 a 0 PULSE(0 1m 1n 1n 1n 5n 10n)", ["0", "1m", "1n", "1n", "1n", "5n", "10n"]),
    ],
)
def test_the_functions_with_or_without_parentheses(line: str, args: list[str]) -> None:
    assert _texts(_stimulus(line)) == args


def test_the_function_follows_the_dc_and_ac_parts() -> None:
    source = _source("V1 a 0 DC 1 AC 1 0 SIN(0 1 1k)")
    assert source.dc == NumericValue("1", Span(12, 13)) and source.ac is not None
    assert source.stimulus.name == "SIN" and source.stimulus.span == Span(21, 32)
    assert _source("V1 a 0 2 SIN(0 1 1k)").dc.text == "2"
    assert _source("I1 a 0 AC 1 EXP(0 1)").ac.phase is None


def test_a_braced_argument_is_a_formula() -> None:
    spec = _stimulus("V1 a 0 PULSE(0 {hi})")
    assert spec.args[1] == Formula("hi", "{", Span(17, 21))


def test_pat_holds_its_bit_string_as_an_identifier() -> None:
    spec = _stimulus("V1 a 0 PAT(5 0 0 1n 1n 5n b010)")
    assert spec.args[6] == Identifier("b010", Span(28, 32))
    assert len(spec.args) == 7 and spec.params == ()
    assert _stimulus("V1 a 0 pat 5 0 0 1n 1n 5n B01").args[6] == Identifier("B01", Span(28, 31))


@pytest.mark.parametrize(
    "line",
    ["V1 a 0 PAT(5 0 0 1n 1n 5n b010) R=3", "V1 a 0 PAT 5 0 0 1n 1n 5n b010 r = {n}"],
)
def test_pat_takes_r_after_its_list(line: str) -> None:
    spec = _stimulus(line)
    (repeat,) = spec.params
    assert repeat.name.lower() == "r"
    assert spec.span.end == repeat.span.end


def test_pwl_takes_pairs_then_td_and_r() -> None:
    spec = _stimulus("V1 a 0 PWL 0 0 1n 1 TD=1n R=0")
    assert _texts(spec) == ["0", "0", "1n", "1"]
    assert [(p.name, p.value.text) for p in spec.params] == [("TD", "1n"), ("R", "0")]
    assert spec.span == Span(9, 31)
    paren = _stimulus("V1 a 0 PWL(0 0 1n 1) R=0 TD=2n")
    assert [p.name for p in paren.params] == ["R", "TD"]


@pytest.mark.parametrize(
    ("line", "path"),
    [
        ('V1 a 0 PWL FILE "wave.csv"', Formula("wave.csv", '"', Span(18, 28))),
        ("V1 a 0 pwl file wave.csv", Identifier("wave.csv", Span(18, 26))),
        ('V1 a 0 PWL File "my wave.txt" TD=1n R=0', Formula("my wave.txt", '"', Span(18, 31))),
    ],
)
def test_pwl_file_is_a_parameter_holding_the_path(line: str, path: Formula | Identifier) -> None:
    spec = _stimulus(line)
    assert spec.args == ()
    file = spec.params[0]
    assert file.name.lower() == "file" and file.value == path
    assert file.name_span == Span(13, 17) and file.span == Span(13, path.span.end)


def test_the_other_dialects_still_read_their_own_functions() -> None:
    # Decision 0024: the shared source rules change nothing on ngspice and LTspice.
    for dialect in (Dialect.NGSPICE, Dialect.LTSPICE):
        (_, source, _) = parse(SourceText("t\nV1 a 0 PULSE(0, 1, 1n)\n.end\n"), dialect).items
        assert [arg.text for arg in source.stimulus.args] == ["0", "1", "1n"]


# The forms refused


@pytest.mark.parametrize(
    "line",
    [
        "V1 a 0 SIN(0 1 1k) AC 1",
        "V1 a 0 SIN(0 1 1k) DC 1",
        "V1 a 0 SIN(0 1 1k) 1",
        "V1 a 0 SIN(0 1 1k) PULSE(0 1)",
        "V1 a 0 SINE(0 1 1k)",
        "V1 a 0 PULSE(0 hi 1n)",
        "V1 a 0 PULSE(0 1 1n)DC 1",
        "V1 a 0 PWL (0 0) (1n 1)",
        'V1 a 0 PWL(FILE "x.csv")',
        "V1 a 0 PWL FILE 'x.csv'",
        'V1 a 0 PWL FILE "x.csv" 0 0',
        'V1 a 0 PWL FILE "x.csv" FILE "y.csv"',
        "V1 a 0 PWL FILE",
        "V1 a 0 PWL TD=1n 0 0 1n 1",
        "V1 a 0 PWL 0 0 1n 1 R",
    ],
)
def test_forms_outside_the_order_or_the_syntax_are_refused(line: str) -> None:
    _error(line)


def test_an_unbalanced_parenthesis_is_refused_at_the_opener() -> None:
    error = _error("V1 a 0 PULSE(0 1 1n")
    assert "`)`" in error.expected or "unbalanced" in error.reason


@pytest.mark.parametrize(
    "line", ["V1 a 0 PULSE(0,1)", "V1 a 0 PWL 0,0 1n,1", "V1 a 0 SIN(0, 1, 1k)"]
)
def test_a_comma_is_refused_with_a_hint(line: str) -> None:
    error = _error(line)
    assert "separate the arguments with blanks" in error.reason
    assert error.column == line.index(",") + 1


@pytest.mark.parametrize(
    ("line", "name"),
    [
        ("V1 a 0 PULSE(0 1 TD=10n)", "TD"),
        ("V1 a 0 PULSE(V1=0 V2=1)", "V1"),
        ("V1 a 0 PULSE(0 1) TD=10n", "TD"),
        ("V1 a 0 SIN 0 1 1k R=0", "R"),
        ("V1 a 0 PAT(VHI=5 0 0 1n 1n 5n b01)", "VHI"),
    ],
)
def test_a_keyword_argument_is_refused(line: str, name: str) -> None:
    error = _error(line)
    assert "by position" in error.reason
    assert error.column == line.index(f"{name}=") + 1


@pytest.mark.parametrize(
    ("line", "name"),
    [("V1 a 0 PAT(5 0 0 1n 1n 5n b01 R=3)", "R"), ("V1 a 0 PWL(0 0 1n 1 TD=1n)", "TD")],
)
def test_td_and_r_inside_the_parentheses_are_refused(line: str, name: str) -> None:
    error = _error(line)
    assert "after the list, outside the parentheses" in error.reason
    assert error.column == line.index(f"{name}=") + 1


@pytest.mark.parametrize(
    "line", ["V1 a 0 PWL 0 0 1n 1 TD=1n TD=2n", "V1 a 0 PAT(5 0 0 1n 1n 5n b01) R=1 R=2"]
)
def test_td_and_r_stand_once(line: str) -> None:
    assert "written twice" in _error(line).reason


def test_pwl_file_with_an_equals_sign_is_refused_with_a_hint() -> None:
    error = _error('V1 a 0 PWL FILE="x.csv"')
    assert 'write `FILE "name"`' in error.reason


@pytest.mark.parametrize(
    ("line", "found"),
    [
        ("V1 a 0 PULSE()", "has 0"),
        ("V1 a 0 SIN(0 1)", "has 2"),
        ("V1 a 0 EXP(0)", "has 1"),
        ("V1 a 0 SFFM(0)", "has 1"),
        ("V1 a 0 PAT(5 0 0 1n 1n b01)", "PAT"),
        ("V1 a 0 PULSE(0 1 1n 1n 1n 5n 10n 7)", "has 8"),
        ("V1 a 0 SIN(0 1 1k 0 0 90 1)", "has 7"),
        ("V1 a 0 EXP(0 1 2n 1n 10n 2n 5)", "has 7"),
        ("V1 a 0 SFFM(0 1 1k 2 1k 5)", "has 6"),
        ("V1 a 0 PAT(5 0 0 1n 1n 5n b01 1 7)", "has 9"),
    ],
)
def test_each_function_counts_its_arguments(line: str, found: str) -> None:
    assert found in _error(line).reason


def test_a_positional_pat_repeat_count_is_refused_with_a_hint() -> None:
    line = "V1 a 0 PAT(5 0 0 1n 1n 5n b01 3)"
    error = _error(line)
    assert "write the repeat count as `R=3`" in error.reason
    assert error.column == line.index(" 3)") + 2


@pytest.mark.parametrize(
    "line", ["V1 a 0 PAT(5 0 0 1n 1n 5n 1)", "V1 a 0 PAT(5 0 0 1n 1n 5n {b01})"]
)
def test_pat_needs_its_bit_string_seventh(line: str) -> None:
    assert "seventh argument is its DATA" in _error(line).reason


def test_a_bit_string_elsewhere_is_refused() -> None:
    assert "only PAT's DATA" in _error("V1 a 0 PAT(5 0 0 1n 1n b01 5n)").reason


@pytest.mark.parametrize("line", ["V1 a 0 PWL 0 0 1n", "V1 a 0 PWL 1"])
def test_pwl_needs_pairs(line: str) -> None:
    error = _error(line)
    assert "has no partner" in error.reason


def test_pwl_needs_its_points() -> None:
    assert "without its points" in _error("V1 a 0 PWL").reason


def test_pwl_continues_across_plus_lines() -> None:
    spec = _stimulus('V1 a 0 PWL ; c\n+ FILE\n+ "w.csv" ; c\n+ TD=1n\n+ R=0')
    assert [p.name for p in spec.params] == ["FILE", "TD", "R"]
    assert _texts(_stimulus("V1 a 0 PWL 0 0\n+ 1n 1\n+ R=0")) == ["0", "0", "1n", "1"]


def test_td_and_r_written_twice_say_xyce_uses_the_last() -> None:
    assert "Xyce runs it with the last value" in _error("V1 a 0 PWL 0 0 1 1 R=0 R=1").reason


@pytest.mark.parametrize(
    ("line", "name", "reason"),
    [
        ("V1 a 0 PULSE 0 1 TD=1 2", "TD", "by position"),
        ("V1 a 0 PWL 0 0 TD=1 1 1", "TD", "after the list"),
        ("V1 a 0 PAT 5 0 0 1n 1n R=2 5n b01", "R", "after the list"),
    ],
)
def test_a_keyword_before_an_argument_is_refused_at_the_keyword(
    line: str, name: str, reason: str
) -> None:
    error = _error(line)
    assert reason in error.reason
    assert error.column == line.index(f"{name}=") + 1


def test_a_single_quoted_file_path_is_refused_with_a_hint() -> None:
    line = "V1 a 0 PWL FILE 'w.csv'"
    error = _error(line)
    assert "write the path in double quotes" in error.reason
    assert error.column == line.index("'") + 1
