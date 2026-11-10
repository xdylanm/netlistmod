"""ngspice 47 probes for the transmission lines T, O, U, Y and P (M16 T1, decision 0019).

Each probe pairs what ngspice does with what the library reads, as the probes of the M16 task
list (section 3.1) found. Every circuit drives the line from ``V1 in 0 dc 1 ac 1`` through 50 Ω,
from ``a`` to ``b`` with ground references, into a 50 Ω load, with ``.param z=50 td=1n len=1``.
A matched lossless line gives ``v(b)`` 0.5 in ``.op``, and in ``.ac`` at 100 MHz a phase of
−360·f·TD, so −36° for 1 ns; 10 Ω of series resistance gives 0.4545, and a 50 Ω URC line 0.3333.
"""

from __future__ import annotations

import cmath
import math
from collections.abc import Callable
from pathlib import Path

import pytest

from netlistmod import (
    Dialect,
    Netlist,
    ParseError,
    TransmissionLine,
    UnsupportedConstruct,
)
from tests.support.ngspice import ac, op, run, tran_rows
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ngspice")

_MODELS = (
    ".model lmod ltra l=50n c=20p len=1\n.model lmodr ltra r=10 l=50n c=20p len=1\n"
    ".model umod urc rperl=10\n.model ymod txl r=10 l=50n g=0 c=20p length=1\n"
    ".model pmod cpl length=1 r=10 l=50n g=0 c=20p\n.model dm d\n"
)
_BASE = (
    "probe\nV1 in 0 dc 1 ac 1\nR1 in a 50\n{line}\nR2 b 0 50\n.param z=50 td=1n len=1\n"
    + _MODELS
    + "{analysis}\n.end\n"
)
_OP = ".op"
_AC = ".ac lin 1 100meg 100meg"


def _text(line: str, analysis: str = _OP) -> str:
    return _BASE.format(line=line, analysis=analysis)


def _reading(text: str) -> str:
    """The library's reading of the line under test: ``refused``, ``unsupported``, or its class
    and fields."""
    try:
        netlist = Netlist.from_text(text, dialect=Dialect.NGSPICE)
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


