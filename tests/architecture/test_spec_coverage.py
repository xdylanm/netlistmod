from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).parents[2]
SPEC_DIRECTORY = ROOT / "docs" / "grammars" / "ngspice" / "specs"
REFERENCES_FILE = ROOT / "docs" / "references.md"
GRAMMAR_FILES = [
    ROOT / "src" / "netlistmod" / "grammar" / "core.lark",
    ROOT / "src" / "netlistmod" / "grammar" / "ngspice.lark",
]
SPEC_MARKER = re.compile(r"^\s*//\s*spec:\s*([A-Z0-9-]+)\s*$", re.MULTILINE)
GRAMMAR_DECLARATION = re.compile(
    r"^\s*(?:(?:%extend|%override)\s+)?"
    r"(\??[a-z_][a-z_0-9]*|_?[A-Z][A-Z_0-9]*)(?:\.\d+)?\s*:"
)
# `[<key>] §<number> "<title>"`, for example `[ngspice-manual] §2.4.4 "End-of-line comments"`.
MANUAL_REF = re.compile(r'\[([a-z0-9][a-z0-9-]*)\] §(\d+(?:\.\d+)*) "([^"\r\n]+)"')
REFERENCE_KEY = re.compile(r"^## \[([a-z0-9][a-z0-9-]*)\]\s*$", re.MULTILINE)
# Section numbers cited before F1 that do not exist in the manual edition in references.md.
STALE_CITATION = re.compile(r"§§|manual, §|§5\.1\.1|§5\.2\.[1-4]")
CITATION_SCAN = [ROOT / "docs" / "decisions", ROOT / "docs" / "grammars", ROOT / "src"]


def _load_specs(spec_directory: Path) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for path in sorted(spec_directory.glob("*.yaml")):
        entry = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError(f"Invalid spec entry: {path}")
        identifier = entry["id"]
        if identifier in specs:
            raise ValueError(f"Duplicate spec id: {identifier}")
        specs[identifier] = entry
    return specs


def _grammar_declarations(grammar_files: list[Path]) -> dict[str, list[tuple[str, Path, int]]]:
    declarations: dict[str, list[tuple[str, Path, int]]] = {}
    for path in grammar_files:
        marker: str | None = None
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                marker = None
                continue
            found_marker = SPEC_MARKER.fullmatch(line)
            if found_marker:
                marker = found_marker.group(1)
                continue
            declaration = GRAMMAR_DECLARATION.match(line)
            if declaration:
                if marker is None:
                    raise ValueError(
                        f"Grammar rule has no preceding spec marker: {path}:{line_number}"
                    )
                declarations.setdefault(declaration.group(1).lstrip("?"), []).append(
                    (marker, path, line_number)
                )
    return declarations


def check_spec_coverage(root: Path, spec_directory: Path, grammar_files: list[Path]) -> None:
    """Validate spec references, grammar traceability, and test selectors."""
    specs = _load_specs(spec_directory)
    if not specs:
        raise ValueError(f"No spec entries found in {spec_directory}")
    declarations = _grammar_declarations(grammar_files)
    for identifier, path, line_number in (
        (marker, path, line_number)
        for entries in declarations.values()
        for marker, path, line_number in entries
    ):
        if identifier not in specs:
            raise ValueError(f"Grammar references unknown spec id: {identifier}")

    for identifier, entry in specs.items():
        if "grammar" not in entry:
            raise ValueError(f"Spec entry has no grammar field: {identifier}")
        grammar_names = entry["grammar"]
        if not isinstance(grammar_names, list) or not grammar_names:
            raise ValueError(f"Spec grammar must be a non-empty list: {identifier}")
        for grammar_name in grammar_names:
            if not isinstance(grammar_name, str) or grammar_name not in declarations:
                raise ValueError(
                    f"Spec references missing grammar rule: {identifier}: {grammar_name}"
                )
            if not any(marker == identifier for marker, _, _ in declarations[grammar_name]):
                raise ValueError(
                    f"Grammar rule does not carry spec marker {identifier}: {grammar_name}"
                )

        if entry.get("status") != "disputed" and "tests" not in entry:
            raise ValueError(f"Spec entry has no tests field: {identifier}")
        references = entry.get("tests", [])
        if not isinstance(references, list):
            raise ValueError(f"Spec tests must be a list: {identifier}")
        if entry.get("status") != "disputed" and not references:
            raise ValueError(f"Spec entry has no tests: {identifier}")
        for test_reference in references:
            if not isinstance(test_reference, str):
                raise ValueError(f"Invalid test reference in {identifier}: {test_reference!r}")
            test_path, separator, selector = test_reference.partition("::")
            path = root / test_path
            if not path.is_file():
                raise ValueError(f"Spec references missing test file: {test_reference}")
            if separator and selector not in path.read_text(encoding="utf-8"):
                raise ValueError(f"Spec references missing test selector: {test_reference}")

    for grammar_name, entries in declarations.items():
        for identifier, _, _ in entries:
            listed = specs[identifier].get("grammar", [])
            if grammar_name not in listed:
                raise ValueError(f"Grammar rule is missing from spec {identifier}: {grammar_name}")


