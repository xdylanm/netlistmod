"""ngspice 47 probes for TABLE, POLY, FREQ and the gates (M15b T1, decision 0017).

Each probe pairs what ngspice does with what the library reads, as the probes of the M15b task
list (section 3.1) found. Every circuit drives ``vx`` to 4/3 V with ``.op`` (2 V over 1k and 2k),
has a 1 mA sense source ``Vsense``, a 1k load on ``out`` and ``.param k=2``; a table that doubles
``v(vx)`` gives ``v(out)`` 2.667.
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
from tests.support.ngspice import ac, op, run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ngspice")

_BASE = (
    "probe\nV1 in 0 2\nR1 in vx 1k\nR2 vx 0 2k\nVs vx2 0 1\nRs vx2 vs 1k\nVsense vs 0 0\n"
    "R3 out 0 1k\n.param k=2\n{line}\n.op\n.end\n"
)


def _reading(text: str) -> str:
    """The library's reading of the line under test: ``refused``, or its class, form and fields."""
    try:
        netlist = Netlist.from_text(text, dialect=Dialect.NGSPICE)
    except UnsupportedConstruct:
        return "unsupported"
    except ParseError:
        return "refused"
    item = netlist.lines.find_all((ControlledSource, BehavioralSource), recursive=True)[-1].item
    assert isinstance(item, ControlledSource)
    parts = [type(item).__name__, item.form or "linear"]
    if item.expression:
        parts.append("x=" + item.expression.text)
    if item.table:
        table = item.table
        shape = f"{table.layout}:{len(table.points)}x{len(table.points[0].values)}"
        parts.append(shape + (" " + ",".join(table.format) if table.format else ""))
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


