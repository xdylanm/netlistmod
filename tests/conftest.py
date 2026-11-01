"""Pytest setup for local solver integration tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.support.dialects import deselect_other_dialect
from tests.support.solvers import Solver, SolverName, discover_solver


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--require-solver",
        choices=("ngspice", "ltspice"),
        help="fail instead of skipping tests when this solver is unavailable",
    )


def pytest_report_header(config: pytest.Config) -> list[str]:
    """Name each solver the solver tests will use, with its version (architecture §10.3)."""
    lines = []
    for name in ("ngspice", "ltspice"):
        try:
            found = discover_solver(name)
        except (OSError, RuntimeError) as error:
            lines.append(f"solver {name}: discovery failed: {error}")
            continue
        if found is None:
            lines.append(f"solver {name}: not found")
        else:
            lines.append(f"solver {name}: {found.version} at {found.path}")
    return lines


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "solver(name): test requiring a local solver (ngspice or ltspice)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    deselect_other_dialect(config, items)


@pytest.fixture
def solver(request: pytest.FixtureRequest) -> Iterator[Solver]:
    marker = request.node.get_closest_marker("solver")
    if (
        marker is None
        or len(marker.args) != 1
        or marker.args[0]
        not in (
            "ngspice",
            "ltspice",
        )
    ):
        raise pytest.UsageError(
            "The solver fixture requires @pytest.mark.solver('ngspice'|'ltspice')"
        )

    name: SolverName = marker.args[0]
    solver_info = discover_solver(name)
    if solver_info is None:
        message = f"{name} not found; set {name.upper()}_EXE or add it to PATH"
        if request.config.getoption("--require-solver") == name:
            pytest.fail(message, pytrace=False)
        pytest.skip(message)
    yield solver_info
