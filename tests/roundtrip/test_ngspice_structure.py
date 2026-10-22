from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from netlistmod import Dialect, ParseError, SourceText, UnsupportedConstruct, parse

CORPUS_ROOT = Path(__file__).parents[1] / "corpus" / "ngspice"
CORPUS = CORPUS_ROOT / "structure_basic"
REJECT_CORPUS = CORPUS_ROOT / "structure_rejects"


def _assert_tiling(text: str, items: tuple[object, ...]) -> None:
    offset = 0
    for item in items:
        span = item.span  # type: ignore[attr-defined]
        assert span.start == offset
        offset = span.end
    assert offset == len(text)


def test_structural_corpus_parses_and_preserves_bytes() -> None:
    paths = sorted(CORPUS.glob("*.cir"))
    assert paths
    for path in paths:
        data = path.read_bytes()
        source = SourceText.from_bytes(data)
        result = parse(source, Dialect.NGSPICE)
        _assert_tiling(source.text, result.items)
        assert source.to_bytes() == data


def test_rejection_corpus_reports_manifest_positions() -> None:
    manifest: dict[str, Any] = json.loads(
        (REJECT_CORPUS / "manifest.json").read_text(encoding="utf-8")
    )
    fixtures: dict[str, dict[str, int | str]] = manifest["fixtures"]
    assert fixtures
    for filename, expected in fixtures.items():
        source = SourceText.from_bytes((REJECT_CORPUS / filename).read_bytes())
        with pytest.raises((ParseError, UnsupportedConstruct)) as captured:
            parse(source, Dialect.NGSPICE)
        error = captured.value
        assert (error.line, error.column) == (
            expected["line"],
            expected["column"],
        ), filename


def test_inline_bytes_round_trip_with_line_and_encoding_variants() -> None:
    cases = [
        b"title\r\n.foo x\r\n.end\r\n",
        b"title\n.foo x\r\n\n.end",
        b"title\n\t.foo\tvalue \t\n.end",
        "µ title\n.foo µ\n.end".encode("utf-8"),
        b"title\rcarriage return remains title text\n.end",
        b"title\r\n.foo comment\rinside\n.end\n",
    ]
    for data in cases:
        source = SourceText.from_bytes(data)
        result = parse(source, Dialect.NGSPICE)
        _assert_tiling(source.text, result.items)
        assert source.to_bytes() == data


def test_mixed_endings_are_kept_in_physical_item_spans() -> None:
    text = "title\r\n* comment\n.foo x\r\n.end"
    result = parse(SourceText(text), Dialect.NGSPICE)
    _assert_tiling(text, result.items)
    assert "".join(text[item.span.start : item.span.end] for item in result.items) == text
