"""The LTspice export workflow (M8 T8, decision 14): re-export each schematic and compare.

This runs the ``-netlist`` switch on every run and shows LTspice version drift. The exports are
compared after the one normalisation ``docs/usage/ltspice-export.md`` describes: the absolute path
in the first comment becomes the file name.
"""

from __future__ import annotations

import json
from pathlib import Path
from shutil import copyfile

import pytest

from tests.support.solvers import Solver, run_ltspice

FAMILY = Path(__file__).parent / "corpus" / "ltspice" / "contributed_examples"
SCHEMATICS = sorted(path.with_suffix(".asc") for path in FAMILY.glob("*.net"))
_BUNDLED_LIBRARY = "\\lib\\cmp\\"
_SETTINGS_HELP = (
    "turn off Default Devices and Default Libraries (DefaultDeviceModels and "
    "DefaultDeviceLibraries in %APPDATA%\\LTspice.ini) and close LTspice: a running LTspice "
    "writes the setting only when it exits (docs/usage/ltspice-export.md)"
)


def normalised(export: bytes, schematic: str) -> bytes:
    """The export with its first comment, the absolute schematic path, as the file name."""
    first, separator, rest = export.partition(b"\n")
    assert first.startswith(b"* ") and first.rstrip().endswith(schematic.encode()), first
    return b"* " + schematic.encode() + separator + rest


def check_export_settings(export: bytes, schematic: str) -> None:
    """Fail with the explanation if the export pulls in LTspice's bundled device library."""
    for line in export.decode("utf-8").splitlines():
        if line.lower().startswith(".lib") and _BUNDLED_LIBRARY in line:
            pytest.fail(f"{schematic}: the export has `{line}`: {_SETTINGS_HELP}", pytrace=False)


def test_normalisation_replaces_only_the_first_line() -> None:
    export = b"* C:\\tmp\\x\\a.asc\n* Generated\nR1 a 0 1\n"
    assert normalised(export, "a.asc") == b"* a.asc\n* Generated\nR1 a 0 1\n"


def test_the_settings_check_explains_a_bundled_library_line() -> None:
    check_export_settings(b".lib C:\\mine\\lib.inc\n", "a.asc")
    with pytest.raises(pytest.fail.Exception, match="Default Libraries"):
        check_export_settings(b".lib C:\\Users\\x\\LTspice\\lib\\cmp\\standard.dio\n", "a.asc")


def test_every_export_has_its_schematic_in_the_family() -> None:
    manifest = json.loads((FAMILY / "manifest.json").read_text(encoding="utf-8"))
    assert SCHEMATICS
    for schematic in SCHEMATICS:
        assert schematic.name in manifest["fixtures"]
    assert {path.stem for path in FAMILY.glob("*.asc")} - {p.stem for p in SCHEMATICS} == {
        "r_subckt"
    }


@pytest.mark.solver("ltspice")
@pytest.mark.parametrize("schematic", SCHEMATICS, ids=lambda path: path.stem)
def test_a_reexport_matches_the_committed_netlist(
    solver: Solver, schematic: Path, tmp_path: Path
) -> None:
    for path in FAMILY.iterdir():
        if path.suffix in {".asc", ".asy"}:
            copyfile(path, tmp_path / path.name)
    result = run_ltspice(solver, tmp_path / schematic.name, export_netlist=True)
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    export = (tmp_path / schematic.with_suffix(".net").name).read_bytes()
    check_export_settings(export, schematic.name)
    committed = schematic.with_suffix(".net").read_bytes()
    assert normalised(export, schematic.name) == committed, (
        f"{schematic.name}: LTspice {solver.version} writes a different netlist than the "
        "committed export; re-check docs/usage/ltspice-export.md after an upgrade"
    )
