"""XyceNF 7.10 probes of the X-M1 element lines: R, C, L, K, D, V and I (DC and AC parts) and X
(X-M1 B5; xm1-tasks 5.1 points 9 to 15; decision 0027 items 5 and 6).

Each probe is a minimal netlist authored here and run with ``Xyce`` through
``tests/support/xyce.py``; nothing Xyce writes is committed. A resistance is read through a
divider: ``V1`` is 2 V over ``R1`` (1k) and the element under test from node 2 to ground, so
``v(2)`` is 1 when it is 1k. A capacitance or inductance is read from the current of a 1 V AC
source at 1 kHz.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from tests.support.solvers import Solver
from tests.support.xyce import op, run

pytestmark = pytest.mark.solver("xyce")

_OMEGA = 2 * math.pi * 1e3


def _divider(lines: str) -> str:
    return f"probe\nV1 1 0 2\nR1 1 2 1k\n{lines}.op\n.end\n"


def _v2(solver: Solver, folder: Path, lines: str) -> float:
    return op(solver, folder, _divider(lines))["v(2)"]


def _ac_current(solver: Solver, folder: Path, lines: str) -> float:
    """The magnitude of the current of `V1 1 0 AC 1` at 1 kHz, into the element on node 1."""
    text = f"probe\nV1 1 0 AC 1\n{lines}.ac lin 1 1k 1k\n.end\n"
    result = run(solver, folder, text)
    assert result.ok, f"{result.log}\n{result.stderr}"
    plot = result.plot("AC")
    (row,) = plot.rows
    branch = [v.lower() for v in plot.variables].index("v1#branch")
    return abs(row[branch])


@pytest.mark.parametrize(
    "lines",
    [
        "R5 2 0 1k\n",
        "r5 2 0 1K\n",
        "R5 2 0 R=1k\n",
        "R5 2 0 {500*2}\n",
        "R5 2 0 '1k'\n",
        "R5 2 0 1kohm\n",
        ".model rmod R (R=1)\nR5 2 0 rmod 1k\n",
        ".model rmod RES R=0.5\nR5 2 0 rmod R=2k\n",
        ".model rmod R (RSH=100)\nR5 2 0 rmod L=10u W=1u\n",
        "R5 2 0 1k TC=1m,2u\n",
        "R5 2 0 1k TC=1m, 2u TEMP=27\n",
        "R5 2 0 2k M=2\n",
        ".param q=500\nR5 2 0 1k M=q/q\n",
        "R5 2 0\n+ 1k\n",
    ],
    ids=[
        "positional",
        "case",
        "keyword",
        "braced",
        "quoted",
        "device-unit",
        "model-then-value",
        "model-then-keyword",
        "geometry",
        "tc-list",
        "tc-list-blank-after-comma",
        "multiplicity",
        "bare-parameter-value",
        "continued",
    ],
)
def test_resistor_forms(solver: Solver, tmp_path: Path, lines: str) -> None:
    """The model right after the nodes, then the value, positional or `R=`; the geometry form,
    RSH x L / W from the model ([xyce-ref] §2.3.7 p201–203); `TC=a,b`; a bare instance value
    (decision X-D5)."""
    assert _v2(solver, tmp_path, lines) == pytest.approx(1.0)


def test_the_geometry_form_and_an_explicit_value(solver: Solver, tmp_path: Path) -> None:
    """With `.model rmod R (RSH=100)`, `rmod L=30u W=1u` is 3k; an explicit value replaces the
    geometry, so `rmod 2k L=30u W=1u` is 2k (the maintainer's change to point 10)."""
    model = ".model rmod R (RSH=100)\n"
    geometry = _v2(solver, tmp_path / "geometry", model + "R5 2 0 rmod L=30u W=1u\n")
    assert geometry == pytest.approx(2 * 3 / 4)
    explicit = _v2(solver, tmp_path / "explicit", model + "R5 2 0 rmod 2k L=30u W=1u\n")
    assert explicit == pytest.approx(2 * 2 / 3)


@pytest.mark.parametrize(
    "lines",
    [
        "C5 1 0 1u\n",
        "C5 1 0 C=1u\n",
        ".model cmod C (C=1)\nC5 1 0 cmod 1u\n",
        ".model cmod CAP (C=1)\nC5 1 0 cmod C=1u\n",
        "C5 1 0 Q={1u*V(1)}\n",
        "C5 1 0 0.5u M=2\n",
    ],
    ids=["positional", "keyword", "model", "cap-model-keyword", "charge", "multiplicity"],
)
def test_capacitor_forms(solver: Solver, tmp_path: Path, lines: str) -> None:
    """The model then the value, `C=`, and the charge form `Q=` ([xyce-ref] §2.3.4 p186): 1 uF
    draws 2 pi x 1k x 1u A."""
    assert _ac_current(solver, tmp_path, lines) == pytest.approx(_OMEGA * 1e-6, rel=1e-6)


@pytest.mark.parametrize(
    "lines",
    [
        "L5 1 0 1m\n",
        "L5 1 0 L=1m\n",
        ".model lmod L (L=1)\nL5 1 0 lmod 1m\n",
        ".model lmod IND (L=2)\nL5 1 0 lmod 0.5m\n",
    ],
    ids=["positional", "keyword", "model", "ind-model"],
)
def test_inductor_forms(solver: Solver, tmp_path: Path, lines: str) -> None:
    """The model then the value, or `L=` ([xyce-ref] §2.3.5 p191): 1 mH draws 1 / (2 pi x 1k x
    1m) A."""
    assert _ac_current(solver, tmp_path, lines) == pytest.approx(1 / (_OMEGA * 1e-3), rel=1e-6)


@pytest.mark.parametrize(
    "lines",
    [
        "L1 1 0 1m\nL2 2 0 1m\nR2 2 0 1\nK1 L1 L2 0.5\n",
        "L1 1 0 1m\nL2 2 0 1m\nR2 2 0 1\nK1 L1 L2 {0.5}\n",
        "L1 1 0 1m\nL2 2 0 1m\nR2 2 0 1\nK1 L1 L2 0.5 kmod\n.model kmod CORE\n",
        "L1 1 0 1m\nK1 L1 0.5 kmod\n.model kmod CORE\n",
    ],
    ids=["linear", "braced", "core", "one-winding-core"],
)
def test_coupling_forms(solver: Solver, tmp_path: Path, lines: str) -> None:
    """The inductors, the coupling, then an optional CORE model, which may couple one winding
    ([xyce-ref] §2.3.6 p194)."""
    result = run(solver, tmp_path, f"probe\nV1 1 0 AC 1\n{lines}.ac lin 1 1k 1k\n.end\n")
    assert result.ok, result.log


def test_the_coupling_changes_the_current(solver: Solver, tmp_path: Path) -> None:
    """A coupled, loaded secondary lowers the primary's impedance: the K line is read."""
    lines = "L1 1 0 1m\nL2 2 0 1m\nR2 2 0 1\n"
    alone = _ac_current(solver, tmp_path / "alone", lines)
    coupled = _ac_current(solver, tmp_path / "coupled", lines + "K1 L1 L2 0.9\n")
    assert coupled > alone * 1.5


@pytest.mark.parametrize(
    "line",
    [
        "D1 1 0 dm",
        "D1 1 0 dm 2",
        "D1 1 0 dm {2}",
        "D1 1 0 dm 2 OFF",
        "D1 1 0 dm OFF=1",
        "D1 1 0 dm AREA=2 M=1 TEMP=27",
    ],
)
def test_diode_forms(solver: Solver, tmp_path: Path, line: str) -> None:
    """The model, an optional positional area, then flags and parameters ([xyce-ref] §2.3.8
    p207)."""
    result = run(solver, tmp_path, f"probe\nV1 1 0 0.6\n.model dm D\n{line}\n.op\n.end\n")
    assert result.ok, result.log


def test_the_positional_area_scales_the_current(solver: Solver, tmp_path: Path) -> None:
    """`dm 2` is twice the junction of `dm`."""
    text = "probe\nV1 1 0 0.6\n.model dm D\nD1 1 0 dm{}\n.op\n.end\n"
    one = op(solver, tmp_path / "one", text.format(""))["v1#branch"]
    two = op(solver, tmp_path / "two", text.format(" 2"))["v1#branch"]
    assert two == pytest.approx(2 * one, rel=1e-6)


@pytest.mark.parametrize(
    "lines",
    [
        "V2 2 0 1\n",
        "V2 2 0 DC 1\n",
        "V2 2 0 {1}\n",
        "V2 2 0 DC '1'\n",
        "V2 2 0 1 AC 1\n",
        "V2 2 0 DC 1 AC 1 45\n",
        "V2 2 0 1V\n",
        "I2 2 0 1m\n",
        "I2 2 0 DC 1m AC 1m\n",
        "V2 3 0\nR5 2 0 1k\n",
    ],
    ids=[
        "value",
        "dc",
        "braced",
        "dc-quoted",
        "ac",
        "dc-ac-phase",
        "unit",
        "current",
        "current-dc-ac",
        "no-value",
    ],
)
def test_source_dc_and_ac_forms(solver: Solver, tmp_path: Path, lines: str) -> None:
    """`[DC] value`, then `AC magnitude [phase]` ([xyce-ref] §2.3.10 p226, §2.3.9 p221); a
    source with nothing after its nodes is 0."""
    assert _v2(solver, tmp_path, lines) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "lines",
    [
        "X1 2 s\n",
        "X1 2 s r=1k\n",
        "X1 2 s PARAMS: r=1k\n",
        "X1 2 s\n+ params: r=1k\n",
        "X1 2 s r=500*2\n",
        "X1 2 s r={500*2}\n",
        "X1 2 s r=1kohm\n",
        "X1 2 s r=2k M=2\n",
    ],
    ids=[
        "default",
        "param",
        "params-keyword",
        "params-on-a-plus-line",
        "bare",
        "braced",
        "device-unit",
        "multiplicity",
    ],
)
def test_subcircuit_call_forms(solver: Solver, tmp_path: Path, lines: str) -> None:
    """Nodes, the subcircuit, `PARAMS:` optional, then parameters, `M=` among them; a bare value
    without blanks ([xyce-ref] §2.3.33 p803; decision X-D5)."""
    definition = ".subckt s a params: r=3k\nR1 a 0 {r}\n.ends\n"
    if lines == "X1 2 s\n":
        definition = definition.replace("r=3k", "r=1k")
    assert _v2(solver, tmp_path, definition + lines) == pytest.approx(1.0)


