"""Expression edits (M15 T8, decision 0016 item 7)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from netlistmod import Dialect, EditError, Netlist
from tests.support.dialects import current_dialect

_NGSPICE = (
    "t\nV1 a 0 1\nVs a b 0\nR1 b 0 1k\n"
    "B1 o 0 V = 2 * v(a) tc1=0\nB2 p 0 v={2*v(a)}\nE1 q 0 vol='2*v(a)'\n"
    "G1 0 r value {1m*v(a)} m=2\nC1 a 0 q='1n*v(a)'\nR2 a 0 R='1k*(1+v(a))'\n"
    "R3 o 0 1k\nR4 p 0 1k\nR5 q 0 1k\nR6 r 0 1k\nE2 s 0 a 0 2\nR7 s 0 1k\n.op\n.end\n"
)
_LTSPICE = (
    "t\nV1 a 0 1\nVs a b 0\nR1 b 0 1k\n"
    "B1 o 0 V=2*V(a) ic=0\nB2 p 0 V={2*V(a)}\nE1 q 0 value={2*V(a)}\n"
    "F1 0 r value={2*I(Vs)}\nC1 a 0 Q=1n*x\nL1 a n Flux=1m*tanh(5*x)\nR2 n 0 1k\n"
    "R3 o 0 1k\nR4 p 0 1k\nR5 q 0 1k\nR6 r 0 1k\nE2 s 0 a 0 2\nR7 s 0 1k\n.op\n.end\n"
)


def _netlist() -> Netlist:
    dialect = current_dialect()
    return Netlist.from_text(_NGSPICE if dialect is Dialect.NGSPICE else _LTSPICE, dialect=dialect)


def _line(netlist: Netlist, designator: str) -> str:
    return next(line for line in netlist.text.splitlines() if line.startswith(designator + " "))


@pytest.mark.ngspice_only
@pytest.mark.parametrize(
    ("designator", "line"),
    [
        ("B1", "B1 o 0 V = 3*v(a) tc1=0"),
        ("B2", "B2 p 0 v={3*v(a)}"),
        ("E1", "E1 q 0 vol='3*v(a)'"),
        ("G1", "G1 0 r value {3*v(a)} m=2"),
        ("C1", "C1 a 0 q='3*v(a)'"),
        ("R2", "R2 a 0 R='3*v(a)'"),
    ],
)
def test_set_expression_on_ngspice(designator: str, line: str) -> None:
    assert _line(_netlist().set_expression(designator, "3*v(a)"), designator) == line


@pytest.mark.ltspice_only
@pytest.mark.parametrize(
    ("designator", "line"),
    [
        ("B1", "B1 o 0 V=3*V(a) ic=0"),
        ("B2", "B2 p 0 V={3*V(a)}"),
        ("E1", "E1 q 0 value={3*V(a)}"),
        ("F1", "F1 0 r value={3*V(a)}"),
        ("C1", "C1 a 0 Q=3*V(a)"),
        ("L1", "L1 a n Flux=3*V(a)"),
    ],
)
def test_set_expression_on_ltspice(designator: str, line: str) -> None:
    assert _line(_netlist().set_expression(designator, "3*V(a)"), designator) == line


@pytest.mark.parametrize(
    ("designator", "message"),
    [
        ("E2", "has a gain, not an expression; use set_value"),
        ("R1", "its value is not a formula; use set_formula"),
        ("V1", "is a voltage source line and has no expression"),
    ],
)
def test_set_expression_refuses_lines_without_one(designator: str, message: str) -> None:
    with pytest.raises(EditError, match=message):
        _netlist().set_expression(designator, "1")


def test_set_value_on_an_expression_form_points_to_set_expression() -> None:
    with pytest.raises(EditError, match="is written as an expression .*use set_expression"):
        _netlist().set_value("E1", "3")


def test_a_bare_expression_that_does_not_land_is_refused() -> None:
    # A blank and a name= would end a bare expression, so the new text would not be one slot.
    with pytest.raises(EditError):
        _netlist().set_expression("B1", "2 * v(a) tc2=1")


def test_set_param_edits_the_trailing_parameters() -> None:
    netlist = _netlist()
    name = "tc1" if current_dialect() is Dialect.NGSPICE else "ic"
    assert _line(netlist.set_param("B1", name, "1"), "B1").endswith(f"{name}=1")


def test_a_second_expression_edit_in_a_batch_is_refused() -> None:
    netlist = _netlist()
    with pytest.raises(EditError, match="set_expression B1"):
        with netlist.batch() as batch:
            batch.set_expression("B1", "1")
            batch.set_expression("B1", "2")


_EDITS: list[Callable[[Netlist], Netlist]] = [
    lambda n: n.set_expression("B1", "4*v(a)"),
    lambda n: n.set_expression("B2", "v(b)+1"),
    lambda n: n.set_expression("E1", "v(a)*v(b)"),
    lambda n: n.set_expression("C1", "2n*v(a)"),
    lambda n: n.set_value("E2", "5"),
]


@settings(max_examples=40, deadline=None)
@given(st.lists(st.sampled_from(_EDITS), min_size=1, max_size=5))
def test_no_expression_edit_changes_the_signature(
    steps: list[Callable[[Netlist], Netlist]],
) -> None:
    # An expression may read other nets, which stay out of the signature (decision 0016 item 6).
    netlist = _netlist()
    signature = netlist.signature()
    for step in steps:
        edited = step(netlist)
        assert edited.signature() == signature
        assert step(edited).to_bytes() == edited.to_bytes()
        netlist = edited
