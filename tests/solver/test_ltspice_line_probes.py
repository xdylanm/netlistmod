"""LTspice 26.1.1 probes for the transmission lines T, O and U (M16 T1, decision 0019).

Each probe pairs what LTspice does with what the library reads, as the probes of the M16 task
list (section 3.1) found. The circuit is the ngspice probes' (``test_ngspice_line_probes.py``):
50 Ω in, the line from ``a`` to ``b`` with ground references, 50 Ω out, and
``.param z=50 td=1n len=1``.
"""

from __future__ import annotations

import cmath
import math
from collections.abc import Callable
from pathlib import Path

import pytest

from netlistmod import (
    Dialect,
    ModelStatement,
    Netlist,
    ParseError,
    TransmissionLine,
    UnsupportedConstruct,
)
from tests.support.ltspice import ac, op, run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ltspice")

_MODELS = (
    ".model lmod LTRA(L=50n C=20p len=1)\n.model lmodr LTRA(R=10 L=50n C=20p len=1)\n"
    ".model umod URC(Rperl=10)\n.model dm D\n"
)
_BASE = (
    "probe\nV1 in 0 1 AC 1\nR1 in a 50\n{line}\nR2 b 0 50\n.param z=50 td=1n len=1\n"
    + _MODELS
    + "{analysis}\n.end\n"
)
_OP = ".op"
_AC = ".ac list 100meg"


def _text(line: str, analysis: str = _OP) -> str:
    return _BASE.format(line=line, analysis=analysis)


def _reading(text: str) -> str:
    try:
        netlist = Netlist.from_text(text, dialect=Dialect.LTSPICE)
    except UnsupportedConstruct:
        return "unsupported"
    except ParseError:
        return "refused"
    found = netlist.lines.find_all(TransmissionLine, recursive=True)
    if not found:
        return "none"
    item = found[-1].item
    assert isinstance(item, TransmissionLine)
    parts = [type(item).__name__, str(len(item.nodes))]
    model = getattr(item, "model", None)
    if model is not None:
        parts.append(model.model_name)
    parts.extend(f"{p.name}={getattr(p.value, 'text', '')}" for p in item.params)
    return " ".join(parts)


# (line, LTspice runs it, the library's reading)
_PROBES = {
    "t-zo-td": ("T1 a 0 b 0 Zo=50 Td=1n", True, "LosslessLine 4 Zo=50 Td=1n"),
    "t-z0": ("T1 a 0 b 0 Z0=50 Td=1n", True, "LosslessLine 4 Z0=50 Td=1n"),
    "t-upper": ("T1 a 0 b 0 ZO=50 TD=1n", True, "LosslessLine 4 ZO=50 TD=1n"),
    "t-braced": ("T1 a 0 b 0 Zo={z} Td={td}", True, "LosslessLine 4 Zo=z Td=td"),
    "t-bare": ("T1 a 0 b 0 Zo=z Td=1n", True, "refused"),
    "t-td-first": ("T1 a 0 b 0 Td=1n Zo=50", True, "LosslessLine 4 Td=1n Zo=50"),
    "t-comma": ("T1 a 0 b 0 Zo=50, Td=1n", True, "refused"),
    "t-continued": ("T1 a 0 b 0 Zo=50\n+ Td=1n", True, "LosslessLine 4 Zo=50 Td=1n"),
    "t-f-nl": ("T1 a 0 b 0 Zo=50 F=100meg NL=0.1", True, "refused"),
    "t-f": ("T1 a 0 b 0 Zo=50 F=100meg", True, "refused"),
    "t-no-length": ("T1 a 0 b 0 Zo=50", True, "refused"),
    "t-td-and-f": ("T1 a 0 b 0 Zo=50 Td=1n F=100meg NL=0.2", True, "refused"),
    "t-ic": ("T1 a 0 b 0 Zo=50 Td=1n IC=0,0,0,0", True, "refused"),
    "t-rel-abs": ("T1 a 0 b 0 Zo=50 Td=1n rel=1 abs=1", True, "refused"),
    "t-no-z0": ("T1 a 0 b 0 Td=1n", False, "refused"),
    "t-foo": ("T1 a 0 b 0 Zo=50 Td=1n foo=1", False, "refused"),
    "t-m": ("T1 a 0 b 0 Zo=50 Td=1n m=2", False, "refused"),
    "t-positional": ("T1 a 0 b 0 50 1n", False, "refused"),
    "t-three-nodes": ("T1 a 0 b Zo=50 Td=1n", False, "refused"),
    "o-ltra": ("O1 a 0 b 0 lmod", True, "LossyLine 4 lmod"),
    "o-ltra-r": ("O1 a 0 b 0 lmodr", True, "LossyLine 4 lmodr"),
    "o-len": ("O1 a 0 b 0 lmod len=2", False, "refused"),
    "o-m": ("O1 a 0 b 0 lmod m=2", False, "refused"),
    "o-type-name": ("O1 a 0 b 0 lmod LTRA", False, "refused"),
    "o-three-nodes": ("O1 a 0 b lmod", False, "refused"),
    "o-diode-model": ("O1 a 0 b 0 dm", False, "LossyLine 4 dm"),
    "u-upper": ("U1 a b 0 umod L=5", True, "RcLine 3 umod L=5"),
    "u-lower": ("U1 a b 0 umod l=5", True, "RcLine 3 umod l=5"),
    "u-n": ("U1 a b 0 umod L=5 N=6", True, "RcLine 3 umod L=5 N=6"),
    "u-braced": ("U1 a b 0 umod L={len*5}", True, "RcLine 3 umod L=len*5"),
    "u-bare": ("U1 a b 0 umod L=len", True, "RcLine 3 umod L=len"),
    "u-inv": ("U1 inv b 0 umod L=5\nR3 a inv 1m", True, "RcLine 3 umod L=5"),
    "u-no-l": ("U1 a b 0 umod", False, "refused"),
    "u-n-only": ("U1 a b 0 umod N=6", False, "refused"),
    "u-positional": ("U1 a b 0 umod 5", False, "refused"),
    "u-m": ("U1 a b 0 umod L=5 m=2", False, "refused"),
    "u-four-nodes": ("U1 a b 0 c umod L=5", False, "refused"),
    "u-diode-model": ("U1 a b 0 dm L=5", False, "RcLine 3 dm L=5"),
    "u-ltra-model": ("U1 a b 0 lmod L=5", False, "RcLine 3 lmod L=5"),
}