def check_manual_references(spec_directory: Path, references_file: Path) -> None:
    """Require every spec citation to use the reference form and a key from references.md."""
    if not references_file.is_file():
        raise ValueError(f"References file not found: {references_file}")
    keys = set(REFERENCE_KEY.findall(references_file.read_text(encoding="utf-8")))
    for identifier, entry in _load_specs(spec_directory).items():
        citations = entry.get("manual_ref")
        if isinstance(citations, str):
            citations = [citations]
        if not isinstance(citations, list) or not citations:
            raise ValueError(f"Spec entry has no manual_ref: {identifier}")
        for citation in citations:
            found = MANUAL_REF.fullmatch(citation) if isinstance(citation, str) else None
            if found is None:
                raise ValueError(f"Malformed manual_ref in {identifier}: {citation!r}")
            if found.group(1) not in keys:
                raise ValueError(f"Unknown reference key in {identifier}: {found.group(1)}")


def check_no_stale_citations(paths: list[Path]) -> None:
    """Reject the citation forms and section numbers that F1 replaced."""
    for directory in paths:
        for path in sorted(directory.rglob("*")):
            if path.suffix not in {".md", ".yaml", ".lark", ".py"}:
                continue
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if STALE_CITATION.search(line):
                    raise ValueError(f"Stale manual citation: {path}:{line_number}")


def check_device_matrix(device_json: Path, device_document: Path) -> None:
    """Ensure the documented device matrix matches its packaged JSON source."""
    matrix = json.loads(device_json.read_text(encoding="utf-8"))
    document = device_document.read_text(encoding="utf-8")
    rows = re.findall(
        r"^\| ([A-Z]) \| (supported|planned|error) \| ([12]) \| (.+) \|$",
        document,
        re.MULTILINE,
    )
    parsed: dict[str, dict[str, str | int]] = {}
    for letter, status, phase, milestone in rows:
        parsed[letter] = {
            "status": status,
            "phase": int(phase),
            "milestone": "M3" if milestone == "M3" else "post-review",
        }
    if parsed != matrix:
        raise ValueError("devices.md does not match ngspice-devices.json")


def test_ngspice_specs_reference_tests_and_grammar_rules() -> None:
    check_spec_coverage(ROOT, SPEC_DIRECTORY, GRAMMAR_FILES)
    check_manual_references(SPEC_DIRECTORY, REFERENCES_FILE)
    check_no_stale_citations(CITATION_SCAN)
    check_device_matrix(
        ROOT / "src" / "netlistmod" / "grammar" / "ngspice-devices.json",
        ROOT / "docs" / "grammars" / "ngspice" / "devices.md",
    )


def test_spec_checker_rejects_missing_test_reference(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "NG-TEST-001.yaml").write_text(
        "id: NG-TEST-001\nstatus: documented\ngrammar: [start]\n"
        "tests: [tests/missing.py::test_missing]\n",
        encoding="utf-8",
    )
    grammar = tmp_path / "test.lark"
    grammar.write_text("// spec: NG-TEST-001\nstart: WORD\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing test file"):
        check_spec_coverage(tmp_path, specs, [grammar])


def test_spec_checker_rejects_dangling_grammar_reference(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "NG-TEST-001.yaml").write_text(
        "id: NG-TEST-001\nstatus: documented\ngrammar: [start]\ntests: []\n",
        encoding="utf-8",
    )
    grammar = tmp_path / "test.lark"
    grammar.write_text("// spec: NG-MISSING-001\nstart: WORD\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unknown spec id"):
        check_spec_coverage(tmp_path, specs, [grammar])


def test_spec_checker_rejects_unreferenced_supported_entry(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    specs.mkdir()
    test_file = tmp_path / "tests" / "test_example.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_accept():\n    pass\n", encoding="utf-8")
    (specs / "NG-TEST-001.yaml").write_text(
        "id: NG-TEST-001\nstatus: supported\ngrammar: [start]\n"
        "tests: [tests/test_example.py::test_accept]\n",
        encoding="utf-8",
    )
    (specs / "NG-OTHER-001.yaml").write_text(
        "id: NG-OTHER-001\nstatus: documented\ngrammar: [start]\n"
        "tests: [tests/test_example.py::test_accept]\n",
        encoding="utf-8",
    )
    grammar = tmp_path / "test.lark"
    grammar.write_text("// spec: NG-OTHER-001\nstart: WORD\n", encoding="utf-8")

    with pytest.raises(ValueError, match="does not carry spec marker"):
        check_spec_coverage(tmp_path, specs, [grammar])