# (line, ngspice runs it, the library's reading)
_PROBES = {
    "t-td": ("T1 a 0 b 0 Z0=50 TD=1n", True, "LosslessLine 4 Z0=50 TD=1n"),
    "t-td-units": ("T1 a 0 b 0 Z0=50 TD=1NS", True, "LosslessLine 4 Z0=50 TD=1NS"),
    "t-zo": ("T1 a 0 b 0 ZO=50 TD=1n", True, "LosslessLine 4 ZO=50 TD=1n"),
    "t-td-first": ("T1 a 0 b 0 TD=1n Z0=50", True, "LosslessLine 4 TD=1n Z0=50"),
    "t-braced": ("T1 a 0 b 0 Z0={z} TD={td}", True, "LosslessLine 4 Z0=z TD=td"),
    "t-bare": ("T1 a 0 b 0 Z0=z TD=1n", True, "refused"),
    "t-blanks": ("T1 a 0 b 0 Z0 = 50 TD = 1n", True, "LosslessLine 4 Z0=50 TD=1n"),
    "t-comma": ("T1 a 0 b 0 Z0=50, TD=1n", True, "LosslessLine 4 Z0=50 TD=1n"),
    "t-continued": ("T1 a 0 b 0 Z0=50\n+ TD=1n", True, "LosslessLine 4 Z0=50 TD=1n"),
    "t-f-nl": ("T1 a 0 b 0 Z0=50 F=100meg NL=0.1", True, "LosslessLine 4 Z0=50 F=100meg NL=0.1"),
    "t-nl-f": ("T1 a 0 b 0 Z0=50 NL=0.1 F=100meg", True, "LosslessLine 4 Z0=50 NL=0.1 F=100meg"),
    "t-f": ("T1 a 0 b 0 Z0=50 F=100meg", True, "LosslessLine 4 Z0=50 F=100meg"),
    "t-no-length": ("T1 a 0 b 0 Z0=50", True, "refused"),
    "t-nl-only": ("T1 a 0 b 0 Z0=50 NL=0.1", True, "refused"),
    "t-td-and-f": ("T1 a 0 b 0 Z0=50 TD=1n F=100meg NL=0.2", True, "refused"),
    "t-f-and-td": ("T1 a 0 b 0 Z0=50 F=100meg NL=0.2 TD=1n", True, "refused"),
    "t-no-z0": ("T1 a 0 b 0 TD=1n", False, "refused"),
    "t-three-nodes": ("T1 a 0 b Z0=50 TD=1n", False, "refused"),
    "t-ic": (
        "T1 a 0 b 0 Z0=50 TD=1n IC=0, 0, 0, 0",
        True,
        "LosslessLine 4 Z0=50 TD=1n IC=0, 0, 0, 0",
    ),
    "t-ic-tight": (
        "T1 a 0 b 0 Z0=50 TD=1n IC=0,0,0,0",
        True,
        "LosslessLine 4 Z0=50 TD=1n IC=0,0,0,0",
    ),
    "t-ic-two": ("T1 a 0 b 0 Z0=50 TD=1n IC=0,0", True, "refused"),
    "t-ic-one": ("T1 a 0 b 0 Z0=50 TD=1n IC=1", True, "refused"),
    "t-ic-blanks": ("T1 a 0 b 0 Z0=50 TD=1n IC=0 0 0 0", True, "refused"),
    "t-ic-five": ("T1 a 0 b 0 Z0=50 TD=1n IC=0,0,0,0,0", False, "refused"),
    "t-rel-abs": ("T1 a 0 b 0 Z0=50 TD=1n rel=1 abs=1", True, "refused"),
    "t-foo": ("T1 a 0 b 0 Z0=50 TD=1n foo=1", False, "refused"),
    "t-m": ("T1 a 0 b 0 Z0=50 TD=1n m=2", False, "refused"),
    "t-positional": ("T1 a 0 b 0 50 1n", False, "refused"),
    "t-off": ("T1 a 0 b 0 Z0=50 TD=1n off", False, "refused"),
    "t-z0-twice": ("T1 a 0 b 0 Z0=50 Z0=75 TD=1n", True, "refused"),
    "t-z0-zo": ("T1 a 0 b 0 Z0=50 Zo=75 TD=1n", True, "refused"),
    "o-ltra": ("O1 a 0 b 0 lmod", True, "LossyLine 4 lmod"),
    "o-ltra-r": ("O1 a 0 b 0 lmodr", True, "LossyLine 4 lmodr"),
    "o-len": ("O1 a 0 b 0 lmod len=2", False, "refused"),
    "o-m": ("O1 a 0 b 0 lmod m=2", False, "refused"),
    "o-three-nodes": ("O1 a 0 b lmod", False, "refused"),
    "o-no-model": ("O1 a 0 b 0", False, "refused"),
    "o-diode-model": ("O1 a 0 b 0 dm", False, "LossyLine 4 dm"),
    "o-txl-model": ("O1 a 0 b 0 ymod", False, "LossyLine 4 ymod"),
    "o-undefined-model": ("O1 a 0 b 0 nomod", False, "LossyLine 4 nomod"),
    "u-l": ("U1 a b 0 umod l=5", True, "RcLine 3 umod l=5"),
    "u-upper-l": ("U1 a b 0 umod L=5", True, "RcLine 3 umod L=5"),
    "u-n-after": ("U1 a b 0 umod l=5 n=6", True, "RcLine 3 umod l=5 n=6"),
    "u-n-before": ("U1 a b 0 umod n=6 l=5", True, "RcLine 3 umod n=6 l=5"),
    "u-n-fraction": ("U1 a b 0 umod l=5 n=6.5", True, "RcLine 3 umod l=5 n=6.5"),
    "u-braced": ("U1 a b 0 umod l={len*5}", True, "RcLine 3 umod l=len*5"),
    "u-blanks": ("U1 a b 0 umod l = 5", True, "RcLine 3 umod l=5"),
    "u-inv": ("U1 inv b 0 umod l=5\nR3 a inv 1m", True, "RcLine 3 umod l=5"),
    "u-no-l": ("U1 a b 0 umod", True, "refused"),
    "u-n-only": ("U1 a b 0 umod n=6", True, "refused"),
    "u-positional": ("U1 a b 0 umod 5", True, "refused"),
    "u-m": ("U1 a b 0 umod l=5 m=2", False, "refused"),
    "u-off": ("U1 a b 0 umod off", False, "refused"),
    "u-two-nodes": ("U1 a b umod l=5", False, "unsupported"),
    "u-four-nodes": ("U1 a b 0 c umod l=5", False, "unsupported"),
    "u-diode-model": ("U1 a b 0 dm l=5", False, "RcLine 3 dm l=5"),
    "u-ltra-model": ("U1 a b 0 lmod l=5", False, "RcLine 3 lmod l=5"),
    "u-model-5": ("U1 a b 0 5 l=5", False, "refused"),
    "u-digital": ("U1 inv p n a b d0 dmio", False, "unsupported"),
    "y-len": ("Y1 a 0 b 0 ymod len=1", True, "TxlLine 4 ymod len=1"),
    "y-upper-len": ("Y1 a 0 b 0 ymod LEN=1", True, "TxlLine 4 ymod LEN=1"),
    "y-model-length": ("Y1 a 0 b 0 ymod", True, "TxlLine 4 ymod"),
    "y-braced": ("Y1 a 0 b 0 ymod len={len}", True, "TxlLine 4 ymod len=len"),
    "y-len-2": ("Y1 a 0 b 0 ymod len=2", True, "TxlLine 4 ymod len=2"),
    "y-m": ("Y1 a 0 b 0 ymod m=2", True, "refused"),
    "y-positional": ("Y1 a 0 b 0 ymod 2", True, "refused"),
    "y-reference": ("Y1 a r b 0 ymod\nVr r 0 0.2", True, "refused"),
    "y-three-nodes": ("Y1 a 0 b ymod", False, "refused"),
    "y-ltra-model": ("Y1 a 0 b 0 lmod", False, "TxlLine 4 lmod"),
    "p-one": ("P1 a 0 b 0 pmod", True, "CoupledLine 4 pmod"),
    "p-len": ("P1 a 0 b 0 pmod len=2", True, "CoupledLine 4 pmod len=2"),
    "p-gnd": ("P1 a gnd b GND pmod", True, "CoupledLine 4 pmod"),
    "p-m": ("P1 a 0 b 0 pmod m=2", False, "refused"),
    "p-reference": ("P1 a r b 0 pmod\nVr r 0 0.2", True, "refused"),
    "p-odd": ("P1 a 0 b pmod", False, "refused"),
    "p-positional": ("P1 a 0 b 0 pmod 2", False, "refused"),
    "p-txl-model": ("P1 a 0 b 0 ymod", False, "CoupledLine 4 ymod"),
}


