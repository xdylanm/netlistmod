"""xyce `.OPTIONS`, `.IC`, `.DCVOLT`, `.NODESET`, `.MEASURE` and the `.DATA` block (X-M2 B3;
decision 0028 items 2 and 5 to 8; xm2-tasks 5.1 points 18 to 27)."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    End,
    Formula,
    IcDirective,
    Identifier,
    MeasureDirective,
    Node,
    NodeCondition,
    NodesetDirective,
    NumericValue,
    OpaqueBlock,
    OptionItem,
    OptionsDirective,
    ParseError,
    SourceText,
    Span,
    SubcktDefinition,
    Title,
    parse,
)
from netlistmod.dialects import _XYCE
from netlistmod.model.nodes import DataTable


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
    assert text[statement.span.start : statement.span.end].rstrip("\n") == line
    return statement


def _error(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        _parse(f"t\n{line}\n.END\n")
    return captured.value


def _at(line: str, piece: str, start: int = 0) -> Span:
    """The span of `piece` in the netlist `_item` builds (the line starts at offset 2)."""
    offset = line.index(piece, start)
    return Span(2 + offset, 2 + offset + len(piece))


def _number(line: str, text: str, start: int = 0) -> NumericValue:
    return NumericValue(text, _at(line, text, start))


# .OPTIONS: packages (XY-OPT-001)

_PACKAGES = [
    "DEVICE",
    "DIAGNOSTIC",
    "TIMEINT",
    "NONLIN",
    "NONLIN-TRAN",
    "NONLIN-HB",
    "LOCA",
    "LINSOL",
    "LINSOL-HB",
    "LINSOL-AC",
    "OUTPUT",
    "RESTART",
    "SAMPLES",
    "EMBEDDEDSAMPLES",
    "PCES",
    "SENSITIVITY",
    "HBINT",
    "DIST",
    "FFT",
    "MEASURE",
    "PARSER",
]


@pytest.mark.parametrize("package", [*_PACKAGES, "timeint", "Nonlin-Tran"])
def test_options_take_each_package_of_the_manual(package: str) -> None:
    line = f".options {package} abc=1"
    options = _item(line)
    assert isinstance(options, OptionsDirective)
    assert options.package == Identifier(package, _at(line, package))
    assert options.options == (
        OptionItem("abc", _at(line, "abc"), _number(line, "1"), _at(line, "abc=1")),
    )


def test_option_is_a_synonym() -> None:
    line = ".OPTION DEVICE TNOM=27"
    options = _item(line)
    assert (options.keyword, options.package.name) == (".OPTION", "DEVICE")


def test_option_scale_stands_without_a_package() -> None:
    line = ".option SCALE = 1e-6"
    options = _item(line)
    assert options.package is None
    assert options.options == (
        OptionItem("SCALE", _at(line, "SCALE"), _number(line, "1e-6"), _at(line, "SCALE = 1e-6")),
    )


@pytest.mark.parametrize(
    ("line", "piece", "message"),
    [
        (".options timint reltol=1", "timint", "did you mean `TIMEINT`"),
        (".options nonlin_tran maxstep=20", "nonlin_tran", "did you mean `NONLIN-TRAN`"),
        (".options print x=1", "print", "is not an `.OPTIONS` package"),
        (".options linsol-es x=1", "linsol-es", "is not an `.OPTIONS` package"),
        (".options zzzz x=1", "zzzz", "the packages are DEVICE"),
        (".options reltol=1e-3", "reltol", "needs a package"),
        (".option reltol=1e-3", "reltol", "needs a package"),
        (".options scale=1e-6", "scale", "only the singular `.OPTION scale=`"),
        (".option scale=1e-6 x=1", "scale", "needs a package"),
        (".options", ".options", "has no item"),
        (".options timeint", "timeint", "has no item"),
        (".options timeint ; comment", "timeint", "has no item"),
    ],
)
def test_a_package_that_is_missing_or_unknown_is_rejected(
    line: str, piece: str, message: str
) -> None:
    error = _error(line)
    assert (error.line, error.column) == (2, 1 + line.index(piece))
    assert message in error.reason


@pytest.mark.parametrize(
    ("line", "message"),
    [
        (".options temp=127", "write `.OPTIONS DEVICE TEMP=`"),
        (".OPTION TNOM=50", "write `.OPTIONS DEVICE TNOM=`"),
        (".options Temp = 27", "Xyce applies a package-less line whose only item is `Temp=`"),
    ],
)
def test_a_packageless_temp_or_tnom_gets_the_device_hint(line: str, message: str) -> None:
    # Xyce 7.10 applies TEMP= or TNOM= alone without a package, silently (discrepancies.md);
    # the manual gives every item a package, so the line stays refused, with the DEVICE hint.
    error = _error(line)
    assert message in error.reason
    assert "silently" in error.reason and "§2.1.25.1 p98" in error.reason


@pytest.mark.parametrize(
    "line", [".options reltol=1e-3", ".options temp=127 reltol=1e-3", ".option tnom=50 x=1"]
)
def test_another_packageless_line_is_ignored_with_a_warning(line: str) -> None:
    error = _error(line)
    assert "needs a package" in error.reason
    assert error.reason.endswith("Xyce ignores a line without one, with a warning")


# .OPTIONS: items and values (XY-OPT-002)


def test_option_values_are_numbers_or_words() -> None:
    line = ".options timeint method = gear reltol=1e-3 maxord=2 erroption=1kohm"
    options = _item(line)
    assert [(item.name, item.value) for item in options.options] == [
        ("method", Identifier("gear", _at(line, "gear"))),
        ("reltol", _number(line, "1e-3")),
        ("maxord", _number(line, "2")),
        ("erroption", _number(line, "1kohm")),
    ]
    assert all(item.values == () and item.pairs == () for item in options.options)


def test_an_option_value_may_be_a_comma_list() -> None:
    line = ".options output outputtimepoints=1n, 2n,3n"
    (item,) = _item(line).options
    assert item.value is None
    assert item.values == (_number(line, "1n"), _number(line, "2n"), _number(line, "3n"))
    assert item.span == _at(line, "outputtimepoints=1n, 2n,3n")


def test_samples_take_expressions_in_braces_and_quotes() -> None:
    line = ".options samples outputs={V(1)},'V(2)' measures=m1,m2 numsamples=10"
    outputs, measures, count = _item(line).options
    assert outputs.values == (
        Formula("V(1)", "{", _at(line, "{V(1)}")),
        Formula("V(2)", "'", _at(line, "'V(2)'")),
    )
    assert measures.values == (Identifier("m1", _at(line, "m1")), Identifier("m2", _at(line, "m2")))
    assert count.value == _number(line, "10")
    embedded = _item(".OPTIONS EMBEDDEDSAMPLES OUTPUTS={V(1)}")
    assert isinstance(embedded.options[0].value, Formula)


@pytest.mark.parametrize("package", ["output", "RESTART"])
def test_initial_interval_takes_pairs(package: str) -> None:
    line = f".options {package} initial_interval=0.1us 1.0us\n+ 0.5us 10us 0.1us"
    (item,) = _item(line).options
    assert item.value == _number(line, "0.1us")
    assert item.pairs == (
        (_number(line, "1.0us"), _number(line, "0.5us")),
        (_number(line, "10us"), _number(line, "0.1us", line.index("10us"))),
    )
    assert item.span == Span(_at(line, "initial_interval").start, len(line) + 2)


def test_options_continue_across_plus_comment_and_indented_lines() -> None:
    line = ".options device\n* comment\n+ tnom=27 ; first\n  indented\n+ temp=30"
    options = _item(line)
    assert [item.name for item in options.options] == ["tnom", "temp"]
    assert len(options.trailing_comments) == 3


@pytest.mark.parametrize(
    ("line", "piece", "message"),
    [
        (".options device tnom={20+7}", "{20+7}", "only in the SAMPLES and EMBEDDEDSAMPLES"),
        (".options device tnom='27'", "'27'", "only in the SAMPLES and EMBEDDEDSAMPLES"),
        (".options device 1 2", "1", "is not a `name=value` item"),
        (".options device tnom", "tnom", "is not a `name=value` item"),
        (".options device tnom=27 foo", "foo", "is not a `name=value` item"),
        (".options device tnom=27 30", "30", "is not a `name=value` item"),
        (".options timeint initial_interval=1n 5n 2n", "5n", "is not a `name=value` item"),
        (".options output initial_interval=1n 5n", "5n", "has no partner"),
        (".options output initial_interval=1n,2n 5n 6n", "5n", "is not a `name=value` item"),
        (".options output initial_interval=1n 5n x", "x", "is not a `name=value` item"),
        (".options device tnom=1abc", "1abc", "is not a number Xyce reads"),
        (".options output outputtimepoints=1n,1abc", "1abc", "is not a number Xyce reads"),
    ],
)
def test_malformed_option_items_are_rejected(line: str, piece: str, message: str) -> None:
    error = _error(line)
    assert (error.line, error.column) == (2, 1 + line.index(piece))
    assert message in error.reason


@pytest.mark.parametrize(
    "line",
    [
        ".options device tnom=27, defad=0",
        ".options device tnom=27,",
        ".options device tnom 27",
        ".options device tnom=",
        ".options device =1",
    ],
)
def test_option_syntax_errors_are_rejected(line: str) -> None:
    assert _error(line).line == 2


# .IC, .DCVOLT (XY-ICN-001) and .NODESET (XY-NOD-001)


@pytest.mark.parametrize("keyword", [".ic", ".IC", ".dcvolt", ".DCVolt"])
def test_ic_takes_voltage_conditions(keyword: str) -> None:
    line = f"{keyword} v(2)=0.5 V(x1:m) = {{p}} v($G1)='1/2'"
    ic = _item(line)
    assert isinstance(ic, IcDirective)
    assert ic.keyword == keyword
    assert ic.conditions == (
        NodeCondition(Node("2", _at(line, "2")), _number(line, "0.5"), _at(line, "v(2)=0.5")),
        NodeCondition(
            Node("x1:m", _at(line, "x1:m")),
            Formula("p", "{", _at(line, "{p}")),
            _at(line, "V(x1:m) = {p}"),
        ),
        NodeCondition(
            Node("$G1", _at(line, "$G1")),
            Formula("1/2", "'", _at(line, "'1/2'")),
            _at(line, "v($G1)='1/2'"),
        ),
    )
    assert all(condition.form == "v" for condition in ic.conditions)


@pytest.mark.parametrize("keyword", [".ic", ".dcvolt", ".nodeset"])
def test_conditions_may_be_node_value_pairs(keyword: str) -> None:
    line = f"{keyword} 2 0.5 x1:m {{p}} v 1.5V"
    statement = _item(line)
    assert [(c.node.name, c.value.text, c.form) for c in statement.conditions] == [
        ("2", "0.5", "pair"),
        ("x1:m", "p", "pair"),
        ("v", "1.5V", "pair"),
    ]
    assert statement.conditions[1].span == _at(line, "x1:m {p}")


def test_nodeset_takes_voltage_conditions() -> None:
    line = ".NODESET V(2)=3.1"
    nodeset = _item(line)
    assert isinstance(nodeset, NodesetDirective)
    assert nodeset.conditions == (
        NodeCondition(Node("2", _at(line, "2")), _number(line, "3.1"), _at(line, "V(2)=3.1")),
    )


def test_conditions_continue_across_plus_lines() -> None:
    line = ".ic v(2)=0.5\n* comment\n+ v(3)=0.25 ; c"
    ic = _item(line)
    assert [c.node.name for c in ic.conditions] == ["2", "3"]
    assert len(ic.trailing_comments) == 2


@pytest.mark.parametrize(
    ("line", "piece", "message"),
    [
        (".ic v(2)=0.5 3 0.25", "3 0.25", "mixes"),
        (".nodeset 2 0.5 v(3)=0.25", "v(3)", "mixes"),
        (".ic i(C1)=1m", "i(", "node voltage only"),
        (".nodeset I(L1)=1m", "I(", "node voltage only"),
        (".nodeset all=0.5", "all", "is not a Xyce initial condition"),
        (".ic v(2)=1 ALL = 0.5", "ALL", "is not a Xyce initial condition"),
        (".ic v(2,3)=0.5", "v(", "takes one node"),
        (".ic", ".ic", "has no condition"),
        (".nodeset ; comment", ".nodeset", "has no condition"),
        (".ic 2", "2", "has no value"),
        (".dcvolt 2 0.5 3", "3", "hangs on an odd number"),
    ],
)
def test_malformed_conditions_are_rejected(line: str, piece: str, message: str) -> None:
    error = _error(line)
    assert (error.line, error.column) == (2, 1 + line.index(piece))
    assert message in error.reason


@pytest.mark.parametrize(
    ("line", "outcome"),
    [
        (".ic all=0.5", "Xyce ignores it on `.ic`, with a warning"),
        (".DCVOLT ALL = 0.5", "Xyce ignores it on `.DCVOLT`, with a warning"),
        (".ic v(2)=1\n+ all=0.5", "Xyce ignores it on `.ic`, with a warning"),
        (".nodeset all=0.5", "Xyce stops on it on `.NODESET`"),
    ],
)
def test_all_is_refused_with_what_xyce_does_on_each_keyword(line: str, outcome: str) -> None:
    # `.IC`/`.DCVOLT` `all=` is warned and ignored by Xyce 7.10, `.NODESET all=` stops it
    # (discrepancies.md); each cites its own section.
    error = _error(line)
    assert error.reason.endswith(outcome)
    section = "§2.1.22 p92" if "nodeset" in line else "§2.1.14 p48"
    assert section in error.reason


@pytest.mark.parametrize(
    ("line", "outcome"),
    [
        (".ic i(C1)=1m", "Xyce ignores a current on `.ic`, with a warning"),
        (".nodeset I(L1)=1m", "Xyce stops on a current on `.NODESET`"),
        (".DCVOLT v(2,3)=0.5", "Xyce ignores a difference on `.DCVOLT`, with a warning"),
        (".nodeset v(2,3)=0.5", "Xyce stops on a difference on `.NODESET`"),
        (".ic v(2)=0.5 3 0.25", "Xyce ignores the other form on `.ic`, with a warning"),
        (".nodeset 2 0.5 v(3)=0.25", "Xyce stops on the other form on `.NODESET`"),
    ],
)
def test_other_refused_conditions_say_what_xyce_does_on_each_keyword(
    line: str, outcome: str
) -> None:
    # Xyce 7.10 warns and ignores what it cannot read on `.IC` and `.DCVOLT`, and stops on
    # `.NODESET` (discrepancies.md).
    assert _error(line).reason.endswith(outcome)


@pytest.mark.parametrize(
    "line",
    [".ic v(2)", ".ic v(2)=", ".ic v(2)=0.5, v(3)=0.25", ".ic 2=0.5", ".ic v(2)=x", ".ic 2 {x"],
)
def test_condition_syntax_errors_are_rejected(line: str) -> None:
    assert _error(line).line == 2


def test_conditions_are_allowed_in_a_body() -> None:
    # Xyce applies them in every instance (decision 0028 item 2).
    text = "t\n.subckt s a\n.ic v(a)=1\n.DCVOLT a 1\n.nodeset a 0.5\nR1 a 0 1k\n.ends\n.END\n"
    (definition,) = _parse(text).items[1:-1]
    assert isinstance(definition, SubcktDefinition)
    kinds = [type(item).__name__ for item in definition.body]
    assert kinds == ["IcDirective", "IcDirective", "NodesetDirective", "Resistor"]


# .MEASURE (XY-MEA-001)


@pytest.mark.parametrize(
    "mode",
    ["TRAN", "dc", "AC", "noise", "FFT", "tran_cont", "DC_CONT", "Ac_Cont", "NOISE_CONT"],
)
def test_measure_takes_each_mode_of_the_manual(mode: str) -> None:
    line = f".measure {mode} res1 max v(1)"
    measure = _item(line)
    assert isinstance(measure, MeasureDirective)
    assert (measure.analysis, measure.analysis_span) == (mode, _at(line, mode))
    assert (measure.result, measure.result_span) == ("res1", _at(line, "res1"))
    assert (measure.body_text, measure.body_span) == ("max v(1)", _at(line, "max v(1)"))


def test_meas_is_a_synonym_and_the_body_continues() -> None:
    line = ".MEAS TRAN rise TRIG v(1)=0.1 RISE=1\n* comment\n+ TARG {v(1)} = 0.9 ; c"
    measure = _item(line)
    assert measure.keyword == ".MEAS"
    assert measure.body_text == "TRIG v(1)=0.1 RISE=1\n* comment\n+ TARG {v(1)} = 0.9"
    assert len(measure.trailing_comments) == 2


@pytest.mark.parametrize(
    ("line", "message"),
    [
        (".meas tr r1 avg v(1)", "(write `TRAN`)"),
        (".meas hb r1 avg v(1)", "is not a `.MEASURE` mode"),
        (".meas OP r1 avg v(1)", "is not a `.MEASURE` mode"),
        (".measure sp r1 avg v(1)", "is not a `.MEASURE` mode"),
        (".meas fft_cont r1 enob v(1)", "is not a `.MEASURE` mode"),
        (".meas r1 avg v(1)", "the mode is required"),
    ],
)
def test_a_measure_mode_outside_the_list_is_rejected(line: str, message: str) -> None:
    error = _error(line)
    assert (error.line, error.column) == (2, 1 + line.index(" ") + 1)
    assert message in error.reason


@pytest.mark.parametrize("line", [".meas", ".meas tran", ".meas tran r1", ".meas tran r1 ; c"])
def test_a_measure_without_its_body_is_rejected(line: str) -> None:
    assert _error(line).line == 2


# .DATA ... .ENDDATA (XY-DAT-001)


def test_data_reads_a_table() -> None:
    text = "t\n.data test\n+ r1 r2\n+ 8.0000e+00 4.0000e+00\n+ 9 4k\n.enddata\n.END\n"
    (table,) = _parse(text).items[1:-1]
    assert isinstance(table, DataTable) and isinstance(table, OpaqueBlock)
    assert (table.kind, table.keyword, table.rows) == ("data", ".data", 2)
    assert table.span == Span(2, text.index(".END"))
    assert table.keyword_span == Span(2, 7)
    assert table.name == Identifier("test", Span(8, 12))
    r1 = text.index("r1")
    assert table.columns == (
        Identifier("r1", Span(r1, r1 + 2)),
        Identifier("r2", Span(r1 + 3, r1 + 5)),
    )
    assert table.body_text == "r1 r2\n+ 8.0000e+00 4.0000e+00\n+ 9 4k"
    assert text[table.body_span.start : table.body_span.end] == table.body_text
    end = text.index(".enddata")
    assert table.end_span == Span(end, end + len(".enddata"))


def test_data_columns_may_follow_the_name_and_rows_are_a_stream() -> None:
    text = "t\n.DATA T R1 R2\n+ 1k 1k 1k\n+ 3k\n.ENDDATA\n.END\n"
    (table,) = _parse(text).items[1:-1]
    assert [column.name for column in table.columns] == ["R1", "R2"]
    assert table.rows == 2
    # A column is a sweep target: a parameter, a device, `dev:param` or `model:param`.
    text = "t\n.data t p R1:R dm:IS\n+ 1 2 3\n.enddata\n.END\n"
    (table,) = _parse(text).items[1:-1]
    assert [column.name for column in table.columns] == ["p", "R1:R", "dm:IS"]


def test_comment_blank_and_indented_lines_may_stand_in_a_table() -> None:
    text = (
        "t\n.data t\n* columns\n+ r1\n\n; rows\n+ 1\n+ 2 ; two\n* end\n\n  indented\n"
        ".enddata ; c\n.END\n"
    )
    (table,) = _parse(text).items[1:-1]
    assert table.rows == 2
    assert table.span.end == text.index(".END")


def test_tables_and_directives_tile_the_source() -> None:
    text = "t\n.data a x\n+ 1\n.enddata\n.data b y\n+ 2\n.ENDDATA\n.dc data=a\n.END\n"
    items = _parse(text).items
    assert [type(item).__name__ for item in items[1:-1]] == [
        "DataTable",
        "DataTable",
        "DcDirective",
    ]


@pytest.mark.parametrize(
    ("body", "piece", "message"),
    [
        (".data t\n+ r1 r2\n+ 1k 1k\n+ 1k\n.enddata", "1k\n.enddata", "3 values for 2 columns"),
        (".data t r1\n.enddata", "r1", "0 values for 1 columns"),
        (".data t\n+ 1 2\n.enddata", "1 2", "has no column names"),
        (".data t\n.enddata", "t\n.enddata", "has no column names"),
        (".data t x:\n+ 1\n.enddata", "x:", "empty part"),
        (".data a:b x\n+ 1\n.enddata", "a:b", "where the table's name is"),
        (".data t\n+ r1\n+ {1k}\n.enddata", "{1k}", "a plain number"),
        (".data t\n+ r1\n+ '1k'\n.enddata", "'1k'", "a plain number"),
        (".data t\n+ r1\n+ 1 x\n.enddata", "x", "stand before the values"),
        (".data t\n+ r1 1abc\n+ 1\n.enddata", "1abc", "is not a number Xyce reads"),
        (".data 1 r1\n+ 1\n.enddata", "1", "where the table's name is"),
        (".data t r1\n+ 1\n.enddata t", "t\n", "takes no name"),
        (".enddata", ".enddata", "closes no `.DATA` table"),
    ],
)
def test_malformed_tables_are_rejected(body: str, piece: str, message: str) -> None:
    text = f"t\n{body}\n.END\n"
    with pytest.raises(ParseError) as captured:
        _parse(text)
    error = captured.value
    offset = text.rindex(piece) if piece.endswith("\n") else text.index(piece, 2)
    line = text.count("\n", 0, offset) + 1
    column = offset - (text.rfind("\n", 0, offset) + 1) + 1
    assert (error.line, error.column) == (line, column)
    assert message in error.reason


@pytest.mark.parametrize(
    "body",
    [
        ".data t r1\n+ 1",
        ".data t r1\n+ 1\nR1 a 0 1k\n.enddata",
        ".data t r1\n+ 1\n.print tran v(1)\n.enddata",
        ".data\n.enddata",
    ],
)
def test_an_unterminated_table_is_rejected(body: str) -> None:
    with pytest.raises(ParseError):
        _parse(f"t\n{body}\n.END\n")


def test_a_table_without_end_at_end_of_input_names_its_opener() -> None:
    with pytest.raises(ParseError) as captured:
        _parse("t\n.data t r1\n+ 1\n")
    assert (captured.value.line, captured.value.column) == (2, 1)
    assert "`.ENDDATA` is missing" in captured.value.reason


# Top level only: Xyce ignores them in a body (decision 0028 item 2).


@pytest.mark.parametrize(
    "lines",
    [
        ".options timeint reltol=1e-3",
        ".OPTION scale=1e-6",
        ".meas tran r avg v(a)",
        ".MEASURE dc r max v(a)",
        ".data t r\n+ 1\n.enddata",
    ],
)
def test_options_measures_and_tables_are_refused_in_a_body(lines: str) -> None:
    with pytest.raises(ParseError) as captured:
        _parse(f"t\n.subckt s a\n{lines}\n.ends\n.END\n")
    error = captured.value
    assert (error.line, error.column) == (3, 1)
    assert "not allowed inside a subcircuit definition" in error.reason
    assert "silently ignores it there" in error.reason


def test_the_directives_round_trip() -> None:
    text = (
        "t\n.options timeint method=gear\n.OPTION SCALE=1u\n.ic v(1)=0\n.nodeset 2 1\n"
        ".meas tran r avg v(1)\n.data t r1\n+ 1\n.enddata\nR1 1 0 1k\n.END\n"
    )
    items = _parse(text).items
    assert "".join(text[item.span.start : item.span.end] for item in items) == text
