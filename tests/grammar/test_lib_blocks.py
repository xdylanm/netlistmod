"""`.lib name` … `.endl` blocks are opaque on both dialects (M11 T3; decision 0012 item 1)."""

from __future__ import annotations

import pytest

from netlistmod import (
    Dialect,
    Netlist,
    OpaqueBlock,
    OpaqueStatement,
    ParseError,
    Resistor,
    UnknownDirective,
)

_CIRCUIT = "V1 in 0 1\nR1 in out 1k\n"


@pytest.fixture(params=[Dialect.NGSPICE, Dialect.LTSPICE], ids=lambda dialect: dialect.value)
def both_dialects(request: pytest.FixtureRequest) -> Dialect:
    dialect: Dialect = request.param
    return dialect


def _load(dialect: Dialect, body: str) -> Netlist:
    return Netlist.from_text(f"t\n{_CIRCUIT}{body}.op\n.end\n", dialect=dialect)


def _kinds(netlist: Netlist) -> list[tuple[str, str]]:
    return [
        (type(line.item).__name__, line.item.kind)
        for line in netlist.lines
        if isinstance(line.item, OpaqueBlock | OpaqueStatement)
    ]


def test_the_body_of_a_block_is_not_topology(both_dialects: Dialect) -> None:
    text = ".lib extras\nR3 out hidden 1k\nR4 hidden 0 1k\n.endl\n"
    netlist = _load(both_dialects, text)
    assert _kinds(netlist) == [("OpaqueBlock", "lib")]
    assert sorted(net.name for net in netlist.nets()) == ["0", "in", "out"]
    assert [line.item.designator for line in netlist.lines.find_all(Resistor)] == ["R1"]
    assert netlist.signature() == _load(both_dialects, "").signature()
    assert netlist.source.text == f"t\n{_CIRCUIT}{text}.op\n.end\n"


@pytest.mark.parametrize(
    "block",
    [
        ".lib x\n.endl\n",
        ".LIB x\nR9 a b 1k\n.ENDL\n",
        ".lib x\nR9 a b 1k\n.endl x\n",
        ".lib x ; comment\nR9 a b 1k\n.endl ; comment\n",
        "  .lib x\n  R9 a b 1k\n  .endl\n",
        ".lib x\nnot even a netlist line (\n\n* comment\n+ continuation\n.endl\n",
        ".lib x\n.model d D\n+ is=1\n+ n=2\n\n+ after a blank line\n.endl\n",
        '.lib x\n.lib "vendor.lib" tt\n.lib other.lib sec\n.endl\n',
        ".lib x\n.subckt s p\nR9 p 0 1k\n.ends\n.model d D\n.param k=1\n.tran 1u 1m\n.endl\n",
    ],
)
def test_block_forms(both_dialects: Dialect, block: str) -> None:
    netlist = _load(both_dialects, block)
    assert _kinds(netlist) == [("OpaqueBlock", "lib")]
    assert [line.item.designator for line in netlist.lines.find_all(Resistor)] == ["R1"]
    assert netlist.scope().models == {}


@pytest.mark.parametrize(
    "statement",
    [".lib models.lib", ".lib models.lib typical", '.lib "a b.lib" typical', ".lib a.lib ; c"],
)
def test_a_lib_line_with_no_endl_stays_a_statement(both_dialects: Dialect, statement: str) -> None:
    assert _kinds(_load(both_dialects, f"{statement}\n")) == [("OpaqueStatement", "lib")]


def test_a_two_field_lib_line_before_an_endl_on_ngspice_is_not_a_block() -> None:
    netlist = _load(Dialect.NGSPICE, ".lib models.lib typical\nR2 out 0 1k\n.endl\n")
    assert _kinds(netlist) == [("OpaqueStatement", "lib")]
    assert netlist.lines.find(UnknownDirective) is not None


def test_a_lookahead_does_not_cross_end(both_dialects: Dialect) -> None:
    # What follows .end is an error of its own, so the .lib line must not reach past it.
    with pytest.raises(ParseError) as captured:
        Netlist.from_text(f"t\n{_CIRCUIT}.lib x\n.end\n.endl\n", dialect=both_dialects)
    assert captured.value.line == 6


def test_blocks_do_not_nest(both_dialects: Dialect) -> None:
    text = f"t\n{_CIRCUIT}.lib x\n.lib y\nR9 a b 1k\n.endl\n"
    netlist = Netlist.from_text(f"{text}.op\n.end\n", dialect=both_dialects)
    assert _kinds(netlist) == [("OpaqueStatement", "lib"), ("OpaqueBlock", "lib")]


def test_two_blocks_stand_side_by_side(both_dialects: Dialect) -> None:
    netlist = _load(both_dialects, ".lib x\nR8 a b 1k\n.endl\n.lib y\nR9 a b 1k\n.endl\n")
    assert _kinds(netlist) == [("OpaqueBlock", "lib"), ("OpaqueBlock", "lib")]


def test_a_block_may_stand_in_a_subcircuit_body(both_dialects: Dialect) -> None:
    body = ".subckt s p\n.lib x\nR9 p hidden 1k\n.endl\nR8 p 0 1k\n.ends\nX1 out s\n"
    netlist = _load(both_dialects, body)
    assert [net.name for net in netlist.nets(("s",))] == ["p", "0"]


def test_a_stray_endl_is_unchanged() -> None:
    netlist = _load(Dialect.NGSPICE, ".endl\n")
    assert netlist.lines.find(UnknownDirective) is not None
    with pytest.raises(ParseError):
        _load(Dialect.LTSPICE, ".endl\n")


def test_a_second_endl_after_a_block_is_stray() -> None:
    netlist = _load(Dialect.NGSPICE, ".lib x\n.endl\n.endl\n")
    assert netlist.lines.find(OpaqueBlock) is not None
    assert netlist.lines.find(UnknownDirective) is not None
    with pytest.raises(ParseError):
        _load(Dialect.LTSPICE, ".lib x\n.endl\n.endl\n")


def test_an_endl_inside_an_opaque_if_block_stays_text() -> None:
    netlist = _load(Dialect.NGSPICE, ".if (1)\n.lib x\n.endl\n.endif\n")
    assert _kinds(netlist) == [("OpaqueBlock", "if")]


def test_a_block_keeps_crlf_and_a_lone_cr(both_dialects: Dialect) -> None:
    text = (
        f"t\r\n{_CIRCUIT.replace(chr(10), chr(13) + chr(10))}.lib x\r\nR9\ra b\r\n.endl\r\n.end\r\n"
    )
    netlist = Netlist.from_text(text, dialect=both_dialects)
    assert _kinds(netlist) == [("OpaqueBlock", "lib")]
    assert netlist.source.text == text
