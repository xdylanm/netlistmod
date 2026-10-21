from __future__ import annotations

from pathlib import Path
from shutil import copyfile

import pytest

from tests.support.solvers import Solver, run_ltspice

CORPUS = Path(__file__).parent / "corpus" / "ltspice" / "m0_export_candidate"


@pytest.mark.solver("ltspice")
def test_ltspice_batch_runs_headlessly(solver: Solver, tmp_path: Path) -> None:
    source_directory = tmp_path / "input"
    source_directory.mkdir()
    netlist = source_directory / "batch_smoke.cir"
    netlist.write_text(
        "M0 LTspice batch smoke test\nV1 in 0 1\nR1 in 0 1k\n.op\n.end\n",
        encoding="ascii",
    )

    result = run_ltspice(solver, netlist, working_directory=tmp_path)

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert (source_directory / "batch_smoke.log").is_file()
    assert (source_directory / "batch_smoke.raw").is_file()


@pytest.mark.solver("ltspice")
def test_ltspice_exports_authored_schematic_headlessly(solver: Solver, tmp_path: Path) -> None:
    schematic = tmp_path / "export_smoke.asc"
    copyfile(CORPUS / "export_smoke.asc", schematic)

    result = run_ltspice(solver, schematic, export_netlist=True)

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert (tmp_path / "export_smoke.net").is_file()
    assert b"R1" in (tmp_path / "export_smoke.net").read_bytes()
