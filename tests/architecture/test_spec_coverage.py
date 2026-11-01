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
    ROOT / "src" / "netlistmod" / "grammar" / "formula.lark",
]
LTSPICE_SPEC_DIRECTORY = ROOT / "docs" / "grammars" / "ltspice" / "specs"
LTSPICE_GRAMMAR_FILES = [
    ROOT / "src" / "netlistmod" / "grammar" / "ltspice.lark",
    ROOT / "src" / "netlistmod" / "grammar" / "formula_ltspice.lark",
]
LTSPICE_SHARED_FILES = [
    ROOT / "src" / "netlistmod" / "grammar" / "core.lark",
    ROOT / "src" / "netlistmod" / "grammar" / "formula.lark",
]
SPEC_MARKER = re.compile(r"^\s*//\s*spec:\s*([A-Z0-9-]+)\s*$", re.MULTILINE)
GRAMMAR_DECLARATION = re.compile(
    r"^\s*(?:(?:%extend|%override)\s+)?"
    r"(\??[a-z_][a-z_0-9]*|_?[A-Z][A-Z_0-9]*)(?:\.\d+)?\s*:"
)
# `[<key>] §<number> "<title>"`, for example `[ngspice-manual] §2.4.4 "End-of-line comments"`.
# The LTspice reference has files and headings, not numbers: `[ltspice-ref] <FILE>.md "<heading>"`.
MANUAL_REF = re.compile(
    r'\[([a-z0-9][a-z0-9-]*)\] (?:§\d+(?:\.\d+)*|[A-Z][A-Z0-9-]*\.md) "([^"\r\n]+)"'
)
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


def check_spec_coverage(
    root: Path,
    spec_directory: Path,
    grammar_files: list[Path],
    shared_files: list[Path] | None = None,
) -> None:
    """Validate spec references, grammar traceability, and test selectors.

    An overlay's entry lists its rules under ``grammar`` and the shared rules it relies on, which
    carry another dialect's markers, under ``core_rules``; it may have only the latter.
    """
    specs = _load_specs(spec_directory)
    if not specs:
        raise ValueError(f"No spec entries found in {spec_directory}")
    declarations = _grammar_declarations(grammar_files)
    shared = _grammar_declarations(shared_files or [])
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
        core_rules = entry.get("core_rules", [])
        if not isinstance(grammar_names, list) or not (grammar_names or core_rules):
            raise ValueError(f"Spec grammar must be a non-empty list: {identifier}")
        for rule in core_rules:
            if rule not in shared:
                raise ValueError(f"Spec references missing core rule: {identifier}: {rule}")
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
        r"^\| ([A-Z@&]) \| (supported|planned|error) \| ([12]) \| (.+) \|$",
        document,
        re.MULTILINE,
    )
    parsed: dict[str, dict[str, str | int]] = {}
    for letter, status, phase, milestone in rows:
        parsed[letter] = {
            "status": status,
            "phase": int(phase),
            "milestone": milestone if milestone in {"M3", "M8"} else "post-review",
        }
    if parsed != matrix:
        raise ValueError(f"{device_document.name} does not match {device_json.name}")


STATUSES = ("documented", "observed", "validated", "disputed")
SOLVER_TESTS = "tests/solver/"
RULE_DOCUMENTS = [
    ROOT / "docs" / "grammars" / "ngspice" / "names.md",
    ROOT / "docs" / "grammars" / "ngspice" / "scoping.md",
]
DISCREPANCIES = ROOT / "docs" / "grammars" / "ngspice" / "discrepancies.md"
# A rule row: | ID | Rule | Manual | Status | Tests |
RULE_ROW = re.compile(r"^\| ([A-Z]\d+) \|(.*)\| ([^|]*) \| ([^|]*) \|$", re.MULTILINE)
VALIDATED_ON_LINE = re.compile(r"^Validated on: \w+ [\w.]+ \(\d{4}-\d{2}-\d{2}\)(?:, .+)?$", re.M)
TEST_CITATION = re.compile(r"`(?:(tests/[\w/]+\.py)::)?(test_\w+)`")


def _solver_test_names(root: Path) -> set[str]:
    names: set[str] = set()
    for path in sorted((root / SOLVER_TESTS).glob("*.py")):
        names.update(re.findall(r"^def (test_\w+)\(", path.read_text("utf-8"), re.MULTILINE))
    return names


