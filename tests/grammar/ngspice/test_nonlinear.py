"""TABLE, POLY, FREQ and the gates on E, F, G and H (M15b, decision 0017; NG-TBL-001, NG-PLY-001,
NG-XSP-001).

The probes behind each case are in ``tests/solver/test_ngspice_nonlinear_probes.py``.
"""

from __future__ import annotations

import pytest

from netlistmod import (
    Cccs,
    Ccvs,
    ControlledSource,
    Dialect,
    ParseError,
    SourceText,
    Vccs,
    Vcvs,
    parse,
)


def _element(line: str) -> ControlledSource:
    item = parse(SourceText(f"title\n{line}\n.end\n"), Dialect.NGSPICE).items[1]
    assert isinstance(item, ControlledSource)
    return item


def _reject(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"title\n{line}\n.end\n"), Dialect.NGSPICE)
    return captured.value


def _values(item: ControlledSource) -> list[list[str]]:
    assert item.table is not None
    return [[value.text for value in point.values] for point in item.table.points]


@pytest.mark.parametrize(
    ("line", "layout", "points"),
    [
        ("E1 out 0 TABLE {v(vx)} = (0,0) (2,4)", "pairs", [["0", "0"], ["2", "4"]]),
        ("E1 out 0 TABLE {v(vx)} (0 0) (2 4)", "pairs", [["0", "0"], ["2", "4"]]),
        ("E1 out 0 TABLE {v(vx)}=(0,0)(2,4)", "pairs", [["0", "0"], ["2", "4"]]),
        ("E1 out 0 TABLE 'v(vx)' = (0,0) (2,4)", "pairs", [["0", "0"], ["2", "4"]]),
        ("E1 out 0 table {v(vx)} = (0,0,2,4)", "flat", [["0", "0"], ["2", "4"]]),
        ("E1 out 0 TABLE {v(vx)} = (0,3)", "pairs", [["0", "3"]]),
        ("E1 out 0 TABLE {v(vx)} = (0,0)\n+ (2,-5mV)", "pairs", [["0", "0"], ["2", "-5mV"]]),
        ("G1 0 out TABLE {v(vx)} = (0,0) (2,4) m=2", "pairs", [["0", "0"], ["2", "4"]]),
    ],
)
def test_the_expression_form_of_table(line: str, layout: str, points: list[list[str]]) -> None:
    item = _element(line)
    assert isinstance(item, Vcvs | Vccs)
    assert (item.form, item.value, item.dimension, item.coefficients) == ("table", None, None, ())
    assert item.expression is not None and item.expression.text == "v(vx)"
    assert item.table is not None and item.table.layout == layout
    assert _values(item) == points
    assert len(item.nodes) == 2
    assert [param.name for param in item.params] == (["m"] if "m=" in line else [])


@pytest.mark.parametrize(
    ("line", "layout"),
    [
        ("E1 out 0 vx 0 TABLE = (0,0,2,4)", "flat"),
        ("E1 out 0 vx 0 TABLE (0,0) (2,4)", "pairs"),
        ("E1 out 0 vx 0 table = (0 0) (2 4)", "pairs"),
    ],
)
def test_the_four_node_table_reads_its_control_nodes(line: str, layout: str) -> None:
    item = _element(line)
    assert isinstance(item, Vcvs)
    assert (item.form, item.expression, item.value) == ("table", None, None)
    assert [node.name for node in item.control_nodes] == ["vx", "0"]
    assert item.table is not None and item.table.layout == layout
    assert _values(item) == [["0", "0"], ["2", "4"]]


def test_the_table_remembers_its_spans() -> None:
    line = "E1 out 0 TABLE {v(vx)} = (0, 0) (2, 4)"
    item = _element(line)
    assert item.table is not None
    text = f"title\n{line}\n.end\n"
    assert text[item.table.span.start : item.table.span.end] == "(0, 0) (2, 4)"
    point = item.table.points[1]
    assert text[point.span.start : point.span.end] == "2, 4"


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("E1 out 0 TABLE {v(vx)} = (0,0) (2,{2*k})", 35),
        ("E1 out 0 TABLE {v(vx)} = (0,0) (2,k)", 35),
        ("E1 out 0 TABLE {v(vx)} = (0,0) (2)", 33),
        ("E1 out 0 TABLE {v(vx)} = (0,0,0) (2,4,0)", 27),
        ("E1 out 0 TABLE {v(vx)} = (0,0,2)", 31),
        ("E1 out 0 vx 0 TABLE = (0,0,2)", 28),
        ("E1 out 0 TABLE {v(vx)} = (0,0) (2,4) m=2", 38),
        ("G1 0 out vx 0 TABLE = (0,0,2,4)", 15),
    ],
)
def test_malformed_tables_are_refused(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)


