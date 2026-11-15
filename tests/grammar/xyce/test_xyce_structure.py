"""The structure-only xyce grammar of X-M0 (decision 0026): the title, `*` comments, blank lines
and `.END`, and the refusal of every other line."""

from __future__ import annotations

from typing import Any

import pytest
from lark.exceptions import VisitError

from netlistmod import (
    BlankLine,
    CommentLine,
    End,
    ParseError,
    SourceText,
    Span,
    Title,
    UnsupportedConstruct,
    parse,
)
from netlistmod.dialects import _XYCE
from netlistmod.grammar.loader import build_parser, device_matrix, parse_tree, registered_dialects
from netlistmod.model.transform import _NodeBuilder


def _parse(text: str) -> Any:
    return parse(SourceText(text), _XYCE)


def _kinds(text: str) -> list[type]:
    return [type(item) for item in _parse(text).items]


def _tiles(text: str) -> None:
    position = 0
    for item in _parse(text).items:
        assert item.span.start == position
        position = item.span.end
    assert position == len(text)


def test_xyce_is_registered_and_builds_strict() -> None:
    assert _XYCE in registered_dialects()
    parser = build_parser(_XYCE)
    assert parser.options.strict is True
    assert parser.options.parser == "lalr"
    assert parser.options.lexer == "contextual"
    assert _parse("t\n.END\n").dialect is _XYCE


def test_the_first_line_is_always_the_title() -> None:
    (title, end) = _parse("Test RLC Circuit\n.END\n").items
    assert title == Title("Test RLC Circuit", False, Span(0, 17))
    assert isinstance(end, End)
    # A first line that looks like a statement, or that is blank, is still the title.
    assert _parse("R1 a 0 1k\n.END\n").items[0].text == "R1 a 0 1k"
    assert _parse(".END\n.END\n").items[0].text == ".END"
    assert _parse(".param x=1\n.END\n").items[0].text == ".param x=1"
    assert _parse("\n.END\n").items[0] == Title("", False, Span(0, 1))
    assert _parse("  \n.END\n").items[0].text == ""


def test_title_comments_blank_lines_and_end_tile_the_source() -> None:
    text = "title\n* one\n\n   \n*two\n  * indented\n.END\n\n"
    assert _kinds(text) == [
        Title,
        CommentLine,
        BlankLine,
        BlankLine,
        CommentLine,
        CommentLine,
        End,
        BlankLine,
    ]
    _tiles(text)
    assert _parse(text).items[1].text == "* one"
    assert _parse(text).items[5].text == "* indented"


def test_crlf_and_a_missing_final_newline() -> None:
    text = "title\r\n* c\r\n.END\r\n"
    assert _kinds(text) == [Title, CommentLine, End]
    _tiles(text)
    assert _kinds("title\n.END") == [Title, End]
    _tiles("title\n.END   ")


@pytest.mark.parametrize("end", [".END", ".end", ".End"])
def test_end_is_case_insensitive(end: str) -> None:
    assert _kinds(f"title\n{end}\n") == [Title, End]


def test_end_is_required() -> None:
    for text in ("title\n", "title\n* c\n", "title\n\n"):
        with pytest.raises(ParseError, match="must end with"):
            _parse(text)
    with pytest.raises(ParseError):
        _parse("")


def test_end_is_last_with_only_blank_lines_after_it() -> None:
    for after in ("* c", "R1 a 0 1k", ".END", ".param x=1", "+ x"):
        with pytest.raises(ParseError) as captured:
            _parse(f"title\n.END\n{after}\n")
        assert captured.value.line == 3
    for text in ("title\n.END x\n", "title\n.END ; c\n"):
        with pytest.raises(ParseError) as captured:
            _parse(text)
        assert captured.value.line == 2


@pytest.mark.parametrize("letter", sorted(device_matrix(_XYCE)))
def test_every_element_line_is_unsupported(letter: str) -> None:
    with pytest.raises(UnsupportedConstruct, match="not yet supported on Xyce") as captured:
        _parse(f"title\n{letter}1 a 0 1\n.END\n")
    error = captured.value
    assert (error.line, error.column) == (2, 1)
    assert error.construct.startswith(f"{letter} device, not yet supported on Xyce (planned for ")
    assert str(device_matrix(_XYCE)[letter]["milestone"]) in error.construct
    with pytest.raises(UnsupportedConstruct):
        _parse(f"title\n{letter.lower()}1 a 0 1\n.END\n")


def test_every_device_letter_is_planned() -> None:
    matrix = device_matrix(_XYCE)
    assert {entry["status"] for entry in matrix.values()} == {"planned"}
    # A and N are not Xyce letters ([xyce-ref] Table 2-35 p177–178).
    assert "A" not in matrix
    assert "N" not in matrix


@pytest.mark.parametrize("letter", ["A", "N"])
def test_a_letter_xyce_does_not_have_is_rejected(letter: str) -> None:
    with pytest.raises(ParseError) as captured:
        _parse(f"title\n{letter}1 a 0 1\n.END\n")
    assert (captured.value.line, captured.value.column) == (2, 1)


