"""The M8 regression gate (T1, decision 3): the ngspice parse of every corpus file is unchanged.

``tree_snapshot.json`` was generated before ``core.lark`` was split for LTspice. It holds, per
corpus netlist and per ``rkm`` mode, a digest of the node classes and spans of the parse, or the
error class, position and expected terminals of a rejected file, so a change of lexer state shows
as well. Regenerating it is a deliberate act:
``python -m tests.grammar.ngspice.test_tree_snapshot``. It was regenerated for M9 H2, when parse
errors for incomplete lines stopped listing punctuation as expected, and text after ``.end`` stopped
being reported as an unsupported letter. 15 rejected files changed: 14 lost those names, and
``structure_rejects/text_after_end.cir`` went from ``UnsupportedConstruct`` to ``ParseError``. No
node or position changed. M11 added ``structure_basic/lib_block.cir`` and
``edits_golden/add_lib_block.expected.cir``, and no other entry changed. M12 removed the three
rejected source function files, added the new accept files and golden files, and changed no other
entry. M13 added the ``kicad_transistors`` family; 17 rejected files gained the four transistor
letters among their expected terminals, and no node, position or error class changed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import fields, is_dataclass
from pathlib import Path

import pytest

from netlistmod import Dialect, ParseError, SourceText, Span, UnsupportedConstruct, parse

ROOT = Path(__file__).parents[3]
CORPUS = ROOT / "tests" / "corpus" / "ngspice"
SNAPSHOT = Path(__file__).with_name("tree_snapshot.json")
NETLIST_SUFFIXES = {".cir", ".net", ".sp"}


def _corpus_files() -> list[Path]:
    return sorted(
        path
        for path in CORPUS.rglob("*")
        if path.suffix.lower() in NETLIST_SUFFIXES and "solver_stubs" not in path.parts
    )


def _walk(node: object) -> Iterator[tuple[str, int, int]]:
    """Every node with a span, depth first: its class and span. Unset optional fields are
    skipped, so a field that only another dialect fills does not change the digest."""
    if isinstance(node, tuple):
        for element in node:
            yield from _walk(element)
    elif is_dataclass(node) and not isinstance(node, type | Span):
        span = getattr(node, "span", None)
        if isinstance(span, Span):
            yield type(node).__name__, span.start, span.end
        for field in fields(node):
            yield from _walk(getattr(node, field.name))


def _outcome(source: SourceText, *, rkm: bool) -> dict[str, object]:
    try:
        result = parse(source, Dialect.NGSPICE, rkm=rkm)
    except (ParseError, UnsupportedConstruct) as error:
        expected = sorted(getattr(error, "expected", ()))
        return {
            "error": type(error).__name__,
            "line": error.line,
            "column": error.column,
            "expected": expected,
        }
    nodes = list(_walk(result.items))
    encoded = json.dumps(nodes, separators=(",", ":")).encode("utf-8")
    return {"nodes": len(nodes), "digest": hashlib.sha256(encoded).hexdigest()}


def _snapshot() -> dict[str, dict[str, object]]:
    snapshot: dict[str, dict[str, object]] = {}
    for path in _corpus_files():
        source = SourceText.read(path)
        snapshot[path.relative_to(CORPUS).as_posix()] = {
            "standard": _outcome(source, rkm=False),
            "rkm": _outcome(source, rkm=True),
        }
    return snapshot


def test_snapshot_covers_the_ngspice_corpus() -> None:
    recorded = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert set(recorded) == {path.relative_to(CORPUS).as_posix() for path in _corpus_files()}


@pytest.mark.parametrize(
    "path", _corpus_files(), ids=lambda path: path.relative_to(CORPUS).as_posix()
)
def test_ngspice_parse_matches_the_snapshot(path: Path) -> None:
    recorded = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    source = SourceText.read(path)
    expected = recorded[path.relative_to(CORPUS).as_posix()]
    assert _outcome(source, rkm=False) == expected["standard"]
    assert _outcome(source, rkm=True) == expected["rkm"]


if __name__ == "__main__":
    SNAPSHOT.write_text(json.dumps(_snapshot(), indent=1, sort_keys=True) + "\n", encoding="utf-8")
