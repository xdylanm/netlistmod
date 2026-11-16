"""xyce names and net identity in the document layer (X-M1 B2; decision 0027 items 1 and 3;
``docs/grammars/xyce/names.md``)."""

from __future__ import annotations

import pytest

from netlistmod import DiagnosticCode, Dialect, Edit, EditPlan, Netlist, Span, TopologyViolation
from netlistmod.dialects import _XYCE
from netlistmod.document.names import fold, is_automatic_global, is_ground, net_name


def _netlist(text: str) -> Netlist:
    return Netlist.from_text(text, dialect=_XYCE)


def test_names_fold_by_ascii_case_only() -> None:
    # Xyce ignores case ([xyce-ug] §4.1.3 p41) in ASCII only: `Ä` and `ä` are two nodes (observed).
    assert fold("R1aB", _XYCE) == "r1ab"
    assert fold("Äb", _XYCE) == "Äb"
    assert fold("Äb", _XYCE) != fold("äb", _XYCE)


def test_only_zero_is_ground_without_replaceground() -> None:
    for name in ("gnd", "GND", "gnd!", "ground", "00"):
        assert not is_ground(name, _XYCE)
        assert net_name(name, _XYCE) == name.lower()
    assert is_ground("0", _XYCE)


@pytest.mark.parametrize("name", ["GND", "gnd", "Gnd!", "GND!", "ground", "Ground"])
def test_replaceground_makes_the_ground_synonyms_ground(name: str) -> None:
    # [xyce-ref] §2.1.28 p125: GND, GND! and GROUND in any case.
    assert is_ground(name, _XYCE, replace_ground=True)
    assert net_name(name, _XYCE, replace_ground=True) == "0"


@pytest.mark.parametrize("name", ["GROUND!", "gnd1", "00", "grnd", "vgnd"])
def test_other_names_stay_nets_under_replaceground(name: str) -> None:
    # GROUND! is not a synonym (xm1-tasks 5.1 point 5).
    assert not is_ground(name, _XYCE, replace_ground=True)


def test_the_other_dialects_keep_their_ground_rule() -> None:
    for dialect in (Dialect.NGSPICE, Dialect.LTSPICE):
        assert is_ground("gnd", dialect)
        assert not is_ground("gnd!", dialect)


@pytest.mark.parametrize("name", ["$G", "$GVDD", "$gvdd", "$g_x", "$G1"])
def test_a_dollar_g_node_is_global(name: str) -> None:
    # Decision X-D3: every node whose name begins `$G`, in any case ([xyce-ref] §2.3.1.1 p182).
    assert is_automatic_global(name, _XYCE)


@pytest.mark.parametrize("name", ["$VDD", "G$", "x$gvdd", "$"])
def test_other_dollar_names_are_not_global(name: str) -> None:
    assert not is_automatic_global(name, _XYCE)


def test_the_global_prefix_is_per_dialect() -> None:
    assert not is_automatic_global("$gvdd", Dialect.NGSPICE)
    assert not is_automatic_global("$gvdd", Dialect.LTSPICE)
    assert is_automatic_global("$g_vdd", Dialect.LTSPICE)


def test_replaceground_sets_the_netlist_wide_flag() -> None:
    plain = _netlist("t\n.global GND a\n.END\n")
    assert not plain.scope().replace_ground
    assert [net.name for net in plain.nets()] == ["gnd", "a"]
    replaced = _netlist("t\n.global GND a\n.preprocess replaceground true\n.END\n")
    assert replaced.scope().replace_ground
    nets = replaced.nets()
    assert [net.name for net in nets] == ["0", "a"]
    assert nets[0].spellings == ("GND",)
    assert nets[0].global_
    off = _netlist("t\n.global GND\n.preprocess replaceground false\n.END\n")
    assert not off.scope().replace_ground
    assert [net.name for net in off.nets()] == ["gnd"]


def test_a_dollar_g_net_is_global() -> None:
    netlist = _netlist("t\n.global $Gvdd\n.END\n")
    (net,) = netlist.nets()
    assert (net.name, net.scope, net.global_) == ("$gvdd", (), True)


def test_the_signature_records_replaceground() -> None:
    plain = _netlist("t\n.global a\n.END\n").signature()
    assert plain.entries == (("global", ("a",)),)
    on = _netlist("t\n.global a\n.preprocess replaceground TRUE\n.END\n").signature()
    off = _netlist("t\n.global a\n.preprocess replaceground FALSE\n.END\n").signature()
    assert on.entries[-1] == ("replaceground", ("TRUE",))
    assert off.entries[-1] == ("replaceground", ("FALSE",))
    assert len({plain.digest(), on.digest(), off.digest()}) == 3


def test_an_edit_cannot_change_replaceground() -> None:
    # The flag changes net identity, so it is topology (P4; decision 0027 item 3).
    netlist = _netlist("t\n.preprocess replaceground true\n.END\n")
    start = netlist.text.index("true")
    plan = EditPlan((Edit(Span(start, start + 4), "false", "flip the flag"),))
    with pytest.raises(TopologyViolation):
        netlist.apply(plan)


def test_an_indented_line_is_reported() -> None:
    text = "t\n  R1 a 0 1k\n* plain comment\n  * indented comment\n.END\n"
    netlist = _netlist(text)
    (diagnostic,) = netlist.diagnostics
    assert diagnostic.code is DiagnosticCode.INDENTED_LINE_IGNORED
    assert diagnostic.severity == "warning"
    assert (diagnostic.line, diagnostic.column) == (2, 1)
    assert diagnostic.span == Span(2, 13)
    assert "reads it as a comment" in diagnostic.message


def test_a_structure_only_netlist_has_no_diagnostics() -> None:
    netlist = _netlist("t\n* c\n; d\n\n.global a\n* e\n+ b ; f\n.END ; g\n")
    assert netlist.diagnostics == ()
    assert netlist.to_bytes() == "t\n* c\n; d\n\n.global a\n* e\n+ b ; f\n.END ; g\n".encode()
