"""ngspice transistor lines, Q, M, J and Z, and the .model forms they need (M13, decision 0014)."""

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
    result = parse(SourceText(text), Dialect.NGSPICE)
    assert len(result.items) == 3, result.items
    item = result.items[1]
    assert item.span == Span(6, 6 + len(line) + 1)
    return item


def _reject(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"title\n{line}\n.end\n"), Dialect.NGSPICE)
    return captured.value


def _reading(item: Any) -> tuple[Any, ...]:
    return (
        type(item),
        [node.name for node in item.nodes],
        item.model.model_name,
        item.area and item.area.text,
        [flag.name for flag in item.flags],
        [param.name for param in item.params],
    )


def _slice(line: str, span: Span) -> str:
    return f"title\n{line}"[span.start : span.end]


# Decisions 1, 2 and 4: the model is the last name before the first flag, parameter or the end.
@pytest.mark.parametrize(
    ("line", "nodes", "model"),
    [
        ("Q1 c b e qm", ["c", "b", "e"], "qm"),
        ("Q1 c b e s qm", ["c", "b", "e", "s"], "qm"),
        ("Q1 c b e s tj qm", ["c", "b", "e", "s", "tj"], "qm"),
        ("Q1 c b e 2 qm", ["c", "b", "e", "2"], "qm"),
        ("Q1 c b e off qm", ["c", "b", "e", "off"], "qm"),
        ("Q1 c b e qm s", ["c", "b", "e", "qm"], "s"),
        ("Q1 c b e 2N3904", ["c", "b", "e"], "2N3904"),
        ("Q1 c b e 2N7000_OJ", ["c", "b", "e"], "2N7000_OJ"),
        ("M1 d g s b nm", ["d", "g", "s", "b"], "nm"),
        ("M1 d g s vd", ["d", "g", "s"], "vd"),
        ("M1 d g s s vd", ["d", "g", "s", "s"], "vd"),
        ("M1 d g s tj tc vd", ["d", "g", "s", "tj", "tc"], "vd"),
        ("J1 d g s jm", ["d", "g", "s"], "jm"),
        ("Z1 d g s zm", ["d", "g", "s"], "zm"),
    ],
)
def test_the_model_is_the_last_name(line: str, nodes: list[str], model: str) -> None:
    item = _element(line)
    assert [node.name for node in item.nodes] == nodes
    assert item.model.model_name == model
    assert _slice(line, item.model.span) == model
    for node in item.nodes:
        assert _slice(line, node.span) == node.name


@pytest.mark.parametrize(
    ("line", "kind"),
    [("Q1 c b e qm", BipolarTransistor), ("M1 d g s b nm", Mosfet), ("J1 d g s jm", Jfet)]
    + [("Z1 d g s zm", Mesfet), ("qout c b e qm", BipolarTransistor)],
)
def test_each_letter_has_its_own_node(line: str, kind: type) -> None:
    item = _element(line)
    assert type(item) is kind
    assert item.designator == line.split()[0]


def test_flags_and_open_parameters_follow_the_model() -> None:
    item = _element("Q1 c b e qm area=2 areab=1 areac=3 temp=30 off")
    assert _reading(item) == (
        BipolarTransistor,
        ["c", "b", "e"],
        "qm",
        None,
        ["off"],
        ["area", "areab", "areac", "temp"],
    )
    line = "M1 d g s b nm l=1u w=2u ad=1p as=1p pd=1u ps=1u nrd=1 nrs=1 m=2 off foo=1"
    assert _reading(_element(line))[4:] == (
        ["off"],
        ["l", "w", "ad", "as", "pd", "ps", "nrd", "nrs", "m", "foo"],
    )


def test_off_after_the_model_is_a_flag() -> None:
    assert _reading(_element("Q1 c b e s qm off"))[1:5] == (
        ["c", "b", "e", "s"],
        "qm",
        None,
        ["off"],
    )


def test_thermal_is_a_vdmos_flag() -> None:
    item = _element("M1 d g s tj tc vd thermal")
    assert [flag.name for flag in item.flags] == ["thermal"]
    assert len(item.nodes) == 5


@pytest.mark.parametrize("line", ["Q1 c b e qm ic=0.6, 5.0", "Q1 c b e qm ic=0.6,5.0 off"])
def test_ic_takes_a_comma_list(line: str) -> None:
    param = _element(line).params[0]
    assert param.name == "ic"
    assert isinstance(param.value, ValueList)
    assert [value.text for value in param.value.values] == ["0.6", "5.0"]


# Decision 5: J and Z take a positional area on ngspice; Q takes area= only.
@pytest.mark.parametrize("line", ["J1 d g s jm 2 off", "Z1 d g s zm 2 off"])
def test_j_and_z_take_a_positional_area(line: str) -> None:
    item = _element(line)
    assert isinstance(item.area, NumericValue)
    assert item.area.text == "2"
    assert _slice(line, item.area.span) == "2"
    assert [flag.name for flag in item.flags] == ["off"]


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("Q1 c b", 7),  # too few nodes
        ("Q1 c b e s tj x qm", 19),  # six nodes
        ("M1 d g s b x y nm", 18),  # six nodes
        ("J1 d g s b jm", 14),  # four nodes
        ("Z1 d g s b zm", 14),
        ("Q1 c b e 2", 11),  # a number as the model
        ("Q1 c b e qm 2", 14),  # a positional area on Q
        ("Q1 c b e 2N3904 2", 18),
        ("J1 d g s jm 2 x", 16),  # a name after the area
    ],
)
def test_malformed_transistor_lines_are_rejected(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)


@pytest.mark.parametrize(
    ("line", "column", "word"),
    [
        ("Q1 c b e s qm 2", 15, "2"),
        ("Q1 c b e qm 2 off", 15, "off"),
        ("M1 d g s 2 thermal", 12, "thermal"),
    ],
)
def test_a_model_name_cannot_be_a_number_or_a_keyword(line: str, column: int, word: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert f"`{word}` is in the model's place" in error.reason


# Decision 7: bare pchan and nchan flags, and dotted values kept as text.
@pytest.mark.parametrize(
    "line",
    [".model vd VDMOS pchan VTO=-2", ".model vd VDMOS(pchan VTO=-2)", ".model vd VDMOS(nchan)"],
)
def test_a_model_may_carry_a_channel_flag(line: str) -> None:
    model = parse(SourceText(f"t\n{line}\n.end\n"), Dialect.NGSPICE).items[1]
    assert isinstance(model, ModelStatement)
    assert [flag.name.lower() for flag in model.flags] in (["pchan"], ["nchan"])


@pytest.mark.parametrize(
    "line", [".model b NMOS level=8 version=3.3.0", ".model b NMOS(version=3.3.0 level=8)"]
)
def test_a_dotted_model_value_is_text(line: str) -> None:
    model = parse(SourceText(f"t\n{line}\n.end\n"), Dialect.NGSPICE).items[1]
    version = next(param for param in model.params if param.name == "version")
    assert version.value == Identifier("3.3.0", version.value.span)


def test_continued_transistor_lines_join() -> None:
    item = parse(SourceText("t\nQ1 c b\n+ e s qm\n+ off\n.end\n"), Dialect.NGSPICE).items[1]
    assert _reading(item)[1:5] == (["c", "b", "e", "s"], "qm", None, ["off"])
