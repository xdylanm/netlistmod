"""LTspice 26.1.1 probes for B, ``value=`` on E to H, and C's and L's forms (M15 T3 to T5, 0016).

Each probe pairs what LTspice does with what the library reads, as the probes of the M15 task
list (section 3.1) found. Every circuit drives ``vx`` to 4/3 V with ``.op``, and has a 1 V source
through a 1k resistor with a 0 V sense source, a 1k load on ``out``, and ``.param k=2``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import (
    BehavioralSource,
    Capacitor,
    ControlledSource,
    Dialect,
    Inductor,
    Netlist,
    ParseError,
    UnsupportedConstruct,
)
from tests.support.ltspice import run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ltspice")

_BASE = (
    "probe\nV1 in 0 2\nR1 in vx 1k\nR2 vx 0 2k\nVs vx2 0 1\nRs vx2 vs 1k\nVsense vs 0 0\n"
    "R3 out 0 1k\n.param k=2\n{line}\n.op\n.end\n"
)


def _reading(text: str) -> str:
    """The library's reading of the line under test, ``refused`` or ``unsupported``."""
    try:
        netlist = Netlist.from_text(text, dialect=Dialect.LTSPICE)
    except UnsupportedConstruct:
        return "unsupported"
    except ParseError:
        return "refused"
    kinds = (BehavioralSource, ControlledSource, Capacitor, Inductor)
    item = netlist.lines.find_all(kinds, recursive=True)[-1].item
    if isinstance(item, BehavioralSource):
        return f"B {item.quantity} {item.expression.text}"
    if isinstance(item, Capacitor):
        assert item.charge is not None
        return f"C Q {item.charge.text}"
    if isinstance(item, Inductor):
        flux = item.flux.text if item.flux is not None else "-"
        return f"L {flux} {','.join(param.name for param in item.params)}"
    assert isinstance(item, ControlledSource) and item.expression is not None
    return f"{type(item).__name__} {item.form} {item.expression.text}"


# (line, LTspice runs it, the library's reading)
_PROBES = {
    "b-bare": ("B1 out 0 V=2*V(vx)", True, "B v 2*V(vx)"),
    "b-blanks": ("B1 out 0 V = 2 * V(vx)", True, "B v 2 * V(vx)"),
    "b-braces": ("B1 out 0 V={2*V(vx)}", True, "B v 2*V(vx)"),
    "b-brace-param": ("B1 out 0 V={k}*V(vx)", True, "B v {k}*V(vx)"),
    "b-bare-param": ("B1 out 0 V=k*V(vx)", True, "B v k*V(vx)"),
    "b-continued": ("B1 out 0 V = 2 *\n+ V(vx)", True, "B v 2 *\n+ V(vx)"),
    "b-current": ("B1 0 out I=2*I(Vsense)", True, "B i 2*I(Vsense)"),
    "b-resistor": ("B1 out vx R=1k+V(vx)", True, "B r 1k+V(vx)"),
    "b-power": ("B1 out 0 P=4m vprx=1", True, "B p 4m"),
    "b-params": ("B1 out 0 V=2*V(vx) ic=0 tripdv=1m tripdt=1n", True, "B v 2*V(vx)"),
    "b-rpar": ("B1 0 out I=2m*V(vx) Rpar=1Meg", True, "B i 2m*V(vx)"),
    "b-r-rpar": ("B1 out vx R=1k Rpar=1Meg", True, "B r 1k"),
    "b-v-rpar": ("B1 out 0 V=2*V(vx) Rpar=1Meg", False, "refused"),
    "b-p-rpar": ("B1 out 0 P=4m Rpar=1Meg", False, "refused"),
    "b-v-vprx": ("B1 out 0 V=2*V(vx) vprx=1", True, "B v 2*V(vx)"),
    "b-time": ("B1 out 0 V=2+time", True, "B v 2+time"),
    "b-v-and-i": ("B1 out 0 V=2 I=1m", False, "refused"),
    "b-none": ("B1 out 0", False, "refused"),
    "b-tc1": ("B1 out 0 V=2*V(vx) tc1=0", False, "refused"),
    # Review R1: a read of a node inside an instance of sub.
    "b-into-node": (
        ".subckt sub a\nVq a b 0\nR1 b n 1k\nR2 n 0 1k\n.ends\nX1 vx sub\n" + "B1 out 0 V=V(X1:n)",
        True,
        "B v V(X1:n)",
    ),
    # Review R2: LTspice reads `value` there as the keyword, on all four letters.
    "e-value-node": ("Rv value 0 1k\nE1 out 0 value 0 2", False, "refused"),
    "g-value-node": ("Rv value 0 1k\nG1 0 out value 0 1m", False, "refused"),
    "f-value-source": ("value vx vq 0\nRq vq 0 1k\nF1 0 out value 2", True, "refused"),
    "h-value-source": ("value vx vq 0\nRq vq 0 1k\nH1 out 0 value 1k", True, "refused"),
    "e-value": ("E1 out 0 value={2*V(vx)}", True, "Vcvs value 2*V(vx)"),
    "e-value-bare": ("E1 out 0 value=2*V(vx)", True, "Vcvs value 2*V(vx)"),
    "g-value": ("G1 0 out value={2m*V(vx)}", True, "Vccs value 2m*V(vx)"),
    "f-value": ("F1 0 out value={2*I(Vsense)}", True, "Cccs value 2*I(Vsense)"),
    "h-value": ("H1 out 0 value={1k*I(Vsense)}", True, "Ccvs value 1k*I(Vsense)"),
    "e-vol": ("E1 out 0 vol='2*V(vx)'", False, "refused"),
    "e-table-braces": ("E1 out 0 TABLE {V(vx)} = (0,0) (1,2) (2,4)", True, "refused"),
    "c-charge": ("C9 out 0 Q=1u*x ic=0 m=2", True, "C Q 1u*x"),
    "c-charge-braces": ("C9 out 0 Q={1u*x}", True, "C Q 1u*x"),
    "l-flux": ("L9 out n9 Flux=1m*tanh(5*x)\nR9 n9 0 1k", True, "L 1m*tanh(5*x) "),
    # Review R5: LTspice runs Rser= on the Flux= and hysteretic forms; the reference shows none.
    "l-flux-rser": ("L9 out n9 Flux=1m*tanh(5*x) Rser=1\nR9 n9 0 1k", True, "refused"),
    "l-hysteretic-rser": (
        "L9 out n9 Hc=16 Bs=.44 Br=.10 A=0.0000251 Lm=0.0198 Lg=0.0006858 N=1000 Rser=1\n"
        "R9 n9 0 1k",
        True,
        "refused",
    ),
    "l-hysteretic": (
        "L9 out n9 Hc=16 Bs=.44 Br=.10 A=0.0000251 Lm=0.0198 Lg=0.0006858 N=1000\nR9 n9 0 1k",
        True,
        "L - Hc,Bs,Br,A,Lm,Lg,N",
    ),
}


