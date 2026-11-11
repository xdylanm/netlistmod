"""A lone CR right before a CRLF is ordinary text (T3; decision 0001, M18 decision 12, A2-20).

The source layer ends a line only at LF or CRLF, so ``* abc\\r\\r\\n`` is one line holding
``* abc\\r``. Every free-text terminal takes a CR that is not followed by LF, so the line parses,
its item's span is the source's line, and the bytes round-trip.
"""

from __future__ import annotations

import pytest

from netlistmod import (
    CommentLine,
    Dialect,
    OpaqueBlock,
    ParseError,
    Resistor,
    SourceText,
    Title,
    UnknownDirective,
    parse,
)

# (dialect, the line, the item class, the text the item keeps); each line ends in CR CRLF.
_CASES = [
    (Dialect.NGSPICE, "* abc\r", CommentLine, "* abc\r"),
    (Dialect.LTSPICE, "* abc\r", CommentLine, "* abc\r"),
    (Dialect.LTSPICE, "; abc\r", CommentLine, "; abc\r"),
    (Dialect.NGSPICE, ".foo bar\r", UnknownDirective, ".foo bar\r"),
    (Dialect.LTSPICE, ".backanno bar\r", UnknownDirective, ".backanno bar\r"),
    (Dialect.NGSPICE, "R1 a b 1 ; c\r", Resistor, "; c\r"),
    (Dialect.NGSPICE, "R1 a b 1 $ c\r", Resistor, "$ c\r"),
    (Dialect.LTSPICE, "R1 a b 1 ; c\r", Resistor, "; c\r"),
    (Dialect.LTSPICE, "R1 a b 1 $ c\r", Resistor, "$ c\r"),
]


def _text_of(item: object, text: str) -> str:
    if isinstance(item, CommentLine):
        return item.text
    if isinstance(item, UnknownDirective):
        return item.raw
    assert isinstance(item, Resistor)
    (comment,) = item.trailing_comments
    return text[comment.start : comment.end]


@pytest.mark.parametrize(
    ("dialect", "line", "kind", "kept"),
    _CASES,
    ids=[f"{dialect.value}-{line.strip()}" for dialect, line, _, _ in _CASES],
)
def test_a_lone_cr_before_a_crlf_is_text(
    dialect: Dialect, line: str, kind: type, kept: str
) -> None:
    data = f"title\n{line}\r\n.end\n".encode()
    source = SourceText.from_bytes(data)
    assert source.line_count == 3
    items = parse(source, dialect).items
    item = items[1]
    assert isinstance(item, kind)
    assert item.span == source.line_span(2)
    assert _text_of(item, source.text) == kept
    assert "".join(source.text[i.span.start : i.span.end] for i in items) == source.text
    assert source.to_bytes() == data


@pytest.mark.parametrize("dialect", [Dialect.NGSPICE, Dialect.LTSPICE])
@pytest.mark.parametrize("title", ["t\r", "t\r\r", ".title t\r"])
def test_a_title_may_end_in_a_lone_cr(dialect: Dialect, title: str) -> None:
    data = f"{title}\r\nR1 a b 1\r\n.end\r\n".encode()
    source = SourceText.from_bytes(data)
    items = parse(source, dialect).items
    assert isinstance(items[0], Title)
    assert items[0].span == source.line_span(1)
    assert items[0].text == title.removeprefix(".title ")
    assert source.position(items[1].span.start) == (2, 1)
    assert source.to_bytes() == data


@pytest.mark.parametrize(
    ("dialect", "block"),
    [
        (Dialect.NGSPICE, ".control\r\nop\r\r\n.endc\r\n"),
        (Dialect.NGSPICE, ".if (1)\r\nR1 a b 1\r\r\n.endif\r\n"),
    ],
)
def test_a_block_line_may_end_in_a_lone_cr(dialect: Dialect, block: str) -> None:
    data = f"title\r\n{block}.end\r\n".encode()
    source = SourceText.from_bytes(data)
    items = parse(source, dialect).items
    assert isinstance(items[1], OpaqueBlock)
    assert items[1].span == source.line_span(2).hull(source.line_span(4))
    assert source.to_bytes() == data


@pytest.mark.parametrize("dialect", [Dialect.NGSPICE, Dialect.LTSPICE])
def test_a_lone_cr_after_end_is_still_refused(dialect: Dialect) -> None:
    # Outside a free-text terminal a lone CR is a syntax error (architecture §6.3 rule 13).
    with pytest.raises(ParseError):
        parse(SourceText("title\n.end\r\r\n"), dialect)
