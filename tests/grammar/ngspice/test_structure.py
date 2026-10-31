from __future__ import annotations

import random
import string
from collections.abc import Iterable
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from lark import Lark

from netlistmod import (
    BlankLine,
    CommentLine,
    Dialect,
    End,
    OpaqueBlock,
    OpaqueStatement,
    ParseError,
    SourceText,
    Span,
    Title,
    TitleDirective,
    UnknownDirective,
    UnsupportedConstruct,
    parse,
)
from netlistmod.grammar.loader import (
    GRAMMARS,
    build_parser,
    device_matrix,
    parse_tree,
    pending_dialects,
    registered_dialects,
)


def _parse(text: str):
    return parse(SourceText(text), Dialect.NGSPICE)


def _assert_spans_tile(text: str, items: Iterable[object]) -> None:
    position = 0
    for item in items:
        span = item.span  # type: ignore[attr-defined]
        assert span.start == position
        assert span.end >= span.start
        position = span.end
    assert position == len(text)


def test_loader_builds_and_caches_registered_ngspice_grammar() -> None:
    parser = build_parser(Dialect.NGSPICE)
    assert parser.options.parser == "lalr"
    assert parser.options.lexer == "contextual"
    assert parser.options.strict is True
    assert build_parser(Dialect.NGSPICE) is parser
    assert GRAMMARS[Dialect.NGSPICE] == ("core.lark", "ngspice.lark")
    assert registered_dialects() == frozenset({Dialect.NGSPICE})
    assert pending_dialects() == frozenset({Dialect.LTSPICE})
    with pytest.raises(ValueError, match="No grammar registered"):
        build_parser(Dialect.LTSPICE)
    with pytest.raises(ValueError, match="Unknown dialect"):
        build_parser("ngspice")  # type: ignore[arg-type]


@pytest.mark.parametrize("grammar", ["core.lark", "ngspice.lark"])
def test_each_grammar_builds_independently_under_strict_mode(grammar: str) -> None:
    Lark.open_from_package(
        "netlistmod.grammar",
        grammar,
        parser="lalr",
        lexer="contextual",
        propagate_positions=True,
        strict=True,
    )


def test_parse_tree_retains_positions_and_requires_explicit_dialect() -> None:
    source = SourceText("title\r\n.end")
    tree = parse_tree(source, Dialect.NGSPICE)
    assert tree.meta.start_pos == 0
    assert tree.meta.end_pos == len(source.text)
    with pytest.raises(ValueError):
        parse_tree(source, None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("title\n.end\n", ("title", False)),
        ("+ title\n.end\n", ("+ title", False)),
        (".title foo ; bar\n.end\n", ("foo ; bar", True)),
        (".title foo $ bar\n.end\n", ("foo $ bar", True)),
        (".title\n.end\n", ("", True)),
        ("\n.end\n", ("", False)),
    ],
)
def test_title_forms_are_single_tokens(text: str, expected: tuple[str, bool]) -> None:
    result = _parse(text)
    title = result.items[0]
    assert isinstance(title, Title)
    assert (title.text, title.explicit) == expected
    _assert_spans_tile(text, result.items)


def test_structural_nodes_are_typed_and_spans_tile_source() -> None:
    text = (
        "implicit title\r\n"
        "\t \r\n"
        "* full comment\n"
        ".mystery argument\n"
        ".title replacement\n"
        '.include "models.lib"\n'
        ".lib typical section\n"
        ".control\n"
        'R1 x 0 "unbalanced\n'
        ".endc\n"
        ".if (1)\n"
        ".if (2)\n"
        ".endif\n"
        ".else\n"
        ".endif\n"
        ".end\n"
        "\n \t\n"
    )
    result = _parse(text)
    assert isinstance(result.items[0], Title)
    assert result.items[0].text == "implicit title"
    assert isinstance(result.items[1], BlankLine)
    assert isinstance(result.items[2], CommentLine)
    assert isinstance(result.items[3], UnknownDirective)
    assert result.items[3].name == ".mystery"
    assert result.items[3].raw == ".mystery argument"
    assert isinstance(result.items[4], TitleDirective)
    assert result.items[4].text == "replacement"
    assert isinstance(result.items[5], OpaqueStatement)
    assert result.items[5].kind == "include"
    assert isinstance(result.items[6], OpaqueStatement)
    assert result.items[6].kind == "lib"
    assert isinstance(result.items[7], OpaqueBlock)
    assert result.items[7].kind == "control"
    assert isinstance(result.items[8], OpaqueBlock)
    assert result.items[8].kind == "if"
    assert isinstance(result.items[9], End)
    assert [type(item) for item in result.items[10:]] == [BlankLine, BlankLine]
    _assert_spans_tile(text, result.items)


