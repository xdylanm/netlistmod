"""Every accept fixture in LTspice 26.1.1 (M8 T10, T8 tier; architecture §10.3 (a) and (c)).

Each fixture is loaded, prepared as its manifest's ``solver`` field says and run with an ``.op``
added when it has no analysis (``tests/support/ltspice.py``). Besides the fields of decision 0008,
``{"warning": "<text>"}`` names the one message the run may write as a ``file(line):`` line. (a) It
must run without an error and produce data. (c) It is saved unedited with ``load(...).save(...)``,
which must give the same bytes, and the saved file must give the same raw files, except ``Title:``
(the absolute path) and ``Date:``. Nothing LTspice writes is committed (decision 0009 item 2).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from netlistmod import Dialect, Netlist
from tests.support.ltspice import Run, run
from tests.support.solvers import Solver, copy_external_files

pytestmark = pytest.mark.solver("ltspice")

CORPUS = Path(__file__).parents[1] / "corpus" / "ltspice"
STUBS = CORPUS / "solver_stubs"
# Accept families; the *_rejects families are probed by test_ltspice_validation.py.
FAMILIES = (
    "contributed_examples",
    "edits_golden",
    "elements_basic",
    "encoding_samples",
    "m0_export_candidate",
    "names_basic",
    "statements_basic",
    "ltspice_transistors",
    "controlled_sources",
    "transmission_lines",
)
_NETLISTS = {".cir", ".net"}


def solver_fields() -> dict[Path, dict[str, Any]]:
    """Each accept fixture with its manifest ``solver`` field (``{}`` when it runs as is).

    A fixture whose entry records an ``error`` is one the library rejects; it is not an accept
    fixture.
    """
    fields: dict[Path, dict[str, Any]] = {}
    for family in FAMILIES:
        manifest = json.loads((CORPUS / family / "manifest.json").read_text(encoding="utf-8"))
        for name, entry in sorted(manifest["fixtures"].items()):
            if Path(name).suffix not in _NETLISTS:
                continue
            if isinstance(entry, dict) and "error" in entry:
                continue
            fields[CORPUS / family / name] = (
                entry.get("solver", {}) if isinstance(entry, dict) else {}
            )
    return fields


RUNNABLE = [
    pytest.param(path, field, id=f"{path.parent.name}/{path.name}")
    for path, field in solver_fields().items()
    if "skip" not in field
]


def _run(solver: Solver, folder: Path, path: Path, field: dict[str, Any]) -> Run:
    copy_external_files(folder, field)
    netlist = Netlist.load(path, dialect=Dialect.LTSPICE)
    harness = field.get("harness")
    result = run(
        solver,
        folder,
        netlist,
        stubs={include: STUBS / stub for include, stub in field.get("stubs", {}).items()},
        harness=None if harness is None else (STUBS / harness).read_text(encoding="utf-8"),
    )
    warning = field.get("warning")
    if warning is None:
        assert result.ok, result.log
    else:
        # LTspice writes a warning in the form of an error line; only this one is allowed.
        assert result.returncode == 0, result.log
        assert result.errors and all(warning in line for line in result.errors), result.log
    return result


@pytest.mark.parametrize(("path", "field"), RUNNABLE)
def test_accept_fixture_runs_in_ltspice(
    solver: Solver, tmp_path: Path, path: Path, field: dict[str, Any]
) -> None:
    result = _run(solver, tmp_path, path, field)
    assert result.plots, result.log
    assert all(plot.rows for plot in result.plots), result.log


@pytest.mark.parametrize(("path", "field"), RUNNABLE)
def test_unedited_round_trip_gives_identical_results(
    solver: Solver, tmp_path: Path, path: Path, field: dict[str, Any]
) -> None:
    saved = tmp_path / "saved" / path.name
    saved.parent.mkdir()
    Netlist.load(path, dialect=Dialect.LTSPICE).save(saved)
    assert saved.read_bytes() == path.read_bytes()
    original = _run(solver, tmp_path / "original", path, field)
    again = _run(solver, tmp_path / "again", saved, field)
    assert again.comparable == original.comparable
