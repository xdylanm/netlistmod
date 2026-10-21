from __future__ import annotations

from pathlib import Path
from shutil import copyfile

import pytest

from tests.support.solvers import Solver, run_ngspice

CORPUS = Path(__file__).parent / "corpus" / "ngspice" / "kicad_basic"


@pytest.mark.solver("ngspice")
@pytest.mark.parametrize(
    ("fixture", "analysis"),
    [
        ("ac_basic_rc_lpf.cir", ".ac dec 10 1 100k\n.print ac v(/vout)"),
        ("dc_basic_r_divider.cir", ".op"),
        ("dc_basic_r_divider_decimal_vals.cir", ".op"),
    ],
)
def test_ngspice_batch_accepts_corpus_with_analysis(
    solver: Solver, tmp_path: Path, fixture: str, analysis: str
) -> None:
    netlist = tmp_path / fixture
    copyfile(CORPUS / fixture, netlist)
    content = netlist.read_bytes()
    assert content.count(b".end") == 1
    netlist.write_bytes(content.replace(b".end", f"{analysis}\n.end".encode("ascii")))

    result = run_ngspice(solver, netlist)

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert (tmp_path / "ngspice.log").is_file()


@pytest.mark.solver("ngspice")
def test_ngspice_batch_reports_missing_analysis(solver: Solver, tmp_path: Path) -> None:
    netlist = tmp_path / "dc_basic_r_divider.cir"
    copyfile(CORPUS / netlist.name, netlist)

    result = run_ngspice(solver, netlist)
    log = (tmp_path / "ngspice.log").read_text(encoding="utf-8")

    assert result.returncode != 0
    assert "no simulations run" in log.lower()
