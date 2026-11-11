"""The "Validation status" table of each grammar README, generated from the spec entries.

``tests/architecture/test_spec_coverage.py`` checks that each README holds what this module
generates. After changing an entry, print the table and paste it over the README's::

    uv run --env-file .env python -m tests.support.spec_coverage ngspice
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).parents[2]
SOLVER_TESTS = "tests/solver/"
HEADER = "| Entry | Construct | Status | Tests | Validated on |\n|---|---|---|---|---|"
# The order of the totals line; architecture §11.2 defines the four words.
STATUSES = ("validated", "observed", "disputed", "documented")


def spec_directory(dialect: str) -> Path:
    return ROOT / "docs" / "grammars" / dialect / "specs"


def load_entries(directory: Path) -> list[dict[str, Any]]:
    """The entries in file-name order."""
    return [yaml.safe_load(path.read_text("utf-8")) for path in sorted(directory.glob("*.yaml"))]


def tests_cell(entry: dict[str, Any]) -> str:
    """``6 + 2 solver``: the entry's test references outside and inside ``tests/solver/``."""
    references = [str(reference) for reference in entry.get("tests") or []]
    solver = sum(reference.startswith(SOLVER_TESTS) for reference in references)
    return f"{len(references) - solver} + {solver} solver"


def validated_on_cell(entry: dict[str, Any]) -> str:
    """``ngspice 47 (2026-10-30, 2026-10-31)``: the dates of each solver version, in order."""
    dates: dict[str, list[str]] = {}
    for record in entry.get("validated_on") or []:
        dates.setdefault(f"{record['solver']} {record['version']}", []).append(record["date"])
    return "; ".join(f"{key} ({', '.join(values)})" for key, values in dates.items())


def row_cells(entry: dict[str, Any]) -> tuple[str, str, str, str]:
    """Construct, status, tests and validated-on cells of an entry's row."""
    return (_cell(entry["construct"]), entry["status"], tests_cell(entry), validated_on_cell(entry))


def row(entry: dict[str, Any]) -> str:
    identifier = entry["id"]
    cells = " | ".join(row_cells(entry))
    return f"| [{identifier}](./specs/{identifier}.yaml) | {cells} |"


def totals_line(entries: list[dict[str, Any]]) -> str:
    """``75 entries: 72 validated, 3 observed, 0 disputed, 0 documented.``"""
    counts = ", ".join(
        f"{sum(entry['status'] == status for entry in entries)} {status}" for status in STATUSES
    )
    return f"{len(entries)} entries: {counts}."


def status_table(directory: Path) -> str:
    entries = load_entries(directory)
    rows = "\n".join(row(entry) for entry in entries)
    return f"{HEADER}\n{rows}\n\n{totals_line(entries)}\n"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    print(status_table(spec_directory(sys.argv[1])), end="")
