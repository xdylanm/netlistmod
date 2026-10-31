"""The ordered, searchable sequence of logical lines (architecture §5.4, decision 0006).

A :class:`Line` is one logical item: a statement with its continuation lines and end-of-line
comments, a blank line, a comment line or a whole opaque block. Its span is the item span the
parser produces, so the lines of a netlist tile its text. A subcircuit definition is one line
whose ``body`` holds the lines of its body.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import overload

from netlistmod.model.nodes import TopLevelItem
from netlistmod.source import Span

ScopePath = tuple[str, ...]
"""A definition scope: folded subcircuit names from the top level, ``()`` for the top level."""


@dataclass(frozen=True, slots=True, eq=False)
class Line:
    """One logical item of the netlist; lines compare by identity.

    ``first_line`` and ``last_line`` are 1-based physical line numbers. ``scope`` is the
    definition scope that holds the item. ``body`` holds the lines of a subcircuit definition's
    body and is ``None`` for every other item.
    """

    item: TopLevelItem
    span: Span
    first_line: int
    last_line: int
    scope: ScopePath
    body: Lines | None = None


class Lines(Sequence[Line]):
    """An immutable sequence of lines with type search and insertion points."""

    __slots__ = ("_lines",)

    def __init__(self, lines: Sequence[Line]) -> None:
        """Wrap ``lines``, which must be in source order."""
        self._lines = tuple(lines)

    @overload
    def __getitem__(self, index: int) -> Line: ...

    @overload
    def __getitem__(self, index: slice) -> Lines: ...

    def __getitem__(self, index: int | slice) -> Line | Lines:
        """Return a line, or a slice as ``Lines``."""
        if isinstance(index, slice):
            return Lines(self._lines[index])
        return self._lines[index]

    def __len__(self) -> int:
        """Return the number of lines (bodies are not counted)."""
        return len(self._lines)

    def __iter__(self) -> Iterator[Line]:
        """Iterate over the lines in source order (bodies are not entered)."""
        return iter(self._lines)

    def __repr__(self) -> str:
        """Show the item types."""
        return f"Lines({[type(line.item).__name__ for line in self._lines]})"

    def walk(self) -> Iterator[Line]:
        """Iterate over every line, entering subcircuit bodies after their definition line."""
        for line in self._lines:
            yield line
            if line.body is not None:
                yield from line.body.walk()

    def find(self, kind: type | tuple[type, ...], *, recursive: bool = False) -> Line | None:
        """Return the first line whose item is an instance of ``kind``, or ``None``."""
        return next(iter(self.find_all(kind, recursive=recursive)), None)

    def find_all(
        self, kind: type | tuple[type, ...], *, recursive: bool = False
    ) -> tuple[Line, ...]:
        """Return every line whose item is an instance of ``kind``, in source order.

        With ``recursive=True`` the search enters subcircuit bodies.
        """
        lines = self.walk() if recursive else iter(self._lines)
        return tuple(line for line in lines if isinstance(line.item, kind))

    def index_of(self, target: Line | object) -> int:
        """Return the position of a line, or of the line holding an item, by identity.

        Only this sequence is searched, not the bodies; ``ValueError`` if it is not here.
        """
        for index, line in enumerate(self._lines):
            if line is target or line.item is target:
                return index
        raise ValueError("the line is not in this sequence")

    def insert_before(self, line: Line) -> Span:
        """A zero-width insertion point at the start of ``line`` (a physical line boundary)."""
        self._check(line)
        return Span(line.span.start, line.span.start)

    def insert_after(self, line: Line) -> Span:
        """A zero-width insertion point at the end of ``line``, after its terminator.

        For a last line without a final newline this is the end of the text; M6 decides the
        text inserted there.
        """
        self._check(line)
        return Span(line.span.end, line.span.end)

    def _check(self, line: Line) -> None:
        if not any(candidate is line for candidate in self.walk()):
            raise ValueError("the line is not in this sequence or its bodies")
