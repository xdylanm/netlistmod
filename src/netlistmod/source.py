"""Byte-preserving source text and character-based source spans.

``DEFAULT_FALLBACKS`` lists the ordered decoders used after BOM and UTF-8
detection.
"""

from __future__ import annotations

import codecs
import os
import tempfile
from bisect import bisect_right
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Sequence

from netlistmod.errors import EncodingError

DEFAULT_FALLBACKS = ("cp1252", "latin-1")
_UTF32_BOMS = (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")
_BOMS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)
_ENCODING_ALIASES = {
    "utf-8": "utf-8",
    "utf-8-sig": "utf-8",
    "utf-16-le": "utf-16-le",
    "utf-16le": "utf-16-le",
    "utf-16-be": "utf-16-be",
    "utf-16be": "utf-16-be",
    "cp1252": "cp1252",
    "windows-1252": "cp1252",
    "iso8859-1": "latin-1",
    "latin-1": "latin-1",
    "iso-8859-1": "latin-1",
}
_BOM_BY_ENCODING = {
    "utf-8": codecs.BOM_UTF8,
    "utf-16-le": codecs.BOM_UTF16_LE,
    "utf-16-be": codecs.BOM_UTF16_BE,
}


def _normalize_encoding(encoding: str) -> str:
    """Normalize a codec name to the spelling retained by ``SourceText``."""
    try:
        canonical = codecs.lookup(encoding).name.casefold()
    except LookupError as error:
        raise EncodingError(f"Unknown encoding {encoding!r}") from error
    try:
        return _ENCODING_ALIASES[canonical]
    except KeyError:
        return canonical


@dataclass(frozen=True, order=True)
class Span:
    """A half-open span of character offsets in decoded source text."""

    start: int
    end: int

    def __post_init__(self) -> None:
        """Reject negative, reversed, or non-integer offsets."""
        if not isinstance(self.start, int) or not isinstance(self.end, int):
            raise ValueError("Span offsets must be integers")
        if self.start < 0 or self.end < self.start:
            raise ValueError("Span must satisfy 0 <= start <= end")

    @property
    def length(self) -> int:
        """Return the number of characters in this span."""
        return self.end - self.start

    @property
    def is_empty(self) -> bool:
        """Whether this span is a zero-width insertion point."""
        return self.start == self.end

    def overlaps(self, other: Span) -> bool:
        """Whether two spans share source characters or an interior insertion."""
        if self.is_empty and other.is_empty:
            return False
        if self.is_empty:
            return other.start < self.start < other.end
        if other.is_empty:
            return self.start < other.start < self.end
        return self.start < other.end and other.start < self.end

    def contains(self, offset: int) -> bool:
        """Whether ``offset`` identifies a character within this span."""
        return self.start <= offset < self.end

    def hull(self, other: Span) -> Span:
        """Return the smallest span containing this span and ``other``."""
        return Span(min(self.start, other.start), max(self.end, other.end))


