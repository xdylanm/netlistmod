"""The Xyce harness on XyceNF 7.10 (X-M0 task B3; section 5.1 item 5).

These check what ``tests/support/xyce.py`` relies on: the version line, exit codes, where
diagnostics are written, the four modes and the raw file of each analysis. The netlists are
authored here; every file Xyce writes stays in the test's temporary folder.
"""

from __future__ import annotations

import cmath
import math
import re
from pathlib import Path

import pytest

from tests.support.solvers import Solver
from tests.support.xyce import dc, names, norun, op, run, syntax, version_line

pytestmark = pytest.mark.solver("xyce")

_DIVIDER = "divider\nV1 1 0 2\nR1 1 2 1k\nR2 2 0 1k\n"


def test_version_line(solver: Solver) -> None:
    """``-v`` prints one line, ``XyceNF Release <version>``; the discovered version is its number,
    the value spec entries record in ``validated_on`` (section 5.1 item 5)."""
    line = version_line(solver)
    assert re.fullmatch(r"Xyce(NF)? Release \d+\.\d+(\.\d+)*", line), line
    assert line.endswith(f" Release {solver.version}")


def test_an_operating_point(solver: Solver, tmp_path: Path) -> None:
    """``.op`` is written as a one-point ``DC transfer characteristic`` plot whose first variable
    is ``sweep``; voltages are named ``V(node)`` and currents ``V1#branch``."""
    result = run(solver, tmp_path, _DIVIDER + ".op\n.end\n")
    assert result.ok and result.returncode == 0
    (plot,) = result.plots
    assert plot.title == "divider" and plot.flags == ("real",)
    assert plot.variables == ("sweep", "V(1)", "V(2)", "V1#branch")
    assert op(solver, tmp_path / "op", _DIVIDER + ".op\n.end\n") == pytest.approx(
        {"v(1)": 2.0, "v(2)": 1.0, "v1#branch": -1e-3}
    )


def test_a_stepped_dc_sweep(solver: Solver, tmp_path: Path) -> None:
    """A ``.step`` writes one plot per step, with ``Title:`` and ``Date:`` given only before the
    first; the reader gives each plot the title."""
    text = _DIVIDER + ".dc V1 0 2 1\n.step R2 1k 2k 1k\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.ok
    first, second = result.plots
    assert first.title == second.title == "divider"
    assert first.real("V(2)") == pytest.approx((0.0, 0.5, 1.0))
    assert second.real("V(2)") == pytest.approx((0.0, 2 / 3, 4 / 3))
    rows = dc(solver, tmp_path / "dc", _DIVIDER + ".dc V1 0 2 1\n.end\n")
    assert [row["sweep"] for row in rows] == [0.0, 1.0, 2.0]
    assert [row["v(2)"] for row in rows] == pytest.approx([0.0, 0.5, 1.0])


def test_an_ac_analysis_has_complex_values(solver: Solver, tmp_path: Path) -> None:
    """An AC plot writes each value as ``re, im``, with a space after the comma, and a blank line
    after each point."""
    text = "rc\nV1 1 0 dc 0 ac 1\nR1 1 2 1k\nC1 2 0 1u\n.ac lin 3 100 300\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.ok
    plot = result.plot("AC Analysis")
    assert "complex" in plot.flags
    frequencies = [value.real for value in plot.column("frequency")]
    assert frequencies == [100.0, 200.0, 300.0]
    for frequency, value in zip(frequencies, plot.column("V(2)"), strict=True):
        expected = 1 / complex(1, 2 * math.pi * frequency * 1e3 * 1e-6)
        assert cmath.isclose(value, expected, rel_tol=1e-6)


def test_a_transient_analysis(solver: Solver, tmp_path: Path) -> None:
    """A transient plot's first variable is ``time``, from 0 to the stop time."""
    text = "rc\nV1 1 0 1\nR1 1 2 1k\nC1 2 0 1n\n.tran 0.1u 1u\n.end\n"
    plot = run(solver, tmp_path, text).plot("Transient Analysis")
    times = plot.real("time")
    assert times[0] == 0.0 and times[-1] == pytest.approx(1e-6)


def test_a_print_line_writes_a_prn_file_beside_the_netlist(solver: Solver, tmp_path: Path) -> None:
    """Without ``-r``, ``.print`` writes ``<netlist>.prn`` next to the netlist, inside the test's
    folder; with ``-r`` it writes none."""
    text = _DIVIDER + ".dc V1 0 2 1\n.print dc v(2)\n.end\n"
    printed = run(solver, tmp_path / "print", text, mode="print")
    assert printed.ok and printed.raw_bytes is None
    assert printed.prn_bytes is not None and (tmp_path / "print" / "probe.cir.prn").is_file()
    header, *rows = printed.prn_bytes.decode("ascii").splitlines()
    assert header.split() == ["Index", "V(2)"] and len(rows) == 4  # and an end line
    raw = run(solver, tmp_path / "raw", text)
    assert raw.ok and raw.prn_bytes is None and raw.raw_bytes is not None


def test_an_error_exits_with_1_and_is_placed_at_its_line(solver: Solver, tmp_path: Path) -> None:
    """An error exits with 1 and is written to stdout as ``Netlist error in file … at or near
    line N`` and a message; stderr holds the abort summary. ``-syntax`` and ``-norun`` find it
    too, and write no raw file."""
    text = "error\nV1 1 0 2\nR1 1 0 1k\nQ1 1\n.op\n.end\n"
    for result in (
        run(solver, tmp_path / "run", text),
        syntax(solver, tmp_path / "syntax", text),
        norun(solver, tmp_path / "norun", text),
    ):
        assert result.returncode == 1 and not result.ok
        assert result.errors_at(4), result.log
        assert result.raw_bytes is None
        assert "abort" in result.stderr.lower()


def test_a_warning_does_not_change_the_exit_code(solver: Solver, tmp_path: Path) -> None:
    """A warning, here one with no line (no ``.print``), leaves the exit code 0."""
    result = run(solver, tmp_path, _DIVIDER + ".op\n.end\n")
    assert result.returncode == 0
    assert any(item.line is None and "print" in item.message for item in result.warnings)


def test_syntax_and_norun_do_not_simulate(solver: Solver, tmp_path: Path) -> None:
    """``-syntax`` and ``-norun`` succeed on a good netlist and write no raw file."""
    for result in (
        syntax(solver, tmp_path / "syntax", _DIVIDER + ".op\n.end\n"),
        norun(solver, tmp_path / "norun", _DIVIDER + ".op\n.end\n"),
    ):
        assert result.ok and result.raw_bytes is None


def test_the_names_file_lists_nodes_and_branches(solver: Solver, tmp_path: Path) -> None:
    """``-namesfile`` lists every solution variable in lower case, without ground: the nodes and
    the branch current of each voltage source."""
    text = "names\nV1 In 0 2\nR1 In Out 1k\nR2 Out 0 1k\n.op\n.end\n"
    assert names(solver, tmp_path, text) == {"in", "out", "v1_branch"}