def test_continuations_require_immediate_previous_statement() -> None:
    text = "title\n.plot v(out)\n  + trace\n.include first.lib\n.end"
    result = _parse(text)
    directive, include = result.items[1:3]
    assert isinstance(directive, UnknownDirective)
    assert directive.raw == ".plot v(out)\n  + trace"
    assert isinstance(include, OpaqueStatement)
    assert include.raw == ".include first.lib"
    assert isinstance(result.items[3], End)
    _assert_spans_tile(text, result.items)


@pytest.mark.parametrize(
    ("text", "line", "column", "excerpt"),
    [
        ("title\n.include a\n+ b\n.end\n", 3, 1, "+ b\n^"),
        ("title\n.lib a b\n+ c\n.end\n", 3, 1, "+ c\n^"),
        ("title\n.INCLUDE a ; note\n+ b\n.end\n", 3, 1, "+ b\n^"),
        ("title\r\n.include a\r\n  + b\r\n.end\r\n", 3, 3, "  + b\n  ^"),
        ("title\n.include a \\\\\nb\n.end\n", 2, 12, ".include a \\\\\n           ^"),
        ("title\n.lib a b\\\\\nc\n.end\n", 2, 9, ".lib a b\\\\\n        ^"),
    ],
)
def test_include_and_lib_cannot_be_continued(
    text: str, line: int, column: int, excerpt: str
) -> None:
    with pytest.raises(ParseError) as captured:
        _parse(text)
    assert (captured.value.line, captured.value.column) == (line, column)
    assert captured.value.excerpt == excerpt


@pytest.mark.parametrize(
    ("statement", "raw"),
    [
        (".options a \\\\\nb", ".options a \\\\\nb"),
        (".options a\\\\\nb", ".options a\\\\\nb"),
        (".options a \\\\\n    b", ".options a \\\\\n    b"),
        (".options a \\\\\r\nb", ".options a \\\\\r\nb"),
        (".foo a \\\\\nb \\\\\nc", ".foo a \\\\\nb \\\\\nc"),
        (".foo a \\\\\nb\n+ c", ".foo a \\\\\nb\n+ c"),
        (".foo a\n+ b \\\\\nc", ".foo a\n+ b \\\\\nc"),
        (".foo 'q' \\\\\nb", ".foo 'q' \\\\\nb"),
        (".foo\\\\\nb", ".foo\\\\\nb"),
        (".foo a\\\\\\\nb", ".foo a\\\\\\\nb"),
        (".foo a \\\\\nb ; note", ".foo a \\\\\nb "),
    ],
)
def test_backslash_continuation_joins_the_next_line(statement: str, raw: str) -> None:
    text = f"title\n{statement}\n.end\n"
    result = _parse(text)
    directive = result.items[1]
    assert isinstance(directive, UnknownDirective)
    assert directive.raw == raw
    assert directive.span == Span(len("title\n"), len("title\n") + len(statement) + 1)
    _assert_spans_tile(text, result.items)


@pytest.mark.parametrize(
    ("text", "line", "column"),
    [
        ("title\n.foo a \\\\\n\n.end\n", 2, 8),
        ("title\n.foo a \\\\\n  \n.end\n", 2, 8),
        ("title\n.foo a \\\\\n* c\n.end\n", 2, 8),
        ("title\n.foo a \\\\\n+ b\n.end\n", 2, 8),
        ("title\n.foo a \\\\\n; c\n.end\n", 2, 8),
        ("title\n.foo a \\\\\n// c\n.end\n", 2, 8),
        ("title\n.foo a \\\\", 2, 10),
        ("title\n.foo a\n\\\\\n.bar\n.end\n", 3, 1),
        ("title\n.foo a\n  \\\\\n.bar\n.end\n", 3, 3),
        ("title\n.end \\\\\n", 2, 6),
    ],
)
def test_backslash_continuation_rejects_lines_that_cannot_continue(
    text: str, line: int, column: int
) -> None:
    with pytest.raises(ParseError) as captured:
        _parse(text)
    assert (captured.value.line, captured.value.column) == (line, column)


