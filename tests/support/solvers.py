"""Local-only discovery and execution helpers for SPICE solvers."""

from __future__ import annotations

import ctypes
import functools
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SolverName = Literal["ngspice", "ltspice"]


@dataclass(frozen=True, slots=True)
class Solver:
    name: SolverName
    path: Path
    version: str


def _executable_names(name: SolverName) -> tuple[str, ...]:
    if name == "ngspice":
        return ("ngspice_con.exe", "ngspice.exe", "ngspice")
    return ("LTspice.exe", "XVIIx64.exe", "ltspice")


def _default_paths(name: SolverName, environ: Mapping[str, str]) -> list[Path]:
    roots = [
        Path(environ[key])
        for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
        if environ.get(key)
    ]
    paths: list[Path] = []
    if name == "ngspice":
        for root in roots:
            for installation_root in (
                root / "Programs" / "ngspice",
                root / "ngspice",
            ):
                if installation_root.is_dir():
                    for executable in _executable_names(name):
                        paths.extend(sorted(installation_root.glob(f"**/{executable}")))
        for root in roots:
            paths.extend(
                root / relative
                for relative in (
                    "Programs/ngspice/bin/ngspice_con.exe",
                    "Programs/ngspice/bin/ngspice.exe",
                    "ngspice/bin/ngspice_con.exe",
                    "ngspice/bin/ngspice.exe",
                )
            )
    else:
        for root in roots:
            paths.extend(
                root / relative
                for relative in (
                    "Programs/ADI/LTspice/LTspice.exe",
                    "ADI/LTspice/LTspice.exe",
                    "Programs/LTspice/LTspice.exe",
                    "LTspice/LTspice.exe",
                )
            )
    return paths


def _candidate_paths(
    name: SolverName,
    environ: Mapping[str, str],
    search_path: str | None,
) -> list[Path]:
    env_key = "NGSPICE_EXE" if name == "ngspice" else "LTSPICE_EXE"
    candidates: list[Path] = []
    configured = environ.get(env_key)
    if configured:
        configured_path = Path(configured).expanduser()
        if name == "ngspice":
            if configured_path.name.lower() == "ngspice.exe":
                candidates.append(configured_path.with_name("ngspice_con.exe"))
        candidates.append(configured_path)

    candidates.extend(
        Path(found)
        for executable in _executable_names(name)
        if (found := shutil.which(executable, path=search_path)) is not None
    )
    candidates.extend(_default_paths(name, environ))
    return candidates


def _windows_file_version(path: Path) -> str:
    if sys.platform != "win32":
        raise RuntimeError("LTspice file version metadata is only available on Windows")

    class FixedFileInfo(ctypes.Structure):
        _fields_ = [
            ("signature", ctypes.c_uint32),
            ("structure_version", ctypes.c_uint32),
            ("file_version_ms", ctypes.c_uint32),
            ("file_version_ls", ctypes.c_uint32),
            ("product_version_ms", ctypes.c_uint32),
            ("product_version_ls", ctypes.c_uint32),
            ("file_flags_mask", ctypes.c_uint32),
            ("file_flags", ctypes.c_uint32),
            ("file_os", ctypes.c_uint32),
            ("file_type", ctypes.c_uint32),
            ("file_subtype", ctypes.c_uint32),
            ("file_date_ms", ctypes.c_uint32),
            ("file_date_ls", ctypes.c_uint32),
        ]

    version_api = ctypes.WinDLL("version", use_last_error=True)
    get_size = version_api.GetFileVersionInfoSizeW
    get_info = version_api.GetFileVersionInfoW
    query_value = version_api.VerQueryValueW
    get_size.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32)]
    get_size.restype = ctypes.c_uint32
    get_info.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    get_info.restype = ctypes.c_int
    query_value.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_uint32),
    ]
    query_value.restype = ctypes.c_int

    ignored = ctypes.c_uint32()
    size = get_size(str(path), ctypes.byref(ignored))
    if not size:
        raise OSError(ctypes.get_last_error(), f"Cannot read version metadata for {path}")
    buffer = ctypes.create_string_buffer(size)
    if not get_info(str(path), 0, size, buffer):
        raise OSError(ctypes.get_last_error(), f"Cannot read version metadata for {path}")
    value = ctypes.c_void_p()
    value_size = ctypes.c_uint32()
    if not query_value(buffer, "\\", ctypes.byref(value), ctypes.byref(value_size)):
        raise OSError(ctypes.get_last_error(), f"Cannot read version metadata for {path}")

    fixed = ctypes.cast(value, ctypes.POINTER(FixedFileInfo)).contents
    major, minor = fixed.product_version_ms >> 16, fixed.product_version_ms & 0xFFFF
    build, revision = fixed.product_version_ls >> 16, fixed.product_version_ls & 0xFFFF
    return f"{major}.{minor}.{build}.{revision}"


@functools.cache
def _version_string(name: SolverName, path: Path) -> str:
    if name == "ltspice":
        return _windows_file_version(path)

    # The GUI build (ngspice.exe) does not exit on `-v`, so query the console build.
    console = path.with_name("ngspice_con.exe")
    executable = console if path.name.lower() == "ngspice.exe" and console.is_file() else path
    result = subprocess.run(
        [str(executable), "-v"],
        capture_output=True,
        check=False,
        stdin=subprocess.DEVNULL,
        text=True,
        timeout=10,
    )
    output = f"{result.stdout}\n{result.stderr}"
    match = re.search(r"ngspice[- ]([^\s,]+)", output, re.IGNORECASE)
    if result.returncode != 0 or match is None:
        raise RuntimeError(
            f"Could not determine ngspice version from {path} "
            f"(exit code {result.returncode}): {output.strip()}"
        )
    return match.group(1)


def discover_solver(
    name: SolverName,
    *,
    environ: Mapping[str, str] | None = None,
    search_path: str | None = None,
) -> Solver | None:
    """Find a local solver by environment, PATH, then standard install locations."""
    if name not in ("ngspice", "ltspice"):
        raise ValueError(f"Unsupported solver name: {name}")
    env = os.environ if environ is None else environ
    path_value = os.environ.get("PATH", "") if search_path is None else search_path
    seen: set[str] = set()
    for candidate in _candidate_paths(name, env, path_value):
        key = os.path.normcase(str(candidate))
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file():
            return Solver(name, candidate, _version_string(name, candidate))
    return None


def run_ngspice(
    solver: Solver,
    netlist: Path,
    *,
    timeout: float = 30,
) -> subprocess.CompletedProcess[str]:
    """Run a netlist in ngspice batch mode, with output isolated in its directory."""
    if solver.name != "ngspice":
        raise ValueError(f"Expected ngspice, got {solver.name}")
    log_path = netlist.parent / "ngspice.log"
    return subprocess.run(
        [str(solver.path), "-b", "-o", str(log_path), str(netlist)],
        capture_output=True,
        check=False,
        cwd=netlist.parent,
        text=True,
        timeout=timeout,
    )


def run_ltspice(
    solver: Solver,
    source: Path,
    *,
    export_netlist: bool = False,
    working_directory: Path | None = None,
    timeout: float = 30,
) -> subprocess.CompletedProcess[str]:
    """Run LTspice headlessly in batch-simulation or schematic-netlist mode."""
    if solver.name != "ltspice":
        raise ValueError(f"Expected LTspice, got {solver.name}")
    switch = "-netlist" if export_netlist else "-b"
    return subprocess.run(
        [str(solver.path), switch, str(source)],
        capture_output=True,
        check=False,
        cwd=source.parent if working_directory is None else working_directory,
        text=True,
        timeout=timeout,
    )
