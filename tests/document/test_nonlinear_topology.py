"""The nonlinear forms' control fields are topology, and their expressions are reads (M15b T4, T7,
T8; decision 0017 items 2, 3 and 7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import (
    Cccs,
    Ccvs,
    CurrentSwitch,
    DiagnosticCode,
    Dialect,
    Edit,
    Netlist,
    Span,
    TopologyViolation,
)
from tests.support.dialects import ltspice_only, ngspice_only

C = DiagnosticCode
_NGSPICE = (
    "V1 in 0 2\nVs in a 0\nVt in b 0\nR1 a 0 1k\nR2 b 0 1k\nRo1 e1 0 1k\nRo2 e2 0 1k\n"
    "Ro3 e3 0 1k\nRo4 f1 0 1k\nRo5 h1 0 1k\nRo6 g1 0 1k\n"
    "E1 e1 0 POLY(1) a 0 0 2\nE2 e2 0 POLY(2) a 0 b 0 0 1 1\nE3 e3 0 a b TABLE = (0,0,2,4)\n"
    "F1 0 f1 POLY(2) Vs Vt 0 1 1\nH1 h1 0 POLY(1) Vs 0 2k\nG1 0 g1 POLY(1) a b 0 1m m=2"
)
_LTSPICE = (
    "V1 in 0 2\nVs in a 0\nVt in b 0\nR1 a 0 1k\nR2 b 0 1k\nRo1 e1 0 1k\nRo2 e2 0 1k\n"
    "Ro3 e3 0 1k\nRo4 f1 0 1k\nRo5 h1 0 1k\nRo6 g1 0 1k\n"
    "E1 e1 0 POLY(1) a 0 0 2\nE2 e2 0 POLY(2) (a,0) (b,0) 0 1 1\nE3 e3 0 a b table=(0,0,2,4)\n"
    "F1 f1 0 POLY(2) Vs Vt 0 1 1\nH1 h1 0 POLY(1) Vs 0 2k\nG1 0 g1 POLY(1) a b 0 1m"
)


def _netlist(body: str, dialect: Dialect) -> Netlist:
    return Netlist.from_text(f"title\n{body}\n.end\n", dialect=dialect)


def _circuit(dialect: Dialect) -> str:
    return _NGSPICE if dialect is Dialect.NGSPICE else _LTSPICE


@pytest.fixture(params=[Dialect.NGSPICE, Dialect.LTSPICE], ids=["ngspice", "ltspice"])
def dialect(request: pytest.FixtureRequest) -> Dialect:
    return request.param  # type: ignore[no-any-return]


def test_poly_control_nodes_are_in_nodes_nets_and_connections(dialect: Dialect) -> None:
    netlist = _netlist(_circuit(dialect), dialect)
    assert [c.node.name for c in netlist.connections("E2")] == ["e2", "0", "a", "0", "b", "0"]
    assert [e.designator for e in netlist.elements_on_net("b")][-3:] == ["E2", "E3", "G1"]
    entries = netlist.signature().entries
    assert ("element", (), "E2", "Vcvs", ("e2", "0", "a", "0", "b", "0")) in entries
    assert ("element", (), "E3", "Vcvs", ("e3", "0", "a", "b")) in entries
    assert netlist.diagnostics == ()


def test_poly_controlling_sources_are_control_entries_in_line_order(dialect: Dialect) -> None:
    netlist = _netlist(_circuit(dialect), dialect)
    assert [entry for entry in netlist.signature().entries if entry[0] == "control"] == [
        ("control", (), "F1", "Vs"),
        ("control", (), "F1", "Vt"),
        ("control", (), "H1", "Vs"),
    ]
    f1 = netlist.element("F1")
    assert isinstance(f1, Cccs) and [s.designator for s in f1.control] == ["Vs", "Vt"]
    h1 = netlist.element("H1")
    assert isinstance(h1, Ccvs) and [s.designator for s in h1.control] == ["Vs"]


def test_swapping_poly_sources_changes_the_signature(dialect: Dialect) -> None:
    body = _circuit(dialect)
    before = _netlist(body, dialect).signature()
    swapped = _netlist(body.replace("POLY(2) Vs Vt", "POLY(2) Vt Vs"), dialect).signature()
    assert before != swapped


@pytest.mark.parametrize(
    "old_new",
    [
        ("POLY(1) a 0 0 2", "POLY(1) b 0 0 2"),
        ("POLY(1) a 0 0 2", "POLY(1) a b 0 2"),
        ("POLY(2) Vs Vt", "POLY(2) Vs Vs"),
        ("POLY(1) Vs 0 2k", "POLY(1) Vt 0 2k"),
        ("a b TABLE = (0,0,2,4)", "a 0 TABLE = (0,0,2,4)"),
    ],
)
@ngspice_only
def test_changing_a_control_field_is_a_topology_violation_on_ngspice(
    old_new: tuple[str, str],
) -> None:
    netlist = _netlist(_NGSPICE, Dialect.NGSPICE)
    old, new = old_new
    start = netlist.text.index(old)
    with pytest.raises(TopologyViolation):
        netlist.apply([Edit(Span(start, start + len(old)), new)])


@pytest.mark.parametrize(
    "old_new",
    [
        ("POLY(1) a 0 0 2", "POLY(1) b 0 0 2"),
        ("POLY(2) (a,0) (b,0)", "POLY(2) (a,0) (a,0)"),
        ("POLY(2) Vs Vt", "POLY(2) Vt Vs"),
        ("a b table=(0,0,2,4)", "a 0 table=(0,0,2,4)"),
    ],
)
@ltspice_only
def test_changing_a_control_field_is_a_topology_violation_on_ltspice(
    old_new: tuple[str, str],
) -> None:
    netlist = _netlist(_LTSPICE, Dialect.LTSPICE)
    old, new = old_new
    start = netlist.text.index(old)
    with pytest.raises(TopologyViolation):
        netlist.apply([Edit(Span(start, start + len(old)), new)])


def test_changing_a_gate_input_is_a_topology_violation() -> None:
    body = "V1 a 0 1\nR1 a b 1k\nR2 b 0 1k\nR3 o 0 1k\nE1 o 0 and(2) a 0 b 0 (0.5, 0) (0.9, 2)"
    netlist = _netlist(body, Dialect.NGSPICE)
    start = netlist.text.index("and(2) a 0 b 0") + len("and(2) a 0 ")
    with pytest.raises(TopologyViolation):
        netlist.apply([Edit(Span(start, start + 1), "a")])


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("R1 a 0 1k\nF1 0 o POLY(1) Vnope 0 2", [(C.UNRESOLVED_ELEMENT, "warning", "Vnope")]),
        (
            "R1 a 0 1k\nF1 0 o POLY(1) Vnope 0 2\n.include s.lib",
            [(C.UNRESOLVED_ELEMENT, "info", "Vnope")],
        ),
        (
            "V1 a 0 1\nR1 a 0 1k\nF1 0 o POLY(2) V1 Vgone 0 1 1",
            [(C.UNRESOLVED_ELEMENT, "warning", "Vgone")],
        ),
        ("V1 a 0 1\nR1 a 0 1k\nR2 o 0 1k\nF1 0 o POLY(2) V1 R1 0 1 1", None),
        ("V1 a 0 1\nR1 a 0 1k\nR2 o 0 1k\nH1 o 0 POLY(1) V1 0 2k", []),
    ],
)
def test_poly_sources_are_resolved_and_diagnosed_as_a_linear_one_is(
    body: str, expected: list[tuple[DiagnosticCode, str, str]] | None
) -> None:
    netlist = _netlist(body, Dialect.NGSPICE)
    codes = [(d.code, d.severity, netlist.slice(d.span)) for d in netlist.diagnostics]
    if expected is None:
        assert [(code, text) for code, _, text in codes] == [(C.CONTROL_SOURCE_MISMATCH, "R1")]
    else:
        assert codes == expected


# --- the query --------------------------------------------------------------------------------


@ngspice_only
def test_table_and_freq_expressions_are_reads() -> None:
    netlist = _netlist(
        "V1 a 0 1\nR1 a b 1k\nR2 b 0 1k\nR3 o 0 1k\nR4 p 0 1k\n"
        "E1 o 0 TABLE {v(a) + v(b,0)} = (0,0) (2,4)\n"
        "E2 p 0 FREQ {2*v(b)}= DB (1, 6.02, 0) (1e9, 6.02, 0)",
        Dialect.NGSPICE,
    )
    assert [(r.kind, r.name) for r in netlist.expression_reads("E1")] == [
        ("node", "a"),
        ("node", "b"),
        ("node", "0"),
    ]
    assert [(r.kind, r.name) for r in netlist.expression_reads("E2")] == [("node", "b")]
    assert netlist.diagnostics == ()


def test_the_other_nonlinear_forms_read_only_their_control_nodes(dialect: Dialect) -> None:
    netlist = _netlist(_circuit(dialect), dialect)
    for designator in ("E1", "E2", "E3", "F1", "H1", "G1"):
        assert netlist.expression_reads(designator) == ()


@ltspice_only
def test_laplace_adds_no_reads_and_s_is_not_a_parameter() -> None:
    netlist = _netlist(
        "V1 a 0 1\nR1 a 0 1k\nR2 o 0 1k\nR3 p 0 1k\n.param K=2\n"
        "E1 o 0 a 0 Laplace=K/(1+s/1k) window=1m\n"
        "B1 p 0 V=V(a) laplace=K/(1+s*K)",
        Dialect.LTSPICE,
    )
    assert netlist.expression_reads("E1") == ()
    assert [(r.kind, r.name) for r in netlist.expression_reads("B1")] == [("node", "a")]
    assert netlist.diagnostics == ()
    unknown = _netlist("R1 a 0 1k\nE1 o 0 a 0 Laplace=1/(1+s*tau)\nR2 o 0 1k", Dialect.LTSPICE)
    assert [d.code for d in unknown.diagnostics] == [C.UNRESOLVED_PARAM]


@ltspice_only
def test_a_table_value_that_names_a_parameter_is_a_reference() -> None:
    netlist = _netlist("R1 a 0 1k\nE1 o 0 a 0 table=(0,0,2,{k})\nR2 o 0 1k", Dialect.LTSPICE)
    assert [(d.code, netlist.slice(d.span)) for d in netlist.diagnostics] == [
        (C.UNRESOLVED_PARAM, "k")
    ]


# --- `control` is a one-source tuple on every M14 corpus line ----------------------------------

_CORPUS = Path(__file__).parents[1] / "corpus"


@pytest.mark.parametrize(
    ("folder", "dialect"),
    [("ngspice", Dialect.NGSPICE), ("ltspice", Dialect.LTSPICE)],
)
def test_control_is_one_source_on_every_linear_f_h_and_w_line(
    folder: str, dialect: Dialect
) -> None:
    linear = 0
    for path in sorted((_CORPUS / folder / "controlled_sources").glob("*.cir")):
        netlist = Netlist.load(path, dialect=dialect)
        for line in netlist.lines.walk():
            item = line.item
            if not isinstance(item, Cccs | Ccvs | CurrentSwitch):
                continue
            if isinstance(item, CurrentSwitch) or item.form is None:
                assert len(item.control) == 1, path.name
                linear += 1
            elif item.form == "value":
                assert item.control == (), path.name  # LTspice's value= form
    assert linear > 0