def test_a_parameter_in_a_table_point_is_refused() -> None:
    reason = _reject("E1 out 0 TABLE {v(vx)} = (0,0) (2,{2*k})").reason
    assert "numbers only" in reason


def test_a_bare_table_expression_is_refused() -> None:
    error = _reject("E1 out 0 TABLE v(vx) = (0,0) (2,4)")
    assert (error.line, error.column) == (2, 10)
    assert "only with its expression in braces or quotes" in error.reason


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("E1 out 0 table 0 2", 10),
        ("E1 table 0 vx 0 2", 4),
        ("E1 out 0 vx table 2", 13),
        ("G1 0 table vx 0 1m", 6),
        ("E1 out 0 Table 0 2", 10),
    ],
)
def test_a_net_named_table_on_e_or_g_is_refused(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert "as the keyword of the TABLE form, in any node position" in error.reason


@pytest.mark.parametrize("line", ["E1 out 0 poly 0 2", "E1 out 0 freq vx 2", "E1 out 0 and 0 2"])
def test_other_keyword_names_stay_nets(line: str) -> None:
    item = _element(line)
    assert item.value is not None and len(item.nodes) == 4


@pytest.mark.parametrize(
    ("line", "kind", "dimension", "nodes", "control", "coefficients"),
    [
        ("E1 out 0 POLY(1) vx 0 0 2", Vcvs, 1, ["out", "0", "vx", "0"], [], ["0", "2"]),
        ("E1 out 0 POLY (1) vx 0 0 2", Vcvs, 1, ["out", "0", "vx", "0"], [], ["0", "2"]),
        ("E1 out 0 POLY(1) vx,0 0,2", Vcvs, 1, ["out", "0", "vx", "0"], [], ["0", "2"]),
        ("E1 out 0 POLY(1) vx 0 0 {k}", Vcvs, 1, ["out", "0", "vx", "0"], [], ["0", "k"]),
        (
            "E1 out 0 POLY(2) vx 0 vx 0 0 1 1",
            Vcvs,
            2,
            ["out", "0", "vx", "0", "vx", "0"],
            [],
            ["0", "1", "1"],
        ),
        ("E1 out 0 POLY(1) vx 0 0 2\n+ 3", Vcvs, 1, ["out", "0", "vx", "0"], [], ["0", "2", "3"]),
        ("G1 0 out POLY(1) vx 0 0 2m", Vccs, 1, ["0", "out", "vx", "0"], [], ["0", "2m"]),
        ("F1 0 out POLY(1) Vsense 0 2", Cccs, 1, ["0", "out"], ["Vsense"], ["0", "2"]),
        (
            "F1 0 out POLY(2) Vs Vt 0 1 1",
            Cccs,
            2,
            ["0", "out"],
            ["Vs", "Vt"],
            ["0", "1", "1"],
        ),
        ("H1 out 0 POLY(1) Vsense 0 2k", Ccvs, 1, ["out", "0"], ["Vsense"], ["0", "2k"]),
    ],
)
def test_poly_counts_its_control_fields_from_the_dimension(
    line: str,
    kind: type,
    dimension: int,
    nodes: list[str],
    control: list[str],
    coefficients: list[str],
) -> None:
    item = _element(line)
    assert type(item) is kind
    assert (item.form, item.value, item.expression, item.table) == ("poly", None, None, None)
    assert item.dimension == dimension
    assert [node.name for node in item.nodes] == nodes
    assert [source.designator for source in getattr(item, "control", ())] == control
    assert [value.text for value in item.coefficients] == coefficients


@pytest.mark.parametrize(
    ("line", "param"),
    [
        ("G1 0 out POLY(1) vx 0 0 2m m=2", "m"),
        ("F1 0 out POLY(2) Vs Vt 0 1 1 m=2", "m"),
    ],
)
def test_poly_takes_m_on_f_and_g(line: str, param: str) -> None:
    item = _element(line)
    assert [(p.name, p.value.text) for p in item.params] == [(param, "2")]


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("E1 out 0 POLY(1) vx 0 0 k", 25, "is a name where a coefficient goes"),
        # M18 A1-4: ngspice 47 runs 2μ as 2 (it ignores the letter); refused, as on R.
        ("E1 out 0 POLY(1) vx 0 0 2μ", 25, "is a name where a coefficient goes"),
        ("E1 out 0 POLY({1}) vx 0 0 2", 15, "is not a dimension"),
        ("E1 out 0 POLY(0) vx 0 0 2", 15, "is not a dimension"),
        ("E1 out 0 POLY(k) vx 0 0 2", 15, "is not a dimension"),
        ("E1 out 0 POLY(1) vx 0", 22, "at least 2 coefficients"),
        ("E1 out 0 POLY(1) vx 0 3", 24, "at least 2 coefficients"),
        ("E1 out 0 POLY(2) vx 0 0 1", 26, "at least 2 coefficients"),
        ("F1 0 out POLY(1) Vsense 2", 26, "at least 2 coefficients"),
        ("E1 out 0 POLY(1) vx", 20, "takes 2 control nodes"),
        ("F1 0 out POLY(2) Vsense", 24, "takes 2 controlling sources"),
        ("E1 out 0 POLY(1) (vx,0) 0 2", 18, ""),
        ("E1 out 0 POLY(1) vx 0 0 2 m=2", 28, ""),
        ("H1 out 0 POLY(1) Vsense 0 2k m=2", 31, ""),
    ],
)
def test_malformed_poly_lines_are_refused(line: str, column: int, reason: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


def test_poly_names_must_not_be_formulas() -> None:
    error = _reject("E1 out 0 POLY(1) {vx} 0 0 2")
    assert (error.line, error.column) == (2, 18)
    assert "is a formula, but a POLY control node is a name" in error.reason


@pytest.mark.parametrize(
    ("line", "formats", "points"),
    [
        (
            "E1 out 0 FREQ {v(vx)}= DB (1, 6.02, 0) (1e9, 6.02, 0)",
            ("DB",),
            [["1", "6.02", "0"], ["1e9", "6.02", "0"]],
        ),
        (
            "E1 out 0 FREQ {v(vx)} DB (1 6.02 0) (1e9 6.02 0)",
            ("DB",),
            [["1", "6.02", "0"], ["1e9", "6.02", "0"]],
        ),
        ("E1 out 0 FREQ {v(vx)} = MAG DEG (1, 1, 0)", ("MAG", "DEG"), [["1", "1", "0"]]),
        (
            "E1 out 0 FREQ 'v(vx)' = r_i (1, 1, 0, 1e9, 1, 0)",
            ("r_i",),
            [["1", "1", "0"], ["1e9", "1", "0"]],
        ),
        (
            "G1 0 out FREQ {v(vx)}= DB (1, {k}, 0) (1k, 1, 0)",
            ("DB",),
            [["1", "k", "0"], ["1k", "1", "0"]],
        ),
    ],
)
def test_freq_reads_its_format_words_and_triples(
    line: str, formats: tuple[str, ...], points: list[list[str]]
) -> None:
    item = _element(line)
    assert item.form == "freq" and item.expression is not None
    assert item.expression.text == "v(vx)"
    assert item.table is not None and item.table.format == formats
    assert _values(item) == points


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("E1 out 0 FREQ {v(vx)} = (1, 2, 0) (1e9, 2, 0)", 25),
        ("E1 out 0 FREQ {v(vx)} = DB (1, 2) (1e9, 2)", 29),
        ("E1 out 0 FREQ {v(vx)} = DB (1e7, 6.02, 0) (1e9, 6.02, 0)", 29),
        ("E1 out 0 FREQ {v(vx)} = DB (1.0e+07Hz, 6.02, 0) (1.0e+09Hz, 6.02, 0)", 29),
        ("E1 out 0 FREQ {v(vx)} = DB (10, 6.02, 0, 1e9, 6.02, 0)", 29),
        ("E1 out 0 FREQ {v(vx)} = DB ({1e7}, 6.02, 0) (1e9, 6.02, 0)", 29),
        ("E1 out 0 FREQ {v(vx)} = DB ({k}, 6.02, 0) (1e9, 6.02, 0)", 29),
        ("E1 out 0 FREQ {v(vx)} = DB MAG (1, 6.02, 0) (1e9, 6.02, 0)", 28),
        ("E1 out 0 FREQ {v(vx)} = MAG DB (1, 6.02, 0) (1e9, 6.02, 0)", 29),
        ("E1 out 0 FREQ {v(vx)} = DEG RAD (1, 6.02, 0) (1e9, 6.02, 0)", 29),
        ("E1 out 0 FREQ {v(vx)} = R_I DB (1, 6.02, 0) (1e9, 6.02, 0)", 29),
        ("E1 out 0 FREQ {v(vx)} = DB R_I (1, 6.02, 0) (1e9, 6.02, 0)", 28),
        ("E1 out 0 FREQ {v(vx)} = DB (1, 6.02, 0, 1e9, 6.02)", 46),
        ("G1 0 out FREQ {v(vx)} = DB (1, 6.02, 0) (1e9, 6.02, 0) m=2", 56),
    ],
)
def test_malformed_freq_lines_are_refused(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)