def check_validation_status(root: Path, spec_directory: Path, discrepancies: Path) -> None:
    """Tie each spec entry's status to its solver evidence (decision 0008, architecture §11.2).

    ``validated`` and ``observed`` need a ``validated_on`` list (``solver``, ``version`` and
    ``date`` in each item) and a ``tests/solver/`` test; ``disputed`` needs a row in
    ``discrepancies.md`` that names the id; ``documented`` needs a ``validation_note``.
    """
    discrepancy_text = discrepancies.read_text(encoding="utf-8")
    for identifier, entry in _load_specs(spec_directory).items():
        status = entry.get("status")
        if status not in STATUSES:
            raise ValueError(f"Unknown status in {identifier}: {status!r}")
        if status in ("validated", "observed"):
            records = entry.get("validated_on")
            if not isinstance(records, list) or not records:
                raise ValueError(f"{status} entry has no validated_on: {identifier}")
            for record in records:
                if not isinstance(record, dict) or not all(
                    isinstance(record.get(key), str) and record[key]
                    for key in ("solver", "version", "date")
                ):
                    raise ValueError(f"Malformed validated_on item in {identifier}: {record!r}")
            if not any(str(test).startswith(SOLVER_TESTS) for test in entry.get("tests", [])):
                raise ValueError(f"{status} entry cites no solver test: {identifier}")
        elif status == "disputed":
            if not re.search(rf"^\|.*\b{re.escape(identifier)}\b.*\|$", discrepancy_text, re.M):
                raise ValueError(f"disputed entry has no discrepancies.md row: {identifier}")
        elif not isinstance(entry.get("validation_note"), str) or not entry["validation_note"]:
            raise ValueError(f"documented entry has no validation_note: {identifier}")


def check_rule_tables(root: Path, documents: list[Path], discrepancies: Path) -> None:
    """Apply the status rules of ``check_validation_status`` to the rule tables of
    ``names.md`` and ``scoping.md``: a ``validated``/``observed`` row cites a solver test (a
    ``same`` cell repeats the row above) and the document has a ``Validated on:`` line."""
    solver_tests = _solver_test_names(root)
    discrepancy_text = discrepancies.read_text(encoding="utf-8")
    for document in documents:
        text = document.read_text(encoding="utf-8")
        rows = RULE_ROW.findall(text)
        if not rows:
            raise ValueError(f"No rule table in {document.name}")
        previous: set[str] = set()
        for identifier, _, status, tests in rows:
            cited = {name for _, name in TEST_CITATION.findall(tests)}
            if tests.strip().startswith("same"):
                cited |= previous
            previous = cited
            for file, _ in TEST_CITATION.findall(tests):
                if file and not (root / file).is_file():
                    raise ValueError(f"{document.name} {identifier} cites a missing file: {file}")
            if status not in STATUSES:
                raise ValueError(f"Unknown status in {document.name} {identifier}: {status!r}")
            if status in ("validated", "observed"):
                if not cited & solver_tests:
                    raise ValueError(f"{document.name} {identifier} cites no solver test")
                if not VALIDATED_ON_LINE.search(text):
                    raise ValueError(f"{document.name} has no `Validated on:` line")
            elif status == "disputed":
                if not re.search(rf"^\|.*\b{identifier}\b.*\|$", discrepancy_text, re.M):
                    raise ValueError(f"{document.name} {identifier} has no discrepancies.md row")
            elif "validation_note:" not in tests:
                raise ValueError(f"{document.name} {identifier} is documented without a note")


def test_ngspice_specs_reference_tests_and_grammar_rules() -> None:
    check_spec_coverage(ROOT, SPEC_DIRECTORY, GRAMMAR_FILES)
    check_manual_references(SPEC_DIRECTORY, REFERENCES_FILE)
    check_no_stale_citations(CITATION_SCAN)
    check_device_matrix(
        ROOT / "src" / "netlistmod" / "grammar" / "ngspice-devices.json",
        ROOT / "docs" / "grammars" / "ngspice" / "devices.md",
    )


STATUS_ROW = re.compile(r"^\| \[([A-Z0-9-]+)\]\([^)]*\) \| .* \| (\w+) \| ([^|]*) \|$", re.M)