@pytest.mark.parametrize("case", sorted(_PROBES))
def test_line_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    line, ngspice_runs, reading = _PROBES[case]
    text = _text(line)
    assert run(solver, tmp_path, text).ok is ngspice_runs
    assert _reading(text) == reading


def _phase(solver: Solver, folder: Path, source: str | Netlist) -> float:
    (value,) = ac(solver, folder, source)["v(b)"]
    return math.degrees(cmath.phase(value))


# What ngspice computes: the forms it reads as the manual says, then the ones it runs with a
# reading the library refuses (decision 0019 items 2 and 4).
@pytest.mark.parametrize(
    ("line", "phase"),
    [
        ("T1 a 0 b 0 Z0=50 TD=1n", -36.0),
        ("T1 a 0 b 0 Z0=50 F=100meg NL=0.1", -36.0),
        ("T1 a 0 b 0 Z0=50 F=100meg", -90.0),
        ("T1 a 0 b 0 Z0=50", -9.0),
        ("T1 a 0 b 0 Z0=50 NL=0.1", -3.6),
        ("T1 a 0 b 0 Z0=50 TD=1n F=100meg NL=0.2", -36.0),
        ("O1 a 0 b 0 lmod", -36.0),
    ],
)
def test_what_ngspice_computes_in_ac(
    solver: Solver, tmp_path: Path, line: str, phase: float
) -> None:
    assert _phase(solver, tmp_path, _text(line, _AC)) == pytest.approx(phase, abs=0.1)


