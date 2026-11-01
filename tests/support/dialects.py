"""The dialect of the running test, for the suites parametrised over both dialects (M8 decision 16).

``tests/document/conftest.py`` and ``tests/edits/conftest.py`` run every test once per dialect. A
test whose text only one dialect accepts carries ``ngspice_only`` or ``ltspice_only``, and the
other run is deselected. A module may also name single parameter cases in ``NGSPICE_ONLY_CASES``:
a test name mapped to substrings of the case ids. The LTspice forms of what these exclude are in
``test_ltspice_*.py`` next to them.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from netlistmod import Dialect

_current = Dialect.NGSPICE

ngspice_only = pytest.mark.ngspice_only
ltspice_only = pytest.mark.ltspice_only


def current_dialect() -> Dialect:
    """The dialect the running test is parametrised with."""
    return _current


def is_ltspice() -> bool:
    """Whether the running test is the LTspice run."""
    return _current is Dialect.LTSPICE


def dialect_fixture(request: pytest.FixtureRequest) -> Iterator[Dialect]:
    """Set the current dialect for one test (see the two conftest files)."""
    global _current
    _current = request.param
    try:
        yield request.param
    finally:
        _current = Dialect.NGSPICE


def deselect_other_dialect(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Drop each run whose dialect does not read the test's text; a hook of the top conftest."""
    kept: list[pytest.Item] = []
    dropped: list[pytest.Item] = []
    for item in items:
        callspec = getattr(item, "callspec", None)
        dialect = callspec.params.get("both_dialects") if callspec is not None else None
        cases = getattr(getattr(item, "module", None), "NGSPICE_ONLY_CASES", {})
        case_id = callspec.id if callspec is not None else ""
        name = getattr(item, "originalname", item.name)
        only_ngspice = item.get_closest_marker("ngspice_only") or any(
            case in case_id for case in cases.get(name, ())
        )
        if (dialect is Dialect.LTSPICE and only_ngspice) or (
            dialect is Dialect.NGSPICE and item.get_closest_marker("ltspice_only")
        ):
            dropped.append(item)
        else:
            kept.append(item)
    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = kept