def check_status_summary(readme: Path, spec_directory: Path) -> None:
    """The README's status table lists every entry with its status and validation dates."""
    found = {
        identifier: (status, versions.strip())
        for identifier, status, versions in STATUS_ROW.findall(readme.read_text("utf-8"))
    }
    expected: dict[str, tuple[str, str]] = {}
    for identifier, entry in _load_specs(spec_directory).items():
        dates: dict[str, list[str]] = {}
        for record in entry.get("validated_on") or []:
            dates.setdefault(f"{record['solver']} {record['version']}", []).append(record["date"])
        versions = "; ".join(f"{key} ({', '.join(values)})" for key, values in dates.items())
        expected[identifier] = (entry["status"], versions)
    if found != expected:
        changed = sorted(set(found.items()) ^ set(expected.items()))
        raise ValueError(f"{readme.name} status table differs from the spec entries: {changed}")


def test_ngspice_statuses_are_backed_by_solver_evidence() -> None:
    check_validation_status(ROOT, SPEC_DIRECTORY, DISCREPANCIES)
    check_rule_tables(ROOT, RULE_DOCUMENTS, DISCREPANCIES)
    check_status_summary(ROOT / "docs" / "grammars" / "ngspice" / "README.md", SPEC_DIRECTORY)


def test_ltspice_specs_reference_tests_and_grammar_rules() -> None:
    check_spec_coverage(
        ROOT, LTSPICE_SPEC_DIRECTORY, LTSPICE_GRAMMAR_FILES, shared_files=LTSPICE_SHARED_FILES
    )
    check_manual_references(LTSPICE_SPEC_DIRECTORY, REFERENCES_FILE)
    check_device_matrix(
        ROOT / "src" / "netlistmod" / "grammar" / "ltspice-devices.json",
        ROOT / "docs" / "grammars" / "ltspice" / "devices.md",
    )


def test_ltspice_statuses_are_backed_by_their_evidence() -> None:
    ltspice = ROOT / "docs" / "grammars" / "ltspice"
    discrepancies = ltspice / "discrepancies.md"
    check_validation_status(ROOT, LTSPICE_SPEC_DIRECTORY, discrepancies)
    check_rule_tables(ROOT, [ltspice / "names.md", ltspice / "scoping.md"], discrepancies)
    check_status_summary(ltspice / "README.md", LTSPICE_SPEC_DIRECTORY)


def test_an_overlay_entry_may_rely_on_core_rules_only(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    specs.mkdir()
    test_file = tmp_path / "test_x.py"
    test_file.write_text("def test_x():\n    pass\n", encoding="utf-8")
    entry = (
        "id: LT-TEST-001\nstatus: documented\ngrammar: []\ncore_rules: [{}]\ntests: [test_x.py]\n"
    )
    path = specs / "LT-TEST-001.yaml"
    overlay = tmp_path / "overlay.lark"
    overlay.write_text("// spec: LT-TEST-001\n", encoding="utf-8")
    core = tmp_path / "core.lark"
    core.write_text("// spec: NG-TEST-001\nstart: WORD\n", encoding="utf-8")
    path.write_text(entry.format("start"), encoding="utf-8")
    check_spec_coverage(tmp_path, specs, [overlay], shared_files=[core])
    path.write_text(entry.format("nothing"), encoding="utf-8")
    with pytest.raises(ValueError, match="missing core rule"):
        check_spec_coverage(tmp_path, specs, [overlay], shared_files=[core])


def test_status_summary_check_rejects_a_stale_row(tmp_path: Path) -> None:
    specs, _ = _status_project(tmp_path, "status: validated\n" + _RECORD + _SOLVER_TEST)
    readme = tmp_path / "README.md"
    row = "| [NG-TEST-001](./specs/NG-TEST-001.yaml) | thing | {} | ngspice 47 (2026-10-31) |\n"
    readme.write_text(row.format("validated"), encoding="utf-8")
    check_status_summary(readme, specs)
    readme.write_text(row.format("documented"), encoding="utf-8")
    with pytest.raises(ValueError, match="status table differs"):
        check_status_summary(readme, specs)


def _status_project(tmp_path: Path, entry: str, discrepancy: str = "") -> tuple[Path, Path]:
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "NG-TEST-001.yaml").write_text("id: NG-TEST-001\n" + entry, encoding="utf-8")
    solver = tmp_path / "tests" / "solver"
    solver.mkdir(parents=True)
    (solver / "test_probe.py").write_text("def test_probe():\n    pass\n", encoding="utf-8")
    discrepancies = tmp_path / "discrepancies.md"
    discrepancies.write_text(f"| Solver | Library | Evidence |\n{discrepancy}", encoding="utf-8")
    return specs, discrepancies


