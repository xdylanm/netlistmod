"""The LTspice corpus (M8 T8): accept and reject families, exports, encoding and round trips."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

import pytest

from netlistmod import (
    Dialect,
    Netlist,
    ParseError,
    SourceText,
    Span,
    SubcktInstance,
    UnsupportedConstruct,
    VoltageSource,
    parse,
)

CORPUS = Path(__file__).parents[2] / "corpus" / "ltspice"
ACCEPT_FAMILIES = ("elements_basic", "statements_basic", "names_basic")
REJECT_FAMILIES = ("elements_rejects", "statements_rejects", "names_rejects")
EXPORTS = CORPUS / "contributed_examples"
_ERRORS = {"ParseError": ParseError, "UnsupportedConstruct": UnsupportedConstruct}


def _manifest(family: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((family / "manifest.json").read_text(encoding="utf-8"))
    return data


def _accept_files() -> list[Path]:
    files = [path for name in ACCEPT_FAMILIES for path in sorted((CORPUS / name).glob("*.cir"))]
    errors = _manifest(EXPORTS)["fixtures"]
    files += [p for p in sorted(EXPORTS.glob("*.net")) if isinstance(errors[p.name], str)]
    files += sorted((CORPUS / "encoding_samples").glob("*.net"))
    files += sorted((CORPUS / "encoding_samples").glob("*.cir"))
    files += sorted((CORPUS / "m0_export_candidate").glob("*.net"))
    return files


def _id(path: Path) -> str:
    return f"{path.parent.name}/{path.name}"


def _spanned(node: object) -> Iterator[tuple[object, Span]]:
    if isinstance(node, tuple):
        for element in node:
            yield from _spanned(element)
    elif is_dataclass(node) and not isinstance(node, type | Span):
        span = getattr(node, "span", None)
        if isinstance(span, Span):
            yield node, span
        for field in fields(node):
            yield from _spanned(getattr(node, field.name))


@pytest.mark.parametrize("path", _accept_files(), ids=_id)
def test_accept_files_round_trip_and_tile(path: Path) -> None:
    source = SourceText.read(path)
    result = parse(source, Dialect.LTSPICE)
    cursor = 0
    for item in result.items:
        assert item.span.start == cursor
        cursor = item.span.end
    assert cursor == len(source.text)
    assert source.to_bytes() == path.read_bytes()


@pytest.mark.parametrize("path", _accept_files(), ids=_id)
def test_every_text_slot_slices_back_to_its_text(path: Path) -> None:
    source = SourceText.read(path)
    for node, span in _spanned(parse(source, Dialect.LTSPICE).items):
        text = getattr(node, "text", None)
        delimiter = getattr(node, "delimiter", "")
        if isinstance(text, str) and not delimiter and type(node).__name__ == "NumericValue":
            assert source.text[span.start : span.end] == text


@pytest.mark.parametrize("path", _accept_files(), ids=_id)
def test_queries_run_on_every_accept_file(path: Path) -> None:
    netlist = Netlist.load(path, dialect=Dialect.LTSPICE)
    for scope in netlist.scopes:
        for net in netlist.nets(scope.path):
            used = netlist.elements_on_net(net, scope.path)
            assert used or scope.definition is not None or net.global_
        for element in netlist.elements(scope.path):
            assert len(netlist.connections(element.designator, scope.path)) == len(element.nodes)
    assert len(netlist.signature().digest()) == 64
    assert netlist.to_bytes() == path.read_bytes()


def _reject_cases() -> list[tuple[str, str]]:
    return [
        (family, name)
        for family in REJECT_FAMILIES
        for name in _manifest(CORPUS / family)["fixtures"]
    ]


@pytest.mark.parametrize(("family", "name"), _reject_cases())
def test_reject_files_fail_where_the_manifest_says(family: str, name: str) -> None:
    expected = _manifest(CORPUS / family)["fixtures"][name]
    source = SourceText.read(CORPUS / family / name)
    with pytest.raises((ParseError, UnsupportedConstruct)) as captured:
        parse(source, Dialect.LTSPICE)
    assert type(captured.value) is _ERRORS[expected["error"]]
    assert (captured.value.line, captured.value.column) == (expected["line"], expected["column"])


def test_exports_are_utf8_without_a_bom_and_hold_the_micro_signs() -> None:
    for path in EXPORTS.glob("*.net"):
        source = SourceText.read(path)
        assert source.encoding == "utf-8" and not source.bom, path.name
        assert path.read_bytes().startswith(f"* {path.stem}.asc\n".encode())
    assert "1µ" in SourceText.read(EXPORTS / "simple_transformer.net").text
    assert "1μ" in SourceText.read(EXPORTS / "rc_lowpass.net").text


def test_exports_parse_into_the_expected_values() -> None:
    lowpass = Netlist.load(EXPORTS / "rc_lowpass.net", dialect=Dialect.LTSPICE)
    assert lowpass.element("R1").value.notation == "rkm"
    assert lowpass.element("C1").value.text == "1μ"
    transformer = Netlist.load(EXPORTS / "simple_transformer.net", dialect=Dialect.LTSPICE)
    assert transformer.element("L1").params[0].name == "Rser"
    assert transformer.element("V1").params[0].value.text == "10m"
    buses = Netlist.load(EXPORTS / "bus_connectors.net", dialect=Dialect.LTSPICE)
    assert {"d[0]", "d[1]"} <= {net.name for net in buses.nets()}
    subcircuit = Netlist.load(EXPORTS / "r_divider_subckt.net", dialect=Dialect.LTSPICE)
    instance = subcircuit.element("X§U2")
    assert isinstance(instance, SubcktInstance)
    assert instance.subckt.name == "BasicR" and instance.params[0].value.text == "4.7k"
    assert not subcircuit.diagnostics[1:]  # .backanno is the only finding


def test_the_export_with_a_source_function_loads() -> None:
    result = parse(SourceText.read(EXPORTS / "half_rectifier.net"), Dialect.LTSPICE)
    source = next(item for item in result.items if isinstance(item, VoltageSource))
    assert source.stimulus is not None
    assert source.stimulus.name == "SINE"
    assert [arg.text for arg in source.stimulus.args] == ["0", "1", "60k"]
    assert [param.name for param in source.params] == ["Rser"]


def test_encodings_round_trip() -> None:
    utf16 = SourceText.read(CORPUS / "encoding_samples" / "utf16le_bom.cir")
    assert utf16.encoding == "utf-16-le" and utf16.bom
    assert parse(utf16, Dialect.LTSPICE).items[3].value.text == "1µ"
    cp1252 = SourceText.from_bytes("t\nC1 a 0 1µ\n.end\n".encode("cp1252"))
    assert cp1252.encoding == "cp1252"
    assert parse(cp1252, Dialect.LTSPICE).items[1].value.text == "1µ"
    # BOM-less UTF-16LE is not detected (decision 0009): the caller decodes it and names it.
    bomless = "t\nR1 a 0 1k\n.end\n".encode("utf-16-le")
    named = SourceText(bomless.decode("utf-16-le"), encoding="utf-16-le")
    assert parse(named, Dialect.LTSPICE).items[1].value.text == "1k"
    assert named.to_bytes() == bomless
    with pytest.raises(ParseError):
        parse(SourceText.from_bytes(bomless), Dialect.LTSPICE)
