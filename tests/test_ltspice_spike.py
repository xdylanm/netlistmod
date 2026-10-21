from __future__ import annotations

from pathlib import Path
from shutil import copyfile

import pytest

from netlistmod import SourceText
from tests.support.solvers import Solver, run_ltspice

CORPUS = Path(__file__).parent / "corpus" / "ltspice" / "m0_export_candidate"
ENCODING_CORPUS = Path(__file__).parent / "corpus" / "ltspice" / "encoding_samples"


def test_ltspice_encoding_samples_record_observed_encodings() -> None:
    cp1252_schematic = SourceText.read(ENCODING_CORPUS / "encoding_cp1252.asc")
    utf8_schematic = SourceText.read(ENCODING_CORPUS / "encoding_utf8.asc")
    cp1252_export = SourceText.read(ENCODING_CORPUS / "encoding_cp1252.net")
    utf8_export = SourceText.read(ENCODING_CORPUS / "encoding_utf8.net")

    assert cp1252_schematic.encoding == "cp1252"
    assert "\u00b5" in cp1252_schematic.text
    assert "\u00b0" in cp1252_schematic.text
    assert utf8_schematic.encoding == "utf-8"
    assert "\u03a9" in utf8_schematic.text
    assert cp1252_export.encoding == "utf-8"
    assert not cp1252_export.bom
    assert "\u00b5" in cp1252_export.text
    assert "\u00b0" in cp1252_export.text
    assert utf8_export.encoding == "utf-8"
    assert "\u00c2\u00b5" in utf8_export.text
    assert "\u00ce\u00a9" in utf8_export.text
    assert "\u00c2\u00b0" in utf8_export.text


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
