"""LTspice structure, comments, dot-commands and names (M8 T3; decision 0009)."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    BlankLine,
    CommentLine,
    Dialect,
    End,
    OpaqueStatement,
    ParseError,
    Resistor,
    SourceText,
    Span,
    SubcktDefinition,
    Title,
    TitleDirective,
    UnknownDirective,
    UnsupportedConstruct,
    parse,
)
from netlistmod.grammar.loader import build_parser, pending_dialects, registered_dialects


def _parse(text: str) -> Any:
    return parse(SourceText(text), Dialect.LTSPICE)


def _item(statement: str) -> Any:
    result = _parse(f"title\n{statement}\n.end\n")
    assert len(result.items) == 3, result.items
    return result.items[1]


def _reject(statement: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        _parse(f"title\n{statement}\n.end\n")
    return captured.value


def test_ltspice_is_registered_and_builds_strict() -> None:
    assert Dialect.LTSPICE in registered_dialects()
    assert not pending_dialects()
    assert build_parser(Dialect.LTSPICE).options.strict


def test_the_parse_result_carries_the_dialect() -> None:
    assert _parse("t\n.end\n").dialect is Dialect.LTSPICE


def test_rkm_option_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="applies only to ngspice"):
        parse(SourceText("t\n.end\n"), Dialect.LTSPICE, rkm=True)


@pytest.mark.parametrize(
    ("text", "kinds"),
    [
        ("t\n.end\n", [Title, End]),
        ("t\n.END", [Title, End]),
        ("t\n.end\n\n  \n", [Title, End, BlankLine, BlankLine]),
        ("t\n.end ; a comment\n", [Title, End]),
        ("t\n.end ; a comment", [Title, End]),
        ("\n.end\n", [Title, End]),
        (".title x\n.end\n", [Title, End]),
        ("t\n.title later ; kept\n.end\n", [Title, TitleDirective, End]),
    ],
)
def test_top_level_shape(text: str, kinds: list[type]) -> None:
    result = _parse(text)
    assert [type(item) for item in result.items] == kinds
    assert result.items[-1].span.end == len(text)


@pytest.mark.parametrize(
    "text",
    ["t\nR1 a 0 1k\n", "t\n.end\nR1 a 0 1k\n", "t\n.end foo\n", "t\n.end\n; comment\n"],
)
def test_end_is_required_with_only_blank_lines_after_it(text: str) -> None:
    # Decision 0009: a deliberate exception to §11.3 rule 2; LTspice runs the first two.
    with pytest.raises(ParseError):
        _parse(text)


@pytest.mark.parametrize("line", ["* star", "; semicolon", "   * indented", "\t; tabbed"])
def test_comment_lines(line: str) -> None:
    comment = _item(line)
    assert isinstance(comment, CommentLine)
    assert comment.text == line.strip()


def test_dollar_does_not_start_a_comment_line() -> None:
    assert _reject("$ comment").column == 1
    assert _reject("// comment").column == 1


@pytest.mark.parametrize(
    ("line", "comment"),
    [
        ("R1 a 0 1k ; c", "; c"),
        ("R1 a 0 1k;c", ";c"),
        ("R1 a 0 1k $ c", "$ c"),
        ("R1 a 0 1k  $  c", "$  c"),
        ("R1 a 0 {1k} $ c ; d", "$ c ; d"),
    ],
)
def test_end_of_line_comments(line: str, comment: str) -> None:
    element = _item(line)
    assert isinstance(element, Resistor)
    assert [line[span.start - 6 : span.end - 6] for span in element.trailing_comments] == [comment]


@pytest.mark.parametrize(
    "line",
    ["R1 a 0 1k$ c", "R1 a 0 1k $c", "R1 a 0 1k $", "R1 a 0 1k\t$ c", "R1 a 0 1k $\tc"],
)
def test_dollar_needs_a_space_on_both_sides(line: str) -> None:
    # Each of these stops LTspice 26.1.1 ("Unknown parameter").
    _reject(line)


@pytest.mark.parametrize("line", ["R1 a 0 1k // c", "R1 a 0 1k//c", ".param x=1 // c"])
def test_double_slash_is_not_a_comment(line: str) -> None:
    _reject(line)


def test_dollar_and_slashes_in_names_and_statement_text() -> None:
    assert _item("R1 a$b $G_x 1k").nodes[1].name == "$G_x"
    assert _item("R1 a//b 0 1k").nodes[0].name == "a//b"
    included = _item(".include sub//dir\\h$.inc ; c")
    assert isinstance(included, OpaqueStatement)
    assert included.raw.rstrip() == ".include sub//dir\\h$.inc"
    assert len(included.trailing_comments) == 1


def test_continuation_must_follow_immediately() -> None:
    element = _item("R1 a 0\n+ 1k ; c\n+ m=2")
    assert isinstance(element, Resistor) and element.params[0].name == "m"
    assert _item("R1 a 0 ; before the value\n+ 1k").value.text == "1k"
    # LTspice joins across these (discrepancies.md); the library keeps the strict rule.
    _reject("R1 a 0\n* c\n+ 1k")
    _reject("R1 a 0\n\n+ 1k")


_COMMENT_ONLY_LAST_LINE = "a `+` line that holds only a comment cannot end a statement"


# (statement, line and column of the refused "+" in the netlist; line 1 is the title)
_COMMENT_ONLY_ENDS: dict[str, tuple[str, int, int]] = {
    "semicolon": ("R1 a 0 1k\n+ ; note", 3, 1),
    "semicolon-no-blank": ("R1 a 0 1k\n+;note", 3, 1),
    "tab": ("R1 a 0 1k\n+\t; note", 3, 1),
    "dollar": ("R1 a 0 1k\n+ $ note", 3, 1),
    "indented": ("R1 a 0 1k\n  + ; note", 3, 3),
    "blank-plus-after": ("R1 a 0 1k\n+ ; note\n+", 3, 1),
    "blanks-plus-after": ("R1 a 0 1k\n+ ; note\n+   ", 3, 1),
    "two-comments": ("R1 a 0 1k\n+ ; c1\n+ ; c2", 4, 1),
    "after-a-value-line": ("R1 a 0\n+ 1k\n+ ; note", 4, 1),
    "param": (".param p=1\n+ ; c", 3, 1),
    "model": (".model dd D(Is=1e-14)\n+ ; c", 3, 1),
    "untyped": (".backanno\n+ ; c", 3, 1),
    "tran": (".tran 1m\n+ ; c", 3, 1),
    "x-line": ("X1 a s\n+ ; c", 3, 1),
    "b-line": ("B1 b 0 V=V(a)*2\n+ ; c", 3, 1),
    "a-line": ("A1 a 0 0 0 0 nq q 0 BUF\n+ ; c", 3, 1),
    "subckt-header": (".subckt s p\n+ ; c\nR1 p 0 1k\n.ends", 3, 1),
    "ends": (".subckt s p\nR1 p 0 1k\n.ends\n+ ; c", 5, 1),
}


@pytest.mark.parametrize("case", sorted(_COMMENT_ONLY_ENDS))
def test_a_comment_only_plus_line_may_not_end_a_statement(case: str) -> None:
    # LTspice 26.1.1 stops on each ("Syntax error"; tests/solver/test_ltspice_m18_probes.py),
    # except the .subckt header with ports only, which it runs (discrepancies.md).
    statement, line, column = _COMMENT_ONLY_ENDS[case]
    error = _reject(statement)
    assert (error.line, error.column) == (line, column)
    assert error.reason.startswith(_COMMENT_ONLY_LAST_LINE)
    assert error.expected == ()


@pytest.mark.parametrize("ending", ["\n", "\r\n"])
def test_a_comment_only_plus_line_is_refused_before_end_with_either_line_ending(
    ending: str,
) -> None:
    text = ending.join(["title", "R1 a 0 1k", "+ ; note", ".end", ""])
    with pytest.raises(ParseError) as captured:
        _parse(text)
    assert (captured.value.line, captured.value.column) == (3, 1)
    assert captured.value.reason.startswith(_COMMENT_ONLY_LAST_LINE)


@pytest.mark.parametrize(
    "statement",
    [
        "R1 a 0\n+ ; note\n+ 1k",
        "R1 a 0 1k\n+ ; note\n+ tc=0",
        "R1 a 0\n+ ; c1\n+ ; c2\n+ 1k",
        "R1 a 0\n+\n+ ; c\n+ 1k",
        "R1 a 0 1k\n+",
        "R1 a 0 1k\n+   ",
        ".param p=1\n+ ; c\n+ q=2",
        ".model dd D(Is=1e-14\n+ ; c\n+ N=1)",
        ".model dd D(Is=1e-14\n+ ; c\n+ )",
        ".subckt s p params: r=1k\n+ ; c\n+ q=2\n.ends",
        "R1 a 0 1k ; same line",
        "R1 a 0\n+ 1k ; after the value",
    ],
)
def test_a_comment_only_plus_line_before_a_field_continues(statement: str) -> None:
    # LTspice 26.1.1 runs each (tests/solver/test_ltspice_m18_probes.py).
    _parse(f"title\n{statement}\n.end\n")


def test_a_comment_only_plus_line_after_a_comment_line_keeps_the_general_error() -> None:
    error = _reject("* c\n+ ; c")
    assert (error.line, error.column) == (3, 1)
    assert not error.reason.startswith(_COMMENT_ONLY_LAST_LINE)


@pytest.mark.parametrize("statement", ["R1 a 0 1k\n+ ; note", ".param p=1\n+ ; c", "X1 a s\n+ ; c"])
def test_ngspice_still_reads_a_comment_only_plus_line(statement: str) -> None:
    # ngspice 47 runs these (tests/solver/test_ltspice_m18_probes.py); its grammar is unchanged.
    parse(SourceText(f"title\n{statement}\n.end\n"), Dialect.NGSPICE)


@pytest.mark.parametrize("line", ["R1 a 0 1k \\\\\nm=2", "R1 a 0 \\\\\n1k", "\\\\"])
def test_backslash_continuation_is_rejected(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize(
    "line",
    [".backanno", ".func f(x) {x*2}"],
)
def test_untyped_commands_allowed_in_a_body(line: str) -> None:
    assert isinstance(_item(line), UnknownDirective)
    definition = _item(f".subckt s a\n{line}\n.ends")
    assert isinstance(definition, SubcktDefinition)
    assert isinstance(definition.body[0], UnknownDirective)


@pytest.mark.parametrize(
    "line",
    [
        ".four 1k V(a)",
        ".noise V(a) V1 dec 1 1 10",
        ".tf V(a) V1",
        ".fra",
        ".wave o.wav 16 1k V(a)",
        ".net V(a) V1",
        ".savebias b.txt",
        ".savestate",
        ".loadstate",
        ".FOUR 1k V(a)",
    ],
)
def test_untyped_commands_top_level_only(line: str) -> None:
    command = _item(line)
    assert isinstance(command, UnknownDirective)
    assert command.raw == line
    error = _reject(f".subckt s a\n{line}\n.ends")
    assert "not allowed inside a subcircuit" in str(error)


@pytest.mark.parametrize(
    "line",
    [
        ".foo bar",
        ".tarn 1m",
        ".print tran v(a)",
        ".plot tran v(a)",
        ".width out=80",
        ".probe",
        ".control",
        ".if (1)",
        ".endc",
        ".endif",
        ".else",
        ".ends",
        ".endl",
        ".endmachine",
        ".state a 0",
    ],
)
def test_other_dot_commands_are_errors(line: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, 1)
    assert "not an LTspice dot-command" in str(error)
    assert line.split()[0] in str(error)


def test_machine_block_is_unsupported() -> None:
    with pytest.raises(UnsupportedConstruct, match="machine"):
        _parse("t\n.machine\n.state a 0\n.rule a a 1\n\n.endmachine\n.end\n")
    with pytest.raises(UnsupportedConstruct, match="machine"):
        _parse("t\n.subckt s a\n.machine\n.endmachine\n.ends\n.end\n")
    with pytest.raises(ParseError, match=r"`\.endmachine` is missing"):
        _parse("t\n.machine\n.state a 0\n")


@pytest.mark.parametrize(
    ("line", "kind", "raw"),
    [
        (".include h.inc", "include", ".include h.inc"),
        (".INCLUDE h.inc ; c", "include", ".INCLUDE h.inc"),
        (".inc h.inc", "include", ".inc h.inc"),
        ('.include "a b.inc"', "include", '.include "a b.inc"'),
        (".lib h.inc", "lib", ".lib h.inc"),
        (".lib h.inc sec", "lib", ".lib h.inc sec"),
    ],
)
def test_opaque_statements(line: str, kind: str, raw: str) -> None:
    item = _item(line)
    assert isinstance(item, OpaqueStatement)
    assert (item.kind, item.raw.rstrip()) == (kind, raw)


@pytest.mark.parametrize("line", [".include h.inc\n+ more", ".lib h.inc\n+ sec"])
def test_opaque_statements_cannot_be_continued(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize(
    "name",
    ["o[1]", "a%b", "a<b>", "a~b", "a\\b", "a/b", "a//b", "x1:n", "a#b", "a!b", "a@b", "a&b", "a^b"]
    + ["a*b", "a?b", "a-b", "a+b", "a.b", "a_b", "§", "Ä", "$G_x", "00"],
)
def test_node_names_are_any_string_without_excluded_characters(name: str) -> None:
    element = _item(f"R1 {name} 0 1k")
    assert element.nodes[0].name == name
    assert element.nodes[0].span.length == len(name)


@pytest.mark.parametrize("character", ["(", ")", "{", "}", "=", ",", "'", '"', "|"])
def test_excluded_name_characters(character: str) -> None:
    _reject(f"R1 a{character}b 0 1k")


@pytest.mark.parametrize("designator", ["R§2", "R[2]", "R/2", "R:2", "r_1"])
def test_designators_use_the_same_characters(designator: str) -> None:
    assert _item(f"{designator} a 0 1k").designator == designator


def test_spans_tile_the_source() -> None:
    text = (
        "title\r\n* c\r\n; d\nR1 a 0 1k $ e\r\nR2 a 0\n+ 1k\n\n.step param x 1 2 1 ; f\n"
        ".subckt s p\nR1 p 0 1\n.ends\n.end ; g\r\n\n"
    )
    result = _parse(text)
    cursor = 0
    for item in result.items:
        assert item.span.start == cursor
        cursor = item.span.end
    assert cursor == len(text)
    assert isinstance(result.items[1], CommentLine)
    assert result.items[1].span == Span(7, 12)
