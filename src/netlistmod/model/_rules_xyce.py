"""Rules for xyce's statements: `.SUBCKT` defaults, the includes and `.LIB` (X-M1 B4; decision
0027 item 7)."""

from __future__ import annotations

from typing import Any

from lark import Token

from netlistmod.dialects import fold_name
from netlistmod.model._rules_statements import StatementsRules
from netlistmod.model._tree import (
    _Element,
    _Field,
    _Item,
    _span,
)
from netlistmod.model.nodes import LibCall, OpaqueBlock, OpaqueStatement
from netlistmod.model.values import Identifier


class XyceRules(StatementsRules):
    """Rules for xyce's statements that the other dialects spell differently."""

    def subckt_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    def path_field(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: Identifier(str(token), _span(token)))

    def _opaque_raw(self, element: _Element) -> str:
        """The text from the keyword to the end of the last field, across `+` lines."""
        last = element.all(Identifier)[-1]
        return self._source.text[_span(element.designator).start : last.span.end]

    def include_line(self, children: list[Any]) -> _Item:
        element = _Element(children)
        raw = self._opaque_raw(element)
        comments = element.comments
        return _Item(element.end, lambda span: OpaqueStatement("include", raw, span, comments))

    def lib_call(self, children: list[Any]) -> _Item:
        element = _Element(children)
        raw = self._opaque_raw(element)
        comments = element.comments
        entries = element.all(Identifier)[1:]
        return _Item(element.end, lambda span: LibCall("lib", raw, span, comments, entries))

    def lib_open(self, children: list[Any]) -> Identifier:
        field: _Field = children[1]
        assert isinstance(field.node, Identifier)
        return field.node

    def lib_open_end(self, children: list[Any]) -> None:
        return None

    def lib_text(self, children: list[Any]) -> None:
        return None

    def lib_close(self, children: list[Any]) -> tuple[Token, Identifier | None, int]:
        element = _Element(children)
        return element.designator, element.optional(Identifier), element.end

    def lib_section(self, children: list[Any]) -> _Item:
        name: Identifier = children[0]
        keyword, closing, end = children[-1]
        if closing is None:
            raise self._parse_error(
                keyword,
                f"`{keyword}` without a name: it must name the library entry it closes, "
                f"`{keyword} {name.name}` (Xyce reference manual §2.1.16.2 p51); Xyce stops on it",
            )
        if fold_name(closing.name, self._dialect) != fold_name(name.name, self._dialect):
            raise self._error_at(
                closing.span.start,
                f"`{keyword} {closing.name}` closes the library entry `{name.name}`: the names "
                "must match (Xyce reference manual §2.1.16.2 p51); Xyce stops on it",
            )
        return _Item(end, lambda span: OpaqueBlock("lib", span))
