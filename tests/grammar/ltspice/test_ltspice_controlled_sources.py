"""LTspice linear dependent sources and switches, E, F, G, H, S and W (M14, decision 0015)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from netlistmod import (
    Cccs,
    Ccvs,
    CurrentSwitch,
    Dialect,
    Netlist,
    ParseError,
    SourceText,
    Span,
    UnsupportedConstruct,
    Vccs,
    Vcvs,
    VoltageSwitch,
    parse,
)
from tests.support.corpus import accept_files


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


@pytest.mark.parametrize(
    ("line", "kind", "nodes", "value"),
    [
        ("E1 OUT N002 VX 0 2.2", Vcvs, ["OUT", "N002", "VX", "0"], "2.2"),
        ("G1 OUT 0 VX VX2 -0.00194", Vccs, ["OUT", "0", "VX", "VX2"], "-0.00194"),
        ("E1 a 0 b 0 2k2", Vcvs, ["a", "0", "b", "0"], "2k2"),
        ("G1 a 0 b 0 {-gm}", Vccs, ["a", "0", "b", "0"], "-gm"),
    ],
)
def test_e_and_g_have_four_nodes_and_a_gain(
    line: str, kind: type, nodes: list[str], value: str
) -> None:
    item = _element(line)
    assert type(item) is kind
    assert [node.name for node in item.nodes] == nodes
    assert item.value.text == value


@pytest.mark.parametrize(
    ("line", "kind", "control"),
    [
        ("F1 OUT 0 V1 {K}", Cccs, "V1"),
        ("H1 OUT 0 V1 -2.2k", Ccvs, "V1"),
        ("H1 a 0 X1:Vq 1k", Ccvs, "X1:Vq"),
    ],
)
def test_f_and_h_have_a_controlling_source(line: str, kind: type, control: str) -> None:
    item = _element(line)
    assert type(item) is kind
    assert item.control.designator == control


@pytest.mark.parametrize(
    ("line", "kind", "state", "value"),
    [
        ("S1 0 OUT VX 0 a_switch off", VoltageSwitch, "off", None),
        ("S1 0 OUT VX 0 a_switch on", VoltageSwitch, "on", None),
        ("S1 0 OUT VX 0 a_switch off=1", VoltageSwitch, "off", "1"),
        ("W1 OUT 0 Vsense a_switch", CurrentSwitch, None, None),
    ],
)
def test_switches_take_a_model_and_an_optional_state(
    line: str, kind: type, state: str | None, value: str | None
) -> None:
    item = _element(line)
    assert type(item) is kind
    assert [flag.name for flag in item.flags] == ([state] if state else [])
    if value is not None:
        assert item.flags[0].value.text == value


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("E1 OUT N002 VX 0 E", 18),  # LTspice's export of an unset gain
        ("E1 a 0 b 0", 11),
        ("E1 a 0 b 0 2 3", 14),
        ("E1 a 0 b 0 gain=2", 12),
        ("G1 a 0 b 0 2 m=2", 14),  # no parameter on any of the six
        ("F1 a 0 V1 2 m=2", 13),
        ("S1 a 0 b 0 sm m=2", 15),
        ("S1 a 0 b 0 sm on off", 18),
        ("F1 0,out Vs 2", 5),  # LTspice stops on this comma
    ],
)
def test_malformed_lines_are_rejected(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)


@pytest.mark.parametrize(
    ("line", "column", "form"),
    [
        ("E1 a 0 POLY(1) b 0 0 2", 8, "poly"),
        ("E1 a 0 b 0 table=(0,0,1,2)", 12, "table"),
        ("G1 a 0 b 0 Laplace=1/(1+s)", 12, "laplace"),
        ("H1 a 0 POLY(1) V1 0 2", 8, "poly"),
    ],
)
def test_the_nonlinear_forms_are_unsupported(line: str, column: int, form: str) -> None:
    with pytest.raises(UnsupportedConstruct) as captured:
        parse(SourceText(f"title\n{line}\n.end\n"), Dialect.LTSPICE)
    assert (captured.value.line, captured.value.column) == (2, column)
    assert captured.value.construct == f"LTspice nonlinear dependent source form ({form})"


_FAMILY = Path(__file__).parents[2] / "corpus" / "ltspice" / "controlled_sources"


@pytest.mark.parametrize(
    "path",
    [p for p in accept_files(_FAMILY.parent, (".net", ".cir")) if p.parent == _FAMILY],
    ids=lambda path: path.name,
)
def test_every_file_of_the_family_loads_and_round_trips(path: Path) -> None:
    netlist = Netlist.load(path, dialect=Dialect.LTSPICE)
    assert netlist.to_bytes() == path.read_bytes()


# Review R1: each refused gain form names the form, at the offending token.
@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("E1 out 0 vx 0 gain=2", 15, "`gain=` is not a form of the LTspice reference"),
        ("F1 a 0 Vs gain=2", 11, "write the gain positionally"),
        ("E1 out 0 vx 0 2 3", 17, "`3` is a second value: a dependent source takes one gain"),
        ("H1 a 0 Vs 1k 2k2", 14, "`2k2` is a second value"),
        ("E1 OUT N002 VX 0 E", 18, "`E` is not a gain: the gain is not set"),
        ("G1 OUT 0 VX VX2 G", 17, "`G` is not a gain: the gain is not set"),
        ("F1 OUT 0 V1 F", 13, "`F` is not a gain"),
        ("H1 OUT 0 V1 H", 13, "`H` is not a gain"),
    ],
)
def test_refused_gain_forms_name_the_form(line: str, column: int, reason: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason
