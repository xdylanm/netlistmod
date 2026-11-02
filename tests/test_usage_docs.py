"""Usage guides with doctest examples are executed (architecture §14)."""

from __future__ import annotations

import doctest
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest

from netlistmod import Dialect
from tests.support.solvers import Solver

ROOT = Path(__file__).parents[1]
USAGE = ROOT / "docs" / "usage"
EXECUTED = [
    ROOT / "README.md",
    *(
        USAGE / name
        for name in (
            "structural-parse.md",
            "elements.md",
            "statements.md",
            "document.md",
            "editing.md",
            "errors.md",
        )
    ),
]


@pytest.mark.parametrize("path", EXECUTED, ids=lambda path: path.name)
def test_usage_guide_examples_run(path: Path) -> None:
    result = doctest.testfile(str(path), module_relative=False, encoding="utf-8")
    assert result.attempted > 0
    assert result.failed == 0


def test_read_only_demo_runs(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    demo = USAGE / "examples" / "read_only_demo.py"
    monkeypatch.setattr(sys, "argv", [str(demo)])
    runpy.run_path(str(demo), run_name="__main__")
    output = capsys.readouterr().out
    assert "dc_basic_r_divider.cir: 5 lines" in output
    assert "  /vin: V1, R1  spelled /vin" in output
    assert "  R1: 0->/vin, 1->/vout" in output
    assert "DIALECT_GATED_SYNTAX" in output


def _demo() -> dict[str, Any]:
    return runpy.run_path(str(USAGE / "examples" / "edit_and_simulate.py"), run_name="demo")


@pytest.mark.parametrize("dialect", list(Dialect))
def test_edit_demo_saves_a_minimal_diff(dialect: Dialect, tmp_path: Path) -> None:
    before, after = _demo()["edit_and_save"](dialect, tmp_path)
    assert after.read_bytes() == before.read_bytes().replace(b"R2 out 0 1k", b"R2 out 0 3k")


@pytest.mark.parametrize(
    "dialect",
    [
        pytest.param(Dialect.NGSPICE, marks=pytest.mark.solver("ngspice")),
        pytest.param(Dialect.LTSPICE, marks=pytest.mark.solver("ltspice")),
    ],
)
def test_edit_demo_runs_the_solver(
    dialect: Dialect,
    solver: Solver,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(f"{solver.name.upper()}_EXE", str(solver.path))
    assert _demo()["main"](dialect) == 0
    output = capsys.readouterr().out
    assert "R2=1k: v(out) = 1.5000 V" in output
    assert "R2=3k: v(out) = 2.2500 V" in output
