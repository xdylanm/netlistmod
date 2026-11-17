"""XyceNF 7.10 probes of `.TRAN`, `.AC`, `.DC`, `.OP` and `.STEP` (X-M2 B6; decision 0028 items 3
to 5 and 9; xm2-tasks 5.1 points 7 to 17, 31 and 32).

Each probe is a minimal netlist authored here and run with ``Xyce`` through
``tests/support/xyce.py``, in a temporary folder; nothing Xyce writes is committed. Where Xyce
writes the values a directive asks for (the sweep points, the steps, the last time point), the
probe compares them with the fields the library reads from the same line. The library's own side
is pinned by ``tests/grammar/xyce/test_xyce_analyses.py`` and
``tests/document/test_xyce_directive_findings.py``; these probes back the spec entries and the
rows of ``docs/grammars/xyce/discrepancies.md``, and the claims the diagnostics make about Xyce.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypeVar

import pytest

from netlistmod import (
    AcDirective,
    DcDirective,
    DiagnosticCode,
    Netlist,
    NumericValue,
    StepDirective,
    TranDirective,
    Value,
)
from netlistmod.dialects import _XYCE
from tests.support.solvers import Solver
from tests.support.xyce import Plot, Run, run

pytestmark = pytest.mark.solver("xyce")

_T = TypeVar("_T")

# V1 drives a divider R1, R2 with C1 across R2; X1 hangs a 1 MΩ load on node 2, so `X1:R5:R` is
# a path target; `p` and `gp` are a `.PARAM` and a `.GLOBAL_PARAM`, used by R9 and R8.
_CIRCUIT = (
    "probe\n.param p=1k\n.global_param gp=1k\nV1 1 0 2 AC 1\nR1 1 2 1k\nR2 2 0 rmod 1k\n"
    ".model rmod R R=1\nC1 2 0 1n\n.subckt s a\nR5 a 0 1meg\n.ends\nX1 2 s\nR9 2 0 {p}\n"
    "R8 2 0 {gp}\n"
)
_PAIR = re.compile(r"name = (\S+) value = (\S+)")
_SCALE = {"t": 1e12, "g": 1e9, "meg": 1e6, "x": 1e6, "k": 1e3, "m": 1e-3, "u": 1e-6, "n": 1e-9}
_SCALE |= {"p": 1e-12, "f": 1e-15}


def _netlist(lines: str) -> str:
    return f"{_CIRCUIT}{lines}\n.end\n"


def _library(text: str) -> Netlist:
    return Netlist.from_text(text, dialect=_XYCE)


def _items(text: str, kind: type[_T]) -> list[_T]:
    return [line.item for line in _library(text).lines if isinstance(line.item, kind)]


def _number(value: Value | None) -> float:
    """The value of a plain number of the device-field reader (the probes write no units)."""
    assert isinstance(value, NumericValue), value
    match = re.fullmatch(r"([-+]?[0-9.]+(?:e[-+]?\d+)?)(meg|[tgxkmunpf])?", value.text.lower())
    assert match is not None, value.text
    return float(match.group(1)) * _SCALE.get(match.group(2) or "", 1.0)


def _steps(result: Run) -> list[dict[str, float]]:
    """The stepped values of each plot, from its name (``Step 1 of 2 params: name = R1 value =
    1000 …``), the names in Xyce's case."""
    return [
        {name: float(value) for name, value in _PAIR.findall(plot.name)} for plot in result.plots
    ]


def _column(plot: Plot, name: str) -> list[float]:
    index = [variable.lower() for variable in plot.variables].index(name.lower())
    return [float(row[index].real) for row in plot.rows]


def _ok(solver: Solver, folder: Path, text: str, **kwargs: object) -> Run:
    result = run(solver, folder, text, **kwargs)  # type: ignore[arg-type]
    assert result.ok, f"{result.log}\n{result.stderr}"
    return result


def _stops(solver: Solver, folder: Path, text: str) -> Run:
    result = run(solver, folder, text)
    assert result.returncode != 0, result.log
    return result


def _messages(result: Run) -> str:
    return " | ".join(item.message for item in result.diagnostics)


