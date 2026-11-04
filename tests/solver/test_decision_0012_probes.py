"""Solver evidence for decision 0012 (M11 T3, T4, T8). Nothing LTspice writes is committed."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support import ltspice, ngspice
from tests.support.solvers import Solver

_NG = pytest.mark.solver("ngspice")
_LT = pytest.mark.solver("ltspice")

_DIVIDER = "t\nV1 in 0 1\nR1 in out 1k\nR2 out 0 1k\n"
_BLOCK = _DIVIDER + ".lib extras\nR3 out hidden 1k\nR4 hidden 0 1k\n.endl\n.op\n.end\n"
_CALL = _DIVIDER + 'D1 out 0 dfast\n.lib "parts.lib" extras\n.op\n.end\n'
_PARTS = (
    "* a library file, with no title and no .end\n.lib extras\n.model dfast D\nR3 out 0 1k\n.endl\n"
)
_AC = "t\nV1 a 0 dc 1 ac 1\nR1 a 0 1k\n.ac dec 1 1 10\n.ac dec 1 100 1k\n.end\n"


@_NG
def test_ngspice_stops_on_a_block_in_a_netlist(solver: Solver, tmp_path: Path) -> None:
    result = ngspice.run(solver, tmp_path, _BLOCK)
    assert result.returncode != 0
    assert "unimplemented dot command '.lib'" in result.log


@_LT
def test_ltspice_stops_on_a_block_in_a_netlist(solver: Solver, tmp_path: Path) -> None:
    result = ltspice.run(solver, tmp_path, _BLOCK)
    assert result.returncode != 0
    assert "only allowed in library files" in result.log


@_NG
def test_ngspice_reads_a_section_and_adds_its_elements(solver: Solver, tmp_path: Path) -> None:
    (tmp_path / "parts.lib").write_text(_PARTS, encoding="utf-8")
    assert ngspice.op(solver, tmp_path, _CALL)["v(out)"] == pytest.approx(1 / 3, abs=1e-3)


@_LT
def test_ltspice_reads_a_section_and_ignores_its_elements(solver: Solver, tmp_path: Path) -> None:
    (tmp_path / "parts.lib").write_text(_PARTS, encoding="utf-8")
    assert ltspice.op(solver, tmp_path, _CALL)["v(out)"] == pytest.approx(0.5, abs=5e-3)


@_NG
def test_ngspice_runs_two_lines_of_one_analysis(solver: Solver, tmp_path: Path) -> None:
    result = ngspice.run(solver, tmp_path, _AC)
    assert result.returncode == 0
    assert [plot.name.split()[0] for plot in result.plots] == ["AC", "AC"]


@_LT
def test_ltspice_stops_on_two_lines_of_one_analysis(solver: Solver, tmp_path: Path) -> None:
    result = ltspice.run(solver, tmp_path, _AC)
    assert result.returncode != 0
    assert "More than one analysis" in result.log


@_NG
def test_ngspice_resolves_a_model_defined_in_an_if_block(solver: Solver, tmp_path: Path) -> None:
    text = "t\nV1 a 0 1\nR1 a b 1k\nD1 b 0 dm\n.if (1)\n.model dm D\n.endif\n.op\n.end\n"
    assert ngspice.op(solver, tmp_path, text)["v(b)"] == pytest.approx(0.6, abs=0.2)