@pytest.mark.parametrize(
    ("text", "kind", "value"),
    [
        ("title\n.foo a \\\n.end\n", UnknownDirective, ".foo a \\"),
        ("title\n.foo a \\\\ b\n.end\n", UnknownDirective, ".foo a \\\\ b"),
        ("title\n.foo a \\\\  \n.end\n", UnknownDirective, ".foo a \\\\  "),
        ("title\n.foo a ; c \\\\\n.end\n", UnknownDirective, ".foo a "),
        ("title\n* c \\\\\n.end\n", CommentLine, "* c \\\\"),
        ("title\n.title x \\\\\n.end\n", TitleDirective, "x \\\\"),
    ],
)
def test_backslashes_that_do_not_end_a_statement_line_are_text(
    text: str, kind: type, value: str
) -> None:
    result = _parse(text)
    item = result.items[1]
    assert isinstance(item, kind)
    assert getattr(item, "raw", getattr(item, "text", None)) == value
    assert isinstance(result.items[2], End)


@pytest.mark.parametrize("continued", ["Q1 c b \\\\\ne npn", "Q1 c b\n+ e npn"])
def test_continued_element_line_is_reported_at_its_first_line(continued: str) -> None:
    with pytest.raises(UnsupportedConstruct) as captured:
        _parse(f"title\n{continued}\n.end\n")
    assert captured.value.construct == "ngspice Q device"
    assert (captured.value.line, captured.value.column) == (2, 1)


def test_repeated_continuations_and_line_ending_variants_are_accepted() -> None:
    text = "title\r\n.options a\r\n+ b\n+ c\r\n.end\n"
    result = _parse(text)
    directive = result.items[1]
    assert isinstance(directive, UnknownDirective)
    assert directive.raw == ".options a\r\n+ b\n+ c"
    _assert_spans_tile(text, result.items)


def test_lone_cr_in_full_line_comment_is_free_text() -> None:
    text = "title\n* first\rcarriage return remains comment\n.end\n"
    result = _parse(text)
    assert isinstance(result.items[1], CommentLine)
    assert result.items[1].text == "* first\rcarriage return remains comment"
    _assert_spans_tile(text, result.items)


@pytest.mark.parametrize(
    ("text", "line", "column", "excerpt"),
    [
        ("title\n.foo x\n* comment\n+ y\n.end\n", 4, 1, "+ y\n^"),
        ("title\n.foo x\n\n+ y\n.end\n", 4, 1, "+ y\n^"),
        ("title\n* comment\n+ y\n.end\n", 3, 1, "+ y\n^"),
        ("title\n\n+ y\n.end\n", 3, 1, "+ y\n^"),
        ("title\n+ y\n.end\n", 2, 1, "+ y\n^"),
        ("title\n.end\n+ y\n", 3, 1, "+ y\n^"),
    ],
)
def test_continuations_after_non_statements_or_intervening_lines_fail(
    text: str, line: int, column: int, excerpt: str
) -> None:
    with pytest.raises(ParseError) as captured:
        _parse(text)
    assert (captured.value.line, captured.value.column) == (line, column)
    assert captured.value.excerpt.endswith(excerpt)


@pytest.mark.parametrize(
    ("text", "comment"),
    [
        ("title\n.foo a; note\n.end\n", ";"),
        ("title\n.foo a $ note\n.end\n", "$"),
        ("title\n.foo a;note\n.end\n", ";"),
        ("title\n.foo a$note\n.end\n", "$"),
        ("title\n.foo a // note\n.end\n", "//"),
        ("title\n.foo a//note\n.end\n", "//"),
    ],
)
def test_trailing_comment_spans_preserve_marker_and_offset(text: str, comment: str) -> None:
    result = _parse(text)
    directive = result.items[1]
    assert isinstance(directive, UnknownDirective)
    marker = text.index(comment)
    assert directive.trailing_comments == (Span(marker, text.index("\n", marker)),)