@pytest.mark.parametrize("case", sorted(_PROBES))
def test_line_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    line, ltspice_runs, reading = _PROBES[case]
    text = _text(line)
    assert run(solver, tmp_path, text).ok is ltspice_runs
    assert _reading(text) == reading


def _model_reading(text: str) -> str:
    try:
        netlist = Netlist.from_text(text, dialect=Dialect.LTSPICE)
    except ParseError:
        return "refused"
    item = netlist.lines.find_all(ModelStatement)[-1].item
    assert isinstance(item, ModelStatement)
    return " ".join(flag.name for flag in item.flags) or "no flags"


# LTRA's flags (decision 0019 item 8): LTspice runs three of them, and stops on an unknown word.
@pytest.mark.parametrize(
    ("model", "ltspice_runs"),
    [
        (".model lflag LTRA(L=50n C=20p len=1 nosteplimit lininterp)", True),
        (".model lflag LTRA(L=50n C=20p len=1 steplimit)", True),
        (".model lflag LTRA(L=50n C=20p len=1 foobar)", False),
    ],
)
def test_ltra_flags_are_refused(
    solver: Solver, tmp_path: Path, model: str, ltspice_runs: bool
) -> None:
    text = _text(f"O1 a 0 b 0 lflag\n{model}")
    assert run(solver, tmp_path, text).ok is ltspice_runs
    assert _model_reading(text) == "refused"


def _phase(solver: Solver, folder: Path, source: str | Netlist) -> float:
    (value,) = ac(solver, folder, source)["v(b)"]
    return math.degrees(cmath.phase(value))


@pytest.mark.parametrize(
    ("line", "phase"),
    [
        ("T1 a 0 b 0 Zo=50 Td=1n", -36.0),
        ("T1 a 0 b 0 Zo=50 F=100meg NL=0.1", -36.0),
        ("T1 a 0 b 0 Zo=50 F=100meg", -90.0),
        ("T1 a 0 b 0 Zo=50", -9.0),
        ("T1 a 0 b 0 Zo=50 Td=1n F=100meg NL=0.2", -36.0),
    ],
)
def test_what_ltspice_computes_in_ac(
    solver: Solver, tmp_path: Path, line: str, phase: float
) -> None:
    assert _phase(solver, tmp_path, _text(line, _AC)) == pytest.approx(phase, abs=0.1)


@pytest.mark.parametrize(
    ("line", "result"),
    [
        ("T1 a 0 b 0 Zo=50 Td=1n", 0.5),
        ("T1 a r b 0 Zo=50 Td=1n\nVr r 0 0.2", 0.4),
        ("O1 a 0 b 0 lmodr", 0.4545),
        ("O1 a 0 b 0 lnolen\n.model lnolen LTRA(R=10 L=50n C=20p)", 0.4545),
        ("U1 a b 0 umod L=5", 0.3333),
    ],
)
def test_what_ltspice_computes_in_op(
    solver: Solver, tmp_path: Path, line: str, result: float
) -> None:
    assert op(solver, tmp_path, _text(line))["v(b)"] == pytest.approx(result, abs=2e-4)


def _v(solver: Solver, folder: Path, netlist: Netlist) -> float:
    return op(solver, folder, netlist)["v(b)"]


_EDITS: list[tuple[str, str, Callable[[Netlist], Netlist], float, float]] = [
    ("T1 a 0 b 0 Zo=50 Td=1n", _AC, lambda n: n.set_param("T1", "td", "2n"), -36.0, -72.0),
    ("U1 a b 0 umod L=5", _OP, lambda n: n.set_param("U1", "l", "10"), 1 / 3, 0.25),
    ("O1 a 0 b 0 lmod", _OP, lambda n: n.set_model("O1", "lmodr"), 0.5, 0.4545),
    ("O1 a 0 b 0 lmodr", _OP, lambda n: n.set_model_param("lmodr", "R", "20"), 0.4545, 0.4167),
    ("O1 a 0 b 0 lmodr", _OP, lambda n: n.remove_model_param("lmodr", "R"), 0.4545, 0.5),
    ("U1 a b 0 umod L=5 N=6", _OP, lambda n: n.remove_param("U1", "N"), 1 / 3, 1 / 3),
]


@pytest.mark.parametrize(("line", "analysis", "edit", "before", "after"), _EDITS)
def test_an_edit_moves_the_result(
    solver: Solver,
    tmp_path: Path,
    line: str,
    analysis: str,
    edit: Callable[[Netlist], Netlist],
    before: float,
    after: float,
) -> None:
    netlist = Netlist.from_text(_text(line, analysis), dialect=Dialect.LTSPICE)
    edited = edit(netlist)
    read = _phase if analysis == _AC else _v
    assert read(solver, tmp_path / "before", netlist) == pytest.approx(before, abs=2e-3)
    assert read(solver, tmp_path / "after", edited) == pytest.approx(after, abs=2e-3)
