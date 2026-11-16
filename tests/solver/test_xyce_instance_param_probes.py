"""XyceNF 7.10 probes of the closed instance-parameter lists of R, C, L and D (X-M1 B7;
xm1-tasks 5.1 point 29).

Each probe is a minimal netlist authored here and run with ``Xyce`` through
``tests/support/xyce.py``; nothing Xyce writes is committed. ``V1`` is 2 V over ``R1`` (1k) and
the element under test from node 2 to ground. Each netlist is also read by the library, which
reads the netlists that run and refuses those Xyce stops on, except where the model's level
decides the list (``test_the_model_level_decides_the_list``, a discrepancy row).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import Netlist, ParseError
from netlistmod.dialects import _XYCE
from tests.support.solvers import Solver
from tests.support.xyce import run

pytestmark = pytest.mark.solver("xyce")


def _divider(lines: str, analysis: str = ".op\n") -> str:
    return f"probe\nV1 1 0 2\nR1 1 2 1k\n{lines}{analysis}.end\n"


def _read(lines: str) -> Netlist:
    """The library's reading of the netlist without its `.op`, which is X-M2's."""
    return Netlist.from_text(_divider(lines, ""), dialect=_XYCE)


_LISTED = {
    # Table 2-42 (§2.3.7 p203); `TC=` is the vector form of TC1 and TC2.
    "resistor-level-1": "R5 2 0 1k DTEMP=0 M=1 TC1=0 TC2=0 TCE=0 TEMP=27 L=1u W=1u\n",
    "resistor-tc": "R5 2 0 1k tc=0,0\n",
    "resistor-keyword": "R5 2 0 R=1k\n",
    # Table 2-44 (§2.3.7 p204–205), the thermal resistor of a LEVEL=2 model.
    "resistor-level-2": ".model rt R (level=2)\nR5 2 0 rt 1k a=1 density=1 heatcapacity=1 l=1 "
    "m=1 outputintvars=0 resistivity=1 temp=27 thermal_a=1 thermal_heatcapacity=1 thermal_l=1 "
    "w=1\n",
    # Table 2-37 (§2.3.4 p187).
    "capacitor": "C5 2 0 1u AGE=0 D=0.02 DTEMP=0 IC=0 M=1 TC1=0 TC2=0 TEMP=27\n",
    "capacitor-keyword": "C5 2 0 C=1u tc=0,0\n",
    "capacitor-charge": "C5 2 0 Q={1u*V(2)}\n",
    "capacitor-geometry": ".model cm C (CJ=1)\nC5 2 0 cm L=1u W=1u\n",
    # Table 2-39 (§2.3.5 p193).
    "inductor": "L5 2 0 1u DTEMP=0 IC=0 M=1 TC1=0 TC2=0 TEMP=27\n",
    "inductor-keyword": "L5 2 0 L=1u tc=0,0\n",
    # Table 2-46 (§2.3.8 p208), levels 1 and 2.
    "diode-level-1": ".model dm D\nD5 2 0 dm AREA=1 DTEMP=0 IC=0 M=1 PJ=0 TEMP=27 OFF\n",
    "diode-level-2": ".model dm D (level=2)\nD5 2 0 dm area=1 dtemp=0 ic=0 m=1 pj=0 temp=27\n",
    # Table 2-48 (§2.3.8 p209), JUNCAP200.
    "diode-level-200": ".model dm D (level=200)\nD5 2 0 dm ab=1e-12 lg=1e-6 ls=1e-6 m=1 mult=1\n",
    # Table 2-51 (§2.3.8 p213), DIODE_CMC.
    "diode-level-2002": ".model dm D (level=2002)\nD5 2 0 dm ab=1e-12 area=1e-12 lg=1e-6 ls=1e-6 "
    "mult=1 perim=1e-6 pj=1e-6\n",
}


@pytest.mark.parametrize("lines", list(_LISTED.values()), ids=list(_LISTED))
def test_every_listed_name_runs(solver: Solver, tmp_path: Path, lines: str) -> None:
    text = _divider(lines)
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    _read(lines)


_UNLISTED = {
    "resistor-unknown": "R5 2 0 1k foo=1\n",
    "resistor-model-parameter": "R5 2 0 1k RSH=1\n",
    "resistor-tnom": "R5 2 0 1k tnom=27\n",
    "capacitor-unknown": "C5 2 0 1u foo=1\n",
    "capacitor-tce": "C5 2 0 1u tce=0\n",
    "capacitor-model-parameter": "C5 2 0 1u cj=1\n",
    "inductor-unknown": "L5 2 0 1u foo=1\n",
    "inductor-w": "L5 2 0 1u w=1\n",
    "inductor-age": "L5 2 0 1u age=0\n",
    "diode-unknown": ".model dm D\nD5 2 0 dm foo=1\n",
}


@pytest.mark.parametrize("lines", list(_UNLISTED.values()), ids=list(_UNLISTED))
def test_an_unlisted_name_stops_xyce(solver: Solver, tmp_path: Path, lines: str) -> None:
    """A model parameter, another letter's parameter or an unknown name: Xyce stops
    ("Unrecognized parameter" on R, C and L, "Unrecognized fields" on D), and so does the
    library."""
    text = _divider(lines)
    result = run(solver, tmp_path, text)
    assert result.returncode == 1
    assert any("Unrecognized" in error.message for error in result.errors), result.log
    with pytest.raises(ParseError, match="is not a parameter of a Xyce"):
        _read(lines)


_LEVEL_BOUND = {
    "thermal-name-on-level-1": "R5 2 0 1k thermal_a=1\n",
    "level-1-name-on-level-2": ".model rt R (level=2)\nR5 2 0 rt 1k dtemp=0\n",
    "tc-on-level-2": ".model rt R (level=2)\nR5 2 0 rt 1k tc1=0\n",
    "mult-on-level-1": ".model dm D\nD5 2 0 dm mult=1\n",
    "area-on-level-200": ".model dm D (level=200)\nD5 2 0 dm area=1\n",
    "off-on-level-200": ".model dm D (level=200)\nD5 2 0 dm off\n",
    "m-on-level-2002": ".model dm D (level=2002)\nD5 2 0 dm m=1\n",
}


@pytest.mark.parametrize("lines", list(_LEVEL_BOUND.values()), ids=list(_LEVEL_BOUND))
def test_the_model_level_decides_the_list(solver: Solver, tmp_path: Path, lines: str) -> None:
    """Xyce takes only the table of the model's LEVEL. The library's list is the union of the
    letter's tables, since the level is the model's (and may be in another file), so it reads
    these lines (discrepancies.md)."""
    text = _divider(lines)
    assert run(solver, tmp_path, text).returncode == 1
    _read(lines)