def test_a_node_path_reaches_into_an_instance(solver: Solver, tmp_path: Path) -> None:
    """`X1:c` names the node `c` of instance `X1` (decision X-D2): joined to it, R6 halves the
    subcircuit's 2k to ground."""
    lines = ".subckt s a\nR1 a c 1k\nR2 c 0 1k\n.ends\nX1 2 s\nR6 X1:c 0 1g\n"
    assert _v2(solver, tmp_path, lines) == pytest.approx(2 * 2 / 3, rel=1e-6)


@pytest.mark.parametrize(
    "lines",
    [
        ".model rmod R (R=1)\nR5 2 0 1k rmod\n",
        ".param rv=1k\nR5 2 0 rv\n",
        "R5 2 0\n",
        ".model rmod R (R=1)\nR5 2 0 rmod\n",
        ".model rmod R (RSH=100)\nR5 2 0 rmod L=10u\n",
        "R5 2 0 1k R=3k\n",
        "C5 2 0 1p C=2p\nR5 2 0 1k\n",
        "C5 2 0 1p Q={1p*V(2)}\nR5 2 0 1k\n",
        "C5 2 0 Q=1p\nR5 2 0 1k\n",
        "L1 3 0 1m\nR3 3 0 1\nK1 L1 0.5\nR5 2 0 1k\n",
        ".model dm D\nD1 3 0 2 dm\nR3 3 0 1\nR5 2 0 1k\n",
        "V2 3 0 AC\nR3 3 0 1\nR5 2 0 1k\n",
        "V2 3 0 1, AC 1\nR3 3 0 1\nR5 2 0 1k\n",
        "I2 3 0 1m M=2\nR3 3 0 1\nR5 2 0 1k\n",
        ".subckt s a\nR1 a 0 1k\n.ends\nX1:a 2 s\n",
    ],
    ids=[
        "ngspice-order",
        "bare-parameter-as-value",
        "resistor-without-value",
        "resistor-model-without-value",
        "resistor-model-with-l-only",
        "value-and-r-keyword",
        "value-and-c-keyword",
        "value-and-charge",
        "numeric-charge",
        "one-inductor-without-model",
        "number-before-the-diode-model",
        "bare-ac",
        "comma-in-a-source",
        "multiplicity-on-a-current-source",
        "colon-in-a-designator",
    ],
)
def test_xyce_runs(solver: Solver, tmp_path: Path, lines: str) -> None:
    """Forms Xyce runs, with a warning at most, that the library refuses (discrepancies.md): the
    ngspice order and a bare name as R's value, which Xyce sorts by lookup (point 9); an R
    without a value or with an incomplete geometry (1k default, point 10 as amended); a value
    written twice, of which Xyce silently keeps one; a numeric charge; one inductor without a
    model (point 12); a number before D's model, which Xyce drops (point 13); a bare `AC` and a
    comma on a source line, and `M=` on I (point 14); `:` in a designator."""
    result = run(solver, tmp_path, _divider(lines))
    assert result.ok, result.log


