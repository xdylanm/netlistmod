"""Rules for lines, titles, comments, opaque statements and blocks, and ``.end``."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, NoReturn

from lark import Token

from netlistmod.model._rules_base import _Rules
from netlistmod.model._tree import (
    _comment_spans,
    _dot,
    _Element,
    _end,
    _Field,
    _Item,
    _Rest,
    _span,
)
from netlistmod.model.nodes import (
    BlankLine,
    CommentLine,
    End,
    IndentedLine,
    OpaqueBlock,
    OpaqueStatement,
    ParseResult,
    PreprocessDirective,
    SubcktDefinition,
    Title,
    TitleDirective,
    TopLevelItem,
    UnknownDirective,
)
from netlistmod.model.values import Identifier
from netlistmod.source import Span

_SECOND_PREPROCESS = (
    "a second `.PREPROCESS REPLACEGROUND`: Xyce allows one in a netlist (Xyce reference manual "
    "§2.1.28 p125) and stops on another"
)


@dataclass(frozen=True, slots=True)
class _Truth:
    """The TRUE or FALSE of a ``.PREPROCESS REPLACEGROUND``, as written, and which one it is."""

    word: Identifier
    enabled: bool


def _preprocess_directives(items: tuple[TopLevelItem, ...]) -> list[PreprocessDirective]:
    """Every ``.PREPROCESS REPLACEGROUND`` line, subcircuit bodies included, in source order."""
    found: list[PreprocessDirective] = []
    for item in items:
        if isinstance(item, PreprocessDirective):
            found.append(item)
        elif isinstance(item, SubcktDefinition):
            found.extend(_preprocess_directives(item.body))
    return found


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
        directives = _preprocess_directives(tuple(items))
        if len(directives) > 1:
            raise self._error_at(directives[1].keyword_span.start, _SECOND_PREPROCESS)
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

    # The xyce grammar (decision 0026; X-M1, decision 0027).
    def indented_line(self, children: list[Token]) -> _Item:
        text = str(children[0])
        return _Item(_end(children), lambda span: IndentedLine(text, span))

    def preprocess_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        option = element.all(Identifier)[0]
        truth = element.all(_Truth)[0]
        return _Item(
            element.end,
            lambda span: PreprocessDirective(
                **_dot(element, span), option=option, value=truth.word, enabled=truth.enabled
            ),
        )

    def pp_option(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: Identifier(str(token), _span(token)))

    def pp_value(self, children: list[Any]) -> _Field:
        def build(token: Token) -> _Truth:
            return _Truth(Identifier(str(token), _span(token)), token.type == "TRUE_KW")

        return self._field(children, build)

    def pp_word(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: token)

    def preprocess_other(self, children: list[Any]) -> NoReturn:
        keyword = children[0]
        word = children[1].node
        raise self._unsupported(
            keyword,
            f"`{keyword} {word}`, not yet supported on {self._dialect.display_name}; the library "
            "reads only `.PREPROCESS REPLACEGROUND`",
        )

    # The lines the xyce grammar recognises whole, to refuse them here.
    def unsupported_directive(self, children: list[Any]) -> NoReturn:
        name = children[0]
        raise self._unsupported(
            name, f"dot-command `{name}`, not yet supported on {self._dialect.display_name}"
        )

    def continuation_line(self, children: list[Any]) -> NoReturn:
        raise self._unsupported(
            children[0],
            f"`+` continuation line after a comment or blank line; not yet supported on "
            f"{self._dialect.display_name}",
        )