@pytest.mark.parametrize(
    ("line", "result"),
    [
        ("T1 a 0 b 0 Z0=50 TD=1n", 0.5),
        ("T1 a r b 0 Z0=50 TD=1n\nVr r 0 0.2", 0.4),
        ("O1 a 0 b 0 lmodr", 0.4545),
        ("U1 a b 0 umod l=5", 0.3333),
        ("U1 a b 0 umod", 0.4995),
        ("U1 a b 0 umod 5", 0.4995),
        ("Y1 a 0 b 0 ymod len=1", 0.4545),
        ("Y1 a 0 b 0 ymod len=2", 0.4167),
        ("Y1 a 0 b 0 ymod m=2", 0.4545),
        ("Y1 a r b 0 ymod\nVr r 0 0.2", 0.4545),
        ("Y1 a 0 b r ymod\nVr r 0 0.2", 0.4545),
        ("P1 a 0 b 0 pmod", 0.4545),
        ("P1 a r b 0 pmod\nVr r 0 0.2", 0.4545),
    ],
)
def test_what_ngspice_computes_in_op(
    solver: Solver, tmp_path: Path, line: str, result: float
) -> None:
    assert op(solver, tmp_path, _text(line))["v(b)"] == pytest.approx(result, abs=2e-4)


def _cpl(lines: int) -> str:
    def matrix(diagonal: str, other: str) -> str:
        return " ".join(
            diagonal if i == j else other for i in range(lines) for j in range(i, lines)
        )

    rows = ["probe"]
    for i in range(lines):
        rows += [f"V{i} in{i} 0 dc 1", f"R{i} in{i} a{i} 50", f"RL{i} b{i} 0 50"]
    ins = " ".join(f"a{i}" for i in range(lines))
    outs = " ".join(f"b{i}" for i in range(lines))
    rows += [
        f"P1 {ins} 0 {outs} 0 pmod len=1",
        ".model pmod CPL length=1",
        "+R=" + matrix("10", "0"),
        "+L=" + matrix("50n", "5n"),
        "+G=" + matrix("0", "0"),
        "+C=" + matrix("20p", "-1p"),
        ".tran 0.1n 10n",
        ".end",
    ]
    return "\n".join(rows) + "\n"


def test_p_holds_up_to_eight_lines(solver: Solver, tmp_path: Path) -> None:
    # Decision 0019 item 6 (T1): eight lines run; ngspice 47 crashes on nine (0xC0000409), with
    # a valid, diagonally dominant matrix. The manual's limit of eight stands.
    assert run(solver, tmp_path / "eight", _cpl(8)).ok
    nine = run(solver, tmp_path / "nine", _cpl(9))
    assert not nine.ok
    Netlist.from_text(_cpl(8), dialect=Dialect.NGSPICE)
    with pytest.raises(ParseError, match="has 20 nodes"):
        Netlist.from_text(_cpl(9), dialect=Dialect.NGSPICE)


_LTRA_TRAN = (
    "probe\nV1 in 0 pulse(0 1 0 0.1n 0.1n 5n 40n)\nR1 in a 10\nO1 a 0 b 0 lmod\nR2 b 0 1k\n"
    ".model lmod ltra r=1 l=50n c=20p len=10 {flags}\n.tran 1n 200n\n.end\n"
)


def _waveform(solver: Solver, folder: Path, flags: str) -> list[float]:
    return [row["v(b)"] for row in tran_rows(solver, folder, _LTRA_TRAN.format(flags=flags))]


# Decision 0019 item 8 (T1): ngspice ignores an unknown word in a .model, so only a result a
# flag changes shows that ngspice reads it. lininterp and mixedinterp change this run; the
# others give the same waveform here, so no probe of this circuit decides them, and they load
# as the manual lists them.
@pytest.mark.parametrize(
    ("flags", "changes"),
    [
        ("nosteplimit", False),
        ("steplimit", False),
        ("nocontrol", False),
        ("lininterp", True),
        ("mixedinterp", True),
        ("truncnr", False),
        ("truncdontcut", False),
        ("foobar", False),
    ],
)
def test_which_ltra_flags_change_a_run(
    solver: Solver, tmp_path: Path, flags: str, changes: bool
) -> None:
    plain = _waveform(solver, tmp_path / "plain", "")
    flagged = _waveform(solver, tmp_path / "flagged", flags)
    assert (flagged != plain) is changes
    try:
        Netlist.from_text(_LTRA_TRAN.format(flags=flags), dialect=Dialect.NGSPICE)
        loads = True
    except ParseError:
        loads = False
    assert loads is (flags != "foobar")


