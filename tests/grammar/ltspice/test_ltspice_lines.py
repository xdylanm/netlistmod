"""LTspice transmission lines T, O and U (M16, decision 0019)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from netlistmod import (
    Dialect,
    Formula,
    LosslessLine,
    LossyLine,
    Netlist,
    ParseError,
    RcLine,
    SourceText,
    Span,
    parse,
)
from tests.support.corpus import accept_files


def _item(line: str) -> Any:
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


def _params(item: Any) -> list[tuple[str, str]]:
    return [(param.name, param.value.text) for param in item.params]


@pytest.mark.parametrize(
    ("line", "params"),
    [
        ("T1 a 0 b 0 Zo=50 Td=1n", [("Zo", "50"), ("Td", "1n")]),
        ("T1 N001 0 N002 0 Td=50n Z0=50", [("Td", "50n"), ("Z0", "50")]),
        ("T1 a 0 b 0 ZO=50 TD=1n", [("ZO", "50"), ("TD", "1n")]),
        ("T1 a 0 b 0 Zo={z} Td=1n5", [("Zo", "z"), ("Td", "1n5")]),
        ("T1 a 0 b 0 Zo=50\n+ Td=1n", [("Zo", "50"), ("Td", "1n")]),
    ],
)
def test_t_takes_zo_and_td(line: str, params: list[tuple[str, str]]) -> None:
    item = _item(line)
    assert type(item) is LosslessLine
    assert [node.name for node in item.port1] == [item.nodes[0].name, "0"]
    assert _params(item) == params


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("T1 a 0 b 0 Zo=50", 17, "the line's length must be given, as `Td=`"),
        ("T1 a 0 b 0 Td=1n", 17, "`Z0=` (or `Zo=`) must be given"),
        ("T1 a 0 b 0 Zo=50 Z0=50 Td=1n", 18, "one parameter"),
        ("T1 a 0 b 0 Zo=50 F=100meg NL=0.1", 18, "the reference lists only"),
        ("T1 a 0 b 0 Zo=50 Td=1n IC=0,0,0,0", 24, "the reference lists only"),
        ("T1 a 0 b 0 Zo=50 Td=1n rel=1", 24, "the reference lists only"),
    ],
)
def test_refused_t_lines_name_the_rule(line: str, column: int, reason: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("T1 a 0 b 0 Zo=50 Td=1n foo=1", 24),
        ("T1 a 0 b 0 Zo=50 Td=1n m=2", 24),
        ("T1 a 0 b Zo=50", 12),
    ],
)
def test_other_t_forms_are_syntax_errors(line: str, column: int) -> None:
    assert (_reject(line).line, _reject(line).column) == (2, column)


def test_o_takes_four_nodes_and_a_model() -> None:
    item = _item("O1 N001 0 N002 0 myline")
    assert type(item) is LossyLine
    assert item.model.model_name == "myline"


@pytest.mark.parametrize(
    ("line", "column"), [("O1 N001 0 N002 0 myline LTRA", 25), ("O1 a 0 b 0 lm len=2", 15)]
)
def test_o_takes_nothing_after_its_model(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert "nothing after it" in error.reason


@pytest.mark.parametrize(
    ("line", "params"),
    [
        ("U1 IN1 IN2 0 myRC L=1e-3 N=20", [("L", "1e-3"), ("N", "20")]),
        ("U1 a b 0 um N=6 l=5", [("N", "6"), ("l", "5")]),
        ("U1 a b 0 um L={len*5}", [("L", "len*5")]),
        ("U1 inv b 0 um L=5", [("L", "5")]),
    ],
)
def test_u_is_a_urc_line(line: str, params: list[tuple[str, str]]) -> None:
    item = _item(line)
    assert type(item) is RcLine
    assert len(item.nodes) == 3
    assert _params(item) == params


def test_a_bare_parameter_is_a_bare_formula() -> None:
    value = _item("U1 a b 0 um L=len").params[0].value
    assert isinstance(value, Formula) and value.delimiter == "" and value.text == "len"


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("U1 a b 0 um", 12),
        ("U1 a b 0 um N=6", 16),
        ("U1 a b 0 um 5", 13),
        ("U1 a b 0 um L=5 m=2", 17),
        ("U1 a b 0 0 um L=5", 12),
        ("U1 a b 0 um L=len*2", 15),
    ],
)
def test_refused_u_lines(line: str, column: int) -> None:
    assert (_reject(line).line, _reject(line).column) == (2, column)


@pytest.mark.parametrize("letter", ["Y", "P"])
def test_y_and_p_are_not_ltspice_letters(letter: str) -> None:
    assert _reject(f"{letter}1 a 0 b 0 m").column == 1


def test_ltra_flags_are_refused_with_a_reason() -> None:
    error = _reject(".model lm LTRA(R=1 L=50n C=20p len=1 nosteplimit)")
    assert error.column == 38
    assert "the LTspice reference lists only R, L, G, C and Len" in error.reason


_FAMILY = Path(__file__).parents[2] / "corpus" / "ltspice" / "transmission_lines"
_FIXTURES = json.loads((_FAMILY / "manifest.json").read_text(encoding="utf-8"))["fixtures"]


@pytest.mark.parametrize(
    "path",
    [
        p
        for p in accept_files(_FAMILY.parent, (".net", ".cir"))
        if p.parent == _FAMILY and "error" not in _FIXTURES[p.name]
    ],
    ids=lambda path: path.name,
)
def test_every_file_of_the_family_loads_and_round_trips(path: Path) -> None:
    netlist = Netlist.load(path, dialect=Dialect.LTSPICE)
    assert netlist.to_bytes() == path.read_bytes()


@pytest.mark.parametrize(
    "name", sorted(name for name, entry in _FIXTURES.items() if "error" in entry)
)
def test_the_family_rejects_fail_where_the_manifest_says(name: str) -> None:
    entry = _FIXTURES[name]
    with pytest.raises(ParseError) as captured:
        Netlist.load(_FAMILY / name, dialect=Dialect.LTSPICE)
    assert type(captured.value).__name__ == entry["error"]
    assert (captured.value.line, captured.value.column) == (entry["line"], entry["column"])
