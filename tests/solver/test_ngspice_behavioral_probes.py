"""ngspice 47 probes for B and the expression forms of E, G and C (M15 T3 to T5, decision 0016).

Each probe pairs what ngspice does with what the library reads, as the probes of the M15 task
list (section 3.1) found. Every circuit drives ``vx`` to 1 V with ``.op``, and has a 1 V source
through a 1k resistor with a 0 V sense source, a 1k load on ``out``, and ``.param k=2``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import (
    BehavioralSource,
    ControlledSource,
    Dialect,
    Netlist,
    ParseError,
    UnsupportedConstruct,
)
from tests.support.ngspice import run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ngspice")

_BASE = (
    "probe\nV1 in 0 2\nR1 in vx 1k\nR2 vx 0 2k\nVs vx2 0 1\nRs vx2 vs 1k\nVsense vs 0 0\n"
    "R3 out 0 1k\n.param k=2\n{line}\n.op\n.end\n"
)


def _reading(text: str) -> str:
    """The library's reading of the line under test, ``refused`` or ``unsupported``."""
    try:
        netlist = Netlist.from_text(text, dialect=Dialect.NGSPICE)
    except UnsupportedConstruct:
        return "unsupported"
    except ParseError:
        return "refused"
    item = netlist.lines.find_all((BehavioralSource, ControlledSource), recursive=True)[-1].item
    if isinstance(item, BehavioralSource):
        return f"B {item.quantity} {item.expression.text}"
    assert isinstance(item, ControlledSource)
    if item.expression is None:
        return "linear"
    return f"{type(item).__name__} {item.form} {item.expression.text}"


# (line, ngspice runs it, the library's reading)
_PROBES = {
    "b-bare": ("B1 out 0 V=2*v(vx)", True, "B v 2*v(vx)"),
    "b-blanks": ("B1 out 0 V = 2 * v(vx)", True, "B v 2 * v(vx)"),
    "b-braces": ("B1 out 0 v={2*v(vx)}", True, "B v 2*v(vx)"),
    "b-quotes": ("B1 out 0 v='2*v(vx)'", True, "B v 2*v(vx)"),
    "b-brace-param": ("B1 out 0 V={k}*v(vx)", True, "B v {k}*v(vx)"),
    "b-bare-param": ("B1 out 0 V=k*v(vx)", True, "B v k*v(vx)"),
    "b-tc1": ("B1 out 0 V = 2 * v(vx) tc1=0", True, "B v 2 * v(vx)"),
    "b-continued": ("B1 out 0 V = 2 *\n+ v(vx)", True, "B v 2 *\n+ v(vx)"),
    "b-current": ("B1 0 out I=2*i(Vsense)", True, "B i 2*i(Vsense)"),
    "b-v-and-i": ("B1 out 0 V=2 I=1m", False, "refused"),
    "b-none": ("B1 out 0", False, "refused"),
    "b-r": ("B1 out 0 R=1k", False, "refused"),
    "b-p": ("B1 out 0 P=4m", False, "refused"),
    # Review R5: a $ right after a bare expression is part of it to ngspice, which stops.
    "b-dollar": ("B1 out 0 V=2*v(vx)$c", False, "B v 2*v(vx)"),
    "b-time": ("B1 out 0 V=2+time", True, "B v 2+time"),
    "b-ternary": ("B1 out 0 V = v(vx) > 0.5 ? 2 : 0", True, "B v v(vx) > 0.5 ? 2 : 0"),
    "b-pwl": ("B1 out 0 V = pwl(v(vx), 0,0, 1,2, 2,4)", True, "B v pwl(v(vx), 0,0, 1,2, 2,4)"),
    # Review R1: reads into an instance of sub (Vq, then a divider to n).
    "b-into-node": (
        ".subckt sub a\nVq a b 0\nR1 b n 1k\nR2 n 0 1k\n.ends\nX1 vx sub\n" + "B1 out 0 V=v(x1.n)",
        True,
        "B v v(x1.n)",
    ),
    "b-into-source": (
        ".subckt sub a\nVq a b 0\nR1 b n 1k\nR2 n 0 1k\n.ends\nX1 vx sub\n"
        + "B1 out 0 V=1k*i(v.x1.vq)",
        True,
        "B v 1k*i(v.x1.vq)",
    ),
    "b-into-source-short": (
        ".subckt sub a\nVq a b 0\nR1 b n 1k\nR2 n 0 1k\n.ends\nX1 vx sub\n"
        + "B1 out 0 V=1k*i(x1.vq)",
        False,
        "B v 1k*i(x1.vq)",
    ),
    # Review R2: `value` after the output nodes is the keyword, to ngspice too.
    "e-value-node": ("Rv value 0 1k\nE1 out 0 value 0 2", False, "refused"),
    "g-value-node": ("Rv value 0 1k\nG1 0 out value 0 1m", False, "refused"),
    "f-value-source": ("value vx vq 0\nRq vq 0 1k\nF1 0 out value 2", True, "linear"),
    "h-value-source": ("value vx vq 0\nRq vq 0 1k\nH1 out 0 value 1k", True, "linear"),
    # Review R4: ngspice joins a braced or quoted expression over a + line; the library refuses.
    "e-value-continued": ("E1 out 0 value={2*\n+ v(vx)}", True, "refused"),
    "e-vol-continued": ("E1 out 0 vol='2*\n+ v(vx)'", True, "refused"),
    "b-quoted-continued": ("B1 out 0 V='2*\n+ v(vx)'", True, "refused"),
    "e-vol-quotes": ("E1 out 0 vol='2*v(vx)'", True, "Vcvs vol 2*v(vx)"),
    "e-vol-braces": ("E1 out 0 vol={2*v(vx)}", True, "Vcvs vol 2*v(vx)"),
    "e-vol-bare": ("E1 out 0 vol=2*v(vx)", False, "refused"),
    "e-value": ("E1 out 0 value={2*v(vx)}", True, "Vcvs value 2*v(vx)"),
    "e-value-no-equals": ("E1 out 0 value {2*v(vx)}", True, "Vcvs value 2*v(vx)"),
    "g-cur-m": ("G1 0 out cur='1m*v(vx)' m=2", True, "Vccs cur 1m*v(vx)"),
    "g-value": ("G1 0 out value={2m*v(vx)}", True, "Vccs value 2m*v(vx)"),
    "e-table": ("E1 out 0 TABLE {v(vx)} = (0,0) (1,2) (2,4)", True, "unsupported"),
    "e-poly": ("E1 out 0 POLY(1) vx 0 0 2", True, "unsupported"),
    "e-freq": ("E1 out 0 FREQ {v(vx)}= DB (1, 0, 0) (1e6, 0, 0)", True, "unsupported"),
    "e-laplace": ("E1 out 0 LAPLACE {v(vx)} {2}", False, "refused"),
}


