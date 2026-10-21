"""Pytest setup for local solver integration tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.support.solvers import Solver, SolverName, discover_solver


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--require-solver",
        choices=("ngspice", "ltspice"),
        help="fail instead of skipping tests when this solver is unavailable",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "solver(name): test requiring a local solver (ngspice or ltspice)",
    )


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