# (line, ngspice runs it, the library's reading)
_PROBES = {
    "e-table-pairs": ("E1 out 0 TABLE {v(vx)} = (0,0) (2,4)", True, "Vcvs table x=v(vx) pairs:2x2"),
    "e-table-no-commas": (
        "E1 out 0 TABLE {v(vx)} = (0 0) (2 4)",
        True,
        "Vcvs table x=v(vx) pairs:2x2",
    ),
    "e-table-no-equals": (
        "E1 out 0 TABLE {v(vx)} (0,0) (2,4)",
        True,
        "Vcvs table x=v(vx) pairs:2x2",
    ),
    "e-table-quotes": (
        "E1 out 0 TABLE 'v(vx)' = (0,0) (2,4)",
        True,
        "Vcvs table x=v(vx) pairs:2x2",
    ),
    "e-table-tight": ("E1 out 0 TABLE {v(vx)} =(0,0)(2,4)", True, "Vcvs table x=v(vx) pairs:2x2"),
    "e-table-continued": (
        "E1 out 0 TABLE {v(vx)} = (0,0)\n+ (2,4)",
        True,
        "Vcvs table x=v(vx) pairs:2x2",
    ),
    "e-table-flat": ("E1 out 0 TABLE {v(vx)} = (0,0,2,4)", True, "Vcvs table x=v(vx) flat:2x2"),
    "e-table-one-point": ("E1 out 0 TABLE {v(vx)} = (0,3)", True, "Vcvs table x=v(vx) pairs:1x2"),
    "e-table-bare": ("E1 out 0 TABLE v(vx) = (0,0) (2,4)", True, "refused"),
    "e-table-name": ("E1 out 0 TABLE {v(vx)} = (0,0) (2,k)", True, "refused"),
    "e-table-formula": ("E1 out 0 TABLE {v(vx)} = (0,0) (2,{4})", True, "refused"),
    "e-table-flat-formula": ("E1 out 0 TABLE {v(vx)} = (0,0,2,{2*k})", False, "refused"),
    "e-table-odd": ("E1 out 0 TABLE {v(vx)} = (0,0) (2)", False, "refused"),
    "e-table-odd-flat": ("E1 out 0 TABLE {v(vx)} = (0,0,2)", False, "refused"),
    "e-table-triples": ("E1 out 0 TABLE {v(vx)} = (0,0,0) (2,4,0)", True, "refused"),
    "e-table-units": (
        "E1 out 0 TABLE {v(vx)} = (0,0) (2,-5mV)",
        True,
        "Vcvs table x=v(vx) pairs:2x2",
    ),
    "e-table-m": ("E1 out 0 TABLE {v(vx)} = (0,0) (2,4) m=2", False, "refused"),
    "g-table-m": (
        "G1 0 out TABLE {v(vx)} = (0,0) (2,4m) m=2",
        True,
        "Vccs table x=v(vx) pairs:2x2 p=m=2",
    ),
    "g-table": ("G1 0 out TABLE {v(vx)} = (0,0) (2m,4m)", True, "Vccs table x=v(vx) pairs:2x2"),
    "e-table-nodes-flat": ("E1 out 0 vx 0 TABLE = (0,0,2,4)", True, "Vcvs table flat:2x2"),
    "e-table-nodes-pairs": ("E1 out 0 vx 0 TABLE = (0,0) (2,4)", True, "Vcvs table pairs:2x2"),
    "e-table-nodes-no-commas": ("E1 out 0 vx 0 TABLE = (0 0 2 4)", True, "Vcvs table flat:2x2"),
    "e-table-nodes-no-equals": ("E1 out 0 vx 0 TABLE (0,0,2,4)", True, "Vcvs table flat:2x2"),
    "e-table-nodes-formula": ("E1 out 0 vx 0 TABLE = (0,0,2,{2*k})", True, "refused"),
    "e-table-nodes-braced": ("E1 out 0 vx 0 TABLE = (0,0,2,{4})", True, "refused"),
    "e-table-nodes-name": ("E1 out 0 vx 0 TABLE = (0,0,2,k)", False, "refused"),
    "e-table-nodes-odd": ("E1 out 0 vx 0 TABLE = (0,0,2)", False, "refused"),
    "g-table-nodes": ("G1 0 out vx 0 TABLE = (0,0,2,4)", False, "refused"),
    "e-poly": ("E1 out 0 POLY(1) vx 0 0 2", True, "Vcvs poly N=1 c=0,2"),
    "e-poly-blank": ("E1 out 0 POLY (1) vx 0 0 2", True, "Vcvs poly N=1 c=0,2"),
    "e-poly-braced-dimension": ("E1 out 0 POLY({1}) vx 0 0 2", True, "refused"),
    "e-poly-formula": ("E1 out 0 POLY(1) vx 0 0 {k}", True, "Vcvs poly N=1 c=0,k"),
    "e-poly-name": ("E1 out 0 POLY(1) vx 0 0 k", True, "refused"),
    "e-poly-continued": ("E1 out 0 POLY(1) vx 0\n+ 0 2", True, "Vcvs poly N=1 c=0,2"),
    "e-poly-parens": ("E1 out 0 POLY(1) (vx,0) 0 2", True, "refused"),
    "e-poly-commas": ("E1 out 0 POLY(1) vx,0 0,2", True, "Vcvs poly N=1 c=0,2"),
    "e-poly-zero": ("E1 out 0 POLY(0) 0 2", False, "refused"),
    "e-poly-word-dimension": ("E1 out 0 POLY(k) vx 0 0 2", False, "refused"),
    "e-poly-too-few": ("E1 out 0 POLY(2) vx 0 0 1", False, "refused"),
    "e-poly-no-coefficient": ("E1 out 0 POLY(1) vx 0", False, "refused"),
    "e-poly-one-coefficient": ("E1 out 0 POLY(1) vx 0 3", False, "refused"),
    "e-poly-two": ("E1 out 0 POLY(2) vx 0 vx 0 0 1 1", True, "Vcvs poly N=2 c=0,1,1"),
    "e-poly-m": ("E1 out 0 POLY(1) vx 0 0 2 m=2", True, "refused"),
    "g-poly": ("G1 0 out POLY(1) vx 0 0 2m", True, "Vccs poly N=1 c=0,2m"),
    "g-poly-m": ("G1 0 out POLY(1) vx 0 0 2m m=2", True, "Vccs poly N=1 c=0,2m p=m=2"),
    "f-poly": (
        "F1 0 out POLY(2) Vsense Vsense 0 1 1",
        True,
        "Cccs poly N=2 c=0,1,1 ctl=Vsense,Vsense",
    ),
    "f-poly-m": (
        "F1 0 out POLY(2) Vsense Vsense 0 1 1 m=2",
        True,
        "Cccs poly N=2 c=0,1,1 ctl=Vsense,Vsense p=m=2",
    ),
    "h-poly": ("H1 out 0 POLY(1) Vsense 0 2k", True, "Ccvs poly N=1 c=0,2k ctl=Vsense"),
    "f-poly-missing-source": ("F1 0 out POLY(1) Vnone 0 2", False, "Cccs poly N=1 c=0,2 ctl=Vnone"),
    "f-poly-one-coefficient": ("F1 0 out POLY(1) Vsense 2", False, "refused"),
    "e-freq": (
        "E1 out 0 FREQ {v(vx)}= DB (1, 6.02, 0) (1e9, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 DB",
    ),
    "e-freq-no-commas": (
        "E1 out 0 FREQ {v(vx)}= DB (1 6.02 0) (1e9 6.02 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 DB",
    ),
    "e-freq-no-equals": (
        "E1 out 0 FREQ {v(vx)} DB (1, 6.02, 0) (1e9, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 DB",
    ),
    "e-freq-quotes": (
        "E1 out 0 FREQ 'v(vx)'= DB (1, 6.02, 0) (1e9, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 DB",
    ),
    "e-freq-flat": (
        "E1 out 0 FREQ {v(vx)}= DB (1, 6.02, 0, 1e9, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) flat:2x3 DB",
    ),
    "e-freq-one-point": (
        "E1 out 0 FREQ {v(vx)}= DB (1, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:1x3 DB",
    ),
    "e-freq-mag-deg": (
        "E1 out 0 FREQ {v(vx)}= MAG DEG (1, 2, 0) (1e9, 2, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 MAG,DEG",
    ),
    "e-freq-db-rad": (
        "E1 out 0 FREQ {v(vx)}= DB RAD (1, 6.02, 0) (1e9, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 DB,RAD",
    ),
    "e-freq-r-i": (
        "E1 out 0 FREQ {v(vx)}= R_I (1, 2, 0) (1e9, 2, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 R_I",
    ),
    "e-freq-formula": (
        "E1 out 0 FREQ {v(vx)}= MAG (1, {k}, 0) (1e9, {k}, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 MAG",
    ),
    "g-freq": (
        "G1 0 out FREQ {v(vx)}= DB (1, 6.02, 0) (1e9, 6.02, 0)",
        True,
        "Vccs freq x=v(vx) pairs:2x3 DB",
    ),
    "g-freq-m": ("G1 0 out FREQ {v(vx)}= DB (1, 6.02, 0) (1e9, 6.02, 0) m=2", False, "refused"),
    "e-freq-no-format": ("E1 out 0 FREQ {v(vx)}= (1, 2, 0) (1e9, 2, 0)", False, "refused"),
    "e-freq-two-values": ("E1 out 0 FREQ {v(vx)}= DB (1, 2) (1e9, 2)", False, "refused"),
    # The stop is in the first point: a frequency of more than one character that follows its
    # "(" directly (review R4). A blank after the "(" runs, with or without a Hz suffix.
    "e-freq-first-0": (
        "E1 out 0 FREQ {v(vx)}= DB (0, 6.02, 0) (1e9, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 DB",
    ),
    "e-freq-first-3": (
        "E1 out 0 FREQ {v(vx)}= DB (3, 6.02, 0) (1e9, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 DB",
    ),
    "e-freq-first-10": ("E1 out 0 FREQ {v(vx)}= DB (10, 6.02, 0) (1e9, 6.02, 0)", False, "refused"),
    "e-freq-first-100": (
        "E1 out 0 FREQ {v(vx)}= DB (100, 6.02, 0) (1e9, 6.02, 0)",
        False,
        "refused",
    ),
    "e-freq-first-1.5": (
        "E1 out 0 FREQ {v(vx)}= DB (1.5, 6.02, 0) (1e9, 6.02, 0)",
        False,
        "refused",
    ),
    "e-freq-first-10k": (
        "E1 out 0 FREQ {v(vx)}= DB (10k, 6.02, 0) (1e9, 6.02, 0)",
        False,
        "refused",
    ),
    "e-freq-first-1e7": (
        "E1 out 0 FREQ {v(vx)}= DB (1e7, 6.02, 0) (1e9, 6.02, 0)",
        False,
        "refused",
    ),
    "e-freq-first-2e0": (
        "E1 out 0 FREQ {v(vx)}= DB (2e0, 6.02, 0) (1e9, 6.02, 0)",
        False,
        "refused",
    ),
    "e-freq-first-1-then-1e7": (
        "E1 out 0 FREQ {v(vx)}= DB (1, 6.02, 0) (1e7, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 DB",
    ),
    "e-freq-first-flat-1e7": (
        "E1 out 0 FREQ {v(vx)}= DB (1e7, 6.02, 0, 1e9, 6.02, 0)",
        False,
        "refused",
    ),
    "e-freq-first-blank": (
        "E1 out 0 FREQ {v(vx)}= DB ( 1e7, 6.02, 0) (1e9, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 DB",
    ),
    "e-freq-first-blank-flat": (
        "E1 out 0 FREQ {v(vx)}= DB ( 1e7, 6.02, 0, 1e9, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) flat:2x3 DB",
    ),
    # A braced first frequency stops the same way (review R6): the text after the "(" decides.
    "e-freq-first-braced": (
        "E1 out 0 FREQ {v(vx)}= DB ({1e7}, 6.02, 0) (1e9, 6.02, 0)",
        False,
        "refused",
    ),
    "e-freq-first-parameter": (
        "E1 out 0 FREQ {v(vx)}= DB ({k}, 6.02, 0) (1e9, 6.02, 0)",
        False,
        "refused",
    ),
    "e-freq-first-parameter-blank": (
        "E1 out 0 FREQ {v(vx)}= DB ( {k}, 6.02, 0) (1e9, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 DB",
    ),
    "e-freq-first-blank-hz": (
        "E1 out 0 FREQ {v(vx)}= DB ( 1Hz, 6.02, 0) (1e9, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 DB",
    ),
    "e-freq-hz-both": (
        "E1 out 0 FREQ {v(vx)}= DB ( 1e7Hz, 6.02, 0) (1e9Hz, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 DB",
    ),
    "e-freq-hz-later": (
        "E1 out 0 FREQ {v(vx)}= DB (1, 6.02, 0) (1e9Hz, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 DB",
    ),
    "e-freq-manual": (
        "E1 out 0 FREQ {v(vx)}= DB\n+( 1.000000e+07Hz, 6.02, 0)\n+(1.000000e+08Hz, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 DB",
    ),
    "e-freq-manual-no-blank": (
        "E1 out 0 FREQ {v(vx)}= DB\n+(1.000000e+07Hz, 6.02, 0)\n+(1.000000e+08Hz, 6.02, 0)",
        False,
        "refused",
    ),
    "e-freq-manual-no-hz": (
        "E1 out 0 FREQ {v(vx)}= DB\n+ (1e7, 6.02, 0)\n+ (1e8, 6.02, 0)",
        False,
        "refused",
    ),
    # Contradicting format words: ngspice keeps the last (review R5).
    "e-freq-db-mag": (
        "E1 out 0 FREQ {v(vx)}= DB MAG (1, 6.02, 0) (1e9, 6.02, 0)",
        True,
        "refused",
    ),
    "e-freq-mag-db": (
        "E1 out 0 FREQ {v(vx)}= MAG DB (1, 6.02, 0) (1e9, 6.02, 0)",
        True,
        "refused",
    ),
    "e-freq-deg-rad": (
        "E1 out 0 FREQ {v(vx)}= DB DEG RAD (1, 6.02, 0) (1e9, 6.02, 0)",
        True,
        "refused",
    ),
    "e-freq-r-i-db": (
        "E1 out 0 FREQ {v(vx)}= R_I DB (1, 6.02, 0) (1e9, 6.02, 0)",
        True,
        "refused",
    ),
    "e-freq-db-db": (
        "E1 out 0 FREQ {v(vx)}= DB DB (1, 6.02, 0) (1e9, 6.02, 0)",
        True,
        "Vcvs freq x=v(vx) pairs:2x3 DB,DB",
    ),
    "e-and": ("E1 out 0 and(2) vx 0 vx 0 (0.5, 0) (0.9, 2)", True, "Vcvs and pairs:2x2 N=2"),
    "e-and-upper": ("E1 out 0 AND(2) vx 0 vx 0 (0.5, 0) (0.9, 2)", True, "Vcvs and pairs:2x2 N=2"),
    "e-or": ("E1 out 0 or(2) vx 0 vx 0 (0.5, 0) (0.9, 2)", True, "Vcvs or pairs:2x2 N=2"),
    "e-nand": ("E1 out 0 nand(2) vx 0 vx 0 (0.5, 0) (0.9, 2)", True, "Vcvs nand pairs:2x2 N=2"),
    "e-nor": ("E1 out 0 nor(2) vx 0 vx 0 (0.5, 0) (0.9, 2)", True, "Vcvs nor pairs:2x2 N=2"),
    "e-and-formula": (
        "E1 out 0 and(2) vx 0 vx 0 (0.5, 0) (0.9, {k})",
        True,
        "Vcvs and pairs:2x2 N=2",
    ),
    "e-and-n1": ("E1 out 0 and(1) vx 0 vx 0 (0.5, 0) (0.9, 2)", True, "refused"),
    "e-and-n3": ("E1 out 0 and(3) vx 0 vx 0 (0.5, 0) (0.9, 2)", True, "refused"),
    "e-and-three-pairs": ("E1 out 0 and(2) vx 0 vx 0 vx 0 (0.5, 0) (0.9, 2)", True, "refused"),
    "e-and-one-pair": ("E1 out 0 and(2) vx 0 (0.5, 0) (0.9, 2)", False, "refused"),
    "e-and-one-pair-n1": ("E1 out 0 and(1) vx 0 (0.5, 0) (0.9, 2)", False, "refused"),
    "e-and-odd": ("E1 out 0 and(2) vx 0 vx (0.5, 0) (0.9, 2)", False, "refused"),
    "e-and-three-points": ("E1 out 0 and(2) vx 0 vx 0 (0.5, 0) (0.9, 2) (1, 3)", False, "refused"),
    "e-and-blank": ("E1 out 0 and (2) vx 0 vx 0 (0.5, 0) (0.9, 2)", False, "refused"),
    "e-and-no-commas": ("E1 out 0 and(2) vx 0 vx 0 (0.5 0) (0.9 2)", False, "refused"),
    "e-and-tight": ("E1 out 0 and(2) vx 0 vx 0 (0.5,0)(0.9,2)", False, "refused"),
    "e-and-parens": ("E1 out 0 and(2) (vx,0) (vx,0) (0.5, 0) (0.9, 2)", False, "refused"),
    "g-and": ("G1 0 out and(2) vx 0 vx 0 (0.5, 0) (0.9, 2)", False, "refused"),
    "e-net-table-out": ("Rt table 0 1k\nE1 table 0 vx 0 2", False, "refused"),
    "e-net-table-out-minus": ("Rt table 0 1k\nE1 out table vx 0 2", False, "refused"),
    "e-net-table-control": ("Rt table 0 1k\nE1 out 0 table 0 2", False, "refused"),
    "e-net-table-control-minus": ("Rt table 0 1k\nE1 out 0 vx table 2", False, "refused"),
    "g-net-table-out": ("Rt table 0 1k\nG1 0 table vx 0 1m", False, "refused"),
    "g-net-table-control": ("Rt table 0 1k\nG1 0 out table 0 1m", False, "refused"),
    "e-net-poly": ("Rp poly 0 1k\nE1 poly 0 vx 0 2", True, "Vcvs linear"),
    "e-net-freq": ("Rp freq 0 1k\nE1 freq 0 vx 0 2", True, "Vcvs linear"),
    "e-net-and": ("Rp and 0 1k\nE1 and 0 vx 0 2", True, "Vcvs linear"),
    "e-net-or": ("Rp or 0 1k\nE1 or 0 vx 0 2", True, "Vcvs linear"),
}


