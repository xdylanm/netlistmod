"""xyce `.SUBCKT`/`.ENDS`, `.MODEL`, the includes and `.LIB` (X-M1 B4; decision 0027 item 7;
xm1-tasks 5.1 points 16 to 18 and 28)."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    BlankLine,
    CommentLine,
    End,
    Formula,
    ModelStatement,
    Netlist,
    Node,
    NumericValue,
    OpaqueBlock,
    OpaqueStatement,
    ParamAssignment,
    ParamStatement,
    ParseError,
    SourceText,
    Span,
    SubcktDefinition,
    Title,
    parse,
)
from netlistmod.dialects import _XYCE
from netlistmod.document.diagnostics import DiagnosticCode
from netlistmod.model.model_types import model_type_table
from netlistmod.model.nodes import FuncStatement, LibCall, PreprocessDirective
from netlistmod.model.values import Identifier


def _parse(text: str) -> Any:
    return parse(SourceText(text), _XYCE)


def _items(body: str) -> Any:
    text = f"t\n{body}.END\n"
    items = _parse(text).items
    position = 0
    for item in items:
        assert item.span.start == position
        position = item.span.end
    assert position == len(text)
    assert isinstance(items[0], Title) and isinstance(items[-1], End)
    return items[1:-1]


def _error(body: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        _parse(f"t\n{body}.END\n")
    return captured.value


# .SUBCKT / .ENDS


def test_subckt_takes_ports_and_optional_params_defaults() -> None:
    (definition,) = _items(".subckt amp in out params: g=2 r={g*1k}\n.param q=1\n.ends amp\n")
    assert isinstance(definition, SubcktDefinition)
    assert definition.keyword == ".subckt"
    assert definition.name == "amp"
    assert definition.ports == (Node("in", Span(14, 16)), Node("out", Span(17, 20)))
    assert definition.params == (
        ParamAssignment("g", NumericValue("2", Span(31, 32)), Span(29, 32), Span(29, 30)),
        ParamAssignment("r", Formula("g*1k", "{", Span(35, 41)), Span(33, 41), Span(33, 34)),
    )
    (body,) = definition.body
    assert isinstance(body, ParamStatement)
    assert definition.ends.name == "amp"


@pytest.mark.parametrize(
    "header",
    [
        ".subckt s a b r=1k",
        ".SUBCKT s a b PARAMS: r=1k",
        ".subckt s a b\n+ params: r=1k",
        ".subckt s a b params:\n+ r=1k",
        ".subckt s a b params: r=1kohm",
        ".subckt s a b params: r='1k'",
    ],
)
def test_params_keyword_is_optional(header: str) -> None:
    # [xyce-ref] §2.1.37 p159 writes `[PARAMS:]`; probe test_subckt_forms. A default reads as a
    # device field (`1kohm`).
    (definition,) = _items(f"{header}\n.ends\n")
    assert [p.name for p in definition.params] == ["r"]


def test_params_keyword_without_defaults_is_read() -> None:
    (definition,) = _items(".subckt s a params:\n.ends\n")
    assert definition.params == ()


def test_a_comma_in_params_is_rejected() -> None:
    # Xyce 7.10 stops on it, the manual's own example included (xm1-tasks 5.1 point 28).
    for header in (".subckt s a params: r=1k, q=2", ".subckt s a params: r=1k ,q=2"):
        error = _error(f"{header}\n.ends\n")
        assert "comma" in error.reason


@pytest.mark.parametrize(
    "word", ["time", "freq", "hertz", "vt", "TEMP", "temper", "gmin", "pi", "exp"]
)
def test_a_reserved_word_is_rejected_as_a_default(word: str) -> None:
    # As on `.PARAM` (scoping.md S7): Xyce stops on time, vt, temp and gmin ("not allowed in
    # subcircuit parameter list") and ignores the others (discrepancies.md).
    for header in (f".subckt s a params: {word}=1", f".subckt s a {word} = 1"):
        error = _error(f"{header}\n.ends\n")
        assert "reserved word" in error.reason
        assert (error.line, error.column) == (2, header.index(word) + 1)


@pytest.mark.parametrize("name", ["1x", "a$b", "x#"])
def test_a_default_takes_a_parameter_name(name: str) -> None:
    # Xyce stops on `1x=1` ("contains illegal character(s)"); a default's name is a parameter
    # name (XY-PRM-001), a letter or `_`, then letters, digits, `_` and `.`.
    error = _error(f".subckt s a params: {name}=1\n.ends\n")
    assert error.line == 2


def test_a_default_name_may_hold_a_dot_and_a_port_may_look_like_a_reserved_word() -> None:
    (definition,) = _items(".subckt s temp time params: a.b=2 _c=3\n.ends\n")
    assert [port.name for port in definition.ports] == ["temp", "time"]
    assert [param.name for param in definition.params] == ["a.b", "_c"]


def test_a_bare_default_is_rejected() -> None:
    # Xyce stops on a bare default ("Cannot convert"; decision X-D5).
    error = _error(".subckt s a params: r=2*1k\n.ends\n")
    assert error.line == 2


@pytest.mark.parametrize(
    "header", [".subckt s", ".subckt s params: r=1", ".subckt s 0", ".subckt s a 0"]
)
def test_a_subckt_needs_a_port_that_is_not_ground(header: str) -> None:
    # At least one port; node 0 is not a port ([xyce-ref] §2.1.37 p160; point 16).
    _error(f"{header}\n.ends\n")


def test_ground_as_a_port_has_its_own_message() -> None:
    assert "cannot be `0`" in _error(".subckt s 0 a\n.ends\n").reason


def test_definitions_nest() -> None:
    (outer,) = _items(
        ".subckt s a\n.subckt t b\n.model m D\n.ends t\nX? \n.ends\n".replace("X? \n", "")
    )
    (inner,) = outer.body
    assert isinstance(inner, SubcktDefinition) and inner.name == "t"
    assert isinstance(inner.body[0], ModelStatement)


def test_a_body_holds_comments_indented_lines_and_the_body_statements() -> None:
    (definition,) = _items(
        ".subckt s a\n* c\n; d\n\n  indented\n.param p=1\n.func f(x) {x}\n"
        ".preprocess replaceground true\n.model m D\n.ends\n"
    )
    kinds = [type(item).__name__ for item in definition.body]
    assert kinds == [
        "CommentLine",
        "CommentLine",
        "BlankLine",
        "IndentedLine",
        "ParamStatement",
        "FuncStatement",
        "PreprocessDirective",
        "ModelStatement",
    ]
    assert isinstance(definition.body[0], CommentLine) and isinstance(definition.body[2], BlankLine)
    assert isinstance(definition.body[5], FuncStatement)
    assert isinstance(definition.body[6], PreprocessDirective)


@pytest.mark.parametrize("line", [".global g", ".global_param g=1", ".END"])
def test_top_level_statements_are_refused_in_a_body(line: str) -> None:
    # Xyce stops on `.global` and `.global_param` in a body (probe); `.END` ends the netlist.
    error = _error(f".subckt s a\n{line}\n.ends\n")
    assert (error.line, error.column) == (3, 1)
    assert "not allowed inside a subcircuit definition" in error.reason


def test_an_output_in_a_body_is_refused() -> None:
    # Xyce silently ignores an output in a body (decision 0028 item 2; XY-DIR-003).
    with pytest.raises(ParseError, match="silently ignores it there") as captured:
        _parse("t\n.subckt s a\n.print tran v(a)\n.ends\n.END\n")
    assert (captured.value.line, captured.value.column) == (3, 1)


@pytest.mark.parametrize("line", [".ends", ".ENDS s", ".endl", ".endl x"])
def test_a_stray_block_end_is_a_syntax_error(line: str) -> None:
    error = _error(f"{line}\n")
    assert (error.line, error.column) == (2, 1)


def test_an_unterminated_subckt_is_named() -> None:
    with pytest.raises(ParseError, match="unterminated `.SUBCKT` block"):
        _parse("t\n.subckt s a\n")


def test_ends_names_are_not_checked_by_the_grammar() -> None:
    (definition,) = _items(".subckt s a\n.ends other\n")
    assert definition.ends.name == "other"
    netlist = Netlist.from_text("t\n.subckt s a\n.ends other\n.END\n", dialect=_XYCE)
    (diagnostic,) = netlist.diagnostics
    assert diagnostic.code is DiagnosticCode.ENDS_NAME_MISMATCH
    assert diagnostic.severity == "info"
    assert "Xyce 7.10 does not check the name" in diagnostic.message


def test_a_body_param_shadowed_by_a_params_default_is_reported() -> None:
    # Xyce 7.10 uses the `PARAMS:` default or the instance's value (scoping.md S6; B3).
    netlist = Netlist.from_text(
        "t\n.subckt s a params: r=1k\n.param r=2k\n.ends\n.END\n", dialect=_XYCE
    )
    (diagnostic,) = netlist.diagnostics
    assert diagnostic.code is DiagnosticCode.DUPLICATE_DEFINITION
    assert diagnostic.severity == "warning"
    assert "`PARAMS:` default" in diagnostic.message
    assert (diagnostic.line, diagnostic.column) == (3, 8)


def test_a_repeated_subckt_or_model_is_reported() -> None:
    # Xyce stops on both (probes; _REPEAT_STOPS).
    netlist = Netlist.from_text(
        "t\n.subckt s a\n.ends\n.subckt s a\n.ends\n.model m D\n.model m D\n.END\n",
        dialect=_XYCE,
    )
    messages = [d.message for d in netlist.diagnostics]
    assert [d.code for d in netlist.diagnostics] == [DiagnosticCode.DUPLICATE_DEFINITION] * 2
    assert all("Xyce 7.10 stops with an error" in message for message in messages)


# .MODEL


@pytest.mark.parametrize(
    ("line", "parenthesized"),
    [
        (".model rmod R (R=2 TC1=0)", True),
        (".MODEL rmod R(R=2 TC1=0)", True),
        (".model rmod R R=2 TC1=0", False),
        (".model rmod R\n+ R=2\n+ TC1=0", False),
        (".model rmod R (\n+ R=2\n+ TC1=0)", True),
    ],
)
def test_model_params_with_or_without_parentheses(line: str, parenthesized: bool) -> None:
    (model,) = _items(f"{line}\n")
    assert isinstance(model, ModelStatement)
    assert (model.name, model.model_type, model.parenthesized) == ("rmod", "R", parenthesized)
    assert [(p.name, p.value.text) for p in model.params] == [("R", "2"), ("TC1", "0")]


@pytest.mark.parametrize("line", [".model rmod R", ".model rmod R ()", ".model rmod R()"])
def test_a_model_may_have_no_params(line: str) -> None:
    (model,) = _items(f"{line}\n")
    assert model.params == ()


def test_model_values_are_device_numbers_or_delimited_expressions() -> None:
    (model,) = _items(".model rmod R R=1kohm TC1={1/3} TC2='1m'\n")
    assert [type(p.value) for p in model.params] == [NumericValue, Formula, Formula]
    # A bare expression stops Xyce ("Cannot convert parameter R"), so the grammar refuses it.
    _error(".model rmod R R=2*1\n")


def test_binned_model_names_are_names() -> None:
    # [xyce-ref] §2.1.21.2 p90: `nch.1`, `nch.2`; MOSFET bin resolution is X-M4's.
    first, second = _items(".model nch.1 nmos (level=14)\n.model nch.2 nmos (level=14)\n")
    assert (first.name, second.name) == ("nch.1", "nch.2")


@pytest.mark.parametrize(
    "line",
    [".model rmod R R=2, TC1=0", ".model rmod R (R=2, TC1=0)", ".model rmod R (R=2) (TC1=0)"],
)
def test_model_lines_take_no_comma_and_one_pair_of_parentheses(line: str) -> None:
    _error(f"{line}\n")


def test_a_repeated_model_parameter_is_rejected() -> None:
    # Xyce stops on it ("Duplicate specification of parameter R"; point 18). Names fold by case.
    error = _error(".model rmod R (R=2 r=3)\n")
    assert (error.line, error.column) == (2, 20)
    assert "written twice" in error.reason


def test_xyce_has_its_own_model_types() -> None:
    table = model_type_table(_XYCE)
    assert table["Resistor"] == {"r", "res"}
    assert table["Capacitor"] == {"c", "cap"}
    assert table["Inductor"] == {"l", "ind"}
    assert table["MutualCoupling"] == {"core"}
    assert table["Diode"] == {"d"}
    # The xyce list replaces the shared one: X-M4's transistors have no VDMOS type (decision 0031
    # item 6), and the switches and lines of later milestones are not listed yet.
    assert table["BipolarTransistor"] == {"npn", "pnp"}
    assert table["Mosfet"] == {"nmos", "pmos"}
    assert table["Jfet"] == {"njf", "pjf"}
    assert table["Mesfet"] == {"nmf", "pmf"}
    assert "VoltageSwitch" not in table


# .INC, .INCL, .INCLUDE


@pytest.mark.parametrize(
    "line",
    [
        ".inc models.lib",
        ".INC 'models.lib'",
        '.inc "path to/models.lib"',
        ".incl models.lib",
        ".include C:/lib/models.lib",
        ".include\n+ models.lib",
        ".inc models.lib ; comment",
    ],
)
def test_includes_take_one_path_quoted_or_not(line: str) -> None:
    (statement,) = _items(f"{line}\n")
    assert type(statement) is OpaqueStatement
    assert statement.kind == "include"
    assert statement.raw == line.split(" ;")[0]


def test_an_include_takes_one_path() -> None:
    # Xyce warns and ignores the rest ("Extraneous data on .INCLUDE ignored"; discrepancies.md).
    _error(".inc models.lib other\n")
    _error(".inc\n")


# .LIB


@pytest.mark.parametrize(
    ("line", "entries"),
    [
        (".lib models.lib nom", ["nom"]),
        (".LIB 'models.lib' low", ["low"]),
        ('.lib "models.lib" low high', ["low", "high"]),
        (".lib models.lib\n+ nom", ["nom"]),
    ],
)
def test_a_lib_call_has_a_file_and_entries(line: str, entries: list[str]) -> None:
    (statement,) = _items(f"{line}\n")
    assert isinstance(statement, LibCall) and isinstance(statement, OpaqueStatement)
    assert statement.kind == "lib"
    assert statement.raw == line
    assert [entry.name for entry in statement.entries] == entries


def test_a_lib_call_with_several_entries_is_reported() -> None:
    # Xyce loads only the first entry, with a warning (probe test_lib_forms).
    netlist = Netlist.from_text('t\n.lib "m.lib" low high\n.END\n', dialect=_XYCE)
    (diagnostic,) = netlist.diagnostics
    assert diagnostic.code is DiagnosticCode.LIB_EXTRA_ENTRIES
    assert diagnostic.severity == "info"
    assert "loads only the first, `low`" in diagnostic.message
    assert (diagnostic.line, diagnostic.column) == (2, 18)
    assert Netlist.from_text("t\n.lib m.lib low\n.END\n", dialect=_XYCE).diagnostics == ()


def test_a_lib_with_one_field_is_a_block() -> None:
    (block, after) = _items(
        ".lib low ; the low corner\n.param rval=2\nr3 2 0 9\n* c\n\n  ind\n.endl LOW\n.param q=1\n"
    )
    assert isinstance(block, OpaqueBlock) and block.kind == "lib"
    assert isinstance(after, ParamStatement)


def test_a_lib_block_must_close_with_its_name() -> None:
    error = _error(".lib low\nr3 2 0 9\n.endl high\n")
    assert (error.line, error.column) == (4, 7)
    assert "names must match" in error.reason
    error = _error(".lib low\nr3 2 0 9\n.endl\n")
    assert "without a name" in error.reason


def test_an_unterminated_lib_block_is_named() -> None:
    with pytest.raises(ParseError, match="unterminated `.LIB` block") as captured:
        _parse("t\n.lib low\nr3 2 0 9\n.END\n")
    assert captured.value.line == 2


def test_the_paths_are_identifiers_as_written() -> None:
    (statement,) = _items(".lib 'a b.lib' tt\n")
    assert statement.entries == (Identifier("tt", Span(17, 19)),)
