"""Local-only discovery and execution helpers for SPICE solvers."""

from __future__ import annotations

import ctypes
import functools
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable, Mapping
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SolverName = Literal["ngspice", "ltspice"]

_GENERIC_ALL = 0x10000000


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


def osdi_directory(solver: Solver) -> Path:
    """The folder of the compiled OSDI models an ngspice install ships (``lib/ngspice`` beside
    ``bin``; manual §9.3.1.6). A netlist's ``pre_osdi r2_cmc.osdi`` finds them there through
    ``NGSPICE_OSDI_DIR`` (decision 0020 item 6)."""
    return solver.path.parent.parent / "lib" / "ngspice"


def require_osdi(solver: Solver, modules: Iterable[str]) -> None:
    """Skip the test, with the reason, if the ngspice install ships none of ``modules``: a Linux
    package may build ngspice without its OSDI models."""
    import pytest

    folder = osdi_directory(solver)
    for module in modules:
        if not (folder / module).is_file():
            pytest.skip(f"{module} is not in {folder}: this ngspice ships no OSDI model {module}")


def copy_external_files(folder: Path, field: Mapping[str, object]) -> None:
    """Copy each file a corpus fixture includes from outside the repository, such as
    openjellybean's jellybean.lib, from the path its environment variable names (the manifest's
    ``external`` field). Skip the test if the variable does not name a file."""
    import pytest

    external = field.get("external", {})
    assert isinstance(external, Mapping)
    for include, variable in external.items():
        source = os.environ.get(str(variable))
        if not source or not Path(source).is_file():
            pytest.skip(f"{variable} does not name a file; set it in .env to run this fixture")
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, folder / str(include))


def run_ngspice(
    solver: Solver,
    netlist: Path,
    *,
    timeout: float = 30,
    raw: Path | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a netlist in ngspice batch mode, with output isolated in its directory.

    With ``raw``, ngspice also writes the simulation results to that raw file (``-r``). ``cwd``
    is the working directory (default: the netlist's folder); the log stays next to the netlist.
    ``env`` adds variables to the inherited environment.
    """
    if solver.name != "ngspice":
        raise ValueError(f"Expected ngspice, got {solver.name}")
    log_path = netlist.parent / "ngspice.log"
    raw_args = ["-r", str(raw)] if raw is not None else []
    return subprocess.run(
        [str(solver.path), "-b", *raw_args, "-o", str(log_path), str(netlist)],
        capture_output=True,
        check=False,
        cwd=netlist.parent if cwd is None else cwd,
        env=None if env is None else {**os.environ, **env},
        text=True,
        timeout=timeout,
    )


def run_ltspice(
    solver: Solver,
    source: Path,
    *,
    export_netlist: bool = False,
    ascii_raw: bool = False,
    working_directory: Path | None = None,
    timeout: float = 30,
) -> subprocess.CompletedProcess[str]:
    """Run LTspice headlessly in batch-simulation or schematic-netlist mode.

    With ``ascii_raw``, a batch run writes an ASCII raw file (``-ascii``), with full precision in
    every variable; the default binary file stores floats for all but the first (L0).
    """
    if solver.name != "ltspice":
        raise ValueError(f"Expected LTspice, got {solver.name}")
    switches = ["-netlist"] if export_netlist else ["-b", *(["-ascii"] if ascii_raw else [])]
    command = [str(solver.path), *switches, str(source)]
    cwd = source.parent if working_directory is None else working_directory
    if sys.platform == "win32":
        return run_on_hidden_desktop(command, cwd=cwd, timeout=timeout)
    return subprocess.run(
        command, capture_output=True, check=False, cwd=cwd, text=True, timeout=timeout
    )


def run_on_hidden_desktop(
    command: list[str], *, cwd: Path, timeout: float
) -> subprocess.CompletedProcess[str]:
    """Run a program on a desktop nobody is looking at, and wait for it.

    LTspice is a GUI program and takes the foreground window on every run, even with ``-b``, and
    the usual window flags do not stop it. On its own desktop it cannot, so the suite does not
    pull focus from what the developer is doing. ``subprocess`` cannot choose a desktop, hence
    ``CreateProcessW``. Output is not captured: LTspice writes its log to a file. A dialog would
    be invisible here too, so it ends in ``subprocess.TimeoutExpired``.
    """
    if sys.platform != "win32":
        raise RuntimeError("a hidden desktop is only available on Windows")

    class StartupInfo(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("reserved", wintypes.LPWSTR),
            ("desktop", wintypes.LPWSTR),
            ("title", wintypes.LPWSTR),
            ("placement", wintypes.DWORD * 7),
            ("flags", wintypes.DWORD),
            ("show_window", wintypes.WORD),
            ("reserved2_size", wintypes.WORD),
            ("reserved2", ctypes.c_void_p),
            ("standard_handles", wintypes.HANDLE * 3),
        ]

    class ProcessInformation(ctypes.Structure):
        _fields_ = [
            ("process", wintypes.HANDLE),
            ("thread", wintypes.HANDLE),
            ("process_id", wintypes.DWORD),
            ("thread_id", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    startup = StartupInfo()
    startup.cb = ctypes.sizeof(startup)
    startup.desktop = _hidden_desktop()
    process = ProcessInformation()
    created = kernel32.CreateProcessW(
        None,
        ctypes.create_unicode_buffer(subprocess.list2cmdline(command)),
        None,
        None,
        False,
        0,
        None,
        str(cwd),
        ctypes.byref(startup),
        ctypes.byref(process),
    )
    if not created:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if kernel32.WaitForSingleObject(process.process, int(timeout * 1000)) != 0:
            kernel32.TerminateProcess(process.process, 1)
            kernel32.WaitForSingleObject(process.process, 5000)
            raise subprocess.TimeoutExpired(command, timeout)
        code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(process.process, ctypes.byref(code))
    finally:
        kernel32.CloseHandle(process.process)
        kernel32.CloseHandle(process.thread)
    return subprocess.CompletedProcess(command, code.value, "", "")


@functools.lru_cache(maxsize=1)
def _hidden_desktop() -> str:
    """The name of this process's hidden desktop, which lasts as long as the process does."""
    if sys.platform != "win32":
        raise RuntimeError("a hidden desktop is only available on Windows")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.CreateDesktopW.restype = wintypes.HANDLE
    user32.CreateDesktopW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    name = f"netlistmod-tests-{os.getpid()}"
    if not user32.CreateDesktopW(name, None, None, 0, _GENERIC_ALL, None):
        raise ctypes.WinError(ctypes.get_last_error())
    return name
