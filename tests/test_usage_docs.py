"""Usage guides with doctest examples are executed (architecture §14)."""

from __future__ import annotations

import doctest
from pathlib import Path

import pytest

USAGE = Path(__file__).parents[1] / "docs" / "usage"
EXECUTED = ["elements.md"]


@pytest.mark.parametrize("name", EXECUTED)
def test_usage_guide_examples_run(name: str) -> None:
    result = doctest.testfile(str(USAGE / name), module_relative=False, encoding="utf-8")
    assert result.attempted > 0
    assert result.failed == 0
