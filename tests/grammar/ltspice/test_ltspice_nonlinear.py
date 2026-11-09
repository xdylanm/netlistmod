"""POLY, ``table=`` and ``Laplace=`` on E, F, G and H, and B's ``laplace=`` (M15b, decision 0017;
LT-PLY-001, LT-TBL-001, LT-LAP-001).

The probes behind each case are in ``tests/solver/test_ltspice_nonlinear_probes.py``.
"""

from __future__ import annotations

import pytest

from netlistmod import (
    BehavioralSource,
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


def _element(line: str) -> ControlledSource | BehavioralSource:
    item = parse(SourceText(f"title\n{line}\n.end\n"), Dialect.LTSPICE).items[1]
    assert isinstance(item, ControlledSource | BehavioralSource)
    return item


def _reject(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"title\n{line}\n.end\n"), Dialect.LTSPICE)
    return captured.value


@pytest.mark.parametrize(
    "line",
    [
        "E1 OUT N002 VX 0 table=(0, 0, 2, 4.4)",
        "E1 OUT N002 VX 0 TABLE=(0 0 2 4.4)",
        "E1 OUT N002 VX 0 table(0,0,2,4.4)",
        "E1 OUT N002 VX 0 table = (0, 0, 2, {k})",
        "G1 OUT N002 VX 0 table=(0,0,2,4.4)",
        "E1 OUT N002 VX 0 table=(0, 0,\n+ 2, 4.4)",
    ],
)
def test_table_is_one_flat_list_after_the_control_nodes(line: str) -> None:
    item = _element(line)
    assert isinstance(item, Vcvs | Vccs)
    assert (item.form, item.value, item.expression, item.dimension) == ("table", None, None, None)
    assert [node.name for node in item.control_nodes] == ["VX", "0"]
    assert item.table is not None
    assert (item.table.layout, item.table.format, len(item.table.points)) == ("flat", (), 2)
    assert [len(point.values) for point in item.table.points] == [2, 2]


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("E1 OUT N002 VX 0 table=(0,0) (2,4)", 30),
        ("E1 OUT N002 VX 0 table=((0,0),(2,4))", 25),
        ("E1 OUT N002 VX 0 table=(0,0,2)", 29),
        ("E1 OUT N002 VX 0 table=(0,3)", 24),
        ("E1 OUT N002 table=(0,0,2,4)", 18),
        ("E1 OUT N002 VX 0 table=(0,0,2,4) m=2", 34),
        ("E1 OUT N002 VX 0 TABLE {V(VX)} = (0,0) (2,4.4)", 18),
    ],
)
def test_malformed_tables_are_refused(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)


@pytest.mark.parametrize(
    ("line", "kind", "formula", "params"),
    [
        ("E1 OUT N002 VX 0 Laplace=2/(1+s/1k)", Vcvs, "2/(1+s/1k)", []),
        ("E1 OUT N002 VX 0 Laplace = 2 / (1 + s/1k)", Vcvs, "2 / (1 + s/1k)", []),
        ("E1 OUT N002 VX 0 Laplace={2/(1+s/1k)}", Vcvs, "2/(1+s/1k)", []),
        (
            "G1 OUT 0 VX 0 Laplace=2m/(1+s/1k) window=1m nfft=1024 mtol=1",
            Vccs,
            "2m/(1+s/1k)",
            [("window", "1m"), ("nfft", "1024"), ("mtol", "1")],
        ),
        (
            "E1 OUT N002 VX 0 Laplace=2/(1+s/1k) window=1m\n+ nfft=1024",
            Vcvs,
            "2/(1+s/1k)",
            [("window", "1m"), ("nfft", "1024")],
        ),
    ],
)
def test_laplace_is_a_formula_then_its_parameters(
    line: str, kind: type, formula: str, params: list[tuple[str, str]]
) -> None:
    item = _element(line)
    assert type(item) is kind
    assert isinstance(item, ControlledSource)
    assert (item.form, item.value, item.table) == ("laplace", None, None)
    assert item.expression is not None and item.expression.text == formula
    assert [(param.name, param.value.text) for param in item.params] == params


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("E1 OUT N002 VX 0 window=1m Laplace=2/(1+s/1k)", 18),
        ("E1 OUT N002 VX 0 Laplace=2/(1+s/1k) foo=1", 37),
        ("E1 OUT N002 VX 0 Laplace=V(vx)/(1+s/1k)", 26),
        ("E1 OUT N002 VX 0 Laplace={I(V1)/(1+s/1k)}", 27),
        ("E1 OUT N002 Laplace=2/(1+s/1k)", 20),
    ],
)
def test_malformed_laplace_lines_are_refused(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)


def test_a_voltage_reference_in_laplace_is_named() -> None:
    assert (
        "Voltage reference not allowed here"
        in _reject("E1 OUT N002 VX 0 Laplace=V(vx)/(1+s/1k)").reason
    )


