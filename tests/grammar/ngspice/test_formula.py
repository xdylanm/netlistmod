"""The formula grammar (M5, NG-FML-001): the names a formula refers to, never an evaluation."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from netlistmod import Dialect
from netlistmod.grammar.formula import (
    FormulaToken,
    build_formula_parser,
    parse_formula,
    reserved_words,
)


def _names(text: str) -> list[tuple[str, str]]:
    tokens = parse_formula(text, Dialect.NGSPICE)
    assert tokens is not None, text
    for token in tokens:
        assert text[token.start : token.end] == token.text
    return [(token.kind, token.text) for token in tokens]


@pytest.mark.parametrize(
    ("text", "names"),
    [
        ("rx", [("parameter", "rx")]),
        ("1k*rx", [("parameter", "rx")]),
        ("2meg / (r[1] + r_2)", [("parameter", "r[1]"), ("parameter", "r_2")]),
        ("-x**2^y", [("parameter", "x"), ("parameter", "y")]),
        ("a ? b : c", [("parameter", "a"), ("parameter", "b"), ("parameter", "c")]),
        ("!a && b || c <> d", [("parameter", n) for n in "abcd"]),
        ("a != b == c <= d >= e < f > g", [("parameter", n) for n in "abcdefg"]),
        ("5 \\ 3 % 2 / 1 * 4 - 1 + +2", []),
        ("1.5e-3 * 2.", []),
        ('"text"', []),
        ("(((x)))", [("parameter", "x")]),
    ],
)
def test_bare_identifiers_are_parameter_names(text: str, names: list[tuple[str, str]]) -> None:
    assert _names(text) == names


@pytest.mark.parametrize(
    ("text", "names"),
    [
        ("V(a)*2+gain", [("node", "a"), ("parameter", "gain")]),
        ("v(/out, n-2)", [("node", "/out"), ("node", "n-2")]),
        ("vdb(out) + VM(x)", [("node", "out"), ("node", "x")]),
        ("i(vm)*r", [("source", "vm"), ("parameter", "r")]),
        (
            "f(a, g(b))",
            [("function", "f"), ("parameter", "a"), ("function", "g"), ("parameter", "b")],
        ),
        ("myfunc()", [("function", "myfunc")]),
    ],
)
def test_calls_and_accessors_are_not_parameters(text: str, names: list[tuple[str, str]]) -> None:
    assert _names(text) == names


@pytest.mark.parametrize("word", ["time", "TEMPER", "hertz", "sqrt", "log10", "not", "vec"])
def test_reserved_words_are_not_parameters(word: str) -> None:
    assert _names(f"{word} + 1") == [("reserved", word)]


def test_pi_is_an_identifier() -> None:
    # §2.11.5 defines no constants; ngspice 47 rejects {pi} as an undefined parameter.
    assert _names("2*pi") == [("parameter", "pi")]


@pytest.mark.parametrize("text", ["a#b", "a b", "a!b", "1k2", "(a", "a+", "", "v(a", "@r1[i]"])
def test_text_the_grammar_does_not_accept_gives_no_tokens(text: str) -> None:
    assert parse_formula(text, Dialect.NGSPICE) is None


def test_formula_parser_is_strict_lalr_and_reserved_words_are_data() -> None:
    parser = build_formula_parser(Dialect.NGSPICE)
    assert parser.options.strict is True
    assert parser.options.parser == "lalr"
    assert {"time", "temper", "hertz", "sqrt", "and"} <= reserved_words(Dialect.NGSPICE)


_IDENT = st.from_regex(r"[a-z][a-z0-9_]{0,4}", fullmatch=True).filter(
    lambda name: name not in reserved_words(Dialect.NGSPICE)
)


@given(st.lists(_IDENT, min_size=1, max_size=6), st.lists(st.sampled_from("+-*/^%"), min_size=5))
def test_generated_sums_report_every_identifier(names: list[str], ops: list[str]) -> None:
    text = names[0]
    for name, op in zip(names[1:], ops, strict=False):
        text += f" {op} {name}"
    tokens = parse_formula(text, Dialect.NGSPICE)
    assert tokens is not None
    assert [token.text for token in tokens] == names
    assert all(isinstance(token, FormulaToken) for token in tokens)


@pytest.mark.parametrize("text", ["a&b", "a|b", "a & b"])
def test_single_character_logical_operators_are_not_ngspice(text: str) -> None:
    # ngspice 47 stops at them, so a scan reports no names (M8 review R4); LTspice has them.
    assert parse_formula(text, Dialect.NGSPICE) is None
    tokens = parse_formula(text, Dialect.LTSPICE)
    assert tokens is not None
    assert [token.text for token in tokens] == ["a", "b"]