def test_spec_checker_requires_tests_for_non_disputed_entries(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "NG-TEST-001.yaml").write_text(
        "id: NG-TEST-001\nstatus: observed\ngrammar: [start]\n",
        encoding="utf-8",
    )
    grammar = tmp_path / "test.lark"
    grammar.write_text("// spec: NG-TEST-001\nstart: WORD\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no tests field"):
        check_spec_coverage(tmp_path, specs, [grammar])


def test_spec_checker_requires_exact_rule_traceability(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    specs.mkdir()
    test_file = tmp_path / "tests" / "test_example.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_accept():\n    pass\n", encoding="utf-8")
    (specs / "NG-TEST-001.yaml").write_text(
        "id: NG-TEST-001\nstatus: observed\ngrammar: [start]\n"
        "tests: [tests/test_example.py::test_accept]\n",
        encoding="utf-8",
    )
    grammar = tmp_path / "test.lark"
    grammar.write_text("// spec: NG-OTHER-001\nstart: WORD\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown spec id"):
        check_spec_coverage(tmp_path, specs, [grammar])


def test_spec_checker_rejects_unmarked_grammar_rule(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    specs.mkdir()
    test_file = tmp_path / "tests" / "test_example.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_accept():\n    pass\n", encoding="utf-8")
    (specs / "NG-TEST-001.yaml").write_text(
        "id: NG-TEST-001\nstatus: observed\ngrammar: [start]\n"
        "tests: [tests/test_example.py::test_accept]\n",
        encoding="utf-8",
    )
    grammar = tmp_path / "test.lark"
    grammar.write_text("start: WORD\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no preceding spec marker"):
        check_spec_coverage(tmp_path, specs, [grammar])


def test_spec_checker_requires_grammar_field(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "NG-TEST-001.yaml").write_text(
        "id: NG-TEST-001\nstatus: observed\ntests: [test_example.py]\n",
        encoding="utf-8",
    )
    grammar = tmp_path / "test.lark"
    grammar.write_text("// spec: NG-TEST-001\nstart: WORD\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no grammar field"):
        check_spec_coverage(tmp_path, specs, [grammar])


def _reference_project(tmp_path: Path, manual_ref: str | None) -> tuple[Path, Path]:
    specs = tmp_path / "specs"
    specs.mkdir()
    entry = "id: NG-TEST-001\nstatus: observed\n"
    if manual_ref is not None:
        entry += f"manual_ref: {manual_ref}\n"
    (specs / "NG-TEST-001.yaml").write_text(entry, encoding="utf-8")
    references = tmp_path / "references.md"
    references.write_text("# References\n\n## [test-manual]\n\n- **Title:** Test\n", "utf-8")
    return specs, references


@pytest.mark.parametrize(
    "manual_ref",
    [
        "'[test-manual] §2.4.4 \"End-of-line comments\"'",
        "['[test-manual] §2.1.1 \"Input file structure\"', '[test-manual] §2.8 \".INCLUDE\"']",
    ],
)
def test_manual_reference_check_accepts_single_and_listed_citations(
    tmp_path: Path, manual_ref: str
) -> None:
    specs, references = _reference_project(tmp_path, manual_ref)
    check_manual_references(specs, references)


@pytest.mark.parametrize(
    ("manual_ref", "message"),
    [
        (None, "no manual_ref"),
        ("[]", "no manual_ref"),
        ("'ngspice manual, §2.4.4, \"End-of-line comments\"'", "Malformed manual_ref"),
        ("'[test-manual] §2.4.4 End-of-line comments'", "Malformed manual_ref"),
        ("'[test-manual] 2.4.4 \"End-of-line comments\"'", "Malformed manual_ref"),
        ("'[test-manual] §2.4.4 \"End-of-line comments\"; extra'", "Malformed manual_ref"),
        ("'[other-manual] §2.4.4 \"End-of-line comments\"'", "Unknown reference key"),
    ],
)
def test_manual_reference_check_rejects_malformed_or_unknown_citations(
    tmp_path: Path, manual_ref: str | None, message: str
) -> None:
    specs, references = _reference_project(tmp_path, manual_ref)
    with pytest.raises(ValueError, match=message):
        check_manual_references(specs, references)


def test_manual_reference_check_requires_references_file(tmp_path: Path) -> None:
    specs, references = _reference_project(tmp_path, "'[test-manual] §1 \"Intro\"'")
    references.unlink()
    with pytest.raises(ValueError, match="References file not found"):
        check_manual_references(specs, references)


@pytest.mark.parametrize(
    "text",
    ["ngspice manual §5.2.4", "§§2.4.3 and 2.4.4", "ngspice manual, §2.4.4", "§5.1.1"],
)
def test_stale_citation_check_rejects_replaced_forms(tmp_path: Path, text: str) -> None:
    (tmp_path / "note.md").write_text(f"ok line\nSee {text}.\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"note\.md:2"):
        check_no_stale_citations([tmp_path])


def test_stale_citation_check_accepts_reference_form(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text(
        'See `[ngspice-manual] §2.4.4 "End-of-line comments"`.\n', encoding="utf-8"
    )
    check_no_stale_citations([tmp_path])
