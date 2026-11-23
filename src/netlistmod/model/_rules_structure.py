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
    _field_token,
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
_REMOVEUNUSED_LETTERS = "C, D, I, L, M, Q, R and V"
_REMOVEUNUSED_CITED = "Xyce reference manual §2.1.29 p126"
_PREPROCESS_FORMS = (
    "the `.PREPROCESS` forms are REPLACEGROUND, REMOVEUNUSED and ADDRESISTORS (Xyce reference "
    "manual §2.1.28 p125 and the two sections after it, to p127)"
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

    # The kinds of xyce's `.PREPROCESS ADDRESISTORS` read so far, in source order.
    _addresistors: set[str]
    # Whether xyce's `.PREPROCESS REMOVEUNUSED` has been read (one per netlist).
    _removeunused: bool

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

    def pp_addresistors(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: token)

    pp_kind = pp_addresistors

    pp_number = pp_addresistors

    def preprocess_addresistors(self, children: list[Any]) -> _Item:
        # An UnknownDirective (decision 0028 item 1): it writes another netlist and changes
        # nothing in this one. One of each kind per netlist, subcircuit bodies included: the
        # transformer sees the lines in source order, so the second is refused at its keyword.
        element = _Element(children)
        keyword = element.designator
        kind = element.all(Token)[1]
        folded = str(kind).upper()
        if folded in self._addresistors:
            raise self._parse_error(
                keyword,
                f"a second `.PREPROCESS ADDRESISTORS {folded}`: Xyce allows one of each kind in a "
                "netlist (Xyce reference manual §2.1.30 p127) and stops on another",
            )
        self._addresistors.add(folded)
        end = _span(element.all(Token)[-1]).end
        raw = self._source.text[_span(keyword).start : end]
        comments = element.comments
        return _Item(
            element.end,
            lambda span: UnknownDirective(str(keyword), raw, span, comments, _span(keyword)),
        )

    def pp_bad_kind(self, children: list[Any]) -> NoReturn:
        word = _field_token(children)
        raise self._parse_error(
            word,
            f"`{word}` is not a kind of `.PREPROCESS ADDRESISTORS`: write ONETERMINAL or "
            "NODCPATH, then the resistor's value (Xyce reference manual §2.1.30 p127)",
        )

    pp_removeunused = pp_addresistors

    def preprocess_removeunused(self, children: list[Any]) -> _Item:
        # An UnknownDirective (decision 0031 item 10): Xyce removes devices from the circuit it
        # runs, while the netlist and its topology stay as written (P4). One line per netlist,
        # subcircuit bodies included, seen in source order, so the second is refused.
        element = _Element(children)
        keyword = element.designator
        if self._removeunused:
            raise self._parse_error(
                keyword,
                "a second `.PREPROCESS REMOVEUNUSED`: Xyce allows one in a netlist and stops on "
                f"another; list every letter on one line ({_REMOVEUNUSED_CITED})",
            )
        self._removeunused = True
        end = _span(element.all(Token)[-1]).end
        raw = self._source.text[_span(keyword).start : end]
        comments = element.comments
        return _Item(
            element.end,
            lambda span: UnknownDirective(str(keyword), raw, span, comments, _span(keyword)),
        )

    ru_letter = pp_addresistors

    ru_next_letter = pp_addresistors

    def ru_empty(self, children: list[Any]) -> NoReturn:
        word = children[1].node
        raise self._parse_error(
            word,
            f"`{word}` lists no device letter: write a comma list of at least one of "
            f"{_REMOVEUNUSED_LETTERS} ({_REMOVEUNUSED_CITED}); Xyce stops on an empty one",
        )

    def ru_bad_first(self, children: list[Any]) -> NoReturn:
        self._refuse_letter(_field_token(children))

    ru_bad_next = ru_bad_first

    def _refuse_letter(self, word: Token) -> NoReturn:
        raise self._parse_error(
            word,
            f"`{word}` is not a device letter of `.PREPROCESS REMOVEUNUSED`, which takes a comma "
            f"list of {_REMOVEUNUSED_LETTERS} ({_REMOVEUNUSED_CITED})",
        )

    def ru_trailing(self, children: list[Any]) -> NoReturn:
        raise self._parse_error(
            children[0],
            "a comma after the last letter of `.PREPROCESS REMOVEUNUSED`: the letters are a "
            f"comma list ({_REMOVEUNUSED_CITED}), so remove the trailing comma",
        )

    def ru_blank(self, children: list[Any]) -> NoReturn:
        word = _field_token(children)
        if word.type != "RU_LETTER":
            self._refuse_letter(word)
        raise self._parse_error(
            word,
            f"`{word}` follows a blank: the letters of `.PREPROCESS REMOVEUNUSED` are separated "
            f"by commas, as in `C,R` ({_REMOVEUNUSED_CITED})",
        )

    def preprocess_other(self, children: list[Any]) -> NoReturn:
        word = children[1].node
        raise self._parse_error(word, f"`{word}` is not a `.PREPROCESS` form: {_PREPROCESS_FORMS}")

    def continuation_line(self, children: list[Any]) -> NoReturn:
        raise self._unsupported(
            children[0],
            f"`+` continuation line after a comment or blank line; not yet supported on "
            f"{self._dialect.display_name}",
        )
