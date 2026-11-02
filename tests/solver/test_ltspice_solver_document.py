"""LTspice 26.1.1 probes for names, net identity and scoping (M8 T12, T8 tier; decision 0009).

Each probe pairs what LTspice does with what the library reports; together they validate
``docs/grammars/ltspice/names.md`` and ``scoping.md``. Two names are the same net when a source on
one drives a resistor on the other. Nothing LTspice writes is committed (decision 0009 item 2).
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from netlistmod import DiagnosticCode, Dialect, Netlist, ParseError
from tests.support.ltspice import Run, op_steps, run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ltspice")

LINEAR = 1e-6
NONLINEAR = 1e-3


def netlist(text: str) -> Netlist:
    return Netlist.from_text(text, dialect=Dialect.LTSPICE)


def codes(text: str) -> list[DiagnosticCode]:
    return [diagnostic.code for diagnostic in netlist(text).diagnostics]


def succeeds(solver: Solver, folder: Path, text: str) -> Run:
    result = run(solver, folder, text)
    assert result.ok, result.log
    return result


def same_net(solver: Solver, folder: Path, first: str, second: str) -> bool:
    """Whether LTspice reads the names as one net, and the library agrees."""
    text = f"probe\nV1 {first} 0 3\nR1 {second} x 1k\nR2 x 0 1k\n.op\n.end\n"
    result = succeeds(solver, folder, text)
    same = result.voltage("x") == pytest.approx(1.5, rel=LINEAR)
    assert (len(netlist(text).nets()) == 3) == same
    return bool(same)


# N1: Unicode case folding after NFC.


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("IN", "in"),
        ("ÄIN", "äin"),
        ("STRASSE", "straße"),
        (unicodedata.normalize("NFC", "Ä"), unicodedata.normalize("NFD", "Ä")),
    ],
)
def test_names_fold_by_unicode_case_folding_after_nfc(
    solver: Solver, tmp_path: Path, first: str, second: str
) -> None:
    assert same_net(solver, tmp_path, first, second)


def test_different_letters_are_different_nets(solver: Solver, tmp_path: Path) -> None:
    assert not same_net(solver, tmp_path, "ain", "äin")


# N2, N3: ground.


@pytest.mark.parametrize("name", ["GND", "gnd", "Gnd"])
def test_ground_aliases(solver: Solver, tmp_path: Path, name: str) -> None:
    text = f"probe\nV1 in 0 3\nR1 in out 1k\nR2 out {name} 1k\n.op\n.end\n"
    assert succeeds(solver, tmp_path, text).voltage("out") == pytest.approx(1.5, rel=LINEAR)
    assert sorted(net.name for net in netlist(text).nets()) == ["0", "in", "out"]


@pytest.mark.parametrize("name", ["00", "0.0", "+0"])
def test_a_name_like_zero_is_not_ground(solver: Solver, tmp_path: Path, name: str) -> None:
    text = f"probe\nV1 in 0 3\nR1 in out 1k\nR2 out {name} 1k\nR3 {name} 0 1k\n.op\n.end\n"
    assert succeeds(solver, tmp_path, text).voltage("out") == pytest.approx(2.0, rel=LINEAR)
    assert len(netlist(text).nets()) == 4


def test_numeric_names_are_strings(solver: Solver, tmp_path: Path) -> None:
    assert not same_net(solver, tmp_path, "1", "01")


# N4, N5, N6: designators, models, subcircuits, parameters and couplings fold alike.


@pytest.mark.parametrize(("first", "second"), [("R1", "r1"), ("RÄ", "rä"), ("RSS", "Rß")])
def test_a_repeated_designator_stops_ltspice(
    solver: Solver, tmp_path: Path, first: str, second: str
) -> None:
    text = f"probe\nV1 in 0 3\n{first} in 0 1k\n{second} in 0 1k\n.op\n.end\n"
    assert "already defined" in run(solver, tmp_path, text).log
    assert codes(text) == [DiagnosticCode.DUPLICATE_ELEMENT]


@pytest.mark.parametrize(
    "text",
    [
        "probe\nI1 0 a 1m\nD1 a 0 DM\n.model dm D\n.op\n.end\n",
        "probe\nI1 0 a 1m\nD1 a 0 dÄ\n.model DÄ D\n.op\n.end\n",
        "probe\nV1 a 0 1\nX1 a S\n.subckt s p\nR1 p 0 1k\n.ends\n.op\n.end\n",
        "probe\n.param RX=1k\nV1 a 0 1\nR1 a 0 {rx}\n.op\n.end\n",
        "probe\n.param RÄ=1k\nV1 a 0 1\nR1 a 0 {rä}\n.op\n.end\n",
    ],
)
def test_other_names_fold_alike(solver: Solver, tmp_path: Path, text: str) -> None:
    succeeds(solver, tmp_path, text)
    assert codes(text) == []


def test_coupling_references_fold_alike(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nV1 a 0 0 AC 1 Rser=1\nL1 a 0 1m\nL2 b 0 1m\nR1 b 0 1k\nK1 l1 l2 0.5\n"
        ".ac list 1k\n.end\n"
    )
    succeeds(solver, tmp_path, text)
    assert codes(text) == []


# N7, N8, N9, N10: local, port and global nets.

_LOCAL = "probe\nV1 in 0 3\nX1 in cell\nR9 n 0 1k\n.subckt cell a\nR1 a n 1k\nR2 n 0 1k\n.ends\n"


def test_a_net_in_a_definition_is_local(solver: Solver, tmp_path: Path) -> None:
    text = _LOCAL + ".op\n.end\n"
    result = succeeds(solver, tmp_path, text)
    # The current into the cell is that of two 1k in series; the top-level `n` carries none.
    plot = result.plot("Operating Point")
    assert abs(plot.real("Ix(x1:a)")[0]) == pytest.approx(1.5e-3, rel=LINEAR)
    assert result.voltage("n") == pytest.approx(0, abs=1e-6)
    assert {net.name for net in netlist(text).nets()} == {"in", "0", "n"}
    assert {net.name for net in netlist(text).nets(("cell",))} >= {"a", "n", "0"}


def test_ports_bind_by_position(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nV1 in 0 3\nX1 in out cell\nX2 out 0 cell\n.subckt cell q p\nR1 q p 1k\n.ends\n"
        ".op\n.end\n"
    )
    assert succeeds(solver, tmp_path, text).voltage("out") == pytest.approx(1.5, rel=LINEAR)


@pytest.mark.parametrize(
    ("declaration", "node"), [(".global vcc\n", "vcc"), ("", "$G_vcc"), ("", "$g_VCC")]
)
def test_global_nodes_join_every_scope(
    solver: Solver, tmp_path: Path, declaration: str, node: str
) -> None:
    text = (
        f"probe\n{declaration}V1 {node} 0 3\nX1 out s\nR2 out 0 1k\n"
        f".subckt s b\nR1 {node} b 1k\n.ends\n.op\n.end\n"
    )
    assert succeeds(solver, tmp_path, text).voltage("out") == pytest.approx(1.5, rel=LINEAR)
    assert any(net.name.lower().endswith("vcc") for net in netlist(text).nets(("s",)))


def test_bus_names_are_nets(solver: Solver, tmp_path: Path) -> None:
    assert same_net(solver, tmp_path, "d[0]", "D[0]")
    assert not same_net(solver, tmp_path, "d[0]", "d[1]")


# N11: a node name that reaches into an instance. V(b) is 3 V when R9 carries no current, 2.625 V
# when it is joined to n inside the instance, and 2.25 V when joined to the port q (on c).

_BASE = "probe\nV1 a 0 3\nR1 a b 1k\nR2 c 0 1k\n"
_CELL_S = ".subckt s p q\nR5 p n 1k\nR6 n q 1k\n.ends\n"
_OUTER = ".subckt o u v\n{}\n.ends\n"


def _reach(call: str, node: str, definitions: str = _CELL_S) -> str:
    return f"{_BASE}{call}\nR9 {node} b 1k\n{definitions}.op\n.end\n"


def _into_instance(text: str) -> list[tuple[str, str]]:
    return [
        (d.code, d.severity)
        for d in netlist(text).diagnostics
        if d.code is DiagnosticCode.NODE_INTO_INSTANCE
    ]


TWO_LEVELS = _OUTER.format("X2 u v s") + _CELL_S
BLOCK_LEVEL = _OUTER.format("X§U2 u v s") + _CELL_S


@pytest.mark.parametrize(
    ("call", "node", "definitions", "out"),
    [
        ("X1 a c s", "x1:n", _CELL_S, 2.625),
        ("X1 a c s", "X1:N", _CELL_S, 2.625),
        ("X1 a c s", "x1:q", _CELL_S, 2.25),
        ("X§U1 a c s", "U1:n", _CELL_S, 2.625),
        ("XY§U1 a c s", "xy§u1:n", _CELL_S, 2.625),
        ("Xq1 a c s", "xq1:n", _CELL_S, 2.625),
        ("X1 a c o", "x1:x2:n", TWO_LEVELS, 2.625),
        ("X1 a c o", "x1:x2:q", TWO_LEVELS, 2.25),
        ("X1 a c o", "x1:u2:n", BLOCK_LEVEL, 2.625),
    ],
)
def test_a_node_into_an_instance_is_joined_and_flagged(
    solver: Solver, tmp_path: Path, call: str, node: str, definitions: str, out: float
) -> None:
    text = _reach(call, node, definitions)
    assert succeeds(solver, tmp_path, text).voltage("b") == pytest.approx(out, rel=LINEAR)
    assert _into_instance(text) == [(DiagnosticCode.NODE_INTO_INSTANCE, "warning")]
    assert node.casefold() in {net.name for net in netlist(text).nets()}


@pytest.mark.parametrize(
    ("call", "node", "definitions"),
    [
        ("X1 a c s", "x1:zz", _CELL_S),
        ("X1 a c s", "x7:n", _CELL_S),
        ("X1 a c s", "x1.n", _CELL_S),
        ("X1 a c s", "a:b", _CELL_S),
        ("X1 a c s", "r1:n", _CELL_S),
        ("X§U1 a c s", "xu1:n", _CELL_S),
        ("X§U1 a c s", "x§u1:n", _CELL_S),
        ("Xq1 a c s", "q1:n", _CELL_S),
        ("XY§U1 a c s", "U1:n", _CELL_S),
        ("Xa:b a c s", "xa:b:n", _CELL_S),
        ("X1 a c o", "x1:x2:zz", TWO_LEVELS),
        ("X1 a c o", "x1:x9:n", TWO_LEVELS),
        ("X1 a c o", "x1:xu2:n", BLOCK_LEVEL),
    ],
)
def test_other_names_with_a_colon_are_ordinary_nodes(
    solver: Solver, tmp_path: Path, call: str, node: str, definitions: str
) -> None:
    text = _reach(call, node, definitions)
    assert succeeds(solver, tmp_path, text).voltage("b") == pytest.approx(3.0, rel=LINEAR)
    assert _into_instance(text) == []


def test_a_node_in_a_body_reaches_an_instance_of_that_body(solver: Solver, tmp_path: Path) -> None:
    inner = "X1 a c b o\n.subckt o u v w\nX2 u v s\nR9 {} w 1k\n.ends\n" + _CELL_S
    joined = f"{_BASE}{inner.format('x2:n')}.op\n.end\n"
    assert succeeds(solver, tmp_path / "joined", joined).voltage("b") == pytest.approx(2.625)
    assert _into_instance(joined) == [(DiagnosticCode.NODE_INTO_INSTANCE, "warning")]
    missing = f"{_BASE}{inner.format('x2:zz')}.op\n.end\n"
    assert succeeds(solver, tmp_path / "zz", missing).voltage("b") == pytest.approx(3.0)
    assert _into_instance(missing) == []


def test_a_body_does_not_reach_an_instance_of_the_top_level(solver: Solver, tmp_path: Path) -> None:
    text = f"{_BASE}X1 a c s\nX3 b o\n.subckt o w\nR9 x1:n w 1k\n.ends\n{_CELL_S}.op\n.end\n"
    assert succeeds(solver, tmp_path, text).voltage("b") == pytest.approx(3.0)
    assert _into_instance(text) == []


def test_other_element_nodes_reach_in_too(solver: Solver, tmp_path: Path) -> None:
    source = f"{_BASE}X1 a c s\nV9 x1:n b 0\n{_CELL_S}.op\n.end\n"
    assert succeeds(solver, tmp_path / "v", source).voltage("b") == pytest.approx(2.4)
    assert len(_into_instance(source)) == 1
    block = ".subckt r u v\nR1 u v 1k\n.ends\n"
    call = f"{_BASE}X1 a c s\nX3 x1:n b r\n{block}{_CELL_S}.op\n.end\n"
    assert succeeds(solver, tmp_path / "x", call).voltage("b") == pytest.approx(2.625)
    assert len(_into_instance(call)) == 1


@pytest.mark.parametrize(
    ("declaration", "node"),
    [("", "x1:0"), ("", "x1:gnd"), ("", "x1:$G_x"), (".global vcc\n", "x1:vcc")],
)
def test_a_global_node_in_an_instance_stops_ltspice_and_is_flagged(
    solver: Solver, tmp_path: Path, declaration: str, node: str
) -> None:
    text = _reach(f"{declaration}X1 a c s", node)
    assert "Ill-formed node name" in run(solver, tmp_path, text).log
    assert _into_instance(text) == [(DiagnosticCode.NODE_INTO_INSTANCE, "warning")]


def test_a_definition_in_an_include_is_reached_and_is_info(solver: Solver, tmp_path: Path) -> None:
    (tmp_path / "h.inc").write_bytes(_CELL_S.encode())
    text = f"{_BASE}X1 a c s\nR9 x1:n b 1k\n.include h.inc\n.op\n.end\n"
    assert succeeds(solver, tmp_path, text).voltage("b") == pytest.approx(2.625)
    assert _into_instance(text) == [(DiagnosticCode.NODE_INTO_INSTANCE, "info")]


def test_a_save_vector_reads_the_node_in_the_instance_and_is_no_net(
    solver: Solver, tmp_path: Path
) -> None:
    text = f"{_BASE}R8 b 0 1k\nX1 a c s\n.save V(x1:n) V(b)\n{_CELL_S}.op\n.end\n"
    assert "V(x1:n)" in succeeds(solver, tmp_path, text).plot("Operating Point").variables
    assert netlist(text).diagnostics == ()


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (f"{_BASE}X1 a c s\n.global x1:n\nR9 x1:n b 1k\n{_CELL_S}.op\n.end\n", "syntax error"),
        (f"{_BASE}.subckt y x1:n\nR9 x1:n 0 1k\n.ends\n.op\n.end\n", "Expected end of line"),
    ],
)
def test_a_colon_in_a_global_or_a_port_stops_ltspice_only(
    solver: Solver, tmp_path: Path, text: str, message: str
) -> None:
    assert message in run(solver, tmp_path, text).log
    netlist(text)


# S1, S2: parameters.

_PARAM = (
    "probe\nV1 in 0 3\nX1 in out s{call}\n{top}.subckt s a b{default}\n{body}"
    "R1 a b 1k\nR2 b 0 {{r}}\n.ends\n.op\n.end\n"
)


@pytest.mark.parametrize(
    ("top", "default", "body", "call", "out"),
    [
        (".param r=3k\n", "", "", "", 2.25),  # S1: a global is seen in a body
        (".param r=3k\n", " r=1k", "", "", 1.5),  # S2: a default masks it
        (".param r=3k\n", "", ".param r=1k\n", "", 1.5),  # S2: a body line masks it
        (".param r=7k\n", " r=1k", "", " r=3k", 2.25),  # the instance overrides the default
    ],
)
def test_scopes_mask_as_in_the_rule_table(
    solver: Solver, tmp_path: Path, top: str, default: str, body: str, call: str, out: float
) -> None:
    text = _PARAM.format(top=top, default=default, body=body, call=call)
    assert succeeds(solver, tmp_path, text).voltage("out") == pytest.approx(out, rel=LINEAR)
    assert DiagnosticCode.UNRESOLVED_PARAM not in codes(text)


def test_a_local_parameter_is_not_seen_at_the_top(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nV1 in 0 3\nX1 in 0 s\nR9 in 0 {r}\n.subckt s a b\n.param r=1k\nR1 a b {r}\n.ends\n"
        ".op\n.end\n"
    )
    assert run(solver, tmp_path, text).returncode != 0
    assert codes(text) == [DiagnosticCode.UNRESOLVED_PARAM]


# S3, S4: models and subcircuits.


def test_a_model_is_local_to_its_definition(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nI1 0 a 1m\nD1 a 0 dm\nX1 a s\n.subckt s p\n.model dm D\nD2 p 0 dm\n.ends\n"
        ".op\n.end\n"
    )
    assert run(solver, tmp_path, text).returncode != 0
    assert codes(text) == [DiagnosticCode.UNRESOLVED_MODEL]


def test_a_subcircuit_is_local_to_its_definition(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nV1 a 0 1\nX1 a inner\nX2 a outer\n.subckt outer p\n.subckt inner q\nR1 q 0 1k\n"
        ".ends\nX3 p inner\n.ends\n.op\n.end\n"
    )
    assert run(solver, tmp_path, text).returncode != 0
    assert codes(text) == [DiagnosticCode.UNRESOLVED_SUBCKT]


def test_a_nested_definition_sees_its_enclosing_scopes(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nI1 0 a 1m\nX1 a outer\n.subckt outer p\nX2 p inner\n.subckt inner q\nD1 q 0 dm\n"
        ".ends\n.model dm D\n.ends\n.op\n.end\n"
    )
    assert succeeds(solver, tmp_path, text).plot("Operating Point").rows
    assert codes(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "probe\n.model dm D\nI1 0 a 1m\nD1 a 0 dm\n.op\n.end\n",
        "probe\nI1 0 a 1m\nD1 a 0 dm\n.model dm D\n.op\n.end\n",
        "probe\n.subckt s p\nR1 p 0 1k\n.ends\nV1 a 0 1\nX1 a s\n.op\n.end\n",
    ],
)
def test_lookup_is_independent_of_file_order(solver: Solver, tmp_path: Path, text: str) -> None:
    succeeds(solver, tmp_path, text)
    assert codes(text) == []


# S5: a parameter used before its line.


def test_use_before_definition_is_not_diagnosed(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nV1 in 0 3\nR1 in out 1k\nR2 out 0 {x}\n.param x=3k\n.op\n.end\n"
    assert succeeds(solver, tmp_path, text).voltage("out") == pytest.approx(2.25, rel=LINEAR)
    assert codes(text) == []


def test_a_parameter_refers_to_a_later_one(solver: Solver, tmp_path: Path) -> None:
    text = "probe\n.param y=x\n.param x=3k\nV1 in 0 3\nR1 in out 1k\nR2 out 0 {y}\n.op\n.end\n"
    assert succeeds(solver, tmp_path, text).voltage("out") == pytest.approx(2.25, rel=LINEAR)
    assert codes(text) == []


# S6, S7: repeated definitions.


def _one_duplicate(text: str) -> None:
    diagnostics = netlist(text).diagnostics
    assert [d.code for d in diagnostics] == [DiagnosticCode.DUPLICATE_DEFINITION]
    assert diagnostics[0].severity == "warning"


@pytest.mark.parametrize("body", [".param x=1\n.param x=2\n", ".param x=1 x=2\n"])
def test_a_repeated_param_stops_ltspice(solver: Solver, tmp_path: Path, body: str) -> None:
    text = f"probe\nV1 a 0 1\nR1 a 0 1k\n{body}.op\n.end\n"
    assert not run(solver, tmp_path, text).ok
    _one_duplicate(text)


_S1 = ".subckt s p q\nR1 p q 1k\n.ends\n"
_S2 = ".subckt s p q\nR1 p q 3k\n.ends\n"
_MODEL_USE = "probe\nI1 0 a 1m\nD1 a 0 dm\n{}.op\n.end\n"
_SUBCKT_USE = "probe\nV1 a 0 1\nX1 a b s\nR1 b 0 1k\n{}.op\n.end\n"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (_MODEL_USE.format(".model dm D(Is=1n)\n.model dm D(Is=2n)\n"), "multiple definitions"),
        (_SUBCKT_USE.format(_S1 + _S2), "more than one sub-circuit"),
        (_SUBCKT_USE.format(_S1 + _S1), "more than one sub-circuit"),
    ],
)
def test_a_repeated_definition_that_is_used_stops_ltspice(
    solver: Solver, tmp_path: Path, text: str, message: str
) -> None:
    result = run(solver, tmp_path, text)
    assert result.returncode != 0 and message in result.log, result.log
    _one_duplicate(text)


@pytest.mark.parametrize(
    "text",
    [
        "probe\nV1 a 0 1\nR1 a 0 1k\n.model dm D\n.model dm D(Is=1n)\n.op\n.end\n",
        f"probe\nV1 a 0 1\nR1 a 0 1k\n{_S1}{_S2}.op\n.end\n",
        _MODEL_USE.format(".model dm D\n.model dm D\n"),
    ],
)
def test_other_repeated_definitions_run_and_are_diagnosed(
    solver: Solver, tmp_path: Path, text: str
) -> None:
    assert run(solver, tmp_path, text).returncode == 0
    _one_duplicate(text)


# S8: an unknown name on an X line.


def test_an_unknown_x_parameter_is_ignored_and_not_diagnosed(
    solver: Solver, tmp_path: Path
) -> None:
    text = (
        "probe\nV1 in 0 3\nX1 in out s nosuch=5\n.subckt s a b\nR1 a b 1k\nR2 b 0 1k\n.ends\n"
        ".op\n.end\n"
    )
    assert succeeds(solver, tmp_path, text).voltage("out") == pytest.approx(1.5, rel=LINEAR)
    assert codes(text) == []


# S9: names of elements.

_CELL = ".subckt cell a\nL1 a b 1m\nR8 b 0 1k\nV9 a c 0\nR9 c 0 1k\n.ends\n"


@pytest.mark.parametrize(
    "lines",
    [
        "V1 in 0 0 AC 1 Rser=1\nX1 in cell\nL2 s 0 1m\nR2 s 0 1k\nK1 L1 L2 0.5\n.ac list 1k\n",
        "V1 in 0 1 Rser=1\nX1 in cell\n.dc V9 0 1 1\n",
    ],
)
def test_top_level_references_do_not_reach_into_an_instance(
    solver: Solver, tmp_path: Path, lines: str
) -> None:
    text = f"probe\n{lines}{_CELL}.end\n"
    assert not run(solver, tmp_path, text).ok
    assert codes(text) == [DiagnosticCode.UNRESOLVED_ELEMENT]


@pytest.mark.parametrize("pattern", ["I(R?)", "I(x1:R8)", "I(*)"])
def test_a_save_pattern_refers_to_no_single_element(
    solver: Solver, tmp_path: Path, pattern: str
) -> None:
    text = f"probe\nV1 in 0 1 Rser=1\nX1 in cell\nR1 in 0 1k\n{_CELL}.save {pattern}\n.op\n.end\n"
    assert run(solver, tmp_path, text).returncode == 0
    assert codes(text) == []


def test_temp_is_not_a_reference(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nV1 in 0 1\nR1 in 0 1k\n.dc temp 0 10 10\n.end\n"
    assert succeeds(solver, tmp_path, text).plot("DC").rows
    assert codes(text) == []


# S10: the port count.


def test_a_port_count_mismatch_stops_ltspice(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nV1 a 0 1\nX1 a b s\n.subckt s p\nR1 p 0 1k\n.ends\n.op\n.end\n"
    assert run(solver, tmp_path, text).returncode != 0
    assert codes(text) == [DiagnosticCode.SUBCKT_PORT_MISMATCH]


# S11: words in a formula. R1 carries 1 A, so V(a) is how LTspice reads its value.

_ONE_AMP = "probe\nI1 0 a 1\n{}\n{}\n.end\n"
_FUNCTIONS = (
    "abs acos asin atan atan2 cos sin tan cosh sinh tanh exp ln log10 sqrt cbrt pow pwr pwrs int "
    "floor ceil round buf inv u uramp sgn if limit min max hypot rand flat gauss mc mod select "
    "table xor"
).split()
_CONSTANTS = [
    ("pi", 3.14159265358979),
    ("boltz", 1.3806503e-23),
    ("echarge", 1.602176462e-19),
    ("planck", 6.6262e-34),
    ("kelvin", -273.15),
    ("gmin", 1e-12),
]


def _reads(solver: Solver, folder: Path, lines: str, analysis: str = ".op") -> float:
    return succeeds(solver, folder, _ONE_AMP.format(lines, analysis)).voltage("a")


@pytest.mark.parametrize(("word", "value"), [*_CONSTANTS, ("temp", 27.0)])
def test_a_word_with_a_built_in_value_is_not_a_reference(
    solver: Solver, tmp_path: Path, word: str, value: float
) -> None:
    lines = f"R1 a 0 {{{word}}}"
    assert _reads(solver, tmp_path, lines) == pytest.approx(value, rel=LINEAR)
    text = _ONE_AMP.format(lines, ".op")
    assert netlist(text).references == () and codes(text) == []


@pytest.mark.parametrize(("word", "value"), _CONSTANTS)
def test_a_param_masks_a_constant_in_its_scope(
    solver: Solver, tmp_path: Path, word: str, value: float
) -> None:
    lines = f".param {word}=3k\nR1 a 0 {{{word}}}"
    assert _reads(solver, tmp_path / "top", lines) == pytest.approx(3e3, rel=LINEAR)
    text = _ONE_AMP.format(lines, ".op")
    assert len(netlist(text).references_to_param(word)) == 1 and codes(text) == []
    # A definition in a body masks it there only, so the top level still reads the constant.
    body = f"X1 b s\nR9 b 0 1\n.subckt s p\n.param {word}=3k\nR2 p 0 1\n.ends\nR1 a 0 {{{word}}}"
    assert _reads(solver, tmp_path / "body", body) == pytest.approx(value, rel=LINEAR)
    assert netlist(_ONE_AMP.format(body, ".op")).references_to_param(word) == ()


def test_a_mask_ignores_line_order_and_case(solver: Solver, tmp_path: Path) -> None:
    lines = "R1 a 0 {pi}\n.param PI=3k"
    assert _reads(solver, tmp_path, lines) == pytest.approx(3e3, rel=LINEAR)
    assert len(netlist(_ONE_AMP.format(lines, ".op")).references_to_param("pi")) == 1


def test_a_second_param_of_a_constant_stops_like_any_other(solver: Solver, tmp_path: Path) -> None:
    # The constant is in a scope outside the top level: one line masks it, two are a repeat (S6).
    text = _ONE_AMP.format(".param pi=1k\n.param pi=3k\nR1 a 0 {pi}", ".op")
    assert "already defined" in run(solver, tmp_path, text).log
    assert codes(text) == [DiagnosticCode.DUPLICATE_DEFINITION]


def test_a_step_masks_a_constant(solver: Solver, tmp_path: Path) -> None:
    text = _ONE_AMP.format("R1 a 0 {pi}", ".step param pi list 1 2\n.op")
    assert succeeds(solver, tmp_path, text).plot("Operating Point").real("V(a)") == (1.0, 2.0)
    assert len(netlist(text).references_to_param("pi")) == 1


@pytest.mark.parametrize("word", [*_FUNCTIONS, "time", "freq"])
def test_other_bare_words_are_ordinary_names(solver: Solver, tmp_path: Path, word: str) -> None:
    alone = _ONE_AMP.format(f"R1 a 0 {{{word}}}", ".op")
    assert "No such parameter defined" in run(solver, tmp_path / "alone", alone).log
    assert codes(alone) == [DiagnosticCode.UNRESOLVED_PARAM]
    lines = f".param {word}=3k\nR1 a 0 {{{word}}}"
    assert _reads(solver, tmp_path / "defined", lines) == pytest.approx(3e3, rel=LINEAR)
    defined = _ONE_AMP.format(lines, ".op")
    assert len(netlist(defined).references_to_param(word)) == 1 and codes(defined) == []


@pytest.mark.parametrize(
    ("lines", "analysis"),
    [
        ("R1 a 0 {time+1}", ".tran 1m"),
        ("R1 a 0 {freq+1}", ".ac list 1k"),
        ("R1 a 0 {freq+1}", ".tran 1m"),
        ("R1 a 0 1k m={time+1}", ".tran 1m"),
        (".param y=time+1\nR1 a 0 {y}", ".tran 1m"),
        ("R1 a 0 1k\nC1 a 0 {time+1}", ".tran 1m"),
    ],
)
def test_time_and_freq_have_no_value_in_these_slots_during_an_analysis(
    solver: Solver, tmp_path: Path, lines: str, analysis: str
) -> None:
    text = _ONE_AMP.format(lines, analysis)
    assert "No such parameter defined" in run(solver, tmp_path, text).log
    assert DiagnosticCode.UNRESOLVED_PARAM in codes(text)


def test_a_param_named_time_is_read_in_braces_and_not_in_a_keyword_value(
    solver: Solver, tmp_path: Path
) -> None:
    braces = ".param time=3k\nR1 a 0 {time}"
    rows = succeeds(solver, tmp_path / "braces", _ONE_AMP.format(braces, ".tran 1m uic"))
    assert rows.plot("Transient").real("V(a)")[-1] == pytest.approx(3e3, rel=LINEAR)
    # The `R=` form, which the library rejects, reads the simulation time instead.
    keyword = _ONE_AMP.format(".param time=3k\nR1 a 0 R={time}", ".tran 1m uic")
    result = run(solver, tmp_path / "keyword", keyword)
    assert result.plot("Transient").real("V(a)")[-1] == pytest.approx(1e-3, rel=NONLINEAR)
    with pytest.raises(ParseError):
        netlist(keyword)


@pytest.mark.parametrize("word", ["sqrt", "max", "if", "sin"])
def test_a_call_and_a_param_of_the_same_name_coexist(
    solver: Solver, tmp_path: Path, word: str
) -> None:
    arguments = {"sqrt": "9", "max": "1,3", "if": "1,3,2", "sin": "0"}[word]
    call = f"{word}({arguments})"
    lines = f".param {word}=3k\nR1 a 0 {{{word}+{call}}}"
    alone = {"sqrt": 3.0, "max": 3.0, "if": 3.0, "sin": 0.0}[word]
    assert _reads(solver, tmp_path, lines) == pytest.approx(3e3 + alone, rel=LINEAR)
    assert len(netlist(_ONE_AMP.format(lines, ".op")).references_to_param(word)) == 1


def test_a_func_may_not_redefine_a_built_in_function(solver: Solver, tmp_path: Path) -> None:
    text = _ONE_AMP.format(".func sqrt(x) {x*5}\nR1 a 0 {sqrt(9)}", ".op")
    assert "built-in function" in run(solver, tmp_path, text).log
    netlist(text)  # .func is untyped text: discrepancies.md


@pytest.mark.parametrize(
    ("lines", "ltspice_runs"),
    [
        (".param temp=3k\nR1 a 0 {temp}", False),
        ("X1 a s\n.subckt s p temp=3k\nR2 p 0 {temp}\n.ends", True),
        ("X1 a s\n.subckt s p\n.param temp=3k\nR2 p 0 {temp}\n.ends", True),
    ],
)
def test_temp_may_be_defined_only_in_a_body(
    solver: Solver, tmp_path: Path, lines: str, ltspice_runs: bool
) -> None:
    text = _ONE_AMP.format(lines, ".op")
    result = run(solver, tmp_path, text)
    assert (result.returncode == 0) == ltspice_runs, result.log
    if ltspice_runs:
        assert result.voltage("a") == pytest.approx(3e3, rel=LINEAR)
    else:
        assert "reserved symbol" in result.log
    netlist(text)  # accepted: discrepancies.md


def test_a_bare_param_expression_is_scanned_like_a_formula(solver: Solver, tmp_path: Path) -> None:
    text = "probe\n.param a=1k x=a*3\nV1 in 0 3\nR1 in out 1k\nR2 out 0 {x}\n.op\n.end\n"
    assert succeeds(solver, tmp_path, text).voltage("out") == pytest.approx(2.25, rel=LINEAR)
    assert len(netlist(text).references_to_param("a")) == 1


# S12: .step defines its parameter.


def test_a_stepped_parameter_is_defined_by_its_step(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nV1 in 0 3\nR1 in out 1k\nR2 out 0 {x}\n.step param x list 1k 3k\n.op\n.end\n"
    points = op_steps(solver, tmp_path, text)
    assert [point["v(out)"] for point in points] == pytest.approx([1.5, 2.25], rel=LINEAR)
    assert codes(text) == []


def test_a_step_may_sweep_a_param_with_a_line(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\n.param x=7k\nV1 in 0 3\nR1 in out 1k\nR2 out 0 {x}\n"
        ".step param x list 1k 3k\n.op\n.end\n"
    )
    points = op_steps(solver, tmp_path, text)
    assert [point["v(out)"] for point in points] == pytest.approx([1.5, 2.25], rel=LINEAR)
    assert codes(text) == []


def test_sweeping_a_quantity_twice_stops_ltspice(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nV1 in 0 3\nR1 in out 1k\nR2 out 0 {x}\n"
        ".step param x list 1k 3k\n.step param x list 2k 4k\n.op\n.end\n"
    )
    assert not run(solver, tmp_path, text).ok
    assert codes(text) == [DiagnosticCode.DUPLICATE_DEFINITION]
