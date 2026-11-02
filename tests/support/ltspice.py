"""Shared LTspice harness for the solver tests (M8 T9, T8 tier; decision 0009 item 15).

``run`` writes a netlist into a folder, runs ``LTspice.exe -b -ascii`` and returns a :class:`Run`
with the exit code, the log and the parsed raw files. ``op``, ``op_steps``, ``ac`` and
``tran_rows`` run a netlist that must succeed and return its results. ``ensure_runs`` and
``with_stubs`` prepare a library netlist with the M6 edit API.

LTspice writes the results of an AC analysis to ``<name>.raw`` and its bias point to
``<name>.op.raw``, so a :class:`Run` holds both. Raw files and logs stay in the test's temporary
folder: they are never committed (decision 0009 item 2).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, Unpack

from netlistmod import (
    AcDirective,
    DcDirective,
    Netlist,
    OpDirective,
    Placement,
    TranDirective,
    UnknownDirective,
)
from tests.support.ngspice import with_stubs
from tests.support.raw import Plot, read_raw, without_title_and_date
from tests.support.solvers import Solver, run_ltspice

__all__ = [
    "Run",
    "RunOptions",
    "Source",
    "ac",
    "ensure_runs",
    "op",
    "op_steps",
    "run",
    "tran_rows",
    "with_stubs",
]

_ANALYSES = (OpDirective, TranDirective, AcDirective, DcDirective)
# The analyses LTspice has that the library keeps as untyped text (decision 0009 item 5).
_UNTYPED_ANALYSES = (".noise", ".tf")
# LTspice reports a netlist error as `<path>(<line>): <message>`.
_ERROR_LINE = re.compile(r"\(\d+\): ")


@dataclass(frozen=True, slots=True)
class Run:
    """The outcome of one LTspice batch run."""

    returncode: int
    log: str
    netlist: Path
    raw_bytes: bytes | None
    op_raw_bytes: bytes | None = None

    @property
    def plots(self) -> tuple[Plot, ...]:
        """The plots of ``<name>.raw``, then those of ``<name>.op.raw``."""
        return tuple(
            plot
            for data in (self.raw_bytes, self.op_raw_bytes)
            if data is not None
            for plot in read_raw(data)
        )

    @property
    def errors(self) -> list[str]:
        return [line for line in self.log.splitlines() if _ERROR_LINE.search(line)]

    @property
    def ok(self) -> bool:
        """Exit code 0 and no ``file(line): message`` line in the log."""
        return self.returncode == 0 and not self.errors

    @property
    def comparable(self) -> tuple[bytes | None, bytes | None]:
        """Both raw files without the lines that differ between runs (``Title:``, ``Date:``)."""
        return (
            None if self.raw_bytes is None else without_title_and_date(self.raw_bytes),
            None if self.op_raw_bytes is None else without_title_and_date(self.op_raw_bytes),
        )

    def plot(self, name: str) -> Plot:
        """The one plot whose name starts with ``name`` (``"AC"``, ``"Transient"``, …)."""
        found = [plot for plot in self.plots if plot.name.lower().startswith(name.lower())]
        if len(found) != 1:
            names = [plot.name for plot in self.plots]
            raise AssertionError(f"expected one {name!r} plot, found {names}\n{self.log}")
        return found[0]

    def voltage(self, node: str) -> float:
        """``V(node)`` of an unstepped operating point."""
        (value,) = self.plot("Operating Point").real(f"V({node})")
        return value


Source = Netlist | str | bytes | Path


class RunOptions(TypedDict, total=False):
    """The keyword options of :func:`run`, shared by ``op``, ``ac`` and ``tran_rows``."""

    harness: str | None
    stubs: Mapping[str, Path] | None
    name: str


def run(
    solver: Solver,
    folder: Path,
    source: Source,
    *,
    harness: str | None = None,
    stubs: Mapping[str, Path] | None = None,
    name: str = "probe.cir",
) -> Run:
    """Write ``source`` to ``folder / name`` and run it in LTspice.

    Text is written as UTF-8 and a path is copied byte for byte. A netlist is saved after
    ``with_stubs`` (when ``stubs`` maps include paths to stub files), an include of ``harness``
    (text written to ``run_harness.inc``, included before ``.end``) and ``ensure_runs``.
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
    raw = netlist_path.with_suffix(".raw")
    op_raw = netlist_path.with_suffix(".op.raw")
    log_path = netlist_path.with_suffix(".log")
    for stale in (raw, op_raw, log_path):
        stale.unlink(missing_ok=True)
    result = run_ltspice(solver, netlist_path, ascii_raw=True)
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    return Run(
        result.returncode,
        log,
        netlist_path,
        raw.read_bytes() if raw.is_file() else None,
        op_raw.read_bytes() if op_raw.is_file() else None,
    )


def ensure_runs(netlist: Netlist) -> Netlist:
    """Add an ``.op`` line before ``.end`` when the netlist has no analysis line.

    LTspice stops at a netlist without one ("No analysis specified").
    """
    if netlist.lines.find(_ANALYSES) is not None:
        return netlist
    for line in netlist.lines:
        if isinstance(line.item, UnknownDirective) and line.item.raw.lower().startswith(
            _UNTYPED_ANALYSES
        ):
            return netlist
    return netlist.directives.add(".op")


def _succeeded(result: Run) -> Run:
    assert result.ok, result.log
    return result


def op_steps(
    solver: Solver, folder: Path, source: Source, **options: Unpack[RunOptions]
) -> list[dict[str, float]]:
    """The operating point of a netlist that must run, one mapping (lower-case names) per step."""
    plot = _succeeded(run(solver, folder, source, **options)).plot("Operating Point")
    names = [name.lower() for name in plot.variables]
    return [
        dict(zip(names, (float(value.real) for value in row), strict=True)) for row in plot.rows
    ]


def op(
    solver: Solver, folder: Path, source: Source, **options: Unpack[RunOptions]
) -> dict[str, float]:
    """The operating point of an unstepped netlist that must run: lower-case name → value."""
    (point,) = op_steps(solver, folder, source, **options)
    return point


def ac(
    solver: Solver, folder: Path, source: Source, **options: Unpack[RunOptions]
) -> dict[str, tuple[complex, ...]]:
    """The AC analysis of a netlist that must run: variable → complex values per frequency."""
    plot = _succeeded(run(solver, folder, source, **options)).plot("AC Analysis")
    return {name.lower(): tuple(map(complex, plot.column(name))) for name in plot.variables}


def tran_rows(
    solver: Solver, folder: Path, source: Source, **options: Unpack[RunOptions]
) -> list[dict[str, float]]:
    """The transient rows of a netlist that must run, one mapping per time point."""
    plot = _succeeded(run(solver, folder, source, **options)).plot("Transient Analysis")
    names = [name.lower() for name in plot.variables]
    return [
        dict(zip(names, (float(value.real) for value in row), strict=True)) for row in plot.rows
    ]
