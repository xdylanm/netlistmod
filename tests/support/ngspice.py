"""Shared ngspice harness for the solver tests (M7 T1, T8 tier; decision 0008).

``run`` writes a netlist into a folder, runs it in ngspice batch mode with ``-r`` and returns a
:class:`Run` with the exit code, the log and the parsed raw file. ``op``, ``ac`` and
``tran_rows`` run a netlist that must succeed and return its results. ``ensure_runs`` and
``with_stubs`` prepare a library netlist with the M6 edit API: an ``.op`` line for a file without
an analysis, and stub files in place of includes kept outside the repository.

The raw-file reader is shared with the LTspice harness (``tests/support/raw.py``); its names stay
importable from here.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, Unpack

from netlistmod import (
    AcDirective,
    DcDirective,
    Netlist,
    OpaqueStatement,
    OpDirective,
    Placement,
    TranDirective,
)
from tests.support.raw import Plot, RawFileError, read_raw, without_date
from tests.support.solvers import Solver, run_ngspice

__all__ = [
    "ELEMENTS_HARNESS",
    "STUBS",
    "Plot",
    "RawFileError",
    "Run",
    "RunOptions",
    "Source",
    "ac",
    "ensure_runs",
    "op",
    "read_raw",
    "run",
    "tran_rows",
    "with_stubs",
    "without_date",
]

STUBS = Path(__file__).parents[1] / "corpus" / "ngspice" / "solver_stubs"
# The models and subcircuits the elements_basic fixtures refer to (included before `.end`).
ELEMENTS_HARNESS = (STUBS / "elements_harness.inc").read_text(encoding="utf-8")

# ngspice 47's spinit sets `filetype=ascii`, which wins over this variable; it is set as well so
# that a build without that line still writes ASCII. A `.spiceinit` with `set filetype=binary`
# would still win, and the reader then fails loudly (m7-tasks.md T1).
_ENVIRONMENT = {"SPICE_ASCIIRAWFILE": "1"}
_ANALYSES = (OpDirective, TranDirective, AcDirective, DcDirective)


@dataclass(frozen=True, slots=True)
class Run:
    """The outcome of one ngspice batch run."""

    returncode: int
    log: str
    netlist: Path
    raw_bytes: bytes | None

    @property
    def plots(self) -> tuple[Plot, ...]:
        return () if self.raw_bytes is None else read_raw(self.raw_bytes)

    @property
    def ok(self) -> bool:
        """Exit code 0 and no line of the log mentions an error."""
        return self.returncode == 0 and not self.errors

    @property
    def errors(self) -> list[str]:
        return [line for line in self.log.splitlines() if "error" in line.lower()]

    def plot(self, name: str) -> Plot:
        """The one plot whose name starts with ``name`` (``"AC"``, ``"Transient"``, …)."""
        found = [plot for plot in self.plots if plot.name.lower().startswith(name.lower())]
        if len(found) != 1:
            names = [plot.name for plot in self.plots]
            raise AssertionError(f"expected one {name!r} plot, found {names}\n{self.log}")
        return found[0]

    def voltage(self, node: str) -> float:
        """``v(node)`` of the operating point (15 significant digits, from the raw file).

        Several ``.op`` lines give several operating-point plots; they must agree.
        """
        values = {
            plot.real(f"v({node})")[0]
            for plot in self.plots
            if plot.name.lower().startswith("operating point")
        }
        if len(values) != 1:
            raise AssertionError(f"v({node}): operating points {sorted(values)}\n{self.log}")
        return values.pop()

    def device(self, designator: str, parameter: str) -> float:
        """A device parameter of the operating point, saved with ``.save @r1[resistance]``.

        ngspice 47 names some of these vectors ``v(@r1[resistance])``; both forms are read.
        """
        plot = self.plot("Operating Point")
        vector = f"@{designator}[{parameter}]".lower()
        for name in plot.variables:
            if name.lower() in (vector, f"v({vector})"):
                return plot.real(name)[0]
        raise KeyError(f"{vector} is not saved: {plot.variables}")


Source = Netlist | str | bytes | Path


class RunOptions(TypedDict, total=False):
    """The keyword options of :func:`run`, shared by ``op``, ``ac`` and ``tran_rows``."""

    harness: str | None
    stubs: Mapping[str, Path] | None
    lt: bool
    cwd: Path | None
    name: str


def run(
    solver: Solver,
    folder: Path,
    source: Source,
    *,
    harness: str | None = None,
    stubs: Mapping[str, Path] | None = None,
    lt: bool = False,
    cwd: Path | None = None,
    name: str = "probe.cir",
) -> Run:
    """Write ``source`` to ``folder / name`` and run it in ngspice with a raw file.

    Text is written as UTF-8 and a path is copied byte for byte. A netlist is saved after
    ``with_stubs`` (when ``stubs`` maps include paths to stub files), an include of ``harness``
    (text written to ``run_harness.inc``, included before ``.end``) and ``ensure_runs``. ``lt``
    writes a ``.spiceinit`` with ``set ngbehavior=lt``.
    """
    folder.mkdir(parents=True, exist_ok=True)
    netlist_path = folder / name
    if isinstance(source, Netlist):
        prepared = with_stubs(source, folder, stubs or {})
        if harness is not None:
            (folder / "run_harness.inc").write_bytes(harness.encode("utf-8"))
            prepared = prepared.add_include("run_harness.inc", Placement.BEFORE_END)
        ensure_runs(prepared).save(netlist_path)
    else:
        if harness is not None or stubs:
            raise ValueError("harness and stubs need a Netlist source")
        if isinstance(source, Path):
            data = source.read_bytes()
        else:
            data = source.encode("utf-8") if isinstance(source, str) else source
        netlist_path.write_bytes(data)
    if lt:
        (folder / ".spiceinit").write_text("set ngbehavior=lt\n", encoding="utf-8")
    raw = netlist_path.with_suffix(".raw")
    raw.unlink(missing_ok=True)
    result = run_ngspice(solver, netlist_path, raw=raw, cwd=cwd, env=_ENVIRONMENT)
    log_path = folder / "ngspice.log"
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    raw_bytes = raw.read_bytes() if raw.is_file() else None
    return Run(result.returncode, log, netlist_path, raw_bytes)


def ensure_runs(netlist: Netlist) -> Netlist:
    """Add an ``.op`` line before ``.end`` when the netlist has no analysis line.

    With ``-r``, ngspice 47 runs the analysis lines and writes them to the raw file; an ``op``
    command in a ``.control`` block writes nothing there (probed 2026-10-31, decision 0008).
    """
    if netlist.lines.find(_ANALYSES) is not None:
        return netlist
    return netlist.directives.add(".op")


def with_stubs(netlist: Netlist, folder: Path, stubs: Mapping[str, Path]) -> Netlist:
    """Copy each stub into ``folder`` and point the includes of its path at the copy.

    Each key is an include path as written in an ``.include`` or ``.lib`` line. A ``.lib`` line
    is replaced with ``directives.replace``, with the path swapped for the stub's file name; an
    ``.include`` line is removed and ``add_include`` adds one of the stub in its place (the API
    adds includes only that way, architecture §7.9).
    """
    for path, stub in stubs.items():
        shutil.copyfile(stub, folder / stub.name)
        positions = [
            index
            for index, line in enumerate(netlist.lines)
            if isinstance(line.item, OpaqueStatement) and _include_path(line.item) == path
        ]
        if not positions:
            raise ValueError(f"no .include or .lib line names {path!r}")
        for index in positions:
            line = netlist.lines[index]
            assert isinstance(line.item, OpaqueStatement) and index > 0  # the title comes first
            if line.item.kind == "lib":
                netlist = netlist.directives.replace(
                    line, line.item.raw.replace(path, stub.name, 1)
                )
                continue
            with netlist.batch() as batch:
                batch.directives.remove(line)
                batch.add_include(stub.name, Placement.after(netlist.lines[index - 1]))
            netlist = batch.result
    return netlist


def _include_path(statement: OpaqueStatement) -> str:
    """The path of an ``.include`` or ``.lib`` line, without quotes."""
    fields = statement.raw.split()
    return fields[1].strip("\"'") if len(fields) > 1 else ""


def _succeeded(result: Run) -> Run:
    assert result.ok, result.log
    return result


def op(
    solver: Solver, folder: Path, source: Source, **options: Unpack[RunOptions]
) -> dict[str, float]:
    """The operating point of a netlist that must run: variable name (lower case) → value."""
    result = _succeeded(run(solver, folder, source, **options))
    plot = result.plot("Operating Point")
    return {name.lower(): plot.real(name)[0] for name in plot.variables}


def ac(
    solver: Solver, folder: Path, source: Source, **options: Unpack[RunOptions]
) -> dict[str, tuple[complex, ...]]:
    """The AC analysis of a netlist that must run: variable → complex values per frequency."""
    result = _succeeded(run(solver, folder, source, **options))
    plot = result.plot("AC Analysis")
    return {name.lower(): tuple(map(complex, plot.column(name))) for name in plot.variables}


def tran_rows(
    solver: Solver, folder: Path, source: Source, **options: Unpack[RunOptions]
) -> list[dict[str, float]]:
    """The transient rows of a netlist that must run, one mapping per time point."""
    result = _succeeded(run(solver, folder, source, **options))
    plot = result.plot("Transient Analysis")
    names = [name.lower() for name in plot.variables]
    return [
        dict(zip(names, (float(value.real) for value in row), strict=True)) for row in plot.rows
    ]
