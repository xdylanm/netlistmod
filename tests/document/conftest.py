"""Run this folder's tests once per dialect (M8 decision 16)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from netlistmod import Dialect
from tests.support.dialects import dialect_fixture


@pytest.fixture(autouse=True, params=[Dialect.NGSPICE, Dialect.LTSPICE], ids=["ngspice", "ltspice"])
def both_dialects(request: pytest.FixtureRequest) -> Iterator[Dialect]:
    yield from dialect_fixture(request)
