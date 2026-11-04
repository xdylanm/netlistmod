"""ngspice 47 probes for the entries and rules M7 validates (M7 T8, T8 tier; decision 0008).

Each probe pairs what ngspice does with what the library does, for the spec entries that were
``documented`` before M7 (``NG-DIR-001``, ``NG-NOD-001``, ``NG-PAR-001``, ``NG-UNS-001``,
``NG-VAL-001``), ``NG-STR-001`` and rule S9 of ``scoping.md`` (m7-tasks.md section 5). Unless
noted, the circuit is a divider, ``V1 in 0 DC 3`` with two 1k resistors, and the result is
``v(out)`` of the ``.op`` read from the raw file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import (
    DiagnosticCode,
    Dialect,
    Formula,
    Netlist,
    OpaqueBlock,
    ParseError,
    Resistor,
    SourceText,
    UnknownDirective,
    UnsupportedConstruct,
    parse,
)
from tests.support.ngspice import STUBS, run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ngspice")

_DIVIDER = "probe\nV1 in 0 DC 3\nR1 in {node} 1k\nR2 {node} 0 {r2}\n{extra}.op\n.end\n"


def _divider(extra: str = "", *, node: str = "out", r2: str = "1k") -> str:
    return _DIVIDER.format(node=node, r2=r2, extra=extra)


def _rejects(text: str, error: type[Exception] = ParseError) -> None:
    with pytest.raises(error):
        parse(SourceText(text), Dialect.NGSPICE)


# NG-DIR-001: unknown dot-commands and stray block terminators.


@pytest.mark.parametrize("extra", [".print op v(out)\n", ".width out=80\n", ".func dbl(x) {2*x}\n"])
def test_unknown_dot_commands_run_and_stay_unknown_directives(
    solver: Solver, tmp_path: Path, extra: str
) -> None:
    text = _divider(extra)
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert result.voltage("out") == pytest.approx(1.5)
    netlist = Netlist.from_text(text, dialect=Dialect.NGSPICE)
    assert isinstance(netlist.lines[4].item, UnknownDirective)
    assert [d.code for d in netlist.diagnostics] == [DiagnosticCode.UNTYPED_DIRECTIVE_PRESERVED]


def test_a_func_directive_takes_effect_in_a_value(solver: Solver, tmp_path: Path) -> None:
    # The library keeps .func as text; the formula {dbl(1k)} is a call, not a reference.
    text = _divider(".func dbl(x) {2*x}\n", r2="{dbl(1k)}")
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert result.voltage("out") == pytest.approx(2.0)
    netlist = Netlist.from_text(text, dialect=Dialect.NGSPICE)
    assert isinstance(netlist.lines[4].item, UnknownDirective)
    assert netlist.references == ()


def test_a_stray_endc_runs_with_a_warning_but_the_library_rejects_it(
    solver: Solver, tmp_path: Path
) -> None:
    text = _divider(".endc\n")
    result = run(solver, tmp_path, text)
    assert result.returncode == 0, result.log
    assert "Warning: Missing .control statement!" in result.log
    assert result.voltage("out") == pytest.approx(1.5)
    _rejects(text)


@pytest.mark.parametrize("extra", [".endif\n", ".else\n", ".elseif (1)\n"])
def test_stray_conditional_terminators_fail_in_both(
    solver: Solver, tmp_path: Path, extra: str
) -> None:
    text = _divider(extra)
    assert run(solver, tmp_path, text).returncode != 0
    _rejects(text)


# NG-NOD-001: names.


@pytest.mark.parametrize("node", ["a/b", "n+1", "n-1", "a#b", "1n", "N_OUT.2"])
def test_node_name_characters_agree_with_solver(solver: Solver, tmp_path: Path, node: str) -> None:
    text = _divider(node=node)
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert result.voltage(node.lower()) == pytest.approx(1.5)
    netlist = Netlist.from_text(text, dialect=Dialect.NGSPICE)
    assert [net.name for net in netlist.nets()] == ["in", "0", node.lower()]


@pytest.mark.parametrize("node", ["o[1]", "a%b", "a<b", "a~b", "a(b"])
def test_excluded_name_characters_run_but_the_library_rejects_them(
    solver: Solver, tmp_path: Path, node: str
) -> None:
    # §2.1.3.4 lists characters a node name may not contain; ngspice 47 accepts these.
    text = _divider(node=node)
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert result.voltage(node) == pytest.approx(1.5)
    _rejects(text)


@pytest.mark.parametrize("node", ["a'b", "a=b"])
def test_quote_and_equals_in_a_node_name_fail_in_both(
    solver: Solver, tmp_path: Path, node: str
) -> None:
    text = _divider(node=node)
    assert run(solver, tmp_path, text).returncode != 0
    _rejects(text)


# NG-PAR-001: instance parameters and the off flag.


@pytest.mark.parametrize(
    ("param", "extra", "expected"),
    [
        ("m=2", "", 2.0),  # two 1k in parallel
        ("tc1=0.01", ".temp 127\n", 1.0),  # 1k * (1 + 0.01 * (127 - 27)) = 2k
    ],
)
def test_instance_parameters_move_the_result(
    solver: Solver, tmp_path: Path, param: str, extra: str, expected: float
) -> None:
    text = _divider(extra).replace("R1 in out 1k", f"R1 in out 1k {param}")
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert result.voltage("out") == pytest.approx(expected, rel=1e-6)
    resistor = Netlist.from_text(text, dialect=Dialect.NGSPICE).element("R1")
    assert [(p.name, p.value.text) for p in getattr(resistor, "params")] == [
        tuple(param.split("="))
    ]


def test_the_off_flag_on_a_diode_runs(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nV1 in 0 DC 3\nR1 in a 1k\nD1 a 0 dm off\n.model dm d\n.op\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert 0.6 < result.voltage("a") < 0.7
    diode = Netlist.from_text(text, dialect=Dialect.NGSPICE).element("D1")
    assert [flag.name for flag in getattr(diode, "flags")] == ["off"]


# NG-UNS-001: recognised but unsupported forms are real ngspice syntax.


def test_the_charge_form_runs_and_the_library_reports_it_unsupported(
    solver: Solver, tmp_path: Path
) -> None:
    text = "probe\nV1 in 0 DC 3\nR1 in out 1k\nC1 out 0 q={1n*v(out)}\n.tran 1u 10u\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    _rejects(text, UnsupportedConstruct)


def test_params_keyword_on_an_x_line_runs_but_the_library_rejects_it(
    solver: Solver, tmp_path: Path
) -> None:
    text = (
        "probe\nV1 in 0 DC 3\nX1 in out div params: r=2k\n"
        ".subckt div a b r=1k\nR1 a b 1k\nR2 b 0 {r}\n.ends\n.op\n.end\n"
    )
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert result.voltage("out") == pytest.approx(2.0)
    with pytest.raises(ParseError, match="params:"):
        parse(SourceText(text), Dialect.NGSPICE)


# NG-VAL-001: formulas and string values.


@pytest.mark.parametrize("value", ["{a*2}", "'a*2'"])
def test_brace_and_quote_formulas_evaluate_alike(
    solver: Solver, tmp_path: Path, value: str
) -> None:
    text = _divider(r2=value).replace("probe\n", "probe\n.param a=1k\n")
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert result.voltage("out") == pytest.approx(2.0)
    resistor = Netlist.from_text(text, dialect=Dialect.NGSPICE).element("R2")
    assert isinstance(resistor, Resistor) and isinstance(resistor.value, Formula)
    assert resistor.value.text == "a*2"


def test_a_semicolon_inside_braces_fails_in_both(solver: Solver, tmp_path: Path) -> None:
    text = _divider(r2="{a;b}").replace("probe\n", "probe\n.param a=1k b=1k\n")
    assert run(solver, tmp_path, text).returncode != 0
    _rejects(text)


@pytest.mark.parametrize("call", ["X1 in out div", 'X1 in out div f="y"'])
def test_string_defaults_and_overrides_run(solver: Solver, tmp_path: Path, call: str) -> None:
    text = (
        f'probe\nV1 in 0 DC 3\n{call}\n.subckt div a b f="x"\nR1 a b 1k\nR2 b 0 1k\n.ends\n'
        ".op\n.end\n"
    )
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert result.voltage("out") == pytest.approx(1.5)
    assert Netlist.from_text(text, dialect=Dialect.NGSPICE).diagnostics == ()


# NG-STR-001: top-level structure (structure_basic, with a condition ngspice can read).


def test_structure_sample_runs_with_a_valid_condition(solver: Solver, tmp_path: Path) -> None:
    # structure_basic.cir with `.if (enabled)` for `.if {enabled}` (which ngspice 47 rejects,
    # m7-tasks.md T10), the parameters defined, a source and load for v(out), and a control
    # block that runs before it reads v(out). The fixture includes models.lib whole and as a
    # library section, which no one file can serve in ngspice 47 (a `.lib` section in a file
    # included whole is "unimplemented"), so the two lines name two stubs.
    text = (
        "M2 structural sample\n* full-line comment\n\n.param enabled=1 nested=0\n"
        "V1 out 0 DC 1\nR1 out 0 1k\n"
        ".plot v(out)\n  + display options\n"
        '.include "structure_models.inc"\n.lib structure_models.lib typical\n'
        ".control\nop\nlet trace = v(out)\n.endc\n"
        ".if (enabled)\n.if (nested)\n.endif\n.else\n.endif\n.op\n.end\n"
    )
    for stub in ("structure_models.inc", "structure_models.lib"):
        (tmp_path / stub).write_bytes((STUBS / stub).read_bytes())
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert result.voltage("out") == pytest.approx(1.0)
    items = parse(SourceText(text), Dialect.NGSPICE).items
    assert sum(isinstance(item, OpaqueBlock) for item in items) == 2


def test_an_if_condition_in_braces_fails_in_ngspice_but_the_library_keeps_it(
    solver: Solver, tmp_path: Path
) -> None:
    # Opaque text (decision 0008 item 1): the library keeps `.if` blocks opaque and does not
    # check the condition; ngspice 47 reads `.if (expr)` and stops at `.if {expr}`.
    braces = _divider(".param enabled=1\n.if {enabled}\n.endif\n")
    result = run(solver, tmp_path, braces)
    assert result.returncode != 0
    assert "Bad sytax in netlist line .if {enabled}" in result.log  # sic
    parens = braces.replace("{enabled}", "(enabled)")
    assert run(solver, tmp_path, parens).ok
    for text in (braces, parens):
        items = parse(SourceText(text), Dialect.NGSPICE).items
        assert any(isinstance(item, OpaqueBlock) and item.kind == "if" for item in items)


# Rule S9 of scoping.md: K, .dc and .save i() name elements of the same scope.

_CELL = ".subckt cell a\nL1 a b 1m\nR8 b 0 1k\nV9 a c 0\nR9 c 0 1k\n.ends\n"


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        (
            "V1 in 0 DC 0 AC 1\nX1 in cell\nL2 s 0 1m\nR2 s 0 1k\nK1 L1 L2 0.5\n.ac lin 1 1k 1k\n",
            "coupling to non-existent inductor l1",
        ),
        ("V1 in 0 DC 1\nX1 in cell\n.dc V9 0 1 1\n", "not in the circuit"),
        ("V1 in 0 DC 1\nX1 in cell\n.save i(V9)\n.op\n", "no data saved"),
    ],
)
def test_top_level_references_do_not_reach_into_an_instance(
    solver: Solver, tmp_path: Path, lines: str, message: str
) -> None:
    text = f"probe\n{lines}{_CELL}.end\n"
    result = run(solver, tmp_path, text)
    assert not result.ok
    assert message in result.log, result.log
    netlist = Netlist.from_text(text, dialect=Dialect.NGSPICE)
    assert [d.code for d in netlist.diagnostics] == [DiagnosticCode.UNRESOLVED_ELEMENT]
