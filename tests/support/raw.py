"""Shared ASCII raw-file reader of the solver harnesses (M7 T1, M8 T9; decision 0009 item 15).

The reader is clean-room: it was written from the ASCII files ngspice 47 produces (m7-tasks.md
section 7; samples in ``tests/corpus/ngspice/solver_stubs/raw/``) and reads LTspice's ``-ascii``
files unchanged (m8-tasks.md L0). It is test code reading solver output, not netlist syntax, so it
uses ``str`` methods (P13 governs ``src/``).
"""

from __future__ import annotations

from dataclasses import dataclass

Value = float | complex


class RawFileError(ValueError):
    """A raw file that this reader cannot read."""


@dataclass(frozen=True, slots=True)
class Plot:
    """One analysis of a raw file: variable names as written (``v(out)``) and the data rows."""

    title: str
    name: str
    flags: tuple[str, ...]
    variables: tuple[str, ...]
    kinds: tuple[str, ...]
    rows: tuple[tuple[Value, ...], ...]

    def column(self, variable: str) -> tuple[Value, ...]:
        """The values of ``variable`` (case-insensitive), one per point."""
        names = [name.lower() for name in self.variables]
        try:
            index = names.index(variable.lower())
        except ValueError:
            raise KeyError(f"{variable!r} is not in plot {self.name!r}: {self.variables}") from None
        return tuple(row[index] for row in self.rows)

    def real(self, variable: str) -> tuple[float, ...]:
        """The values of ``variable`` in a real plot."""
        values = self.column(variable)
        if not all(isinstance(value, float) for value in values):
            raise RawFileError(f"{variable!r} in plot {self.name!r} is complex")
        return tuple(float(value.real) for value in values)


def read_raw(data: bytes | str) -> tuple[Plot, ...]:
    """Parse an ASCII raw file into its plots, in file order."""
    text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
    lines = text.splitlines()
    plots: list[Plot] = []
    position = 0
    while position < len(lines):
        if not lines[position].strip():
            position += 1
            continue
        plot, position = _read_plot(lines, position)
        plots.append(plot)
    return tuple(plots)


def _read_plot(lines: list[str], position: int) -> tuple[Plot, int]:
    header: dict[str, str] = {}
    while True:
        if position >= len(lines):
            raise RawFileError("the raw file ends inside a plot header")
        key, separator, value = lines[position].partition(":")
        position += 1
        if not separator:
            raise RawFileError(
                f"line {position}: expected `Key: value`, got {lines[position - 1]!r}"
            )
        if key.strip() == "Variables":
            break
        header[key.strip()] = value.strip()
    for required in ("Title", "Plotname", "Flags", "No. Variables", "No. Points"):
        if required not in header:
            raise RawFileError(f"plot header without `{required}:`")
    count, points = int(header["No. Variables"]), int(header["No. Points"])
    variables: list[str] = []
    kinds: list[str] = []
    for index in range(count):
        fields = _line(lines, position).split()
        position += 1
        if len(fields) < 3 or fields[0] != str(index):
            raise RawFileError(f"line {position}: expected variable {index}, got {fields}")
        variables.append(fields[1])
        kinds.append(fields[2])
    marker = _line(lines, position).strip()
    position += 1
    if marker == "Binary:":
        raise RawFileError("binary raw file: only ASCII raw files are read (SPICE_ASCIIRAWFILE)")
    if marker != "Values:":
        raise RawFileError(f"line {position}: expected `Values:`, got {marker!r}")
    flags = tuple(header["Flags"].split())
    convert = _complex if "complex" in flags else float
    rows: list[tuple[Value, ...]] = []
    for point in range(points):
        fields = _line(lines, position).split()
        position += 1
        if not fields or fields[0] != str(point):
            raise RawFileError(f"line {position}: expected point {point}, got {fields}")
        values = fields[1:]
        while len(values) < count:
            values.extend(_line(lines, position).split())
            position += 1
        if len(values) != count:
            raise RawFileError(f"point {point}: {len(values)} values for {count} variables")
        rows.append(tuple(convert(value) for value in values))
    plot = Plot(
        header["Title"],
        header["Plotname"],
        flags,
        tuple(variables),
        tuple(kinds),
        tuple(rows),
    )
    return plot, position


def _line(lines: list[str], position: int) -> str:
    if position >= len(lines):
        raise RawFileError("the raw file ends inside a plot")
    return lines[position]


def _complex(text: str) -> complex:
    real, separator, imaginary = text.partition(",")
    if not separator:
        raise RawFileError(f"complex value without `,`: {text!r}")
    return complex(float(real), float(imaginary))


def without_date(data: bytes) -> bytes:
    """A raw file without its ``Date:`` lines, the only part that differs between runs."""
    return b"".join(
        line for line in data.splitlines(keepends=True) if not line.startswith(b"Date:")
    )


def without_title_and_date(data: bytes) -> bytes:
    """An LTspice raw file without ``Title:`` (the absolute netlist path) and ``Date:``."""
    return b"".join(
        line
        for line in data.splitlines(keepends=True)
        if not line.startswith((b"Title:", b"Date:"))
    )


def sweeps(plot: Plot) -> tuple[tuple[tuple[Value, ...], ...], ...]:
    """The rows of a stepped plot, one group per step.

    LTspice writes the steps of a ``.tran``, ``.ac`` or ``.dc`` one after another in one plot; a
    step starts where the first variable (the time, frequency or sweep axis) returns to its first
    value.
    """
    groups: list[list[tuple[Value, ...]]] = []
    for row in plot.rows:
        if not groups or row[0] == plot.rows[0][0]:
            groups.append([])
        groups[-1].append(row)
    return tuple(tuple(group) for group in groups)
