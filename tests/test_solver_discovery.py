from __future__ import annotations

from pathlib import Path

import pytest

from tests.support import solvers


@pytest.fixture(autouse=True)
def fake_solver_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(solvers, "_version_string", lambda _name, _path: "test-version")


def test_environment_path_takes_precedence_over_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = tmp_path / "configured.exe"
    on_path = tmp_path / "ngspice.exe"
    configured.touch()
    on_path.touch()
    monkeypatch.setattr(solvers.shutil, "which", lambda *_args, **_kwargs: str(on_path))

    found = solvers.discover_solver(
        "ngspice", environ={"NGSPICE_EXE": str(configured)}, search_path=""
    )

    assert found is not None
    assert found.path == configured
    assert found.version == "test-version"


@pytest.mark.parametrize("executable", ["ngspice_con.exe", "ngspice.exe"])
def test_path_discovery_supports_ngspice_executables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, executable: str
) -> None:
    binary = tmp_path / executable
    binary.touch()
    monkeypatch.setattr(
        solvers.shutil,
        "which",
        lambda name, path=None: str(binary) if name == executable else None,
    )

    found = solvers.discover_solver("ngspice", environ={}, search_path="")

    assert found is not None
    assert found.path == binary


def test_default_install_location_is_searched(tmp_path: Path) -> None:
    binary = tmp_path / "Programs" / "ADI" / "LTspice" / "LTspice.exe"
    binary.parent.mkdir(parents=True)
    binary.touch()

    found = solvers.discover_solver(
        "ltspice", environ={"LOCALAPPDATA": str(tmp_path)}, search_path=""
    )

    assert found is not None
    assert found.path == binary


def test_versioned_ngspice_install_location_is_searched(tmp_path: Path) -> None:
    binary = (
        tmp_path / "Programs" / "ngspice" / "ngspice-47_64" / "Spice64" / "bin" / "ngspice_con.exe"
    )
    binary.parent.mkdir(parents=True)
    binary.touch()

    found = solvers.discover_solver(
        "ngspice", environ={"LOCALAPPDATA": str(tmp_path)}, search_path=""
    )

    assert found is not None
    assert found.path == binary


def test_missing_solver_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(solvers.shutil, "which", lambda *_args, **_kwargs: None)

    assert solvers.discover_solver("ngspice", environ={}, search_path="") is None


def test_unknown_solver_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported solver"):
        solvers.discover_solver("unknown")  # type: ignore[arg-type]


def test_xyce_environment_path_is_used(tmp_path: Path) -> None:
    configured = tmp_path / "xyce.exe"
    configured.touch()

    found = solvers.discover_solver("xyce", environ={"XYCE_EXE": str(configured)}, search_path="")

    assert found is not None
    assert (found.name, found.path) == ("xyce", configured)


def test_the_newest_xyce_install_location_is_searched_first(tmp_path: Path) -> None:
    for version in ("7.9", "7.10"):
        binary = tmp_path / f"XyceNF_{version}" / "bin" / "Xyce.exe"
        binary.parent.mkdir(parents=True)
        binary.touch()

    found = solvers.discover_solver("xyce", environ={"PROGRAMFILES": str(tmp_path)}, search_path="")

    assert found is not None
    assert found.path == tmp_path / "XyceNF_7.10" / "bin" / "Xyce.exe"


def test_xyce_version_is_read_from_the_version_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(solvers, "xyce_version_line", lambda _path: "XyceNF Release 7.10.0")
    assert solvers._xyce_version(Path("Xyce.exe")) == "7.10.0"
    monkeypatch.setattr(solvers, "xyce_version_line", lambda _path: "something else")
    with pytest.raises(RuntimeError, match="Unexpected Xyce version line"):
        solvers._xyce_version(Path("Xyce.exe"))