@pytest.mark.parametrize(
    ("line", "first", "words"),
    [
        # A blank after the "(" runs in ngspice, with or without a unit suffix (review R4).
        ("E1 out 0 FREQ {v(vx)} = DB ( 1e7, 6.02, 0) (1e9, 6.02, 0)", "1e7", ("DB",)),
        ("E1 out 0 FREQ {v(vx)} = DB ( 1e7Hz, 6.02, 0) (1e9Hz, 6.02, 0)", "1e7Hz", ("DB",)),
        ("E1 out 0 FREQ {v(vx)} = DB ( 1.5, 6.02, 0, 1e9, 6.02, 0)", "1.5", ("DB",)),
        ("E1 out 0 FREQ {v(vx)} = DB ( {k}, 6.02, 0) (1e9, 6.02, 0)", "k", ("DB",)),
        ("E1 out 0 FREQ {v(vx)} = DB (1, 6.02, 0) (1e7Hz, 6.02, 0)", "1", ("DB",)),
        ("E1 out 0 FREQ {v(vx)} = DB (0, 6.02, 0)", "0", ("DB",)),
        ("E1 out 0 FREQ {v(vx)} = DB DB (1, 6.02, 0)", "1", ("DB", "DB")),
        ("E1 out 0 FREQ {v(vx)} = MAG DEG (1, 6.02, 0)", "1", ("MAG", "DEG")),
        ("E1 out 0 FREQ {v(vx)} = DB RAD (1, 6.02, 0)", "1", ("DB", "RAD")),
    ],
)
def test_freq_first_frequency_and_format_words_that_run(
    line: str, first: str, words: tuple[str, ...]
) -> None:
    item = _element(line)
    assert item.table is not None
    assert item.table.points[0].values[0].text == first
    assert item.table.format == words


