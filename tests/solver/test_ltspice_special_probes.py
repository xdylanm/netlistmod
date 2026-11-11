"""LTspice 26.1.1 probes for the special functions (A), the frequency response analyzer (@) and
its probe (&) (M17 T1, decision 0020 items 3, 7 and 8).

Each probe pairs what LTspice does with what the library reads, as the probes of the M17 task
list (section 3.1) found. Every circuit has ``V1 in 0 1`` and ``Rin in 0 1k``; an A line drives
``q`` (into ``Rq q 0 1k``) from ``in``, and an analyzer sits between ``in`` and ``out`` with
``Rl out 0 1k``. Only syntax facts and results come out of these runs; nothing LTspice writes is
committed (decision 0009 item 2).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from netlistmod import (
    Component,
    Dialect,
    FraProbe,
    FrequencyAnalyzer,
    Netlist,
    ParseError,
    SpecialFunction,
    UnsupportedConstruct,
)
from tests.support.ltspice import op, run
from tests.support.raw import read_raw
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ltspice")

_BASE = "probe\nV1 in 0 1\nRin in 0 1k\nRq q 0 1k\nRl out 0 1k\n{body}\n{analysis}\n.end\n"
_NODES = "in 0 0 0 0 nq q 0"


def _text(body: str, analysis: str = ".op") -> str:
    return _BASE.format(body=body, analysis=analysis)


def _reading(text: str) -> str:
    """The library's reading of the line under test: ``refused``, ``unsupported``, or its class,
    and the function of an A line."""
    try:
        netlist = Netlist.from_text(text, dialect=Dialect.LTSPICE)
    except UnsupportedConstruct:
        return "unsupported"
    except ParseError:
        return "refused"
    found = [
        line.item
        for line in netlist.lines.walk()
        if isinstance(line.item, SpecialFunction | FrequencyAnalyzer | FraProbe)
    ]
    item = found[0]
    assert isinstance(item, Component)
    if isinstance(item, SpecialFunction):
        return f"SpecialFunction {item.function.name}"
    return type(item).__name__


# (body, LTspice runs it, the library's reading)
_FUNCTIONS: dict[str, tuple[str, bool, str]] = {
    **{
        name.lower(): (f"A1 {_NODES} {name}", True, f"SpecialFunction {name}")
        for name in ("BUF", "AND", "OR", "XOR", "SCHMITT", "DFLOP", "SRFLOP", "VARISTOR", "OTA")
    },
    "phasedet": (f"A1 {_NODES} PHASEDET", True, "SpecialFunction PHASEDET"),
    "lower-case": (f"A1 {_NODES} buf", True, "SpecialFunction buf"),
    "counter": (f"A1 {_NODES} COUNTER cycles=4", True, "SpecialFunction COUNTER"),
    "counter-without-cycles": (f"A1 {_NODES} COUNTER", False, "SpecialFunction COUNTER"),
    "modulator": (f"A1 {_NODES} MODULATOR mark=2k space=1k", True, "SpecialFunction MODULATOR"),
    "modulator-without-mark": (f"A1 {_NODES} MODULATOR", False, "SpecialFunction MODULATOR"),
    "samplehold": (
        "V2 clk 0 PULSE(0 1 0 1n 1n 5u 10u)\nA1 in 0 clk 0 0 0 q 0 SAMPLEHOLD",
        True,
        "SpecialFunction SAMPLEHOLD",
    ),
    "samplehold-unclocked": (f"A1 {_NODES} SAMPLEHOLD", False, "SpecialFunction SAMPLEHOLD"),
    **{
        name.lower(): (f"A1 {_NODES} {name}", False, "refused")
        for name in ("INV", "SCHMTBUF", "SCHMTINV", "MODULATE", "PHIDET", "FOO")
    },
    "vhigh": (f"A1 {_NODES} BUF Vhigh=5", True, "SpecialFunction BUF"),
    "vhigh-braced": (f".param vh=5\nA1 {_NODES} BUF Vhigh={{vh}}", True, "SpecialFunction BUF"),
    "vhigh-bare": (f".param x=5\nA1 {_NODES} BUF Vhigh=x", True, "refused"),
    "gate-parameters": (
        f"A1 {_NODES} BUF Vhigh=5 Vlow=0 Trise=1n Tfall=1n Td=1n Rout=1 Cout=1p Ref=0.5",
        True,
        "SpecialFunction BUF",
    ),
    "comma": (f"A1 {_NODES} BUF Vhigh=5, Vlow=0", True, "refused"),
    "comma-after-function": (f"A1 {_NODES} BUF, Vhigh=5", False, "refused"),  # syntax error
    "schmitt-thresholds": (f"A1 {_NODES} SCHMITT Vt=0.5 Vh=0.1", True, "SpecialFunction SCHMITT"),
    "ota-parameters": (
        f"A1 {_NODES} OTA G=1m Iout=1m Isink=-1m Rout=1k",
        True,
        "SpecialFunction OTA",
    ),
    "varistor-rclamp": (f"A1 {_NODES} VARISTOR Rclamp=2", True, "SpecialFunction VARISTOR"),
    "varistor-vrating": (
        f"A1 {_NODES} VARISTOR Rclamp=1 Vrating=5",
        False,
        "SpecialFunction VARISTOR",
    ),
    "unknown-parameter": (f"A1 {_NODES} BUF foo=5", False, "SpecialFunction BUF"),
    "flag": (f"A1 {_NODES} BUF off", False, "refused"),
    "positional": (f"A1 {_NODES} BUF 5", False, "refused"),
    "seven-nodes": ("A1 in 0 0 0 0 q 0 BUF", False, "refused"),
    "nine-nodes": ("A1 in 0 0 0 0 nq q 0 0 BUF", False, "refused"),
    "subcircuit": (
        f"X1 in q s\n.subckt s in q\nA1 {_NODES} BUF\n.ends",
        True,
        "SpecialFunction BUF",
    ),
}


@pytest.mark.parametrize("case", sorted(_FUNCTIONS))
def test_special_function_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    body, ltspice_runs, reading = _FUNCTIONS[case]
    text = _text(body, ".tran 20u" if "PULSE" in body else ".op")
    assert run(solver, tmp_path, text).ok is ltspice_runs
    assert _reading(text) == reading


_ANALYZERS: dict[str, tuple[str, bool, str]] = {
    "plain": ("@1 in out fstart=1k fend=10k", True, "FrequencyAnalyzer"),
    "none": ("@1 in out", True, "FrequencyAnalyzer"),
    "zm": ("@1 in out zm fstart=1k fend=10k", True, "FrequencyAnalyzer"),
    "zm-upper-last": ("@1 in out fstart=1k fend=10k ZM", True, "FrequencyAnalyzer"),
    "zm-twice": ("@1 in out zm zm", True, "refused"),
    "refnode": ("@1 in out refnode=q", True, "FrequencyAnalyzer"),
    "intnode": ("@1 in out intnode=out", True, "FrequencyAnalyzer"),
    "refnode-missing": ("@1 in out refnode=nowhere", False, "FrequencyAnalyzer"),
    "flist": ("@1 in out flist=1k 2k 5k", True, "FrequencyAnalyzer"),
    "flist-commas": ("@1 in out flist=1k,2k,5k", True, "refused"),
    "param-comma": ("@1 in out fstart=1k, fend=10k", True, "refused"),
    "zm-comma": ("@1 in out zm, fstart=1k fend=10k", True, "refused"),
    "pp": ("@1 in out pp=1k 10m 10k 1m", True, "FrequencyAnalyzer"),
    "nmax": ("@1 in out nmax=1k 2 10k 1", True, "FrequencyAnalyzer"),
    "ac-comma": ("@1 in out ac=1,0", True, "FrequencyAnalyzer"),
    "ac-blank": ("@1 in out ac=1 0", True, "FrequencyAnalyzer"),
    "enabled": ("@1 in out enabled=0", True, "FrequencyAnalyzer"),
    "braced": (".param f1=1k\n@1 in out fstart={f1} fend=10k", True, "FrequencyAnalyzer"),
    "bare": (".param f1=1k\n@1 in out fstart=f1 fend=10k", True, "refused"),
    "timing": (
        "@1 in out pp0=1m pp1=1m f0=1k f1=10k tavgmin=1m tsettle=1m delay=1m",
        True,
        "FrequencyAnalyzer",
    ),
    "continued": ("@1 in out fstart=1k\n+ fend=10k", True, "FrequencyAnalyzer"),
    "unknown": ("@1 in out foo=1", False, "refused"),
    "one-node": ("@1 in", False, "refused"),
    "three-nodes": ("@1 in out q", False, "refused"),
    "twice": ("@1 in out\n@1 in out", False, "FrequencyAnalyzer"),
    "subcircuit": ("X1 in out s\n.subckt s in out\n@1 in out\n.ends", True, "FrequencyAnalyzer"),
    "probe": ("@1 in out\n&1 out 0 in 0", True, "FrequencyAnalyzer"),
    "probe-named": ("@A in out\n&a out 0 in 0", True, "FrequencyAnalyzer"),
    "probe-only-analyzer": ("@1 in out\n&2 out 0 in 0", True, "FrequencyAnalyzer"),
    "probe-without-analyzer": ("&1 out 0 in 0", False, "FraProbe"),
    "probe-no-match": ("@1 in out\n@3 in q\n&2 out 0 in 0", False, "FrequencyAnalyzer"),
    "probe-other-scope": (
        "@1 in out\nX1 in out s\n.subckt s a b\n&1 a 0 b 0\n.ends",
        False,
        "FrequencyAnalyzer",
    ),
    "probe-three-nodes": ("@1 in out\n&1 out 0 in", False, "refused"),
    "probe-five-nodes": ("@1 in out\n&1 out 0 in 0 q", False, "refused"),
    "probe-parameter": ("@1 in out\n&1 out 0 in 0 x=1", False, "refused"),
}


@pytest.mark.parametrize("case", sorted(_ANALYZERS))
def test_analyzer_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    body, ltspice_runs, reading = _ANALYZERS[case]
    text = _text(body)
    assert run(solver, tmp_path, text).ok is ltspice_runs
    assert _reading(text) == reading


def test_a_state_machine_stays_unsupported(solver: Solver, tmp_path: Path) -> None:
    text = _text(".machine\n.state s0 0\n.endmachine")
    with pytest.raises(UnsupportedConstruct, match="out of scope for v1"):
        Netlist.from_text(text, dialect=Dialect.LTSPICE)


def test_vhigh_moves_the_output(solver: Solver, tmp_path: Path) -> None:
    # Vhigh=5 puts the threshold at 2.5 V, so 1 V in is low and the inverted output nq is high.
    netlist = Netlist.from_text(_text(f"A1 {_NODES} BUF Vhigh=5"), dialect=Dialect.LTSPICE)
    assert op(solver, tmp_path / "before", netlist)["v(nq)"] == pytest.approx(5, abs=2e-2)
    edited = netlist.set_param("A1", "Vhigh", "3")
    assert op(solver, tmp_path / "after", edited)["v(nq)"] == pytest.approx(3, abs=2e-2)
    removed = netlist.remove_param("A1", "Vhigh")
    assert op(solver, tmp_path / "removed", removed)["v(nq)"] < 0.5


_LOOP = (
    "probe\nV1 a 0 0 AC 1\nR1 a b 1k\nE1 c 0 b 0 -10\nR2 c d 10k\n"
    "@1 d b fstart=1k fend={fend} oct=1 tavgmin=0.5m tsettle=0.2m\n&1 d 0 b 0\nC1 b d 1n\n"
    ".fra\n.end\n"
)


def _frequencies(solver: Solver, folder: Path, source: Netlist) -> list[float]:
    result = run(solver, folder, source)
    assert result.ok, result.log
    (plot,) = read_raw((folder / "probe.fra_1.raw").read_bytes())
    assert plot.name.startswith("Frequency Response")
    return [float(abs(value)) for value in plot.column("frequency")]


@pytest.mark.parametrize(
    ("edit", "highest"),
    [
        (lambda n: n.set_param("@1", "fend", "8k"), 8e3),
        (lambda n: n.set_param("@1", "fstart", "2k"), 4e3),
    ],
)
def test_an_analyzer_edit_moves_its_frequencies(
    solver: Solver, tmp_path: Path, edit: Callable[[Netlist], Netlist], highest: float
) -> None:
    netlist = Netlist.from_text(_LOOP.replace("{fend}", "4k"), dialect=Dialect.LTSPICE)
    before = _frequencies(solver, tmp_path / "before", netlist)
    assert max(before) == pytest.approx(4e3, rel=1e-3)
    after = _frequencies(solver, tmp_path / "after", edit(netlist))
    assert after != before
    assert max(after) == pytest.approx(highest, rel=1e-3)
