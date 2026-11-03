"""Load, edit, save and simulate a netlist with netlistmod, and print one net's voltage.

The library never launches a solver, so this script does it. It prints the voltage before and
after the edit, read from each run's raw file. Results are printed only, never stored.

Run from the repository root. Without a netlist it sets ``R2`` of a built-in voltage divider to
3k and probes ``out``::

    uv run --env-file .env python docs/usage/examples/edit_and_simulate.py --dialect ngspice
    uv run --env-file .env python docs/usage/examples/edit_and_simulate.py --dialect ltspice

To use a netlist, add its path and a probe; the edit is optional::

    my.cir --dialect ltspice --edit-value="R2,3k" --probe="out"

It runs only ``.op``: the line is added to the run files if it is missing, and a netlist with
another analysis is refused. An analysis inside an ``.include`` is not seen, because the library
does not read included files. ``--probe`` names a top-level net.

``--rkm`` accepts ngspice values such as ``2k7``. Without ``ngbehavior=lt`` in its ``.spiceinit``,
ngspice reads that value as 2k, so the voltages are wrong; the script prints a line for each value.

The input file is not changed. The run files go beside it, so that relative includes resolve, and
are removed afterwards. The solver is ``NGSPICE_EXE`` or ``LTSPICE_EXE``; ngspice is also looked up
on ``PATH``.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from netlistmod import (
    AcDirective,
    DcDirective,
    DiagnosticCode,
    Dialect,
    Net,
    Netlist,
    OpaqueBlock,
    OpDirective,
    SpiceNetlistError,
    StepDirective,
    TranDirective,
    UnknownDirective,
)

TEXT = "divider\nV1 in 0 DC 3\nR1 in out 1k\nR2 out 0 1k\n.op\n.end\n"
DEFAULT_EDIT = ("R2", "3k")
DEFAULT_PROBE = "out"
# Analyses the library keeps as untyped text, so they are recognised by name.
UNTYPED_ANALYSES = {".disto", ".four", ".net", ".noise", ".pss", ".pz", ".sens", ".sp", ".tf"}
# Info that can change the voltages: the solver may not read this syntax as the library does.
SHOWN_INFO = {DiagnosticCode.DIALECT_GATED_SYNTAX}
SOLVER_TIMEOUT = 60
LOG_LINES = 15


class DemoError(Exception):
    """A problem this script reports itself, outside the library's own errors."""


def with_op(netlist: Netlist) -> Netlist:
    """``netlist`` with an ``.op`` line, added if missing; refuse any other analysis."""
    for line in netlist.lines:
        item = line.item
        if isinstance(item, TranDirective | AcDirective | DcDirective | StepDirective):
            name = type(item).__name__.removesuffix("Directive").lower()
        elif isinstance(item, UnknownDirective) and item.name.lower() in UNTYPED_ANALYSES:
            name = item.name.lower().removeprefix(".")
        elif isinstance(item, OpaqueBlock):
            # Its contents are not read, so it may hold an analysis.
            name = f"{item.kind} block"
        else:
            continue
        raise DemoError(f"line {line.first_line}: this script runs only .op, and found .{name}")
    if any(isinstance(line.item, OpDirective) for line in netlist.lines):
        return netlist
    return netlist.directives.add(".op")


def versions(netlist: Netlist, edit: tuple[str, str] | None) -> list[tuple[str, Netlist]]:
    """The netlists to run, each with a label: as written, then with ``edit`` made."""
    before = with_op(netlist)
    if edit is None:
        return [("as written", before)]
    reference, value = edit
    # A new netlist, re-parsed and checked against the topology of the original.
    after = before.set_value(reference, value)
    element = before.element(reference)
    old = getattr(element, "value", None) or getattr(element, "dc", None)
    old_label = f"{reference}={old.text}" if old is not None else f"{reference} as written"
    return [(old_label, before), (f"{reference}={value}", after)]


def find_net(netlist: Netlist, probe: str) -> Net:
    """The top-level net with this name, in any spelling or case."""
    for net in netlist.nets():
        if probe.casefold() in {net.name, *(name.casefold() for name in net.spellings)}:
            return net
    names = ", ".join(sorted(net.spellings[0] for net in netlist.nets()))
    raise DemoError(f"no net {probe!r} at the top level; the nets are: {names}")


def find_solver(dialect: Dialect) -> str | None:
    """The solver's path from the environment, or ``None``."""
    if dialect is Dialect.NGSPICE:
        return os.environ.get("NGSPICE_EXE") or shutil.which("ngspice")
    return os.environ.get("LTSPICE_EXE")


