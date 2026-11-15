"""Shared Xyce harness for the solver tests (X-M0 B3, T8 tier; decision 0008).

``run`` writes a netlist into a folder, runs ``Xyce`` on it in one of five modes and returns a
:class:`Run` with the exit code, the log (stdout), the diagnostics parsed from it, and the raw,
``.prn`` or names file the mode writes. ``syntax``, ``norun`` and ``names`` are shorthands; ``op``
and ``dc`` run a netlist that must succeed and return its results.

What the harness relies on was probed on XyceNF 7.10 (X-M0 section 5.1 item 5); only the binary
is run (P10: Xyce's source, including its installed headers, is never read):

- exit code 0, or 1 on any error; a warning does not change it;
- diagnostics on stdout, one ``Netlist error in file <f> at or near line <n>`` (or
  ``Netlist warning …``) line followed by a message line that starts with a space, or an
  unlocated ``Netlist error: <message>``; a long path wraps the first line, and each part goes on
  a line that starts with a space; stderr holds the abort summary;
- ``-syntax`` checks the netlist, ``-norun`` also sets the circuit up, and neither simulates;
- ``-r <file> -a`` writes an ASCII raw file, read by ``tests/support/raw.py``; ``.op`` is written as
  a one-point ``DC transfer characteristic`` plot whose first variable is ``sweep``, and a ``.dc``
  as a plot whose name ends with that;
- without ``-r``, a ``.print`` line writes ``<netlist>.prn`` beside the netlist; with ``-r`` it
  writes none;
- ``-namesfile <file>`` writes ``HEADER`` then one ``\\t<index>\\t<name>`` line per solution
  variable, in lower case, the nodes (ground is not one) and branch currents such as
  ``v1_branch``.

Every file a run writes lands in ``folder``, never in the repository; nothing Xyce writes is
committed (X-M0 section 2 item 2).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from tests.support.raw import Plot, RawFileError, read_raw
from tests.support.solvers import Solver, xyce_version_line

__all__ = [
    "Diagnostic",
    "Mode",
    "Plot",
    "RawFileError",
    "Run",
    "Source",
    "dc",
    "names",
    "nodes",
    "norun",
    "op",
    "read_diagnostics",
    "read_names",
    "run",
    "syntax",
    "version_line",
]

Mode = Literal["run", "print", "syntax", "norun", "namesfile"]
Source = str | bytes | Path

_LOCATED = re.compile(r"Netlist (error|warning) in file (.+?) at or near line (\d+) (.+)")
_UNLOCATED = re.compile(r"Netlist (error|warning): (.+)")


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One ``Netlist error`` or ``Netlist warning`` of the log. ``line`` is ``None`` when Xyce
    names no place (``Netlist warning: No print specified``)."""

    kind: Literal["error", "warning"]
    file: str | None
    line: int | None
    message: str


@dataclass(frozen=True, slots=True)
class Run:
    """The outcome of one Xyce run."""

    mode: Mode
    returncode: int
    log: str
    stderr: str
    netlist: Path
    raw_bytes: bytes | None
    prn_bytes: bytes | None
    names_bytes: bytes | None

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        return read_diagnostics(self.log)

    @property
    def errors(self) -> tuple[Diagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.kind == "error")

    @property
    def warnings(self) -> tuple[Diagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.kind == "warning")

    @property
    def ok(self) -> bool:
        """Exit code 0 and no ``Netlist error`` in the log."""
        return self.returncode == 0 and not self.errors

    @property
    def plots(self) -> tuple[Plot, ...]:
        return () if self.raw_bytes is None else read_raw(self.raw_bytes, xyce=True)

    @property
    def names(self) -> frozenset[str]:
        """Every solution variable of a ``namesfile`` run (see :func:`read_names`)."""
        if self.names_bytes is None:
            raise AssertionError(f"no names file was written\n{self.log}\n{self.stderr}")
        return read_names(self.names_bytes)

    def errors_at(self, line: int) -> tuple[Diagnostic, ...]:
        """The errors Xyce places at or near ``line`` of the netlist."""
        return tuple(item for item in self.errors if item.line == line)

    def warnings_at(self, line: int) -> tuple[Diagnostic, ...]:
        """The warnings Xyce places at or near ``line`` of the netlist."""
        return tuple(item for item in self.warnings if item.line == line)

    def plot(self, name: str) -> Plot:
        """The one plot whose name starts with ``name`` (``"AC"``, ``"Transient"``, …)."""
        found = [plot for plot in self.plots if plot.name.lower().startswith(name.lower())]
        if len(found) != 1:
            names = [plot.name for plot in self.plots]
            raise AssertionError(f"expected one {name!r} plot, found {names}\n{self.log}")
        return found[0]


