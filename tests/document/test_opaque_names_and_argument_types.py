"""H5 argument types and H8 names in opaque blocks (M11 T5, T8; decision 0012 item 5)."""

from __future__ import annotations

import pytest

from netlistmod import (
    Diagnostic,
    DiagnosticCode,
    Dialect,
    EditError,
    Netlist,
    SourceText,
    parse,
)
from tests.support.dialects import current_dialect

_NESTED = (
    "t\n.subckt a p\n.subckt b q\nR1 q 0 1k\n.ends\n.ends\n.subckt ab r\nR2 r 0 1k\n.ends\n.end\n"
)


def _netlist(body: str) -> Netlist:
    return Netlist.from_text(f"t\nV1 a 0 1\n{body}.end\n", dialect=current_dialect())


def _found(netlist: Netlist, code: DiagnosticCode) -> Diagnostic:
    (diagnostic,) = [item for item in netlist.diagnostics if item.code is code]
    return diagnostic


def test_a_string_is_not_a_scope() -> None:
    netlist = Netlist.from_text(_NESTED, dialect=current_dialect())
    with pytest.raises(TypeError, match=r"\('ab',\)"):
        netlist.scope("ab")
    with pytest.raises(TypeError, match=r"\('ab',\)"):
        netlist.nets("ab")


@pytest.mark.parametrize("path", [("ab",), ["ab"]], ids=["tuple", "list"])
def test_a_sequence_is_a_scope(path: tuple[str, ...] | list[str]) -> None:
    netlist = Netlist.from_text(_NESTED, dialect=current_dialect())
    assert [net.name for net in netlist.nets(path)] == ["r", "0"]


def test_parse_names_source_text() -> None:
    with pytest.raises(TypeError, match="SourceText, not str"):
        parse("t\n.end\n", current_dialect())  # type: ignore[arg-type]
    assert parse(SourceText("t\n.end\n"), current_dialect()) is not None


_LIB = ".lib x\n.model dm D\n.endl\n"
_IF = ".if (1)\n.model dm D\n.endif\n"
_BLOCKS = {
    Dialect.NGSPICE: [_LIB, _IF, '.lib "m.lib" x\n'],
    Dialect.LTSPICE: [_LIB, '.lib "m.lib" x\n'],
}


def _opaque_sources() -> list[str]:
    return _BLOCKS[current_dialect()]


def test_an_unresolved_model_is_info_beside_an_opaque_source() -> None:
    for source in _opaque_sources():
        netlist = _netlist(f"D1 a 0 dm\n{source}")
        diagnostic = _found(netlist, DiagnosticCode.UNRESOLVED_MODEL)
        assert diagnostic.severity == "info", source
        assert "opaque block" in diagnostic.message


def test_an_unresolved_model_is_a_warning_with_no_opaque_source() -> None:
    assert _found(_netlist("D1 a 0 dm\n"), DiagnosticCode.UNRESOLVED_MODEL).severity == "warning"


@pytest.mark.parametrize(
    ("element", "code"),
    [
        ("X1 a sub\n", DiagnosticCode.UNRESOLVED_SUBCKT),
        ("R1 a 0 {k}\n", DiagnosticCode.UNRESOLVED_PARAM),
    ],
    ids=["subckt", "param"],
)
def test_other_unresolved_names_follow(element: str, code: DiagnosticCode) -> None:
    for source in _opaque_sources():
        assert _found(_netlist(f"{element}{source}"), code).severity == "info", source


def test_a_block_counts_in_its_own_scope_and_inside_it() -> None:
    inner = "X1 a s\n.subckt s p\nD1 p 0 dm\n.ends\n"
    outer = _netlist(f"{inner}{_LIB}")
    assert _found(outer, DiagnosticCode.UNRESOLVED_MODEL).severity == "info"
    # A block inside the definition says nothing about the top level.
    body = ".subckt s p\n.lib x\n.endl\n.ends\nD1 a 0 dm\nX1 a s\n"
    assert _found(_netlist(body), DiagnosticCode.UNRESOLVED_MODEL).severity == "warning"


@pytest.mark.ngspice_only
def test_a_control_block_does_not_count() -> None:
    netlist = _netlist("D1 a 0 dm\n.control\nrun\n.endc\n")
    assert _found(netlist, DiagnosticCode.UNRESOLVED_MODEL).severity == "warning"


def test_set_model_accepts_a_name_from_an_opaque_source_when_told() -> None:
    for source in _opaque_sources():
        netlist = _netlist(f"D1 a 0 dm\n.model other D\n{source}")
        with pytest.raises(EditError, match="allow_external=True"):
            netlist.set_model("D1", "elsewhere")
        edited = netlist.set_model("D1", "elsewhere", allow_external=True)
        assert "D1 a 0 elsewhere" in edited.source.text


def test_set_model_refuses_a_name_with_no_opaque_source() -> None:
    netlist = _netlist("D1 a 0 dm\n.model dm D\n")
    with pytest.raises(EditError, match="is not defined"):
        netlist.set_model("D1", "elsewhere", allow_external=True)