@pytest.mark.parametrize(
    "statement",
    [
        ".param x=1",
        ".PARAM x=1",
        ".tran 1n 1u",
        ".subckt s a b",
        ".ends",
        ".endl",
        ".include 'x.cir'",
        ".lib x.lib tt",
        ".global_param g=1",
        ".preprocess replaceground true",
        ".options timeint method=gear",
        ".print tran v(1) ; comment $ and // are text here",
        ".title other",
        ".unknown_command",
    ],
)
def test_every_other_dot_command_is_unsupported(statement: str) -> None:
    with pytest.raises(UnsupportedConstruct, match="not yet supported on Xyce") as captured:
        _parse(f"title\n{statement}\n.END\n")
    error = captured.value
    assert (error.line, error.column) == (2, 1)
    assert error.construct == f"dot-command `{statement.split()[0]}`, not yet supported on Xyce"


def test_a_continued_dot_command_is_unsupported_whole() -> None:
    with pytest.raises(UnsupportedConstruct) as captured:
        _parse("title\n.param x=1\n+ y=2\n.END\n")
    assert captured.value.line == 2


def test_a_syntax_error_later_is_reported_before_an_unsupported_line() -> None:
    # The whole source is parsed first, as on the other dialects.
    with pytest.raises(ParseError):
        _parse("title\n.param x=1\n")


@pytest.mark.parametrize("between", ["* a comment\n", "\n", "* a comment\n\n", "; c\n"])
@pytest.mark.parametrize("plus", ["+ y=2", "  + y=2"])
def test_a_continuation_after_comment_or_blank_lines_is_not_a_syntax_error(
    between: str, plus: str
) -> None:
    # A `+` line joins the last non-comment line across comment and blank lines ([xyce-ug]
    # §4.1.3.2 p43; probe test_a_continuation_joins_across_comments_and_blank_lines): the
    # statement it joins is refused, not the `+` line.
    with pytest.raises(UnsupportedConstruct, match="dot-command `.param`") as captured:
        _parse(f"title\n.param x=1\n{between}{plus}\n.END\n")
    assert (captured.value.line, captured.value.column) == (2, 1)


def test_a_continuation_line_is_refused_by_its_own_rule() -> None:
    # Every statement X-M0 recognises is refused before the `+` line that follows it, so the
    # rule's own refusal is checked on its subtree.
    source = SourceText("title\n.param x=1\n* c\n+ y=2\n.END\n")
    (subtree,) = parse_tree(source, _XYCE).find_data("continuation_line")
    with pytest.raises(VisitError) as captured:
        _NodeBuilder(source, _XYCE).transform(subtree)
    error = captured.value.orig_exc
    assert isinstance(error, UnsupportedConstruct)
    assert error.construct == (
        "`+` continuation line after a comment or blank line; not yet supported on Xyce"
    )
    assert (error.line, error.column) == (4, 1)


@pytest.mark.parametrize("before", ["", "* c\n", "\n", "; c\n", "* c\n\n"])
def test_a_continuation_with_only_the_title_before_it_is_rejected(before: str) -> None:
    # The title is a comment ([xyce-ug] §4.1.3.1 p42), so there is no line to join; Xyce fails
    # too (probe test_a_continuation_never_joins_the_title).
    text = f"title\n{before}+ x\n.END\n"
    with pytest.raises(ParseError) as captured:
        _parse(text)
    assert captured.value.line == text.count("\n", 0, text.index("+")) + 1


@pytest.mark.parametrize("line", [";", "; a comment", ";* not a star comment"])
def test_a_line_that_begins_with_a_semicolon_is_unsupported(line: str) -> None:
    # An in-line comment may occur on any line ([xyce-ug] §4.1.3.1 p43), so a line that begins
    # with `;` is valid; X-M1 reads it.
    with pytest.raises(UnsupportedConstruct) as captured:
        _parse(f"title\n* c\n{line}\n.END\n")
    assert captured.value.construct == (
        "line that begins with `;`, an in-line comment; not yet supported on Xyce"
    )
    assert (captured.value.line, captured.value.column) == (3, 1)


def test_an_indented_line_is_unsupported() -> None:
    # Xyce reads an indented line as a comment ([xyce-ug] §4.1.3.1 p43); decision X-D1 is X-M1's.
    for line in ("  .param x=1", "\tR1 a 0 1k", "  hello"):
        with pytest.raises(UnsupportedConstruct, match="indented line") as captured:
            _parse(f"title\n{line}\n.END\n")
        assert (captured.value.line, captured.value.column) == (2, 1)
    # An indented `.END` is such a comment, so the netlist has no `.END`.
    with pytest.raises(ParseError, match="must end with"):
        _parse("title\n  .END\n")


@pytest.mark.parametrize("line", ["$ comment", "// comment", "+ continued"])
def test_other_line_starts_are_rejected(line: str) -> None:
    # `$` and `//` start no comment on Xyce or in the manual's comment rules (probe
    # test_dollar_and_double_slash_do_not_end_a_line); a `+` on line 2 joins only the title.
    with pytest.raises(ParseError) as captured:
        _parse(f"title\n{line}\n.END\n")
    assert (captured.value.line, captured.value.column) == (2, 1)


def test_rkm_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="applies only to ngspice"):
        parse(SourceText("t\n.END\n"), _XYCE, rkm=True)
