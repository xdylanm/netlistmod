"""Rules for lines, titles, comments, opaque statements and blocks, and ``.end``."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, NoReturn

from lark import Token

from netlistmod.model._rules_base import _Rules
from netlistmod.model._tree import (
    _comment_spans,
    _end,
    _Item,
    _Rest,
    _span,
)
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
from netlistmod.source import Span


class StructureRules(_Rules):
    """Rules for lines, titles, comments, opaque statements and blocks, and ``.end``."""

    def start(self, children: list[Any]) -> ParseResult:
        items: list[TopLevelItem] = []
        cursor = 0
        for child in children:
            for item in child if isinstance(child, tuple) else (child,):
                items.append(item.build(Span(cursor, item.end)))
                cursor = item.end
        # Ignored whitespace after the last token (for example ``.end`` plus spaces and no
        # newline) belongs to the last item.
        text = self._source.text
        if cursor < len(text):
            items[-1] = replace(items[-1], span=Span(items[-1].span.start, len(text)))
        return ParseResult(tuple(items), self._dialect)

    def explicit_title(self, children: list[Token]) -> _Item:
        text = next((str(token) for token in children if token.type == "TITLE_ARG"), "")
        return _Item(_end(children), lambda span: Title(text, True, span))

    def implicit_title(self, children: list[Token]) -> _Item:
        text = str(children[0])
        return _Item(_end(children), lambda span: Title(text, False, span))

    def empty_title(self, children: list[Token]) -> _Item:
        return _Item(_end(children), lambda span: Title("", False, span))

    def blank_line(self, children: list[Token]) -> _Item:
        return _Item(_end(children), BlankLine)

    def comment_line(self, children: list[Token]) -> _Item:
        text = str(children[0])
        return _Item(_end(children), lambda span: CommentLine(text, span))

    def title_stmt(self, children: list[Token]) -> _Item:
        text = next((str(token) for token in children if token.type == "TITLE_ARG"), "")
        return _Item(_end(children), lambda span: TitleDirective(text, span))

    def rest(self, children: list[Token]) -> _Rest:
        parts = [token for token in children if token.type in {"TEXT", "QUOTED"}]
        text_end = parts[-1].end_pos if parts else None
        return _Rest(text_end, _comment_spans(children))

    line_rest = rest

    def unknown_stmt(self, children: list[Any]) -> _Item:
        name, raw, comments = self._statement(children)
        name_span = _span(children[0])
        return _Item(
            _end(children), lambda span: UnknownDirective(name, raw, span, comments, name_span)
        )

    top_unknown_stmt = unknown_stmt

    def include_stmt(self, children: list[Any]) -> _Item:
        _, raw, comments = self._statement(children)
        return _Item(_end(children), lambda span: OpaqueStatement("include", raw, span, comments))

    def lib_stmt(self, children: list[Any]) -> _Item:
        _, raw, comments = self._statement(children)
        return _Item(_end(children), lambda span: OpaqueStatement("lib", raw, span, comments))

    def control_block(self, children: list[Any]) -> _Item:
        return _Item(_end(children), lambda span: OpaqueBlock("control", span))

    def if_block(self, children: list[Any]) -> _Item:
        return _Item(_end(children), lambda span: OpaqueBlock("if", span))

    def lib_block(self, children: list[Any]) -> _Item:
        return _Item(_end(children), lambda span: OpaqueBlock("lib", span))

    def control_line(self, children: list[Any]) -> None:
        return None

    def if_line(self, children: list[Any]) -> None:
        return None

    def nested_if_block(self, children: list[Any]) -> None:
        # Part of its outer block's text, as any if_line is (M18 A2-19).
        return None

    def lib_line(self, children: list[Any]) -> None:
        return None

    def end(self, children: list[Any]) -> tuple[_Item, ...]:
        end_item = _Item(_end(children), End)
        trailer_items = tuple(child for child in children if isinstance(child, _Item))
        return (end_item, *trailer_items)

    # Lark prefixes aliases that come from an imported grammar with the module name.
    core__explicit_title = explicit_title

    core__implicit_title = implicit_title

    core__empty_title = empty_title

    core__blank_line = blank_line

    core__comment_line = comment_line

    core__end = end

    def machine_block(self, children: list[Any]) -> NoReturn:
        raise self._unsupported(children[0], "LTspice .machine state machine, out of scope for v1")

    def machine_line(self, children: list[Any]) -> None:
        return None
