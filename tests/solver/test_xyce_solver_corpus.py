"""The xyce corpus in XyceNF 7.10 (X-M1 B7, X-M2 B6; T8 tier; architecture §10.3 (a) and (c)).

Each accept fixture is copied with its family (the files it includes) into a temporary folder,
given an `.op` before its `.END` (which gives way to a file's own analysis, X-M2's) and run with
``tests/support/xyce.py``. (a) It must run without an error and give data, and the library's
top-level nets must be Xyce's top-level nodes. (c) Saved unedited with ``load(...).save(...)`` it
gives the same bytes, and the saved file the same results. A fixture whose manifest ``solver``
field is ``{"mode": "print"}`` runs without ``-r``, on which Xyce aborts for `.EMBEDDEDSAMPLING`,
`.HB`, `.LIN` and `.PCE`: it must run without an error, and the saved file write the same files.
Each rejection fixture whose manifest names Xyce's outcome is run the same way: Xyce stops on
it, or runs it (a row of discrepancies.md). Nothing Xyce writes is committed.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from netlistmod import Netlist
from netlistmod.dialects import _XYCE
from tests.support.solvers import Solver
from tests.support.xyce import Mode, Run, nodes, run

pytestmark = pytest.mark.solver("xyce")

CORPUS = Path(__file__).parents[1] / "corpus" / "xyce"
FAMILIES = (
    "structure_basic",
    "statements_basic",
    "elements_basic",
    "directives_basic",
    "sources_basic",
)
REJECT_FAMILIES = (
    "structure_rejects",
    "statements_rejects",
    "elements_rejects",
    "directives_rejects",
    "sources_rejects",
)
_END = re.compile(rb"^\.end(?![a-z0-9_])", re.IGNORECASE | re.MULTILINE)


def _manifest(family: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (CORPUS / family / "manifest.json").read_text(encoding="utf-8")
    )
    return data


def solver_fields() -> dict[Path, dict[str, Any]]:
    """Each accept netlist with its manifest ``solver`` field (``{}`` when it runs as is)."""
    found: dict[Path, dict[str, Any]] = {}
    for family in FAMILIES:
        for name, entry in sorted(_manifest(family)["fixtures"].items()):
            if name.endswith(".cir"):
                found[CORPUS / family / name] = (
                    entry.get("solver", {}) if isinstance(entry, dict) else {}
                )
    return found


def with_op(data: bytes) -> bytes:
    """``data`` with an ``.op`` line before its ``.END`` (or at its end), in its line endings."""
    eol = b"\r\n" if b"\r\n" in data else b"\n"
    match = _END.search(data)
    if match is None:
        return data + b".op" + eol
    return data[: match.start()] + b".op" + eol + data[match.start() :]


def _prepare(folder: Path, path: Path) -> bytes:
    shutil.copytree(path.parent, folder)
    (folder / "manifest.json").unlink()
    return with_op(path.read_bytes())


def _printed(path: Path) -> bool:
    return solver_fields()[path].get("mode") == "print"


def _run(solver: Solver, folder: Path, path: Path, source: Path | None = None) -> Run:
    mode: Mode = "print" if _printed(source or path) else "run"
    result = run(solver, folder, _prepare(folder, path), name=path.name, mode=mode)
    assert result.ok, result.log
    if mode == "run":
        assert result.plots and all(plot.rows for plot in result.plots), result.log
    return result


RUNNABLE = [
    pytest.param(path, id=f"{path.parent.name}/{path.name}")
    for path, field in solver_fields().items()
    if "skip" not in field
]


@pytest.mark.parametrize("path", RUNNABLE)
def test_accept_fixture_runs_in_xyce(solver: Solver, tmp_path: Path, path: Path) -> None:
    _run(solver, tmp_path / "run", path)


@pytest.mark.parametrize("path", RUNNABLE)
def test_the_top_level_nets_are_xyces_nodes(solver: Solver, tmp_path: Path, path: Path) -> None:
    """Xyce names a node of an instance `x1:n`; the top level's nodes have no `:`. The library's
    nets of the top level are the same, without ground and with the node paths left out (their
    own nets, decision X-D2), in lower case as Xyce writes them. A nonlinear K's internal
    variables (`ymin!k2_r`) are not nodes."""
    folder = tmp_path / "names"
    found = nodes(solver, folder, _prepare(folder, path), name=path.name)
    netlist = Netlist.load(path, dialect=_XYCE)
    library = {
        net.name.lower() for net in netlist.nets() if net.name != "0" and ":" not in net.name
    }
    assert library == {node for node in found if ":" not in node and "!" not in node}


@pytest.mark.parametrize("path", RUNNABLE)
def test_unedited_round_trip_gives_identical_results(
    solver: Solver, tmp_path: Path, path: Path
) -> None:
    family = tmp_path / "saved" / path.parent.name
    shutil.copytree(path.parent, family)
    saved = family / path.name
    saved.unlink()
    Netlist.load(path, dialect=_XYCE).save(saved)
    assert saved.read_bytes() == path.read_bytes()
    original = _run(solver, tmp_path / "original", path)
    again = _run(solver, tmp_path / "again", saved, source=path)
    if _printed(path):
        written = {item.name for item in original.netlist.parent.iterdir()}
        assert {item.name for item in again.netlist.parent.iterdir()} == written
        return
    assert [(p.variables, p.rows) for p in again.plots] == [
        (p.variables, p.rows) for p in original.plots
    ]


def _reject_cases() -> list[Any]:
    return [
        pytest.param(family, name, entry["xyce"], id=f"{family}/{name}")
        for family in REJECT_FAMILIES
        for name, entry in sorted(_manifest(family)["fixtures"].items())
        if "xyce" in entry
    ]


@pytest.mark.parametrize(("family", "name", "outcome"), _reject_cases())
def test_xyce_stops_on_or_runs_each_rejection(
    solver: Solver, tmp_path: Path, family: str, name: str, outcome: str
) -> None:
    path = CORPUS / family / name
    result = run(solver, tmp_path, with_op(path.read_bytes()), name=name)
    if outcome == "stops":
        assert result.returncode == 1, result.log
    else:
        assert outcome == "runs"
        assert result.ok, result.log