@pytest.mark.parametrize("case", sorted(_PROBES))
def test_nonlinear_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    line, ngspice_runs, reading = _PROBES[case]
    text = _BASE.format(line=line)
    assert run(solver, tmp_path, text).ok is ngspice_runs
    assert _reading(text) == reading


# What ngspice computes at vx = 4/3 V: the forms it reads as the manual says, then the ones it
# runs and reads wrongly, which the library refuses (decision 0017 item 4).
@pytest.mark.parametrize(
    ("line", "result"),
    [
        ("E1 out 0 TABLE {v(vx)} = (0,0) (2,4)", 8 / 3),
        ("E1 out 0 TABLE {v(vx)} = (0,3)", 3.0),
        ("E1 out 0 vx 0 TABLE = (0,0,2,4)", 8 / 3),
        ("E1 out 0 vx 0 TABLE = (0,0,2,{4})", 8 / 3),
        ("E1 out 0 TABLE {v(vx)} = (0,0) (2,{4})", 8 / 3),
        ("E1 out 0 POLY(1) vx 0 0 2", 8 / 3),
        ("E1 out 0 POLY(2) vx 0 vx 0 0 1 1", 8 / 3),
        ("G1 0 out POLY(1) vx 0 0 2m", 8 / 3),
        ("F1 0 out POLY(2) Vsense Vsense 0 1 1", 2.0),
        ("F1 0 out POLY(2) Vsense Vsense 0 1 1 m=2", 4.0),
        ("H1 out 0 POLY(1) Vsense 0 2k", 2.0),
        ("G1 0 out TABLE {v(vx)} = (0,0) (2,4m) m=2", 16 / 3),
        ("E1 out 0 and(2) vx 0 vx 0 (0.5, 0) (0.9, 2)", 2.0),
        ("E1 out 0 TABLE v(vx) = (0,0) (2,4)", 4.0),
        ("E1 out 0 vx 0 TABLE = (0,0,2,{2*k})", 4 / 3),
        ("E1 out 0 TABLE {v(vx)} = (0,0,0) (2,4,0)", 4 / 3),
        ("E1 out 0 FREQ {v(vx)}= DB MAG (1, 6.02, 0) (1e9, 6.02, 0)", 8.03),
        ("E1 out 0 FREQ {v(vx)}= DB (1, 6.02, 0) (1e9, 6.02, 0)", 8 / 3),
    ],
)
def test_what_ngspice_computes(solver: Solver, tmp_path: Path, line: str, result: float) -> None:
    values = op(solver, tmp_path, _BASE.format(line=line))
    assert values["v(out)"] == pytest.approx(result, rel=1e-3)


