"""The LTspice harness on the real solver (M8 T9, T8 tier; decision 0009 item 15)."""

from __future__ import annotations

import cmath
import math
from pathlib import Path

import pytest

from netlistmod import Dialect, Netlist
from tests.support.ltspice import ac, op, op_steps, run, tran_rows
from tests.support.raw import sweeps
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ltspice")

_DIVIDER = "t\nV1 in 0 3\nR1 in out 1k\nR2 out 0 {r2}\n{analysis}\n.end\n"


def test_an_operating_point(solver: Solver, tmp_path: Path) -> None:
    point = op(solver, tmp_path, _DIVIDER.format(r2="1k", analysis=".op"))
    assert point["v(out)"] == pytest.approx(1.5, rel=1e-12)
    assert point["i(r1)"] == pytest.approx(1.5e-3, rel=1e-12)


def test_a_netlist_without_an_analysis_gets_an_op_line(solver: Solver, tmp_path: Path) -> None:
    text = _DIVIDER.format(r2="1k", analysis="")
    assert not run(solver, tmp_path / "text", text).ok  # "No analysis specified"
    netlist = Netlist.from_text(text, dialect=Dialect.LTSPICE)
    assert run(solver, tmp_path / "netlist", netlist).voltage("out") == pytest.approx(1.5)


def test_a_stepped_operating_point_has_one_row_per_step(solver: Solver, tmp_path: Path) -> None:
    points = op_steps(
        solver, tmp_path, _DIVIDER.format(r2="{x}", analysis=".step param x 1k 3k 2k\n.op")
    )
    assert [point["x"] for point in points] == [1e3, 3e3]
    assert [point["v(out)"] for point in points] == pytest.approx([1.5, 2.25], rel=1e-12)


def test_ac_results_and_the_bias_point_in_its_own_file(solver: Solver, tmp_path: Path) -> None:
    text = "t\nV1 in 0 2 AC 1\nR1 in out 1k\nC1 out 0 1u\n.ac list 100 200\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert result.raw_bytes is not None and result.op_raw_bytes is not None
    assert result.voltage("in") == 2.0
    values = ac(solver, tmp_path, text)
    for frequency, value in zip((100, 200), values["v(out)"], strict=True):
        expected = 1 / complex(1, 2 * math.pi * frequency * 1e-3)
        assert cmath.isclose(value, expected, rel_tol=1e-9)


def test_transient_rows_and_steps(solver: Solver, tmp_path: Path) -> None:
    text = "t\nV1 in 0 1\nR1 in out {{x}}\nC1 out 0 1u\n.ic V(out)=0\n.tran 1m uic\n{step}\n.end\n"
    rows = tran_rows(solver, tmp_path / "one", text.format(step=".param x=1k"))
    assert rows[-1]["time"] == pytest.approx(1e-3)
    assert rows[-1]["v(out)"] == pytest.approx(1 - math.exp(-1), rel=1e-3)
    stepped = run(solver, tmp_path / "two", text.format(step=".step param x list 1k 2k"))
    assert stepped.ok, stepped.log
    assert len(sweeps(stepped.plot("Transient"))) == 2


def test_a_netlist_error_is_an_error_line(solver: Solver, tmp_path: Path) -> None:
    result = run(solver, tmp_path, _DIVIDER.format(r2="1k", analysis=".foo\n.op"))
    assert result.returncode != 0 and not result.ok
    assert len(result.errors) == 1 and "(5): " in result.errors[0]
    assert result.plots == ()