def read_diagnostics(log: str) -> tuple[Diagnostic, ...]:
    """The diagnostics of a log. Each starts with a ``Netlist error`` or ``Netlist warning`` line
    and goes on over the lines after it that start with a space: the message, and, when the path
    is long, the path and ``at or near line N`` too, which Xyce then puts on lines of their own."""
    lines = log.splitlines()
    found: list[Diagnostic] = []
    for index, text in enumerate(lines):
        if not text.startswith(("Netlist error", "Netlist warning")):
            continue
        block = [text.strip()]
        for following in lines[index + 1 :]:
            if not following.startswith(" "):
                break
            block.append(following.strip())
        joined = " ".join(block)
        if located := _LOCATED.fullmatch(joined):
            found.append(
                Diagnostic(
                    _kind(located.group(1)),
                    located.group(2),
                    int(located.group(3)),
                    located.group(4),
                )
            )
        elif unlocated := _UNLOCATED.fullmatch(joined):
            found.append(Diagnostic(_kind(unlocated.group(1)), None, None, unlocated.group(2)))
        else:
            raise AssertionError(f"a diagnostic of an unknown form: {joined!r}")
    return tuple(found)


def _kind(word: str) -> Literal["error", "warning"]:
    return "error" if word == "error" else "warning"


def read_names(data: bytes) -> frozenset[str]:
    """The names of a ``-namesfile`` file: ``HEADER``, then ``\\t<index>\\t<name>`` lines (the
    name right-aligned with spaces). Anything else fails loudly."""
    lines = data.decode("utf-8").splitlines()
    if not lines or lines[0].strip() != "HEADER":
        raise AssertionError(f"a names file starts with HEADER: {lines[:1]}")
    found: list[str] = []
    for number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        fields = line.split()
        # The index counts the names, not the lines: a blank line takes no index.
        if len(fields) != 2 or fields[0] != str(len(found)):
            raise AssertionError(f"names file line {number}: {line!r}")
        found.append(fields[1])
    if len(set(found)) != len(found):
        raise AssertionError(f"a name is listed twice: {found}")
    return frozenset(found)


