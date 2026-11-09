"""LTspice 26.1.1 probes for ``table=``, ``Laplace=``, POLY and B's ``laplace=`` (M15b T1,
decision 0017).

Each probe pairs what LTspice does with what the library reads, as the probes of the M15b task
list (section 3.1) found. Every circuit drives ``vx`` to 4/3 V with ``.op`` (2 V over 1k and 2k),
has a 1 mA sense source ``Vsense``, a 1k load on ``out`` and ``.param k=2``; a table that doubles
``V(vx)`` gives ``V(out)`` 2.667, and ``Laplace=`` gives its DC gain.
"""

from __future__ import annotations

from collections.abc import Callable
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
from tests.support.ltspice import op, run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ltspice")

_BASE = (
    "probe\nV1 in 0 2\nR1 in vx 1k\nR2 vx 0 2k\nVs vx2 0 1\nRs vx2 vs 1k\nVsense vs 0 0\n"
    "R3 out 0 1k\n.param k=2\n{line}\n.op\n.end\n"
)


def _reading(text: str) -> str:
    """The library's reading of the line under test: ``refused``, or its class, form and fields."""
    try:
        netlist = Netlist.from_text(text, dialect=Dialect.LTSPICE)
    except UnsupportedConstruct:
        return "unsupported"
    except ParseError:
        return "refused"
    item = netlist.lines.find_all((ControlledSource, BehavioralSource), recursive=True)[-1].item
    if isinstance(item, BehavioralSource):
        params = " ".join(f"{p.name}={getattr(p.value, 'text', '')}" for p in item.params)
        return f"B {item.quantity} {params}"
    assert isinstance(item, ControlledSource)
    parts = [type(item).__name__, item.form or "linear"]
    if item.expression:
        parts.append("x=" + item.expression.text)
    if item.table:
        table = item.table
        parts.append(f"{table.layout}:{len(table.points)}x{len(table.points[0].values)}")
    if item.dimension is not None:
        parts.append(f"N={item.dimension}")
    if item.coefficients:
        parts.append("c=" + ",".join(value.text for value in item.coefficients))
    control = getattr(item, "control", ())
    if control:
        parts.append("ctl=" + ",".join(source.designator for source in control))
    if item.params:
        parts.append(
            "p=" + ",".join(f"{p.name}={getattr(p.value, 'text', '')}" for p in item.params)
        )
    return " ".join(parts)


