"""Transistor edits: where area goes, and what is refused (M13 T9, decision 0014)."""

from __future__ import annotations

import pytest

from netlistmod import Dialect, EditError, Netlist
from tests.support.dialects import current_dialect

_MODELS = ".model qn NPN\n.model qp PNP\n.model mn NMOS\n.model jn NJF\n.model zn NMF\n"


def _netlist(body: str) -> Netlist:
    return Netlist.from_text(f"t\n{body}\n{_MODELS}.end\n", dialect=current_dialect())


def _line(netlist: Netlist) -> str:
    return netlist.to_bytes().decode("utf-8").splitlines()[1]


def test_q_area_is_positional_only_in_ltspice() -> None:
    edited = _netlist("Q1 c b e qn off").set_param("Q1", "area", "2")
    if current_dialect() is Dialect.LTSPICE:
        assert _line(edited) == "Q1 c b e qn 2 off"
    else:
        assert _line(edited) == "Q1 c b e qn off area=2"


@pytest.mark.parametrize("letter", ["J", "Z"])
def test_j_and_z_area_is_positional(letter: str) -> None:
    model = f"{letter.lower()}n"
    assert _line(_netlist(f"{letter}1 d g s {model}").set_param(f"{letter}1", "area", "3")) == (
        f"{letter}1 d g s {model} 3"
    )
    replaced = _netlist(f"{letter}1 d g s {model} 2 off").set_param(f"{letter}1", "area", "3")
    assert _line(replaced) == f"{letter}1 d g s {model} 3 off"


@pytest.mark.ngspice_only
def test_a_written_area_assignment_is_edited_in_place() -> None:
    edited = _netlist("J1 d g s jn area=2").set_param("J1", "area", "4")
    assert _line(edited) == "J1 d g s jn area=4"


def test_set_model_keeps_the_nodes_and_checks_the_type() -> None:
    netlist = _netlist("Q1 c b e s qn")
    assert _line(netlist.set_model("Q1", "qp")) == "Q1 c b e s qp"
    with pytest.raises(EditError, match="takes a model of type `NPN`, `PNP`"):
        netlist.set_model("Q1", "mn")


def test_set_model_on_an_unread_model_needs_allow_external() -> None:
    netlist = Netlist.from_text(
        "t\nM1 d g s b nm\n.include jellybean.lib\n.end\n", dialect=current_dialect()
    )
    with pytest.raises(EditError, match="allow_external=True"):
        netlist.set_model("M1", "2N7000_OJ")
    edited = netlist.set_model("M1", "2N7000_OJ", allow_external=True)
    assert _line(edited) == "M1 d g s b 2N7000_OJ"


@pytest.mark.ltspice_only
def test_an_ltspice_mosfet_has_no_area() -> None:
    with pytest.raises(EditError, match="does not parse"):
        _netlist("M1 d g s b mn").set_param("M1", "area", "2")


def test_a_model_that_reads_as_a_name_cannot_be_written_as_a_number() -> None:
    with pytest.raises(EditError):
        _netlist("Q1 c b e qn").set_model("Q1", "2", allow_external=True)


@pytest.mark.parametrize(
    ("line", "kind"),
    [("Q1 c b e qn", "bipolar transistor"), ("Z1 d g s zn", "MESFET"), ("M1 d g s b mn", "MOSFET")],
)
def test_edit_errors_name_the_element_kind(line: str, kind: str) -> None:
    designator = line.split()[0]
    with pytest.raises(EditError, match=f"`{designator}` is a {kind} line and has no value slot"):
        _netlist(line).set_value(designator, "1")
