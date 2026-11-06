"""Corpus helpers shared by the tests that read every accept file of a dialect.

A fixture whose manifest entry holds ``"pending": "<milestone>"`` is a file written ahead of the
milestone that makes it load (M15 decision 1: the files of M15b's forms). Until then it is left
out of the accept lists, and the solver sweeps skip it through its ``solver.skip`` field.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=None)
def pending_files(family: Path) -> frozenset[str]:
    """The names of a family's fixtures that wait for a later milestone."""
    manifest = family / "manifest.json"
    if not manifest.is_file():
        return frozenset()
    fixtures = json.loads(manifest.read_text(encoding="utf-8")).get("fixtures", {})
    return frozenset(
        name for name, entry in fixtures.items() if isinstance(entry, dict) and "pending" in entry
    )


def accept_files(root: Path, suffixes: tuple[str, ...] = (".cir",)) -> list[Path]:
    """Every accept file under ``root`` (a dialect's corpus folder), without the pending ones."""
    return sorted(
        path
        for family in root.iterdir()
        if family.is_dir() and not family.name.endswith("_rejects")
        for path in family.iterdir()
        if path.suffix in suffixes and path.name not in pending_files(family)
    )
