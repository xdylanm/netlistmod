"""Convert the strict grammar's parse tree into typed nodes with source spans.

Syntax is defined by the Lark grammar (architecture P13). This module only maps each grammar
rule to a node: one transformer method per rule, no regular expressions and no re-scanning of
source lines. Raw statement text is a slice of the source by span.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, NoReturn

from lark import Token, Transformer, v_args
from lark.tree import Meta

from netlistmod.dialects import Dialect
from netlistmod.grammar.loader import parse_tree
from netlistmod.model.nodes import (
    BlankLine,
    CommentLine,
    End,
    OpaqueBlock,
    OpaqueStatement,
    ParseResult,
    Title,
    TitleDirective,
    TopLevelItem,
    UnknownDirective,
)
from netlistmod.source import SourceText, Span


@dataclass(frozen=True, slots=True)
class _Item:
    """A top-level item waiting for its span.

    Whitespace between items is ignored by the grammar and has no token, so an item's span
    runs from the end of the previous item to ``end``. That keeps the spans contiguous.
    """

    end: int
    build: Callable[[Span], TopLevelItem]


@dataclass(frozen=True, slots=True)
class _Rest:
    """Where a statement's text ends, and its end-of-line comments in source order."""

    text_end: int | None
    comments: tuple[Span, ...]


@v_args(meta=True)
class _NodeBuilder(Transformer[Token, ParseResult]):
    """Build nodes for one parse; every grammar rule has exactly one method."""

    def __init__(self, source: SourceText) -> None:
        super().__init__()
        self._text = source.text

    def __default__(self, data: Any, children: Any, meta: Any) -> NoReturn:
        raise TypeError(f"Unhandled grammar rule {data!r}")

    def start(self, meta: Meta, children: list[Any]) -> ParseResult:
        items: list[TopLevelItem] = []
        cursor = 0
        for child in children:
            for item in child if isinstance(child, tuple) else (child,):
                items.append(item.build(Span(cursor, item.end)))
                cursor = item.end
        # Ignored whitespace after the last token (for example ``.end`` plus spaces and no
        # newline) belongs to the last item.
        if cursor < len(self._text):
            items[-1] = replace(items[-1], span=Span(items[-1].span.start, len(self._text)))
        return ParseResult(tuple(items))

    def explicit_title(self, meta: Meta, children: list[Token]) -> _Item:
        text = next((str(token) for token in children if token.type == "TITLE_ARG"), "")
        return _Item(meta.end_pos, lambda span: Title(text, True, span))

    def implicit_title(self, meta: Meta, children: list[Token]) -> _Item:
        text = str(children[0])
        return _Item(meta.end_pos, lambda span: Title(text, False, span))

    def empty_title(self, meta: Meta, children: list[Token]) -> _Item:
        return _Item(meta.end_pos, lambda span: Title("", False, span))

    def blank_line(self, meta: Meta, children: list[Token]) -> _Item:
        return _Item(meta.end_pos, BlankLine)

    def comment_line(self, meta: Meta, children: list[Token]) -> _Item:
        text = str(children[0])
        return _Item(meta.end_pos, lambda span: CommentLine(text, span))

    def title_stmt(self, meta: Meta, children: list[Token]) -> _Item:
        text = next((str(token) for token in children if token.type == "TITLE_ARG"), "")
        return _Item(meta.end_pos, lambda span: TitleDirective(text, span))

    def rest(self, meta: Meta, children: list[Token]) -> _Rest:
        parts = [token for token in children if token.type in {"TEXT", "QUOTED"}]
        text_end = parts[-1].end_pos if parts else None
        comments: list[Span] = []
        for token in children:
            if token.type != "TRAILING_COMMENT":
                continue
            if token.start_pos is None or token.end_pos is None:
                raise ValueError("Lark did not propagate trailing-comment positions")
            comments.append(Span(token.start_pos, token.end_pos))
        return _Rest(text_end, tuple(comments))

    line_rest = rest

    def unknown_stmt(self, meta: Meta, children: list[Any]) -> _Item:
        name, raw, comments = self._statement(children)
        return _Item(meta.end_pos, lambda span: UnknownDirective(name, raw, span, comments))

    def include_stmt(self, meta: Meta, children: list[Any]) -> _Item:
        _, raw, comments = self._statement(children)
        return _Item(meta.end_pos, lambda span: OpaqueStatement("include", raw, span, comments))

    def lib_stmt(self, meta: Meta, children: list[Any]) -> _Item:
        _, raw, comments = self._statement(children)
        return _Item(meta.end_pos, lambda span: OpaqueStatement("lib", raw, span, comments))

    def control_block(self, meta: Meta, children: list[Any]) -> _Item:
        return _Item(meta.end_pos, lambda span: OpaqueBlock("control", span))

    def if_block(self, meta: Meta, children: list[Any]) -> _Item:
        return _Item(meta.end_pos, lambda span: OpaqueBlock("if", span))

    def control_line(self, meta: Meta, children: list[Any]) -> None:
        return None

    def if_line(self, meta: Meta, children: list[Any]) -> None:
        return None

    def end(self, meta: Meta, children: list[Any]) -> tuple[_Item, ...]:
        line_end = next(
            (token for token in children if isinstance(token, Token) and token.type == "LINE_END"),
            None,
        )
        end_pos = line_end.end_pos if line_end is not None else meta.end_pos
        if end_pos is None:
            raise ValueError("Lark did not propagate .end positions")
        end_item = _Item(end_pos, End)
        trailer_items = tuple(child for child in children if isinstance(child, _Item))
        return (end_item, *trailer_items)

    # Lark prefixes aliases that come from an imported grammar with the module name.
    core__explicit_title = explicit_title
    core__implicit_title = implicit_title
    core__empty_title = empty_title
    core__blank_line = blank_line
    core__comment_line = comment_line
    core__end = end

    def _statement(self, children: list[Any]) -> tuple[str, str, tuple[Span, ...]]:
        name, rest = children[0], children[1]
        raw = self._text[name.start_pos : rest.text_end or name.end_pos]
        return str(name), raw, rest.comments


def parse(source: SourceText, dialect: Dialect) -> ParseResult:
    """Parse ``source`` with the strict grammar of ``dialect``.

    The dialect is required: there is no default and no auto-detection. An empty source, a
    missing ``.end`` or any syntax the grammar does not accept raises ``ParseError``; an element
    line raises ``UnsupportedConstruct`` or ``ParseError`` (elements are parsed from M3 on).
    """
    return _NodeBuilder(source).transform(parse_tree(source, dialect))