def simulate(solver: str, dialect: Dialect, netlist: Path) -> Path:
    """Run ``netlist`` in batch mode and return its ASCII raw file."""
    raw = netlist.with_suffix(".raw")
    log = netlist.with_suffix(".log")
    if dialect is Dialect.NGSPICE:
        command = [solver, "-b", "-r", str(raw), "-o", str(log), str(netlist)]
        environment = {**os.environ, "SPICE_ASCIIRAWFILE": "1"}
    else:
        command = [solver, "-b", "-ascii", str(netlist)]
        environment = None
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            cwd=netlist.parent,
            env=environment,
            timeout=SOLVER_TIMEOUT,
        )
    except subprocess.TimeoutExpired as error:
        raise DemoError(f"the solver did not finish in {SOLVER_TIMEOUT} s") from error
    if result.returncode != 0 or not raw.exists():
        raise DemoError(f"the solver failed (exit {result.returncode}):\n{_log_tail(log)}")
    return raw


def _log_tail(log: Path) -> str:
    """The end of a solver log, which may be UTF-16 (LTspice) or a single-byte encoding."""
    if not log.exists():
        return "(no log file)"
    text = log.read_bytes().decode("latin-1").replace("\0", "")
    return "\n".join([line for line in text.splitlines() if line.strip()][-LOG_LINES:])


def net_voltage(raw: Path, net: Net) -> float:
    """The voltage of ``net`` from an ASCII raw file with one point.

    ngspice may name the variable just ``out`` rather than ``v(out)``. Ground has no variable.
    """
    if net.name == "0":
        return 0.0
    lines = raw.read_bytes().decode("latin-1").splitlines()
    first_variable = lines.index("Variables:") + 1
    values_at = lines.index("Values:")
    names = [line.split()[1].lower() for line in lines[first_variable:values_at]]
    # The first value shares its line with the point number.
    values = [lines[values_at + 1].split()[-1], *lines[values_at + 2 :]]
    for name, value in zip(names, values, strict=False):
        if name in {f"v({net.name})", net.name}:
            return float(value.strip())
    raise DemoError(f"no voltage for {net.name!r} among {names}")


def run(
    solver: str,
    dialect: Dialect,
    runs: list[tuple[str, Netlist]],
    net: Net,
    probe: str,
    folder: Path,
) -> None:
    """Save and simulate each version in ``folder``, print the voltage, and remove the run files."""
    prefix = f"_edit_and_simulate_{uuid4().hex[:8]}_"
    try:
        for number, (label, version) in enumerate(runs):
            saved = folder / f"{prefix}{number}.cir"
            version.save(saved)
            voltage = net_voltage(simulate(solver, dialect, saved), net)
            print(f"{label}: v({probe}) = {voltage:.4f} V")
    finally:
        for leftover in folder.glob(f"{prefix}*"):
            leftover.unlink()


def main(
    dialect: Dialect,
    path: Path | None = None,
    edit: tuple[str, str] | None = None,
    probe: str | None = None,
    *,
    rkm: bool = False,
) -> int:
    """Print the voltage at ``probe`` before and after ``edit``; 1 if anything fails."""
    if path is None:
        edit, probe = edit or DEFAULT_EDIT, probe or DEFAULT_PROBE
    if probe is None:
        print("error: a netlist needs --probe", file=sys.stderr)
        return 1
    try:
        if path is None:
            netlist = Netlist.from_text(TEXT, dialect=dialect)
        else:
            netlist = Netlist.load(path, dialect=dialect, rkm=rkm)
        for diagnostic in netlist.diagnostics:
            if diagnostic.severity != "info" or diagnostic.code in SHOWN_INFO:
                print(
                    f"{diagnostic.line}:{diagnostic.column} {diagnostic.severity} "
                    f"{diagnostic.code.value}: {diagnostic.message}",
                    file=sys.stderr,
                )
        net = find_net(netlist, probe)
        runs = versions(netlist, edit)
        solver = find_solver(dialect)
        if solver is None:
            raise DemoError(f"{dialect.value}: no solver found; set NGSPICE_EXE or LTSPICE_EXE")
        if path is not None:
            run(solver, dialect, runs, net, probe, path.resolve().parent)
        else:
            with TemporaryDirectory() as name:
                run(solver, dialect, runs, net, probe, Path(name))
    except (SpiceNetlistError, DemoError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


def _edit_value(text: str) -> tuple[str, str]:
    """``reference,new_value`` as a pair."""
    reference, _, value = text.partition(",")
    if not reference.strip() or not value.strip():
        raise argparse.ArgumentTypeError(f"expected <reference>,<new_value>, not {text!r}")
    return reference.strip(), value.strip()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("netlist", nargs="?", type=Path, help="default: a built-in divider")
    parser.add_argument(
        "--dialect", choices=[d.value for d in Dialect], default=Dialect.NGSPICE.value
    )
    parser.add_argument(
        "--edit-value", type=_edit_value, metavar="REFERENCE,VALUE", help="the value to change"
    )
    parser.add_argument("--probe", metavar="NET", help="the net whose voltage is printed")
    parser.add_argument("--rkm", action="store_true", help="accept ngspice RKM values such as 2k7")
    args = parser.parse_args()
    sys.exit(main(Dialect(args.dialect), args.netlist, args.edit_value, args.probe, rkm=args.rkm))
