"""The spec-coverage report of the phase 1 review package (M9 T9): construct, entry, status, tests.

Run from the repository root; it prints the Markdown tables of ``phase-1-review.md``::

    uv run --env-file .env python -m tests.support.spec_coverage
"""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).parents[2]


def report() -> str:
    """One table per dialect, in entry order, with a count of each entry's tests."""
    sections: list[str] = []
    for dialect in ("ngspice", "ltspice"):
        rows = [
            yaml.safe_load(path.read_text(encoding="utf-8"))
            for path in sorted((ROOT / "docs" / "grammars" / dialect / "specs").glob("*.yaml"))
        ]
        statuses = sorted({row["status"] for row in rows})
        summary = ", ".join(
            f"{sum(row['status'] == status for row in rows)} `{status}`" for status in statuses
        )
        lines = [
            f"**{dialect}:** {len(rows)} entries: {summary}.",
            "",
            "| Entry | Construct | Status | Tests |",
            "|---|---|---|---|",
        ]
        lines += [
            f"| `{row['id']}` | {_cell(row['construct'])} | {row['status']} | {len(row['tests'])} |"
            for row in rows
        ]
        sections.append("\n".join(lines))
    return "\n\n".join(sections) + "\n"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    print(report(), end="")
