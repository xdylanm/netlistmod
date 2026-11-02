"""The shared raw reader and the LTspice harness on synthetic files (M8 T9; decision 0009 item 2).

No LTspice raw file or log is committed: these strings are written here, in the layout m8-tasks.md
section 3 describes, with values chosen for the test. No solver is needed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import Dialect, Netlist
from tests.support.ltspice import Run, ensure_runs, run, with_stubs
from tests.support.raw import RawFileError, read_raw, sweeps, without_title_and_date
from tests.support.solvers import Solver, run_ltspice


def _raw(flags: str, plot: str, variables: list[tuple[str, str]], rows: list[list[str]]) -> bytes:
    lines = [
        r"Title: C:\work\folder\probe.cir",
        "Date: Mon Jan  1 00:00:00 2026",
        f"Plotname: {plot}",
        f"Flags: {flags}",
        f"No. Variables: {len(variables)}",
        f"No. Points:          {len(rows)}",
        "Offset:    0.0000000000000000e+00",
        "Command: synthetic",
        "Variables:",
    ]
    lines += [f"\t{i}\t{name}\t{kind}" for i, (name, kind) in enumerate(variables)]
    lines.append("Values:")
    for index, row in enumerate(rows):
        lines.append(f"{index}\t\t{row[0]}")
        lines += [f"\t{value}" for value in row[1:]]
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


_OP = _raw(
    "real",
    "Operating Point",
    [("V(in)", "voltage"), ("V(out)", "voltage"), ("I(R1)", "device_current")],
    [["3.0", "1.5", "1.5e-3"]],
)


def _run(raw: bytes | None = _OP, *, code: int = 0, log: str = "", op: bytes | None = None) -> Run:
    return Run(code, log, Path("probe.cir"), raw, op)


def test_an_operating_point_with_the_ltspice_header_keys() -> None:
    (plot,) = read_raw(_OP)
    assert plot.title == r"C:\work\folder\probe.cir"
    assert (plot.name, plot.flags) == ("Operating Point", ("real",))
    assert plot.kinds == ("voltage", "voltage", "device_current")
    assert plot.real("v(OUT)") == (1.5,)  # names compare case-insensitively


def test_a_complex_plot() -> None:
    (plot,) = read_raw(
        _raw(
            "complex forward linear",
            "AC Analysis",
            [("frequency", "frequency"), ("V(out)", "voltage")],
            [["1e2,0", "0.5,-0.25"]],
        )
    )
    assert plot.column("V(out)") == (complex(0.5, -0.25),)
    with pytest.raises(RawFileError, match="complex"):
        plot.real("V(out)")


def test_a_stepped_operating_point_has_one_row_per_step() -> None:
    (plot,) = read_raw(
        _raw(
            "real stepped",
            "Operating Point",
            [("x", "param"), ("V(out)", "voltage")],
            [["1e3", "1.5"], ["3e3", "2.25"]],
        )
    )
    assert plot.real("x") == (1e3, 3e3)
    assert plot.real("V(out)") == (1.5, 2.25)


def test_sweeps_split_a_stepped_plot_where_the_axis_returns() -> None:
    (plot,) = read_raw(
        _raw(
            "real forward stepped",
            "Transient Analysis",
            [("time", "time"), ("V(out)", "voltage")],
            [["0", "0"], ["1", "1"], ["2", "2"], ["0", "0"], ["2", "4"]],
        )
    )
    assert [len(group) for group in sweeps(plot)] == [3, 2]
    assert sweeps(plot)[1][1] == (2.0, 4.0)


def test_title_and_date_are_dropped_for_the_comparison() -> None:
    stripped = without_title_and_date(_OP)
    assert b"Title:" not in stripped and b"Date:" not in stripped
    assert len(_OP.splitlines()) - len(stripped.splitlines()) == 2
    assert b"Offset:" in stripped


def test_a_binary_file_fails_loudly() -> None:
    with pytest.raises(RawFileError, match="binary raw file"):
        read_raw(_OP.replace(b"Values:", b"Binary:"))


def test_a_run_reads_both_raw_files() -> None:
    ac = _raw(
        "complex forward linear",
        "AC Analysis",
        [("frequency", "frequency"), ("V(out)", "voltage")],
        [["1e2,0", "0.5,0"]],
    )
    result = _run(ac, op=_OP)
    assert [plot.name for plot in result.plots] == ["AC Analysis", "Operating Point"]
    assert result.voltage("out") == 1.5
    assert result.comparable == (without_title_and_date(ac), without_title_and_date(_OP))


def test_a_run_without_files_has_no_plots() -> None:
    result = _run(None, code=1, log="No analysis specified.")
    assert result.plots == () and result.comparable == (None, None)
    assert not result.ok
    with pytest.raises(AssertionError, match="No analysis specified"):
        result.plot("Operating Point")


@pytest.mark.parametrize(
    ("code", "log", "ok"),
    [
        (0, "Total elapsed time\n", True),
        (1, "Total elapsed time\n", False),
        (0, r"C:\work\probe.cir(5): Expected device instantiation here." + "\n", False),
    ],
)
def test_a_run_fails_on_its_exit_code_or_an_error_line(code: int, log: str, ok: bool) -> None:
    assert _run(code=code, log=log).ok is ok


def _ltspice(text: str) -> Netlist:
    return Netlist.from_text(text, dialect=Dialect.LTSPICE)


def test_ensure_runs_adds_an_op_line_only_without_an_analysis() -> None:
    bare = _ltspice("t\nV1 a 0 1\nR1 a 0 1k\n.end\n")
    assert ensure_runs(bare).text == "t\nV1 a 0 1\nR1 a 0 1k\n.op\n.end\n"
    for line in (".tran 1m", ".noise V(a) V1 dec 1 1 10", ".tf V(a) V1"):
        netlist = _ltspice(f"t\nV1 a 0 1\nR1 a 0 1k\n{line}\n.end\n")
        assert ensure_runs(netlist) is netlist


def test_stubs_replace_the_include_in_an_ltspice_netlist(tmp_path: Path) -> None:
    stub = tmp_path / "models_stub.inc"
    stub.write_text("* models\n", encoding="utf-8")
    folder = tmp_path / "run"
    folder.mkdir()
    netlist = _ltspice("t\n.inc models.inc\n.lib other.lib\nV1 a 0 1\n.op\n.end\n")
    stubbed = with_stubs(netlist, folder, {"other.lib": stub})
    assert ".lib models_stub.inc\n" in stubbed.text
    assert (folder / "models_stub.inc").is_file()


def test_a_harness_or_stubs_need_a_netlist(tmp_path: Path) -> None:
    solver = Solver("ltspice", tmp_path / "unused.exe", "0")
    with pytest.raises(ValueError, match="need a Netlist"):
        run(solver, tmp_path, "t\n.end\n", harness="* h\n")


def test_the_ltspice_runner_rejects_another_solver(tmp_path: Path) -> None:
    solver = Solver("ngspice", tmp_path / "unused.exe", "0")
    with pytest.raises(ValueError, match="Expected LTspice"):
        run_ltspice(solver, tmp_path / "probe.cir", ascii_raw=True)


def test_require_solver_may_be_repeated(request: pytest.FixtureRequest) -> None:
    assert isinstance(request.config.getoption("--require-solver"), list)