def _codes(text: str) -> list[DiagnosticCode]:
    return [item.code for item in _library(text).diagnostics]


# .TRAN (XY-TRN-001)


@pytest.mark.parametrize(
    "line",
    [
        ".tran 1n 2n",
        ".TRAN 1n 2n 0",
        ".tran 1n 2n 0 1n",
        ".tran 1n 2n NOOP",
        ".tran 1n 2n uic",
        ".tran 1n 2n UIC NOOP",
        ".tran 1n 2n 0 1n NOOP",
        ".tran 1n 2n {schedule(0, 1n)}",
        ".tran 1n 2n NOOP 'SCHEDULE(0, 1n)'",
        ".tran 1ns 2ns",
        ".tran {1n} '2n'",
    ],
)
def test_tran_forms_run_to_tstop(solver: Solver, tmp_path: Path, line: str) -> None:
    """The manual's fields `tstep tstop [tstart [tmax]] [NOOP] [UIC] [{schedule(...)}]`
    ([xyce-ref] §2.1.38 p161), the device-field reader's units and delimited expressions (point
    10): each runs, and the last time point is the tstop the library reads."""
    text = _netlist(line)
    (tran,) = _items(text, TranDirective)
    assert tran.tstop.text in ("2n", "2ns")
    plot = _ok(solver, tmp_path, text).plot("Transient")
    assert _column(plot, "time")[-1] == pytest.approx(2e-9)


@pytest.mark.parametrize(
    ("line", "message"),
    [
        (".tran 1n", "unexpected number of fields"),
        (".tran 1n 2n 0 1n 3n", "expected NOOP/UIC"),
        (".tran 1n, 2n", "Cannot convert ','"),
        (".tran 1n 2n startup", "Cannot convert 'startup'"),
        (".tran 1n NOOP 2n", "Cannot convert 'NOOP'"),
        (".tran 1n 2j", "Cannot convert '2j'"),
        (".tran 1n 2µ", "to double"),
    ],
)
def test_tran_stops_on(solver: Solver, tmp_path: Path, line: str, message: str) -> None:
    """One value, a fifth number, a comma, a word, a flag before tstop, the imaginary `j` and the
    micro sign stop Xyce (points 7 and 10), as the library refuses them."""
    assert message in _messages(_stops(solver, tmp_path, _netlist(line)))


def test_a_schedule_after_tstart_stops_xyce(solver: Solver, tmp_path: Path) -> None:
    """The manual's form with tstart and a schedule stops Xyce 7.10, which the library reads as
    decided (decision 0028 item 3; a discrepancies.md row); without tstart it runs."""
    _stops(solver, tmp_path / "tstart", _netlist(".tran 1n 2n 0 {schedule(0, 1n)}"))
    _ok(solver, tmp_path / "alone", _netlist(".tran 1n 2n {schedule(0, 1n)}"))


def test_the_manuals_whole_form_stops_xyce(solver: Solver, tmp_path: Path) -> None:
    """`tstep tstop tstart tmax NOOP UIC` stops Xyce, which caps the field count; the library reads
    it (a discrepancies.md row)."""
    result = _stops(solver, tmp_path, _netlist(".tran 1n 2n 0 1n NOOP UIC"))
    assert "unexpected number of fields" in _messages(result)
    _library(_netlist(".tran 1n 2n 0 1n NOOP UIC"))


