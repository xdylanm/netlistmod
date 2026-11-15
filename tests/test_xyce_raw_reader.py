"""The shared raw-file reader on Xyce's ASCII form, and the parsers of ``tests/support/xyce.py``
(X-M0 B3). No solver is needed.

The Xyce forms are read only with ``read_raw(..., xyce=True)``; without it each one still fails, so
the reader stays as strict for ngspice and LTspice as before X-M0.

Nothing Xyce writes is committed (X-M0 section 2 item 2), so the samples are strings written
here in the shape XyceNF 7.10's ``-r <file> -a`` files take: CRLF lines, a tab before each
variable and value, a blank line after each point, complex values ``re, im``, and ``Title:`` and
``Date:`` only before the first of several plots. The values are made up.
"""

from __future__ import annotations

import pytest

from tests.support.raw import RawFileError, read_raw
from tests.support.xyce import Diagnostic, read_diagnostics, read_names


def _raw(*lines: str) -> bytes:
    return "".join(f"{line}\r\n" for line in lines).encode("ascii")


_HEADER = ("Title: sample", "Date: Mon Jan  1 00:00:00 2026")


def _plot(name: str, flags: str, variables: list[str], points: list[list[str]]) -> list[str]:
    lines = [
        f"Plotname: {name}",
        f"Flags: {flags}",
        f"No. Variables: {len(variables)}",
        f"No. Points: {len(points)}                 ",
        "Variables:",
        *(f"\t{index}\t{variable}" for index, variable in enumerate(variables)),
        "Values:",
    ]
    for index, values in enumerate(points):
        lines.append(f"{index}\t{values[0]}")
        lines.extend(f"\t{value}" for value in values[1:])
        lines.append("")
    return lines


_OP_VARIABLES = ["sweep\tvoltage", "V(1)\tvoltage", "V1#branch\tcurrent"]


def test_an_operating_point_with_a_blank_line_after_the_point() -> None:
    data = _raw(
        *_HEADER,
        *_plot("DC transfer characteristic", "real", _OP_VARIABLES, [["0", "2", "-1e-3"]]),
    )
    (plot,) = read_raw(data, xyce=True)
    assert (plot.title, plot.name, plot.flags) == (
        "sample",
        "DC transfer characteristic",
        ("real",),
    )
    assert plot.variables == ("sweep", "V(1)", "V1#branch")
    assert plot.real("v(1)") == (2.0,)
    assert plot.real("V1#branch") == (-1e-3,)


def test_blank_lines_between_points() -> None:
    points = [["0", "0", "0"], ["1", "1", "-5e-4"], ["2", "2", "-1e-3"]]
    (plot,) = read_raw(_raw(*_HEADER, *_plot("DC Sweep", "real", _OP_VARIABLES, points)), xyce=True)
    assert plot.real("sweep") == (0.0, 1.0, 2.0)
    assert plot.real("V(1)") == (0.0, 1.0, 2.0)


def test_complex_values_with_a_space_after_the_comma() -> None:
    variables = ["frequency\tfrequency", "V(2)\tvoltage"]
    points = [["1.0e+02, 0.0e+00", "7.5e-01, -4.5e-01"], ["2.0e+02, 0.0e+00", "4.0e-01, -5.0e-01"]]
    (plot,) = read_raw(
        _raw(*_HEADER, *_plot("AC Analysis", "complex", variables, points)), xyce=True
    )
    assert plot.column("frequency") == (complex(100, 0), complex(200, 0))
    assert plot.column("V(2)") == (complex(0.75, -0.45), complex(0.4, -0.5))
    with pytest.raises(RawFileError, match="complex"):
        plot.real("V(2)")


def test_complex_values_without_a_space_still_read() -> None:
    variables = ["frequency\tfrequency", "V(2)\tvoltage"]
    (plot,) = read_raw(
        _raw(*_HEADER, *_plot("AC Analysis", "complex", variables, [["1e2,0", "1,-1"]])),
        xyce=True,
    )
    assert plot.column("V(2)") == (complex(1, -1),)


def test_later_plots_take_the_title_of_the_first() -> None:
    first = _plot("Step Analysis: Step 1 of 2", "real", _OP_VARIABLES, [["0", "1", "-1e-3"]])
    second = _plot("Step Analysis: Step 2 of 2", "real", _OP_VARIABLES, [["0", "2", "-2e-3"]])
    plots = read_raw(_raw(*_HEADER, *first, *second), xyce=True)
    assert [plot.title for plot in plots] == ["sample", "sample"]
    assert [plot.real("V(1)") for plot in plots] == [(1.0,), (2.0,)]


