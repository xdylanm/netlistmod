"""Edited xyce netlists still run in XyceNF 7.10 with the expected value (X-M1 B6; decision
0027 items 5 and 9; xm1-tasks 5.1 points 10, 11 and 22).

Each circuit is a 1 V source ``V1`` across the element under test, so the current through ``V1``
is the closed form. The library edits the netlist; the ``.op`` line is added to the edited text
only for the run, since the hidden dialect reads ``.op`` from X-M2. Each test asserts the
unedited result as well, so it cannot pass because the edit was ignored. Nothing Xyce writes is
committed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import Netlist
from netlistmod.dialects import _XYCE
from tests.support.solvers import Solver
from tests.support.xyce import op

pytestmark = pytest.mark.solver("xyce")

LINEAR = 1e-6
NONLINEAR = 1e-3


def _netlist(body: str) -> Netlist:
    return Netlist.from_text(f"edit\nV1 1 0 1\n{body}.end\n", dialect=_XYCE)


def _current(solver: Solver, folder: Path, netlist: Netlist) -> float:
    """The current the element draws from ``V1``, in amperes."""
    text = netlist.text.removesuffix(".end\n") + ".op\n.end\n"
    return -op(solver, folder, text)["v1#branch"]


def test_set_value(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist("R1 1 0 1k\n")
    assert _current(solver, tmp_path / "before", netlist) == pytest.approx(1e-3, rel=LINEAR)
    edited = netlist.set_value("R1", "2k")
    assert _current(solver, tmp_path / "after", edited) == pytest.approx(0.5e-3, rel=LINEAR)


def test_set_value_after_the_model_replaces_the_geometry(solver: Solver, tmp_path: Path) -> None:
    # RSH x L / W = 100 x 30 = 3k; an explicit value replaces it (xm1-tasks 5.1 point 10).
    netlist = _netlist(".model rmod R RSH=100\nR1 1 0 rmod L=30u W=1u\n")
    assert _current(solver, tmp_path / "before", netlist) == pytest.approx(1 / 3e3, rel=LINEAR)
    edited = netlist.set_value("R1", "2k")
    assert "R1 1 0 rmod 2k L=30u W=1u\n" in edited.text
    assert _current(solver, tmp_path / "after", edited) == pytest.approx(0.5e-3, rel=LINEAR)


def test_set_model_after_the_nodes_beside_a_keyword(solver: Solver, tmp_path: Path) -> None:
    # The model's `R` multiplies the value, as B5's `model-then-keyword` probe found.
    netlist = _netlist(".model rmod R R=0.5\nR1 1 0 R=2k\n")
    assert _current(solver, tmp_path / "before", netlist) == pytest.approx(0.5e-3, rel=LINEAR)
    edited = netlist.set_model("R1", "rmod")
    assert "R1 1 0 rmod R=2k\n" in edited.text
    assert _current(solver, tmp_path / "after", edited) == pytest.approx(1e-3, rel=LINEAR)


def test_remove_value_leaves_the_geometry(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist(".model rmod R RSH=100\nR1 1 0 rmod R=2k L=30u W=1u\n")
    assert _current(solver, tmp_path / "before", netlist) == pytest.approx(0.5e-3, rel=LINEAR)
    edited = netlist.remove_value("R1")
    assert "R1 1 0 rmod L=30u W=1u\n" in edited.text
    assert _current(solver, tmp_path / "after", edited) == pytest.approx(1 / 3e3, rel=LINEAR)


def test_set_param_of_a_value_keyword(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist("R1 1 0 R=1k\n")
    edited = netlist.set_param("R1", "R", "4k")
    assert _current(solver, tmp_path / "after", edited) == pytest.approx(0.25e-3, rel=LINEAR)


def test_set_dc(solver: Solver, tmp_path: Path) -> None:
    netlist = Netlist.from_text("edit\nV1 1 0 DC 1 AC 1\nR1 1 0 1k\n.end\n", dialect=_XYCE)
    assert _current(solver, tmp_path / "before", netlist) == pytest.approx(1e-3, rel=LINEAR)
    edited = netlist.set_dc("V1", "3")
    assert _current(solver, tmp_path / "after", edited) == pytest.approx(3e-3, rel=LINEAR)


def test_params_set_edits_the_definition_xyce_uses(solver: Solver, tmp_path: Path) -> None:
    # Xyce 7.10 uses the first of two `.param` definitions (xm1-tasks 5.1 point 22).
    netlist = _netlist(".param a=1k\n.param a=2k\nR1 1 0 {a}\n")
    assert _current(solver, tmp_path / "before", netlist) == pytest.approx(1e-3, rel=LINEAR)
    edited = netlist.params.set("a", "4k")
    assert _current(solver, tmp_path / "after", edited) == pytest.approx(0.25e-3, rel=LINEAR)


def test_params_set_edits_a_global_param(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist(".global_param g=1k\nR1 1 0 {g}\n")
    edited = netlist.params.set("g", "500")
    assert _current(solver, tmp_path / "after", edited) == pytest.approx(2e-3, rel=LINEAR)


def test_set_param_of_a_positional_diode_area(solver: Solver, tmp_path: Path) -> None:
    # A diode's current scales with its area: three times the area, three times the current.
    netlist = _netlist(".model dm D IS=1e-14\nD1 1 0 dm 1\n")
    before = _current(solver, tmp_path / "before", netlist)
    edited = netlist.set_param("D1", "area", "3")
    assert "D1 1 0 dm 3\n" in edited.text
    after = _current(solver, tmp_path / "after", edited)
    assert after / before == pytest.approx(3, rel=NONLINEAR)


def test_set_instance_param(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist("X1 1 0 s\n.subckt s a b PARAMS: r=1k\nR1 a b {r}\n.ends\n")
    assert _current(solver, tmp_path / "before", netlist) == pytest.approx(1e-3, rel=LINEAR)
    edited = netlist.set_instance_param("X1", "r", "2k")
    assert _current(solver, tmp_path / "after", edited) == pytest.approx(0.5e-3, rel=LINEAR)