@dataclass(frozen=True)
class SourceText:
    """Decoded source with byte-exact saves and default CP1252/Latin-1 fallbacks."""

    text: str
    encoding: str = "utf-8"
    bom: bool = False

    def __post_init__(self) -> None:
        """Normalize the stored encoding name."""
        object.__setattr__(self, "encoding", _normalize_encoding(self.encoding))

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        *,
        fallback_encodings: Sequence[str] = DEFAULT_FALLBACKS,
    ) -> SourceText:
        """Decode bytes using BOM detection, strict UTF-8, then fallbacks."""
        for marker in _UTF32_BOMS:
            if data.startswith(marker):
                raise EncodingError("UTF-32 BOMs are not supported")

        for marker, encoding in _BOMS:
            if data.startswith(marker):
                try:
                    text = data[len(marker) :].decode(encoding, errors="strict")
                except UnicodeDecodeError as error:
                    raise EncodingError(
                        f"Data after {encoding} BOM is not valid {encoding}"
                    ) from error
                return cls(text=text, encoding=encoding, bom=True)

        try:
            return cls(data.decode("utf-8", errors="strict"), "utf-8", False)
        except UnicodeDecodeError:
            pass

        failures: list[str] = []
        for requested_encoding in fallback_encodings:
            encoding = _normalize_encoding(requested_encoding)
            try:
                return cls(data.decode(encoding, errors="strict"), encoding, False)
            except UnicodeDecodeError as error:
                failures.append(f"{encoding}: {error}")

        detail = "; ".join(failures) if failures else "no fallback encodings configured"
        raise EncodingError(f"Unable to decode source bytes ({detail})")

    def to_bytes(self) -> bytes:
        """Encode the text with its recorded codec and restore its BOM."""
        try:
            encoded = self.text.encode(self.encoding, errors="strict")
        except (UnicodeEncodeError, LookupError) as error:
            raise EncodingError(f"Text cannot be encoded as {self.encoding}") from error
        if not self.bom:
            return encoded
        try:
            marker = _BOM_BY_ENCODING[self.encoding]
        except KeyError as error:
            raise EncodingError(f"No BOM is defined for {self.encoding}") from error
        return marker + encoded

    def with_text(self, new_text: str) -> SourceText:
        """Return a new source value preserving the original encoding and BOM."""
        return SourceText(new_text, self.encoding, self.bom)

    @classmethod
    def read(
        cls,
        path: str | os.PathLike[str],
        *,
        fallback_encodings: Sequence[str] = DEFAULT_FALLBACKS,
    ) -> SourceText:
        """Read source bytes from ``path`` without newline translation."""
        return cls.from_bytes(Path(path).read_bytes(), fallback_encodings=fallback_encodings)

    def write(self, path: str | os.PathLike[str]) -> None:
        """Atomically write source bytes, leaving the target intact on encoding failure."""
        data = self.to_bytes()
        target = Path(path)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(data)
            os.replace(temporary_path, target)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @cached_property
    def _line_starts(self) -> tuple[int, ...]:
        """Lazily cache line starts without adding an empty line after a final LF."""
        starts = [0]
        for offset, character in enumerate(self.text):
            if character == "\n" and offset + 1 < len(self.text):
                starts.append(offset + 1)
        return tuple(starts)

    @property
    def line_count(self) -> int:
        """Return the number of source lines, treating empty text as one line."""
        return len(self._line_starts)

    def line_span(self, line: int) -> Span:
        """Return the 1-based line span, including its LF or CRLF terminator."""
        if line < 1 or line > self.line_count:
            raise ValueError(f"Line must be between 1 and {self.line_count}")
        start = self._line_starts[line - 1]
        end = self._line_starts[line] if line < self.line_count else len(self.text)
        return Span(start, end)

    def position(self, offset: int) -> tuple[int, int]:
        """Convert a character offset (including EOF) to a 1-based line and column."""
        if offset < 0 or offset > len(self.text):
            raise ValueError(f"Offset must be between 0 and {len(self.text)}")
        line_index = bisect_right(self._line_starts, offset) - 1
        return line_index + 1, offset - self._line_starts[line_index] + 1

    def offset(self, line: int, column: int) -> int:
        """Convert a 1-based line and column to a character offset."""
        if column < 1:
            raise ValueError("Column must be at least 1")
        span = self.line_span(line)
        if column > span.length + 1:
            raise ValueError(f"Column must be between 1 and {span.length + 1}")
        return span.start + column - 1

    def excerpt(self, offset: int) -> str:
        """Render the source line at ``offset`` followed by a caret line."""
        line, column = self.position(offset)
        span = self.line_span(line)
        source_line = self.text[span.start : span.end].rstrip("\n")
        if source_line.endswith("\r"):
            source_line = source_line[:-1]
        caret_column = min(column - 1, len(source_line))
        return f"{source_line}\n{' ' * caret_column}^"