def test_a_tran_shows_td_and_len_move_the_waveform(solver: Solver, tmp_path: Path) -> None:
    pulse = "V1 in 0 dc 1 ac 1"
    tran = ".tran 0.05n 6n"
    step = pulse.replace("dc 1 ac 1", "pulse(0 1 0 0.1n 0.1n 10n 20n)")

    def first_rise(line: str, folder: str) -> float:
        rows = tran_rows(solver, tmp_path / folder, _text(line, tran).replace(pulse, step))
        return next(row["time"] for row in rows if row["v(b)"] > 0.2)

    assert first_rise("T1 a 0 b 0 Z0=50 TD=1n", "td1") == pytest.approx(1.05e-9, abs=0.1e-9)
    assert first_rise("T1 a 0 b 0 Z0=50 TD=2n", "td2") == pytest.approx(2.05e-9, abs=0.1e-9)
    assert first_rise("Y1 a 0 b 0 ymod len=2", "len2") > first_rise("Y1 a 0 b 0 ymod", "len1")


def _v(solver: Solver, folder: Path, netlist: Netlist) -> float:
    return op(solver, folder, netlist)["v(b)"]


# The exit: an edited TD=, l=, len=, model name and model parameter move the result, and so do
# a removed parameter and a removed model parameter (decision 0019 item 11).
_EDITS: list[tuple[str, str, Callable[[Netlist], Netlist], float, float]] = [
    ("T1 a 0 b 0 Z0=50 TD=1n", _AC, lambda n: n.set_param("T1", "td", "2n"), -36.0, -72.0),
    ("T1 a 0 b 0 Zo=50 TD=1n", _OP, lambda n: n.set_param("T1", "z0", "75"), 0.5, 0.5),
    ("U1 a b 0 umod l=5", _OP, lambda n: n.set_param("U1", "l", "10"), 1 / 3, 0.25),
    ("Y1 a 0 b 0 ymod len=1", _OP, lambda n: n.set_param("Y1", "len", "2"), 0.4545, 0.4167),
    ("Y1 a 0 b 0 ymod len=2", _OP, lambda n: n.remove_param("Y1", "len"), 0.4167, 0.4545),
    ("P1 a 0 b 0 pmod", _OP, lambda n: n.set_param("P1", "len", "2"), 0.4545, 0.4167),
    ("O1 a 0 b 0 lmod", _OP, lambda n: n.set_model("O1", "lmodr"), 0.5, 0.4545),
    ("O1 a 0 b 0 lmodr", _OP, lambda n: n.set_model_param("lmodr", "r", "20"), 0.4545, 0.4167),
    ("O1 a 0 b 0 lmodr", _OP, lambda n: n.remove_model_param("lmodr", "r"), 0.4545, 0.5),
    ("U1 a b 0 umod l=5", _OP, lambda n: n.set_model_param("umod", "rperl", "20"), 1 / 3, 0.25),
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
    netlist = Netlist.from_text(_text(line, analysis), dialect=Dialect.NGSPICE)
    edited = edit(netlist)
    read = _phase if analysis == _AC else _v
    assert read(solver, tmp_path / "before", netlist) == pytest.approx(before, abs=2e-3)
    assert read(solver, tmp_path / "after", edited) == pytest.approx(after, abs=2e-3)


def test_an_edited_impedance_moves_a_mismatched_line(solver: Solver, tmp_path: Path) -> None:
    # A matched line reads 0.5 at DC whatever Z0 is; at 100 MHz a mismatch shows in the phase.
    netlist = Netlist.from_text(_text("T1 a 0 b 0 Zo=50 TD=1n", _AC), dialect=Dialect.NGSPICE)
    edited = netlist.set_param("T1", "z0", "75")
    assert "Zo=75" in edited.source.text
    assert _phase(solver, tmp_path / "before", netlist) != pytest.approx(
        _phase(solver, tmp_path / "after", edited), abs=0.5
    )
