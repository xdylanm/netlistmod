"""xyce `.PRINT`, typed shallowly (X-M2.1 C3; decision 0029 item 5): a print type of the manual's
closed list, required and first, then the rest kept as text, across `+` lines, top level only
(`XY-PRT-001`)."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    DiagnosticCode,
    Dialect,
    End,
    Netlist,
    ParseError,
    SourceText,
    Span,
    Title,
    UnknownDirective,
    parse,
)
from netlistmod.dialects import _XYCE
from netlistmod.model.nodes import PrintDirective

# The print types of [xyce-ref] §2.1.31 p128 (its table) and §2.1.31.6 and §2.1.31.7 (HOMOTOPY,
# SENS and TRANADJOINT).
PRINT_TYPES = [
    "AC",
    "AC_IC",
    "DC",
    "ES",
    "HB",
    "HB_FD",
    "HB_IC",
    "HB_STARTUP",
    "HB_TD",
    "NOISE",
    "PCE",
    "TRAN",
    "HOMOTOPY",
    "SENS",
    "TRANADJOINT",
]


def _parse(text: str) -> Any:
    return parse(SourceText(text), _XYCE)


def _item(line: str) -> Any:
    """The one statement of a netlist holding `line`; the items tile the source."""
    text = f"t\n{line}\n.END\n"
    items = _parse(text).items
    position = 0
    for item in items:
        assert item.span.start == position
        position = item.span.end
    assert position == len(text)
    assert isinstance(items[0], Title) and isinstance(items[-1], End)
    (statement,) = items[1:-1]
    return statement


def _error(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        _parse(f"t\n{line}\n.END\n")
    return captured.value


@pytest.mark.parametrize(
    "kind", [*PRINT_TYPES, *(kind.lower() for kind in PRINT_TYPES), "Tran", "Hb_Fd"]
)
def test_print_takes_each_type_of_the_manual(kind: str) -> None:
    line = f".PRINT {kind} FORMAT=CSV v(1) {{abs(v(2)) + 1}}"
    directive = _item(line)
    assert isinstance(directive, PrintDirective)
    assert (directive.keyword, directive.keyword_span) == (".PRINT", Span(2, 8))
    assert directive.print_type == kind
    assert directive.print_type_span == Span(9, 9 + len(kind))
    body = line[line.index("FORMAT") :]
    assert directive.body_text == body
    assert directive.body_span == Span(2 + line.index("FORMAT"), 2 + len(line))
    assert directive.trailing_comments == ()


def test_print_continues_across_comment_and_blank_lines() -> None:
    # Xyce joins the `+` lines ([xyce-ug] §4.1.3.2 p43); the comments between are the statement's,
    # and inside its body.
    text = "t\n.print tran v(1) ; first\n* between\n\n  indented\n+ v(2)\n+ v(3) ; last\n.END\n"
    (_, directive, _) = _parse(text).items
    assert isinstance(directive, PrintDirective)
    assert directive.body_text == text[text.index("v(1)") : text.index(" ; last")]
    found = [text[span.start : span.end] for span in directive.trailing_comments]
    assert found == ["; first", "* between", "  indented", "; last"]
    assert directive.span == Span(2, text.index(".END"))


def test_the_type_may_follow_on_a_plus_line() -> None:
    directive = _item(".print\n+ dc v(1)")
    assert isinstance(directive, PrintDirective)
    assert (directive.print_type, directive.body_text) == ("dc", "v(1)")


def test_print_round_trips() -> None:
    text = "t\r\n.PRINT TRAN v(1)\r\n+ i(V1) ; c\r\n.print ac vm(1)\r\nR1 1 0 1k\r\n.END\r\n"
    items = _parse(text).items
    assert "".join(text[item.span.start : item.span.end] for item in items) == text
    assert [type(item) for item in items[1:3]] == [PrintDirective] * 2


@pytest.mark.parametrize(
    ("line", "word"),
    [
        (".print foo v(1)", "foo"),
        (".print transient v(1)", "transient"),
        (".print op v(1)", "op"),
        (".print sp v(1)", "sp"),
        (".print noise_ic v(1)", "noise_ic"),
        (".print v(1)", "v(1)"),
        (".print format=csv tran v(1)", "format=csv"),
        (".print tran, v(1)", "tran,"),
    ],
)
def test_a_print_type_outside_the_list_is_rejected(line: str, word: str) -> None:
    # Xyce stops on each ("Analysis type ... and print type ... are inconsistent").
    error = _error(line)
    assert (error.line, error.column) == (2, 8)
    assert error.reason.startswith(f"`{word}` is not a `.PRINT` type: the print type is required")
    assert "TRANADJOINT (Xyce reference manual §2.1.31 p128)" in error.reason


@pytest.mark.parametrize("word", ["tr", "TR"])
def test_tr_is_rejected_with_a_hint(word: str) -> None:
    # Xyce runs `TR` as TRAN (discrepancies.md); the manual's type is TRAN.
    error = _error(f".print {word} v(1)")
    assert error.reason.startswith(f"`{word}` is not a `.PRINT` type (write `TRAN`)")


@pytest.mark.parametrize("line", [".print", ".PRINT ; c"])
def test_a_print_without_its_type_is_rejected(line: str) -> None:
    error = _error(line)
    assert (error.line, error.column) == (2, 1)
    assert error.reason.startswith(f"`{line.split()[0]}` has no print type")
    assert error.reason.endswith("then the output variables (Xyce reference manual §2.1.31 p128)")


@pytest.mark.parametrize("line", [".print tran", ".print TRAN ; c"])
def test_a_print_without_a_field_is_rejected(line: str) -> None:
    error = _error(line)
    assert (error.line, error.column) == (2, 8)
    assert error.reason == (
        f"`{' '.join(line.split()[:2])}` has no output variable: write at least one after the "
        "print type (Xyce reference manual §2.1.31 p128)"
    )


@pytest.mark.parametrize("name", [".prints", ".print_x", ".printx"])
def test_a_longer_word_is_not_print(name: str) -> None:
    error = _error(f"{name} tran v(1)")
    assert error.reason == f"`{name}` is not an Xyce dot-command, or is not allowed here"


def test_print_is_refused_in_a_body() -> None:
    with pytest.raises(ParseError) as captured:
        _parse("t\n.subckt s a\n.print tran v(a)\n.ends\nX1 1 s\n.END\n")
    assert (captured.value.line, captured.value.column) == (3, 1)
    assert captured.value.reason == (
        "`.print` is not allowed inside a subcircuit definition (`.subckt` ... `.ends`): Xyce "
        "silently ignores it there, so write it at the top level"
    )


def test_print_is_not_reported_as_untyped() -> None:
    text = "t\nR1 1 0 1k\n.print tran v(1)\n.tran 1n 2n\n.END\n"
    assert Netlist.from_text(text, dialect=_XYCE).diagnostics == ()


def test_print_stays_untyped_on_ngspice() -> None:
    # LTspice has no `.print` (its closed list refuses it), so ngspice is the one to check.
    text = "t\n.print tran v(1)\n.end\n"
    (_, directive, *_) = parse(SourceText(text), Dialect.NGSPICE).items
    assert isinstance(directive, UnknownDirective)
    codes = [d.code for d in Netlist.from_text(text, dialect=Dialect.NGSPICE).diagnostics]
    assert codes == [DiagnosticCode.UNTYPED_DIRECTIVE_PRESERVED]
