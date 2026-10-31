"""ngspice 47 checks of edited netlists and the M6 planning probes (M6 T11, T8 tier).

Light checks (the closed-form results of every edit operation are in
``test_ngspice_edit_results.py``, M7): an edited value and an added ``.param`` move ``v(out)``
as the closed form says, an upserted ``.tran`` runs, an unedited save gives the same results, and
the directive and include behavior that decision 0007 relies on (m6-tasks.md section 7).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import Dialect, Netlist
from tests.support.ngspice import Run, run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ngspice")

_DIVIDER = "divider\nV1 in 0 DC 3\nR1 in out 1k\nR2 out 0 1k\n.op\n.end\n"


def _ran(result: Run) -> Run:
    assert result.ok, result.log
    return result


def _rows(result: Run) -> dict[str, list[int]]:
    """The number of points of each plot, by plot name."""
    rows: dict[str, list[int]] = {}
    for plot in result.plots:
        rows.setdefault(plot.name, []).append(len(plot.rows))
    return rows


def _divider() -> Netlist:
    return Netlist.from_text(_DIVIDER, dialect=Dialect.NGSPICE)


def test_an_edited_value_moves_the_output(solver: Solver, tmp_path: Path) -> None:
    edited = _divider().set_value("R2", "2k")
    result = _ran(run(solver, tmp_path, edited))
    assert result.voltage("out") == pytest.approx(3 * 2e3 / (1e3 + 2e3))


def test_an_added_param_moves_the_output(solver: Solver, tmp_path: Path) -> None:
    netlist = _divider()
    for rtop, folder in (("3k", "a"), ("500", "b")):
        with netlist.batch() as batch:
            batch.set_formula("R1", "rtop")
            batch.params.set("rtop", rtop)
        result = _ran(run(solver, tmp_path / folder, batch.result))
        top = float(rtop.removesuffix("k")) * (1e3 if rtop.endswith("k") else 1)
        assert result.voltage("out") == pytest.approx(3 * 1e3 / (top + 1e3))


def test_an_upserted_tran_runs(solver: Solver, tmp_path: Path) -> None:
    edited = _divider().directives.set(".tran 1u 20u").directives.add(".print tran v(out)")
    rows = _rows(_ran(run(solver, tmp_path, edited)))
    assert sorted(rows) == ["Operating Point", "Transient Analysis"]
    assert "v(out)" in _ran(run(solver, tmp_path, edited)).plot("Transient").variables


def test_an_unedited_save_gives_identical_results(solver: Solver, tmp_path: Path) -> None:
    original = _ran(run(solver, tmp_path / "original", _DIVIDER))
    saved = _ran(run(solver, tmp_path / "saved", _divider()))
    assert (tmp_path / "saved" / "probe.cir").read_bytes() == _DIVIDER.encode()
    assert saved.voltage("out") == original.voltage("out") == pytest.approx(1.5)


def test_a_continued_tran_and_an_added_control_block_run(solver: Solver, tmp_path: Path) -> None:
    netlist = _divider()
    with netlist.batch() as batch:
        batch.directives.remove(netlist.lines[-2])  # the .op
        batch.directives.set([".tran 1u 20u", "+ 0 1u"])
        batch.directives.add([".control", "run", "print v(out)", ".endc"])
    result = _ran(run(solver, tmp_path, batch.result))
    assert list(_rows(result)) == ["Transient Analysis"]  # the .op line was removed
    assert result.plot("Transient").real("time")[-1] == pytest.approx(20e-6)  # it reaches tstop
    assert "v(out) = " in result.log or "v(out)" in result.log  # the control block printed


# Probes of m6-tasks.md section 7 (decision 0007 items 7 and 9).

# Without -r, ngspice 47 in batch mode runs no .tran without a .print, .plot or .fourier line
# (exit 1); the shared helper always passes -r (decision 0008), so .print is kept for that case.
_TRAN = "probe\nV1 in 0 DC 3\nR1 in out 1k\nR2 out 0 1k\nC1 out 0 1n\n.print tran v(out)\n"


def test_two_tran_lines_give_two_runs_with_one_setting(solver: Solver, tmp_path: Path) -> None:
    result = _ran(run(solver, tmp_path, _TRAN + ".tran 1u 5u\n.tran 1u 20u\n.end\n"))
    rows = _rows(result)["Transient Analysis"]
    assert len(rows) == 2 and rows[0] == rows[1], rows


def test_two_op_lines_give_two_runs(solver: Solver, tmp_path: Path) -> None:
    result = _ran(run(solver, tmp_path, _DIVIDER.replace(".op\n", ".op\n.op\n")))
    assert _rows(result) == {"Operating Point": [1, 1]}


def test_op_and_tran_both_run(solver: Solver, tmp_path: Path) -> None:
    rows = _rows(_ran(run(solver, tmp_path, _TRAN + ".op\n.tran 1u 2u\n.end\n")))
    assert rows["Operating Point"] == [1] and len(rows["Transient Analysis"]) == 1


def test_the_last_temp_wins(solver: Solver, tmp_path: Path) -> None:
    result = run(solver, tmp_path, _DIVIDER.replace(".op\n", ".temp 50\n.temp 100\n.op\n"))
    assert "Doing analysis at TEMP = 100.000000" in _ran(result).log


def test_options_lines_merge(solver: Solver, tmp_path: Path) -> None:
    text = _DIVIDER.replace(".op\n", ".options temp=40\n.options tnom=30\n.op\n")
    result = _ran(run(solver, tmp_path, text))
    assert "Doing analysis at TEMP = 40.000000 and TNOM = 30.000000" in result.log


def test_a_relative_include_resolves_from_the_netlist_folder(
    solver: Solver, tmp_path: Path
) -> None:
    folder, elsewhere = tmp_path / "netlist", tmp_path / "elsewhere"
    folder.mkdir()
    elsewhere.mkdir()
    (folder / "harness.inc").write_bytes(b"R2 out 0 2k\n")
    netlist = Netlist.from_text(
        "probe\nV1 in 0 DC 3\nR1 in out 1k\n.op\n.end\n", dialect=Dialect.NGSPICE
    ).add_include("harness.inc")
    result = _ran(run(solver, folder, netlist, cwd=elsewhere))
    assert result.voltage("out") == pytest.approx(2.0)
