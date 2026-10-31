"""Usage guides with doctest examples are executed (architecture §14)."""

from __future__ import annotations

import doctest
import runpy
import sys
from pathlib import Path

import pytest

USAGE = Path(__file__).parents[1] / "docs" / "usage"
EXECUTED = ["elements.md", "statements.md", "document.md"]


@pytest.mark.parametrize("name", EXECUTED)
def test_usage_guide_examples_run(name: str) -> None:
    result = doctest.testfile(str(USAGE / name), module_relative=False, encoding="utf-8")
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
