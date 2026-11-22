"""The xyce corpus (X-M1 B7, X-M2 B6; architecture §10, T1 and T8 tiers): accept families that
round-trip byte for byte, with every span slicing back to its text, and rejection families that
fail where their manifests say."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

import pytest

from netlistmod import (
    Formula,
    Identifier,
    ModelReference,
    Netlist,
    Node,
    NumericValue,
    ParamAssignment,
    ParseError,
    SourceText,
    Span,
    UnsupportedConstruct,
    parse,
)
from netlistmod.dialects import _XYCE

CORPUS = Path(__file__).parents[2] / "corpus" / "xyce"
ACCEPT_FAMILIES = (
    "structure_basic",
    "statements_basic",
    "elements_basic",
    "directives_basic",
    "sources_basic",
)
REJECT_FAMILIES = (
    "structure_rejects",
    "statements_rejects",
    "elements_rejects",
    "directives_rejects",
    "sources_rejects",
)
_ERRORS = {"ParseError": ParseError, "UnsupportedConstruct": UnsupportedConstruct}
_CLOSING = {"": "", "{": "}", "'": "'", '"': '"'}


def _manifest(family: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (CORPUS / family / "manifest.json").read_text(encoding="utf-8")
    )
    return data


def _accept_files() -> list[Path]:
    return [path for family in ACCEPT_FAMILIES for path in sorted((CORPUS / family).glob("*.cir"))]


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


def test_the_families_are_the_corpus() -> None:
    assert {path.name for path in CORPUS.iterdir()} == {*ACCEPT_FAMILIES, *REJECT_FAMILIES}


@pytest.mark.parametrize("path", _accept_files(), ids=_id)
def test_accept_files_round_trip_and_tile(path: Path) -> None:
    source = SourceText.read(path)
    result = parse(source, _XYCE)
    cursor = 0
    for item in result.items:
        assert item.span.start == cursor
        cursor = item.span.end
    assert cursor == len(source.text)
    assert source.to_bytes() == path.read_bytes()


@pytest.mark.parametrize("path", _accept_files(), ids=_id)
def test_every_sub_span_lies_in_its_item_and_slices_back(path: Path) -> None:
    source = SourceText.read(path)
    text = source.text
    checked = 0
    for item in parse(source, _XYCE).items:
        for node, span in _spanned(item):
            assert item.span.start <= span.start <= span.end <= item.span.end, node
            piece = text[span.start : span.end]
            if isinstance(node, NumericValue):
                assert piece == node.text
            elif isinstance(node, Formula):
                assert piece == f"{node.delimiter}{node.text}{_CLOSING[node.delimiter]}"
            elif isinstance(node, Identifier | Node):
                assert piece == node.name
            elif isinstance(node, ModelReference):
                assert piece == node.model_name
            elif isinstance(node, ParamAssignment):
                name = node.name_span
                assert text[name.start : name.end] == node.name
                assert piece.startswith(node.name)
            else:
                continue
            checked += 1
    assert checked


@pytest.mark.parametrize("path", _accept_files(), ids=_id)
def test_queries_run_on_every_accept_file(path: Path) -> None:
    netlist = Netlist.load(path, dialect=_XYCE)
    for scope in netlist.scopes:
        for net in netlist.nets(scope=scope.path):
            used = netlist.elements_on_net(net, scope=scope.path)
            assert used or scope.definition is not None or net.global_
        for element in netlist.elements(scope=scope.path):
            assert len(netlist.connections(element.designator, scope=scope.path)) == len(
                element.nodes
            )
    assert len(netlist.signature().digest()) == 64
    assert netlist.to_bytes() == path.read_bytes()


@pytest.mark.parametrize(
    ("crlf", "lf"),
    [("structure_basic/structure_crlf.cir", "structure_basic/structure.cir")]
    + [("elements_basic/elements_crlf.cir", "elements_basic/elements.cir")]
    + [("directives_basic/options_crlf.cir", "directives_basic/options.cir")]
    + [("sources_basic/sources_crlf.cir", "sources_basic/sources.cir")],
)
def test_a_crlf_twin_reads_as_its_lf_file(crlf: str, lf: str) -> None:
    crlf_bytes = (CORPUS / crlf).read_bytes()
    lf_bytes = (CORPUS / lf).read_bytes()
    assert b"\r\n" in crlf_bytes and b"\r\n" not in lf_bytes
    assert crlf_bytes.replace(b"\r\n", b"\n") == lf_bytes
    twin = Netlist.load(CORPUS / crlf, dialect=_XYCE)
    plain = Netlist.load(CORPUS / lf, dialect=_XYCE)
    assert [type(item) for item in twin.parse_result.items] == [
        type(item) for item in plain.parse_result.items
    ]
    assert twin.signature().digest() == plain.signature().digest()
    assert [d.code for d in twin.diagnostics] == [d.code for d in plain.diagnostics]


def _reject_cases() -> list[tuple[str, str]]:
    return [(family, name) for family in REJECT_FAMILIES for name in _manifest(family)["fixtures"]]


@pytest.mark.parametrize(("family", "name"), _reject_cases())
def test_reject_files_fail_where_the_manifest_says(family: str, name: str) -> None:
    expected = _manifest(family)["fixtures"][name]
    source = SourceText.read(CORPUS / family / name)
    with pytest.raises((ParseError, UnsupportedConstruct)) as captured:
        parse(source, _XYCE)
    assert type(captured.value) is _ERRORS[expected["error"]]
    assert (captured.value.line, captured.value.column) == (expected["line"], expected["column"])
