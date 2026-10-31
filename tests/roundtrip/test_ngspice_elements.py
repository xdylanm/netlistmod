"""Element corpora (M3): byte-exact round-trip, span tiling, sub-spans and rejection positions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from netlistmod import (
    Component,
    Dialect,
    MutualCoupling,
    NumericValue,
    ParseError,
    Resistor,
    SourceText,
    SubcktInstance,
    UnsupportedConstruct,
    VoltageSource,
    parse,
)

CORPUS_ROOT = Path(__file__).parents[1] / "corpus" / "ngspice"
ACCEPT_FAMILIES = ("elements_basic", "structure_basic")
REJECT_CORPUS = CORPUS_ROOT / "elements_rejects"
KICAD = CORPUS_ROOT / "kicad_basic"


def _assert_tiling(text: str, items: tuple[object, ...]) -> None:
    offset = 0
    for item in items:
        span = item.span  # type: ignore[attr-defined]
        assert span.start == offset
        offset = span.end
    assert offset == len(text)


def _sub_spans(element: Component) -> list[tuple[Any, str]]:
    """Every editable sub-span of an element, with the text it must slice back to."""
    pairs: list[tuple[Any, str]] = [(element.designator_span, element.designator)]
    pairs += [(node.span, node.name) for node in element.nodes]
    for param in element.params:
        pairs.append((param.name_span, param.name))
        pairs.append((param.value.span, None))
    for name in ("value", "model", "dc", "subckt"):
        slot = getattr(element, name, None)
        if slot is not None:
            pairs.append((slot.span, getattr(slot, "model_name", getattr(slot, "name", None))))
    if isinstance(element, MutualCoupling):
        pairs += [(ref.span, ref.designator) for ref in element.inductors]
    return pairs


@pytest.mark.parametrize("family", ACCEPT_FAMILIES)
def test_element_corpus_round_trips_and_spans_tile(family: str) -> None:
    paths = sorted((CORPUS_ROOT / family).glob("*.cir"))
    assert paths
    for path in paths:
        data = path.read_bytes()
        source = SourceText.from_bytes(data)
        result = parse(source, Dialect.NGSPICE)
        _assert_tiling(source.text, result.items)
        assert source.to_bytes() == data
        for element in (item for item in result.items if isinstance(item, Component)):
            assert source.text[element.span.start : element.span.end].strip()
            for span, expected in _sub_spans(element):
                text = source.text[span.start : span.end]
                assert text and not text[0].isspace() and not text[-1].isspace(), path.name
                if expected is not None:
                    assert text == expected, path.name


def test_every_value_text_is_the_slice_of_its_span() -> None:
    for path in sorted((CORPUS_ROOT / "elements_basic").glob("*.cir")):
        source = SourceText.from_bytes(path.read_bytes())
        for item in parse(source, Dialect.NGSPICE).items:
            for value in _values(item):
                sliced = source.text[value.span.start : value.span.end]
                if isinstance(value, NumericValue):
                    assert value.text == sliced
                else:
                    assert sliced[0] == value.delimiter and value.text == sliced[1:-1]


def _values(item: object) -> list[Any]:
    values = [getattr(item, name, None) for name in ("value", "dc")]
    ac = getattr(item, "ac", None)
    if ac is not None:
        values += [ac.magnitude, ac.phase]
    values += [param.value for param in getattr(item, "params", ())]
    return [value for value in values if value is not None]


def test_rejection_corpus_reports_manifest_positions_and_kinds() -> None:
    manifest: dict[str, Any] = json.loads(
        (REJECT_CORPUS / "manifest.json").read_text(encoding="utf-8")
    )
    fixtures: dict[str, dict[str, Any]] = manifest["fixtures"]
    assert fixtures
    kinds = {"ParseError": ParseError, "UnsupportedConstruct": UnsupportedConstruct}
    for filename, expected in fixtures.items():
        source = SourceText.from_bytes((REJECT_CORPUS / filename).read_bytes())
        with pytest.raises((ParseError, UnsupportedConstruct)) as captured:
            parse(source, Dialect.NGSPICE)
        error = captured.value
        assert type(error) is kinds[expected["error"]], filename
        assert (error.line, error.column) == (expected["line"], expected["column"]), filename


@pytest.mark.parametrize("name", ["dc_basic_r_divider.cir", "ac_basic_rc_lpf.cir"])
def test_kicad_fixtures_with_rkm_values_need_the_rkm_option(name: str) -> None:
    data = (KICAD / name).read_bytes()
    source = SourceText.from_bytes(data)
    if name == "dc_basic_r_divider.cir":
        with pytest.raises(ParseError, match="RKM notation") as captured:
            parse(source, Dialect.NGSPICE)
        assert (captured.value.line, captured.value.column) == (3, 12)  # R2 /vout 0 1k0
    result = parse(source, Dialect.NGSPICE, rkm=True)
    _assert_tiling(source.text, result.items)
    assert source.to_bytes() == data


def test_kicad_fixtures_parse_into_typed_elements() -> None:
    divider = parse(
        SourceText.from_bytes((KICAD / "dc_basic_r_divider.cir").read_bytes()),
        Dialect.NGSPICE,
        rkm=True,
    )
    source, r2, r1 = divider.items[1:4]
    assert isinstance(source, VoltageSource)
    assert ([n.name for n in source.nodes], source.dc_keyword) == (["/vin", "0"], True)
    assert source.dc is not None and source.dc.text == "2"
    assert isinstance(r1, Resistor) and isinstance(r2, Resistor)
    assert r1.value == NumericValue("1k0", r1.value.span, "rkm", False)  # type: ignore[union-attr]
    assert [n.name for n in r1.nodes] == ["/vin", "/vout"]

    lpf = parse(
        SourceText.from_bytes((KICAD / "ac_basic_rc_lpf.cir").read_bytes()), Dialect.NGSPICE
    )
    v1 = lpf.items[1]
    assert isinstance(v1, VoltageSource) and v1.ac is not None
    assert (v1.dc.text, v1.ac.magnitude.text, v1.ac.phase) == ("0", "1", None)  # type: ignore[union-attr]

    decimal = parse(
        SourceText.from_bytes((KICAD / "dc_basic_r_divider_decimal_vals.cir").read_bytes()),
        Dialect.NGSPICE,
    )
    assert [type(item).__name__ for item in decimal.items] == [
        "Title",
        "VoltageSource",
        "Resistor",
        "Resistor",
        "End",
    ]


def test_continued_subcircuit_call_in_the_corpus_keeps_comments_and_nodes() -> None:
    source = SourceText.from_bytes(
        (CORPUS_ROOT / "elements_basic" / "continuations_comments.cir").read_bytes()
    )
    items = parse(source, Dialect.NGSPICE).items
    call = next(item for item in items if isinstance(item, SubcktInstance))
    assert [n.name for n in call.nodes] == ["a", "b"]
    assert call.subckt.name == "sub"
    assert [source.text[s.start : s.end] for s in call.trailing_comments] == ["; node b"]
