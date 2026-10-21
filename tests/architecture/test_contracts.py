from __future__ import annotations

import ast
import io
import os
import re
import tomllib
from collections.abc import Callable, Iterable
from contextlib import redirect_stderr, redirect_stdout
from importlib.metadata import distribution, entry_points
from pathlib import Path

import pytest
from lark import Lark
from lark.exceptions import LexError

ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "src" / "netlistmod"


def _forbidden_source_operations(root: Path) -> list[str]:
    violations: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        os_names = {"os"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "subprocess":
                        violations.append(f"{path}: imports subprocess")
                    if alias.name == "os":
                        os_names.add(alias.asname or "os")
            elif isinstance(node, ast.ImportFrom):
                if node.module == "subprocess":
                    violations.append(f"{path}: imports subprocess")
                if node.module == "os":
                    violations.extend(
                        f"{path}: imports os.{alias.name}"
                        for alias in node.names
                        if alias.name in {"system", "popen"}
                    )
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id in os_names
                    and node.func.attr in {"system", "popen"}
                ):
                    violations.append(f"{path}: calls os.{node.func.attr}")
    return violations


def _run_import_linter(root: Path) -> tuple[int, str]:
    command_entry = next(
        entry for entry in entry_points(group="console_scripts") if entry.name == "lint-imports"
    )
    command = command_entry.load()
    previous_directory = Path.cwd()
    output = io.StringIO()
    error_output = io.StringIO()
    try:
        os.chdir(root)
        with redirect_stdout(output), redirect_stderr(error_output):
            try:
                if hasattr(command, "main"):
                    command.main(args=[], prog_name="lint-imports", standalone_mode=False)
                else:
                    command()
            except SystemExit as error:
                code = error.code if isinstance(error.code, int) else 1
            else:
                code = 0
    finally:
        os.chdir(previous_directory)
    return code, f"{output.getvalue()}{error_output.getvalue()}"


def _gpl_dependencies(project: Path, license_fields: Callable[[str], Iterable[str]]) -> list[str]:
    metadata = tomllib.loads(project.read_text(encoding="utf-8"))
    dependencies: list[str] = metadata["project"]["dependencies"]
    result: list[str] = []
    for dependency in dependencies:
        name = re.split(r"[<=>!~;\[]", dependency, maxsplit=1)[0].strip()
        if any("GPL" in field.upper() for field in license_fields(name)):
            result.append(name)
    return result


def _installed_license_fields(name: str) -> list[str]:
    package = distribution(name)
    license_fields = [package.metadata.get("License", "")]
    license_fields.extend(package.metadata.get_all("Classifier") or [])
    return license_fields


def test_source_does_not_launch_processes_or_shell_commands() -> None:
    violations = _forbidden_source_operations(SOURCE)

    assert violations == []


def test_source_boundary_guard_detects_deliberate_violations(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "import subprocess\nimport os as operating\noperating.system('echo forbidden')\n",
        encoding="utf-8",
    )

    violations = _forbidden_source_operations(tmp_path)

    assert any("imports subprocess" in violation for violation in violations)
    assert any("calls os.system" in violation for violation in violations)


def test_import_linter_layer_contract_passes() -> None:
    code, output = _run_import_linter(ROOT)

    assert code == 0, output


def test_errors_module_is_below_all_other_package_layers() -> None:
    source = ast.parse((SOURCE / "errors.py").read_text(encoding="utf-8"))
    imports = [
        alias.name
        for node in ast.walk(source)
        if isinstance(node, ast.Import)
        for alias in node.names
    ]
    imports.extend(
        node.module
        for node in ast.walk(source)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert not any(name.startswith("netlistmod.") for name in imports)


def test_import_linter_rejects_deliberate_layer_violation(tmp_path: Path) -> None:
    package = tmp_path / "badpkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "top.py").write_text("", encoding="utf-8")
    (package / "bottom.py").write_text("import badpkg.top\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.importlinter]\nroot_package = "badpkg"\n\n'
        '[[tool.importlinter.contracts]]\nname = "layers"\ntype = "layers"\n'
        'layers = ["badpkg.top", "badpkg.bottom"]\n',
        encoding="utf-8",
    )

    code, output = _run_import_linter(tmp_path)

    assert code != 0, output
    assert "badpkg.bottom" in output


def test_every_package_grammar_builds_in_strict_mode() -> None:
    for grammar in SOURCE.rglob("*.lark"):
        Lark.open(grammar, parser="lalr", strict=True)


def test_strict_mode_rejects_a_deliberate_terminal_collision() -> None:
    conflicting_grammar = "start: FIRST | SECOND\nFIRST: /[a-z]+/\nSECOND: /[a-z]+/"

    with pytest.raises(LexError, match="collision|Collision"):
        Lark(conflicting_grammar, parser="lalr", strict=True)


def test_runtime_dependencies_have_no_gpl_license() -> None:
    dependencies = _gpl_dependencies(ROOT / "pyproject.toml", _installed_license_fields)

    assert dependencies == []


def test_gpl_dependency_guard_detects_deliberate_violation(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[project]\ndependencies = ["example-gpl>=1"]\n',
        encoding="utf-8",
    )

    dependencies = _gpl_dependencies(
        project,
        lambda _name: ["GPL-3.0-only"],
    )

    assert dependencies == ["example-gpl"]