# (line, LTspice runs it, the library's reading)
_PROBES = {
    "e-table": ("E1 out 0 vx 0 table=(0,0,2,4)", True, "Vcvs table flat:2x2"),
    "e-table-upper": ("E1 out 0 vx 0 TABLE=(0,0,2,4)", True, "Vcvs table flat:2x2"),
    "e-table-no-commas": ("E1 out 0 vx 0 table=(0 0 2 4)", True, "Vcvs table flat:2x2"),
    "e-table-blanks": ("E1 out 0 vx 0 table = (0, 0, 2, 4)", True, "Vcvs table flat:2x2"),
    "e-table-no-equals": ("E1 out 0 vx 0 table(0,0,2,4)", True, "Vcvs table flat:2x2"),
    "e-table-continued": ("E1 out 0 vx 0 table=(0,0,\n+ 2,4)", True, "Vcvs table flat:2x2"),
    "e-table-formula": ("E1 out 0 vx 0 table=(0,0,2,{2*k})", True, "Vcvs table flat:2x2"),
    "g-table": ("G1 0 out vx 0 table=(0,0,2,4m)", True, "Vccs table flat:2x2"),
    "e-table-pairs": ("E1 out 0 vx 0 table=(0,0) (2,4)", False, "refused"),
    "e-table-nested": ("E1 out 0 vx 0 table=((0,0),(2,4))", False, "refused"),
    "e-table-odd": ("E1 out 0 vx 0 table=(0,0,2)", False, "refused"),
    "e-table-one-point": ("E1 out 0 vx 0 table=(0,3)", False, "refused"),
    "e-table-name": ("E1 out 0 vx 0 table=(0,0,2,k)", False, "refused"),
    "e-table-m": ("E1 out 0 vx 0 table=(0,0,2,4) m=2", False, "refused"),
    "e-table-two-nodes": ("E1 out 0 table=(0,0,2,4)", False, "refused"),
    "e-table-braces": ("E1 out 0 TABLE {V(vx)} = (0,0) (2,4)", True, "refused"),
    "e-laplace": ("E1 out 0 vx 0 Laplace=2/(1+s/1k)", True, "Vcvs laplace x=2/(1+s/1k)"),
    "e-laplace-blanks": (
        "E1 out 0 vx 0 Laplace=2 / (1 + s/1k)",
        True,
        "Vcvs laplace x=2 / (1 + s/1k)",
    ),
    "e-laplace-braced": ("E1 out 0 vx 0 Laplace={2/(1+s/1k)}", True, "Vcvs laplace x=2/(1+s/1k)"),
    "e-laplace-parameter": ("E1 out 0 vx 0 Laplace=k/(1+s/1k)", True, "Vcvs laplace x=k/(1+s/1k)"),
    "e-laplace-params": (
        "E1 out 0 vx 0 Laplace=2/(1+s/1k) window=1m nfft=1024 mtol=1",
        True,
        "Vcvs laplace x=2/(1+s/1k) p=window=1m,nfft=1024,mtol=1",
    ),
    "e-laplace-continued": (
        "E1 out 0 vx 0 Laplace=2/(1+s/1k) window=1m\n+ nfft=1024",
        True,
        "Vcvs laplace x=2/(1+s/1k) p=window=1m,nfft=1024",
    ),
    "e-laplace-window-first": ("E1 out 0 vx 0 window=1m Laplace=2/(1+s/1k)", True, "refused"),
    "g-laplace": ("G1 0 out vx 0 Laplace=2m/(1+s/1k)", True, "Vccs laplace x=2m/(1+s/1k)"),
    "e-laplace-unknown": ("E1 out 0 vx 0 Laplace=2/(1+s/1k) foo=1", False, "refused"),
    "e-laplace-read": ("E1 out 0 vx 0 Laplace=V(vx)/(1+s/1k)", False, "refused"),
    "e-laplace-two-nodes": ("E1 out 0 Laplace=2/(1+s/1k)", False, "refused"),
    "e-window-alone": ("E1 out 0 vx 0 2 window=1m", True, "refused"),
    "b-laplace": (
        "B1 out 0 V=2*V(vx) laplace=1/(1+s/1k) window=1m nfft=1024 mtol=1",
        True,
        "B v laplace=1/(1+s/1k) window=1m nfft=1024 mtol=1",
    ),
    "b-laplace-braced": ("B1 out 0 V=2*V(vx) laplace={1/(1+s/1k)}", True, "B v laplace=1/(1+s/1k)"),
    "b-laplace-current": ("B1 0 out I=2m*V(vx) laplace=1/(1+s/1k)", True, "B i laplace=1/(1+s/1k)"),
    "b-laplace-resistor": ("B1 out 0 R=1k laplace=1/(1+s/1k)", True, "refused"),
    "b-laplace-power": ("B1 out 0 P=1m laplace=1/(1+s/1k)", True, "refused"),
    "b-window-alone": ("B1 out 0 V=2*V(vx) window=1m", True, "refused"),
    "e-poly": ("E1 out 0 POLY(1) vx 0 0 2", True, "Vcvs poly N=1 c=0,2"),
    "e-poly-pair": ("E1 out 0 POLY(1) (vx,0) 0 2", True, "Vcvs poly N=1 c=0,2"),
    "e-poly-pair-blank": ("E1 out 0 POLY(1) (vx 0) 0 2", True, "Vcvs poly N=1 c=0,2"),
    "e-poly-mixed": ("E1 out 0 POLY(2) (vx,0) vx 0 0 1 1", True, "Vcvs poly N=2 c=0,1,1"),
    "e-poly-tight": ("E1 out 0 POLY(2) (vx,0)(vx,0) 0 1 1", True, "Vcvs poly N=2 c=0,1,1"),
    "e-poly-blank": ("E1 out 0 POLY (1) vx 0 0 2", True, "Vcvs poly N=1 c=0,2"),
    "e-poly-braced-dimension": ("E1 out 0 POLY({1}) vx 0 0 2", True, "refused"),
    "e-poly-commas": ("E1 out 0 POLY(1) vx,0 0,2", True, "Vcvs poly N=1 c=0,2"),
    "e-poly-formula": ("E1 out 0 POLY(1) vx 0 0 {k}", True, "Vcvs poly N=1 c=0,k"),
    "e-poly-name": ("E1 out 0 POLY(1) vx 0 0 k", False, "refused"),
    "e-poly-no-coefficient": ("E1 out 0 POLY(1) vx 0", True, "refused"),
    "e-poly-one-coefficient": ("E1 out 0 POLY(1) vx 0 3", True, "Vcvs poly N=1 c=3"),
    "e-poly-too-few": ("E1 out 0 POLY(2) vx 0 0 1", False, "refused"),
    "g-poly": ("G1 0 out POLY(1) vx 0 0 2m", True, "Vccs poly N=1 c=0,2m"),
    "f-poly": (
        "F1 0 out POLY(2) Vsense Vsense 0 1 1",
        True,
        "Cccs poly N=2 c=0,1,1 ctl=Vsense,Vsense",
    ),
    "f-poly-one-coefficient": ("F1 0 out POLY(1) Vsense 2", True, "Cccs poly N=1 c=2 ctl=Vsense"),
    "h-poly": ("H1 out 0 POLY(1) Vsense 0 2k", True, "Ccvs poly N=1 c=0,2k ctl=Vsense"),
    "f-poly-parens": ("F1 0 out POLY(1) (Vsense) 0 2", False, "refused"),
    "e-net-table": ("Rt table 0 1k\nE1 table 0 vx 0 2", True, "Vcvs linear"),
    "e-net-table-control": ("Rt table 0 1k\nE1 out 0 table 0 2", True, "Vcvs linear"),
    "g-net-table": ("Rt table 0 1k\nG1 0 table vx 0 1m", True, "Vccs linear"),
    "e-net-poly": ("Rp poly 0 1k\nE1 poly 0 vx 0 2", True, "Vcvs linear"),
    "e-net-laplace": ("Rp laplace 0 1k\nE1 laplace 0 vx 0 2", True, "Vcvs linear"),
}


