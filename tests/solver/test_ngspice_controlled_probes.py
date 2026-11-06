"""ngspice 47 probes for E, F, G, H, S and W (M14 T3 to T6, decision 0015).

Each probe pairs what ngspice does with what the library reads, as the probes of the M14 task
list (section 3.1) found. Every circuit is a 2 V divider with ``.op``, a 0 V sense source ``Vs``
and a 1k load on ``out``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import (
    ControlledSource,
    Dialect,
    Netlist,
    ParseError,
    Switch,
    UnsupportedConstruct,
)
from tests.support.ngspice import run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ngspice")

_BASE = (
    "probe\nV1 in 0 2\nR1 in vx 1k\nR2 vx 0 1k\nR3 out 0 1k\nVs vx vs 0\nR4 vs 0 1k\n"
    "{line}\n.op\n.end\n"
)
_SW = ".model sm SW vt=0.5 ron=1 roff=1Meg\n"
_SWH = ".model sm SW vt=1.5 vh=1 ron=1 roff=1Meg\n"
_CW = ".model cm CSW it=0.5m ron=1 roff=1Meg\n"


def _reading(text: str) -> str:
    """``type nodes control value`` of the library's reading, ``refused`` or ``unsupported``."""
    try:
        netlist = Netlist.from_text(text, dialect=Dialect.NGSPICE)
    except UnsupportedConstruct:
        return "unsupported"
    except ParseError:
        return "refused"
    # The last one is the line under test; the others feed it.
    item = netlist.lines.find_all((ControlledSource, Switch), recursive=True)[-1].item
    assert isinstance(item, ControlledSource | Switch)
    control = getattr(item, "control", None)
    parts = [type(item).__name__, ",".join(node.name for node in item.nodes)]
    parts.append(control.designator if control is not None else "-")
    parts.append(item.value.text if isinstance(item, ControlledSource) else item.model.model_name)
    return " ".join(parts)


# (line, ngspice runs it, the library's reading)
_PROBES = {
    "e-gain": ("E1 out 0 vx 0 2", True, "Vcvs out,0,vx,0 - 2"),
    "e-formula": (".param k=2\nE1 out 0 vx 0 {k}", True, "Vcvs out,0,vx,0 - k"),
    "e-quote": ("E1 out 0 vx 0 '2*1'", True, "Vcvs out,0,vx,0 - 2*1"),
    "e-gain-keyword": ("E1 out 0 vx 0 gain=2", True, "refused"),
    "e-no-value": ("E1 out 0 vx 0", False, "refused"),
    "e-two-values": ("E1 out 0 vx 0 2 3", True, "refused"),
    "e-word": ("E1 out 0 vx 0 E", False, "refused"),
    "e-m": ("E1 out 0 vx 0 2 m=2", False, "refused"),
    "e-three-nodes": ("E1 out 0 vx 2", False, "refused"),
    "e-comma": ("E1 out,0 vx 0 2", True, "Vcvs out,0,vx,0 - 2"),
    "e-value": ("E1 out 0 value={2*V(vx)}", True, "unsupported"),
    "e-poly": ("E1 out 0 POLY(1) vx 0 0 2", True, "unsupported"),
    "e-laplace": ("E1 out 0 vx 0 Laplace=2", False, "refused"),
    "g-gain": ("G1 0 out vx 0 2m", True, "Vccs 0,out,vx,0 - 2m"),
    "g-m": ("G1 0 out vx 0 2m m=2", True, "Vccs 0,out,vx,0 - 2m"),
    "f-gain": ("F1 0 out Vs 2", True, "Cccs 0,out Vs 2"),
    "f-m": ("F1 0 out Vs 2 m=2", True, "Cccs 0,out Vs 2"),
    "f-case": ("F1 0 out vs 2", True, "Cccs 0,out vs 2"),
    "f-comma": ("F1 0,out Vs 2", True, "Cccs 0,out Vs 2"),
    "f-later": ("F1 0 out Vz 2\nVz vs vz2 0\nR5 vz2 0 1k", True, "Cccs 0,out Vz 2"),
    "f-ctrl-e": ("E9 n9 0 vx 0 1\nR9 n9 0 1k\nF1 0 out E9 2", True, "Cccs 0,out E9 2"),
    "f-ctrl-h": ("H9 n9 0 Vs 1k\nR9 n9 0 1k\nF1 0 out H9 2", True, "Cccs 0,out H9 2"),
    "f-ctrl-r": ("F1 0 out R4 2", False, "Cccs 0,out R4 2"),
    "f-ctrl-l": ("L9 vs n9 1u\nR9 n9 0 1k\nF1 0 out L9 2", False, "Cccs 0,out L9 2"),
    "f-ctrl-missing": ("F1 0 out Vnope 2", False, "Cccs 0,out Vnope 2"),
    "f-top-v-from-body": (".subckt sub o\nFq 0 o Vs 2\n.ends\nX1 out sub", False, "Cccs 0,o Vs 2"),
    "h-gain": ("H1 out 0 Vs 1k", True, "Ccvs out,0 Vs 1k"),
    "h-m": ("H1 out 0 Vs 1k m=2", False, "refused"),
    "s-off": (_SW + "S1 out in vx 0 sm off", True, "VoltageSwitch out,in,vx,0 - sm"),
    "s-on-upper": (_SW + "S1 out in vx 0 sm ON", True, "VoltageSwitch out,in,vx,0 - sm"),
    "s-none": (_SW + "S1 out in vx 0 sm", True, "VoltageSwitch out,in,vx,0 - sm"),
    "s-on-off": (_SW + "S1 out in vx 0 sm on off", True, "refused"),
    "s-off-value": (_SW + "S1 out in vx 0 sm off=1", False, "refused"),
    "s-m": (_SW + "S1 out in vx 0 sm m=2", False, "refused"),
    "s-no-model": ("S1 out in vx 0", False, "refused"),
    "s-model-named-off": (
        ".model off SW vt=0.5\nS1 out in vx 0 off",
        True,
        "VoltageSwitch out,in,vx,0 - off",
    ),
    "w-off": (_CW + "W1 out in Vs cm off", True, "CurrentSwitch out,in Vs cm"),
    "w-none": (_CW + "W1 out in Vs cm", True, "CurrentSwitch out,in Vs cm"),
    "w-ctrl-r": (_CW + "W1 out in R4 cm", False, "CurrentSwitch out,in R4 cm"),
}


