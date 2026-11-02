"""Load, edit, save and simulate a voltage divider with netlistmod.

The library never launches a solver, so this script does it. It prints the output voltage before
and after the edit, read from each run's raw file. Results are printed only, never stored.

Run from the repository root::

    uv run --env-file .env python docs/usage/examples/edit_and_simulate.py --dialect ngspice
    uv run --env-file .env python docs/usage/examples/edit_and_simulate.py --dialect ltspice

The solver is ``NGSPICE_EXE`` or ``LTSPICE_EXE``; ngspice is also looked up on ``PATH``.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from netlistmod import Dialect, Netlist

TEXT = "divider\nV1 in 0 DC 3\nR1 in out 1k\nR2 out 0 1k\n.op\n.end\n"


def edit_and_save(dialect: Dialect, folder: Path) -> tuple[Path, Path]:
    """Save the netlist as written and with ``R2`` edited; return both paths."""
    before, after = folder / "before.cir", folder / "after.cir"
    netlist = Netlist.from_text(TEXT, dialect=dialect)
    netlist.save(before)
    # A new netlist, re-parsed and checked against the topology of the original.
    netlist.set_value("R2", "3k").save(after)
    return before, after


def find_solver(dialect: Dialect) -> str | None:
    """The solver's path from the environment, or ``None``."""
    if dialect is Dialect.NGSPICE:
        return os.environ.get("NGSPICE_EXE") or shutil.which("ngspice")
    return os.environ.get("LTSPICE_EXE")


def simulate(solver: str, dialect: Dialect, netlist: Path) -> Path:
    """Run ``netlist`` in batch mode and return its ASCII raw file."""
    raw = netlist.with_suffix(".raw")
    if dialect is Dialect.NGSPICE:
        command = [
            solver,
            "-b",
            "-r",
            str(raw),
            "-o",
            str(netlist.with_suffix(".log")),
            str(netlist),
        ]
        environment = {**os.environ, "SPICE_ASCIIRAWFILE": "1"}
    else:
        command = [solver, "-b", "-ascii", str(netlist)]
        environment = None
    subprocess.run(
        command, check=True, capture_output=True, cwd=netlist.parent, env=environment, timeout=60
    )
    return raw


def output_voltage(raw: Path) -> float:
    """``v(out)`` from an ASCII raw file with one point (ngspice may name it just ``out``)."""
    lines = raw.read_bytes().decode("latin-1").splitlines()
    first_variable = lines.index("Variables:") + 1
    values_at = lines.index("Values:")
    names = [line.split()[1].lower() for line in lines[first_variable:values_at]]
    # The first value shares its line with the point number.
    values = [lines[values_at + 1].split()[-1], *lines[values_at + 2 :]]
    for name, value in zip(names, values, strict=False):
        if name in {"v(out)", "out"}:
            return float(value.strip())
    raise ValueError(f"no output voltage among {names}")


def main(dialect: Dialect) -> int:
    """Print the output voltage before and after the edit; 1 if the solver is missing."""
    solver = find_solver(dialect)
    if solver is None:
        print(f"{dialect.value}: no solver found; set NGSPICE_EXE or LTSPICE_EXE", file=sys.stderr)
        return 1
    with TemporaryDirectory() as name:
        before, after = edit_and_save(dialect, Path(name))
        for label, path in (("R2=1k", before), ("R2=3k", after)):
            print(f"{label}: v(out) = {output_voltage(simulate(solver, dialect, path)):.4f} V")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dialect", choices=[d.value for d in Dialect], default=Dialect.NGSPICE.value
    )
    sys.exit(main(Dialect(parser.parse_args().dialect)))
