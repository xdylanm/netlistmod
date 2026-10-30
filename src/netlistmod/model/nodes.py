"""Immutable structural nodes produced by the ngspice parser."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from netlistmod.source import Span


@dataclass(frozen=True, slots=True)
class Title:
    """The first line of the netlist: an implicit title or an explicit ``.title`` statement.

    The whole title text is a single token; ``;``, ``$`` and ``//`` do not start a comment in it.
    """

    text: str
    explicit: bool
    span: Span


@dataclass(frozen=True, slots=True)
class TitleDirective:
    """A ``.title`` statement after the first line; it replaces the displayed title."""

    text: str
    span: Span


@dataclass(frozen=True, slots=True)
class BlankLine:
    """A whitespace-only physical line."""

    span: Span


@dataclass(frozen=True, slots=True)
class CommentLine:
    """A full-line comment, retained verbatim through its source span."""

    text: str
    span: Span


@dataclass(frozen=True, slots=True)
class UnknownDirective:
    """An untyped dot-command whose exact statement text is preserved.

    ``raw`` runs from the name to the end of the last non-comment text, so it excludes comments
    after that text but includes those on earlier lines of a continued statement.
    ``trailing_comments`` holds every end-of-line comment of the statement in source order.
    """

    name: str
    raw: str
    span: Span
    trailing_comments: tuple[Span, ...] = ()


@dataclass(frozen=True, slots=True)
class OpaqueBlock:
    """A preserved ``.control`` or conditional block."""

    kind: Literal["control", "if"]
    span: Span


@dataclass(frozen=True, slots=True)
class OpaqueStatement:
    """An opaque ``.include`` or ``.lib`` statement; ``raw`` and comments as in UnknownDirective."""

    kind: Literal["include", "lib"]
    raw: str
    span: Span
    trailing_comments: tuple[Span, ...] = ()


@dataclass(frozen=True, slots=True)
class End:
    """The required ``.end`` statement, including its terminator."""

    span: Span


TopLevelItem: TypeAlias = (
    Title
    | TitleDirective
    | BlankLine
    | CommentLine
    | UnknownDirective
    | OpaqueBlock
    | OpaqueStatement
    | End
)


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Top-level items whose spans tile the source, ending with :class:`End` and blank lines."""

    items: tuple[TopLevelItem, ...]