def _out(solver: Solver, folder: Path, netlist: Netlist) -> float:
    return op(solver, folder, netlist)["v(out)"]


_EDITS: list[tuple[str, Callable[[Netlist], Netlist], float, float]] = [
    (
        "E1 out 0 TABLE {v(vx)} = (0,0) (2,4)",
        lambda n: n.set_table("E1", [("0", "0"), ("2", "5")]),
        8 / 3,
        10 / 3,
    ),
    (
        "E1 out 0 TABLE {v(vx)} = (0,0) (2,4)",
        lambda n: n.set_table("E1", [("0", "0"), ("1", "1"), ("2", "5")]),
        8 / 3,
        # Linear between the points, as ngspice interpolates a table.
        1 + (5 - 1) * (4 / 3 - 1),
    ),
    (
        "E1 out 0 vx 0 TABLE = (0,0,2,4)",
        lambda n: n.set_table("E1", [("0", "0"), ("2", "5")]),
        8 / 3,
        10 / 3,
    ),
    (
        "G1 0 out TABLE {v(vx)} = (0,0) (2,4m)",
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
        "E1 out 0 POLY(1) vx 0 0 2",
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
        "E1 out 0 and(2) vx 0 vx 0 (0.5, 0) (0.9, 2)",
        lambda n: n.set_table("E1", [("0.5", "0"), ("0.9", "3")]),
        2.0,
        3.0,
    ),
    (
        "E1 out 0 TABLE {v(vx)} = (0,0) (2,4)",
        lambda n: n.set_expression("E1", "2*v(vx)"),
        8 / 3,
        4.0,
    ),
]