@pytest.mark.parametrize(
    "lines",
    [
        "R5 2 0 resistance=1k\n",
        "C5 2 0 capacitance=1p\nR5 2 0 1k\n",
        "L5 2 0 inductance=1m\nR5 2 0 1k\n",
        "C5 2 0\nR5 2 0 1k\n",
        ".model cmod C (CJ=1)\nC5 2 0 cmod\nR5 2 0 1k\n",
        ".model cmod C (CJ=1)\nC5 2 0 cmod W=1u\nR5 2 0 1k\n",
        "L5 2 0\nR5 2 0 1k\n",
        ".model lmod L (L=1)\nL5 2 0 lmod\nR5 2 0 1k\n",
        "R5 2 0 1k TC=1m,2u,3u\n",
        "R5 2 0 1k,M=1\n",
        "L1 3 0 1m\nR3 3 0 1\nL2 4 0 1m\nR4 4 0 1\nK1 L1 L2 kmod 0.5\n.model kmod CORE\n"
        "R5 2 0 1k\n",
        "V2 3 0 AC 1 DC 2\nR3 3 0 1\nR5 2 0 1k\n",
        "V2 3 0 DC=1\nR3 3 0 1\nR5 2 0 1k\n",
        "V2 3 0 2*1\nR3 3 0 1\nR5 2 0 1k\n",
        ".subckt s a params: r=1k\nR1 a 0 {r}\n.ends\nX1 2 s PARAMS: r=1k, M=1\n",
    ],
    ids=[
        "resistance-keyword",
        "capacitance-keyword",
        "inductance-keyword",
        "capacitor-without-value",
        "capacitor-model-only",
        "capacitor-model-with-w-only",
        "inductor-without-value",
        "inductor-model-only",
        "three-tc-values",
        "comma-on-a-resistor",
        "core-model-before-the-coupling",
        "dc-after-ac",
        "dc-keyword-with-equals",
        "bare-dc-value",
        "comma-in-params",
    ],
)
def test_xyce_stops_on(solver: Solver, tmp_path: Path, lines: str) -> None:
    """The long value keywords; a C without a value, `C=`, `Q=` or `L=`; an L without a value;
    more than two `TC=` values; a comma on an R or X line; the model before K's coupling; `DC`
    after `AC`, `DC=` and a bare DC value (points 10 to 15)."""
    assert run(solver, tmp_path, _divider(lines)).returncode == 1