def test_blank_lines_between_points_fail_without_xyce() -> None:
    points = [["0", "0", "0"], ["1", "1", "-5e-4"]]
    data = _raw(*_HEADER, *_plot("DC Sweep", "real", _OP_VARIABLES, points))
    with pytest.raises(RawFileError, match="expected point 1"):
        read_raw(data)
    # The same file without the blank lines, as ngspice writes it, reads either way.
    strict = data.replace(b"\r\n\r\n", b"\r\n")
    assert read_raw(strict) == read_raw(data, xyce=True)


def test_complex_values_with_a_space_fail_without_xyce() -> None:
    variables = ["frequency\tfrequency", "V(2)\tvoltage"]
    data = _raw(*_HEADER, *_plot("AC Analysis", "complex", variables, [["1e2, 0", "1, -1"]]))
    # `1e2,` is read as a complex value with no imaginary part, as before X-M0: a ValueError, of
    # which RawFileError is a kind.
    with pytest.raises(ValueError):
        read_raw(data)


def test_a_later_plot_without_a_title_fails_without_xyce() -> None:
    first = _plot("Step Analysis: Step 1 of 2", "real", _OP_VARIABLES, [["0", "1", "-1e-3"]])
    second = _plot("Step Analysis: Step 2 of 2", "real", _OP_VARIABLES, [["0", "2", "-2e-3"]])
    with pytest.raises(RawFileError, match="Title"):
        read_raw(_raw(*_HEADER, *first, *second))


def test_the_first_plot_still_needs_a_title() -> None:
    data = _raw(*_plot("DC transfer characteristic", "real", _OP_VARIABLES, [["0", "1", "0"]]))
    with pytest.raises(RawFileError, match="Title"):
        read_raw(data, xyce=True)


def test_two_blank_lines_between_points_fail() -> None:
    lines = _plot("DC Sweep", "real", _OP_VARIABLES, [["0", "0", "0"], ["1", "1", "0"]])
    second_point = lines.index("1\t1")
    data = _raw(*_HEADER, *lines[:second_point], "", *lines[second_point:])
    with pytest.raises(RawFileError, match="expected point 1"):
        read_raw(data, xyce=True)


def test_a_blank_line_before_the_first_point_fails() -> None:
    lines = _plot("DC Sweep", "real", _OP_VARIABLES, [["0", "0", "0"]])
    values = lines.index("Values:")
    data = _raw(*_HEADER, *lines[: values + 1], "", *lines[values + 1 :])
    with pytest.raises(RawFileError, match="expected point 0"):
        read_raw(data, xyce=True)


def test_a_missing_value_fails() -> None:
    lines = _plot("DC Sweep", "real", _OP_VARIABLES, [["0", "0", "0"], ["1", "1", "0"]])
    lines.remove("\t1")
    with pytest.raises(RawFileError):
        read_raw(_raw(*_HEADER, *lines), xyce=True)


def test_the_names_file() -> None:
    data = _raw("HEADER", "\t0\t           2", "\t1\t   v1_branch", "\t2\t           1")
    assert read_names(data) == {"1", "2", "v1_branch"}


def test_a_blank_line_in_the_names_file_takes_no_index() -> None:
    assert read_names(_raw("HEADER", "", "\t0\ta", "", "\t1\tb", "")) == {"a", "b"}
    with pytest.raises(AssertionError, match="line 4"):
        read_names(_raw("HEADER", "\t0\ta", "", "\t2\tb"))


@pytest.mark.parametrize(
    "lines",
    [
        ("\t0\tx",),
        ("HEADER", "\t1\tx"),
        ("HEADER", "\t0\tx y"),
        ("HEADER", "\t0\tx", "\t1\tx"),
    ],
    ids=["no-header", "wrong-index", "two-names", "repeated"],
)
def test_a_malformed_names_file_fails(lines: tuple[str, ...]) -> None:
    with pytest.raises(AssertionError):
        read_names(_raw(*lines))


def test_diagnostics_located_unlocated_and_wrapped() -> None:
    log = "\n".join(
        [
            "***** Reading and parsing netlist...",
            "Netlist warning in file probe.cir at or near line 4",
            " Unrecognized dot line will be ignored",
            "Netlist warning: No print specified",
            "Netlist error in file",
            r" C:\a\long\folder\probe.cir",
            " at or near line 3",
            " Unrecognized fields for device R1",
            "Simulation aborted due to error.",
        ]
    )
    assert read_diagnostics(log) == (
        Diagnostic("warning", "probe.cir", 4, "Unrecognized dot line will be ignored"),
        Diagnostic("warning", None, None, "No print specified"),
        Diagnostic("error", r"C:\a\long\folder\probe.cir", 3, "Unrecognized fields for device R1"),
    )


def test_a_diagnostic_of_an_unknown_form_fails() -> None:
    with pytest.raises(AssertionError, match="unknown form"):
        read_diagnostics("Netlist error in file probe.cir\n")