@pytest.mark.parametrize(
    ("statement", "raw", "comment"),
    [
        (".param n1=1 // new value", ".param n1=1 ", "// new value"),
        (".options a // don't", ".options a ", "// don't"),
        (".options a='x//y'", ".options a='x//y'", None),
        (".param n1=2//3", ".param n1=2", "//3"),
        (".foo a/ /b", ".foo a/ /b", None),
    ],
)
def test_double_slash_is_an_end_of_line_comment_delimiter(
    statement: str, raw: str, comment: str | None
) -> None:
    text = f"title\n{statement}\n.end\n"
    result = _parse(text)
    directive = result.items[1]
    assert isinstance(directive, UnknownDirective)
    assert directive.raw == raw
    if comment is None:
        assert directive.trailing_comments == ()
    else:
        marker = text.index(comment)
        assert directive.trailing_comments == (Span(marker, marker + len(comment)),)
    _assert_spans_tile(text, result.items)


@pytest.mark.parametrize(
    ("statement", "raw", "comment"),
    [
        (".include a//b", ".include a", "//b"),
        ('.include "a//b"', '.include "a//b"', None),
        (".include /users/spice/common/bsim3-param.mod", None, None),
        (".lib lib//x.lib section", ".lib lib", "//x.lib section"),
    ],
)
def test_double_slash_in_opaque_statement_paths(
    statement: str, raw: str | None, comment: str | None
) -> None:
    text = f"title\n{statement}\n.end\n"
    item = _parse(text).items[1]
    assert isinstance(item, OpaqueStatement)
    assert item.raw == (statement if raw is None else raw)
    if comment is None:
        assert item.trailing_comments == ()
    else:
        assert item.trailing_comments == (Span(text.index(comment), text.index("\n", 6)),)


def test_double_slash_does_not_split_titles() -> None:
    result = _parse("first // title\n.title second // title\n.end\n")
    assert isinstance(result.items[0], Title)
    assert result.items[0].text == "first // title"
    assert isinstance(result.items[1], TitleDirective)
    assert result.items[1].text == "second // title"


@pytest.mark.parametrize(
    ("statement", "raw", "comments"),
    [
        (".foo a\n+ b // c\n+ d", ".foo a\n+ b // c\n+ d", ("// c",)),
        (
            ".foo a ; one\n+ b $ two\n+ c // three",
            ".foo a ; one\n+ b $ two\n+ c ",
            ("; one", "$ two", "// three"),
        ),
        (".foo a\n+ b ; last", ".foo a\n+ b ", ("; last",)),
        (
            ".foo a\n+ ; only a comment\n+ b",
            ".foo a\n+ ; only a comment\n+ b",
            ("; only a comment",),
        ),
        (".foo ; c\r\n+ a\r\n+ b", ".foo ; c\r\n+ a\r\n+ b", ("; c",)),
    ],
)
def test_each_line_of_a_continued_statement_may_end_in_a_comment(
    statement: str, raw: str, comments: tuple[str, ...]
) -> None:
    text = f"title\n{statement}\n.end\n"
    result = _parse(text)
    directive = result.items[1]
    assert isinstance(directive, UnknownDirective)
    assert directive.raw == raw
    assert tuple(text[span.start : span.end] for span in directive.trailing_comments) == comments
    assert directive.span == Span(len("title\n"), len("title\n") + len(statement) + 1)
    _assert_spans_tile(text, result.items)


def test_standalone_end_of_line_comment_markers_are_rejected() -> None:
    for line in (";", "$", "// comment", "  // indented", "//"):
        with pytest.raises(ParseError) as captured:
            _parse(f"title\n{line}\n.end\n")
        assert captured.value.line == 2
        assert captured.value.column == len(line) - len(line.lstrip()) + 1


def test_quotes_are_grouped_but_braces_do_not_protect_comment_markers() -> None:
    text = "title\n.foo \"a ; $ //\"\n.bar {b ; $ //}\n.baz 'c ; $ //'\n.end\n"
    result = _parse(text)
    directives = [item for item in result.items if isinstance(item, UnknownDirective)]
    assert [item.raw for item in directives] == [
        '.foo "a ; $ //"',
        ".bar {b ",
        ".baz 'c ; $ //'",
    ]
    assert directives[0].trailing_comments == ()
    assert directives[2].trailing_comments == ()
    marker = text.index(";", text.index(".bar"))
    assert directives[1].trailing_comments == (Span(marker, text.index("\n", marker)),)


