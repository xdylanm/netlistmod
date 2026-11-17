"""The closed list of xyce dot-commands (X-M2 B4; decision 0028 items 1 and 2; xm2-tasks 5.1 points
1 to 5): the untyped commands read as `UnknownDirective`, `.SAVE` among them, every other
dot-command refused with hints, `.PREPROCESS ADDRESISTORS` and the other `.PREPROCESS` words, and
which directives a subcircuit body may hold."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    DiagnosticCode,
    End,
    IcDirective,
    Netlist,
    NodesetDirective,
    ParseError,
    SaveDirective,
    SourceText,
    Span,
    SubcktDefinition,
    Title,
    UnknownDirective,
    UnsupportedConstruct,
    parse,
)
from netlistmod.dialects import _XYCE
from netlistmod.model.nodes import PreprocessDirective

# The closed list's untyped commands ([xyce-ref] §2.1; decision 0028 item 1).
_UNTYPED = [
    ".PRINT",
    ".FOUR",
    ".FFT",
    ".RESULT",
    ".SAVE",
    ".SENS",
    ".NOISE",
    ".HB",
    ".LIN",
    ".SAMPLING",
    ".EMBEDDEDSAMPLING",
    ".PCE",
]
# Commands that are not Xyce's: Table 6-1 of [xyce-ref] (p847–848), the ngspice and LTspice ones,
# those the binary knows outside the manual, and misspellings (xm2-tasks 5.1 point 2).
_NOT_XYCE = [
    ".TF",
    ".PZ",
    ".DISTO",
    ".MC",
    ".WCASE",
    ".PLOT",
    ".WATCH",
    ".VECTOR",
    ".AUTOCONVERGE",
    ".DISTRIBUTION",
    ".LOADBIAS",
    ".SAVEBIAS",
    ".STIMULUS",
    ".TEXT",
    ".control",
    ".endc",
    ".if",
    ".endif",
    ".aliases",
    ".backanno",
    ".MOR",
    ".INITCOND",
    ".LOAD",
    ".tarn",
    ".optoins",
    ".tranx",
    ".prints",
    ".save_all",
]
# The hints of point 2.
_HINTS = {
    ".TEMP 27": "`.STEP TEMP ...` (Xyce reference manual §2.1.36 p155) or `.OPTIONS DEVICE TEMP=`",
    ".temp 27 85": "`.STEP TEMP ...`",
    ".PROBE": "write `.PRINT ... FORMAT=PROBE`",
    ".probe v(1)": "write `.PRINT ... FORMAT=PROBE`",
    ".title other": "the first line of the netlist is its title",
    ".TITLE other": "the first line of the netlist is its title",
    ".opt reltol=1e-4": "write `.OPTIONS` and a package",
    ".OPT": "write `.OPTIONS` and a package",
}


def _parse(text: str) -> Any:
    return parse(SourceText(text), _XYCE)


def _items(text: str) -> tuple[Any, ...]:
    """The items of a netlist, which tile its source."""
    items = _parse(text).items
    position = 0
    for item in items:
        assert item.span.start == position
        position = item.span.end
    assert position == len(text)
    return tuple(items)


def _item(line: str) -> Any:
    text = f"t\n{line}\n.END\n"
    items = _items(text)
    assert isinstance(items[0], Title) and isinstance(items[-1], End)
    (statement,) = items[1:-1]
    return statement


def _error(text: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        _parse(text)
    return captured.value


# XY-DIR-001


@pytest.mark.parametrize("name", [*_UNTYPED, *(name.lower() for name in _UNTYPED)])
def test_each_untyped_command_is_an_unknown_directive(name: str) -> None:
    line = f"{name} tran v(1) {{abs(v(2)) + 1}} FILE=out.prn"
    directive = _item(line)
    assert isinstance(directive, UnknownDirective)
    assert directive.name == name
    assert directive.raw == line
    assert directive.name_span == Span(2, 2 + len(name))
    assert directive.trailing_comments == ()


@pytest.mark.parametrize("name", [".pce", ".PRINT"])
def test_an_untyped_command_may_have_no_field(name: str) -> None:
    directive = _item(f"{name} ; c")
    assert isinstance(directive, UnknownDirective)
    assert directive.raw == name
    assert directive.trailing_comments == (Span(2 + len(name) + 1, 2 + len(name) + 4),)


def test_an_untyped_command_continues_across_comment_and_blank_lines() -> None:
    # Xyce joins the `+` lines (point 1); the comments between are the statement's.
    text = "t\n.print tran v(1) ; first\n* between\n\n  indented\n+ v(2)\n+ v(3) ; last\n.END\n"
    (_, directive, _) = _items(text)
    assert isinstance(directive, UnknownDirective)
    assert directive.raw == text[2 : text.index(" ; last")]
    found = [text[span.start : span.end] for span in directive.trailing_comments]
    assert found == ["; first", "* between", "  indented", "; last"]
    assert directive.span == Span(2, text.index(".END"))


def test_an_untyped_command_carries_the_untyped_diagnostic() -> None:
    netlist = Netlist.from_text("t\n.FOUR 1k v(1)\n.END\n", dialect=_XYCE)
    (diagnostic,) = netlist.diagnostics
    assert diagnostic.code is DiagnosticCode.UNTYPED_DIRECTIVE_PRESERVED
    assert diagnostic.severity == "info"
    assert (diagnostic.line, diagnostic.column) == (2, 1)
    assert diagnostic.span == Span(2, 7)


def test_the_untyped_commands_round_trip() -> None:
    text = (
        "t\r\n.print tran v(1)\r\n+ v(2)\r\n.FOUR 1k v(1) ; c\r\n"
        ".sens objfunc={V(1)} param=R1:R\r\n"
        ".hb 1e4\r\n.noise v(1) V1 dec 10 1 1k\r\nR1 1 0 1k\r\n.END\r\n"
    )
    items = _items(text)
    assert "".join(text[item.span.start : item.span.end] for item in items) == text
    assert [type(item) for item in items[1:6]] == [UnknownDirective] * 5


# XY-SAV-001


@pytest.mark.parametrize(
    "line", [".SAVE TYPE=IC FILE=op.ic LEVEL=ALL", ".save", ".save v(2)", ".SAVE TYPE=NODESET"]
)
def test_save_is_never_a_save_directive(line: str) -> None:
    # Xyce's `.SAVE` writes an operating point and has no vectors ([xyce-ref] §2.1.34 p152).
    directive = _item(line)
    assert isinstance(directive, UnknownDirective)
    assert not isinstance(directive, SaveDirective)
    assert directive.raw == line


# XY-DIR-002


@pytest.mark.parametrize("name", _NOT_XYCE)
def test_another_dot_command_is_refused_at_its_first_character(name: str) -> None:
    error = _error(f"t\nR1 1 0 1k\n{name} 1 2\n.END\n")
    assert (error.line, error.column) == (3, 1)
    assert error.reason == f"`{name}` is not an Xyce dot-command, or is not allowed here"


@pytest.mark.parametrize(("line", "hint"), sorted(_HINTS.items()))
def test_some_refusals_carry_a_hint(line: str, hint: str) -> None:
    error = _error(f"t\n{line}\n.END\n")
    assert (error.line, error.column) == (2, 1)
    name = line.split()[0]
    assert error.reason.startswith(f"`{name}` is not an Xyce dot-command, or is not allowed here: ")
    assert hint in error.reason


def test_step_param_and_a_stray_enddata_keep_their_own_refusals() -> None:
    # `.step param` (B2, XY-STP-001) and a `.ENDDATA` without a table (B3, XY-DAT-001).
    assert "no `param` keyword" in _error("t\n.step param x 1 2 1\n.END\n").reason
    assert "closes no `.DATA` table" in _error("t\n.ENDDATA\n.END\n").reason


@pytest.mark.parametrize(
    "block",
    [
        ".control\nrun\nset x = 1\n.endc",
        ".foo\nR3 2 0 1k\n.endfoo",
        ".if (1)\nthis is not a netlist line\n.endif",
        ".aliases\nR1 = r_1\n.endaliases",
    ],
)
def test_a_would_be_block_is_refused_at_its_opener(block: str) -> None:
    # Xyce reads the lines between as circuit lines (point 1); the library stops at the opener,
    # so they are never read.
    error = _error(f"t\nV1 1 0 1\n{block}\n.END\n")
    assert (error.line, error.column) == (3, 1)
    assert f"`{block.split()[0]}` is not an Xyce dot-command" in error.reason


def test_a_refused_command_in_a_body_is_refused_as_at_the_top_level() -> None:
    error = _error("t\n.subckt s a\n.temp 27\n.ends\n.END\n")
    assert (error.line, error.column) == (3, 1)
    assert "`.temp` is not an Xyce dot-command" in error.reason
    assert "`.STEP TEMP ...`" in error.reason


# XY-DIR-003


@pytest.mark.parametrize("name", _UNTYPED)
def test_an_untyped_command_is_refused_in_a_body(name: str) -> None:
    error = _error(f"t\n.subckt s a\nR1 a 0 1k\n{name} tran v(a)\n+ v(b)\n.ends\n.END\n")
    assert (error.line, error.column) == (4, 1)
    assert error.reason == (
        f"`{name}` is not allowed inside a subcircuit definition (`.subckt` ... `.ends`): Xyce "
        "silently ignores it there, so write it at the top level"
    )


@pytest.mark.parametrize(
    "line",
    [
        ".TRAN 1n 1u",
        ".AC DEC 10 1 1k",
        ".DC V1 0 1 0.1",
        ".OP",
        ".STEP R1 1k 2k 1k",
        ".OPTIONS TIMEINT METHOD=GEAR",
        ".OPTION SCALE=1u",
        ".MEAS TRAN r AVG v(a)",
        ".MEASURE DC r MAX v(a)",
        ".DATA t r1\n+ 1\n.ENDDATA",
        *(f"{name} v(a)" for name in _UNTYPED),
    ],
)
def test_every_ignored_directive_is_refused_in_a_body(line: str) -> None:
    # Point 5: Xyce silently ignores the analyses, `.OPTIONS`, `.STEP`, `.MEAS`, `.DATA` and the
    # outputs in a body.
    error = _error(f"t\n.subckt s a\n{line}\n.ends\n.END\n")
    assert (error.line, error.column) == (3, 1)
    assert error.reason.endswith("silently ignores it there, so write it at the top level")


@pytest.mark.parametrize("line", [".GLOBAL a", ".GLOBAL_PARAM g=1", ".END"])
def test_the_statements_xyce_stops_on_in_a_body_say_only_where(line: str) -> None:
    error = _error(f"t\n.subckt s a\n{line}\n.ends\n.END\n")
    assert (error.line, error.column) == (3, 1)
    assert "not allowed inside a subcircuit definition" in error.reason
    assert "ignores" not in error.reason


def test_conditions_and_preprocess_are_allowed_in_a_body() -> None:
    # Xyce applies `.IC`, `.DCVOLT` and `.NODESET` in every instance and `.PREPROCESS` netlist-wide.
    text = (
        "t\n.subckt s a\nR1 a 0 1k\n.IC V(a)=0\n.DCVOLT a 0\n.NODESET V(a)=1\n"
        ".PREPROCESS REPLACEGROUND TRUE\n.PREPROCESS ADDRESISTORS ONETERMINAL 1G\n.ends\n.END\n"
    )
    (_, definition, _) = _items(text)
    assert isinstance(definition, SubcktDefinition)
    kinds = [type(item) for item in definition.body]
    assert kinds[1:] == [
        IcDirective,
        IcDirective,
        NodesetDirective,
        PreprocessDirective,
        UnknownDirective,
    ]


# XY-PRE-002


@pytest.mark.parametrize(
    "line",
    [
        ".PREPROCESS ADDRESISTORS ONETERMINAL 1G",
        ".preprocess addresistors nodcpath 100meg",
        ".Preprocess AddResistors OneTerminal 1e9 ; c",
        ".PREPROCESS\n+ ADDRESISTORS\n* c\n+ NODCPATH 1G",
    ],
)
def test_addresistors_is_an_unknown_directive(line: str) -> None:
    directive = _item(line)
    assert isinstance(directive, UnknownDirective)
    assert directive.name.upper() == ".PREPROCESS"
    assert directive.raw == line.split(" ;")[0]
    assert directive.name_span == Span(2, 13)


def test_each_kind_of_addresistors_may_stand_once() -> None:
    text = (
        "t\n.PREPROCESS ADDRESISTORS ONETERMINAL 1G\n.subckt s a\n"
        ".PREPROCESS ADDRESISTORS NODCPATH 1G\n.ends\n.END\n"
    )
    assert [type(item) for item in _items(text)] == [Title, UnknownDirective, SubcktDefinition, End]


@pytest.mark.parametrize(
    ("text", "line"),
    [
        (
            "t\n.preprocess addresistors oneterminal 1G\n.PREPROCESS ADDRESISTORS ONETERMINAL 2G\n",
            3,
        ),
        (
            "t\n.preprocess addresistors nodcpath 1G\n.subckt s a\n"
            ".preprocess addresistors NODCPATH 1G\n.ends\n",
            4,
        ),
    ],
)
def test_a_second_addresistors_of_one_kind_is_rejected(text: str, line: int) -> None:
    # One of each kind per netlist; Xyce stops on a second ([xyce-ref] §2.1.30 p127).
    error = _error(f"{text}.END\n")
    assert (error.line, error.column) == (line, 1)
    assert "a second `.PREPROCESS ADDRESISTORS " in error.reason


@pytest.mark.parametrize(
    ("line", "column", "message"),
    [
        (".PREPROCESS ADDRESISTORS NOGND 1G", 26, "is not a kind of `.PREPROCESS ADDRESISTORS`"),
        (".PREPROCESS ADDRESISTORS 1G", 26, "is not a kind of `.PREPROCESS ADDRESISTORS`"),
        (".PREPROCESS ADDRESISTORS ONETERMINAL", None, "ends too early"),
        (".PREPROCESS ADDRESISTORS ONETERMINAL {1G}", 38, ""),
        (".PREPROCESS ADDRESISTORS ONETERMINAL 1G 2G", 41, ""),
        (".PREPROCESS ADDRESISTORS", None, "ends too early"),
    ],
)
def test_a_malformed_addresistors_is_rejected(line: str, column: int | None, message: str) -> None:
    error = _error(f"t\n{line}\n.END\n")
    assert error.line == 2
    if column is not None:
        assert error.column == column
    assert message in error.reason


@pytest.mark.parametrize(
    "line", [".preprocess x", ".PREPROCESS NOGND 1G", ".PREPROCESS REPLACE_GROUND TRUE"]
)
def test_another_preprocess_word_is_rejected(line: str) -> None:
    error = _error(f"t\n{line}\n.END\n")
    assert (error.line, error.column) == (2, 13)
    assert "is not a `.PREPROCESS` form" in error.reason
    assert "REPLACEGROUND, REMOVEUNUSED and ADDRESISTORS" in error.reason


def test_removeunused_stays_unsupported_in_a_body_too() -> None:
    with pytest.raises(UnsupportedConstruct, match="it deletes devices") as captured:
        _parse("t\n.subckt s a\n.PREPROCESS REMOVEUNUSED R\n.ends\n.END\n")
    assert (captured.value.line, captured.value.column) == (3, 1)
