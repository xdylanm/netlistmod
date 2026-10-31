"""ngspice 47 checks of edited netlists and the M6 planning probes (M6 T11, T8 tier).

Light checks (M7 does the full set): an edited value and an added ``.param`` move ``v(out)`` as
the closed form says, an upserted ``.tran`` runs, an unedited save gives the same results, and
the directive and include behavior that decision 0007 relies on (m6-tasks.md section 7).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from netlistmod import Dialect, Netlist
from tests.support.solvers import Solver, run_ngspice

pytestmark = pytest.mark.solver("ngspice")

_DIVIDER = "divider\nV1 in 0 DC 3\nR1 in out 1k\nR2 out 0 1k\n.op\n.end\n"


def _run(solver: Solver, folder: Path, netlist: Netlist | str, *, cwd: Path | None = None) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "probe.cir"
    if isinstance(netlist, Netlist):
        netlist.save(path)
    else:
        path.write_bytes(netlist.encode("utf-8"))
    result = run_ngspice(solver, path, cwd=cwd)
    log = (folder / "ngspice.log").read_text(encoding="utf-8")
    assert result.returncode == 0, log
    assert "error" not in log.lower(), log
    return log


def _voltage(log: str, node: str) -> float:
    match = re.search(rf"(?m)^\s*{re.escape(node)}\s+([-+0-9.eE]+)\s*$", log)
    assert match is not None, log
    return float(match.group(1))


def _rows(log: str) -> list[int]:
    return [int(rows) for rows in re.findall(r"No\. of Data Rows : (\d+)", log)]


def _divider() -> Netlist:
    return Netlist.from_text(_DIVIDER, dialect=Dialect.NGSPICE)


def test_an_edited_value_moves_the_output(solver: Solver, tmp_path: Path) -> None:
    edited = _divider().set_value("R2", "2k")
    log = _run(solver, tmp_path, edited)
    assert _voltage(log, "out") == pytest.approx(3 * 2e3 / (1e3 + 2e3))


def test_an_added_param_moves_the_output(solver: Solver, tmp_path: Path) -> None:
    netlist = _divider()
    for rtop, folder in (("3k", "a"), ("500", "b")):
        with netlist.batch() as batch:
            batch.set_formula("R1", "rtop")
            batch.params.set("rtop", rtop)
        log = _run(solver, tmp_path / folder, batch.result)
        top = float(rtop.removesuffix("k")) * (1e3 if rtop.endswith("k") else 1)
        assert _voltage(log, "out") == pytest.approx(3 * 1e3 / (top + 1e3))


def test_an_upserted_tran_runs(solver: Solver, tmp_path: Path) -> None:
    edited = _divider().directives.set(".tran 1u 20u").directives.add(".print tran v(out)")
    log = _run(solver, tmp_path, edited)
    assert len(_rows(log)) == 2  # .op and .tran
    assert re.search(r"(?m)^Index\s+time\s+v\(out\)", log), log


def test_an_unedited_save_gives_identical_results(solver: Solver, tmp_path: Path) -> None:
    original = _run(solver, tmp_path / "original", _DIVIDER)
    saved = _run(solver, tmp_path / "saved", _divider())
    assert (tmp_path / "saved" / "probe.cir").read_bytes() == _DIVIDER.encode()
    assert _voltage(saved, "out") == _voltage(original, "out") == pytest.approx(1.5)


# Probes of m6-tasks.md section 7 (decision 0007 items 7 and 9).

# In batch mode ngspice 47 runs no .tran without a .print, .plot or .fourier line (exit 1).
_TRAN = "probe\nV1 in 0 DC 3\nR1 in out 1k\nR2 out 0 1k\nC1 out 0 1n\n.print tran v(out)\n"


def test_two_tran_lines_give_two_runs_with_one_setting(solver: Solver, tmp_path: Path) -> None:
    log = _run(solver, tmp_path, _TRAN + ".tran 1u 5u\n.tran 1u 20u\n.end\n")
    rows = _rows(log)
    assert len(rows) == 2 and rows[0] == rows[1], rows


def test_two_op_lines_give_two_runs(solver: Solver, tmp_path: Path) -> None:
    assert _rows(_run(solver, tmp_path, _DIVIDER.replace(".op\n", ".op\n.op\n"))) == [1, 1]


def test_op_and_tran_both_run(solver: Solver, tmp_path: Path) -> None:
    rows = _rows(_run(solver, tmp_path, _TRAN + ".op\n.tran 1u 2u\n.end\n"))
    assert len(rows) == 2 and rows[0] == 1


def test_the_last_temp_wins(solver: Solver, tmp_path: Path) -> None:
    log = _run(solver, tmp_path, _DIVIDER.replace(".op\n", ".temp 50\n.temp 100\n.op\n"))
    assert "Doing analysis at TEMP = 100.000000" in log


def test_options_lines_merge(solver: Solver, tmp_path: Path) -> None:
    text = _DIVIDER.replace(".op\n", ".options temp=40\n.options tnom=30\n.op\n")
    log = _run(solver, tmp_path, text)
    assert "Doing analysis at TEMP = 40.000000 and TNOM = 30.000000" in log


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
    log = _run(solver, folder, netlist, cwd=elsewhere)
    assert _voltage(log, "out") == pytest.approx(2.0)
