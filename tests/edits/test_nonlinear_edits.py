"""The table and polynomial edits (M15b T8, decision 0017 item 6).

Golden diffs are in ``tests/corpus/*/edits_golden`` (the ``nonlinear_*`` cases).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from netlistmod import Dialect, EditError, Netlist, TopologyViolation
from tests.support.dialects import current_dialect

_NGSPICE = (
    "t\nV1 in 0 2\nR1 in vx 1k\nR2 vx 0 2k\nVs vx vs 0\nR3 vs 0 1k\n"
    "E1 a 0 TABLE {v(vx)} = (0,0) (2,4)\nE2 b 0 vx 0 TABLE = (0 0 2 4)\n"
    "G1 0 c TABLE {v(vx)} = (0,0) (2,4m) m=2\n"
    "E3 d 0 FREQ {v(vx)}= DB (1, 6.02, 0) (1e9, 6.02, 0)\n"
    "E4 e 0 and(2) vx 0 vx 0 (0.5, 0) (0.9, 2)\nE5 f 0 POLY(1) vx 0 0 2\n"
    "F1 0 g POLY(2) Vs Vs 0 1 1 m=2\nH1 h 0 POLY(1) Vs 0 2k\nE6 i 0 vx 0 2\n"
    "Rl a 0 1k\nRm b 0 1k\nRn c 0 1k\nRo d 0 1k\nRp e 0 1k\nRq f 0 1k\nRr g 0 1k\nRs h 0 1k\n"
    "Rt i 0 1k\n.op\n.end\n"
)
_LTSPICE = (
    "t\nV1 in 0 2\nR1 in vx 1k\nR2 vx 0 2k\nVs vx vs 0\nR3 vs 0 1k\n"
    "E1 a 0 vx 0 table=(0, 0, 2, 4)\nG1 0 c vx 0 table=(0,0,2,4m)\n"
    "E3 d 0 vx 0 Laplace=2/(1+s/1k) window=1m\nE5 f 0 POLY(1) (vx,0) 0 2\n"
    "F1 0 g POLY(2) Vs Vs 0 1 1\nH1 h 0 POLY(1) Vs 0 2k\nE6 i 0 vx 0 2\n"
    "Rl a 0 1k\nRn c 0 1k\nRo d 0 1k\nRq f 0 1k\nRr g 0 1k\nRs h 0 1k\nRt i 0 1k\n.op\n.end\n"
)


def _netlist() -> Netlist:
    dialect = current_dialect()
    return Netlist.from_text(_NGSPICE if dialect is Dialect.NGSPICE else _LTSPICE, dialect=dialect)


def _line(netlist: Netlist, designator: str) -> str:
    return next(line for line in netlist.text.splitlines() if line.startswith(designator + " "))


@pytest.mark.ngspice_only
@pytest.mark.parametrize(
    ("designator", "points", "line"),
    [
        ("E1", [("0", "0"), ("2", "5")], "E1 a 0 TABLE {v(vx)} = (0,0) (2,5)"),
        ("E1", [("0", "0")], "E1 a 0 TABLE {v(vx)} = (0,0)"),
        ("E1", [("0", "0"), ("1", "2"), ("2", "4")], "E1 a 0 TABLE {v(vx)} = (0,0) (1,2) (2,4)"),
        ("E2", [("0", "0"), ("2", "5")], "E2 b 0 vx 0 TABLE = (0 0 2 5)"),
        ("E2", [("0", "0"), ("1", "2"), ("2", "4")], "E2 b 0 vx 0 TABLE = (0 0 1 2 2 4)"),
        ("G1", [("0", "0"), ("2", "5m")], "G1 0 c TABLE {v(vx)} = (0,0) (2,5m) m=2"),
        (
            "E3",
            [("1", "5", "0"), ("1e9", "5", "10")],
            "E3 d 0 FREQ {v(vx)}= DB (1, 5, 0) (1e9, 5, 10)",
        ),
        (
            "E3",
            [("1", "5", "0"), ("1e6", "5", "0"), ("1e9", "4", "0")],
            "E3 d 0 FREQ {v(vx)}= DB (1, 5, 0) (1e6, 5, 0) (1e9, 4, 0)",
        ),
        ("E4", [("0.4", "0"), ("0.8", "3")], "E4 e 0 and(2) vx 0 vx 0 (0.4, 0) (0.8, 3)"),
    ],
)
def test_set_table_on_ngspice(designator: str, points: list[tuple[str, ...]], line: str) -> None:
    assert _line(_netlist().set_table(designator, points), designator) == line


@pytest.mark.ltspice_only
@pytest.mark.parametrize(
    ("designator", "points", "line"),
    [
        ("E1", [("0", "0"), ("2", "5")], "E1 a 0 vx 0 table=(0, 0, 2, 5)"),
        ("E1", [("0", "0"), ("1", "2"), ("2", "4")], "E1 a 0 vx 0 table=(0, 0, 1, 2, 2, 4)"),
        ("G1", [("0", "0"), ("2", "{k}")], "G1 0 c vx 0 table=(0,0,2,{k})"),
    ],
)
def test_set_table_on_ltspice(designator: str, points: list[tuple[str, ...]], line: str) -> None:
    assert _line(_netlist().set_table(designator, points), designator) == line


@pytest.mark.parametrize(
    ("designator", "values", "ngspice", "ltspice"),
    [
        ("E5", ["0", "3"], "E5 f 0 POLY(1) vx 0 0 3", "E5 f 0 POLY(1) (vx,0) 0 3"),
        ("E5", ["0", "3", "4"], "E5 f 0 POLY(1) vx 0 0 3 4", "E5 f 0 POLY(1) (vx,0) 0 3 4"),
        ("E5", ["1", "2"], "E5 f 0 POLY(1) vx 0 1 2", "E5 f 0 POLY(1) (vx,0) 1 2"),
        ("F1", ["0", "2", "2"], "F1 0 g POLY(2) Vs Vs 0 2 2 m=2", "F1 0 g POLY(2) Vs Vs 0 2 2"),
        ("F1", ["5", "6"], "F1 0 g POLY(2) Vs Vs 5 6 m=2", "F1 0 g POLY(2) Vs Vs 5 6"),
        ("H1", ["0", "3k"], "H1 h 0 POLY(1) Vs 0 3k", "H1 h 0 POLY(1) Vs 0 3k"),
    ],
)
def test_set_poly_coefficients(
    designator: str, values: list[str], ngspice: str, ltspice: str
) -> None:
    expected = ngspice if current_dialect() is Dialect.NGSPICE else ltspice
    assert _line(_netlist().set_poly_coefficients(designator, values), designator) == expected


def test_set_poly_coefficients_keeps_the_separator_and_down_to_the_minimum() -> None:
    dialect = current_dialect()
    text = "t\nV1 a 0 1\nR1 a 0 1k\nR2 o 0 1k\nE1 o 0 POLY(1) a 0 0,2,3\n.end\n"
    netlist = Netlist.from_text(text, dialect=dialect) if dialect is Dialect.NGSPICE else None
    if netlist is None:
        text = text.replace("0,2,3", "0 2 3")
        netlist = Netlist.from_text(text, dialect=dialect)
    separator = "," if dialect is Dialect.NGSPICE else " "
    edited = netlist.set_poly_coefficients("E1", ["1", "2", "3", "4"])
    assert _line(edited, "E1").endswith(separator.join(["1", "2", "3", "4"]))
    with pytest.raises(EditError, match="at least"):
        netlist.set_poly_coefficients("E1", [] if dialect is Dialect.LTSPICE else ["1"])


@pytest.mark.parametrize(
    ("designator", "points", "message"),
    [
        ("E1", [("0", "0", "1")], "takes 2 values"),
        ("E3", [("0", "0")], "takes 3 values"),
        ("E4", [("0.4", "0")], "a gate takes exactly two points"),
        ("E4", [("0.4", "0"), ("0.8", "3"), ("1", "1")], "a gate takes exactly two points"),
        ("E1", [], "at least one point"),
        ("E1", [("0", "{k}")], "is not a number"),
        ("E1", [("0", "k")], "is not a number"),
        ("E3", [("1e9", "5", "0"), ("1e10", "5", "0")], "stops on a FREQ table"),
        ("E5", [("0", "0")], "has POLY coefficients, not a table"),
        ("E6", [("0", "0")], "is a voltage-controlled voltage source line and has no table"),
    ],
)
@pytest.mark.ngspice_only
def test_set_table_refusals_on_ngspice(
    designator: str, points: list[tuple[str, ...]], message: str
) -> None:
    with pytest.raises(EditError, match=message):
        _netlist().set_table(designator, points)


@pytest.mark.parametrize(
    ("designator", "points", "message"),
    [
        ("E1", [("0", "0")], "takes at least two points"),
        ("E1", [("0", "0", "1"), ("1", "1", "1")], "takes 2 values"),
        ("E3", [("0", "0")], "has no table"),
    ],
)
@pytest.mark.ltspice_only
def test_set_table_refusals_on_ltspice(
    designator: str, points: list[tuple[str, ...]], message: str
) -> None:
    with pytest.raises(EditError, match=message):
        _netlist().set_table(designator, points)


def test_set_poly_coefficients_refusals() -> None:
    netlist = _netlist()
    with pytest.raises(EditError, match="is not a POLY line"):
        netlist.set_poly_coefficients("E6", ["1", "2"])
    with pytest.raises(EditError, match="is not a POLY line"):
        netlist.set_poly_coefficients("E1", ["1", "2"])
    with pytest.raises(EditError, match="at least"):
        netlist.set_poly_coefficients("E5", [])


def test_a_comment_among_the_coefficients_blocks_a_change_of_count() -> None:
    dialect = current_dialect()
    text = "t\nV1 a 0 1\nR1 a 0 1k\nR2 o 0 1k\nE1 o 0 POLY(1) a 0 0 ; c\n+ 2 3\n.end\n"
    netlist = Netlist.from_text(text, dialect=dialect)
    with pytest.raises(EditError, match="comment among its coefficients"):
        netlist.set_poly_coefficients("E1", ["0", "1"])
    # The same count is replaced one value at a time and keeps the comment.
    kept = netlist.set_poly_coefficients("E1", ["0", "5", "6"])
    assert "; c" in kept.text and kept.text.endswith("+ 5 6\n.end\n")


@pytest.mark.ngspice_only
def test_set_expression_covers_table_and_freq_and_names_the_others() -> None:
    netlist = _netlist()
    assert "TABLE {2*v(vx)}" in netlist.set_expression("E1", "2*v(vx)").text
    assert "FREQ {2*v(vx)}=" in netlist.set_expression("E3", "2*v(vx)").text
    with pytest.raises(
        EditError, match="reads its control nodes and has no expression; use set_table"
    ):
        netlist.set_expression("E2", "1")
    with pytest.raises(EditError, match="use set_poly_coefficients"):
        netlist.set_expression("E5", "1")
    with pytest.raises(EditError, match="use set_table"):
        netlist.set_expression("E4", "1")


@pytest.mark.ngspice_only
@pytest.mark.parametrize(
    ("designator", "message"),
    [
        ("E1", "use set_expression for the expression and set_table for the points"),
        ("E2", "use set_table"),
        ("E5", "use set_poly_coefficients"),
        ("F1", "use set_poly_coefficients"),
    ],
)
def test_set_value_names_the_right_operation(designator: str, message: str) -> None:
    with pytest.raises(EditError, match=message):
        _netlist().set_value(designator, "3")


@pytest.mark.ltspice_only
def test_laplace_uses_set_expression_and_set_param() -> None:
    netlist = _netlist()
    assert _line(netlist.set_expression("E3", "3/(1+s/2k)"), "E3").startswith(
        "E3 d 0 vx 0 Laplace=3/(1+s/2k) window=1m"
    )
    assert _line(netlist.set_param("E3", "nfft", "1024"), "E3").endswith("window=1m nfft=1024")
    assert _line(netlist.set_param("E3", "window", "2m"), "E3").endswith("window=2m")
    with pytest.raises(EditError, match="takes no parameter `m`"):
        netlist.set_param("E3", "m", "2")
    with pytest.raises(
        EditError, match="takes no parameter `window`; only a line with `Laplace=` takes it"
    ):
        netlist.set_param("E1", "window", "2m")
    with pytest.raises(EditError, match="is written as laplace and has no gain"):
        netlist.set_value("E3", "2")


@pytest.mark.ngspice_only
def test_m_is_set_on_g_and_on_f_poly_and_nowhere_else() -> None:
    netlist = _netlist()
    assert _line(netlist.set_param("G1", "m", "3"), "G1").endswith("m=3")
    assert _line(netlist.set_param("F1", "m", "3"), "F1").endswith("m=3")
    with pytest.raises(EditError, match="only F and G take `m=`"):
        netlist.set_param("E1", "m", "3")


_EDITS: list[Callable[[Netlist], Netlist]] = [
    lambda n: n.set_poly_coefficients("E5", ["0", "3", "4"]),
    lambda n: n.set_poly_coefficients("F1", ["0", "2", "2"]),
    lambda n: n.set_poly_coefficients("H1", ["0", "9k"]),
    lambda n: n.set_table("E1", [("0", "0"), ("1", "1"), ("2", "5")]),
    lambda n: n.set_table("E1", [("0", "0"), ("2", "5")]),
    lambda n: n.set_table("G1", [("0", "0"), ("2", "5m")]),
]


@settings(max_examples=40, deadline=None)
@given(st.lists(st.sampled_from(_EDITS), min_size=1, max_size=5))
def test_no_table_or_poly_edit_changes_the_signature(
    steps: list[Callable[[Netlist], Netlist]],
) -> None:
    dialect = current_dialect()
    netlist = _netlist()
    baseline = netlist.signature()
    for step in steps:
        # Each edit applies on both dialects (E1 and G1 are a TABLE line on ngspice and a
        # `table=` line on LTspice), so a step that raises fails the property (A3-14).
        netlist = step(netlist)
        assert netlist.signature() == baseline, dialect


@pytest.mark.parametrize(
    "text",
    [
        "x",
        "1 2",
        "{",
        "0 0",
        "(0)",
        "a,b",
    ],
)
def test_text_that_would_change_the_topology_does_not_land(text: str) -> None:
    # A coefficient written as extra control nodes: the line re-reads with other fields, so the
    # edit is refused or the topology check stops it (nothing is written either way).
    netlist = _netlist()
    try:
        edited = netlist.set_poly_coefficients("E5", ["0", text])
    except (EditError, TopologyViolation):
        return
    assert edited.signature() == netlist.signature()


# --- the text of a rewrite (review R3) --------------------------------------------------------

_HEAD = "t\nV1 in 0 2\nR1 in vx 1k\nR2 vx 0 2k\nVs vx vs 0\nR3 vs 0 1k\nRl o 0 1k\n"


def _ngspice(lines: str) -> Netlist:
    return Netlist.from_text(_HEAD + lines + ".op\n.end\n", dialect=Dialect.NGSPICE)


def _lines(netlist: Netlist) -> list[str]:
    body = netlist.text.split("Rl o 0 1k\n", 1)[1]
    return body.splitlines()[:-2]


@pytest.mark.ngspice_only
@pytest.mark.parametrize(
    ("line", "points", "expected"),
    [
        (
            "E1 o 0 TABLE {v(vx)} = (0,0) (2,4)\n",
            [("0", "0"), ("1", "1"), ("2", "4")],
            ["E1 o 0 TABLE {v(vx)} = (0,0) (1,1) (2,4)"],
        ),
        (
            "E1 o 0 TABLE {v(vx)}=(0,0)(2,4)\n",
            [("0", "0"), ("1", "1"), ("2", "4")],
            ["E1 o 0 TABLE {v(vx)}=(0,0)(1,1)(2,4)"],
        ),
        (
            "E1 o 0 TABLE {v(vx)} = (0 , 0)   (2 , 4)\n",
            [("0", "0"), ("1", "1"), ("2", "4")],
            ["E1 o 0 TABLE {v(vx)} = (0 , 0)   (1 , 1)   (2 , 4)"],
        ),
        (
            "E1 o 0 TABLE {v(vx)} = (0 0 2 4)\n",
            [("0", "0"), ("1", "1"), ("2", "4")],
            ["E1 o 0 TABLE {v(vx)} = (0 0 1 1 2 4)"],
        ),
        (
            "E1 o 0 FREQ {v(vx)}= DB ( 1e7, 6.02, 0) (1e9, 6.02, 0)\n",
            [("1e7", "6", "0"), ("1e8", "5", "0"), ("1e9", "4", "0")],
            ["E1 o 0 FREQ {v(vx)}= DB ( 1e7, 6, 0) ( 1e8, 5, 0) ( 1e9, 4, 0)"],
        ),
        (
            "E1 o 0 FREQ {v(vx)}= DB\n+(1, 6.02, 0)\n+(1e9, 6.02, 0)\n",
            [("1", "6", "0"), ("1e6", "5", "0"), ("1e9", "4", "0")],
            [
                "E1 o 0 FREQ {v(vx)}= DB",
                "+(1, 6, 0)",
                "+(1e6, 5, 0)",
                "+(1e9, 4, 0)",
            ],
        ),
        (
            "E1 o 0 TABLE {v(vx)} = (0,0)\n+ (2,4)\n",
            [("0", "0"), ("1", "1"), ("2", "4")],
            ["E1 o 0 TABLE {v(vx)} = (0,0)", "+ (1,1)", "+ (2,4)"],
        ),
        (
            "E1 o 0 TABLE {v(vx)} =\n+ (0,0)\n+ (2,4)\n",
            [("0", "0"), ("2", "4")],
            ["E1 o 0 TABLE {v(vx)} =", "+ (0,0)", "+ (2,4)"],
        ),
    ],
)
def test_set_table_keeps_the_text_the_line_wrote(
    line: str, points: list[tuple[str, ...]], expected: list[str]
) -> None:
    edited = _ngspice(line).set_table("E1", points)
    assert _lines(edited) == expected


@pytest.mark.ngspice_only
def test_set_table_writes_each_point_on_a_line_of_its_own() -> None:
    netlist = _ngspice("E1 o 0 TABLE {v(vx)} =\n+ (0,0)\n+ (2,4)\n")
    edited = netlist.set_table("E1", [("0", "0"), ("1", "1"), ("2", "4"), ("3", "4")])
    assert _lines(edited) == ["E1 o 0 TABLE {v(vx)} =", "+ (0,0)", "+ (1,1)", "+ (2,4)", "+ (3,4)"]
    assert edited.signature() == netlist.signature()


@pytest.mark.ngspice_only
@pytest.mark.parametrize(
    ("line", "message"),
    [
        (
            "E1 o 0 TABLE {v(vx)} =\n+ (0,0) ; first\n+ (2,4) ; second\n",
            "has a comment among its points",
        ),
        ("E1 o 0 TABLE {v(vx)} = (0,0,\n+ 2,4)\n", "not each on a line of their own"),
        ("E1 o 0 TABLE {v(vx)} = (0,\n+ 0) (2,4)\n", "not each on a line of their own"),
    ],
)
def test_set_table_refuses_a_count_change_that_loses_a_comment_or_joins_lines(
    line: str, message: str
) -> None:
    netlist = _ngspice(line)
    with pytest.raises(EditError, match=message):
        netlist.set_table("E1", [("0", "0"), ("1", "1"), ("2", "4")])
    # The same number of points is always edited value for value, comments and lines kept.
    edited = netlist.set_table("E1", [("0", "0"), ("2", "5")])
    assert edited.text.count("\n") == netlist.text.count("\n")


@pytest.mark.ngspice_only
def test_set_table_refuses_a_first_frequency_that_ngspice_stops_on() -> None:
    netlist = _ngspice("E1 o 0 FREQ {v(vx)}= DB (1, 6.02, 0) (1e9, 6.02, 0)\n")
    with pytest.raises(EditError, match="follows its parenthesis directly"):
        netlist.set_table("E1", [("1e7", "6.02", "0"), ("1e9", "6.02", "0")])
    # A first frequency of one character, a later one of any length, and a blank all run.
    assert (
        "(3, 6.02, 0)" in netlist.set_table("E1", [("3", "6.02", "0"), ("1e9", "6.02", "0")]).text
    )
    blank = _ngspice("E1 o 0 FREQ {v(vx)}= DB ( 1e7Hz, 6.02, 0) (1e9Hz, 6.02, 0)\n")
    assert (
        "( 1e8Hz, 6.02, 0)"
        in blank.set_table("E1", [("1e8Hz", "6.02", "0"), ("1e9Hz", "6.02", "0")]).text
    )


@pytest.mark.ngspice_only
def test_set_poly_coefficients_refuses_a_count_change_over_a_continuation() -> None:
    netlist = _ngspice("E1 o 0 POLY(1) vx 0 0\n+ 2\n")
    with pytest.raises(EditError, match="continue on another line"):
        netlist.set_poly_coefficients("E1", ["0", "2", "3"])
    edited = netlist.set_poly_coefficients("E1", ["1", "3"])
    assert _lines(edited) == ["E1 o 0 POLY(1) vx 0 1", "+ 3"]


@pytest.mark.ltspice_only
def test_set_table_on_a_ltspice_table_over_a_continuation() -> None:
    head = "t\nV1 in 0 2\nR1 in vx 1k\nR2 vx 0 2k\nRl o 0 1k\n"
    netlist = Netlist.from_text(
        head + "E1 o 0 vx 0\n+ table=(0,0,2,4)\n.op\n.end\n", dialect=Dialect.LTSPICE
    )
    edited = netlist.set_table("E1", [("0", "0"), ("1", "1"), ("2", "4")])
    assert "+ table=(0,0,1,1,2,4)" in edited.text
    split = Netlist.from_text(
        head + "E1 o 0 vx 0 table=(0,0,\n+ 2,4)\n.op\n.end\n", dialect=Dialect.LTSPICE
    )
    with pytest.raises(EditError, match="not each on a line of their own"):
        split.set_table("E1", [("0", "0"), ("1", "1"), ("2", "4")])


@pytest.mark.ltspice_only
def test_set_param_laplace_on_b_refuses_a_reference() -> None:
    netlist = Netlist.from_text(
        "t\nV1 in 0 2\nR1 in vx 1k\nR2 vx 0 2k\nRl o 0 1k\n"
        "B1 o 0 V=2*V(vx) laplace=1/(1+s/1k)\n.op\n.end\n",
        dialect=Dialect.LTSPICE,
    )
    for formula in ("V(vx)/(1+s)", "I(V1)/(1+s)"):
        with pytest.raises(EditError, match="not allowed here"):
            netlist.set_param("B1", "laplace", formula)