@pytest.mark.parametrize(("line", "edit", "before", "after"), _EDITS)
def test_an_edited_table_or_coefficient_moves_the_result(
    solver: Solver,
    tmp_path: Path,
    line: str,
    edit: Callable[[Netlist], Netlist],
    before: float,
    after: float,
) -> None:
    netlist = Netlist.from_text(_BASE.format(line=line), dialect=Dialect.NGSPICE)
    assert _out(solver, tmp_path / "before", netlist) == pytest.approx(before, rel=1e-4)
    assert _out(solver, tmp_path / "after", edit(netlist)) == pytest.approx(after, rel=1e-4)


_AC = "ac\nV1 in 0 DC 0 AC 1\nR1 in vx 1k\nR2 vx 0 2k\nR3 out 0 1k\n{line}\n.ac lin 1 1k 1k\n.end\n"


def test_freq_is_an_ac_form_and_an_edited_point_moves_it(solver: Solver, tmp_path: Path) -> None:
    # The manual supports FREQ in AC only: 6.02 dB doubles the 2/3 V at vx.
    line = "E1 out 0 FREQ {v(vx)}= DB (1, 6.02, 0) (1e9, 6.02, 0)"
    netlist = Netlist.from_text(_AC.format(line=line), dialect=Dialect.NGSPICE)
    (before,) = ac(solver, tmp_path / "before", netlist)["v(out)"]
    assert abs(before) == pytest.approx(4 / 3, rel=1e-3)
    edited = netlist.set_table("E1", [("1", "12.04", "0"), ("1e9", "12.04", "0")])
    (after,) = ac(solver, tmp_path / "after", edited)["v(out)"]
    assert abs(after) == pytest.approx(8 / 3, rel=1e-3)
    tripled = edited.set_expression("E1", "3*v(vx)")
    (third,) = ac(solver, tmp_path / "expression", tripled)["v(out)"]
    assert abs(third) == pytest.approx(8, rel=1e-3)