@pytest.mark.parametrize(
    ("line", "kind", "nodes", "control", "coefficients"),
    [
        ("E1 OUT N002 POLY(1) VX 0 0 2.2", Vcvs, ["OUT", "N002", "VX", "0"], [], ["0", "2.2"]),
        ("E1 OUT N002 POLY(1) (VX,0) 0 2.2", Vcvs, ["OUT", "N002", "VX", "0"], [], ["0", "2.2"]),
        ("E1 OUT N002 POLY(1) (VX 0) 0 2.2", Vcvs, ["OUT", "N002", "VX", "0"], [], ["0", "2.2"]),
        (
            "E1 OUT N002 POLY(2) (VX,0) VX 0 0 1 1",
            Vcvs,
            ["OUT", "N002", "VX", "0", "VX", "0"],
            [],
            ["0", "1", "1"],
        ),
        (
            "E1 OUT N002 POLY(2) (VX,0)(VX,0) 0 1 1",
            Vcvs,
            ["OUT", "N002", "VX", "0", "VX", "0"],
            [],
            ["0", "1", "1"],
        ),
        ("E1 OUT N002 POLY (1) VX 0 0 2.2", Vcvs, ["OUT", "N002", "VX", "0"], [], ["0", "2.2"]),
        ("E1 OUT N002 POLY(1) VX,0 0,2", Vcvs, ["OUT", "N002", "VX", "0"], [], ["0", "2"]),
        ("E1 OUT N002 POLY(1) VX 0 0 6K34", Vcvs, ["OUT", "N002", "VX", "0"], [], ["0", "6K34"]),
        ("E1 OUT N002 POLY(1) VX 0 3", Vcvs, ["OUT", "N002", "VX", "0"], [], ["3"]),
        ("G1 0 OUT POLY(1) VX 0 0 2m", Vccs, ["0", "OUT", "VX", "0"], [], ["0", "2m"]),
        ("F1 OUT 0 POLY(2) V1 V2 0 1 1", Cccs, ["OUT", "0"], ["V1", "V2"], ["0", "1", "1"]),
        ("F1 OUT 0 POLY(1) Vsense 2", Cccs, ["OUT", "0"], ["Vsense"], ["2"]),
        ("H1 OUT 0 POLY(1) Vsense 0 2k", Ccvs, ["OUT", "0"], ["Vsense"], ["0", "2k"]),
    ],
)
def test_poly_counts_its_control_fields_from_the_dimension(
    line: str,
    kind: type,
    nodes: list[str],
    control: list[str],
    coefficients: list[str],
) -> None:
    item = _element(line)
    assert type(item) is kind
    assert isinstance(item, ControlledSource)
    assert (item.form, item.value, item.expression, item.table) == ("poly", None, None, None)
    assert item.dimension == (2 if "POLY(2)" in line else 1)
    assert [node.name for node in item.nodes] == nodes
    assert [source.designator for source in getattr(item, "control", ())] == control
    assert [value.text for value in item.coefficients] == coefficients


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("E1 OUT N002 POLY({1}) VX 0 0 2.2", 18, "is not a dimension"),
        ("E1 OUT N002 POLY(0) VX 0 0 2.2", 18, "is not a dimension"),
        ("E1 OUT N002 POLY(1) VX 0 0 k", 28, "is a name where a coefficient goes"),
        ("E1 OUT N002 POLY(1) VX 0", 25, "at least 1 coefficient"),
        ("E1 OUT N002 POLY(2) VX 0 0 1", 29, "at least 1 coefficient"),
        ("F1 OUT 0 POLY(1) (Vsense) 0 2", 18, ""),
        ("F1 OUT 0 POLY(1) Vsense 0 2 m=2", 30, ""),
        ("E1 OUT N002 POLY(1) VX 0 0 2.2 m=2", 33, ""),
    ],
)
def test_malformed_poly_lines_are_refused(line: str, column: int, reason: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


def test_a_pair_may_not_stand_among_the_coefficients() -> None:
    error = _reject("E1 OUT N002 POLY(1) VX 0 (0,1)")
    assert "is a control pair" in error.reason


@pytest.mark.parametrize(
    ("line", "formula", "params"),
    [
        (
            "B1 OUT 0 V=K*V(VX) laplace=1/(1+s/1k) window=1m nfft=1024",
            "1/(1+s/1k)",
            ["laplace", "window", "nfft"],
        ),
        ("B1 OUT 0 V=K*V(VX) laplace={1/(1+s/1k)} mtol=1", "1/(1+s/1k)", ["laplace", "mtol"]),
        ("B1 OUT 0 I=K*V(VX) laplace=1/(1+s/1k)", "1/(1+s/1k)", ["laplace"]),
        ("B1 OUT 0 V=K*V(VX) ic=1 laplace=1/(1+s/1k)", "1/(1+s/1k)", ["ic", "laplace"]),
    ],
)
def test_b_takes_laplace_as_a_trailing_parameter(
    line: str, formula: str, params: list[str]
) -> None:
    item = _element(line)
    assert isinstance(item, BehavioralSource)
    assert item.expression.text == "K*V(VX)"
    assert [param.name for param in item.params] == params
    laplace = next(param for param in item.params if param.name == "laplace")
    assert getattr(laplace.value, "text", None) == formula


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("B1 OUT 0 R=1k laplace=1/(1+s/1k)", 15),
        ("B1 OUT 0 P=1m laplace=1/(1+s/1k)", 15),
        ("B1 OUT 0 V=K*V(VX) window=1m", 20),
    ],
)
def test_b_laplace_is_refused_where_the_reference_does_not_show_it(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