def test_the_freq_stop_names_the_fix() -> None:
    error = _reject("E1 out 0 FREQ {v(vx)} = DB (1e7, 6.02, 0) (1e9, 6.02, 0)")
    assert "write a blank after it, `( 1e7, ...)`" in error.reason
    braced = _reject("E1 out 0 FREQ {v(vx)} = DB ({k}, 6.02, 0) (1e9, 6.02, 0)")
    assert "`( {k}, ...)`" in braced.reason
    assert "keeps the last" in _reject("E1 out 0 FREQ {v(vx)} = DB MAG (1, 6.02, 0)").reason


@pytest.mark.parametrize("word", ["and", "AND", "or", "nand", "NOR"])
def test_gates_read_two_points_and_their_inputs(word: str) -> None:
    item = _element(f"E1 out 0 {word}(2) vx 0 vx 0 (0.5, 0) (0.9, {{k}})")
    assert isinstance(item, Vcvs)
    assert (item.form, item.dimension, item.expression, item.value) == (
        word.lower(),
        2,
        None,
        None,
    )
    assert [node.name for node in item.control_nodes] == ["vx", "0", "vx", "0"]
    assert _values(item) == [["0.5", "0"], ["0.9", "k"]]


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("E1 out 0 and(1) vx 0 vx 0 (0.5, 0) (0.9, 2)", 14),
        ("E1 out 0 and(3) vx 0 vx 0 (0.5, 0) (0.9, 2)", 14),
        ("E1 out 0 and(2) vx 0 (0.5, 0) (0.9, 2)", 22),
        ("E1 out 0 and(1) vx 0 (0.5, 0) (0.9, 2)", 22),
        ("E1 out 0 and(2) vx 0 vx (0.5, 0) (0.9, 2)", 25),
        ("E1 out 0 and(2) vx 0 vx 0 (0.5, 0) (0.9, 2) (1, 3)", 27),
        ("E1 out 0 and (2) vx 0 vx 0 (0.5, 0) (0.9, 2)", 14),
        ("E1 out 0 and(2) vx 0 vx 0 (0.5 0) (0.9 2)", 28),
        ("E1 out 0 and(2) vx 0 vx 0 (0.5,0)(0.9,2)", 34),
        ("E1 out 0 and(2) (vx,0) (vx,0) (0.5, 0) (0.9, 2)", 17),
        ("G1 0 out and(2) vx 0 vx 0 (0.5, 0) (0.9, 2)", 13),
    ],
)
def test_malformed_gates_are_refused(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)