def test_freq_table_varies_with_frequency_and_set_table_moves_it(
    solver: Solver, tmp_path: Path
) -> None:
    # The manual's layout: a blank after the first "(" (review R4). 0 dB at 1 kHz and -20 dB at
    # 1 MHz. ngspice interpolates the magnitude linearly in frequency, so halfway (500.5 kHz) the
    # gain is (1 + 0.1) / 2 and the 2/3 V at vx scales by it.
    line = "E1 out 0 FREQ {v(vx)}= DB" + chr(10) + "+( 1e3, 0, 0)" + chr(10) + "+(1e6, -20, 0)"
    text = _AC.format(line=line).replace(".ac lin 1 1k 1k", ".ac lin 1 500.5k 500.5k")
    netlist = Netlist.from_text(text, dialect=Dialect.NGSPICE)
    (middle,) = ac(solver, tmp_path / "before", netlist)["v(out)"]
    assert abs(middle) == pytest.approx(2 / 3 * 0.55, rel=1e-2)
    edited = netlist.set_table("E1", [("1e3", "0", "0"), ("1e6", "-40", "0")])
    (lower,) = ac(solver, tmp_path / "after", edited)["v(out)"]
    assert abs(lower) == pytest.approx(2 / 3 * 0.505, rel=1e-2)
