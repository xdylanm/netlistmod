"""Whole `.lib` blocks, and `directives.add` over a singleton (M11 T3, T4; decision 0012)."""

from __future__ import annotations

import pytest

from netlistmod import (
    AcDirective,
    DcDirective,
    Edit,
    EditError,
    Netlist,
    OpaqueBlock,
    OpaqueStatement,
    OpDirective,
    Span,
    TempDirective,
    TopologyViolation,
    TranDirective,
)
from tests.support.dialects import current_dialect

_BLOCK = ".lib x\nR9 out hidden 1k\n.model d D\n.endl\n"
_CIRCUIT = "V1 in 0 1\nR1 in out 1k\n"


def _netlist(body: str = "") -> Netlist:
    return Netlist.from_text(f"t\n{_CIRCUIT}{body}.end\n", dialect=current_dialect())


def _text(body: str = "") -> str:
    return f"t\n{_CIRCUIT}{body}.end\n"


def test_add_a_whole_block() -> None:
    edited = _netlist().directives.add(_BLOCK.splitlines())
    assert edited.source.text == _text(_BLOCK)
    assert edited.lines.find(OpaqueBlock) is not None
    assert edited.signature() == _netlist().signature()


def test_remove_a_whole_block() -> None:
    netlist = _netlist(_BLOCK)
    edited = netlist.directives.remove(netlist.lines.find_all(OpaqueBlock)[0])
    assert edited.source.text == _text()


def test_replace_a_whole_block() -> None:
    netlist = _netlist(_BLOCK)
    replacement = [".lib y", "R7 a b 1k", ".endl"]
    edited = netlist.directives.replace(netlist.lines.find_all(OpaqueBlock)[0], replacement)
    assert edited.source.text == _text(".lib y\nR7 a b 1k\n.endl\n")


def test_an_edit_elsewhere_leaves_a_block_unchanged() -> None:
    edited = _netlist(_BLOCK).set_value("R1", "2k")
    assert edited.source.text == _text(_BLOCK).replace("R1 in out 1k", "R1 in out 2k")


def test_the_body_cannot_be_addressed() -> None:
    with pytest.raises(EditError, match="R9"):
        _netlist(_BLOCK).set_value("R9", "2k")


def test_an_edit_cannot_cut_into_a_block() -> None:
    netlist = _netlist(_BLOCK)
    block = netlist.lines.find_all(OpaqueBlock)[0]
    inner = Span(block.span.start + 7, block.span.start + 9)
    with pytest.raises(TopologyViolation, match="opaque `.lib` item"):
        netlist.apply([Edit(inner, "R8")])


def test_adding_a_header_alone_stays_a_statement() -> None:
    edited = _netlist().directives.add(".lib x")
    assert edited.lines.find(OpaqueStatement) is not None


_KINDS = [
    (".op", OpDirective),
    (".tran 1u 1m", TranDirective),
    (".ac dec 1 1 10", AcDirective),
    (".dc V1 0 1 1", DcDirective),
    (".temp 75", TempDirective),
]


@pytest.mark.parametrize(("line", "kind"), _KINDS, ids=[line.split()[0] for line, _ in _KINDS])
class TestAddStaysLiteral:
    def test_add_writes_a_second_line(self, line: str, kind: type) -> None:
        netlist = _netlist(f"{line}\n")
        edited = netlist.directives.add(line)
        assert edited.source.text == _text(f"{line}\n{line}\n")
        assert len(edited.lines.find_all(kind)) == 2

    def test_set_refuses_the_ambiguity_it_leaves(self, line: str, kind: type) -> None:
        edited = _netlist(f"{line}\n").directives.add(line)
        with pytest.raises(EditError, match="ambiguous"):
            edited.directives.set(line)

    def test_replace_and_remove_work_on_it(self, line: str, kind: type) -> None:
        edited = _netlist(f"{line}\n").directives.add(line)
        first, second = edited.lines.find_all(kind)
        assert edited.directives.remove(first).source.text == _text(f"{line}\n")
        replaced = edited.directives.replace(second, ".options reltol=1e-4")
        assert replaced.source.text == _text(f"{line}\n.options reltol=1e-4\n")

    def test_a_batch_writes_what_it_is_given(self, line: str, kind: type) -> None:
        netlist = _netlist()
        with netlist.batch() as batch:
            batch.directives.add(line)
            batch.directives.add(line)
        assert len(batch.result.lines.find_all(kind)) == 2

    def test_set_is_still_the_upsert(self, line: str, kind: type) -> None:
        edited = _netlist(f"{line}\n").directives.set(line)
        assert edited.source.text == _text(f"{line}\n")
