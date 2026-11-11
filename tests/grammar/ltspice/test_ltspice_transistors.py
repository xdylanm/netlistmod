"""LTspice transistor lines, Q, M, J and Z, and the .model forms they need (M13, decision 0014)."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    BipolarTransistor,
    Dialect,
    Identifier,
    Jfet,
    Mesfet,
    ModelStatement,
    Mosfet,
    NumericValue,
    ParseError,
    SourceText,
    Span,
    ValueList,
    parse,
)


def _element(line: str) -> Any:
    text = f"title\n{line}\n.end\n"
    result = parse(SourceText(text), Dialect.LTSPICE)
    assert len(result.items) == 3, result.items
    item = result.items[1]
    assert item.span == Span(6, 6 + len(line) + 1)
    return item


def _reject(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"title\n{line}\n.end\n"), Dialect.LTSPICE)
    return captured.value


def _slice(line: str, span: Span) -> str:
    return f"title\n{line}"[span.start : span.end]


@pytest.mark.parametrize(
    ("line", "nodes", "model", "area"),
    [
        ("Q1 c b e qm", ["c", "b", "e"], "qm", None),
        ("Q1 c b e s qm", ["c", "b", "e", "s"], "qm", None),
        ("Q1 c b e 0 2N3904", ["c", "b", "e", "0"], "2N3904", None),
        ("Q1 c b e 2 qm", ["c", "b", "e", "2"], "qm", None),
        ("Q1 c b e off qm", ["c", "b", "e", "off"], "qm", None),
        ("Q1 c b e qm s", ["c", "b", "e", "qm"], "s", None),
        ("Q1 c b e qm 2", ["c", "b", "e"], "qm", "2"),
        ("Q1 c b e s qm 2", ["c", "b", "e", "s"], "qm", "2"),
        ("Q1 c b e 2N3904", ["c", "b", "e"], "2N3904", None),
        ("Q1 c b e s 2N3904", ["c", "b", "e", "s"], "2N3904", None),
        ("Q1 c b e 2N3904 2", ["c", "b", "e"], "2N3904", "2"),
        ("Q1 c b e s qm 1n5", ["c", "b", "e", "s"], "qm", "1n5"),
        # Review R1: LTspice reads qm as the model and 1n5 as the area; see discrepancies.md.
        ("Q1 c b e qm 1n5", ["c", "b", "e", "qm"], "1n5", None),
        ("M1 d g s b nm", ["d", "g", "s", "b"], "nm", None),
        ("M1 d g s vd", ["d", "g", "s"], "vd", None),
        ("MQ8 d g OUT OUT 2N7000_OJ", ["d", "g", "OUT", "OUT"], "2N7000_OJ", None),
        ("J1 d g s jm", ["d", "g", "s"], "jm", None),
        ("J1 d g s jm 1n5", ["d", "g", "s"], "jm", "1n5"),
        ("Z1 d g s zm 2", ["d", "g", "s"], "zm", "2"),
        # M18 A1-4: a number with any letter after it is an area, as LTspice's NUMBER reads it
        # (U+03BC is the Greek mu, U+00B5 the micro sign).
        ("Q1 c b 0 qm 1μ", ["c", "b", "0"], "qm", "1μ"),
        ("Q1 c b 0 qm 2Ω", ["c", "b", "0"], "qm", "2Ω"),
        ("Q1 c b 0 qm 1µ", ["c", "b", "0"], "qm", "1µ"),
        ("Q1 c b 0 s qm 1μ off", ["c", "b", "0", "s"], "qm", "1μ"),
        ("J1 d g 0 jm 2μ", ["d", "g", "0"], "jm", "2μ"),
        ("J1 d g 0 jm 2Ω off", ["d", "g", "0"], "jm", "2Ω"),
        ("Z1 d g 0 zm 2μ", ["d", "g", "0"], "zm", "2μ"),
        ("Q1 c b 1μ qm", ["c", "b", "1μ"], "qm", None),
    ],
)
def test_the_model_is_the_last_name(
    line: str, nodes: list[str], model: str, area: str | None
) -> None:
    item = _element(line)
    assert [node.name for node in item.nodes] == nodes
    assert item.model.model_name == model
    assert _slice(line, item.model.span) == model
    assert (item.area and item.area.text) == area
    if item.area is not None:
        assert isinstance(item.area, NumericValue)
        assert _slice(line, item.area.span) == area


@pytest.mark.parametrize(
    ("line", "kind"),
    [("Q1 c b e qm", BipolarTransistor), ("M1 d g s b nm", Mosfet), ("J1 d g s jm", Jfet)]
    + [("Z1 d g s zm", Mesfet)],
)
def test_each_letter_has_its_own_node(line: str, kind: type) -> None:
    assert type(_element(line)) is kind


# Decision 6: each letter's closed parameter list, and off.
@pytest.mark.parametrize(
    ("line", "params"),
    [
        ("Q1 c b e qm 2 temp=30 off", ["temp"]),
        ("M1 d g s b nm L=1u W=2u AD=1p AS=1p PD=1u PS=1u NRD=1 NRS=1 m=2 temp=30", None),
        ("M1 d g s vd L=1u W=2u M=2 IC=1,2,3 off", ["L", "W", "M", "IC"]),
        ("J1 d g s jm 2 temp=30 off", ["temp"]),
        ("Z1 d g s zm 2 m=2 temp=30 off", ["m", "temp"]),
    ],
)
def test_each_letter_takes_its_own_parameters(line: str, params: list[str] | None) -> None:
    item = _element(line)
    names = [param.name for param in item.params]
    if params is None:
        params = [word.split("=")[0] for word in line.split() if "=" in word]
    assert names == params


@pytest.mark.parametrize("line", ["M1 d g s b nm IC=0.6, 5.0", "M1 d g s b nm ic=0.6,5.0 off"])
def test_ic_takes_a_comma_list(line: str) -> None:
    param = _element(line).params[0]
    assert isinstance(param.value, ValueList)
    assert [value.text for value in param.value.values] == ["0.6", "5.0"]


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("Q1 c b", 7),  # too few nodes
        ("Q1 c b e s tj qm", 15),  # five nodes
        ("M1 d g s tj tc vd thermal", 16),  # five nodes, and no thermal flag
        ("J1 d g s b jm", 12),  # four nodes
        ("Q1 c b e 2", 11),  # a number as the model
        ("Q1 c b e 1μ", 12),  # a number with a Greek mu as the model (M18 A1-4)
        ("Q1 c b 0 qm 1μ x", 16),  # a name after the area
        ("Q1 c b e qm 2 x", 15),  # a name after the area
        ("Q1 c b e qm area=2", 17),  # outside the closed lists; area could still be a name
        ("Q1 c b e qm ic=0.6,5", 15),
        ("M1 d g s b nm foo=1", 15),
        ("J1 d g s jm area=2", 13),
        ("J1 d g s jm m=2", 13),
        ("J1 d g s jm ic=1,2", 13),
    ],
)
def test_malformed_transistor_lines_are_rejected(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)


# M18 A1-4: M has no positional area, so a number after the model is in the model's place, as `2`
# is; LTspice stops on both ("Unknown parameter").
@pytest.mark.parametrize(
    ("line", "word"),
    [("M1 d g s mm 2", "2"), ("M1 d g s mm 1μ", "1μ"), ("M1 d g s mm 2Ω", "2Ω")],
)
def test_a_number_after_an_m_model_is_refused_as_the_model(line: str, word: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, 13)
    assert error.reason.startswith(f"`{word}` is in the model's place")
    assert "a model name cannot be a number" in error.reason


def test_a_model_name_cannot_be_a_keyword() -> None:
    error = _reject("Q1 c b e 2 off")
    assert (error.line, error.column) == (2, 12)
    assert "`off` is in the model's place" in error.reason


@pytest.mark.parametrize(
    "line",
    [
        ".model vd VDMOS pchan VTO=-2",
        ".model vd VDMOS(pchan VTO=-2)",
        ".model vd VDMOS(VTO=2, nchan)",
    ]
    + [".model s ako:vd VDMOS pchan"],
)
def test_a_model_may_carry_a_channel_flag(line: str) -> None:
    model = parse(SourceText(f"t\n{line}\n.end\n"), Dialect.LTSPICE).items[1]
    assert isinstance(model, ModelStatement)
    assert [flag.name.lower() for flag in model.flags] in (["pchan"], ["nchan"])


@pytest.mark.parametrize(
    "line",
    [".model b NMOS level=8 version=3.3.0", ".model b NMOS(version=3.3.0, level=8)"],
)
def test_a_dotted_model_value_is_text(line: str) -> None:
    model = parse(SourceText(f"t\n{line}\n.end\n"), Dialect.LTSPICE).items[1]
    version = next(param for param in model.params if param.name == "version")
    assert version.value == Identifier("3.3.0", version.value.span)