@pytest.mark.parametrize("case", sorted(_PROBES))
def test_controlled_source_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    line, ngspice_runs, reading = _PROBES[case]
    text = _BASE.format(line=line)
    assert run(solver, tmp_path, text).ok is ngspice_runs
    assert _reading(text) == reading


def _out(solver: Solver, folder: Path, line: str) -> float:
    result = run(solver, folder, _BASE.format(line=line))
    assert result.ok, result.log
    return result.voltage("out")


def test_each_gain_takes_effect(solver: Solver, tmp_path: Path) -> None:
    # V(vx) = 2/3 V (R2 and the sense branch in parallel), and Vs carries 2/3 mA.
    assert _out(solver, tmp_path / "e", "E1 out 0 vx 0 3") == pytest.approx(2.0, rel=1e-6)
    assert _out(solver, tmp_path / "g", "G1 0 out vx 0 3m") == pytest.approx(2.0, rel=1e-6)
    assert _out(solver, tmp_path / "f", "F1 0 out Vs 3") == pytest.approx(2.0, rel=1e-6)
    assert _out(solver, tmp_path / "h", "H1 out 0 Vs 1.5k") == pytest.approx(1.0, rel=1e-6)


@pytest.mark.parametrize("line", ["G1 0 out vx 0 1.5m m=2", "F1 0 out Vs 1.5 m=2"])
def test_m_doubles_the_output(solver: Solver, tmp_path: Path, line: str) -> None:
    assert _out(solver, tmp_path, line) == pytest.approx(2.0, rel=1e-6)


def test_the_state_sets_a_switch_inside_its_hysteresis(solver: Solver, tmp_path: Path) -> None:
    on = _out(solver, tmp_path / "on", _SWH + "S1 out in vx 0 sm on")
    off = _out(solver, tmp_path / "off", _SWH + "S1 out in vx 0 sm off")
    assert on == pytest.approx(2 * 1000 / 1001, rel=1e-3)
    assert off == pytest.approx(2 * 1000 / 1_001_000, rel=1e-2)