@pytest.mark.parametrize("case", sorted(_PROBES))
def test_nonlinear_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    line, ltspice_runs, reading = _PROBES[case]
    text = _BASE.format(line=line)
    assert run(solver, tmp_path, text).ok is ltspice_runs
    assert _reading(text) == reading


# What LTspice computes at V(vx) = 4/3 V (a Laplace= source gives its DC gain).
@pytest.mark.parametrize(
    ("line", "result"),
    [
        ("E1 out 0 vx 0 table=(0,0,2,4)", 8 / 3),
        ("E1 out 0 vx 0 table=(0,0,2,{2*k})", 8 / 3),
        ("G1 0 out vx 0 table=(0,0,2,4m)", 8 / 3),
        ("E1 out 0 vx 0 Laplace=2/(1+s/1k)", 8 / 3),
        ("E1 out 0 vx 0 Laplace={2/(1+s/1k)} window=1m nfft=1024 mtol=1", 8 / 3),
        ("G1 0 out vx 0 Laplace=2m/(1+s/1k)", 8 / 3),
        ("B1 out 0 V=2*V(vx) laplace=1/(1+s/1k)", 8 / 3),
        ("E1 out 0 POLY(1) vx 0 0 2", 8 / 3),
        ("E1 out 0 POLY(1) (vx,0) 0 2", 8 / 3),
        ("E1 out 0 POLY(2) (vx,0)(vx,0) 0 1 1", 8 / 3),
        ("G1 0 out POLY(1) vx 0 0 2m", 8 / 3),
        ("F1 0 out POLY(2) Vsense Vsense 0 1 1", 2.0),
        ("H1 out 0 POLY(1) Vsense 0 2k", 2.0),
        ("E1 out 0 POLY(1) vx 0 3", 3.0),
        ("E1 out 0 POLY(1) vx 0", 4 / 3),
    ],
)
def test_what_ltspice_computes(solver: Solver, tmp_path: Path, line: str, result: float) -> None:
    values = op(solver, tmp_path, _BASE.format(line=line))
    assert values["v(out)"] == pytest.approx(result, rel=1e-4)


