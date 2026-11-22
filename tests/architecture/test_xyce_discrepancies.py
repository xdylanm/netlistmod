"""The xyce discrepancy table keeps decision 0029's categories and rule (X-M2.1 C2).

Every row of ``docs/grammars/xyce/discrepancies.md`` has a category, and each section says what the
library does beside Xyce, which bounds the categories that may stand in it (decision 0029 item 2):
where the library reads a form Xyce stops on, the row is ``manual`` or ``library-limit``; where it
refuses a form both the manual and Xyce accept, ``library-limit``. Each row's evidence names tests
that exist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
TABLE = ROOT / "docs" / "grammars" / "xyce" / "discrepancies.md"
CATEGORIES = {"manual", "imprecise", "manual-error", "library-limit"}

# Each section: the categories allowed in it, and a word every row's library cell holds (the
# library refuses, or reads), or None.
SECTIONS: dict[str, tuple[frozenset[str], str | None]] = {
    "Forms Xyce runs and the library refuses": (frozenset({"manual", "imprecise"}), "ParseError"),
    "Forms the manual and Xyce accept and the library refuses": (
        frozenset({"library-limit"}),
        "ParseError",
    ),
    "Forms the library reads and Xyce stops on or ignores": (
        frozenset({"manual", "library-limit"}),
        "Read",
    ),
    "Forms the library reads or refuses as Xyce does, against the manual": (
        frozenset({"manual-error"}),
        None,
    ),
    "Where the manual is silent or imprecise": (frozenset({"imprecise"}), None),
}
_CITATION = re.compile(r"`(tests/[\w/]+\.py)::(\w+)`")


@dataclass(frozen=True)
class Row:
    section: str
    line: int
    cells: dict[str, str]


def _rows(text: str) -> list[Row]:
    """The rows of every table, keyed by the header's column names; a malformed table fails."""
    rows: list[Row] = []
    section = ""
    header: list[str] | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## "):
            section, header = line[3:], None
        elif not line.startswith("|"):
            header = None
        elif header is None:
            header = _cells(line)
        elif not set(line) <= set("|-"):
            cells = _cells(line)
            assert len(cells) == len(header), f"line {number}: {len(cells)} cells"
            rows.append(Row(section, number, dict(zip(header, cells, strict=True))))
    return rows


def _cells(line: str) -> list[str]:
    assert line.startswith("| ") and line.endswith(" |"), line[:60]
    return [cell.strip() for cell in line[2:-2].split(" | ")]


ROWS = _rows(TABLE.read_text(encoding="utf-8"))


def _id(row: Row) -> str:
    return f"line{row.line}"


def test_every_section_is_known_and_has_rows() -> None:
    sections = [
        line[3:] for line in TABLE.read_text(encoding="utf-8").splitlines() if line[:3] == "## "
    ]
    assert sections == list(SECTIONS)
    assert {row.section for row in ROWS} == set(SECTIONS)


@pytest.mark.parametrize("row", ROWS, ids=_id)
def test_every_row_has_a_category_its_section_allows(row: Row) -> None:
    category = row.cells["Category"]
    assert category.startswith("`") and category.endswith("`"), category
    assert category.strip("`") in CATEGORIES
    allowed, _ = SECTIONS[row.section]
    assert category.strip("`") in allowed, f"{category} in {row.section!r}"


@pytest.mark.parametrize("row", ROWS, ids=_id)
def test_the_library_side_matches_the_section(row: Row) -> None:
    _, word = SECTIONS[row.section]
    if word == "Read":
        assert row.cells["Library behaviour"].startswith("Read")
    elif word is not None:
        assert word in row.cells["Library behaviour"]


@pytest.mark.parametrize("row", ROWS, ids=_id)
def test_the_evidence_names_tests_that_exist(row: Row) -> None:
    citations = _CITATION.findall(row.cells["Evidence"])
    assert citations, row.cells["Evidence"]
    for path, name in citations:
        source = ROOT / path
        assert source.is_file(), path
        assert re.search(rf"^def {name}\(", source.read_text(encoding="utf-8"), re.M), (
            f"{path}::{name}"
        )


def test_the_table_has_the_columns() -> None:
    for row in ROWS:
        expected = ["Xyce 7.10", "Library behaviour", "Category", "Evidence"]
        if row.section != "Where the manual is silent or imprecise":
            expected.insert(1, "Manual")
        assert list(row.cells) == expected, row.line
