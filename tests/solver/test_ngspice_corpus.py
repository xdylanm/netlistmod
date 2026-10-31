"""Every accept fixture in ngspice 47 (M7 T5, T8 tier; architecture §10.3 (a) and (c)).

Each fixture is loaded, prepared as its manifest's ``solver`` field says (stub files in place of
includes kept outside the repository, an included harness of definitions) and run with an
``.op`` added when it has no analysis (``tests/support/ngspice.py``). (a) It must run without an
error and produce data. (c) It is saved unedited with ``load(...).save(...)``, which must give
the same bytes, and the saved file must give the same raw file, except its ``Date:`` line.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from netlistmod import Dialect, Netlist
from tests.support.ngspice import STUBS, Run, run, without_date
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ngspice")

CORPUS = Path(__file__).parents[1] / "corpus" / "ngspice"
# Accept families; the *_rejects families are probed by the discrepancy tests.
FAMILIES = (
    "structure_basic",
    "kicad_basic",
    "kicad_extended",
    "elements_basic",
    "statements_basic",
    "document_basic",
    "edits_golden",
)


def solver_fields() -> dict[Path, dict[str, Any]]:
    """Each accept fixture with its manifest ``solver`` field (``{}`` when it runs as is)."""
    fields: dict[Path, dict[str, Any]] = {}
    for family in FAMILIES:
        manifest = json.loads((CORPUS / family / "manifest.json").read_text(encoding="utf-8"))
        for name, entry in sorted(manifest["fixtures"].items()):
            if name.endswith(".cir"):
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
    # RKM values occur only in the KiCad corpus; standard notation parses the same with rkm=True.
    netlist = Netlist.load(path, dialect=Dialect.NGSPICE, rkm=True)
    harness = field.get("harness")
    result = run(
        solver,
        folder,
        netlist,
        stubs={include: STUBS / stub for include, stub in field.get("stubs", {}).items()},
        harness=None if harness is None else (STUBS / harness).read_text(encoding="utf-8"),
    )
    assert result.ok, result.log
    assert result.raw_bytes is not None and result.plots, result.log
    return result


@pytest.mark.parametrize(("path", "field"), RUNNABLE)
def test_accept_fixture_runs_in_ngspice(
    solver: Solver, tmp_path: Path, path: Path, field: dict[str, Any]
) -> None:
    result = _run(solver, tmp_path, path, field)
    assert all(plot.rows for plot in result.plots), result.log


@pytest.mark.parametrize(("path", "field"), RUNNABLE)
def test_unedited_round_trip_gives_identical_results(
    solver: Solver, tmp_path: Path, path: Path, field: dict[str, Any]
) -> None:
    saved = tmp_path / "saved" / path.name
    saved.parent.mkdir()
    Netlist.load(path, dialect=Dialect.NGSPICE, rkm=True).save(saved)
    assert saved.read_bytes() == path.read_bytes()
    original = _run(solver, tmp_path / "original", path, field)
    again = _run(solver, tmp_path / "again", saved, field)
    assert original.raw_bytes is not None and again.raw_bytes is not None
    assert without_date(again.raw_bytes) == without_date(original.raw_bytes)
