"""Statement corpora (M4): byte-exact round-trip, tiling (including bodies), sub-spans, rejects."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from netlistmod import (
    AcDirective,
    Component,
    DcDirective,
    Dialect,
    Formula,
    IcDirective,
    Identifier,
    MeasureDirective,
    ModelStatement,
    NodesetDirective,
    OptionsDirective,
    ParamStatement,
    ParseError,
    SaveDirective,
    SourceText,
    SubcktDefinition,
    TempDirective,
    TranDirective,
    UnsupportedConstruct,
    parse,
)

CORPUS_ROOT = Path(__file__).parents[1] / "corpus" / "ngspice"
REJECT_CORPUS = CORPUS_ROOT / "statements_rejects"
# RKM values occur only in the KiCad corpus; standard notation parses the same with rkm=True.
ALL_ACCEPT = sorted(
    path
    for family in CORPUS_ROOT.iterdir()
    if family.is_dir() and not family.name.endswith("_rejects")
    for path in family.glob("*.cir")
)


def _assert_tiling(items: tuple[Any, ...], start: int, end: int) -> None:
    offset = start
    for item in items:
        assert item.span.start == offset
        offset = item.span.end
    assert offset == end


def _walk(items: tuple[Any, ...]) -> Iterator[Any]:
    for item in items:
        yield item
        if isinstance(item, SubcktDefinition):
            yield from _walk(item.body)


def _named_spans(item: Any) -> list[tuple[Any, str | None]]:
    """Each sub-span of a typed dot-command with the text it must slice back to (or None)."""
    pairs: list[tuple[Any, str | None]] = []
    keyword_span = getattr(item, "keyword_span", None)
    if keyword_span is not None:
        pairs.append((keyword_span, item.keyword))
    if isinstance(item, ParamStatement | ModelStatement | SubcktDefinition):
        params = item.assignments if isinstance(item, ParamStatement) else item.params
        for param in params:
            pairs += [(param.name_span, param.name), (param.value.span, None)]
    if isinstance(item, ModelStatement):
        pairs += [(item.name_span, item.name), (item.model_type_span, item.model_type)]
    if isinstance(item, SubcktDefinition):
        pairs.append((item.name_span, item.name))
        pairs += [(port.span, port.name) for port in item.ports]
        if item.ends.name is not None:
            pairs.append((item.ends.name_span, item.ends.name))
    if isinstance(item, TranDirective | AcDirective | TempDirective):
        names = ("tstep", "tstop", "tstart", "tmax", "points", "fstart", "fstop", "value")
        pairs += [(v.span, None) for v in (getattr(item, n, None) for n in names) if v]
        if isinstance(item, TranDirective) and item.uic is not None:
            pairs.append((item.uic.span, item.uic.name))
        if isinstance(item, AcDirective):
            pairs.append((item.variation_span, item.variation))
    if isinstance(item, DcDirective):
        for sweep in item.sweeps:
            pairs.append((sweep.source_span, sweep.source))
            pairs += [(v.span, None) for v in (sweep.start, sweep.stop, sweep.increment)]
    if isinstance(item, OptionsDirective):
        for option in item.options:
            pairs.append((option.name_span, option.name))
            if isinstance(option.value, Identifier):
                pairs.append((option.value.span, option.value.name))
            elif option.value is not None:
                pairs.append((option.value.span, None))
    if isinstance(item, IcDirective | NodesetDirective):
        for condition in item.conditions:
            pairs.append((condition.value.span, None))
            if condition.node is not None:
                pairs.append((condition.node.span, condition.node.name))
    if isinstance(item, SaveDirective):
        pairs += [(vector.span, vector.text) for vector in item.vectors]
        for vector in item.vectors:
            pairs += [(node.span, node.name) for node in vector.nodes]
            if vector.source is not None:
                pairs.append((vector.source.span, vector.source.designator))
    if isinstance(item, MeasureDirective):
        pairs += [
            (item.analysis_span, item.analysis),
            (item.result_span, item.result),
            (item.body_span, item.body_text),
        ]
    return pairs


@pytest.mark.parametrize("path", ALL_ACCEPT, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_accept_corpora_round_trip_and_tile_including_bodies(path: Path) -> None:
    data = path.read_bytes()
    source = SourceText.from_bytes(data)
    result = parse(source, Dialect.NGSPICE, rkm=True)
    assert source.to_bytes() == data
    _assert_tiling(result.items, 0, len(source.text))
    for item in _walk(result.items):
        if isinstance(item, SubcktDefinition):
            assert item.header_span.start == item.span.start
            _assert_tiling(item.body, item.header_span.end, item.ends.span.start)
            assert item.ends.span.end == item.span.end


@pytest.mark.parametrize("path", ALL_ACCEPT, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_every_sub_span_slices_back_to_its_text(path: Path) -> None:
    source = SourceText.from_bytes(path.read_bytes())
    for item in _walk(parse(source, Dialect.NGSPICE, rkm=True).items):
        if isinstance(item, Component):
            continue
        for span, expected in _named_spans(item):
            text = source.text[span.start : span.end]
            assert text and not text[0].isspace() and not text[-1].isspace(), path.name
            if expected is not None:
                assert text == expected, path.name


def test_statement_corpus_holds_every_typed_construct() -> None:
    kinds: set[str] = set()
    for path in sorted((CORPUS_ROOT / "statements_basic").glob("*.cir")):
        source = SourceText.from_bytes(path.read_bytes())
        kinds |= {type(item).__name__ for item in _walk(parse(source, Dialect.NGSPICE).items)}
    assert {
        "ParamStatement",
        "ModelStatement",
        "SubcktDefinition",
        "TranDirective",
        "AcDirective",
        "DcDirective",
        "OpDirective",
        "OptionsDirective",
        "TempDirective",
        "IcDirective",
        "NodesetDirective",
        "SaveDirective",
        "MeasureDirective",
    } <= kinds


def test_nested_definition_and_multi_line_model_in_the_corpus() -> None:
    folder = CORPUS_ROOT / "statements_basic"
    source = SourceText.from_bytes((folder / "subcircuits.cir").read_bytes())
    items = parse(source, Dialect.NGSPICE).items
    outer = next(i for i in items if isinstance(i, SubcktDefinition) and i.name == "outer")
    inner = next(i for i in outer.body if isinstance(i, SubcktDefinition))
    assert (inner.name, inner.ends.name, outer.ends.name) == ("inner", "inner", None)
    div = next(i for i in items if isinstance(i, SubcktDefinition) and i.name == "div")
    assert [(p.name, p.value.text) for p in div.params] == [("r2", "1k")]

    source = SourceText.from_bytes((folder / "params_models.cir").read_bytes())
    model = next(
        i
        for i in parse(source, Dialect.NGSPICE).items
        if isinstance(i, ModelStatement) and i.name == "dslow"
    )
    assert model.parenthesized
    assert [(p.name, p.value.text) for p in model.params] == [
        ("is", "1e-15"),
        ("n", "1.5"),
        ("rs", "10"),
    ]
    assert source.text[model.span.start : model.span.end].count("\n") == 3
    analyses = SourceText.from_bytes((folder / "analyses.cir").read_bytes())
    saves = [i for i in parse(analyses, Dialect.NGSPICE).items if isinstance(i, SaveDirective)]
    assert [(v.function, [n.name for n in v.nodes]) for v in saves[1].vectors] == [
        ("vm", ["out"]),
        ("vdb", ["out"]),
        ("v", ["in", "out"]),
        ("v", ["in"]),
    ]
    params = [i for i in parse(source, Dialect.NGSPICE).items if isinstance(i, ParamStatement)]
    assert any(
        isinstance(a.value, Formula) and a.value.delimiter == '"'
        for p in params
        for a in p.assignments
    )


def test_rejection_corpus_reports_manifest_positions_and_kinds() -> None:
    manifest: dict[str, Any] = json.loads(
        (REJECT_CORPUS / "manifest.json").read_text(encoding="utf-8")
    )
    fixtures: dict[str, dict[str, Any]] = manifest["fixtures"]
    assert len(fixtures) >= 25
    kinds = {"ParseError": ParseError, "UnsupportedConstruct": UnsupportedConstruct}
    for filename, expected in fixtures.items():
        source = SourceText.from_bytes((REJECT_CORPUS / filename).read_bytes())
        with pytest.raises((ParseError, UnsupportedConstruct)) as captured:
            parse(source, Dialect.NGSPICE)
        error = captured.value
        assert type(error) is kinds[expected["error"]], filename
        assert (error.line, error.column) == (expected["line"], expected["column"]), filename
