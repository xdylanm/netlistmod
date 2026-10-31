"""Statements and directives (M4): accept and reject tests, sub-spans and errors."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    AcDirective,
    BlankLine,
    CommentLine,
    DcDirective,
    Dialect,
    End,
    EndsLine,
    Flag,
    Formula,
    IcDirective,
    Identifier,
    MeasureDirective,
    ModelStatement,
    NodesetDirective,
    NumericValue,
    OpaqueBlock,
    OpaqueStatement,
    OpDirective,
    OptionsDirective,
    ParamStatement,
    ParseError,
    Resistor,
    SaveDirective,
    SourceText,
    Span,
    SubcktDefinition,
    SubcktInstance,
    TempDirective,
    TranDirective,
    UnknownDirective,
    parse,
)
from netlistmod.grammar.loader import build_parser


def _parse(text: str):
    return parse(SourceText(text), Dialect.NGSPICE)


def _item(statement: str) -> Any:
    """Parse one statement (possibly several lines); its span must cover it and its newline."""
    text = f"title\n{statement}\n.end\n"
    result = _parse(text)
    assert len(result.items) == 3, result.items
    item = result.items[1]
    assert item.span == Span(6, 6 + len(statement) + 1)
    return item


def _reject(statement: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        _parse(f"title\n{statement}\n.end\n")
    return captured.value


def _slice(statement: str, span: Span | None) -> str:
    assert span is not None
    return f"title\n{statement}\n"[span.start : span.end]


def _assert_tiling(
    text: str, items: tuple[Any, ...], start: int = 0, end: int | None = None
) -> None:
    offset = start
    for item in items:
        assert item.span.start == offset
        offset = item.span.end
    assert offset == (len(text) if end is None else end)


def _values(item: Any) -> list[Any]:
    values = [getattr(item, name, None) for name in ("tstep", "tstop", "tstart", "tmax")]
    values += [getattr(item, name, None) for name in ("points", "fstart", "fstop", "value")]
    return [value for value in values if value is not None]


# NG-PRM-001 .param


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        (".param pippo=5", [("pippo", "5", NumericValue)]),
        (".param po=6 pp=7.8", [("po", "6", NumericValue), ("pp", "7.8", NumericValue)]),
        (".param p={pp}", [("p", "pp", Formula)]),
        (".param pop='pp+p'", [("pop", "pp+p", Formula)]),
        ('.PARAM s="txt"', [("s", "txt", Formula)]),
        (".param c = {a + 1k}", [("c", "a + 1k", Formula)]),
        (".param x=1 x=2", [("x", "1", NumericValue), ("x", "2", NumericValue)]),
        (".param a!#%[1]_b=-1e3", [("a!#%[1]_b", "-1e3", NumericValue)]),
        (".param a=1\n+ b=2 ; c", [("a", "1", NumericValue), ("b", "2", NumericValue)]),
        (".param timer=1", [("timer", "1", NumericValue)]),
    ],
)
def test_param_statement_assignments_and_spans(
    statement: str, expected: list[tuple[str, str, type]]
) -> None:
    item = _item(statement)
    assert isinstance(item, ParamStatement)
    assert _slice(statement, item.keyword_span) == statement.split()[0]
    assert [(a.name, a.value.text, type(a.value)) for a in item.assignments] == expected
    for assignment in item.assignments:
        assert _slice(statement, assignment.name_span) == assignment.name
        value = _slice(statement, assignment.value.span)
        assert value.strip("{}'\"") == assignment.value.text
        assert _slice(statement, assignment.span).startswith(assignment.name)
        assert _slice(statement, assignment.span).endswith(value)


@pytest.mark.parametrize(
    ("statement", "column", "reason"),
    [
        (".param c = a+1k", 12, "bare expression"),
        (".param c = a", 12, "bare expression"),
        (".param a = 123 * 3", 12, "bare expression"),
        (".param c=1k+a", 10, "bare expression"),
        (".param", 7, ""),
        (".param x=", 10, ""),
        (".param time=1", 8, "reserved name"),
        (".param TEMPER=1", 8, "reserved name"),
        (".param hertz=1", 8, "reserved name"),
        (".param 1a=2", 8, ""),
        (".param a=1,b=2", 10, "bare expression"),
        (".param a=1 b", 13, ""),
        (".param a$b=1", 9, ""),
    ],
)
def test_malformed_param_statements_are_rejected(statement: str, column: int, reason: str) -> None:
    error = _reject(statement)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


# NG-MOD-001 .model


@pytest.mark.parametrize(
    ("statement", "name", "model_type", "params", "parenthesized"),
    [
        (
            ".model MOD1 npn (bf=50 is=1e-13 vbf=50)",
            "MOD1",
            "npn",
            [("bf", "50"), ("is", "1e-13"), ("vbf", "50")],
            True,
        ),
        (".MODEL ind1 L tc1=0.001", "ind1", "L", [("tc1", "0.001")], False),
        (".model dm D is=1e-14, n=1.5", "dm", "D", [("is", "1e-14"), ("n", "1.5")], False),
        (".model dm D(is=1e-14\n+ n=1.5)", "dm", "D", [("is", "1e-14"), ("n", "1.5")], True),
        (".model dm D( is=1 , n={nn} )", "dm", "D", [("is", "1"), ("n", "nn")], True),
        (".model dm D ; c\n+ (is=1) $ d", "dm", "D", [("is", "1")], True),
        (".model dm D()", "dm", "D", [], True),
        (".model dm D", "dm", "D", [], False),
        (".model sw1 aswitch(cntl_off=0)", "sw1", "aswitch", [("cntl_off", "0")], True),
        (".model d1 D is=1 is=2", "d1", "D", [("is", "1"), ("is", "2")], False),
    ],
)
def test_model_statement_fields_and_spans(
    statement: str,
    name: str,
    model_type: str,
    params: list[tuple[str, str]],
    parenthesized: bool,
) -> None:
    item = _item(statement)
    assert isinstance(item, ModelStatement)
    assert (item.name, item.model_type, item.parenthesized) == (name, model_type, parenthesized)
    assert _slice(statement, item.name_span) == name
    assert _slice(statement, item.model_type_span) == model_type
    assert [(p.name, p.value.text) for p in item.params] == params
    for param in item.params:
        assert _slice(statement, param.name_span) == param.name


@pytest.mark.parametrize(
    ("statement", "column", "reason"),
    [
        (".model dm D(is=1e-14", 12, "unbalanced `(`"),
        (".model dm D(is=1e-14\n+ n=1.5", 12, "unbalanced `(`"),
        (".model dm", 10, ""),
        (".model", 7, ""),
        (".model x D bf", 14, ""),
        (".model x D(is=1,)", 17, ""),
        (".model x D(,is=1)", 12, ""),
        (".model x D(is=1) n=2", 18, ""),
        (".model x D is=a", 15, ""),
    ],
)
def test_malformed_model_statements_are_rejected(statement: str, column: int, reason: str) -> None:
    error = _reject(statement)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


def test_parentheses_stay_errors_on_element_lines() -> None:
    for line, column in (("R1 a b 1k (x)", 11), ("X1 a b sub(1)", 11)):
        error = _reject(line)
        assert (error.line, error.column) == (2, column)


# NG-SBD-001 .subckt ... .ends


def test_subcircuit_definition_fields_body_and_spans() -> None:
    statement = ".subckt div a b r2=1k ; header\nR1 a b 1k\n* body comment\n\n.ends div"
    item = _item(statement)
    assert isinstance(item, SubcktDefinition)
    assert (item.name, [p.name for p in item.ports]) == ("div", ["a", "b"])
    assert [(p.name, p.value.text) for p in item.params] == [("r2", "1k")]
    assert _slice(statement, item.name_span) == "div"
    assert [_slice(statement, p.span) for p in item.ports] == ["a", "b"]
    assert _slice(statement, item.keyword_span) == ".subckt"
    assert _slice(statement, item.header_span) == ".subckt div a b r2=1k ; header\n"
    assert [_slice(statement, s) for s in item.trailing_comments] == ["; header"]
    assert [type(i) for i in item.body] == [Resistor, CommentLine, BlankLine]
    _assert_tiling("", item.body, item.header_span.end, item.ends.span.start)
    assert item.ends == EndsLine("div", item.ends.name_span, item.ends.span)
    assert _slice(statement, item.ends.name_span) == "div"
    assert _slice(statement, item.ends.span) == ".ends div\n"


@pytest.mark.parametrize(
    ("statement", "ends_name"),
    [
        (".subckt div a b\nR1 a b 1k\n.ends", None),
        (".subckt div a b\nR1 a b 1k\n.ends other", "other"),
        (".subckt div a b\n.ends", None),
        (".SUBCKT div a a\n.ENDS DIV ; c", "DIV"),
        (".subckt div 1 2 3 4\n.ends", None),
    ],
)
def test_subcircuit_ends_name_is_recorded_not_checked(
    statement: str, ends_name: str | None
) -> None:
    item = _item(statement)
    assert isinstance(item, SubcktDefinition)
    assert item.ends.name == ends_name


def test_nested_subcircuits_and_allowed_body_items() -> None:
    statement = (
        ".subckt outer a b\n"
        ".subckt inner p q r=1\n"
        "R1 p q {r}\n"
        ".ends inner\n"
        ".model dm D\n"
        ".param k=2\n"
        "* c\n"
        ".include x.inc\n"
        ".if (1)\n"
        "R2 a b 1k\n"
        ".endif\n"
        ".global gnd\n"
        "X1 a b inner r=2\n"
        ".ends outer"
    )
    outer = _item(statement)
    assert isinstance(outer, SubcktDefinition)
    kinds = [type(item) for item in outer.body]
    assert kinds == [
        SubcktDefinition,
        ModelStatement,
        ParamStatement,
        CommentLine,
        OpaqueStatement,
        OpaqueBlock,
        UnknownDirective,
        SubcktInstance,
    ]
    _assert_tiling("", outer.body, outer.header_span.end, outer.ends.span.start)
    inner = outer.body[0]
    assert isinstance(inner, SubcktDefinition)
    assert inner.name == "inner" and inner.ends.name == "inner"
    assert _slice(statement, inner.span) == ".subckt inner p q r=1\nR1 p q {r}\n.ends inner\n"
    _assert_tiling("", inner.body, inner.header_span.end, inner.ends.span.start)


@pytest.mark.parametrize(
    ("body", "keyword"),
    [
        (".tran 1u 10u", ".tran"),
        (".ac dec 10 1 1k", ".ac"),
        (".dc v1 0 1 1", ".dc"),
        (".op", ".op"),
        (".options reltol=1", ".options"),
        (".OPTION reltol=1", ".OPTION"),
        (".temp 27", ".temp"),
        (".ic v(1)=0", ".ic"),
        (".nodeset all=0", ".nodeset"),
        (".save all", ".save"),
        (".meas tran x MAX v(1)", ".meas"),
        (".measure tran x MAX v(1)", ".measure"),
        (".title inside", ".title"),
        (".control\nrun\n.endc", ".control"),
        (".tran garbage (", ".tran"),
    ],
)
def test_statements_not_allowed_in_a_subcircuit_are_rejected_at_the_keyword(
    body: str, keyword: str
) -> None:
    error = _reject(f".subckt div a b\nR1 a b 1k\n{body}\n.ends")
    assert (error.line, error.column) == (4, 1)
    assert f"`{keyword}` is not allowed inside a subcircuit definition" in error.reason


def test_end_inside_a_subcircuit_is_rejected() -> None:
    error = _reject(".subckt div a b\n.end\n.ends")
    assert (error.line, error.column) == (3, 1)
    assert "`.end` is not allowed inside a subcircuit" in error.reason


@pytest.mark.parametrize(
    ("statement", "column", "reason"),
    [
        (".subckt div a 0\n.ends", 15, "cannot be `0`"),
        (".subckt div 0 a\n.ends", 13, "cannot be `0`"),
        (".subckt div\n.ends", 12, ""),
        (".subckt\n.ends", 8, ""),
        (".subckt div a b params: r=1\n.ends", 17, "`params:`"),
        (".subckt div a b r=1 c\n.ends", 22, ""),
        (".subckt div a b r=x\n.ends", 19, ""),
        (".subckt div a b\n.ends a b", 9, ""),
    ],
)
def test_malformed_subcircuit_lines_are_rejected(statement: str, column: int, reason: str) -> None:
    error = _reject(statement)
    line = 2 if ".ends a b" not in statement else 3
    assert (error.line, error.column) == (line, column)
    assert reason in error.reason


@pytest.mark.parametrize(
    ("text", "line"),
    [
        ("title\n.subckt div a b\nR1 a b 1k\n.end\n", 2),
        ("title\n.subckt div a b\nR1 a b 1k\n.end", 2),
        ("title\n.subckt outer a b\n.subckt inner p q\n.ends\n.end\n", 2),
        ("title\n.subckt outer a b\n.subckt inner p q\n.end\n", 3),
        ("title\n.subckt div a b\n", 2),
    ],
)
def test_unterminated_subcircuit_is_reported_at_its_innermost_open_line(
    text: str, line: int
) -> None:
    with pytest.raises(ParseError) as captured:
        _parse(text)
    assert (captured.value.line, captured.value.column) == (line, 1)
    assert captured.value.expected == ("`.ends`",)
    assert "unterminated `.subckt` block" in captured.value.reason


@pytest.mark.parametrize("text", ["title\n.ends\n.end\n", "title\n.ENDS div\n.end\n"])
def test_stray_ends_is_rejected(text: str) -> None:
    with pytest.raises(ParseError) as captured:
        _parse(text)
    assert (captured.value.line, captured.value.column) == (2, 1)


def test_ends_like_names_stay_unknown_directives() -> None:
    assert isinstance(_item(".endsx a"), UnknownDirective)


# NG-TRN-001, NG-ACA-001, NG-DCA-001, NG-OPP-001 analyses


@pytest.mark.parametrize(
    ("statement", "values", "uic"),
    [
        (".tran 1ns 100ns", ["1ns", "100ns"], None),
        (".tran 1ns 1000ns 500ns", ["1ns", "1000ns", "500ns"], None),
        (".tran 1n 1u 0 10p uic", ["1n", "1u", "0", "10p"], "uic"),
        (".TRAN 1n 1u UIC", ["1n", "1u"], "UIC"),
        (".tran 1n 1u 0 UIC", ["1n", "1u", "0"], "UIC"),
        (".tran {ts} '2*ts'", ["ts", "2*ts"], None),
        (".tran 1n\n+ 1u ; c", ["1n", "1u"], None),
    ],
)
def test_tran_directive_fields(statement: str, values: list[str], uic: str | None) -> None:
    item = _item(statement)
    assert isinstance(item, TranDirective)
    assert [value.text for value in _values(item)] == values
    assert (item.uic.name if item.uic else None) == uic
    if item.uic is not None:
        assert item.uic == Flag(uic or "", item.uic.span)
        assert _slice(statement, item.uic.span) == uic
    for value in _values(item):
        assert _slice(statement, value.span).strip("{}'") == value.text


@pytest.mark.parametrize(
    ("statement", "variation", "values"),
    [
        (".ac dec 10 1 10K", "dec", ["10", "1", "10K"]),
        (".ac dec 10 1K 100MEG", "dec", ["10", "1K", "100MEG"]),
        (".ac lin 100 1 100HZ", "lin", ["100", "1", "100HZ"]),
        (".AC OCT 5 1 1k", "OCT", ["5", "1", "1k"]),
    ],
)
def test_ac_directive_fields(statement: str, variation: str, values: list[str]) -> None:
    item = _item(statement)
    assert isinstance(item, AcDirective)
    assert item.variation == variation
    assert _slice(statement, item.variation_span) == variation
    assert [value.text for value in _values(item)] == values


@pytest.mark.parametrize(
    ("statement", "sweeps"),
    [
        (".dc VIN 0.25 5.0 0.25", [("VIN", "0.25", "5.0", "0.25")]),
        (".dc VDS 0 10 .5 VGS 0 5 1", [("VDS", "0", "10", ".5"), ("VGS", "0", "5", "1")]),
        (".dc VCE 0 10 .25 IB 0 10u 1u", [("VCE", "0", "10", ".25"), ("IB", "0", "10u", "1u")]),
        (".dc RLoad 1k 2k 100", [("RLoad", "1k", "2k", "100")]),
        (".dc TEMP -15 75 5", [("TEMP", "-15", "75", "5")]),
    ],
)
def test_dc_directive_sweeps(statement: str, sweeps: list[tuple[str, ...]]) -> None:
    item = _item(statement)
    assert isinstance(item, DcDirective)
    actual = [(s.source, s.start.text, s.stop.text, s.increment.text) for s in item.sweeps]
    assert actual == sweeps
    for sweep in item.sweeps:
        assert _slice(statement, sweep.source_span) == sweep.source
        assert _slice(statement, sweep.span).startswith(sweep.source)
        assert _slice(statement, sweep.span).endswith(sweep.increment.text)


@pytest.mark.parametrize("statement", [".op", ".OP", ".op ; comment"])
def test_op_directive(statement: str) -> None:
    item = _item(statement)
    assert isinstance(item, OpDirective)
    assert _slice(statement, item.keyword_span).lower() == ".op"


@pytest.mark.parametrize(
    ("statement", "column"),
    [
        (".tran 1ns", 10),
        (".tran", 6),
        (".tran 1n 1u 0 1n 1n", 18),
        (".tran 1n 1u uic 0", 17),
        (".ac dec 10 1", 13),
        (".ac log 10 1 1k", 5),
        (".ac 10 1 1k", 5),
        (".dc VIN 0 5", 12),
        (".dc VIN 0 5 1 VGS 0 1", 22),
        (".dc VIN 0 5 1 VGS 0 1 1 X 0 1 1", 25),
        (".op 1", 5),
    ],
)
def test_malformed_analyses_are_rejected(statement: str, column: int) -> None:
    error = _reject(statement)
    assert (error.line, error.column) == (2, column)


# NG-OPT-001, NG-TMP-001, NG-ICN-001


@pytest.mark.parametrize(
    ("statement", "options"),
    [
        (".options reltol=.005 trtol=8", [("reltol", ".005"), ("trtol", "8")]),
        (".option noacct", [("noacct", None)]),
        (".OPTIONS method=gear noinit", [("method", "gear"), ("noinit", None)]),
        (".options temp={t0} a = 1", [("temp", "t0"), ("a", "1")]),
        (".options a,b", [("a", None), ("b", None)]),
    ],
)
def test_options_directive_items(statement: str, options: list[tuple[str, str | None]]) -> None:
    item = _item(statement)
    assert isinstance(item, OptionsDirective)
    actual = [
        (
            o.name,
            None
            if o.value is None
            else (o.value.name if isinstance(o.value, Identifier) else o.value.text),
        )
        for o in item.options
    ]
    assert actual == options
    for option in item.options:
        assert _slice(statement, option.name_span) == option.name
        assert _slice(statement, option.span).startswith(option.name)
    if "gear" in statement:
        assert isinstance(item.options[0].value, Identifier)


@pytest.mark.parametrize(("statement", "value"), [(".temp 27", "27"), (".TEMP {t}", "t")])
def test_temp_directive(statement: str, value: str) -> None:
    item = _item(statement)
    assert isinstance(item, TempDirective)
    assert item.value.text == value


@pytest.mark.parametrize(
    ("statement", "kind", "conditions"),
    [
        (".ic v(11)=5 v(4)=-5 v(2)=2.2", IcDirective, [("11", "5"), ("4", "-5"), ("2", "2.2")]),
        (".nodeset v(12)=4.5 v(4)=2.23", NodesetDirective, [("12", "4.5"), ("4", "2.23")]),
        (".nodeset all=1.5", NodesetDirective, [(None, "1.5")]),
        (".IC V(out) = {v0}", IcDirective, [("out", "v0")]),
        (".ic v( n1 )=1", IcDirective, [("n1", "1")]),
        (".ic v(/vout)=1", IcDirective, [("/vout", "1")]),
    ],
)
def test_initial_condition_directives(
    statement: str, kind: type, conditions: list[tuple[str | None, str]]
) -> None:
    item = _item(statement)
    assert isinstance(item, kind)
    actual = [(c.node.name if c.node else None, c.value.text) for c in item.conditions]
    assert actual == conditions
    for condition in item.conditions:
        if condition.node is not None:
            assert _slice(statement, condition.node.span) == condition.node.name
        assert _slice(statement, condition.span).lower().startswith(("v(", "all"))


@pytest.mark.parametrize(
    ("statement", "column", "reason"),
    [
        (".options", 9, ""),
        (".options a=", 12, ""),
        (".temp", 6, ""),
        (".temp 27 30", 10, ""),
        (".ic all=1", 5, ""),
        (".ic v(1)", 9, ""),
        (".ic v(1=5", 8, ""),
        (".ic v(1", 5, "unbalanced `(`"),
        (".ic v (1)=1", 5, ""),
        (".ic v(1,2)=1", 8, ""),
        (".ic", 4, ""),
        (".nodeset v(1)=1 all=2", 17, ""),
        (".nodeset all=1 all=2", 16, ""),
    ],
)
def test_malformed_option_and_condition_directives_are_rejected(
    statement: str, column: int, reason: str
) -> None:
    error = _reject(statement)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


# NG-SAV-001 .save, NG-MEA-001 .meas


@pytest.mark.parametrize(
    ("statement", "vectors"),
    [
        (".save i(vin) node1 v(node2)", ["i(vin)", "node1", "v(node2)"]),
        (".save @m1[id] vsource#branch", ["@m1[id]", "vsource#branch"]),
        (".save all @m2[vdsat]", ["all", "@m2[vdsat]"]),
        (".SAVE V(a,b) I(v1)\n+ out", ["V(a,b)", "I(v1)", "out"]),
    ],
)
def test_save_directive_vectors(statement: str, vectors: list[str]) -> None:
    item = _item(statement)
    assert isinstance(item, SaveDirective)
    assert [v.text for v in item.vectors] == vectors
    assert [_slice(statement, v.span) for v in item.vectors] == vectors


@pytest.mark.parametrize(
    ("statement", "column"),
    [(".save", 6), (".save vdb(out)", 10), (".save v(a, b)", 8)],
)
def test_malformed_save_directives_are_rejected(statement: str, column: int) -> None:
    error = _reject(statement)
    assert (error.line, error.column) == (2, column)


@pytest.mark.parametrize(
    ("statement", "analysis", "result", "body"),
    [
        (
            ".measure tran tdiff TRIG v(1) VAL=0.5 RISE=1 TARG v(1) VAL=0.5 RISE=2",
            "tran",
            "tdiff",
            "TRIG v(1) VAL=0.5 RISE=1 TARG v(1) VAL=0.5 RISE=2",
        ),
        (".meas ac vmax MAX vdb(out)", "ac", "vmax", "MAX vdb(out)"),
        (".MEAS DC x WHEN v(1)=1", "DC", "x", "WHEN v(1)=1"),
        (".meas sp x MAX v(1)", "sp", "x", "MAX v(1)"),
        (".meas tran x param='a*2' ; c", "tran", "x", "param='a*2'"),
        (".meas tran x FIND v(1)\n+ AT=1m", "tran", "x", "FIND v(1)\n+ AT=1m"),
        (".meas tran x\n+ FIND v(1) AT=1m", "tran", "x", "FIND v(1) AT=1m"),
        (".meas tran x ; c\n+ FIND v(1) AT=1m", "tran", "x", "FIND v(1) AT=1m"),
    ],
)
def test_measure_directive_is_typed_shallowly(
    statement: str, analysis: str, result: str, body: str
) -> None:
    item = _item(statement)
    assert isinstance(item, MeasureDirective)
    assert (item.analysis, item.result, item.body_text) == (analysis, result, body)
    assert _slice(statement, item.analysis_span) == analysis
    assert _slice(statement, item.result_span) == result
    assert _slice(statement, item.body_span) == body


@pytest.mark.parametrize(
    ("statement", "column"),
    [
        (".meas foo x MAX v(1)", 7),
        (".meas tran", 11),
        (".meas tran x", 13),
        (".meas", 6),
    ],
)
def test_malformed_measure_directives_are_rejected(statement: str, column: int) -> None:
    error = _reject(statement)
    assert (error.line, error.column) == (2, column)


# Shared behaviour.


@pytest.mark.parametrize(
    "statement",
    [".opt gmin=1e-12", ".print tran v(1)", ".probe v(1)", ".func f(x) {x}", ".options_x a"],
)
def test_other_dot_commands_stay_unknown_directives(statement: str) -> None:
    item = _item(statement)
    assert isinstance(item, UnknownDirective)
    assert item.raw == statement


@pytest.mark.parametrize(
    ("statement", "comments"),
    [
        (".tran 1n 1u ; one", ["; one"]),
        (".tran 1n ; one\n+ 1u $ two", ["; one", "$ two"]),
        (".tran 1n \\\\\n1u // two", ["// two"]),
        (".options a=1 ; one\n+ b=2", ["; one"]),
        (".save v(1) ; one\n+ v(2)", ["; one"]),
        (".param a=1 ; one\n+ b=2 // two", ["; one", "// two"]),
        (".model m D (is=1 ; one\n+ n=1) $ two", ["; one", "$ two"]),
        (".ic v(1)=1 ; one", ["; one"]),
    ],
)
def test_continuations_and_comments_on_directives(statement: str, comments: list[str]) -> None:
    item = _item(statement)
    assert [_slice(statement, span) for span in item.trailing_comments] == comments


@pytest.mark.parametrize(
    "text",
    [
        "title\r\n.param a=1\r\n.tran 1n 1u\r\n.end\r\n",
        "title\n.param a=1\r\n+ b=2\n.subckt d x y\r\nR1 x y 1\n.ends\r\n.end",
    ],
)
def test_line_ending_variants_tile(text: str) -> None:
    _assert_tiling(text, _parse(text).items)


def test_keywords_are_case_insensitive_and_keep_their_spelling() -> None:
    text = "title\n.PaRaM a=1\n.Tran 1n 1u\n.END\n"
    result = _parse(text)
    assert [type(i) for i in result.items[1:3]] == [ParamStatement, TranDirective]
    assert result.items[2].keyword == ".Tran"  # type: ignore[union-attr]
    assert isinstance(result.items[3], End)


def test_statement_parser_is_strict_lalr() -> None:
    parser = build_parser(Dialect.NGSPICE)
    names = {terminal.name for terminal in parser.terminals}
    assert {"PARAM_KW", "MODEL_KW", "SUBCKT_KW", "ENDS_KW", "LPAR", "OUTPUT_VECTOR"} <= names
    assert parser.options.strict is True
