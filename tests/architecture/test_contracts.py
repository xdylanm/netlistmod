from __future__ import annotations

import ast
import io
import os
import re
import tomllib
from collections.abc import Callable, Iterable, Iterator
from contextlib import redirect_stderr, redirect_stdout
from importlib.metadata import distribution, entry_points
from pathlib import Path

import interegular
import pytest
from lark import Lark
from lark.exceptions import LexError

from netlistmod.dialects import Dialect
from netlistmod.grammar.loader import build_parser, pending_dialects, registered_dialects

ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "src" / "netlistmod"
GRAMMAR_DECLARATION = re.compile(
    r"^\s*(?:(%extend|%override)\s+)?(\??[a-z_][a-z_0-9]*|_?[A-Z][A-Z_0-9]*)"
    r"(?:\.\d+)?\s*:"
)
RULE_ALIAS = re.compile(r"->\s*([a-z_][a-z_0-9]*)")


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


def _regex_imports(root: Path) -> list[str]:
    violations: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(alias.name == "re" for alias in node.names):
                violations.append(str(path))
            if isinstance(node, ast.ImportFrom) and node.module == "re":
                violations.append(str(path))
    return violations


def _missing_transformer_methods(grammar_files: list[Path], transformer: type) -> set[str]:
    expected: set[str] = set()
    for path in grammar_files:
        current_name: str | None = None
        current_inline = False
        current_extended = False
        aliases: list[str] = []

        def finish() -> None:
            # Terminals (also "_" sub-terminals), extensions and inlined rules ("_name") have
            # no transformer method: Lark splices an inlined rule's children into its parent.
            if (
                current_name is None
                or current_name[0].isupper()
                or current_name.startswith("_")
                or current_extended
            ):
                return
            if aliases:
                prefix = "core__" if path.name == "core.lark" else ""
                expected.update(f"{prefix}{alias}" for alias in aliases)
            elif not current_inline:
                expected.add(current_name)

        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                finish()
                current_name = None
                aliases = []
                continue
            match = GRAMMAR_DECLARATION.match(line)
            if match:
                finish()
                directive, declared_name = match.groups()
                current_name = declared_name.lstrip("?")
                current_inline = declared_name.startswith("?")
                current_extended = directive == "%extend"
                aliases = RULE_ALIAS.findall(line)
                continue
            if current_name is not None:
                aliases.extend(RULE_ALIAS.findall(line))
        finish()
    return {method for method in expected if not callable(getattr(transformer, method, None))}


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


def test_model_does_not_import_regular_expressions() -> None:
    assert _regex_imports(SOURCE / "model") == []


def test_document_does_not_import_regular_expressions() -> None:
    # P13 (M5): formula names come from the formula grammar, never from string scanning.
    assert _regex_imports(SOURCE / "document") == []


def test_edit_does_not_import_regular_expressions() -> None:
    # P13 (M6): edits take spans from the nodes and compose text; they never scan for syntax.
    assert _regex_imports(SOURCE / "edit") == []


def test_regex_import_guard_detects_deliberate_violation(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("from re import compile\n", encoding="utf-8")
    assert _regex_imports(tmp_path) == [str(tmp_path / "bad.py")]


def test_every_lark_rule_has_a_transformer_method() -> None:
    from netlistmod.model.transform import _NodeBuilder

    # The formula grammars are separate; their trees are walked by grammar/formula.py (M5).
    grammar_files = sorted(
        path for path in (SOURCE / "grammar").glob("*.lark") if not path.name.startswith("formula")
    )
    assert _missing_transformer_methods(grammar_files, _NodeBuilder) == set()


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


def test_parser_registry_accounts_for_each_dialect() -> None:
    assert registered_dialects().isdisjoint(pending_dialects())
    assert registered_dialects() | pending_dialects() == frozenset(Dialect)


def test_strict_mode_rejects_a_deliberate_terminal_collision() -> None:
    conflicting_grammar = "start: FIRST | SECOND\nFIRST: /[a-z]+/\nSECOND: /[a-z]+/"

    with pytest.raises(LexError, match="collision|Collision"):
        Lark(conflicting_grammar, parser="lalr", strict=True)


# Terminals whose lookarounds interegular cannot model. Lark's strict mode skips them in the
# collision check without an error, so each one must be reviewed by hand (decision 0003). Adding a
# terminal here is a deliberate act; this list must not grow silently.
UNCHECKED_TERMINALS = {
    Dialect.NGSPICE: frozenset(
        {
            "BLOCK_TEXT",
            "BS_CONT",
            "B_PIECE",
            "COMMENT_LINE",
            "DOT_NAME",
            "LIB_BLOCK_KW",
            "TEXT",
            "TITLE_ARG",
            "TITLE_TEXT",
            "TRAILING_COMMENT",
        }
    ),
    Dialect.LTSPICE: frozenset(
        {
            "BARE_FORMULA",
            "BLOCK_TEXT",
            "B_PIECE",
            "MODEL_BARE",
            "BRACE_FORMULA",
            "COMMENT_LINE",
            "LIB_BLOCK_KW",
            "TEXT",
            "TITLE_ARG",
            "TITLE_TEXT",
            "TRAILING_COMMENT",
        }
    ),
}


def _collision_unchecked(regexp: str) -> bool:
    try:
        interegular.parse_pattern(regexp).to_fsm()
    except interegular.patterns.Unsupported:
        return True
    return False


@pytest.mark.parametrize("dialect", sorted(registered_dialects(), key=lambda item: item.value))
def test_terminals_outside_strict_collision_checking_are_known(dialect: Dialect) -> None:
    terminals = build_parser(dialect).terminals
    unchecked = {item.name for item in terminals if _collision_unchecked(item.pattern.to_regexp())}
    assert unchecked == UNCHECKED_TERMINALS[dialect]


def test_strict_mode_does_not_check_a_lookahead_terminal_for_collisions() -> None:
    # Documents the gap the list above tracks: these two terminals overlap on "a", yet strict mode
    # builds the grammar because the lookahead puts FIRST outside the collision check.
    overlapping = "start: (FIRST | SECOND)+\nFIRST: /(?:[a-z]|x(?!y))+/\nSECOND: /[a-c]+/"
    assert _collision_unchecked("(?:[a-z]|x(?!y))+")
    Lark(overlapping, parser="lalr", lexer="contextual", strict=True)


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


# M11 T7: a wheel has no decision records, and a bare section sign does not say whose section.
_INTERNAL_CITATION = re.compile(r"decision \d|architecture §|(?<!manual )§\d")


def _message_strings(path: Path) -> Iterator[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bare = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in bare:
            yield node.lineno, node.value


def test_no_message_cites_an_internal_document() -> None:
    root = SOURCE
    found = [
        f"{path.relative_to(root)}:{line}: {text}"
        for path in sorted(root.rglob("*.py"))
        for line, text in _message_strings(path)
        if _INTERNAL_CITATION.search(text)
    ]
    assert not found