def test_end_is_required_last_and_allows_no_final_newline_or_blank_trailers() -> None:
    for text in ("title\n.end", "title\n.end\n", "title\n.end\n\n  \n"):
        result = _parse(text)
        assert isinstance(result.items[-1], (End, BlankLine))
        assert any(isinstance(item, End) for item in result.items)
        _assert_spans_tile(text, result.items)


def test_crlf_mixed_endings_case_and_indented_block_closers() -> None:
    text = "+ first title\r\n.CONTROL\nop\r\n  .ENDC\n.if (1)\r\n  .ELSE\n  .ENDIF\r\n.END"
    result = _parse(text)
    assert [type(item) for item in result.items] == [Title, OpaqueBlock, OpaqueBlock, End]
    _assert_spans_tile(text, result.items)


@pytest.mark.parametrize(
    ("text", "line", "column", "excerpt"),
    [
        ("", 1, 1, "\n^"),
        ("title\n", 1, 7, "title\n     ^"),
        ("title\n.end\n* comment\n", 3, 1, "* comment\n^"),
        ("title\n.end\n.foo after\n", 3, 1, ".foo after\n^"),
        ("title\n.end\n.control\n.endc\n", 3, 1, ".control\n^"),
        ("title\n.end\n.end\n", 3, 1, ".end\n^"),
        ("title\n.end\n+ after\n", 3, 1, "+ after\n^"),
        ("title\n.end ; trailing\n", 2, 6, ".end ; trailing\n     ^"),
        ("title\n.end $ trailing\n", 2, 6, ".end $ trailing\n     ^"),
        ("title\n.end // trailing\n", 2, 6, ".end // trailing\n     ^"),
        ("title\n.end// trailing\n", 2, 5, ".end// trailing\n    ^"),
        ("title\n;\n.end\n", 2, 1, ";\n^"),
        ("title\n$\n.end\n", 2, 1, "$\n^"),
        ("title\n// comment\n.end\n", 2, 1, "// comment\n^"),
        ("title\n.end\r", 2, 5, ".end\n    ^"),
        ("title\n.end\n\r", 3, 1, "\n^"),
    ],
)
def test_r2_rejects_report_source_position_and_excerpt(
    text: str, line: int, column: int, excerpt: str
) -> None:
    with pytest.raises(ParseError) as captured:
        _parse(text)
    error = captured.value
    assert (error.line, error.column) == (line, column)
    assert error.excerpt == excerpt


def test_missing_end_reports_reason_at_source_end() -> None:
    with pytest.raises(ParseError, match="netlist must end.*missing") as captured:
        _parse("title\n")
    assert captured.value.reason == "the netlist must end with `.end`, which is missing"
    assert (captured.value.line, captured.value.column) == (1, 7)
    assert captured.value.excerpt == "title\n     ^"


def test_unbalanced_quote_is_a_positioned_lexer_error() -> None:
    with pytest.raises(ParseError) as captured:
        _parse('title\n.foo "unclosed\n.end\n')
    assert (captured.value.line, captured.value.column) == (2, 6)
    assert captured.value.excerpt == '.foo "unclosed\n     ^'


@pytest.mark.parametrize(
    ("text", "kind", "closer"),
    [
        ("title\n.control\n", "control", ".endc"),
        ("title\n.if (1)\n", "if", ".endif"),
    ],
)
def test_unterminated_opaque_blocks_point_to_opening_line(
    text: str, kind: str, closer: str
) -> None:
    with pytest.raises(ParseError) as captured:
        _parse(text)
    error = captured.value
    assert (error.line, error.column) == (2, 1)
    assert error.expected == (f"`{closer}`",)
    assert f"unterminated `.{kind}` block" in error.reason
    assert error.excerpt == text.splitlines()[1] + "\n^"


def test_nested_unterminated_if_reports_the_innermost_opener() -> None:
    text = "title\n.if (1)\n.if (2)\n"
    with pytest.raises(ParseError) as captured:
        _parse(text)
    assert (captured.value.line, captured.value.column) == (3, 1)
    assert captured.value.expected == ("`.endif`",)


