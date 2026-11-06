"""What a parse error says about an incomplete line or text after `.end` (M9 H2).

The position does not change: the `*_rejects` manifests pin it. These check the words only, and
do not name the missing field for each construct, which would repeat the grammar in Python.
"""

from __future__ import annotations

import pytest

from netlistmod import Dialect, ParseError, SourceText, UnsupportedConstruct, parse

_BOTH = [Dialect.NGSPICE, Dialect.LTSPICE]
_INCOMPLETE = "this line ends too early"
_PUNCTUATION = ("separator", "continuation", "comment")


def _reject(text: str, dialect: Dialect) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(text), dialect)
    return captured.value


@pytest.mark.parametrize("dialect", _BOTH)
@pytest.mark.parametrize(
    ("line", "column"),
    [("R1 a 0", 7), ("R1 a", 5), (".model dm", 10), ("V1 a 0 AC", 10)],
)
@pytest.mark.parametrize("ending", ["\n.end\n", "\r\n.end\r\n", ""], ids=["lf", "crlf", "eof"])
def test_a_line_that_ends_too_early_says_so(
    dialect: Dialect, line: str, column: int, ending: str
) -> None:
    error = _reject(f"t\n{line}{ending}", dialect)
    assert error.reason == _INCOMPLETE
    assert (error.line, error.column) == (2, column)
    assert _INCOMPLETE in str(error)
    assert not any(word in name for name in error.expected for word in _PUNCTUATION)
    assert "end of line" not in error.expected


@pytest.mark.parametrize("ending", ["\n.end\n", ""], ids=["lf", "eof"])
def test_a_tran_with_one_value_ends_too_early_in_ngspice(ending: str) -> None:
    error = _reject(f"t\n.tran 1ns{ending}", Dialect.NGSPICE)
    assert error.reason == _INCOMPLETE
    assert error.expected == ()
    assert (error.line, error.column) == (2, 10)
    assert "Expected" not in str(error)


def test_a_tran_with_one_value_is_complete_in_ltspice() -> None:
    parse(SourceText("t\n.tran 1ns\n.end\n"), Dialect.LTSPICE)


def test_too_many_fields_read_as_a_parameter_also_end_too_early_in_ngspice() -> None:
    # The grammar reads `foo` as a parameter name waiting for `=`, so the words must not claim
    # that a field is missing.
    error = _reject("t\nR1 a 0 1k foo bar\n.end\n", Dialect.NGSPICE)
    assert error.reason == _INCOMPLETE
    assert (error.line, error.column) == (2, 18)
    assert not any(word in name for name in error.expected for word in _PUNCTUATION)


def test_what_the_grammar_still_asks_for_stays_in_the_message() -> None:
    error = _reject("t\n.tran 1ns \n.end\n", Dialect.NGSPICE)
    assert error.reason == _INCOMPLETE
    assert "number" in error.expected
    assert not any(word in name for name in error.expected for word in _PUNCTUATION)


@pytest.mark.parametrize("dialect", _BOTH)
def test_a_complete_line_with_no_end_is_still_a_missing_end(dialect: Dialect) -> None:
    error = _reject("t\nR1 a 0 1k\n", dialect)
    assert "`.end`, which is missing" in error.reason
    assert _INCOMPLETE not in str(error)


@pytest.mark.parametrize("dialect", _BOTH)
def test_a_complete_last_line_with_no_line_end_is_not_incomplete(dialect: Dialect) -> None:
    assert _INCOMPLETE not in str(_reject("t\nR1 a 0 1k", dialect))


@pytest.mark.parametrize("dialect", _BOTH)
def test_an_unbalanced_parenthesis_keeps_its_own_message(dialect: Dialect) -> None:
    error = _reject("t\n.model dm D (n=1\n.end\n", dialect)
    assert "unbalanced `(`" in error.reason


@pytest.mark.parametrize("dialect", _BOTH)
@pytest.mark.parametrize(
    ("after", "column"),
    [
        ("R1 a 0 1k\n", 1),
        ("  R1 a 0 1k\n", 3),
        ("R1 a 0 1k", 1),
        (".op\n", 1),
        (".end\n", 1),
        ("* comment\n", 1),
    ],
)
def test_text_after_end_says_the_netlist_ends_there(
    dialect: Dialect, after: str, column: int
) -> None:
    error = _reject(f"t\n.end\n{after}", dialect)
    assert "the netlist ends at `.end`" in error.reason
    assert (error.line, error.column) == (3, column)


@pytest.mark.parametrize("dialect", _BOTH)
def test_blank_lines_after_end_are_valid(dialect: Dialect) -> None:
    parse(SourceText("t\n.end\n\n  \n"), dialect)


@pytest.mark.parametrize("dialect", _BOTH)
@pytest.mark.parametrize("after", ["T1 a b c m\n", "hello world\n"])
def test_a_planned_letter_after_end_says_the_netlist_ends_there(
    dialect: Dialect, after: str
) -> None:
    error = _reject(f"t\n.end\n{after}", dialect)
    assert "the netlist ends at `.end`" in error.reason
    assert (error.line, error.column) == (3, 1)


@pytest.mark.parametrize("dialect", _BOTH)
def test_a_planned_letter_before_end_stays_an_unsupported_construct(dialect: Dialect) -> None:
    with pytest.raises(UnsupportedConstruct):
        parse(SourceText("t\nT1 a b c m\n.end\n"), dialect)


def test_end_inside_a_subcircuit_keeps_its_own_message() -> None:
    error = _reject("t\n.subckt s a\n.end\n.ends\n.end\n", Dialect.NGSPICE)
    assert "`.end` is not allowed inside a subcircuit" in error.reason
