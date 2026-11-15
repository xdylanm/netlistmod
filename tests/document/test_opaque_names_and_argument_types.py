"""H5 argument types and H8 names in opaque blocks (M11 T5, T8; decision 0012 item 5)."""

from __future__ import annotations

from collections.abc import Callable

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
        netlist.nets(scope="ab")


_SCOPE_READS = {
    "scope": lambda n, s: n.scope(s),
    "element": lambda n, s: n.element("R2", scope=s),
    "elements": lambda n, s: n.elements(scope=s),
    "references_to_param": lambda n, s: n.references_to_param("k", scope=s),
    "nets": lambda n, s: n.nets(scope=s),
    "net": lambda n, s: n.topology.net("r", scope=s),
    "elements_on_net": lambda n, s: n.elements_on_net("r", scope=s),
    "connections": lambda n, s: n.connections("R2", scope=s),
    "expression_reads": lambda n, s: n.expression_reads("R2", scope=s),
    "ports": lambda n, s: n.ports("ab", scope=s),
}


@pytest.mark.parametrize("read", list(_SCOPE_READS.values()), ids=list(_SCOPE_READS))
def test_a_scope_object_is_not_a_scope_path(read: Callable[[Netlist, object], object]) -> None:
    # M20 D2 (A1-14): the path is the argument; a Scope names `.path` in the TypeError.
    netlist = Netlist.from_text(_NESTED, dialect=current_dialect())
    scope = netlist.scope(("ab",))
    with pytest.raises(TypeError, match=r"not a Scope object: pass Scope\.path \(\('ab',\)\)"):
        read(netlist, scope)


def test_a_scope_is_read_only() -> None:
    # M20 D2 (A1-6): "Nothing is mutable" (document-layer.md section 1).
    netlist = Netlist.from_text(_NESTED, dialect=current_dialect())
    scope = netlist.scope(("a",))
    for name in (
        "path",
        "display",
        "definition",
        "lines",
        "parent",
        "children",
        "dialect",
        "params",
        "models",
        "subckts",
        "elements",
        "may_define_elsewhere",
    ):
        before = getattr(scope, name)
        with pytest.raises(AttributeError):
            setattr(scope, name, ("x",))
        assert getattr(scope, name) is before
    with pytest.raises(AttributeError):
        scope.extra = 1  # type: ignore[attr-defined]
    assert scope.path == ("a",)
    assert scope.dialect is current_dialect()
    assert netlist.scope(("a",)) is scope


@pytest.mark.parametrize("path", [("ab",), ["ab"]], ids=["tuple", "list"])
def test_a_sequence_is_a_scope(path: tuple[str, ...] | list[str]) -> None:
    netlist = Netlist.from_text(_NESTED, dialect=current_dialect())
    assert [net.name for net in netlist.nets(scope=path)] == ["r", "0"]


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


def test_may_define_elsewhere_marks_the_scope_of_an_opaque_source() -> None:
    # The documented Scope attribute (M20 D2, A1-7): an opaque source in the scope itself.
    for source in [*_opaque_sources(), '.include "m.inc"\n']:
        netlist = _netlist(f".subckt s p\nR1 p 0 1k\n.ends\n{source}")
        assert netlist.scope().may_define_elsewhere, source
        assert not netlist.scope(("s",)).may_define_elsewhere, source
    inside = _netlist(f".subckt s p\n{_LIB}.ends\n")
    assert not inside.scope().may_define_elsewhere
    assert inside.scope(("s",)).may_define_elsewhere


@pytest.mark.ngspice_only
def test_a_control_block_does_not_define_elsewhere() -> None:
    assert not _netlist(".control\nrun\n.endc\n").scope().may_define_elsewhere
