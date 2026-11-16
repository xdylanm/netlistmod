"""xyce `.PARAM`, `.GLOBAL_PARAM`, `.FUNC`, the value forms and the formula grammar (X-M1 B3;
decision 0027 items 9 to 11)."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    End,
    Formula,
    Identifier,
    NumericValue,
    ParamAssignment,
    ParamStatement,
    ParseError,
    SourceText,
    Span,
    Title,
    parse,
)
from netlistmod.dialects import _XYCE
from netlistmod.grammar.formula import builtin_functions, parse_formula, reserved_words
from netlistmod.model.nodes import FuncStatement, GlobalParamStatement
from netlistmod.model.values import FunctionDefinition


def _parse(text: str) -> Any:
    return parse(SourceText(text), _XYCE)


def _items(line: str) -> Any:
    text = f"t\n{line}\n.END\n"
    items = _parse(text).items
    position = 0
    for item in items:
        assert item.span.start == position
        position = item.span.end
    assert position == len(text)
    return items


def _statement(line: str) -> Any:
    (title, statement, end) = _items(line)
    assert isinstance(title, Title) and isinstance(end, End)
    return statement


def _values(line: str) -> list[tuple[str, str, str]]:
    statement = _statement(line)
    return [
        (a.name, type(a.value).__name__, getattr(a.value, "delimiter", ""))
        for a in statement.assignments
    ]


def test_param_takes_numbers_braces_quotes_and_bare_values() -> None:
    statement = _statement(".PARAM a=1k b={a*2} c='a+1' d=a*3")
    assert isinstance(statement, ParamStatement)
    assert not isinstance(statement, GlobalParamStatement)
    assert statement.keyword == ".PARAM"
    assert statement.assignments == (
        ParamAssignment("a", NumericValue("1k", Span(11, 13)), Span(9, 13), Span(9, 10)),
        ParamAssignment("b", Formula("a*2", "{", Span(16, 21)), Span(14, 21), Span(14, 15)),
        ParamAssignment("c", Formula("a+1", "'", Span(24, 29)), Span(22, 29), Span(22, 23)),
        ParamAssignment("d", Formula("a*3", "", Span(32, 35)), Span(30, 35), Span(30, 31)),
    )
    assert statement.functions == ()


@pytest.mark.parametrize(
    "line",
    [
        ".param a=1, b=2",
        ".param a=1 ,b=2",
        ".param a = 1 , b = 2",
        ".param a=1,\n+ b=2",
        ".param a=1\n* c\n+ , b=2",
        ".param a=1 ; c\n+ b=2",
    ],
)
def test_param_separates_with_blanks_or_commas(line: str) -> None:
    # Commas are optional, blanks may stand around `=` ([xyce-ref] §2.1.26 p120).
    assert [name for name, *_ in _values(line)] == ["a", "b"]


@pytest.mark.parametrize(
    ("value", "kind", "delimiter"),
    [
        ("1", "NumericValue", ""),
        ("-2.5e-3", "NumericValue", ""),
        ("2j", "NumericValue", ""),
        ("1.0+2.0J", "Formula", ""),
        ("{1+2j}", "Formula", "{"),
        ("1x", "NumericValue", ""),
        ("1kv", "NumericValue", ""),
        ("-a", "Formula", ""),
        (".5*b", "Formula", ""),
        ("agauss(1,0.1,0.1)", "Formula", ""),
        ("max(a,min(b,c))", "Formula", ""),
        ("a==b?1:0", "Formula", ""),
        ("x1:a", "Formula", ""),
        ('{table("f.txt")}', "Formula", "{"),
        ("'a + b'", "Formula", "'"),
        ("{a + b}", "Formula", "{"),
    ],
)
def test_param_value_forms(value: str, kind: str, delimiter: str) -> None:
    assert _values(f".param p={value}") == [("p", kind, delimiter)]


@pytest.mark.parametrize("value", ['"abc"', "1kohm", "1kk", "1e", "1keg", "1µ", "2k7", "{a", "'a"])
def test_a_string_or_a_bad_number_is_rejected(value: str) -> None:
    # No strings in `.PARAM` (Xyce stops on one); the number readers' refusals (XY-NUM-002).
    with pytest.raises(ParseError) as captured:
        _parse(f"t\n.param p={value}\n.END\n")
    assert captured.value.line == 2


@pytest.mark.parametrize(
    "line", [".param a = 1 + 2", ".param a=1 +2", ".param a=b c", ".param a=1 {2}"]
)
def test_a_blank_inside_a_bare_value_is_rejected_with_a_hint(line: str) -> None:
    # Decision X-D5: a bare value has no blank; Xyce deletes them (discrepancies.md).
    with pytest.raises(ParseError, match="write the expression in braces") as captured:
        _parse(f"t\n{line}\n.END\n")
    assert captured.value.line == 2


@pytest.mark.parametrize("name", ["a", "A_1", "_x", "a.b", "a.b.c", "x1"])
def test_parameter_names(name: str) -> None:
    assert _values(f".param {name}=1") == [(name, "NumericValue", "")]


@pytest.mark.parametrize("name", ["1a", "a#", "a@b", "a$", "a:b", ".a"])
def test_a_name_outside_the_parameter_rule_is_rejected(name: str) -> None:
    with pytest.raises(ParseError):
        _parse(f"t\n.param {name}=1\n.END\n")


@pytest.mark.parametrize(
    "word", ["time", "TIME", "freq", "hertz", "vt", "temp", "temper", "gmin", "pi", "exp"]
)
def test_a_reserved_word_is_rejected_as_a_parameter(word: str) -> None:
    for line in (f".param {word}=1", f".param a=1, {word}=2", f".global_param {word}=1"):
        with pytest.raises(ParseError, match="is a reserved word"):
            _parse(f"t\n{line}\n.END\n")
    # A longer name is an ordinary one.
    assert _values(f".param {word}x=1") == [(f"{word}x", "NumericValue", "")]


def test_param_function_assignments() -> None:
    line = ".PARAM FTEST(X)='2*X' B=12.0 SUM(A,B,C)={A+B+C}"
    statement = _statement(line)
    assert [a.name for a in statement.assignments] == ["B"]
    (ftest, total) = statement.functions
    assert ftest == FunctionDefinition(
        "FTEST",
        Span(9, 14),
        (Identifier("X", Span(15, 16)),),
        Formula("2*X", "'", Span(18, 23)),
        Span(9, 23),
    )
    assert total.name == "SUM"
    assert [arg.name for arg in total.args] == ["A", "B", "C"]
    assert total.body.text == "A+B+C"


@pytest.mark.parametrize(
    "line",
    [
        ".param f(x)={x}",
        ".param f(x) = {x}",
        ".param f( x , y )={x}",
        ".param a=1, f(x)={x}",
        ".param f#(x)={x}",
        ".param f(x)={x},\n+ g(y)='y'",
    ],
)
def test_param_function_forms(line: str) -> None:
    assert _statement(line).functions[0].name.startswith("f")


@pytest.mark.parametrize(
    "line",
    [".param f(x)x", ".param f(x) {x}", ".param f (x)={x}", ".param f(x)=x", ".param f(x)=1"],
)
def test_a_param_function_needs_its_equals_and_a_delimited_body(line: str) -> None:
    with pytest.raises(ParseError):
        _parse(f"t\n{line}\n.END\n")


def test_global_param_is_a_top_level_param() -> None:
    statement = _statement(".GLOBAL_PARAM T={27+100*time}, A=1 B=2")
    assert isinstance(statement, GlobalParamStatement)
    assert isinstance(statement, ParamStatement)
    assert statement.keyword == ".GLOBAL_PARAM"
    assert [a.name for a in statement.assignments] == ["T", "A", "B"]


def test_global_param_defines_no_function() -> None:
    with pytest.raises(ParseError, match="defines no function"):
        _parse("t\n.global_param f(x)={x}\n.END\n")


@pytest.mark.parametrize(
    ("line", "name", "args", "body"),
    [
        (".FUNC E(x) {exp(x)}", "E", ["x"], "exp(x)"),
        (".func DECAY(CNST) {E(-CNST*TIME)}", "DECAY", ["CNST"], "E(-CNST*TIME)"),
        (".func MIN3(A,B,C) {MIN(A,MIN(B,C))}", "MIN3", ["A", "B", "C"], "MIN(A,MIN(B,C))"),
        (".func SUM(A,B,C)={A+B+C}", "SUM", ["A", "B", "C"], "A+B+C"),
        (".func f(x) = 'x*2'", "f", ["x"], "x*2"),
        (".func f(x){x}", "f", ["x"], "x"),
        (".func f() {1}", "f", [], "1"),
        (".func f#@`(x) {x}", "f#@`", ["x"], "x"),
        (".func f(x)\n+ {x} ; c", "f", ["x"], "x"),
    ],
)
def test_func_defines_one_function(line: str, name: str, args: list[str], body: str) -> None:
    statement = _statement(line)
    assert isinstance(statement, FuncStatement)
    function = statement.function
    assert function.name == name
    assert [arg.name for arg in function.args] == args
    assert function.body.text == body
    text = f"t\n{line}\n.END\n"
    assert text[function.name_span.start : function.name_span.end] == name


@pytest.mark.parametrize(
    "line",
    [".func f(x) x", ".func f(x) {x} g(y) {y}", ".func f (x) {x}", ".func f(x)", '.func f(x) "x"'],
)
def test_a_func_without_a_body_or_with_two_is_rejected(line: str) -> None:
    with pytest.raises(ParseError):
        _parse(f"t\n{line}\n.END\n")


@pytest.mark.parametrize("name", ["sin", "SQRT", "if", "table", "r", "m", "exp", "pi", "time"])
def test_a_builtin_function_name_is_rejected(name: str) -> None:
    # The manual forbids it ([xyce-ref] §2.1.10 p42); Xyce ignores the definition (discrepancies).
    for line in (f".func {name}(x) {{x}}", f".param {name}(x)={{x}}"):
        with pytest.raises(ParseError, match="built-in function or a reserved word"):
            _parse(f"t\n{line}\n.END\n")


@pytest.mark.parametrize("arg", ["pi", "exp", "time", "TEMP"])
def test_a_reserved_word_is_rejected_as_an_argument(arg: str) -> None:
    for line in (f".func f({arg}) {{1}}", f".param f(a,{arg})={{1}}"):
        with pytest.raises(ParseError, match="cannot be a function argument"):
            _parse(f"t\n{line}\n.END\n")


def test_the_builtin_lists_agree() -> None:
    # The grammar's BUILTIN_OPEN and formula-reserved.json list the same names.
    import re

    from lark import Lark

    lark = Lark.open_from_package("netlistmod.grammar", "xyce.lark", parser=None, lexer="basic")
    pattern = lark.get_terminal("BUILTIN_OPEN").pattern.value
    names = set(re.search(r"\(\?:([^)]*)\)", pattern).group(1).split("|"))  # type: ignore[union-attr]
    assert names == builtin_functions(_XYCE) | reserved_words(_XYCE)


def _tokens(text: str) -> list[tuple[str, str]]:
    found = parse_formula(text, _XYCE)
    assert found is not None, text
    return [(token.kind, token.text) for token in found]


def test_the_formula_grammar_reads_xyce_operators() -> None:
    assert _tokens("a**2 ^ b | c & ~d % e") == [
        ("parameter", "a"),
        ("parameter", "b"),
        ("parameter", "c"),
        ("parameter", "d"),
        ("parameter", "e"),
    ]
    assert _tokens("a==b ? c : d") == [("parameter", n) for n in "abcd"]
    assert parse_formula("a && c", _XYCE) is None
    assert parse_formula("!a", _XYCE) is None
    assert parse_formula("a\\b", _XYCE) is None


def test_the_formula_grammar_reads_names_numbers_calls_and_accessors() -> None:
    assert _tokens("f(x.y, a#b) + sin(c) * 1kj * 1mil * 2.5e-3hz") == [
        ("function", "f"),
        ("parameter", "x.y"),
        ("parameter", "a#b"),
        ("function", "sin"),
        ("parameter", "c"),
    ]
    assert _tokens("V(X1:A) - V(a, b) + I(V1) + vdb(o)") == [
        ("node", "X1:A"),
        ("node", "a"),
        ("node", "b"),
        ("source", "V1"),
        ("node", "o"),
    ]
    assert _tokens("pi*exp*temp*time*freq*vt*gmin*hertz*temper") == [
        ("reserved", word)
        for word in ["pi", "exp", "temp", "time", "freq", "vt", "gmin", "hertz", "temper"]
    ]


@pytest.mark.parametrize("text", ["a?b:c", "1kohm", "1kk", "a[1]", "1e"])
def test_the_formula_grammar_refuses_what_xyce_refuses(text: str) -> None:
    # `b:c` is a name, as the manual warns (p165); the number readers' refusals.
    assert parse_formula(text, _XYCE) is None
