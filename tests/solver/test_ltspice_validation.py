"""LTspice 26.1.1 probes for every ``LT-*`` spec entry (M8 T12, T8 tier; decision 0009).

Each probe pairs what LTspice does with what the library does. Unless noted, the circuit is a
divider, ``V1 in 0 3`` with two 1k resistors, and the result is ``V(out)`` of the ``.op`` read from
the ASCII raw file. Only syntax facts come out of these runs; nothing LTspice writes is committed
(decision 0009 item 2). ``test_ltspice_discrepancies.py`` probes the rows of ``discrepancies.md``,
and ``test_ltspice_solver_document.py`` the rule tables of ``names.md`` and ``scoping.md``.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from netlistmod import (
    Dialect,
    Formula,
    Netlist,
    NumericValue,
    OpaqueStatement,
    ParseError,
    Resistor,
    SourceText,
    StepDirective,
    SubcktInstance,
    UnknownDirective,
    UnsupportedConstruct,
    parse,
)
from tests.support.ltspice import Run, op_steps, run, tran_rows
from tests.support.raw import sweeps
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ltspice")

CORPUS = Path(__file__).parents[1] / "corpus" / "ltspice"
LINEAR = 1e-6
NONLINEAR = 1e-3


def divider(extra: str = "", *, r1: str = "1k", r2: str = "1k") -> str:
    return f"probe\nV1 in 0 3\nR1 in out {r1}\nR2 out 0 {r2}\n{extra}.op\n.end\n"


def netlist(text: str) -> Netlist:
    return Netlist.from_text(text, dialect=Dialect.LTSPICE)


def runs(solver: Solver, folder: Path, text: str) -> Run:
    """Both accept ``text``: LTspice runs it and the library parses it."""
    result = run(solver, folder, text)
    assert result.ok, result.log
    netlist(text)
    return result


def stops(solver: Solver, folder: Path, text: str, message: str = "") -> None:
    """Both reject ``text``: LTspice stops and the library raises."""
    result = run(solver, folder, text)
    assert not result.ok, result.log
    assert message in result.log, result.log
    with pytest.raises((ParseError, UnsupportedConstruct)):
        parse(SourceText(text), Dialect.LTSPICE)


def resistance(solver: Solver, folder: Path, value: str) -> float:
    """How LTspice reads a value: the voltage of 1 A through a resistor of that value."""
    text = f"probe\nI1 0 a 1\nR1 a 0 {value}\n.op\n.end\n"
    result = runs(solver, folder, text)
    return result.voltage("a")


# LT-STR-001, LT-TTL-001: the first line, .title, the top-level shape.


def test_the_first_line_is_the_title_even_if_it_looks_like_an_element(
    solver: Solver, tmp_path: Path
) -> None:
    text = "V1 in 0 5\nV2 in 0 1\nR1 in 0 1k\n.op\n.end\n"
    assert runs(solver, tmp_path, text).voltage("in") == 1.0  # V1 would short V2
    assert [element.designator for element in netlist(text).elements()] == ["V2", "R1"]


def test_a_later_title_runs_and_is_kept(solver: Solver, tmp_path: Path) -> None:
    text = divider(".title a later title\n")
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(1.5)


# LT-END-001.


def test_end_may_carry_a_comment(solver: Solver, tmp_path: Path) -> None:
    text = divider().replace(".end\n", ".end ; the end\n\n")
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(1.5)


# LT-COM-001, LT-COM-002.


@pytest.mark.parametrize(
    "line", ["* star\n", "; semicolon\n", "   * indented\n", "   ; indented\n"]
)
def test_comment_lines_are_ignored(solver: Solver, tmp_path: Path, line: str) -> None:
    assert runs(solver, tmp_path, divider(line)).voltage("out") == pytest.approx(1.5)


@pytest.mark.parametrize("comment", ["; 5k", " ; 5k", " $ 5k", ' ; "quoted" $'])
def test_end_of_line_comments_hide_the_rest_of_the_line(
    solver: Solver, tmp_path: Path, comment: str
) -> None:
    text = divider(r2=f"1k{comment}")
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(1.5)


@pytest.mark.parametrize("value", ["1k $c", "1k\t$ c", "1k $\tc", "1k // c"])
def test_other_comment_forms_stop_both(solver: Solver, tmp_path: Path, value: str) -> None:
    stops(solver, tmp_path, divider(r2=value))


def test_a_dollar_line_stops_both(solver: Solver, tmp_path: Path) -> None:
    stops(solver, tmp_path, divider("$ a comment\n"), "Expected device instantiation")


# LT-CNT-001, LT-FLD-001.


def test_continuation_lines_join_the_statement(solver: Solver, tmp_path: Path) -> None:
    text = divider().replace("R2 out 0 1k\n", "R2 out\n+ 0\n  + 3k ; c\n")
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(2.25)


def test_backslash_continuation_stops_both(solver: Solver, tmp_path: Path) -> None:
    text = divider().replace("R2 out 0 1k\n", "R2 out 0 \\\\\n1k\n")
    stops(solver, tmp_path, text)


def test_blanks_tabs_and_the_equals_sign_separate_fields(solver: Solver, tmp_path: Path) -> None:
    text = divider().replace("R1 in out 1k", "R1\tin  out\t1k  m = 2")
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(2.0, rel=LINEAR)


@pytest.mark.parametrize(
    "line",
    [
        ".param a=1, b=2\n",
        ".options reltol=1m, abstol=1p\n",
        ".save V(in), V(out)\n",
        ".model dm D(Is=1n, N=2)\n",
    ],
)
def test_the_commas_the_library_accepts_run(solver: Solver, tmp_path: Path, line: str) -> None:
    assert runs(solver, tmp_path, divider(line)).voltage("out") == pytest.approx(1.5)


# LT-DIR-001, LT-TXT-001: the closed list of dot-commands.


@pytest.mark.parametrize(
    "line",
    [
        ".backanno",
        ".func dbl(x) {2*x}",
        ".four 1k V(out)",
        ".noise V(out) V1 dec 1 1 10",
        ".tf V(out) V1",
        ".wave out.wav 16 44.1K V(out)",
        ".net V(out) V1",
        ".savebias bias.txt",
        ".savestate",
    ],
)
def test_the_untyped_commands_are_kept_and_run(solver: Solver, tmp_path: Path, line: str) -> None:
    text = divider(f"{line}\n")
    result = run(solver, tmp_path, text)
    assert result.returncode == 0 and result.ok, result.log
    assert netlist(text).lines.find(UnknownDirective) is not None


@pytest.mark.parametrize("line", [".loadstate", ".loadstate reset"])
def test_loadstate_without_a_file_runs_with_a_message_and_stays_text(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    text = divider(f"{line}\n")
    result = run(solver, tmp_path, text)
    assert result.returncode == 0 and result.voltage("out") == pytest.approx(1.5)
    assert "no default loadstate file found" in result.errors[0]
    assert netlist(text).lines.find(UnknownDirective) is not None


def test_loadstate_reads_a_saved_state(solver: Solver, tmp_path: Path) -> None:
    circuit = "probe\nV1 a 0 1\nR1 a b 1k\nC1 b 0 1n\n{}\n.tran 2u\n.end\n"
    assert runs(solver, tmp_path, circuit.format('.savestate "s.st" time=1u'))
    assert (tmp_path / "s.st").is_file()
    assert runs(solver, tmp_path, circuit.format('.loadstate "s.st"')).plot("Transient").rows


def test_fra_needs_its_device(solver: Solver, tmp_path: Path) -> None:
    device = "@1 a b fstart=1k fend=2k pp0=2m pp1=1m f0=1k f1=2k\n"
    circuit = "probe\nV1 a 0 1\nR1 a b 1k\nR9 b 0 1k\n{}.fra{}\n.end\n"
    alone = run(solver, tmp_path / "alone", circuit.format("", ""))
    assert alone.returncode != 0 and "requires at least one enabled fra device" in alone.log
    assert netlist(circuit.format("", "")).lines.find(UnknownDirective) is not None
    with_device = circuit.format(device, "")
    assert run(solver, tmp_path / "device", with_device).returncode == 0
    with pytest.raises(UnsupportedConstruct):
        parse(SourceText(with_device), Dialect.LTSPICE)


@pytest.mark.parametrize("arguments", ["", " Tstart=0 dTmax=1u Tstep=1u Tstop=1m"])
def test_fra_keywords_are_read(solver: Solver, tmp_path: Path, arguments: str) -> None:
    text = f"probe\nV1 a 0 1\nR1 a b 1k\nR9 b 0 1k\n.fra{arguments}\n.end\n"
    result = run(solver, tmp_path, text)
    # Past the syntax: LTspice stops only at the missing device.
    assert not result.errors and "requires at least one enabled fra device" in result.log
    netlist(text)


def test_a_func_takes_effect_and_stays_text(solver: Solver, tmp_path: Path) -> None:
    text = divider(".func dbl(x) {2*x}\n", r2="{dbl(1k)}")
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(2.0, rel=LINEAR)
    assert netlist(text).references == ()


@pytest.mark.parametrize(
    "line",
    [".foo bar", ".tarn 1m", ".control", ".if (1)", ".endif", ".endc", ".ends"],
)
def test_other_dot_commands_stop_both(solver: Solver, tmp_path: Path, line: str) -> None:
    stops(solver, tmp_path, divider(f"{line}\n"), "Expected device instantiation")


@pytest.mark.parametrize("line", [".backanno", ".func f(x) {x}"])
def test_commands_allowed_in_a_body(solver: Solver, tmp_path: Path, line: str) -> None:
    text = divider(f"X1 in 0 s\n.subckt s a b\n{line}\nR1 a b 1k\n.ends\n")
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(1.5)


@pytest.mark.parametrize(
    "line",
    [
        ".four 1k V(a)",
        ".tran 1m",
        ".step param x 1 2 1",
        ".tf V(a) V1",
        ".savestate",
        ".loadstate",
        ".fra Tstop=1m",
    ],
)
def test_commands_stopped_in_a_body(solver: Solver, tmp_path: Path, line: str) -> None:
    text = divider(f"X1 in 0 s\n.subckt s a b\n{line}\nR1 a b 1k\n.ends\n")
    stops(solver, tmp_path, text, "Expected a sequence")


def test_a_comment_ends_the_text_of_a_measurement(solver: Solver, tmp_path: Path) -> None:
    text = divider(".meas y param 1 ; a comment\n.meas z param 2 $ a comment\n")
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(1.5)


# LT-OPA-001.


@pytest.mark.parametrize("line", [".include h.inc", ".inc h.inc", ".lib h.inc"])
def test_an_include_brings_in_its_file_and_stays_opaque(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    (tmp_path / "h.inc").write_bytes(b".param x=3k\n")
    text = divider(f"{line}\n", r2="{x}")
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(2.25, rel=LINEAR)
    assert netlist(text).lines.find(OpaqueStatement) is not None


# LT-MCH-001, LT-UNS-001.


def test_a_state_machine_runs_and_is_unsupported(solver: Solver, tmp_path: Path) -> None:
    block = (
        ".machine\n.state a 0\n.state b 1\n.rule a b time>0.5m\n.output (q) state\n.endmachine\n"
    )
    text = f"probe\nR1 q 0 1k\n{block}.tran 1m\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    with pytest.raises(UnsupportedConstruct):
        parse(SourceText(text), Dialect.LTSPICE)


@pytest.mark.parametrize(
    "line",
    [
        "C1 out 0 Q=1u*x",
        "L1 out 0 Flux=1m*x",
        "Q1 out in 0 npn\n.model npn NPN",
        "E1 a 0 in 0 2\nR9 a 0 1k",
    ],
)
def test_other_forms_run_and_are_unsupported(solver: Solver, tmp_path: Path, line: str) -> None:
    text = divider(f".param x=1\n{line}\n")
    assert run(solver, tmp_path, text).ok
    with pytest.raises(UnsupportedConstruct):
        parse(SourceText(text), Dialect.LTSPICE)


def test_ngspice_source_functions_stop_ltspice(solver: Solver, tmp_path: Path) -> None:
    stops(solver, tmp_path, divider("V9 a 0 TRNOISE(1m 1u 0 0)\n"))


@pytest.mark.parametrize("letter", ["N1 a b c", "P1 a b c", "Y1 a b c"])
def test_letters_that_are_not_ltspice_letters_stop_both(
    solver: Solver, tmp_path: Path, letter: str
) -> None:
    stops(solver, tmp_path, divider(f"{letter}\n"))


# LT-NUM-001 to LT-NUM-004.


@pytest.mark.parametrize(
    ("value", "reads"),
    [
        ("2", 2.0),
        ("2.5", 2.5),
        (".5", 0.5),
        ("1e3", 1e3),
        ("1E-3", 1e-3),
        ("+2", 2.0),
        ("2T", 2e12),
        ("2G", 2e9),
        ("2Meg", 2e6),
        ("2MEG", 2e6),
        ("2k", 2e3),
        ("2K", 2e3),
        ("2mil", 2 * 25.4e-6),
        ("2m", 2e-3),
        ("2M", 2e-3),
        ("2u", 2e-6),
        ("2n", 2e-9),
        ("2p", 2e-12),
        ("2f", 2e-15),
    ],
)
def test_numbers_and_multipliers(solver: Solver, tmp_path: Path, value: str, reads: float) -> None:
    assert resistance(solver, tmp_path, value) == pytest.approx(reads, rel=LINEAR)
    assert isinstance(netlist(f"t\nR1 a 0 {value}\n.op\n.end\n").element("R1"), Resistor)


@pytest.mark.parametrize(
    ("value", "reads"),
    [
        ("10V", 10.0),
        ("5Volts", 5.0),
        ("1kOhm", 1e3),
        ("1kΩ", 1e3),
        ("4Farads", 4e-15),
        ("1a", 1.0),
    ],
)
def test_letters_after_a_number_are_ignored(
    solver: Solver, tmp_path: Path, value: str, reads: float
) -> None:
    assert resistance(solver, tmp_path, value) == pytest.approx(reads, rel=LINEAR)


@pytest.mark.parametrize(
    ("value", "reads"),
    [
        ("2k2", 2.2e3),
        ("6K34", 6.34e3),
        ("1meg5", 1.5e6),
        ("2R2", 2.2),
        ("100R", 100.0),
        ("1M0", 1e-3),
        ("4n7", 4.7e-9),
        ("1µ5", 1.5e-6),
    ],
)
def test_the_embedded_decimal(solver: Solver, tmp_path: Path, value: str, reads: float) -> None:
    assert resistance(solver, tmp_path, value) == pytest.approx(reads, rel=LINEAR)
    resistor = netlist(f"t\nR1 a 0 {value}\n.op\n.end\n").element("R1")
    assert isinstance(resistor, Resistor) and isinstance(resistor.value, NumericValue)
    assert resistor.value.notation in ("rkm", "standard") and resistor.value.text == value


@pytest.mark.parametrize(
    ("text", "out"),
    [
        (divider().replace("V1 in 0 3", "V1 in 0 2k2"), 1100.0),
        (divider(".param x=2k2\n", r2="{x}"), 3 * 2.2 / 3.2),
        (divider(".step param x list 1k 2k2\n", r2="{x}"), None),
    ],
)
def test_the_embedded_decimal_in_other_slots(
    solver: Solver, tmp_path: Path, text: str, out: float | None
) -> None:
    if out is None:
        points = op_steps(solver, tmp_path, text)
        assert [point["x"] for point in points] == [1e3, 2.2e3]
    else:
        assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(out, rel=LINEAR)


@pytest.mark.parametrize("micro", ["µ", "μ"])
def test_both_micro_signs_read_as_micro(solver: Solver, tmp_path: Path, micro: str) -> None:
    assert resistance(solver, tmp_path, f"2{micro}") == pytest.approx(2e-6, rel=LINEAR)


def test_a_cp1252_micro_sign_reads_as_micro(solver: Solver, tmp_path: Path) -> None:
    data = "probe\nI1 0 a 1\nR1 a 0 2µ\n.op\n.end\n".encode("cp1252")
    assert run(solver, tmp_path, data).voltage("a") == pytest.approx(2e-6, rel=LINEAR)
    assert SourceText.from_bytes(data).encoding == "cp1252"


# LT-VAL-001, LT-FML-001.


@pytest.mark.parametrize("value", ["{a*2}", "'a*2'"])
def test_brace_and_quote_formulas_evaluate_alike(
    solver: Solver, tmp_path: Path, value: str
) -> None:
    text = divider(".param a=1k\n", r2=value)
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(2.0, rel=LINEAR)
    resistor = netlist(text).element("R2")
    assert isinstance(resistor, Resistor) and isinstance(resistor.value, Formula)
    assert resistor.value.text == "a*2"


def test_a_semicolon_inside_a_formula_stops_both(solver: Solver, tmp_path: Path) -> None:
    stops(solver, tmp_path, divider(".param a=1k\n", r2="{a;a}"))


@pytest.mark.parametrize(
    ("formula", "reads"),
    [("{(a&b)*3k}", 3e3), ("{(a&0)*3k+1k}", 1e3), ("{(a|0)*3k}", 3e3), ("{(0|0)*3k+1k}", 1e3)],
)
def test_single_logical_operators_evaluate(
    solver: Solver, tmp_path: Path, formula: str, reads: float
) -> None:
    text = f"probe\n.param a=1 b=1\nI1 0 x 1\nR1 x 0 {formula}\n.op\n.end\n"
    assert runs(solver, tmp_path, text).voltage("x") == pytest.approx(reads, rel=LINEAR)
    assert len(netlist(text).references_to_param("a")) == ("a" in formula)


@pytest.mark.parametrize(
    ("formula", "reads"),
    [("{pi}", math.pi), ("{sqrt(4)}", 2.0), ("{max(1, 2)}", 2.0), ("{if(1,2,3)}", 2.0)],
)
def test_constants_and_functions_are_not_references(
    solver: Solver, tmp_path: Path, formula: str, reads: float
) -> None:
    text = f"probe\nI1 0 x 1\nR1 x 0 {formula}\n.op\n.end\n"
    assert runs(solver, tmp_path, text).voltage("x") == pytest.approx(reads, rel=LINEAR)
    assert netlist(text).references == ()


# LT-PRM-001.


@pytest.mark.parametrize(
    "line",
    [
        ".param x=3k\n",
        ".param x 3k\n",
        ".param x = 3k\n",
        ".param x={3k}\n",
        ".param x='3k'\n",
        ".param x=1k+2k\n",
        ".param x=1k + 2k\n",
        ".param y=2k x=y+1k\n",
        ".param y=2k, x=y+1k\n",
        ".param y 2k x 3k\n",
        ".param x=max(1k, 3k) y=1\n",
    ],
)
def test_param_forms_give_the_same_value(solver: Solver, tmp_path: Path, line: str) -> None:
    text = divider(line, r2="{x}")
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(2.25, rel=LINEAR)
    assert len(netlist(text).references_to_param("x")) >= 1


@pytest.mark.parametrize("name", ["time", "temper", "hertz", "_p", "q.r", "s#t"])
def test_other_parameter_names_run(solver: Solver, tmp_path: Path, name: str) -> None:
    text = divider(f".param {name}=3k\n", r2=f"{{{name}}}")
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(2.25, rel=LINEAR)


def test_a_string_parameter_runs(solver: Solver, tmp_path: Path) -> None:
    assert runs(solver, tmp_path, divider('.param u="text"\n')).voltage("out") == pytest.approx(1.5)


@pytest.mark.parametrize("line", [".param x", ".param x=1 2", ".param 1a=1"])
def test_malformed_params_stop_both(solver: Solver, tmp_path: Path, line: str) -> None:
    stops(solver, tmp_path, divider(f"{line}\n"))


# LT-RES-001.


@pytest.mark.parametrize(
    ("params", "extra", "out"),
    [
        ("m=2", "", 2.0),  # 1k / 2 for R1
        ("tc=0.01", ".temp 127\n", 1.0),  # 1k * (1 + 0.01 * 100) = 2k for R1
        ("tc=0.01,0", ".temp 127\n", 1.0),
        ("tc=0.01, 0, 0", ".temp 127\n", 1.0),
        ("tc1=0.01", ".temp 127\n", 1.0),
        ("tc1=0 tc2=1u", ".temp 1027\n", 1.0),  # 1k * (1 + 1u * 1000^2) = 2k
        ("tc=0.01 temp=127", "", 1.0),
        ("tol=1", "", 1.5),
        ("pwr=0.25", "", 1.5),
        ('mfg="Vishay, Inc." pn=CRCW0603', "", 1.5),
        ("noiseless", "", 1.5),
        ("noiseless=0", "", 1.5),
    ],
)
def test_resistor_parameters(
    solver: Solver, tmp_path: Path, params: str, extra: str, out: float
) -> None:
    text = divider(extra, r1=f"1k {params}")
    plot = runs(solver, tmp_path, text).plot("Operating Point")
    assert plot.real("V(out)")[0] == pytest.approx(out, rel=LINEAR)


@pytest.mark.parametrize("value", ["R47", "x", "x*3", '"1k"', "1k foo=1", "1k rm", "1k 5k"])
def test_malformed_resistor_lines_stop_both(solver: Solver, tmp_path: Path, value: str) -> None:
    stops(solver, tmp_path, divider(r2=value))


# LT-CAP-001.


@pytest.mark.parametrize(
    "params",
    [
        "Rser=1",
        "Lser=1n",
        "Rser=1 Lser=1n RLshunt=1",
        "Cpar=1p",
        "m=2",
        "temp=30",
        "V=6.3 Irms=1.2",
        'mfg="TDK" pn=C3216 type="X5R"',
        "noiseless",
        "noiseless=1",
    ],
)
def test_capacitor_parameters_run(solver: Solver, tmp_path: Path, params: str) -> None:
    text = divider(f"C1 out 0 1u {params}\n")
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(1.5, rel=LINEAR)


def test_capacitor_parameters_take_effect(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nV1 in 0 3\nR1 in out 1k\nC1 out 0 1u Rpar=1k\n.op\n.end\n"
    assert runs(solver, tmp_path / "rpar", text).voltage("out") == pytest.approx(1.5, rel=LINEAR)
    # ic= also holds the capacitor at that voltage in an operating point.
    held = "probe\nV1 in 0 3\nR1 in out 1k\nC1 out 0 1u ic=0\n.op\n.end\n"
    assert runs(solver, tmp_path / "held", held).voltage("out") == pytest.approx(0, abs=1e-4)
    # The first row of a `uic` transient holds zeros, so the initial value is in the second.
    charged = "probe\nR1 out 0 1k\nC1 out 0 1u ic=2{m}\n.tran 1m uic\n.end\n"
    rows = tran_rows(solver, tmp_path / "ic", charged.format(m=""))
    assert rows[1]["v(out)"] == pytest.approx(2.0, rel=NONLINEAR)
    assert rows[-1]["v(out)"] == pytest.approx(2 * math.exp(-1), rel=NONLINEAR)
    # Two capacitors in parallel double the time constant.
    rows = tran_rows(solver, tmp_path / "m", charged.format(m=" m=2"))
    assert rows[-1]["v(out)"] == pytest.approx(2 * math.exp(-0.5), rel=NONLINEAR)


def test_malformed_capacitor_lines_stop_both(solver: Solver, tmp_path: Path) -> None:
    stops(solver, tmp_path, divider("C1 out 0 1u Rsr=1\n"), "Unknown parameter")
    stops(solver, tmp_path, divider('C1 out 0 1u V="6.3"\n'), "Numeric value expected")


# LT-IND-001.


@pytest.mark.parametrize(
    "params",
    [
        "Rser=1",
        "Rpar=1k",
        "Cpar=1p",
        "m=2 Rser=1",
        "temp=30 tc1=1m tc2=1u",
        "ic=0",
        "Ipk=5",
        'mfg="Bourns, Inc." pn=SRP1245A',
        "noiseless",
        "noiseless=0",
    ],
)
def test_inductor_parameters_run(solver: Solver, tmp_path: Path, params: str) -> None:
    text = f"probe\nV1 in 0 3\nR1 in out 1k\nL1 out a 1m {params}\nR2 a 0 1k\n.op\n.end\n"
    assert runs(solver, tmp_path, text).voltage("in") == 3.0


def test_inductor_parameters_take_effect(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nV1 in 0 3\nR1 in out 1k\nL1 out 0 1m Rser=1k\n.op\n.end\n"
    assert runs(solver, tmp_path / "rser", text).voltage("out") == pytest.approx(1.5, rel=LINEAR)
    # A current held by ic=1 decays through the 1 Ω load, with tau = 1 ms.
    decay = "probe\nL1 out 0 1m ic=1\nR1 out 0 1\n.tran 1m uic\n.end\n"
    rows = tran_rows(solver, tmp_path / "ic", decay)
    assert rows[1]["v(out)"] == pytest.approx(-1.0, rel=NONLINEAR)


@pytest.mark.parametrize("params", ["tc=1m", 'type="x"', "foo=1"])
def test_malformed_inductor_lines_stop_both(solver: Solver, tmp_path: Path, params: str) -> None:
    stops(solver, tmp_path, divider(f"L1 out 0 1m {params}\n"), "Unknown parameter")


# LT-SRC-001.


@pytest.mark.parametrize(
    ("source", "out"),
    [
        ("3", 1.5),
        ("DC 3", 1.5),
        ("3 Rser=1k", 1.0),
        ("3 AC 1", 1.5),
        ("3 AC=1 45", 1.5),
        ("DC 3 AC 1 45 Rser=1k Cpar=1p", 1.0),
    ],
)
def test_voltage_source_forms(solver: Solver, tmp_path: Path, source: str, out: float) -> None:
    text = f"probe\nV1 in 0 {source}\nR1 in out 1k\nR2 out 0 1k\n.op\n.end\n"
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(out, rel=LINEAR)


def test_a_source_without_a_value_runs_with_a_warning(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nV1 in 0\nR1 in 0 1k\n.op\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.returncode == 0 and "Missing value, assuming 0V" in result.log
    assert result.voltage("in") == 0.0
    netlist(text)


@pytest.mark.parametrize(
    ("source", "out"),
    [
        ("1m", 1.0),
        ("DC 1m", 1.0),
        ("1m AC 1", 1.0),
    ],
)
def test_current_source_forms(solver: Solver, tmp_path: Path, source: str, out: float) -> None:
    text = f"probe\nI1 0 a {source}\nR1 a 0 1k\n.op\n.end\n"
    assert runs(solver, tmp_path, text).voltage("a") == pytest.approx(out, rel=NONLINEAR)


@pytest.mark.parametrize("flag", ["load", "load=1"])
def test_a_load_source_sinks_its_current(solver: Solver, tmp_path: Path, flag: str) -> None:
    text = f"probe\nV1 in 0 3\nR1 in a 1k\nI1 a 0 1m {flag}\n.op\n.end\n"
    assert runs(solver, tmp_path, text).voltage("a") == pytest.approx(2.0, rel=NONLINEAR)


@pytest.mark.parametrize("source", ["AC 1 45", "R=1k"])
def test_current_source_forms_without_a_dc_value(
    solver: Solver, tmp_path: Path, source: str
) -> None:
    text = f"probe\nV1 b 0 1\nI1 b a {source}\nR1 a 0 1k\n.op\n.end\n"
    runs(solver, tmp_path, text)


@pytest.mark.parametrize("line", ["I1 a 0", "I1 a 0 1m Rser=1"])
def test_malformed_current_sources_stop_both(solver: Solver, tmp_path: Path, line: str) -> None:
    stops(solver, tmp_path, divider(f"{line}\n"))


# LT-DIO-001.

_DIODE = "probe\nI1 0 a 1m\nD1 a 0 dm{params}\n.model dm D(Is=1e-14)\n.op\n.end\n"
VT = 1.380649e-23 * 300.15 / 1.602176634e-19


@pytest.mark.parametrize(
    ("params", "factor", "slope"),
    [
        ("", 1.0, 1.0),
        (" 2", 2.0, 1.0),
        (" area=2", 2.0, 1.0),
        (" m=2", 2.0, 1.0),
        (" n=2", 1.0, 2.0),
        (" 2 m=2", 4.0, 1.0),
    ],
)
def test_diode_parameters_take_effect(
    solver: Solver, tmp_path: Path, params: str, factor: float, slope: float
) -> None:
    text = _DIODE.format(params=params)
    voltage = runs(solver, tmp_path, text).voltage("a")
    assert voltage == pytest.approx(
        slope * VT * math.log(1e-3 / (factor * 1e-14) + 1), rel=NONLINEAR
    )


def test_diode_rpar_takes_effect(solver: Solver, tmp_path: Path) -> None:
    text = _DIODE.format(params=" Rpar=1")
    assert runs(solver, tmp_path, text).voltage("a") == pytest.approx(1e-3, rel=NONLINEAR)


@pytest.mark.parametrize("params", [" off", " off=1", " 2 off", " temp=30", " off area=3"])
def test_other_diode_forms_run(solver: Solver, tmp_path: Path, params: str) -> None:
    runs(solver, tmp_path, _DIODE.format(params=params))


@pytest.mark.parametrize("params", [" off 2", " foo=1"])
def test_malformed_diodes_stop_both(solver: Solver, tmp_path: Path, params: str) -> None:
    stops(solver, tmp_path, _DIODE.format(params=params))


# LT-SUB-001, LT-SBD-001.

_DEFINITION = ".subckt div a b r=1k\nR1 a b 1k\nR2 b 0 {r}\n.ends\n"


@pytest.mark.parametrize(
    ("call", "out"),
    [
        ("X1 in out div", 1.5),
        ("X1 in out div r=3k", 2.25),
        ("X1 in out div params: r=3k", 2.25),
        ("X§U1 in out div r=3k ;§pnba a)b", 2.25),
        ("X1 in out div r=3k5", 3 * 3.5 / 4.5),
    ],
)
def test_subcircuit_calls(solver: Solver, tmp_path: Path, call: str, out: float) -> None:
    text = f"probe\nV1 in 0 3\n{call}\n{_DEFINITION}.op\n.end\n"
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(out, rel=LINEAR)
    assert netlist(text).lines.find(SubcktInstance) is not None


@pytest.mark.parametrize(
    "header",
    [
        ".subckt div a b r=1k",
        ".subckt div a b params: r=1k",
        ".SUBCKT div a b r={1k}",
    ],
)
def test_subcircuit_headers(solver: Solver, tmp_path: Path, header: str) -> None:
    body = "R1 a b 1k\nR2 b 0 {r}\n.ends div\n"
    text = f"probe\nV1 in 0 3\nX1 in out div\n{header}\n{body}.op\n.end\n"
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(1.5, rel=LINEAR)


def test_definitions_nest(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nV1 in 0 3\nX1 in out outer\n.subckt outer a b\nX2 a b inner\nR2 b 0 1k\n"
        ".subckt inner p q\nR1 p q 1k\n.ends inner\n.ends outer\n.op\n.end\n"
    )
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(1.5, rel=LINEAR)


@pytest.mark.parametrize("line", [".tran 1m", ".step param x 1 2 1", ".global a"])
def test_top_level_statements_in_a_body_stop_both(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    text = f"probe\nV1 in 0 3\nX1 in 0 s\n.subckt s a b\n{line}\nR1 a b 1k\n.ends\n.op\n.end\n"
    stops(solver, tmp_path, text)


# LT-MUT-001.


@pytest.mark.parametrize(
    "coupling", ["K1 L1 L2 0.5", "K1 L1 L2 L3 0.5", "K1 L1 L2 L3 L4 0.5", "K1 l1 l2 0m5"]
)
def test_couplings(solver: Solver, tmp_path: Path, coupling: str) -> None:
    text = (
        "probe\nV1 a 0 0 AC 1 Rser=1\nL1 a 0 1m\nL2 b 0 1m\nL3 c 0 1m\nL4 e 0 1m\n"
        f"R2 b 0 1k\nR3 c 0 1k\nR4 e 0 1k\n{coupling}\n.ac list 1k\n.end\n"
    )
    assert runs(solver, tmp_path, text).plot("AC").rows


def test_a_coupling_with_one_inductor_stops_both(solver: Solver, tmp_path: Path) -> None:
    stops(solver, tmp_path, divider("L1 a 0 1m\nK1 L1 0.5\n"), "Expected names of inductors")


# LT-MOD-001.


@pytest.mark.parametrize(
    "model",
    [
        ".model dm D(Is=1e-14)",
        ".model dm D Is=1e-14",
        ".model dm D(Is=1e-14, N=1)",
        ".model base D(Is=1e-14)\n.model dm ako:base D(N=1)",
        ".model dm D(Is={1e-14})",
        ".model dm D(Is=1e-14 mfg=OnSemi type=silicon)",
        '.model dm D(Is=1e-14 mfg="On Semi, Inc." type="a b")',
        ".model dm D(Is=1e-14 Iave=1 Vpk=75)",
    ],
)
def test_model_forms_read_the_same(solver: Solver, tmp_path: Path, model: str) -> None:
    text = f"probe\nI1 0 a 1m\nD1 a 0 dm\n{model}\n.op\n.end\n"
    assert runs(solver, tmp_path, text).voltage("a") == pytest.approx(
        VT * math.log(1e-3 / 1e-14 + 1), rel=NONLINEAR
    )


def test_a_derived_model_inherits_and_overrides(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nI1 0 a 1m\nD1 a 0 dm\n.model base D(Is=1e-14 N=1)\n.model dm ako:base D(N=2)\n"
        ".op\n.end\n"
    )
    assert runs(solver, tmp_path, text).voltage("a") == pytest.approx(
        2 * VT * math.log(1e-3 / 1e-14 + 1), rel=NONLINEAR
    )
    assert len(netlist(text).references) == 2


@pytest.mark.parametrize(
    "parameters", ["Is=x", "Is=abc", "Is=1n*2", "pn=OnSemi", "pn=1N4148A", 'pn="3M"']
)
def test_a_model_bare_word_is_rejected_by_the_library(parameters: str) -> None:
    text = f"probe\n.param x=1n\nI1 0 a 1m\nD1 a 0 dm\n.model dm D({parameters})\n.op\n.end\n"
    with pytest.raises(ParseError):
        parse(SourceText(text), Dialect.LTSPICE)


def test_pn_on_a_model_is_an_ignored_numeric_name(solver: Solver, tmp_path: Path) -> None:
    # T12 pin (m8-tasks.md section 12): `pn` is not a metadata name on a .model.
    text = "probe\nI1 0 a 1m\nD1 a 0 dm\n.model dm D(Is=1e-14 pn=3M)\n.op\n.end\n"
    assert run(solver, tmp_path / "number", text).returncode == 0
    netlist(text)
    word = text.replace("pn=3M", "pn=OnSemi")
    result = run(solver, tmp_path / "word", word)
    assert result.returncode == 0 and "Ignoring unknown model parameter" in result.log
    assert not run(solver, tmp_path / "part", text.replace("pn=3M", "pn=1N4148A")).ok


# LT-TRN-001.


@pytest.mark.parametrize(
    "line",
    [
        ".tran 1m",
        ".tran 1u 1m",
        ".tran 1u 1m 0",
        ".tran 1u 1m 0 1u",
        ".tran 1m uic",
        ".tran 1m startup",
        ".tran 1m nodiscard",
        ".tran 1u 1m 0 1u uic",
        ".tran 1m startup uic nodiscard",
        ".tran 1m1",
    ],
)
def test_tran_forms(solver: Solver, tmp_path: Path, line: str) -> None:
    text = f"probe\nV1 in 0 1\nR1 in out 1k\nC1 out 0 1n\n{line}\n.end\n"
    assert runs(solver, tmp_path, text).plot("Transient").rows


def test_steady_is_read_but_needs_a_circuit_with_a_steady_state(
    solver: Solver, tmp_path: Path
) -> None:
    text = "probe\nV1 in 0 1\nR1 in out 1k\nC1 out 0 1n\n.tran 1m steady\n.end\n"
    assert "Don't know how to detect" in run(solver, tmp_path, text).log
    netlist(text)


@pytest.mark.parametrize("line", [".tran 1u 1m 0 1u 5u", ".tran 1m foo"])
def test_malformed_tran_stops_both(solver: Solver, tmp_path: Path, line: str) -> None:
    stops(solver, tmp_path, f"probe\nV1 in 0 1\nR1 in 0 1k\n{line}\n.end\n", "Expected end of line")


# LT-ACA-001.

_RC = "probe\nV1 in 0 0 AC 1\nR1 in out 1k\nC1 out 0 1u\n{}\n.end\n"


@pytest.mark.parametrize(
    ("line", "points"),
    [
        (".ac lin 3 100 300", 3),
        (".ac oct 1 100 400", 3),
        (".ac dec 1 100 1k", 2),
        (".ac list 100 200", 2),
        (".ac list 100 1k5", 2),
    ],
)
def test_ac_forms(solver: Solver, tmp_path: Path, line: str, points: int) -> None:
    assert len(runs(solver, tmp_path, _RC.format(line)).plot("AC").rows) == points


def test_ac_reads_a_file(solver: Solver, tmp_path: Path) -> None:
    (tmp_path / "freq.txt").write_bytes(b"100 200 300\n")
    assert len(runs(solver, tmp_path, _RC.format(".ac file=freq.txt")).plot("AC").rows) == 3


def test_an_empty_ac_list_stops_both(solver: Solver, tmp_path: Path) -> None:
    stops(solver, tmp_path, _RC.format(".ac list"), "Expected list")


# LT-DCA-001.

_SOURCES = "probe\nV1 a 0 1\nV2 b 0 1\nV3 c 0 1\nR1 a 0 1k\nR2 b 0 1k\nR3 c 0 1k\n{}\n.end\n"


@pytest.mark.parametrize(
    ("line", "points"),
    [
        (".dc V1 0 3 1", 4),
        (".dc lin V1 0 3 1", 4),
        (".dc dec V1 1 100 1", 3),
        (".dc oct V1 1 4 1", 3),
        (".dc V1 list 1 2 3", 3),
        (".dc V1 0 1 1 V2 0 2 1", 6),
        (".dc V1 0 1 1 V2 0 1 1 V3 0 1 1", 8),
        (".dc dec V1 1 10 1 V2 list 1 2 3", 6),
    ],
)
def test_dc_forms(solver: Solver, tmp_path: Path, line: str, points: int) -> None:
    assert len(runs(solver, tmp_path, _SOURCES.format(line)).plot("DC").rows) == points


def test_dc_reads_a_file(solver: Solver, tmp_path: Path) -> None:
    (tmp_path / "v.txt").write_bytes(b"1 2 3\n")
    assert len(runs(solver, tmp_path, _SOURCES.format(".dc V1 file=v.txt")).plot("DC").rows) == 3


def test_four_sweeps_stop_both(solver: Solver, tmp_path: Path) -> None:
    text = _SOURCES.format(".dc V1 0 1 1 V2 0 1 1 V3 0 1 1 V1 0 1 1")
    stops(solver, tmp_path, text, "syntax error")


# LT-OPP-001.


def test_op(solver: Solver, tmp_path: Path) -> None:
    assert runs(solver, tmp_path, divider()).plot("Operating Point").rows
    stops(solver, tmp_path, divider().replace(".op", ".op 1"), "syntax error")


# LT-STP-001.

_STEP = "probe\n.model dm D(Is=1n)\nV1 in 0 3\nR1 in out 1k\nR2 out 0 {{x}}\n{}\n.op\n.end\n"


@pytest.mark.parametrize(
    ("line", "count"),
    [
        (".step param x 1k 3k 2k", 2),
        (".step param x lin 1k 3k 2k", None),
        (".step lin param x 1k 3k 2k", 2),
        (".step dec param x 1 100 1", 3),
        (".step oct param x 1 4 1", 3),
        (".step param x list 1k 2k 3k", 3),
        (".step param x list 1k 2k2", 2),
    ],
)
def test_step_forms(solver: Solver, tmp_path: Path, line: str, count: int | None) -> None:
    text = _STEP.format(line)
    if count is None:
        assert not run(solver, tmp_path, text).ok
        with pytest.raises(ParseError):
            parse(SourceText(text), Dialect.LTSPICE)
        return
    assert len(op_steps(solver, tmp_path, text)) == count
    assert netlist(text).lines.find(StepDirective) is not None


@pytest.mark.parametrize(
    ("line", "count"),
    [
        (".step V1 1 2 1", 2),
        (".step temp list 0 27", 2),
        (".step D dm(Is) 1n 2n 1n", 2),
    ],
)
def test_step_sweeps_other_quantities(
    solver: Solver, tmp_path: Path, line: str, count: int
) -> None:
    text = _STEP.format(f".param x=1k\n{line}")
    assert len(op_steps(solver, tmp_path, text)) == count
    netlist(text)


def test_step_reads_a_file(solver: Solver, tmp_path: Path) -> None:
    (tmp_path / "v.txt").write_bytes(b"1k 2k 3k\n")
    assert len(op_steps(solver, tmp_path, _STEP.format(".step param x file=v.txt"))) == 3


def test_nested_steps_multiply(solver: Solver, tmp_path: Path) -> None:
    text = _STEP.format(".param y=1\n.step param x list 1k 2k\n.step param y list 1 2 3")
    assert len(op_steps(solver, tmp_path, text)) == 6
    four = (
        "probe\nV1 in 0 3\nR1 in out {a+b+c+d}\nR2 out 0 1k\n"
        ".step param a list 1 2\n.step param b list 1 2\n.step param c list 1 2\n"
        ".step param d list 1 2\n.op\n.end\n"
    )
    assert len(op_steps(solver, tmp_path, four)) == 16


@pytest.mark.parametrize(
    "line",
    [
        ".step param x {1} 2 1",
        ".step lin param x list 1 2",
        ".step param x list 1",
    ],
)
def test_malformed_step_stops_both(solver: Solver, tmp_path: Path, line: str) -> None:
    stops(solver, tmp_path, _STEP.format(line))


def test_a_stepped_transient_writes_one_sweep_per_value(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nV1 in 0 1\nR1 in out {x}\nC1 out 0 1u\n.ic V(out)=0\n"
        ".step param x list 1k 2k 4k\n.tran 1m uic\n.end\n"
    )
    assert len(sweeps(runs(solver, tmp_path, text).plot("Transient"))) == 3


# LT-TMP-001.


@pytest.mark.parametrize(("line", "count"), [(".temp 127", 1), (".temp 27 127", 2)])
def test_temp(solver: Solver, tmp_path: Path, line: str, count: int) -> None:
    text = divider(f"{line}\n", r1="1k tc1=0.01")
    points = op_steps(solver, tmp_path, text)
    assert len(points) == count
    assert points[-1]["v(out)"] == pytest.approx(1.0, rel=LINEAR)
    netlist(text)


# LT-OPT-001.


@pytest.mark.parametrize(
    "line", [".options reltol=1m", ".option abstol=1p", ".opt method=gear", ".options logparams"]
)
def test_options(solver: Solver, tmp_path: Path, line: str) -> None:
    assert runs(solver, tmp_path, divider(f"{line}\n")).voltage("out") == pytest.approx(1.5)


# LT-ICN-001.

_CHARGE = "probe\nV1 in 0 1\nR1 in out 1k\nC1 out 0 1u\n{}\n.tran 1m uic\n.end\n"


def test_ic_sets_a_node_voltage(solver: Solver, tmp_path: Path) -> None:
    rows = tran_rows(solver, tmp_path, _CHARGE.format(".ic V(out)=0.5"))
    assert rows[1]["v(out)"] == pytest.approx(0.5, rel=NONLINEAR)
    netlist(_CHARGE.format(".ic V(out)=0.5"))


def test_ic_sets_an_inductor_current(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nL1 out 0 1m\nR1 out 0 1\n.ic I(L1)=1\n.tran 1m uic\n.end\n"
    rows = tran_rows(solver, tmp_path, text)
    assert rows[1]["v(out)"] == pytest.approx(-1.0, rel=NONLINEAR)
    assert netlist(text).diagnostics == ()


def test_nodeset_runs(solver: Solver, tmp_path: Path) -> None:
    text = divider(".nodeset V(out)=1\n")
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(1.5)


@pytest.mark.parametrize("line", [".ic all=1", ".nodeset all=1"])
def test_all_stops_both(solver: Solver, tmp_path: Path, line: str) -> None:
    stops(solver, tmp_path, divider(f"{line}\n"), "syntax error")


# LT-SAV-001.


def test_save_limits_the_saved_data(solver: Solver, tmp_path: Path) -> None:
    result = runs(solver, tmp_path, divider(".save V(out)\n"))
    assert result.plot("Operating Point").variables == ("V(out)",)


@pytest.mark.parametrize(
    ("vectors", "names"),
    [
        ("I(R1)", {"I(R1)"}),
        ("I(R?)", {"I(R1)", "I(R2)"}),
        ("V(*)", {"V(in)", "V(out)"}),
        ("V(out) I(R1), V(in)", {"V(out)", "I(R1)", "V(in)"}),
    ],
)
def test_save_vectors(solver: Solver, tmp_path: Path, vectors: str, names: set[str]) -> None:
    result = runs(solver, tmp_path, divider(f".save {vectors}\n"))
    assert set(result.plot("Operating Point").variables) == names


def test_save_device_currents_and_differences_run(solver: Solver, tmp_path: Path) -> None:
    runs(solver, tmp_path, divider(".save Id(*) V(in,out)\n"))


@pytest.mark.parametrize("vector", ["out", "VM(out)"])
def test_malformed_save_stops_both(solver: Solver, tmp_path: Path, vector: str) -> None:
    stops(solver, tmp_path, divider(f".save {vector}\n"))


# LT-MEA-001.


@pytest.mark.parametrize(
    "line",
    [
        ".meas y param 1",
        ".measure y param 1",
        ".meas op y find V(out)",
        ".meas y find V(out)",
    ],
)
def test_measurements_run_at_the_operating_point(solver: Solver, tmp_path: Path, line: str) -> None:
    assert runs(solver, tmp_path, divider(f"{line}\n")).voltage("out") == pytest.approx(1.5)


@pytest.mark.parametrize("line", [".meas tran y max V(out)", ".meas y avg V(out)"])
def test_measurements_run_on_a_transient(solver: Solver, tmp_path: Path, line: str) -> None:
    text = f"probe\nV1 out 0 1\nR1 out 0 1k\n{line}\n.tran 1m\n.end\n"
    assert "y:" in runs(solver, tmp_path, text).log


def test_a_noise_measurement_runs(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nV1 in 0 1 AC 1\nR1 in out 1k\nR2 out 0 1k\n.noise V(out) V1 dec 1 1 10\n"
        ".meas noise y max V(onoise)\n.end\n"
    )
    assert run(solver, tmp_path, text).returncode == 0
    netlist(text)


# LT-GLB-001.


def test_a_global_node_joins_every_scope(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\n.global vcc\nV1 vcc 0 3\nX1 out s\nR2 out 0 1k\n.subckt s b\nR1 vcc b 1k\n.ends\n"
        ".op\n.end\n"
    )
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(1.5, rel=LINEAR)


# LT-NOD-001.


@pytest.mark.parametrize(
    "node",
    ["a/b", "n+1", "n-1", "a#b", "1n", "o[1]", "a%b", "a<b>", "a~b", "a\\b", "a//b", "x1:n", "a$b"],
)
def test_name_characters_run(solver: Solver, tmp_path: Path, node: str) -> None:
    text = f"probe\nV1 in 0 3\nR1 in {node} 1k\nR2 {node} 0 1k\n.op\n.end\n"
    plot = runs(solver, tmp_path, text).plot("Operating Point")
    assert plot.real(f"V({node})")[0] == pytest.approx(1.5, rel=LINEAR)
    assert len(netlist(text).nets()) == 3


@pytest.mark.parametrize(
    "node", ["a=b", "a(b", "a)b", "a,b", "a{b", "a}b", "a'b", 'a"b', "a|b", "a;b"]
)
def test_excluded_name_characters_stop_both(solver: Solver, tmp_path: Path, node: str) -> None:
    text = f"probe\nV1 in 0 3\nR1 in {node} 1k\nR2 {node} 0 1k\n.op\n.end\n"
    stops(solver, tmp_path, text)


@pytest.mark.parametrize("designator", ["R§1", "R[2]", "Rx%", "R$"])
def test_designators_use_the_same_characters(
    solver: Solver, tmp_path: Path, designator: str
) -> None:
    text = f"probe\nV1 in 0 3\n{designator} in out 1k\nR9 out 0 1k\n.op\n.end\n"
    assert runs(solver, tmp_path, text).voltage("out") == pytest.approx(1.5, rel=LINEAR)
