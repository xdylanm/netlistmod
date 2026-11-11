"""LTspice 26.1.1 probes for the value and grammar fixes of M18 D5 (A1-4, A1-6, A1-8, A1-11, A2-20).

Each probe pairs what LTspice does with what the library reads. Nothing LTspice writes is
committed (decision 0009 item 2).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import (
    Dialect,
    NumericValue,
    ParseError,
    Resistor,
    SourceText,
    SubcktDefinition,
    Transistor,
    Vcvs,
    parse,
)
from tests.support.ltspice import run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ltspice")

_Q = (
    "probe\nV1 vcc 0 5\nRC vcc c 1k\nV2 b 0 0.7\nR9 qm 0 1\n"
    ".model qm NPN(IS=1e-16)\n{line}\n.op\n.end\n"
)
_M = (
    "probe\nV1 vcc 0 5\nRD vcc d 1k\nVG g 0 3\nRS s 0 10\nR9 mm 0 1\n"
    ".model mm VDMOS(VTO=1 KP=1m)\n{line}\n.op\n.end\n"
)
_J = (
    "probe\nV1 vcc 0 5\nRD vcc d 1k\nVG g 0 0\nR9 jm 0 1\n.model jm NJF(beta=1m)\n"
    ".model zm NMF(beta=1m)\n{line}\n.op\n.end\n"
)
_E = "probe\nVC c 0 1\nR1 o 0 1\n{line}\n.op\n.end\n"


def _transistor(text: str) -> tuple[list[str], str, str | None] | None:
    try:
        items = parse(SourceText(text), Dialect.LTSPICE).items
    except ParseError:
        return None
    item = next(item for item in items if isinstance(item, Transistor))
    area = item.area.text if item.area is not None else None
    return [node.name for node in item.nodes], item.model.model_name, area


# A1-4: (circuit, the node to read, a line whose result it must equal, the library's reading).
# LTspice's NUMBER takes any letter after a number, and so does the positional number since D5.
_AREAS = {
    "q-greek-mu": (_Q, "c", "Q1 c b 0 qm 1μ", "Q1 c b 0 qm 1u", (["c", "b", "0"], "qm", "1μ")),
    "q-ohm": (_Q, "c", "Q1 c b 0 qm 2Ω", "Q1 c b 0 qm 2", (["c", "b", "0"], "qm", "2Ω")),
    "j-greek-mu": (_J, "d", "J1 d g 0 jm 2μ", "J1 d g 0 jm 2u", (["d", "g", "0"], "jm", "2μ")),
    "j-ohm": (_J, "d", "J1 d g 0 jm 2Ω", "J1 d g 0 jm 2", (["d", "g", "0"], "jm", "2Ω")),
    "z-greek-mu": (_J, "d", "Z1 d g 0 zm 2μ", "Z1 d g 0 zm 2u", (["d", "g", "0"], "zm", "2μ")),
}


@pytest.mark.parametrize("case", sorted(_AREAS))
def test_an_area_with_any_letter_reads_as_ltspice_reads_it(
    solver: Solver, tmp_path: Path, case: str
) -> None:
    template, node, line, same_as, reading = _AREAS[case]
    text = template.format(line=line)
    result = run(solver, tmp_path / "probe", text)
    reference = run(solver, tmp_path / "reference", template.format(line=same_as))
    assert result.ok and reference.ok, result.log + reference.log
    assert result.voltage(node) == pytest.approx(reference.voltage(node), rel=1e-9)
    assert _transistor(text) == reading


@pytest.mark.parametrize("line", ["M1 d g s mm 2", "M1 d g s mm 1μ"])
def test_a_number_after_an_m_model_stops_ltspice_and_is_refused(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    text = _M.format(line=line)
    result = run(solver, tmp_path, text)
    assert not result.ok
    assert any("Unknown parameter" in error for error in result.errors), result.log
    assert _transistor(text) is None


@pytest.mark.parametrize(
    ("line", "out", "coefficients"),
    [
        ("E1 o 0 POLY(1) c 0 0 2μ", 2e-6, ["0", "2μ"]),
        ("E1 o 0 POLY(1) (c,0) 0 2μ", 2e-6, ["0", "2μ"]),
        ("E1 o 0 POLY(1) c 0 0 2Ω", 2.0, ["0", "2Ω"]),
    ],
)
def test_a_poly_coefficient_with_any_letter_reads_as_ltspice_reads_it(
    solver: Solver, tmp_path: Path, line: str, out: float, coefficients: list[str]
) -> None:
    text = _E.format(line=line)
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert result.voltage("o") == pytest.approx(out, rel=1e-9)
    item = next(i for i in parse(SourceText(text), Dialect.LTSPICE).items if isinstance(i, Vcvs))
    assert [value.text for value in item.coefficients] == coefficients


def _resistance(solver: Solver, folder: Path, value: str) -> float:
    result = run(solver, folder, f"probe\nV1 a 0 1\nR1 a 0 {value}\n.op\n.end\n")
    assert result.ok, result.log
    (current,) = result.plot("Operating Point").real("I(V1)")
    return -1 / current


# A1-6 and A1-8: LTspice reads these numbers without the letters and the digits after them. The
# library refuses `1d3` and `1_000` (LT-NUM-002) and keeps `1a` as text: the reference's
# SPICE-SYNTAX-REFERENCE leaves `a` out, SCHEMATIC-REFERENCE lists it (discrepancies.md).
@pytest.mark.parametrize(
    ("value", "ohms", "loads"),
    [("1d3", 1.0, False), ("1D3", 1.0, False), ("1_000", 1.0, False), ("1a", 1.0, True)],
)
def test_letters_ltspice_does_not_read_as_a_multiplier(
    solver: Solver, tmp_path: Path, value: str, ohms: float, loads: bool
) -> None:
    assert _resistance(solver, tmp_path, value) == pytest.approx(ohms, rel=1e-9)
    try:
        items = parse(SourceText(f"t\nR1 a 0 {value}\n.end\n"), Dialect.LTSPICE).items
    except ParseError:
        assert not loads
    else:
        assert loads
        resistor = items[1]
        assert isinstance(resistor, Resistor)
        assert isinstance(resistor.value, NumericValue)
        assert resistor.value.text == value


# A1-7 (decision 14): the library does not read .options, so `reject_number_tails`, which makes
# LTspice stop at letters after a number, changes nothing in what loads (discrepancies.md).
@pytest.mark.parametrize(("value", "runs"), [("10V", False), ("10", True)])
def test_reject_number_tails_is_not_read_by_the_library(
    solver: Solver, tmp_path: Path, value: str, runs: bool
) -> None:
    text = f"probe\nV1 a 0 1\nR1 a 0 {value}\n.options reject_number_tails\n.op\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.ok is runs, result.log
    if not runs:
        assert any("reject_number_tails" in error for error in result.errors), result.log
    resistor = parse(SourceText(text), Dialect.LTSPICE).items[2]
    assert isinstance(resistor, Resistor)
    assert isinstance(resistor.value, NumericValue)
    assert resistor.value.text == value


# A1-11, decision 10: the comma between .subckt parameters, as on X.
_SUBCKT = "probe\nV1 a 0 1\nX1 a 0 s\n{header}\nR1 p n {{r}}\n.ends s\n.op\n.end\n"


@pytest.mark.parametrize(
    ("header", "names"),
    [
        (".subckt s p n r=1k, q=2", ["r", "q"]),
        (".subckt s p n params: r=1k, q=2", ["r", "q"]),
        (".subckt s p n r=1k,q=2, w=3", ["r", "q", "w"]),
        (".subckt s p n r=1k ,q=2", ["r", "q"]),
        (".subckt s p n, r=1k", ["r"]),
    ],
)
def test_subckt_parameter_commas_run_and_load(
    solver: Solver, tmp_path: Path, header: str, names: list[str]
) -> None:
    text = _SUBCKT.format(header=header)
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    (current,) = result.plot("Operating Point").real("I(V1)")
    assert current == pytest.approx(-1e-3, rel=1e-9)
    items = parse(SourceText(text), Dialect.LTSPICE).items
    definition = next(item for item in items if isinstance(item, SubcktDefinition))
    assert [param.name for param in definition.params] == names


def test_a_comma_right_after_params_stops_ltspice_and_is_refused(
    solver: Solver, tmp_path: Path
) -> None:
    # M18 D2 (decision 5's rule): a line shape the grammar can see, so it is refused.
    text = _SUBCKT.format(header=".subckt s p n params:, r=1k")
    result = run(solver, tmp_path, text)
    assert not result.ok
    assert any("Expected end of line" in error for error in result.errors), result.log
    with pytest.raises(ParseError, match="a comma right after `params:`"):
        parse(SourceText(text), Dialect.LTSPICE)


# A2-20, decision 12: a lone CR right before a CRLF is text.
@pytest.mark.parametrize(
    "data",
    [
        b"probe\r\r\nV1 a 0 1\r\nR1 a 0 1k\r\n.op\r\n.end\r\n",
        b"probe\r\n* abc\r\r\nV1 a 0 1\r\nR1 a 0 1k\r\n.op\r\n.end\r\n",
        b"probe\r\nV1 a 0 1\r\nR1 a 0 1k ; c\r\r\n.op\r\n.end\r\n",
    ],
)
def test_a_lone_cr_before_a_crlf_runs_and_loads(
    solver: Solver, tmp_path: Path, data: bytes
) -> None:
    result = run(solver, tmp_path, data)
    assert result.ok, result.log
    source = SourceText.from_bytes(data)
    parse(source, Dialect.LTSPICE)
    assert source.to_bytes() == data
