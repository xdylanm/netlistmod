"""ngspice 47 probes for statements and directives (M4, T8 tier).

Each probe pairs what ngspice does with what the library does. Unless noted, the circuit is a
divider, ``V1 in 0 DC 3`` with two 1k resistors, and the result is ``v(out)`` of the ``.op``
read from the raw file (``tests/support/ngspice.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import (
    Dialect,
    IcDirective,
    ModelStatement,
    OptionsDirective,
    ParseError,
    SaveDirective,
    SourceText,
    SubcktDefinition,
    UnknownDirective,
    UnsupportedConstruct,
    parse,
)
from tests.support.ngspice import run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ngspice")

CORPUS = Path(__file__).parents[1] / "corpus" / "ngspice" / "statements_basic"

_DIVIDER = "probe\nV1 in 0 DC 3\nR1 in out 1k\n{r2}\n{extra}.op\n.end\n"


def _divider(extra: str = "", r2: str = "R2 out 0 1k") -> str:
    return _DIVIDER.format(r2=r2, extra=extra)


def _parses(text: str) -> bool:
    try:
        parse(SourceText(text), Dialect.NGSPICE)
    except (ParseError, UnsupportedConstruct):
        return False
    return True


def test_divider_harness_gives_the_closed_form_result(solver: Solver, tmp_path: Path) -> None:
    result = run(solver, tmp_path, _divider())
    assert result.returncode == 0, result.log
    assert result.voltage("out") == pytest.approx(1.5)
    assert _parses(_divider())


@pytest.mark.parametrize(
    ("extra", "accepted_by_library"),
    [
        # Decision 2: analyses may not stand in a subcircuit body (§2.6.1 "control lines").
        (".subckt div a b\nR1 a b 1k\n.tran 1u 10u\n.ends\n", False),
        (".subckt div a b\nR1 a b 1k\n.op\n.ends\n", False),
        # Decision 3: ports cannot be 0 (§2.6.1).
        (".subckt div a 0\nR1 a 0 1k\n.ends\n", False),
        # Decision 4: bare expressions in .param (§2.11.1 recommends braces).
        (".param a=1k\n.param c = a\n", False),
        # Settled in M4: §2.14 shows one value, §2.11.1 reserves time, temper and hertz and
        # requires a letter first, §11.1 shows at least one option, §11.3.5 takes no argument,
        # §11.6.1 at least one vector, §11.4 a measurement after the result name, §2.5 a value
        # for every model parameter, and §11.2.1 has v(...) items or all= but not both.
        (".temp 27 30\n", False),
        (".param time=1\n", False),
        (".param 1a=2\n", False),
        (".options\n", False),
        (".op 1\n", False),
        (".save\n", False),
        (".meas tran x\n", False),
        (".model x D bf\n", False),
        (".nodeset v(out)=1 all=2\n", False),
        # Accepted by both.
        (".subckt d a a\nR1 a 0 1k\n.ends\n", True),
        (".model dm D()\n", True),
        (".subckt div a b\nR1 a b 1k\n.ends other\n", True),
    ],
)
def test_solver_runs_these_and_the_library_follows_the_manual(
    solver: Solver, tmp_path: Path, extra: str, accepted_by_library: bool
) -> None:
    text = _divider(extra)
    result = run(solver, tmp_path, text)
    assert result.returncode == 0, result.log
    assert result.voltage("out") == pytest.approx(1.5)
    assert _parses(text) is accepted_by_library


@pytest.mark.parametrize(
    "extra",
    [
        ".ends\n",
        ".ic all=1\n",
        ".tran 1n 1u 0 1n 1n\n",
        ".ac log 10 1 1k\n",
        ".dc V1 0 1\n",
        ".param a=1k\n.param c = a + 1k\n",
    ],
)
def test_solver_and_library_both_reject(solver: Solver, tmp_path: Path, extra: str) -> None:
    text = _divider(extra)
    result = run(solver, tmp_path, text)
    assert result.returncode != 0
    assert not _parses(text)


@pytest.mark.parametrize(
    ("extra", "r2", "expected"),
    [
        # §2.11.1 notes ngspice reads a blank-free bare expression; the library rejects it.
        (".param a=1k\n.param c = a+1k\n", "R2 out 0 {c}", 2.0),
        (".param a=1k\n.param c = {a+1k}\n", "R2 out 0 {c}", 2.0),
        (".param a=1k\n.param c = 'a+1k'\n", "R2 out 0 {c}", 2.0),
    ],
)
def test_param_values_reach_the_element(
    solver: Solver, tmp_path: Path, extra: str, r2: str, expected: float
) -> None:
    text = _divider(extra, r2)
    result = run(solver, tmp_path, text)
    assert result.returncode == 0, result.log
    assert result.voltage("out") == pytest.approx(expected)
    assert _parses(text) is ("a+1k\n" not in extra)


def test_changing_a_param_value_moves_the_result(solver: Solver, tmp_path: Path) -> None:
    results = []
    for value in ("1k", "3k"):
        text = _divider(f".param rb={value}\n", "R2 out 0 {rb}")
        item = parse(SourceText(text), Dialect.NGSPICE).items[3]
        result = run(solver, tmp_path, text)
        assert result.returncode == 0, result.log
        results.append(result.voltage("out"))
        assert item.span.start < item.span.end
    assert results == [pytest.approx(1.5), pytest.approx(2.25)]


def test_subcircuit_default_and_instance_override(solver: Solver, tmp_path: Path) -> None:
    definition = ".subckt div a b r2=1k\nR1 a b 1k\nR2 b 0 {r2}\n.ends div\n"
    results = []
    for call in ("X1 in out div", "X1 in out div r2=3k"):
        text = f"probe\nV1 in 0 DC 3\n{definition}{call}\n.op\n.end\n"
        result = run(solver, tmp_path, text)
        assert result.returncode == 0, result.log
        results.append(result.voltage("out"))
        definitions = [
            item
            for item in parse(SourceText(text), Dialect.NGSPICE).items
            if isinstance(item, SubcktDefinition)
        ]
        assert [d.params[0].value.text for d in definitions] == ["1k"]
    assert results == [pytest.approx(1.5), pytest.approx(2.25)]


def test_nested_subcircuit_definition_runs(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nV1 in 0 DC 3\n"
        ".subckt outer a b\n.subckt inner p q\nR1 p q 1k\n.ends inner\n"
        "X1 a b inner\nR2 b 0 1k\n.ends outer\n"
        "X1 in out outer\n.op\n.end\n"
    )
    result = run(solver, tmp_path, text)
    assert result.returncode == 0, result.log
    assert result.voltage("out") == pytest.approx(1.5)
    outer = parse(SourceText(text), Dialect.NGSPICE).items[2]
    assert isinstance(outer, SubcktDefinition)
    assert isinstance(outer.body[0], SubcktDefinition)


@pytest.mark.parametrize(
    "model",
    [
        ".model dm D is=1e-14, n=1.5\n",
        ".model dm D(is=1e-14\n+ n=1.5)\n",
        ".model dm D (is=1e-14 n=1.5)\n",
    ],
)
def test_model_forms_run_alike(solver: Solver, tmp_path: Path, model: str) -> None:
    text = f"probe\nV1 in 0 DC 3\nR1 in out 1k\nD1 out 0 dm\n{model}.op\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.returncode == 0, result.log
    # The same diode with defaults (is=1e-14, n=1) is the reference: n=1.5 raises v(out).
    reference = run(solver, tmp_path, text.replace(model, ".model dm D is=1e-14\n"))
    assert reference.returncode == 0, reference.log
    assert result.voltage("out") > reference.voltage("out")
    statement = parse(SourceText(text), Dialect.NGSPICE).items[4]
    assert isinstance(statement, ModelStatement)
    assert [(p.name, p.value.text) for p in statement.params] == [("is", "1e-14"), ("n", "1.5")]


def test_model_inside_subcircuit_is_local(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nV1 in 0 DC 3\nR1 in out 1k\nD1 out 0 dm\n"
        ".subckt holder a\n.model dm D\nR1 a 0 1k\n.ends\n.op\n.end\n"
    )
    result = run(solver, tmp_path, text)
    assert result.returncode != 0
    # Accepted as syntax; model scoping is resolved in M5 (§2.6.1: models are local).
    assert _parses(text)


@pytest.mark.parametrize(
    ("option", "kind"),
    [(".option reltol=1e-3", OptionsDirective), (".opt gmin=1e-12", UnknownDirective)],
)
def test_option_spellings(solver: Solver, tmp_path: Path, option: str, kind: type) -> None:
    text = _divider(option + "\n")
    result = run(solver, tmp_path, text)
    assert result.returncode == 0, result.log
    assert result.voltage("out") == pytest.approx(1.5)
    assert isinstance(parse(SourceText(text), Dialect.NGSPICE).items[4], kind)


def test_initial_condition_with_blanks_inside_v(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nV1 in 0 DC 3\nR1 in out 1k\nC1 out 0 1u\n"
        ".ic v( out )=2\n.tran 1u 2u 0 1u uic\n.print tran v(out)\n.end\n"
    )
    result = run(solver, tmp_path, text)
    assert result.returncode == 0, result.log
    assert result.plot("Transient").real("v(out)")[0] == pytest.approx(2.0)
    directive = parse(SourceText(text), Dialect.NGSPICE).items[4]
    assert isinstance(directive, IcDirective)
    assert directive.conditions[0].node is not None
    assert directive.conditions[0].node.name == "out"


@pytest.mark.parametrize(
    ("argument", "variables", "function", "nodes"),
    [
        ("vm(out)", ["v(out)"], "vm", ["out"]),
        ("vdb(out)", ["v(out)"], "vdb", ["out"]),
        ("v(in, out)", ["v(in)", "v(out)"], "v", ["in", "out"]),
        ("v( out )", ["v(out)"], "v", ["out"]),
        ("i(V1)", ["i(v1)"], "i", []),
    ],
)
def test_save_vector_forms_and_the_stored_variables(
    solver: Solver,
    tmp_path: Path,
    argument: str,
    variables: list[str],
    function: str,
    nodes: list[str],
) -> None:
    # ngspice stores the plain voltages: v(a, b) as v(a) and v(b), vm and vdb as v. The library
    # records the vector as written (decision 0005; discrepancies.md).
    text = (
        "probe\nV1 in 0 DC 1 AC 1\nR1 in out 1k\nC1 out 0 1u\n"
        f".ac dec 2 1 1k\n.save {argument}\n.end\n"
    )
    result = run(solver, tmp_path, text)
    assert result.returncode == 0, result.log
    assert [v for v in result.plot("AC").variables if v != "frequency"] == variables
    directive = parse(SourceText(text), Dialect.NGSPICE).items[5]
    assert isinstance(directive, SaveDirective)
    vector = directive.vectors[0]
    assert (vector.text, vector.function) == (argument, function)
    assert [node.name for node in vector.nodes] == nodes


@pytest.mark.parametrize("path", sorted(CORPUS.glob("*.cir")), ids=lambda path: path.name)
def test_accept_corpus_runs_in_ngspice(solver: Solver, tmp_path: Path, path: Path) -> None:
    result = run(solver, tmp_path, path.read_bytes().decode("utf-8"))
    assert result.returncode == 0, result.log
    assert "Error" not in result.log, result.log