def run(
    solver: Solver,
    folder: Path,
    source: Source,
    *,
    mode: Mode = "run",
    name: str = "probe.cir",
    timeout: float = 60,
) -> Run:
    """Write ``source`` to ``folder / name`` and run Xyce on it in ``mode``.

    Text is written as UTF-8 with its line endings as given, bytes as they are, and a path is
    copied byte for byte. ``run`` simulates and writes ``<name>.raw`` (``-r … -a``); ``print``
    simulates with no switch, so that ``.print`` lines write ``<name>.prn``; ``syntax``
    and ``norun`` pass ``-syntax`` and ``-norun``; ``namesfile`` writes ``<name>.names``
    (``-namesfile``). The working directory is ``folder``.
    """
    if solver.name != "xyce":
        raise ValueError(f"Expected xyce, got {solver.name}")
    folder.mkdir(parents=True, exist_ok=True)
    netlist = folder / name
    if isinstance(source, Path):
        shutil.copyfile(source, netlist)
    else:
        netlist.write_bytes(source.encode("utf-8") if isinstance(source, str) else source)
    raw = netlist.with_name(f"{name}.raw")
    names_file = netlist.with_name(f"{name}.names")
    prn = netlist.with_name(f"{name}.prn")
    for stale in (raw, names_file, prn):
        stale.unlink(missing_ok=True)
    switches = {
        "run": ["-r", str(raw), "-a"],
        "print": [],
        "syntax": ["-syntax"],
        "norun": ["-norun"],
        "namesfile": ["-namesfile", str(names_file)],
    }[mode]
    result = subprocess.run(
        [str(solver.path), *switches, str(netlist)],
        capture_output=True,
        check=False,
        cwd=folder,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return Run(
        mode,
        result.returncode,
        result.stdout,
        result.stderr,
        netlist,
        raw.read_bytes() if raw.is_file() else None,
        prn.read_bytes() if prn.is_file() else None,
        names_file.read_bytes() if names_file.is_file() else None,
    )


def syntax(solver: Solver, folder: Path, source: Source, *, name: str = "probe.cir") -> Run:
    """``Xyce -syntax``: the netlist is read and checked, not set up or simulated."""
    return run(solver, folder, source, mode="syntax", name=name)


def norun(solver: Solver, folder: Path, source: Source, *, name: str = "probe.cir") -> Run:
    """``Xyce -norun``: the netlist is read and the circuit set up, not simulated."""
    return run(solver, folder, source, mode="norun", name=name)


def names(
    solver: Solver, folder: Path, source: Source, *, name: str = "probe.cir"
) -> frozenset[str]:
    """Every solution variable of a netlist that must set up (``-namesfile``), in lower case:
    its nodes, without ground, and branch currents such as ``v1_branch``."""
    result = run(solver, folder, source, mode="namesfile", name=name)
    assert result.ok, f"{result.log}\n{result.stderr}"
    return result.names


def nodes(
    solver: Solver, folder: Path, source: Source, *, name: str = "probe.cir"
) -> frozenset[str]:
    """The nodes of a netlist that must set up: :func:`names` without the ``*_branch`` names.

    A node whose own name ends in ``_branch`` would be dropped too; the probes use none."""
    return frozenset(
        item for item in names(solver, folder, source, name=name) if not item.endswith("_branch")
    )


def _succeeded(result: Run) -> Run:
    assert result.ok, f"{result.log}\n{result.stderr}"
    return result


def op(
    solver: Solver, folder: Path, source: Source, *, name: str = "probe.cir"
) -> dict[str, float]:
    """The operating point of a netlist that must run (with an ``.op`` line): variable name in
    lower case (``v(out)``, ``v1#branch``) to value. The ``sweep`` column is left out."""
    plot = _succeeded(run(solver, folder, source, name=name)).plot("DC transfer characteristic")
    if len(plot.rows) != 1:
        raise AssertionError(f"an operating point has one row, got {len(plot.rows)}")
    return {
        variable.lower(): value
        for variable, value in zip(
            plot.variables, (float(v.real) for v in plot.rows[0]), strict=True
        )
        if variable.lower() != "sweep"
    }


def dc(
    solver: Solver, folder: Path, source: Source, *, name: str = "probe.cir"
) -> list[dict[str, float]]:
    """The rows of the one DC sweep of a netlist that must run, one mapping per point, the sweep
    value under ``sweep``. Xyce names the plot ``DC Sweep: Step … DC transfer characteristic``."""
    result = _succeeded(run(solver, folder, source, name=name))
    if len(result.plots) != 1 or not result.plots[0].name.endswith("DC transfer characteristic"):
        raise AssertionError(f"expected one DC sweep, found {[p.name for p in result.plots]}")
    plot = result.plots[0]
    variables = [variable.lower() for variable in plot.variables]
    return [dict(zip(variables, (float(v.real) for v in row), strict=True)) for row in plot.rows]


def version_line(solver: Solver) -> str:
    """The line ``Xyce -v`` prints (``XyceNF Release 7.10.0``)."""
    if solver.name != "xyce":
        raise ValueError(f"Expected xyce, got {solver.name}")
    return xyce_version_line(solver.path)
