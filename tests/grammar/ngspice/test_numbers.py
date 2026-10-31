"""Numbers, scale factors, trailing letters, RKM notation and formulas (M3, T1 tier)."""

from __future__ import annotations

import pytest

from netlistmod import (
    Capacitor,
    Dialect,
    Formula,
    Inductor,
    NumericValue,
    ParseError,
    Resistor,
    SourceText,
    parse,
)


def _element(line: str, *, rkm: bool = False) -> object:
    return parse(SourceText(f"title\n{line}\n.end\n"), Dialect.NGSPICE, rkm=rkm).items[1]


def _value(line: str, *, rkm: bool = False) -> NumericValue | Formula:
    element = _element(line, rkm=rkm)
    assert isinstance(element, Resistor | Capacitor | Inductor)
    assert element.value is not None
    return element.value


def _reject(line: str, *, rkm: bool = False) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"title\n{line}\n.end\n"), Dialect.NGSPICE, rkm=rkm)
    return captured.value


@pytest.mark.parametrize(
    "text",
    ["100", "-44", "+1k", "3.14159", ".5", "5.", "1e-14", "2.65e3", "1E3", "1e3k", "1.5e-3meg"],
)
def test_number_forms_are_stored_verbatim(text: str) -> None:
    value = _value(f"R1 a b {text}")
    assert value == NumericValue(text, value.span)
    assert value.notation == "standard"
    assert value.span.end - value.span.start == len(text)


@pytest.mark.parametrize(
    "text", ["1T", "1g", "1Meg", "1MEG", "1k", "1mil", "1MIL", "1m", "1u", "1n", "1p", "1f", "1a"]
)
def test_scale_factors_are_case_insensitive_and_kept_as_text(text: str) -> None:
    assert _value(f"C1 a b {text}").text == text


@pytest.mark.parametrize(
    "text", ["10V", "10Volts", "1UF", "1kOhm", "1kHz", "1kk", "15.7MA", "470R"]
)
def test_letters_after_a_number_are_part_of_the_value(text: str) -> None:
    value = _value(f"R1 a b {text}")
    assert value.text == text
    assert isinstance(value, NumericValue) and value.notation == "standard"


@pytest.mark.parametrize("line", ["R1 a b 1µ", "C1 a b 4.7µF", "L1 a b 10µ"])
def test_micro_sign_is_a_scale_factor(line: str) -> None:
    assert _value(line).text == line.rsplit(" ", 1)[1]


@pytest.mark.parametrize("line", ["R1 a b 1M", "R1 a b 47K", "R1 a b 4E7", "R1 a b 470R"])
def test_standard_notation_is_the_same_in_both_rkm_modes(line: str) -> None:
    assert _value(line, rkm=False) == _value(line, rkm=True)
    assert _value(line).notation == "standard"


@pytest.mark.parametrize(
    "line",
    [
        "R1 a b 2k7",
        "R1 a b 2K7",
        "R1 a b 4R7",
        "R1 a b 4r7",
        "R1 a b R47",
        "R1 a b l47",
        "R1 a b 4L7",
        "R1 a b 4G7",
        "R1 a b 4t7",
        "R1 a b 1k0",
        "C1 a b 4p7",
        "C1 a b 4N7",
        "C1 a b 4u7",
        "C1 a b 4µ7",
        "C1 a b 1m0",
        "C1 a b 1M5",
    ],
)
def test_rkm_values_need_the_option(line: str) -> None:
    error = _reject(line)
    assert "RKM notation" in error.reason and "rkm=True" in error.reason
    assert (error.line, error.column) == (2, line.index(line.rsplit(" ", 1)[1]) + 1)
    value = _value(line, rkm=True)
    assert value == NumericValue(line.rsplit(" ", 1)[1], value.span, "rkm", False)


@pytest.mark.parametrize("line", ["R1 net1 net2 1M0", "R1 a b 4M7", "C1 a b 4F7", "C1 a b 4f7"])
def test_rkm_values_ngspice_reads_differently_are_marked(line: str) -> None:
    assert "RKM notation" in _reject(line).reason
    value = _value(line, rkm=True)
    assert isinstance(value, NumericValue)
    assert (value.notation, value.solver_mismatch) == ("rkm", True)


@pytest.mark.parametrize("rkm", [False, True])
def test_lowercase_m_in_a_resistor_rkm_value_is_rejected_with_a_hint(rkm: bool) -> None:
    error = _reject("R1 a b 1m5", rkm=rkm)
    assert (error.line, error.column) == (2, 8)
    assert "write `L` for milli" in error.reason


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("L1 a b 4u7", 10),  # RKM is for R and C only
        ("C1 a b 4k7", 10),  # k is not a capacitor code
        ("R1 a b 4n7", 10),  # n is not a resistor code
        ("R1 a b 2k7x", 11),
        ("R1 a b 1meg5", 12),
        ("R1 a b 2.2k7", 12),
        ("R1 a b 1kOhm2", 13),
    ],
)
def test_digits_after_letters_outside_rkm_are_rejected_in_both_modes(
    line: str, column: int
) -> None:
    for rkm in (False, True):
        error = _reject(line, rkm=rkm)
        assert (error.line, error.column) == (2, column)


@pytest.mark.parametrize(
    ("line", "text", "delimiter"),
    [
        ("R1 a b {Rx*2}", "Rx*2", "{"),
        ("R1 a b { Rx * 2 }", " Rx * 2 ", "{"),
        ("R1 a b 'Rx*2'", "Rx*2", "'"),
        ("R1 rr 0 'V(rr) < {Vt} ? {R0} : {2*R0}'", "V(rr) < {Vt} ? {R0} : {2*R0}", "'"),
        ("C1 a b {c0/2}", "c0/2", "{"),
        ("C1 a b 'c0;x'", "c0;x", "'"),
    ],
)
def test_formulas_keep_their_text_and_delimiter(line: str, text: str, delimiter: str) -> None:
    value = _value(line)
    assert value == Formula(text, delimiter, value.span)  # type: ignore[arg-type]
    source = f"title\n{line}\n.end\n"
    assert source[value.span.start] == delimiter
    assert source[value.span.start + 1 : value.span.end - 1] == text


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("R1 a b {a{b}}", 8),
        ("R1 a b {}", 8),
        ("R1 a b ''", 8),
        ("R1 a b {open", 8),
        ('R1 a b "string"', 8),
        ("R1 a b {c0;x}", 8),
        ("R1 a b {c0 $x}", 8),
        ("R1 a b {c0//2}", 8),
        ("R1 a b 1.1*Rx", 11),
        ("R1 a b 1k+Rx", 10),
    ],
)
def test_nested_empty_unclosed_and_bare_formulas_are_rejected(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)


def test_a_letter_leading_bare_expression_reads_as_a_model_name() -> None:
    # Limitation (decision 0004): without blanks, Rx+1000 is a valid name, so it is the model
    # slot. Model resolution (M5, UNRESOLVED_MODEL) reports it; it is never a value.
    element = _element("R1 a b Rx+1000")
    assert isinstance(element, Resistor)
    assert element.value is None
    assert element.model is not None and element.model.model_name == "Rx+1000"