@pytest.mark.parametrize("case", sorted(_PROBES))
def test_behavioral_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    line, ngspice_runs, reading = _PROBES[case]
    text = _BASE.format(line=line)
    assert run(solver, tmp_path, text).ok is ngspice_runs
    assert _reading(text) == reading


def test_the_charge_form_runs_and_loads(solver: Solver, tmp_path: Path) -> None:
    text = _BASE.format(line="C9 out 0 q='1u*v(out)'")
    assert run(solver, tmp_path, text).ok
    capacitor = Netlist.from_text(text, dialect=Dialect.NGSPICE).element("C9")
    assert getattr(capacitor, "charge").text == "1u*v(out)"


def _out(solver: Solver, folder: Path, netlist: Netlist) -> float:
    result = run(solver, folder, netlist.text)
    assert result.ok, result.log
    return result.voltage("out")


@pytest.mark.parametrize(
    "line", ["B1 out 0 V=2*v(vx)", "E1 out 0 vol='2*v(vx)'", "G1 0 out cur='2m*v(vx)'"]
)
def test_an_edited_expression_moves_the_result(solver: Solver, tmp_path: Path, line: str) -> None:
    # V(vx) = 4/3 V: 2 V over 1k and 2k.
    netlist = Netlist.from_text(_BASE.format(line=line), dialect=Dialect.NGSPICE)
    before = _out(solver, tmp_path / "before", netlist)
    designator = line.split()[0]
    edited = netlist.set_expression(designator, "3*v(vx)" if designator != "G1" else "3m*v(vx)")
    after = _out(solver, tmp_path / "after", edited)
    assert before == pytest.approx(2 * 4 / 3, rel=1e-6)
    assert after == pytest.approx(3 * 4 / 3, rel=1e-6)