_RECORD = "validated_on:\n- solver: ngspice\n  version: '47'\n  date: '2026-10-31'\n"
_SOLVER_TEST = "tests: [tests/solver/test_probe.py::test_probe]\n"


@pytest.mark.parametrize(
    ("entry", "discrepancy"),
    [
        ("status: validated\n" + _RECORD + _SOLVER_TEST, ""),
        ("status: observed\n" + _RECORD + _SOLVER_TEST, ""),
        ("status: disputed\n", "| reads it differently (NG-TEST-001) | x | y |\n"),
        ("status: documented\nvalidation_note: the solver cannot tell\n", ""),
    ],
)
def test_status_check_accepts_backed_statuses(tmp_path: Path, entry: str, discrepancy: str) -> None:
    specs, discrepancies = _status_project(tmp_path, entry, discrepancy)
    check_validation_status(tmp_path, specs, discrepancies)


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ("status: supported\n", "Unknown status"),
        ("status: validated\n" + _SOLVER_TEST, "no validated_on"),
        ("status: observed\nvalidated_on: []\n" + _SOLVER_TEST, "no validated_on"),
        (
            "status: validated\nvalidated_on:\n- solver: ngspice\n  date: '2026-10-31'\n"
            + _SOLVER_TEST,
            "Malformed validated_on",
        ),
        ("status: validated\n" + _RECORD + "tests: [tests/grammar/x.py::test_x]\n", "no solver"),
        ("status: disputed\n", "no discrepancies.md row"),
        ("status: documented\n", "no validation_note"),
    ],
)
def test_status_check_rejects_unbacked_statuses(tmp_path: Path, entry: str, message: str) -> None:
    specs, discrepancies = _status_project(tmp_path, entry)
    with pytest.raises(ValueError, match=message):
        check_validation_status(tmp_path, specs, discrepancies)


_TABLE = "| ID | Rule | Manual | Status | Tests |\n|---|---|---|---|---|\n"


@pytest.mark.parametrize(
    "rows",
    [
        "| N1 | rule | — | validated | `test_probe` |\n| N2 | rule | — | observed | same |\n",
        "| N1 | rule | — | disputed | — |\n",
        "| N1 | rule | — | documented | validation_note: no solver can tell |\n",
    ],
)
def test_rule_table_check_accepts_backed_rows(tmp_path: Path, rows: str) -> None:
    _, discrepancies = _status_project(tmp_path, "status: observed\n", "| N1 differs | x | y |\n")
    document = tmp_path / "rules.md"
    document.write_text(f"Validated on: ngspice 47 (2026-10-31)\n\n{_TABLE}{rows}", "utf-8")
    check_rule_tables(tmp_path, [document], discrepancies)


@pytest.mark.parametrize(
    ("header", "rows", "message"),
    [
        ("", "| N1 | rule | — | validated | `test_probe` |\n", "no `Validated on:` line"),
        ("V", "| N1 | rule | — | validated (discrepancy) | `test_probe` |\n", "Unknown status"),
        ("V", "| N1 | rule | — | validated | `test_other` |\n", "cites no solver test"),
        ("V", "| N1 | rule | — | observed | `tests/x/missing.py::test_probe` |\n", "missing"),
        ("V", "| N1 | rule | — | disputed | — |\n", "no discrepancies.md row"),
        ("V", "| N1 | rule | — | documented | `test_probe` |\n", "without a note"),
        ("V", "no table\n", "No rule table"),
    ],
)
def test_rule_table_check_rejects_unbacked_rows(
    tmp_path: Path, header: str, rows: str, message: str
) -> None:
    _, discrepancies = _status_project(tmp_path, "status: observed\n")
    document = tmp_path / "rules.md"
    line = "Validated on: ngspice 47 (2026-10-31)\n\n" if header else ""
    table = "" if rows == "no table\n" else _TABLE
    document.write_text(f"{line}{table}{rows}", "utf-8")
    with pytest.raises(ValueError, match=message):
        check_rule_tables(tmp_path, [document], discrepancies)


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
        "'[test-manual] SPICE-SYNTAX-REFERENCE.md \"Node Naming\"'",
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
