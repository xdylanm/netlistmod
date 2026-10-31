"""Text conventions for the text the edit layer writes (decision 0007 item 4).

- An inserted line ends with the terminator of the physical line just before the insertion
  point (of the first line when inserting at the start), so mixed endings stay locally
  consistent and are never normalised (P3).
- Dot-command keywords are lowercase; the element keywords ``DC`` and ``AC`` are uppercase, as
  the manual writes them (§4.1). Fields are separated by one blank; an assignment is
  ``name=value`` without blanks; a new ``.param`` line holds one assignment; nothing is indented.

These functions compose text from the caller's strings; they never scan source text for syntax
(P13). Line terminators are a source-layer property (decision 0001).
"""

from __future__ import annotations

from typing import Final

from netlistmod.source import SourceText

PARAM_KEYWORD: Final = ".param"
INCLUDE_KEYWORD: Final = ".include"
DC_KEYWORD: Final = "DC"
AC_KEYWORD: Final = "AC"
FIELD_SEPARATOR: Final = " "
DEFAULT_TERMINATOR: Final = "\n"


def terminator_before(source: SourceText, offset: int) -> str:
    """The terminator of the physical line that ends at ``offset`` (of line 1 at offset 0).

    ``offset`` is a physical-line boundary. A line without a terminator (only the last line of
    a file can be one) gives ``"\\n"``; placements never insert there.
    """
    line = 1 if offset == 0 else source.position(offset - 1)[0]
    span = source.line_span(line)
    content = source.text[span.start : span.end]
    if content.endswith("\r\n"):
        return "\r\n"
    return DEFAULT_TERMINATOR


def field(text: str) -> str:
    """A field appended to a statement: one blank, then ``text``."""
    return f"{FIELD_SEPARATOR}{text}"


def assignment(name: str, value: str) -> str:
    """A ``name=value`` assignment without blanks."""
    return f"{name}={value}"


def formula(expression: str) -> str:
    """A brace formula, ``{expression}``."""
    return f"{{{expression}}}"


def param_line(name: str, value: str, terminator: str) -> str:
    """A ``.param`` line with one assignment."""
    return f"{PARAM_KEYWORD}{field(assignment(name, value))}{terminator}"


def include_statement(path: str) -> str:
    """An ``.include`` statement with the path quoted, without a terminator."""
    return f'{INCLUDE_KEYWORD}{FIELD_SEPARATOR}"{path}"'
