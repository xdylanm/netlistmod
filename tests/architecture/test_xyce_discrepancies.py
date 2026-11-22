"""The xyce discrepancy table keeps decision 0029's categories and rule (X-M2.1 C2, R1).

Every row of ``docs/grammars/xyce/discrepancies.md`` has a category, and each section says what the
library does beside Xyce, which bounds the categories that may stand in it (decision 0029 item 2):
where the library reads a form Xyce stops on, the row is ``manual`` or ``library-limit``; where it
refuses a form both the manual and Xyce accept, ``library-limit``. Each row's evidence names tests
that exist.

The section alone cannot catch a row filed in the wrong section, since the prose of a row is not
checked. So each row also states its facts in the **Library/Xyce** column, one ``library/Xyce``
pair per form, from a closed vocabulary (X-M2.1 R1): the pairs must fit the row's section, and a
``reads/stops`` or ``reads/hangs`` pair must be ``manual`` or ``library-limit`` in any section.
``none`` is allowed only on a row whose library cell says it is not a reading.
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

# The Library/Xyce column: what the library and Xyce each do with a form the row describes.
LIBRARY_SIDES = {"reads", "refuses"}
XYCE_SIDES = {"runs", "ignores", "stops", "hangs"}
NOT_A_READING = "`none`"  # the stable marker of a row that is not a reading (the `-r` abort)
# Decision 0029 item 2: a form the library reads and Xyce does not get through.
READS_WHAT_XYCE_STOPS_ON = {("reads", "stops"), ("reads", "hangs")}
# Per section: the library side every pair has (or None), and the Xyce sides of which a row must
# hold at least one (or None).
SECTION_PAIRS: dict[str, tuple[str | None, frozenset[str] | None]] = {
    "Forms Xyce runs and the library refuses": ("refuses", frozenset({"runs", "ignores"})),
    "Forms the manual and Xyce accept and the library refuses": ("refuses", frozenset({"runs"})),
    "Forms the library reads and Xyce stops on or ignores": (
        "reads",
        frozenset({"stops", "ignores"}),
    ),
    "Forms the library reads or refuses as Xyce does, against the manual": (None, None),
    "Where the manual is silent or imprecise": (None, None),
}
_PAIR = re.compile(r"`(\w+)/(\w+)`")


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
            # A row outside a table would be read as a header: every table starts with its own.
            assert header[0] == "Xyce 7.10", f"line {number}: a table without its header"
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


def _pairs(row: Row) -> list[tuple[str, str]]:
    """The row's Library/Xyce pairs; a cell outside the vocabulary fails."""
    cell = row.cells["Library/Xyce"]
    if cell == NOT_A_READING:
        return []
    parts = cell.split("; ")
    pairs = [match.groups() for part in parts if (match := _PAIR.fullmatch(part))]
    assert len(pairs) == len(parts), f"line {row.line}: {cell}"
    for library, xyce in pairs:
        assert library in LIBRARY_SIDES and xyce in XYCE_SIDES, f"line {row.line}: {cell}"
    assert len(set(pairs)) == len(pairs), f"line {row.line}: {cell}"
    return [(library, xyce) for library, xyce in pairs]


@pytest.mark.parametrize("row", ROWS, ids=_id)
def test_only_a_row_that_is_not_a_reading_has_no_pair(row: Row) -> None:
    if row.cells["Library/Xyce"] == NOT_A_READING:
        assert row.cells["Library behaviour"].startswith("Not a reading"), row.line
    else:
        assert _pairs(row), row.line


@pytest.mark.parametrize("row", ROWS, ids=_id)
def test_a_form_the_library_reads_and_xyce_stops_on_is_manual_or_a_limit(row: Row) -> None:
    """Decision 0029 item 2, from the row's own facts rather than its section."""
    if READS_WHAT_XYCE_STOPS_ON & set(_pairs(row)):
        assert row.cells["Category"].strip("`") in {"manual", "library-limit"}, (
            f"line {row.line}: the library reads a form Xyce stops on, so the row is `manual` "
            f"or `library-limit`, not {row.cells['Category']}"
        )


@pytest.mark.parametrize("row", ROWS, ids=_id)
def test_the_pairs_fit_the_section(row: Row) -> None:
    library, xyce = SECTION_PAIRS[row.section]
    pairs = _pairs(row)
    if library is not None:
        assert {side for side, _ in pairs} == {library}, f"line {row.line} in {row.section!r}"
    if xyce is not None:
        assert xyce & {side for _, side in pairs}, f"line {row.line} in {row.section!r}"


def test_every_section_has_its_pair_rule() -> None:
    assert list(SECTION_PAIRS) == list(SECTIONS)


def test_the_table_has_the_columns() -> None:
    for row in ROWS:
        expected = ["Xyce 7.10", "Library behaviour", "Library/Xyce", "Category", "Evidence"]
        if row.section != "Where the manual is silent or imprecise":
            expected.insert(1, "Manual")
        assert list(row.cells) == expected, row.line
