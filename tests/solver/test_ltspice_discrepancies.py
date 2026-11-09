"""LTspice 26.1.1 probes for the rows of ``discrepancies.md`` (M8 T12, T8 tier; decision 0009).

Each test pairs what LTspice does with what the library does, for a form on which the two differ.
``test_every_reject_fixture_is_classified`` sweeps the ``*_rejects`` families. Only syntax facts
come out of these runs; nothing LTspice writes is committed (decision 0009 item 2).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from netlistmod import (
    DiagnosticCode,
    Dialect,
    Netlist,
    ParseError,
    SourceText,
    UnsupportedConstruct,
    parse,
)
from tests.support.ltspice import run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ltspice")

CORPUS = Path(__file__).parents[1] / "corpus" / "ltspice"
LINEAR = 1e-6


def divider(extra: str = "", *, r1: str = "1k", r2: str = "1k") -> str:
    return f"probe\nV1 in 0 3\nR1 in out {r1}\nR2 out 0 {r2}\n{extra}.op\n.end\n"


def netlist(text: str) -> Netlist:
    return Netlist.from_text(text, dialect=Dialect.LTSPICE)


def only_ltspice_runs(solver: Solver, folder: Path, text: str) -> None:
    result = run(solver, folder, text)
    assert result.returncode == 0, result.log
    with pytest.raises((ParseError, UnsupportedConstruct)):
        parse(SourceText(text), Dialect.LTSPICE)


def only_the_library_accepts(solver: Solver, folder: Path, text: str, message: str = "") -> None:
    result = run(solver, folder, text)
    assert result.returncode != 0, result.log
    assert message in result.log, result.log
    netlist(text)


# Exceptions to the reference.


@pytest.mark.parametrize(
    "text",
    [
        "probe\nV1 in 0 3\nR1 in 0 1k\n.op\n",
        "probe\nV1 in 0 3\nR1 in 0 1k\n.op\n.end\nthis text is ignored\n",
    ],
)
def test_end_may_be_omitted_and_text_after_it_is_ignored(
    solver: Solver, tmp_path: Path, text: str
) -> None:
    only_ltspice_runs(solver, tmp_path, text)


def test_an_expression_for_a_node_runs_but_the_library_rejects_it(
    solver: Solver, tmp_path: Path
) -> None:
    only_ltspice_runs(
        solver, tmp_path, 'probe\n.param n="out"\nV1 in 0 3\nR1 in {n} 1k\nR2 out 0 1k\n.op\n.end\n'
    )


@pytest.mark.parametrize(
    "line",
    [".step param x list 1,2\n", ".step param x list 1, 2\n"],
)
def test_comma_lists_in_step_run_but_the_library_rejects_them(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    only_ltspice_runs(solver, tmp_path, divider(line, r2="{x}"))


def test_comma_lists_in_dc_and_ac_run_but_the_library_rejects_them(
    solver: Solver, tmp_path: Path
) -> None:
    source = "probe\nV1 in 0 1 AC 1\nR1 in 0 1k\n{}\n.end\n"
    only_ltspice_runs(solver, tmp_path / "dc", source.format(".dc V1 list 1,2"))
    only_ltspice_runs(solver, tmp_path / "ac", source.format(".ac list 1,2"))


# Forms LTspice runs and the library rejects.


@pytest.mark.parametrize(
    "lines", ["R2 out\n* a comment\n+ 0 1k\n", "R2 out\n\n+ 0 1k\n", "R2 out\n; c\n\n+ 0 1k\n"]
)
def test_a_continuation_across_other_lines_runs_but_the_library_rejects_it(
    solver: Solver, tmp_path: Path, lines: str
) -> None:
    text = divider().replace("R2 out 0 1k\n", lines)
    only_ltspice_runs(solver, tmp_path, text)
    assert run(solver, tmp_path, text).voltage("out") == pytest.approx(1.5, rel=LINEAR)


@pytest.mark.parametrize(
    "line",
    [
        ".print dc V(out)",
        ".plot dc V(out)",
        ".width out=80",
        ".opti reltol=1m",
        ".options",
        ".ic",
        ".nodeset",
        ".save",
        ".global",
        ".meas op",
        ".meas op y",
        ".meas tran",
        ".save dialogbox",
    ],
)
def test_undocumented_commands_run_but_the_library_rejects_them(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    only_ltspice_runs(solver, tmp_path, divider(f"{line}\n"))


@pytest.mark.parametrize(
    "line", [".ic I(R1)=1", ".nodeset I(R1)=1", ".ic V(in,out)=1", ".nodeset V(in,out)=1"]
)
def test_other_initial_conditions_run_but_the_library_rejects_them(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    only_ltspice_runs(solver, tmp_path, divider(f"{line}\n"))


def test_an_ic_current_on_a_resistor_is_ignored(solver: Solver, tmp_path: Path) -> None:
    text = divider(".ic I(R1)=1\n")
    assert run(solver, tmp_path, text).voltage("out") == pytest.approx(1.5, rel=LINEAR)


def test_an_ic_current_of_no_element_runs_and_is_diagnosed(solver: Solver, tmp_path: Path) -> None:
    text = divider(".ic I(L9)=1\n")
    assert run(solver, tmp_path, text).voltage("out") == pytest.approx(1.5, rel=LINEAR)
    assert [d.code for d in netlist(text).diagnostics] == [DiagnosticCode.UNRESOLVED_ELEMENT]


def test_an_ic_current_inside_an_instance_is_set_but_the_library_rejects_it(
    solver: Solver, tmp_path: Path
) -> None:
    text = (
        "probe\nX1 out s\nR1 out 0 1\n.subckt s a\nL1 a 0 1m\n.ends\n.ic I(x1:L1)=1\n"
        ".tran 1m uic\n.end\n"
    )
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert abs(result.plot("Transient").real("V(out)")[1]) == pytest.approx(1.0, rel=1e-3)
    with pytest.raises(ParseError):
        parse(SourceText(text), Dialect.LTSPICE)


@pytest.mark.parametrize("line", [".ic V(a)=1", ".nodeset V(a)=1"])
def test_conditions_in_a_body_run_but_the_library_rejects_them(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    text = divider(f"X1 in 0 s\n.subckt s a b\n{line}\nR1 a b 1k\n.ends\n")
    only_ltspice_runs(solver, tmp_path, text)


@pytest.mark.parametrize(
    ("value", "reads"),
    [
        ("1k$c", 1e3),
        ("2.2k2", 2.4e3),
        ("1.5k5", 2e3),
        ("1e3k2", 1.0002e6),
        ("1x5", 1.0),
        ("1a5", 1.0),
        ("1l5", 1.0),
        ("1kohm5", 1e3),
        ("1V5", 1.0),
    ],
)
def test_other_digits_after_letters_read_oddly_and_the_library_rejects_them(
    solver: Solver, tmp_path: Path, value: str, reads: float
) -> None:
    text = f"probe\nI1 0 a 1\nR1 a 0 {value}\n.op\n.end\n"
    assert run(solver, tmp_path, text).voltage("a") == pytest.approx(reads, rel=LINEAR)
    with pytest.raises(ParseError):
        parse(SourceText(text), Dialect.LTSPICE)


@pytest.mark.parametrize(
    "line",
    [
        "C9 out 0 1n tc=1m\n",
        "V9 a 0 1 m=2\nR9 a 0 1k\n",
        "D9 out 0 dm ic=1\n.model dm D\n",
        "R9 out 0 1k mfg='abc'\n",
        "R9 out 0 1k mfg={abc}\n",
        ".model dm D(mfg='abc')\n",
        ".model dm D(mfg={abc})\n",
    ],
)
def test_names_outside_the_closed_lists_run_but_the_library_rejects_them(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    only_ltspice_runs(solver, tmp_path, divider(line))


def test_a_bare_word_for_a_flag_is_a_parameter_reference(solver: Solver, tmp_path: Path) -> None:
    text = divider(".param x=1\n", r2="1k noiseless=x")
    only_ltspice_runs(solver, tmp_path / "defined", text)
    assert run(solver, tmp_path / "undefined", divider(r2="1k noiseless=x")).returncode != 0


def test_mfg_in_braces_is_not_evaluated(solver: Solver, tmp_path: Path) -> None:
    assert run(solver, tmp_path, divider("R9 out 0 1G mfg={1+}\n")).returncode == 0


@pytest.mark.parametrize("element", ["R9 out 0 R=1k", "L9 out a inductance=1m\nR9 a 0 1k"])
def test_keyword_values_run_but_the_library_rejects_them(
    solver: Solver, tmp_path: Path, element: str
) -> None:
    only_ltspice_runs(solver, tmp_path, divider(f"{element}\n"))


@pytest.mark.parametrize("element", ["R9 out 0 resistance=1k", "C9 out 0 C=1n", "L9 out 0 L=1m"])
def test_other_keyword_values_stop_both(solver: Solver, tmp_path: Path, element: str) -> None:
    text = divider(f"{element}\n")
    assert not run(solver, tmp_path, text).ok
    with pytest.raises((ParseError, UnsupportedConstruct)):
        parse(SourceText(text), Dialect.LTSPICE)


@pytest.mark.parametrize(
    ("r2", "line", "out"),
    [
        ("R=x*3", ".param x=1k\n", 2.25),  # 3k
        ("1k m=x", ".param x=2\n", 1.0),  # 500
    ],
)
def test_bare_expressions_are_read_as_references_but_the_library_rejects_them(
    solver: Solver, tmp_path: Path, r2: str, line: str, out: float
) -> None:
    text = divider(line, r2=r2)
    assert run(solver, tmp_path, text).voltage("out") == pytest.approx(out, rel=LINEAR)
    with pytest.raises(ParseError):
        parse(SourceText(text), Dialect.LTSPICE)


@pytest.mark.parametrize(
    "lines",
    [
        "X1 in out s r=2*1k\n.subckt s a b r=1k\nR1 a b 1k\nR2 b 0 {r}\n.ends\n",
        "X1 in out s\n.subckt s a b r=2*1k\nR1 a b 1k\nR2 b 0 {r}\n.ends\n",
    ],
)
def test_bare_expressions_on_subcircuits_run_but_the_library_rejects_them(
    solver: Solver, tmp_path: Path, lines: str
) -> None:
    text = f"probe\nV1 in 0 3\n{lines}.op\n.end\n"
    assert run(solver, tmp_path, text).voltage("out") == pytest.approx(2.0, rel=LINEAR)
    with pytest.raises(ParseError):
        parse(SourceText(text), Dialect.LTSPICE)


@pytest.mark.parametrize(
    ("parameters", "stopped"),
    [
        ("Is=x", False),
        ("Is=x*1n", False),
        ("Is=1n*2", False),
        ("Is=abc", True),
    ],
)
def test_a_bare_word_in_a_model_is_a_parameter_reference_in_ltspice(
    solver: Solver, tmp_path: Path, parameters: str, stopped: bool
) -> None:
    text = f"probe\n.param x=1\nI1 0 a 1m\nD1 a 0 dm\n.model dm D({parameters})\n.op\n.end\n"
    result = run(solver, tmp_path, text)
    assert (result.returncode != 0) == stopped, result.log
    with pytest.raises(ParseError, match="parameter reference"):
        parse(SourceText(text), Dialect.LTSPICE)


@pytest.mark.parametrize(
    "source",
    ["V1 in 0 DC=3", "V1 in 0 AC 1 DC 3", "V1 in 0 3 Rser=1 AC 1", "I1 0 in 1m load AC 1"],
)
def test_other_source_orders_run_but_the_library_rejects_them(
    solver: Solver, tmp_path: Path, source: str
) -> None:
    only_ltspice_runs(solver, tmp_path, f"probe\n{source}\nR1 in 0 1k\n.op\n.end\n")


@pytest.mark.parametrize("params", ["tc=1m 1u", "m=2, temp=30"])
def test_other_resistor_lists_run_but_the_library_rejects_them(
    solver: Solver, tmp_path: Path, params: str
) -> None:
    only_ltspice_runs(solver, tmp_path, divider(r2=f"1k {params}"))


def test_other_commas_run_but_the_library_rejects_them(solver: Solver, tmp_path: Path) -> None:
    only_ltspice_runs(solver, tmp_path / "ac", "probe\nV1 a 0 0 AC 1, 2\nR1 a 0 1k\n.op\n.end\n")
    only_ltspice_runs(
        solver,
        tmp_path / "ports",
        "probe\nV1 in 0 3\nX1 in 0 s\n.subckt s a,b\nR1 a b 1k\n.ends\n.op\n.end\n",
    )


@pytest.mark.parametrize("line", [".dc V1 list 1 2 V2 1 2 1", ".dc V1 0 1", ".dc V1 0 1 V2 0 1 1"])
def test_other_dc_forms_run_but_the_library_rejects_them(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    text = f"probe\nV1 a 0 1\nV2 b 0 1\nR1 a 0 1k\nR2 b 0 1k\n{line}\n.end\n"
    only_ltspice_runs(solver, tmp_path, text)


def test_a_step_without_an_increment_runs_but_the_library_rejects_it(
    solver: Solver, tmp_path: Path
) -> None:
    only_ltspice_runs(solver, tmp_path, divider(".step param x 1k 2k\n", r2="{x}"))


@pytest.mark.parametrize(
    "text",
    [
        divider(".param x=1k\n", r2="{{x}}"),
        divider(".param a$b=1k\n", r2="{a$b}"),
    ],
)
def test_nested_braces_and_a_dollar_in_a_param_run_but_the_library_rejects_them(
    solver: Solver, tmp_path: Path, text: str
) -> None:
    only_ltspice_runs(solver, tmp_path, text)


def test_a_port_named_0_runs_but_the_library_rejects_it(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nV1 in 0 3\nX1 in s\n.subckt s 0\nR1 0 a 1k\n.ends\n.op\n.end\n"
    only_ltspice_runs(solver, tmp_path, text)


def test_encodings_ltspice_reads_by_itself(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nI1 0 a 1\nR1 a 0 2µ\n.op\n.end\n"
    bomless = text.encode("utf-16-le")
    assert run(solver, tmp_path / "utf16", bomless).voltage("a") == pytest.approx(2e-6, rel=LINEAR)
    named = SourceText(bomless.decode("utf-16-le"), encoding="utf-16-le")
    assert parse(named, Dialect.LTSPICE).dialect is Dialect.LTSPICE
    with pytest.raises(ParseError):
        parse(SourceText.from_bytes(bomless), Dialect.LTSPICE)
    latin = text.encode("latin-1")
    assert run(solver, tmp_path / "latin", latin).voltage("a") == pytest.approx(2e-6, rel=LINEAR)


# Forms the library accepts and LTspice rejects.


def test_an_unknown_option_stops_ltspice_only(solver: Solver, tmp_path: Path) -> None:
    only_the_library_accepts(solver, tmp_path, divider(".options foo=1\n"))


def test_big_endian_utf16_stops_ltspice_only(solver: Solver, tmp_path: Path) -> None:
    data = "﻿probe\nV1 in 0 3\nR1 in 0 1k\n.op\n.end\n".encode("utf-16-be")
    assert run(solver, tmp_path, data).returncode != 0
    Netlist.from_text(SourceText.from_bytes(data).text, dialect=Dialect.LTSPICE)


@pytest.mark.parametrize(
    ("analysis", "message"),
    [(".step x 1 2 1\n.op", "Can't sweep that"), (".dc R1 1 2 1", "")],
)
def test_a_sweep_of_something_else_stops_ltspice_only(
    solver: Solver, tmp_path: Path, analysis: str, message: str
) -> None:
    text = f"probe\nV1 in 0 3\nR1 in 0 1k\n{analysis}\n.end\n"
    only_the_library_accepts(solver, tmp_path, text, message)


def test_a_measurement_ltspice_cannot_read_stops_ltspice_only(
    solver: Solver, tmp_path: Path
) -> None:
    only_the_library_accepts(solver, tmp_path, divider(".meas sp y param 1\n"))


@pytest.mark.parametrize(
    ("line", "message"),
    [
        (".loadstate nosuch.st", "syntax error"),
        ('.loadstate "nosuch.st"', "does not exist"),
        (".fra dec 10 1 1k", "syntax error"),
        (".fra foo=1", "syntax error"),
    ],
)
def test_untyped_arguments_ltspice_stops_at_are_kept_as_text(
    solver: Solver, tmp_path: Path, line: str, message: str
) -> None:
    only_the_library_accepts(solver, tmp_path, divider(f"{line}\n"), message)


def test_steady_without_a_steady_state_stops_ltspice_only(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nV1 in 0 1\nR1 in 0 1k\n.tran 1m steady\n.end\n"
    assert "Don't know how to detect" in run(solver, tmp_path, text).log
    netlist(text)


@pytest.mark.parametrize(
    "lines",
    ["L1 a 0 1m\nL2 a 0 1m\nL3 a 0 1m\n", "L1 a b 1m\nL2 b c 1m\nL3 c 0 1m\n"],
)
def test_an_inductor_loop_stops_ltspice_without_an_error_line(
    solver: Solver, tmp_path: Path, lines: str
) -> None:
    # The likely cause of probe L13 (an inference; L13's circuit is not recorded).
    text = f"probe\nV1 a 0 0 AC 1\n{lines}K1 L1 L2 L3 0.5\n.ac list 1k\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.returncode != 0 and not result.errors, result.log
    assert "over-defined circuit matrix" in result.log
    netlist(text)


# Every reject fixture, with a load, a model and an analysis added so that only the fixture's own
# construct can stop LTspice.

_ADDED = (
    b"V99 n99 0 1\nR99 n99 0 1\nR98 a 0 1\nR97 b 0 1\n.model dm D\n.model npn NPN\n"
    b".param x=1 name=1\n.op\n"
)
LTSPICE_RUNS = {
    # Unsupported in phase 1.
    "elements_rejects/phase_2_letter.cir",
    "statements_rejects/machine_block.cir",
    # Rows of discrepancies.md.
    "elements_rejects/resistor_keyword_value.cir",
    "elements_rejects/source_after_ac.cir",
    "elements_rejects/s_on_off.cir",
    "elements_rejects/e_table_braces.cir",
    "elements_rejects/e_poly_dimension.cir",
    "elements_rejects/b_laplace_resistor.cir",
    "elements_rejects/f_value_source.cir",
    "statements_rejects/ic_resistor_current.cir",
    "statements_rejects/meas_sp_body.cir",
    "statements_rejects/model_bare_expression.cir",
    "statements_rejects/model_bare_parameter.cir",
    "statements_rejects/nodeset_current.cir",
    "statements_rejects/text_after_end.cir",
    "elements_rejects/flag_with_a_word.cir",
}
_REJECTS = sorted(
    path
    for family in ("elements_rejects", "statements_rejects", "names_rejects")
    for path in (CORPUS / family).glob("*.cir")
)


def _key(path: Path) -> str:
    return f"{path.parent.name}/{path.name}"


@pytest.mark.parametrize("path", _REJECTS, ids=_key)
def test_every_reject_fixture_is_classified(solver: Solver, tmp_path: Path, path: Path) -> None:
    data = path.read_bytes()
    title = data.index(b"\n") + 1
    result = run(solver, tmp_path, data[:title] + _ADDED + data[title:])
    assert (result.returncode == 0) == (_key(path) in LTSPICE_RUNS), result.log
    manifest = json.loads((path.parent / "manifest.json").read_text(encoding="utf-8"))
    error = {"ParseError": ParseError, "UnsupportedConstruct": UnsupportedConstruct}
    with pytest.raises(error[manifest["fixtures"][path.name]["error"]]):
        parse(SourceText(data.decode("utf-8")), Dialect.LTSPICE)