_EDITS: list[tuple[str, Callable[[Netlist], Netlist], float, float]] = [
    (
        "E1 out 0 vx 0 table=(0,0,2,4)",
        lambda n: n.set_table("E1", [("0", "0"), ("2", "5")]),
        8 / 3,
        10 / 3,
    ),
    (
        "E1 out 0 vx 0 table=(0,0,2,4)",
        lambda n: n.set_table("E1", [("0", "0"), ("1", "1"), ("2", "5")]),
        8 / 3,
        1 + (5 - 1) * (4 / 3 - 1),
    ),
    (
        "G1 0 out vx 0 table=(0,0,2,4m)",
        lambda n: n.set_table("G1", [("0", "0"), ("2", "5m")]),
        8 / 3,
        10 / 3,
    ),
    (
        "E1 out 0 POLY(1) vx 0 0 2",
        lambda n: n.set_poly_coefficients("E1", ["0", "3"]),
        8 / 3,
        4.0,
    ),
    (
        "E1 out 0 POLY(1) (vx,0) 0 2",
        lambda n: n.set_poly_coefficients("E1", ["1", "2", "3"]),
        8 / 3,
        1 + 2 * (4 / 3) + 3 * (4 / 3) ** 2,
    ),
    (
        "F1 0 out POLY(1) Vsense 0 2",
        lambda n: n.set_poly_coefficients("F1", ["0", "3"]),
        2.0,
        3.0,
    ),
    (
        "E1 out 0 vx 0 Laplace=2/(1+s/1k)",
        lambda n: n.set_expression("E1", "3/(1+s/1k)"),
        8 / 3,
        4.0,
    ),
]


@pytest.mark.parametrize(("line", "edit", "before", "after"), _EDITS)
def test_an_edited_table_coefficient_or_formula_moves_the_result(
    solver: Solver,
    tmp_path: Path,
    line: str,
    edit: Callable[[Netlist], Netlist],
    before: float,
    after: float,
) -> None:
    netlist = Netlist.from_text(_BASE.format(line=line), dialect=Dialect.LTSPICE)
    assert op(solver, tmp_path / "before", netlist)["v(out)"] == pytest.approx(before, rel=1e-4)
    assert op(solver, tmp_path / "after", edit(netlist))["v(out)"] == pytest.approx(after, rel=1e-4)


def test_an_edited_laplace_on_b_runs_and_keeps_the_dc_result(
    solver: Solver, tmp_path: Path
) -> None:
    # laplace= shapes the response over time: the operating point is the expression's, whatever
    # the transfer function, so only that the edit lands and runs is checked here.
    line = "B1 out 0 V=2*V(vx) laplace=1/(1+s/1k)"
    netlist = Netlist.from_text(_BASE.format(line=line), dialect=Dialect.LTSPICE)
    edited = netlist.set_param("B1", "laplace", "2/(1+s/2k)")
    assert "laplace=2/(1+s/2k)" in edited.text
    assert op(solver, tmp_path, edited)["v(out)"] == pytest.approx(8 / 3, rel=1e-4)