@pytest.mark.parametrize("closer", [".endc", ".endif", ".else", ".elseif (1)"])
def test_stray_block_closers_are_rejected(closer: str) -> None:
    text = f"title\n{closer}\n.end\n"
    with pytest.raises(ParseError) as captured:
        _parse(text)
    assert (captured.value.line, captured.value.column) == (2, 1)
    assert captured.value.excerpt == closer + "\n^"


PHASE_2_LETTERS = sorted(set(string.ascii_uppercase) - set("RCLKVIDX"))


@pytest.mark.parametrize("letter", PHASE_2_LETTERS)
def test_element_lines_are_positioned_unsupported_constructs(letter: str) -> None:
    with pytest.raises(UnsupportedConstruct) as captured:
        _parse(f"title\n{letter}1 a b 1k\n.end\n")
    assert captured.value.construct == f"ngspice {letter} device"
    assert (captured.value.line, captured.value.column) == (2, 1)
    assert captured.value.excerpt == f"{letter}1 a b 1k\n^"


def test_unknown_letter_is_parse_error_and_device_matrix_is_complete() -> None:
    with pytest.raises(ParseError) as captured:
        _parse("title\nΩ1 a b 1k\n.end\n")
    assert (captured.value.line, captured.value.column) == (2, 1)
    matrix = device_matrix()
    assert set(matrix) == set(string.ascii_uppercase)
    assert all(entry["status"] in {"planned", "supported", "error"} for entry in matrix.values())


def test_device_letter_with_error_status_remains_parse_error() -> None:
    with patch(
        "netlistmod.grammar.loader.device_matrix",
        return_value={"Q": {"status": "error"}},
    ):
        with pytest.raises(ParseError) as captured:
            _parse("title\nQ1 a b 1k\n.end\n")
    assert (captured.value.line, captured.value.column) == (2, 1)


def test_lone_cr_is_free_text_but_not_accepted_after_end() -> None:
    for text in ("title\rinside\n.end\n", "title\n.foo left\rright\n.end\n"):
        _assert_spans_tile(text, _parse(text).items)
    with pytest.raises(ParseError):
        _parse("title\n.end\r")


# No deadline: the first example may build and cache the parser.
@settings(max_examples=200, print_blob=True, deadline=None)
@given(seed=st.integers())
def test_generated_independent_oracle_for_node_kinds_and_spans(seed: int) -> None:
    rng = random.Random(seed)
    kinds = ("blank", "comment", "unknown", "title", "include", "lib", "control", "if")
    title_text = f"title {rng.randrange(1_000_000)}\n"
    pieces = [title_text]
    expected: list[tuple[str, Span]] = [("Title", Span(0, len(title_text)))]

    for index in range(rng.randrange(1, 12)):
        kind = rng.choice(kinds)
        marker = f"{index}_{rng.randrange(1_000_000)}"
        snippets = {
            "blank": ("\n", "BlankLine"),
            "comment": (f"* {marker}\n", "CommentLine"),
            "unknown": (f".unknown {marker}\n", "UnknownDirective"),
            "title": (f".title {marker}\n", "TitleDirective"),
            "include": (f".include {marker}.inc\n", "OpaqueStatement"),
            "lib": (f".lib {marker} section\n", "OpaqueStatement"),
            "control": (f".control\n echo {marker}\n.endc\n", "OpaqueBlock"),
            "if": (f".if ({index})\n echo {marker}\n.endif\n", "OpaqueBlock"),
        }
        piece, node_kind = snippets[kind]
        start = sum(map(len, pieces))
        pieces.append(piece)
        expected.append((node_kind, Span(start, start + len(piece))))

    end = ".end"
    pieces.append(end)
    start = sum(map(len, pieces[:-1]))
    expected.append(("End", Span(start, start + len(end))))
    text = "".join(pieces)

    try:
        result = _parse(text)
        actual = [(type(item).__name__, item.span) for item in result.items]
        assert actual == expected
        _assert_spans_tile(text, result.items)
    except (ParseError, UnsupportedConstruct) as error:
        pytest.fail(f"independent oracle parse failure for seed={seed}: {error}")
    except AssertionError as error:
        pytest.fail(f"independent oracle mismatch for seed={seed}: {error}")
