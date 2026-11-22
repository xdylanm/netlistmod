"""The xyce P port (X-M3 B3; decision 0030 item 6; xm3-tasks 5.1 points 16 to 26)."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    Formula,
    Node,
    NumericValue,
    ParseError,
    SourceText,
    Span,
    SubcktDefinition,
    VoltageSource,
    parse,
)
from netlistmod.dialects import _XYCE, Dialect
from netlistmod.model.nodes import PortSource, element_name


def _port(line: str, before: str = "") -> Any:
    text = f"t\n{before}{line}\n.END\n"
    items = parse(SourceText(text), _XYCE).items
    position = 0
    for item in items:
        assert item.span.start == position
        position = item.span.end
    assert position == len(text)
    port = items[-2]
    assert isinstance(port, PortSource)
    return port


def _error(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"t\n{line}\n.END\n"), _XYCE)
    return captured.value


def test_the_port_line_and_its_parameters() -> None:
    port = _port("P1 a 0 DC 1 port=1 Z0=100 AC 1 30 SIN(0 1 1k)")
    assert port.designator == "P1" and port.nodes == (Node("a", Span(5, 6)), Node("0", Span(7, 8)))
    assert (port.dc, port.dc_keyword) == (NumericValue("1", Span(12, 13)), True)
    assert [(p.name, p.value.text) for p in port.params] == [("port", "1"), ("Z0", "100")]
    assert port.params[0].span == Span(14, 20) and port.params[0].name_span == Span(14, 18)
    assert port.ac is not None and port.ac.phase is not None
    assert port.stimulus is not None and port.stimulus.name == "SIN"
    assert not isinstance(port, VoltageSource)
    assert element_name(port) == "port"


@pytest.mark.parametrize(
    "line",
    [
        "P1 a 0 port=1",
        "p1 a 0 1 PORT = 2",
        "P1 a 0 1 z0=75 port=2",
        "P1 a 0 port={n} z0='r*2'",
        "P1 a 0 port=1 pulse 0 1",
        "Pport_a a 0 port=12",
        "P1 a 0 1\n+ port=1\n+ z0=100",
        "P1 a 0 port=1 Z0=-50",
    ],
)
def test_port_forms_are_read(line: str) -> None:
    port = _port(line)
    assert any(param.name.lower() == "port" for param in port.params)


def test_a_formula_port_number_is_held_as_written() -> None:
    port = _port("P1 a 0 1 port={n}")
    assert port.params[0].value == Formula("n", "{", Span(16, 19))


def test_a_port_may_stand_in_a_subcircuit_body() -> None:
    text = "t\n.SUBCKT pp a\nP1 a 0 port=1\n.ENDS\nX1 1 pp\n.END\n"
    definition = parse(SourceText(text), _XYCE).items[1]
    assert isinstance(definition, SubcktDefinition)
    assert isinstance(definition.body[0], PortSource)


@pytest.mark.parametrize("line", ["P1 a 0 1", "P1 a 0 1 z0=100", "P1 a 0 DC 1 AC 1"])
def test_a_line_without_port_is_refused(line: str) -> None:
    error = _error(line)
    assert "has no `port=`" in error.reason
    assert error.column == 1


@pytest.mark.parametrize(
    ("line", "outcome"),
    [
        ("P1 a 0 port=0", "numbered from 1"),
        ("P1 a 0 port=-1", "numbered from 1"),
        ("P1 a 0 port=+1", "unsigned"),
        ("P1 a 0 port=1.0", "integer literal"),
        ("P1 a 0 port=1.5", "stops on it"),
        ("P1 a 0 port=1e0", "stops on it"),
        ("P1 a 0 port=1k", "stops on it"),
    ],
)
def test_the_port_number_is_an_integer_of_one_or_more(line: str, outcome: str) -> None:
    error = _error(line)
    assert "an integer of 1 or more" in error.reason and outcome in error.reason
    assert error.column == line.index("=") + 2


@pytest.mark.parametrize(
    "line",
    [
        "P1 a 0 port=abc",
        "P1 a 0 port 1",
        "P1 a 0 1 port=1 z0 100",
        "P1 a 0 port=1 port=2",
        "P1 a 0 port=1 z0=100 z0=50",
        "P1 a 0 port=1 z0=100+10j",
        "P1 a 0 port=1 zo=50",
        "P1 a 0 port=1 M=2",
        "P1 a 0 port=1 DC 1",
        "P1 a 0 AC 1 port=1",
        "P1 a 0 SIN(0 1 1k) port=1",
        "P1 a 0 DC port=1",
        "P1 a 0 1, port=1",
        "P1 a 0 2 1 port=1",
        "P1 a port=1",
        "P1 a 0 port=1 AC",
    ],
)
def test_port_forms_are_refused(line: str) -> None:
    _error(line)


def test_p_stays_the_coupled_line_on_ngspice() -> None:
    # Decision 0024: the letter is ngspice's coupled transmission line; nothing changes there.
    with pytest.raises(ParseError):
        parse(SourceText("t\nP1 a 0 port=1\n.end\n"), Dialect.NGSPICE)
