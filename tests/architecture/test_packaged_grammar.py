from __future__ import annotations

import os
import subprocess
import sys
import sysconfig
import venv
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).parents[2]
GRAMMAR_RESOURCES = {
    "netlistmod/grammar/core.lark",
    "netlistmod/grammar/ngspice.lark",
    "netlistmod/grammar/ngspice-devices.json",
    "netlistmod/grammar/ltspice.lark",
    "netlistmod/grammar/ltspice-devices.json",
    "netlistmod/grammar/formula.lark",
    "netlistmod/grammar/formula_ltspice.lark",
    "netlistmod/grammar/formula-reserved.json",
    "netlistmod/document/model-types.json",
}


def test_wheel_contains_and_loads_grammar_resources(tmp_path: Path) -> None:
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(wheels),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, f"{build.stdout}\n{build.stderr}"
    (wheel,) = wheels.glob("*.whl")
    with ZipFile(wheel) as archive:
        assert GRAMMAR_RESOURCES <= set(archive.namelist())

    environment = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    install = subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", str(wheel)],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0, f"{install.stdout}\n{install.stderr}"
    smoke_environment = os.environ.copy()
    smoke_environment.pop("PYTHONPATH", None)
    smoke_environment["NETLISTMOD_TEST_DEPENDENCIES"] = sysconfig.get_paths()["purelib"]
    smoke = subprocess.run(
        [
            str(python),
            "-c",
            (
                "from pathlib import Path; import os, sys; "
                "sys.path.append(os.environ['NETLISTMOD_TEST_DEPENDENCIES']); "
                "import netlistmod; "
                "from netlistmod import Dialect, SourceText, parse; "
                "assert Path(netlistmod.__file__).resolve().is_relative_to(Path(sys.prefix)); "
                "assert any(type(item).__name__ == 'End' for item in "
                "parse(SourceText('title\\n.end\\n'), Dialect.NGSPICE).items)"
            ),
        ],
        cwd=tmp_path,
        env=smoke_environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert smoke.returncode == 0, f"{smoke.stdout}\n{smoke.stderr}"
