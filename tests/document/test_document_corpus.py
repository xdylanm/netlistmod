"""Queries on corpus circuits (M5 exit): document_basic expectations and every accept corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from netlistmod import DiagnosticCode, Dialect, Netlist

pytestmark = pytest.mark.ngspice_only

CORPUS_ROOT = Path(__file__).parents[1] / "corpus" / "ngspice"
FAMILY = CORPUS_ROOT / "document_basic"
MANIFEST: dict[str, Any] = json.loads((FAMILY / "manifest.json").read_text(encoding="utf-8"))
ACCEPT_FILES = sorted(
    path
    for family in CORPUS_ROOT.iterdir()
    if family.is_dir() and not family.name.endswith("_rejects")
    for path in family.glob("*.cir")
)
_UNRESOLVED = {
    "model": DiagnosticCode.UNRESOLVED_MODEL,
    "subckt": DiagnosticCode.UNRESOLVED_SUBCKT,
    "param": DiagnosticCode.UNRESOLVED_PARAM,
    "element": DiagnosticCode.UNRESOLVED_ELEMENT,
}


def _path(scope: str) -> tuple[str, ...]:
    return tuple(scope.split("/")) if scope else ()


@pytest.mark.parametrize("name", sorted(MANIFEST["fixtures"]))
def test_document_basic_queries_match_the_manifest(name: str) -> None:
    expected = MANIFEST["fixtures"][name]
    netlist = Netlist.load(FAMILY / name, dialect=Dialect.NGSPICE, rkm=expected.get("rkm", False))
    assert {"/".join(scope.path) for scope in netlist.scopes} == set(expected["nets"])
    for scope, nets in expected["nets"].items():
        found = netlist.nets(_path(scope))
        assert [[net.name, "/".join(net.scope)] for net in found] == nets
    for designator, nets in expected["connections"].items():
        assert [c.net.name for c in netlist.connections(designator)] == nets
    assert [
        [ref.kind, ref.name, "/".join(ref.scope), ref.target is not None]
        for ref in netlist.references
    ] == expected["references"]
    assert [[d.code.value, d.severity, d.line, d.column] for d in netlist.diagnostics] == expected[
        "diagnostics"
    ]


def test_every_diagnostic_code_occurs_in_the_corpus() -> None:
    codes = {
        code for fixture in MANIFEST["fixtures"].values() for code, *_ in fixture["diagnostics"]
    }
    assert codes == {code.value for code in DiagnosticCode}


@pytest.mark.parametrize("path", ACCEPT_FILES, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_queries_run_on_every_accept_corpus_file(path: Path) -> None:
    netlist = Netlist.load(path, dialect=Dialect.NGSPICE, rkm=True)
    diagnosed = {(d.code, d.span) for d in netlist.diagnostics if d.code in _UNRESOLVED.values()}
    for reference in netlist.references:
        if reference.target is None and reference.kind in _UNRESOLVED:
            assert (_UNRESOLVED[reference.kind], reference.span) in diagnosed, reference
    for scope in netlist.scopes:
        for net in netlist.nets(scope.path):
            assert netlist.elements_on_net(net, scope.path) or scope.definition is not None
        for element in netlist.elements(scope.path):
            assert len(netlist.connections(element.designator, scope.path)) == len(element.nodes)
    assert len(netlist.signature().digest()) == 64
    assert netlist.to_bytes() == path.read_bytes()
