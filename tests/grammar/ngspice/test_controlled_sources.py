"""ngspice linear dependent sources and switches, E, F, G, H, S and W (M14, decision 0015)."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    Cccs,
    Ccvs,
    ControlledSource,
    CurrentSwitch,
    Dialect,
    ElementReference,
    Formula,
    NumericValue,
    ParseError,
    SourceText,
    Span,
    Switch,
    UnsupportedConstruct,
    Vccs,
    Vcvs,
    VoltageSwitch,
    parse,
)


def _element(line: str) -> Any:
    text = f"title\n{line}\n.end\n"
    result = parse(SourceText(text), Dialect.NGSPICE)
    assert len(result.items) == 3, result.items
    item = result.items[1]
    assert item.span == Span(6, 6 + len(line) + 1)
    return item


def _slice(line: str, span: Span) -> str:
    return f"title\n{line}"[span.start : span.end]


def _reject(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"title\n{line}\n.end\n"), Dialect.NGSPICE)
    return captured.value


@pytest.mark.parametrize(
    ("line", "kind", "nodes", "value"),
    [
        ("E1 2 3 14 1 2.0", Vcvs, ["2", "3", "14", "1"], "2.0"),
        ("G1 2 0 5 0 0.1", Vccs, ["2", "0", "5", "0"], "0.1"),
        ("e1 /OUT a /VX GND {k}", Vcvs, ["/OUT", "a", "/VX", "GND"], "k"),
        ("G1 a,0 b 0 '2*gm'", Vccs, ["a", "0", "b", "0"], "2*gm"),
    ],
)
def test_e_and_g_have_four_nodes_and_a_gain(
    line: str, kind: type, nodes: list[str], value: str
) -> None:
    item = _element(line)
    assert type(item) is kind and isinstance(item, ControlledSource)
    assert [node.name for node in item.nodes] == nodes
    assert [node.name for node in item.control_nodes] == nodes[2:]
    assert item.value.text == value
    assert isinstance(item.value, NumericValue | Formula)
    for node in item.nodes:
        assert _slice(line, node.span) == node.name


@pytest.mark.parametrize(
    ("line", "kind", "control", "value"),
    [
        ("F1 13 5 VSENS 5", Cccs, "VSENS", "5"),
        ("HX 5 17 VZ 0.5K", Ccvs, "VZ", "0.5K"),
        ("F1 /OUT GND V1 {K}", Cccs, "V1", "K"),
    ],
)
def test_f_and_h_have_two_nodes_and_a_controlling_source(
    line: str, kind: type, control: str, value: str
) -> None:
    item = _element(line)
    assert type(item) is kind
    assert len(item.nodes) == 2
    assert item.control == ElementReference(control, item.control.span)
    assert _slice(line, item.control.span) == control
    assert item.value.text == value


@pytest.mark.parametrize("line", ["G1 a 0 b 0 1m m=2", "F1 13 5 VSENS 5 m=2"])
def test_f_and_g_take_m(line: str) -> None:
    (param,) = _element(line).params
    assert (param.name, param.value.text) == ("m", "2")


@pytest.mark.parametrize(
    ("line", "kind", "nodes", "state"),
    [
        ("s1 1 2 3 4 switch1 ON", VoltageSwitch, 4, "ON"),
        ("s2 5 6 3 0 sm2 off", VoltageSwitch, 4, "off"),
        ("Switch1 1 2 10 0 smodel1", VoltageSwitch, 4, None),
        ("w1 1 2 vclock switchmod1", CurrentSwitch, 2, None),
        ("W2 3 0 vramp sm1 ON", CurrentSwitch, 2, "ON"),
        ("wreset 5 6 vclck lossyswitch OFF", CurrentSwitch, 2, "OFF"),
    ],
)
def test_switches_take_a_model_and_an_optional_state(
    line: str, kind: type, nodes: int, state: str | None
) -> None:
    # The manual's own examples (§3.3.15).
    item = _element(line)
    assert type(item) is kind and isinstance(item, Switch)
    assert len(item.nodes) == nodes
    assert [flag.name for flag in item.flags] == ([state] if state else [])
    assert _slice(line, item.model.span) == item.model.model_name


def test_a_model_named_off_is_the_model() -> None:
    item = _element("S1 a 0 b 0 off")
    assert item.model.model_name == "off"
    assert item.flags == ()


def test_continuations_join_the_line() -> None:
    item = parse(SourceText("t\nE1 a 0\n+ b 0 2\nW1 a 0\n+ Vs sm off\n.end\n"), Dialect.NGSPICE)
    vcvs, switch = item.items[1], item.items[2]
    assert [node.name for node in vcvs.control_nodes] == ["b", "0"]
    assert switch.control.designator == "Vs"


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("E1 a 0 b 0", 11),  # no gain
        ("E1 a 0 b 2", 11),  # three nodes
        ("E1 a 0 b 0 2 3", 14),  # two values
        ("E1 a 0 b 0 E", 12),  # a word in the gain's place
        ("E1 a 0 b 0 gain=2", 12),  # decision 6
        ("E1 a 0 b 0 2 m=2", 14),  # E takes no parameter
        ("H1 a 0 V1 1k m=2", 14),
        ("G1 a 0 b 0 1m temp=30", 15),
        ("F1 a 0 V1", 10),
        ("S1 a 0 b 0 sm on off", 18),  # both states
        ("S1 a 0 b 0", 11),  # no model
        ("S1 a 0 b 0 sm m=2", 15),
        ("S1 a 0 b 0 sm off=1", 18),  # LTspice only
        ("W1 a 0 V1", 10),
        ("E1 a 0 b 0 Laplace=2", 12),  # LTspice only
    ],
)
def test_malformed_lines_are_rejected(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)


@pytest.mark.parametrize(
    ("line", "form"),
    [
        ("E1 a 0 VALUE={2*V(b)}", "value"),
        ("E1 a 0 vol='2*V(b)'", "vol"),
        ("G1 a 0 cur={V(b)}", "cur"),
        ("E1 a 0 POLY(1) b 0 0 2", "poly"),
        ("E1 a 0 TABLE {V(b)} = (0,0) (1,2)", "table"),
        ("G1 a 0 value = {V(b)}", "value"),
        ("F1 a 0 POLY(1) V1 0 2", "poly"),
        ("H1 a 0 poly (1) V1 0 2", "poly"),
    ],
)
def test_the_nonlinear_forms_are_unsupported(line: str, form: str) -> None:
    with pytest.raises(UnsupportedConstruct) as captured:
        parse(SourceText(f"title\n{line}\n.end\n"), Dialect.NGSPICE)
    assert (captured.value.line, captured.value.column) == (2, 8)
    assert captured.value.construct == f"ngspice nonlinear dependent source form ({form})"
