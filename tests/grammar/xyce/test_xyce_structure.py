"""The structure of the xyce grammar (decision 0026; X-M1 B2, decision 0027 items 1 and 2): the
title, `*` and `;` comments, blank lines, indented lines, `+` continuation across them, `.END`, and
the refusal of the lines the dialect does not read yet."""

from __future__ import annotations

from typing import Any

import pytest
from lark.exceptions import VisitError

from netlistmod import (
    BlankLine,
    CommentLine,
    End,
    GlobalDirective,
    Node,
    ParseError,
    SourceText,
    Span,
    Title,
    UnsupportedConstruct,
    parse,
)
from netlistmod.dialects import _XYCE
from netlistmod.grammar.loader import build_parser, device_matrix, parse_tree, registered_dialects
from netlistmod.model.nodes import IndentedLine
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
    for after in ("* c", "; c", "  indented", "R1 a 0 1k", ".END", ".param x=1", "+ x"):
        with pytest.raises(ParseError) as captured:
            _parse(f"title\n.END\n{after}\n")
        assert captured.value.line == 3
    # Nothing but a `;` comment may follow `.END` on its line (decision 0027 item 2).
    for text in ("title\n.END x\n", "title\n.END x ; c\n"):
        with pytest.raises(ParseError) as captured:
            _parse(text)
        assert captured.value.line == 2


@pytest.mark.parametrize("comment", [" ; c", "; c", ";", "\t;c ; d"])
def test_end_may_end_with_a_semicolon_comment(comment: str) -> None:
    # `;` may end any line ([xyce-ug] §4.1.3.1 p43), so also the `.END` line.
    for ending in ("\n", "\n\n", ""):
        text = f"title\n.END{comment}{ending}"
        assert _kinds(text)[:2] == [Title, End]
        _tiles(text)


@pytest.mark.parametrize(
    "letter",
    sorted(k for k, v in device_matrix(_XYCE).items() if v["status"] == "planned"),
)
def test_every_element_line_is_unsupported(letter: str) -> None:
    with pytest.raises(UnsupportedConstruct, match="not yet supported on Xyce") as captured:
        _parse(f"title\n{letter}1 a 0 1\n.END\n")
    error = captured.value
    assert (error.line, error.column) == (2, 1)
    assert error.construct.startswith(f"{letter} device, not yet supported on Xyce (planned for ")
    assert str(device_matrix(_XYCE)[letter]["milestone"]) in error.construct
    with pytest.raises(UnsupportedConstruct):
        _parse(f"title\n{letter.lower()}1 a 0 1\n.END\n")


def test_the_x_m1_letters_are_supported_and_the_rest_planned() -> None:
    matrix = device_matrix(_XYCE)
    supported = {letter for letter, entry in matrix.items() if entry["status"] == "supported"}
    assert supported == set("CDIKLRVX")
    assert all(matrix[letter]["milestone"] == "X-M1" for letter in supported)
    assert {entry["status"] for entry in matrix.values()} == {"planned", "supported"}
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
        ".four 1k v(1)",
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
        _parse("title\n.print tran\n+ v(1)\n.END\n")
    assert captured.value.line == 2


def test_a_syntax_error_later_is_reported_before_an_unsupported_line() -> None:
    # The whole source is parsed first, as on the other dialects.
    with pytest.raises(ParseError):
        _parse("title\n.print tran v(1)\n")


@pytest.mark.parametrize("between", ["* a comment\n", "\n", "* a comment\n\n", "; c\n"])
@pytest.mark.parametrize("plus", ["+ 1u", "  + 1u"])
def test_a_continuation_after_comment_or_blank_lines_is_not_a_syntax_error(
    between: str, plus: str
) -> None:
    # A `+` line joins the last non-comment line across comment and blank lines ([xyce-ug]
    # §4.1.3.2 p43; probe test_a_continuation_joins_across_comments_and_blank_lines): the
    # statement it joins is refused, not the `+` line.
    with pytest.raises(UnsupportedConstruct, match="dot-command `.print`") as captured:
        _parse(f"title\n.print tran\n{between}{plus}\n.END\n")
    assert (captured.value.line, captured.value.column) == (2, 1)


def test_a_continuation_line_is_refused_by_its_own_rule() -> None:
    # Every statement X-M0 recognises is refused before the `+` line that follows it, so the
    # rule's own refusal is checked on its subtree.
    source = SourceText("title\n.print tran\n* c\n+ 1u\n.END\n")
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


@pytest.mark.parametrize("line", [";", "; a comment", ";* not a star comment", "  ; indented"])
def test_a_line_that_begins_with_a_semicolon_is_a_comment(line: str) -> None:
    # An in-line comment may occur on any line ([xyce-ug] §4.1.3.1 p43), so a line that begins
    # with `;` is a comment line, indented or not (decision 0027 item 2).
    text = f"title\n* c\n{line}\n.END\n"
    items = _parse(text).items
    assert [type(item) for item in items] == [Title, CommentLine, CommentLine, End]
    assert items[2].text == line.lstrip()
    _tiles(text)


@pytest.mark.parametrize("line", ["  .param x=1", "\tR1 a 0 1k", "  hello", " .END", "\tx"])
def test_an_indented_line_is_its_own_kind_of_comment(line: str) -> None:
    # Xyce reads an indented line as a comment ([xyce-ug] §4.1.3.1 p43); decision X-D1 reads it
    # as a node of its own kind, with its blanks (decision 0027 item 1).
    text = f"title\n{line}\n.END\n"
    items = _parse(text).items
    assert [type(item) for item in items] == [Title, IndentedLine, End]
    assert items[1] == IndentedLine(line, Span(6, 6 + len(line) + 1))
    _tiles(text)


def test_an_indented_end_is_not_the_end() -> None:
    # An indented `.END` is such a comment, so the netlist has no `.END`.
    with pytest.raises(ParseError, match="must end with"):
        _parse("title\n  .END\n")


def test_indented_star_and_plus_lines_are_not_indented_lines() -> None:
    # An indented `*` line is a comment, and an indented `+` line continues (decision 0027 item 1).
    assert _kinds("title\n  * c\n.END\n") == [Title, CommentLine, End]
    directive = _parse("t\n.global a\n  + b\n.END\n").items[1]
    assert isinstance(directive, GlobalDirective)
    assert [node.name for node in directive.nodes] == ["a", "b"]


@pytest.mark.parametrize(
    ("between", "comments"),
    [
        ("", []),
        ("* c\n", ["* c"]),
        ("\n", []),
        ("   \n", []),
        ("; c\n", ["; c"]),
        ("  ; c\n", ["  ; c"]),
        ("  indented\n", ["  indented"]),
        ("* a\n\n  b\n;c\n", ["* a", "  b", ";c"]),
    ],
)
def test_a_continuation_joins_across_blank_comment_and_indented_lines(
    between: str, comments: list[str]
) -> None:
    # A `+` line joins the last line that is not a comment, across blank, `*`, `;` and indented
    # lines ([xyce-ug] §4.1.3.2 p43; decision 0027 item 2). The lines between belong to the
    # statement, and their comments are its trailing comments, an indented one with its blanks.
    text = f"title\n.global a ; first\n{between}+ b\n.END\n"
    items = _parse(text).items
    assert [type(item) for item in items] == [Title, GlobalDirective, End]
    directive = items[1]
    b = text.index("+ b") + 2
    assert directive.nodes == (Node("a", Span(14, 15)), Node("b", Span(b, b + 1)))
    assert directive.span == Span(6, text.index(".END"))
    found = [text[span.start : span.end] for span in directive.trailing_comments]
    assert found == ["; first", *comments]
    _tiles(text)


def test_a_continuation_line_may_hold_only_a_comment() -> None:
    # A `+` line holding only `;` is fine ([xyce-ug] §4.1.3.2 p43), after comment lines too.
    for text in ("t\n.global a\n+ ; c\n.END\n", "t\n.global a\n* c\n+;\n+ b\n.END\n"):
        assert _kinds(text) == [Title, GlobalDirective, End]
        _tiles(text)


def test_a_comment_line_not_followed_by_a_continuation_ends_the_statement() -> None:
    text = "t\n.global a\n* c\n  indented\n\n.END\n"
    assert _kinds(text) == [Title, GlobalDirective, CommentLine, IndentedLine, BlankLine, End]
    assert _parse(text).items[1].trailing_comments == ()
    _tiles(text)


def test_crlf_continuation_across_comments() -> None:
    text = "t\r\n.global a\r\n* c\r\n\r\n+ b\r\n.END\r\n"
    assert _kinds(text) == [Title, GlobalDirective, End]
    assert [node.name for node in _parse(text).items[1].nodes] == ["a", "b"]
    _tiles(text)


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
