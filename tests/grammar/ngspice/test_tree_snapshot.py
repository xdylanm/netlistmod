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
letters among their expected terminals, and no node, position or error class changed. M14 added
the ``controlled_sources`` family, the controlled-source golden files, five ``elements_rejects``
files and ``document_basic/control_source.cir``; the same 17 rejected files gained the six new
letters among their expected terminals. No other entry changed. M14 review R1 changed two:
``elements_rejects/e_two_values.cir`` now has its own reason and no expected terminals, and
``elements_rejects/e_m.cir`` lists the value terminals of a second gain; positions and error
classes are the same. M15 added the behavioural ``controlled_sources`` files (the M15b ones
among them, as rejected files), the behavioural golden files, six ``elements_rejects`` files and
``document_basic/node_read.cir``, and removed ``elements_rejects/charge_capacitor.cir``, which
now loads. The same 17 rejected files gained the B letter among their expected terminals; no
other entry changed. M15 review R2 added ``elements_rejects/e_value_node.cir``, and no other
entry changed.
M15b (decision 0017) loaded the ten ``controlled_sources`` files of its forms that M15 had
written as rejected files, so their entries changed from an error to a parse; it changed
``elements_rejects/e_poly_too_few.cir`` from ``UnsupportedConstruct`` to a ``ParseError`` at the
line's end, and added three ``controlled_sources`` files, eleven ``elements_rejects`` files
and the ``nonlinear_*`` golden files. No other entry changed, and no rejected file's expected
terminals changed: M15b adds no element letter. M15b review round 1 replaced
``elements_rejects/e_freq_hz.cir`` with ``elements_rejects/e_freq_first_point.cir`` and added
``controlled_sources/test_esource_freq_manual.cir``; no other entry changed.
M16's task list added the ``transmission_lines`` family with the maintainer's KiCad export,
``test_kicad_tline.cir``, as a rejected file (an O line, unsupported until M16 loads it); no
other entry changed.
M16 (decision 0019) loaded ``test_kicad_tline.cir``, so its entry changed from an error to a
parse, and added the ``transmission_lines`` variants, the ``lines*`` golden files, fourteen
``elements_rejects`` files and two ``statements_rejects`` files.
``elements_rejects/phase_2_letter.cir``
and ``structure_rejects/element_line.cir`` held a T line as the planned letter; they now hold an
A line, which stays planned until M17, so their entries (an unsupported construct at line 2,
column 1) did not change. The same 17
rejected files gained the five new letters among their expected terminals. No node, position or
error class of any other entry changed.
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