def test_the_gate_count_message_names_the_inputs() -> None:
    reason = _reject("E1 out 0 and(1) vx 0 vx 0 (0.5, 0) (0.9, 2)").reason
    assert "ngspice ignores the dimension and counts the inputs" in reason


# Forms of decision 0017 that the grammar refuses with no rule of their own: each has its own
# message, at the same position, instead of the expected tokens (M15b 6.3, carried to M18 C1).
@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("E1 out 0 POLY(1) (vx,0) 0 2", 18, "a POLY control pair in parentheses"),
        ("E1 out 0 POLY(1) (vx 0) 0 2", 18, "a POLY control pair in parentheses"),
        ("E1 out 0 POLY(2) vx 0 (vy,0) 0 1 1", 23, "a POLY control pair in parentheses"),
        ("G1 0 out POLY(1) (vx,0) 0 2m", 18, "a POLY control pair in parentheses"),
        ("E1 out 0 POLY(1)\n+ (vx,0) 0 2", 3, "a POLY control pair in parentheses"),
        ("G1 0 out vx 0 TABLE = (0,0,2,4)", 15, "the four-node TABLE is E's only"),
        ("G1 0 out vx 0 table (0,0) (2,4)", 15, "the four-node TABLE is E's only"),
        ("G1 0 out and(2) vx 0 vx 0 (0.5, 0) (0.9, 2)", 13, "`and(...)` on G: the gates"),
        ("G1 0 out NOR(2) vx 0 vx 0 (0.5, 0) (0.9, 2)", 13, "`NOR(...)` on G: the gates"),
        ("G1 0 out and (2) vx 0 vx 0 (0.5, 0) (0.9, 2)", 14, "`and(...)` on G: the gates"),
        ("E1 out 0 and (2) vx 0 vx 0 (0.5, 0) (0.9, 2)", 14, "`and (`: ngspice stops on a blank"),
        ("E1 out 0 Nand (2) vx 0 vx 0 (0.5, 0) (0.9, 2)", 15, "write `Nand(N)`"),
    ],
)
def test_refused_nonlinear_forms_have_their_own_message(
    line: str, column: int, reason: str
) -> None:
    error = _reject(line)
    assert (error.column, error.expected) == (column, ())
    assert reason in error.reason


@pytest.mark.parametrize(
    "line",
    [
        "E1 out 0 POLY(1) vx 0 (1,2)",  # past the control nodes: not a control pair
        "F1 0 out POLY(1) (Vs) 0 2",
        "E1 out 0 and(2) (vx,0) (vx,0) (0.5, 0) (0.9, 2)",
        "G1 0 out 0 and (2)",
    ],
)
def test_other_malformed_lines_keep_the_expected_tokens(line: str) -> None:
    error = _reject(line)
    assert error.reason == ""
    assert error.expected


@pytest.mark.parametrize(
    ("line", "written"),
    [
        ("E1 out 0 TABLE {v(vx)} = (0,0) (2,{2*k})", "{2*k}"),
        ("E1 out 0 TABLE {v(vx)} = (0,0) ({4},2)", "{4}"),
        ("E1 out 0 TABLE {v(vx)} = (0,0) (2,'4')", "'4'"),
        ("E1 out 0 vx 0 TABLE = (0,0,2,{4})", "{4}"),
    ],
)
def test_a_formula_in_a_table_point_is_quoted_as_written(line: str, written: str) -> None:
    # M15b 6.3, carried to M18 C3: the braces or quotes stay in the quote.
    assert _reject(line).reason.startswith(f"`{written}` in a TABLE point")