@pytest.mark.parametrize("case", sorted(_PROBES))
def test_behavioral_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    line, ltspice_runs, reading = _PROBES[case]
    text = _BASE.format(line=line)
    assert run(solver, tmp_path, text).ok is ltspice_runs
    assert _reading(text) == reading


@pytest.mark.parametrize(
    ("expression", "reads", "references"),
    [("~0", 1.0, 0), ("~1", 0.0, 0), ("2*(~0)+1", 3.0, 0), ("~(1>2)", 1.0, 0), ("~(k>3)", 1.0, 1)],
)
def test_the_tilde_is_a_logical_not(
    solver: Solver, tmp_path: Path, expression: str, reads: float, references: int
) -> None:
    # LT-FML-001: `~` is LTspice's logical NOT (reference B, Supported Operators); `.param k=2`.
    text = _BASE.format(line=f"B1 out 0 V={expression}")
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert result.voltage("out") == pytest.approx(reads, abs=1e-9)
    netlist = Netlist.from_text(text, dialect=Dialect.LTSPICE)
    assert _reading(text) == f"B v {expression}"
    assert len(netlist.references_to_param("k")) == references


def _out(solver: Solver, folder: Path, netlist: Netlist) -> float:
    result = run(solver, folder, netlist.text)
    assert result.ok, result.log
    return result.voltage("out")


@pytest.mark.parametrize(
    "line",
    ["B1 out 0 V=2*V(vx)", "E1 out 0 value={2*V(vx)}", "G1 0 out value={2m*V(vx)}"],
)
def test_an_edited_expression_moves_the_result(solver: Solver, tmp_path: Path, line: str) -> None:
    # V(vx) = 4/3 V: 2 V over 1k and 2k.
    netlist = Netlist.from_text(_BASE.format(line=line), dialect=Dialect.LTSPICE)
    before = _out(solver, tmp_path / "before", netlist)
    designator = line.split()[0]
    edited = netlist.set_expression(designator, "3*V(vx)" if designator != "G1" else "3m*V(vx)")
    after = _out(solver, tmp_path / "after", edited)
    assert before == pytest.approx(2 * 4 / 3, rel=1e-6)
    assert after == pytest.approx(3 * 4 / 3, rel=1e-6)