@pytest.mark.parametrize(
    "line", [".tran 1n 2n NOOP NOOP", ".tran 1n 2n UIC UIC", ".tran 1n 2n NOOP 0"]
)
def test_a_repeated_flag_or_a_number_after_one_runs(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    """Xyce runs a flag written twice and a number after a flag, silently (point 8); the library
    refuses both (a discrepancies.md row)."""
    result = _ok(solver, tmp_path, _netlist(line))
    assert not [item for item in result.warnings if item.line is not None]


def test_uic_is_noop(solver: Solver, tmp_path: Path) -> None:
    """`UIC` is `NOOP`'s synonym ([xyce-ref] §2.1.38 p161; [xyce-ug] §13.6 p205): both skip the
    operating point, so v(2) starts at 0, and give the same rows; Table 6-1's warning is not
    written (point 8)."""
    noop = _ok(solver, tmp_path / "noop", _netlist(".tran 1n 2n NOOP")).plot("Transient")
    uic = _ok(solver, tmp_path / "uic", _netlist(".tran 1n 2n UIC")).plot("Transient")
    plain = _ok(solver, tmp_path / "plain", _netlist(".tran 1n 2n")).plot("Transient")
    assert noop.rows == uic.rows
    assert _column(uic, "v(2)")[0] == pytest.approx(0.0)
    assert _column(plain, "v(2)")[0] != pytest.approx(0.0)


def test_a_schedule_caps_the_time_step(solver: Solver, tmp_path: Path) -> None:
    """`{schedule(t0, h0, t1, h1)}` sets the largest step from each time on ([xyce-ref] §2.1.38
    p161): no step is longer than the schedule's."""
    text = _netlist(".tran 1n 10n {schedule(0, 0.5n, 5n, 0.25n)}")
    times = _column(_ok(solver, tmp_path, text).plot("Transient"), "time")
    steps = [after - before for before, after in zip(times, times[1:], strict=False)]
    assert max(steps) <= 0.5e-9 * (1 + 1e-6)
    late = [
        after - before for before, after in zip(times, times[1:], strict=False) if before > 6e-9
    ]
    assert late and max(late) <= 0.25e-9 * (1 + 1e-6)


# .AC (XY-ACA-001)


@pytest.mark.parametrize(
    ("line", "frequencies"),
    [
        (".ac dec 1 1 100", [1, 10, 100]),
        (".AC OCT 1 1 4", [1, 2, 4]),
        (".ac lin 3 1 3", [1, 2, 3]),
        (".ac dec 1 1hz 10hz", [1, 10]),
    ],
)
def test_ac_sweeps(solver: Solver, tmp_path: Path, line: str, frequencies: list[float]) -> None:
    """`LIN|OCT|DEC points fstart fstop` ([xyce-ref] §2.1.1 p24): the first and last frequency
    are the library's `fstart` and `fstop`."""
    text = _netlist(line)
    (ac,) = _items(text, AcDirective)
    found = _column(_ok(solver, tmp_path, text).plot("AC"), "frequency")
    assert found == pytest.approx(frequencies)
    if "hz" not in line:
        assert (found[0], found[-1]) == pytest.approx((_number(ac.fstart), _number(ac.fstop)))


@pytest.mark.parametrize(
    ("line", "message"),
    [(".ac list 1 10", "unexpected number of fields"), (".ac dec 1 1 10j", "")],
)
def test_ac_stops_on(solver: Solver, tmp_path: Path, line: str, message: str) -> None:
    """`list` (LTspice's) and an imaginary number stop Xyce (point 11), as the library refuses."""
    assert message in _messages(_stops(solver, tmp_path, _netlist(line)))


def test_a_point_count_that_is_not_an_integer_stops_xyce(solver: Solver, tmp_path: Path) -> None:
    """Xyce stops on `.AC dec 1.5 …` ("must be an integer"); the library reads it, since it does
    not check the count (a discrepancies.md row)."""
    result = _stops(solver, tmp_path, _netlist(".ac dec 1.5 1 10"))
    assert "must be an integer" in _messages(result)
    _library(_netlist(".ac dec 1.5 1 10"))


# .DC (XY-DCA-001) and the sweep targets (XY-STP-002)


@pytest.mark.parametrize(
    ("line", "points"),
    [
        (".dc V1 0 1 0.5", [0, 0.5, 1]),
        (".DC LIN V1 0 1 0.5", [0, 0.5, 1]),
        (".dc dec V1 1 100 1", [1, 10, 100]),
        (".dc oct V1 1 4 1", [1, 2, 4]),
        (".dc V1 list 0 1 2", [0, 1, 2]),
        (".dc V1 0 1v 0.5v", [0, 0.5, 1]),
        (".dc R1:R 1k 2k 1k", [1000, 2000]),
        (".dc rmod:R 1 2 1", [1, 2]),
        (".dc TEMP 0 50 50", [0, 50]),
        (".dc p 1k 2k 1k", [1000, 2000]),
        (".dc gp 1k 2k 1k", [1000, 2000]),
        (".dc X1:R5:R 1k 2k 1k", [1000, 2000]),
    ],
)
def test_dc_sweeps_each_target(
    solver: Solver, tmp_path: Path, line: str, points: list[float]
) -> None:
    """A source, `device:parameter`, `model:parameter`, `TEMP`, a `.PARAM`, a `.GLOBAL_PARAM` and a
    path into an instance, each `LIN` (optional), `DEC`, `OCT` or `LIST` ([xyce-ref] §2.1.3 p27;
    point 12): Xyce sweeps the points the line gives, from the library's start."""
    text = _netlist(line)
    (dc,) = _items(text, DcDirective)
    (sweep,) = dc.sweeps
    plot = _ok(solver, tmp_path, text).plot("DC Sweep")
    assert _column(plot, "sweep") == pytest.approx(points)
    first = sweep.values[0] if sweep.values else sweep.start
    if "v" not in line.split()[-1]:
        assert _number(first) == pytest.approx(points[0])


def test_dc_sweeps_nest_the_first_innermost(solver: Solver, tmp_path: Path) -> None:
    """Any number of sweeps, each with its own form, the first innermost ([xyce-ref] §2.1.3 p27;
    point 12): V1 changes fastest, then R1, then TEMP."""
    text = _netlist(".dc V1 0 1 1 R1 1k 2k 1k TEMP 0 50 50")
    assert len(_items(text, DcDirective)[0].sweeps) == 3
    plot = _ok(solver, tmp_path, text).plot("DC Sweep")
    assert _column(plot, "sweep") == pytest.approx([0, 1] * 4)
    assert plot.name.index("V1") < plot.name.index("R1") < plot.name.index("TEMP")


def test_a_list_with_one_value_runs(solver: Solver, tmp_path: Path) -> None:
    """`LIST` with one value runs on `.DC` and `.STEP`, though the manual writes two or more; the
    library refuses it (decision 0028 item 4; a discrepancies.md row)."""
    dc = _ok(solver, tmp_path / "dc", _netlist(".dc V1 list 1")).plot("DC Sweep")
    assert _column(dc, "sweep") == pytest.approx([1.0])
    step = _ok(solver, tmp_path / "step", _netlist(".step R1 list 1k\n.op"))
    assert _steps(step) == [{"R1": 1000.0}]


@pytest.mark.parametrize(
    "line",
    [
        ".dc zz 1 2 1",
        ".dc zz:R 1 2 1",
        ".step zz 1 2 1\n.op",
        ".step zz:IS 1 2 1\n.op",
        ".step X1:R9:R 1 2 1\n.op",
    ],
)
def test_an_undefined_sweep_target_stops_xyce(solver: Solver, tmp_path: Path, line: str) -> None:
    """A target that names no parameter, device, model or path stops Xyce ("… is not defined"), as
    `UNRESOLVED_PARAM`/`UNRESOLVED_ELEMENT` say; a path needs the parameter, `X1:R5:R` (points 12
    and 14; the B5 probes)."""
    text = _netlist(line)
    assert "is not defined" in _messages(_stops(solver, tmp_path, text))
    message = " ".join(item.message for item in _library(text).diagnostics)
    assert "stops on it" in message


@pytest.mark.parametrize("line", [".dc X1:R5 1k 2k 1k", ".step X1:R5 1k 2k 1k\n.op"])
def test_a_path_to_a_device_needs_its_parameter(solver: Solver, tmp_path: Path, line: str) -> None:
    """`X1:R5` without `:R` stops Xyce ("X1:R5 is not defined"): a path target names the
    parameter, `X1:R5:R` (point 14). The library resolves the path to the instance's R5, silently
    (a discrepancies.md row)."""
    text = _netlist(line)
    assert "X1:R5 is not defined" in _messages(_stops(solver, tmp_path, text))
    assert not [item for item in _library(text).diagnostics if item.severity != "info"]


# .OP (XY-OPP-001)


def test_op_runs_and_ignores_extra_fields(solver: Solver, tmp_path: Path) -> None:
    """`.OP` takes no field ([xyce-ref] §2.1.24 p95); Xyce warns "Ignoring extra fields on .OP
    line" and runs, which the library refuses (point 13; a discrepancies.md row)."""
    _ok(solver, tmp_path / "plain", _netlist(".op"))
    result = _ok(solver, tmp_path / "fields", _netlist(".op 1 2"))
    assert any("Ignoring extra fields" in item.message for item in result.warnings)


# .STEP (XY-STP-001)


@pytest.mark.parametrize(
    ("line", "values"),
    [
        (".step R1 1k 2k 1k", [1000, 2000]),
        (".STEP LIN R1 1k 2k 1k", [1000, 2000]),
        (".step dec R1 1k 10k 1", [1000, 10000]),
        (".step oct R1 1k 4k 1", [1000, 2000, 4000]),
        (".step R1 list 1k 2k 3k", [1000, 2000, 3000]),
        (".step R1:R 1k 2k 1k", [1000, 2000]),
        (".step rmod:R 1 2 1", [1, 2]),
        (".step TEMP 0 50 50", [0, 50]),
        (".step p 1k 2k 1k", [1000, 2000]),
        (".step gp 1k 2k 1k", [1000, 2000]),
        (".step X1:R5:R 1k 2k 1k", [1000, 2000]),
    ],
)
def test_step_forms_and_targets(
    solver: Solver, tmp_path: Path, line: str, values: list[float]
) -> None:
    """`[LIN|DEC|OCT] target start stop step` and `target LIST v…` on the targets of `.DC` and a
    path ([xyce-ref] §2.1.36 p155–158; point 14): one plot per step, the values Xyce writes being
    those the line gives from the library's start."""
    text = _netlist(f"{line}\n.op")
    (step,) = _items(text, StepDirective)
    found = [next(iter(item.values())) for item in _steps(_ok(solver, tmp_path, text))]
    assert found == pytest.approx(values)
    first = step.values[0] if step.values else step.start
    assert _number(first) == pytest.approx(values[0])


@pytest.mark.parametrize(
    ("line", "message"),
    [
        (".step param R1 1k 2k 1k", ".STEP line not formatted correctly"),
        (".step R1 {1k} 2k 1k", "Expressions are not supported for STEP"),
    ],
)
def test_step_stops_on(solver: Solver, tmp_path: Path, line: str, message: str) -> None:
    """The `param` keyword and an expression stop Xyce (points 10 and 14), as the library
    refuses."""
    assert message in _messages(_stops(solver, tmp_path, _netlist(f"{line}\n.op")))


def test_a_second_sweep_on_one_line_runs_only_the_last(solver: Solver, tmp_path: Path) -> None:
    """Two sweeps on one `.STEP` line: Xyce silently runs only the second, as the library's
    refusal says (point 14; a discrepancies.md row)."""
    result = _ok(solver, tmp_path, _netlist(".step R1 1k 2k 1k R2 1k 2k 1k\n.op"))
    assert _steps(result) == [{"R2": 1000.0}, {"R2": 2000.0}]


def test_steps_nest_the_first_innermost(solver: Solver, tmp_path: Path) -> None:
    """Several `.STEP` lines nest, the first innermost ([xyce-ref] §2.1.36 p155)."""
    text = _netlist(".step R1 1k 2k 1k\n.step R2 1k 3k 1k\n.tran 1n 2n")
    assert [step["R1"] for step in _steps(_ok(solver, tmp_path, text))] == [1e3, 2e3] * 3


def test_a_repeated_quantity_nests(solver: Solver, tmp_path: Path) -> None:
    """`R1` and `R1:R` are one quantity, which Xyce nests silently: six steps (point 16); the
    library warns (`DUPLICATE_DEFINITION`)."""
    text = _netlist(".step R1 1k 2k 1k\n.step R1:R 1k 3k 1k\n.tran 1n 2n")
    assert len(_steps(_ok(solver, tmp_path, text))) == 6
    assert DiagnosticCode.DUPLICATE_DEFINITION in _codes(text)


def test_a_parameter_target_comes_before_a_device(solver: Solver, tmp_path: Path) -> None:
    """A name that is both a parameter and a device is the parameter (point 14): stepping `R1`
    changes R2, whose value is `{R1}`, and leaves the device R1 at 1k."""
    text = "probe\nV1 1 0 2\nR1 1 2 1k\nR2 2 0 {R1}\n.param R1=3k\n.step R1 1k 2k 1k\n.op\n.end\n"
    plots = _ok(solver, tmp_path, text).plots
    assert [_column(plot, "v(2)")[0] for plot in plots] == pytest.approx([1.0, 4 / 3])


# Which analysis runs (point 15; ANALYSIS_IGNORED)


@pytest.mark.parametrize(
    ("lines", "runs"),
    [
        (".tran 1n 2n\n.ac dec 1 1 10", "AC"),
        (".ac dec 1 1 10\n.tran 1n 2n", "Transient"),
        (".op\n.tran 1n 2n", "Transient"),
        (".tran 1n 2n\n.op", "Transient"),
        (".tran 1n 2n\n.noise v(2) V1 dec 1 1 10", "Noise"),
        (".noise v(2) V1 dec 1 1 10\n.tran 1n 2n", "Transient"),
        (".noise v(2) V1 dec 1 1 10\n.ac dec 1 1 100", "AC"),
        (".dc V1 0 1 1\n.dc R1 1k 2k 1k\n.tran 1n 2n", "Transient"),
    ],
)
def test_only_the_last_analysis_runs(solver: Solver, tmp_path: Path, lines: str, runs: str) -> None:
    """Of `.TRAN`, `.AC`, `.DC` and `.NOISE` Xyce runs the last line; `.OP` gives way to any of
    them (points 15 and 31). The library warns `ANALYSIS_IGNORED` on every other analysis line."""
    text = _netlist(lines)
    (plot,) = _ok(solver, tmp_path, text).plots
    assert plot.name.startswith(runs)
    ignored = _codes(text).count(DiagnosticCode.ANALYSIS_IGNORED)
    assert ignored == lines.count("\n")


def test_the_last_of_two_like_analyses_wins(solver: Solver, tmp_path: Path) -> None:
    """Two `.TRAN` or two `.AC` lines: the last runs (point 15)."""
    tran = _ok(solver, tmp_path / "tran", _netlist(".tran 1n 2n\n.tran 1n 3n")).plot("Transient")
    assert _column(tran, "time")[-1] == pytest.approx(3e-9)
    ac = _ok(solver, tmp_path / "ac", _netlist(".ac dec 1 1 10\n.ac dec 1 1 100")).plot("AC")
    assert _column(ac, "frequency")[-1] == pytest.approx(100)


def test_two_op_lines_run_and_are_not_reported(solver: Solver, tmp_path: Path) -> None:
    text = _netlist(".op\n.op")
    assert len(_ok(solver, tmp_path, text).plots) == 1
    assert DiagnosticCode.ANALYSIS_IGNORED not in _codes(text)


def test_dc_lines_join_into_one_sweep(solver: Solver, tmp_path: Path) -> None:
    """`.DC V1`, `.TRAN`, `.DC R1`: Xyce runs one DC analysis of both sweeps, the first line
    innermost, as `ANALYSIS_IGNORED`'s message on the second `.DC` says (point 15; the B5
    probes)."""
    text = _netlist(".dc V1 0 1 1\n.tran 1n 2n\n.dc R1 1k 2k 1k")
    plot = _ok(solver, tmp_path, text).plot("DC Sweep")
    assert _column(plot, "sweep") == pytest.approx([0, 1, 0, 1])
    assert plot.name.index("V1") < plot.name.index("R1")
    messages = [
        d.message for d in _library(text).diagnostics if d.code is DiagnosticCode.ANALYSIS_IGNORED
    ]
    assert any("joins the `.DC` on line" in message for message in messages)


def test_a_print_is_checked_against_the_first_analysis(solver: Solver, tmp_path: Path) -> None:
    """Xyce checks a `.PRINT` line's type against the first analysis line, though it runs the
    last: `.TRAN`, `.AC`, `.PRINT AC` stops ("Analysis type TRAN and print type AC are
    inconsistent"), and `.PRINT TRAN` passes the check, runs AC and prints nothing. The library
    reads both and warns `ANALYSIS_IGNORED` on the `.TRAN` (a discrepancies.md row; the B5
    probes)."""
    text = _netlist(".tran 1n 2n\n.ac dec 1 1 10\n.print ac v(2)")
    result = run(solver, tmp_path / "ac", text, mode="print")
    assert result.returncode != 0
    assert "Analysis type TRAN and print type AC are inconsistent" in _messages(result)
    assert DiagnosticCode.ANALYSIS_IGNORED in _codes(text)
    text = _netlist(".tran 1n 2n\n.ac dec 1 1 10\n.print tran v(2)")
    result = run(solver, tmp_path / "tran", text, mode="print")
    assert result.ok and result.prn_bytes is None


# .STEP with other directives (point 16; STEP_IGNORED, STEPS_WITH_OP, STEPPED_ANALYSIS_FIELD)


def test_two_steps_with_op_crash_xyce(solver: Solver, tmp_path: Path) -> None:
    """Two `.STEP` lines with `.OP` as the analysis crash Xyce 7.10 ("Analysis mode 4 is not
    available", a non-zero exit), as `STEPS_WITH_OP` warns; with one step, or with `.TRAN` or
    `.DC` as the analysis, it runs."""
    text = _netlist(".step R1 1k 2k 1k\n.step R2 1k 2k 1k\n.op")
    result = run(solver, tmp_path / "op", text)
    assert result.returncode != 0
    assert DiagnosticCode.STEPS_WITH_OP in _codes(text)
    for name, analysis in (("tran", ".tran 1n 2n"), ("dc", ".dc V1 0 1 1")):
        other = _netlist(f".step R1 1k 2k 1k\n.step R2 1k 2k 1k\n{analysis}")
        assert len(_ok(solver, tmp_path / name, other).plots) == 4
        assert DiagnosticCode.STEPS_WITH_OP not in _codes(other)
    one = _netlist(".step R1 1k 2k 1k\n.op")
    assert len(_ok(solver, tmp_path / "one", one).plots) == 2


@pytest.mark.parametrize("order", ["table-first", "table-last"])
def test_a_data_step_drops_the_other_steps(solver: Solver, tmp_path: Path, order: str) -> None:
    """A `.STEP DATA=` line makes Xyce ignore every other `.STEP` line, as `STEP_IGNORED` says
    (point 16): two steps, the table's rows."""
    table = ".data t\n+ r1 r2\n+ 1k 1k\n+ 1k 3k\n.enddata\n.step data=t\n"
    other = ".step R1 1k 2k 1k\n"
    lines = (table + other if order == "table-first" else other + table) + ".dc V1 2 2 1"
    text = _netlist(lines)
    steps = [
        {k: v for k, v in step.items() if k != "V1"} for step in _steps(_ok(solver, tmp_path, text))
    ]
    assert steps == [
        {"R1": 1000.0, "R2": 1000.0},
        {"R1": 1000.0, "R2": 3000.0},
    ]
    assert DiagnosticCode.STEP_IGNORED in _codes(text)


def test_a_stepped_parameter_in_a_tran_field_is_read_once(solver: Solver, tmp_path: Path) -> None:
    """A `.TRAN` field that names a stepped parameter is read once (point 10), as
    `STEPPED_ANALYSIS_FIELD` warns: every step ends at the first value's tstop, 2 ns, not 6 ns."""
    text = _netlist(".step p 1k 3k 2k\n.tran 1n {p*2e-12}")
    plots = _ok(solver, tmp_path, text).plots
    assert len(plots) == 2
    assert [_column(plot, "time")[-1] for plot in plots] == pytest.approx([2e-9, 2e-9])
    assert DiagnosticCode.STEPPED_ANALYSIS_FIELD in _codes(text)
