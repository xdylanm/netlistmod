"""ngspice 47 probes for the value and grammar fixes of M18 D5 (A1-2, A1-4, A2-19, A2-20).

Each probe pairs what ngspice does with what the library reads. The number forms of A1-2 run in
ngspice, which reads them by its own rules (letters it does not know are ignored, and so is
anything after them); the library refuses each, as the manual does not write them, and
discrepancies.md records the reading.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import Dialect, OpaqueBlock, ParseError, SourceText, parse
from tests.support.ngspice import run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ngspice")


def _refused(text: str) -> bool:
    try:
        parse(SourceText(text), Dialect.NGSPICE)
    except ParseError:
        return True
    return False


# A1-2: (value, the resistance ngspice 47 reads, a warning ngspice writes or "").
_NUMBERS = [
    ("1d3", 1000.0, ""),
    ("1D3", 1000.0, ""),
    ("1d-3", -3.0, ""),
    ("2.5D+2", 2.0, ""),
    ("1meg5", 1e6, ""),
    ("2.2k7", 2200.0, ""),
    ("1kOhm2", 1000.0, ""),
    ("1k5x", 1000.0, ""),
    ("1μ", 1.0, ""),
    ("1μF", 1.0, ""),
    ("1kΩ", 1000.0, ""),
    ("1_000", 1.0, ""),
    ("0x10", 1e-12, "too small"),
    ("1.5.3", 1.5, ""),
    ("1e+", 1.0, ""),
    ("(1k)", 1000.0, "can't find model"),
]


@pytest.mark.parametrize(("value", "ohms", "warning"), _NUMBERS, ids=[v for v, _, _ in _NUMBERS])
def test_number_forms_ngspice_runs_but_the_library_refuses(
    solver: Solver, tmp_path: Path, value: str, ohms: float, warning: str
) -> None:
    line = f"R1 a 0 {value}"
    text = f"probe\nV1 a 0 DC 1\n{line}\n.op\n.save all @r1[resistance]\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.returncode == 0, result.log
    assert result.device("r1", "resistance") == pytest.approx(ohms, rel=1e-9)
    assert (warning in result.log) if warning else ("arning" not in result.log), result.log
    assert _refused(f"t\n{line}\n.end\n")


_Q = (
    "probe\nV1 vcc 0 5\nRC vcc c 1k\nV2 b 0 0.7\nR9 qm 0 1\n"
    ".model qm NPN(IS=1e-16)\n{line}\n.op\n.end\n"
)
_M = (
    "probe\nV1 vcc 0 5\nRD vcc d 1k\nVG g 0 3\nRS s 0 10\nR9 mm 0 1\n"
    ".model mm NMOS(VTO=1 KP=1m)\n{line}\n.op\n.end\n"
)
_J = (
    "probe\nV1 vcc 0 5\nRD vcc d 1k\nVG g 0 0\nR9 jm 0 1\n"
    ".model jm NJF(beta=1m)\n{line}\n.op\n.end\n"
)
_E = "probe\nVC c 0 1\nR1 o 0 1\n{line}\n.op\n.end\n"


# A1-4: a number with a letter outside ngspice's NUMBER, after a transistor's model. ngspice 47
# runs a Q or J line with it as the area, ignoring the letter; the library refuses it at the token
# and never reads it as the model. (circuit, node, line, a line with the same result, reason)
_AFTER_MODEL = {
    "q-greek-mu": (_Q, "c", "Q1 c b 0 qm 1μ", "Q1 c b 0 qm", "positional area"),
    "q-ohm": (_Q, "c", "Q1 c b 0 qm 2Ω", "Q1 c b 0 qm 2", "positional area"),
    "j-greek-mu": (_J, "d", "J1 d g 0 jm 2μ", "J1 d g 0 jm 2", "ends too early"),
    "poly-greek-mu": (_E, "o", "E1 o 0 POLY(1) c 0 0 2μ", "E1 o 0 POLY(1) c 0 0 2", "coefficient"),
}


@pytest.mark.parametrize("case", sorted(_AFTER_MODEL))
def test_a_number_with_another_letter_runs_but_the_library_refuses_it(
    solver: Solver, tmp_path: Path, case: str
) -> None:
    template, node, line, same_as, reason = _AFTER_MODEL[case]
    text = template.format(line=line)
    result = run(solver, tmp_path / "probe", text)
    reference = run(solver, tmp_path / "reference", template.format(line=same_as))
    assert result.ok and reference.ok, result.log + reference.log
    assert result.voltage(node) == pytest.approx(reference.voltage(node), rel=1e-9)
    with pytest.raises(ParseError) as captured:
        parse(SourceText(text), Dialect.NGSPICE)
    assert reason in captured.value.reason
    assert captured.value.line == text.splitlines().index(line) + 1


@pytest.mark.parametrize("line", ["M1 d g s mm 1μ", "M1 d g s mm 2"])
def test_a_number_after_an_m_model_stops_ngspice_and_is_refused(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    text = _M.format(line=line)
    result = run(solver, tmp_path, text)
    assert not result.ok
    assert "could not find a valid modelname" in result.log, result.log
    assert _refused(text)


# A2-19: lines after an inner .endif, inside the outer block.
@pytest.mark.parametrize("follow", ["R1 a 0 1k", "* comment", ".param x=1"])
def test_a_line_after_a_nested_if_block_runs_and_loads(
    solver: Solver, tmp_path: Path, follow: str
) -> None:
    text = f"probe\nV1 a 0 1\nR0 a 0 1k\n.if (1)\n.if (2)\n.endif\n{follow}\n.endif\n.op\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    items = parse(SourceText(text), Dialect.NGSPICE).items
    assert [item.kind for item in items if isinstance(item, OpaqueBlock)] == ["if"]


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
    parse(source, Dialect.NGSPICE)
    assert source.to_bytes() == data
