"""ngspice 47 probes for a number as a model name, and for `|` in names (M20 5.1 points 6 and 7).

Decision 0021 item 1, extended by decision 0024: a field the grammar reads as a number (digits,
then letters only: ``2``, ``4093``, ``1k``, ``4093B``) is never a model name, on every letter.
ngspice stops on a pure number in the model's place of a D or S line, reads it as the value
after an R, and runs a name such as ``4093B``, which the library refuses (its number reading is
wider than ngspice's model-name check). Each probe pairs what ngspice does with what the library
reads.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import Dialect, ParseError, SourceText, parse
from tests.support.ngspice import run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ngspice")

_BASE = "probe\nV1 in 0 1\nR9 in a 1k\nV2 c 0 1\n{model}{line}\n.op\n.end\n"


def _reading(text: str) -> str:
    """The model the library reads on the line under test (the last element), or ``refused``."""
    try:
        items = parse(SourceText(text), Dialect.NGSPICE).items
    except ParseError:
        return "refused"
    item = [item for item in items if hasattr(item, "designator")][-1]
    model = getattr(item, "model", None)
    if model is not None:
        return str(model.model_name)
    return str(getattr(item, "subckt").name)


# What ngspice says when it stops on a number in the model's place, by letter.
_STOPS = {
    "D": "could not find a valid modelname",
    "S": "unable to find definition of model",
    "W": "unable to find definition of model",
}

# (.model line, element line, ngspice runs it, the library's reading)
_PROBES = {
    "d-number": (".model 2 D\n", "D1 a 0 2", False, "refused"),
    "d-number-4093": (".model 4093 D\n", "D1 a 0 4093", False, "refused"),
    "d-number-scaled": (".model 1k D\n", "D1 a 0 1k", False, "refused"),
    "d-number-exponent": (".model 1e3 D\n", "D1 a 0 1e3", False, "refused"),
    # ngspice runs these as names; the library reads them as numbers (digits, then letters).
    "d-number-letters": (".model 4093B D\n", "D1 a 0 4093B", True, "refused"),
    "d-number-unit": (".model 1kohm D\n", "D1 a 0 1kohm", True, "refused"),
    "d-part-1n4148": (".model 1n4148 D\n", "D1 a 0 1n4148", True, "1n4148"),
    "d-part-1N4148_OJ": (".model 1N4148_OJ D\n", "D1 a 0 1N4148_OJ", True, "1N4148_OJ"),
    "d-part-CD4093": (".model CD4093 D\n", "D1 a 0 CD4093", True, "CD4093"),
    "d-part-74HC00": (".model 74HC00 D\n", "D1 a 0 74HC00", True, "74HC00"),
    "d-part-4N25": (".model 4N25 D\n", "D1 a 0 4N25", True, "4N25"),
    "s-number": (".model 2 SW\n", "S1 a 0 c 0 2", False, "refused"),
    "s-part": (".model 2N2 SW\n", "S1 a 0 c 0 2N2", True, "2N2"),
    "w-number": (".model 2 CSW\n", "W1 a 0 V2 2", False, "refused"),
    "r-number-after-value": (".model 2 R\n", "R1 a 0 1k 2", True, "refused"),
    "r-4093-after-value": (".model 4093 R\n", "R1 a 0 1k 4093", True, "refused"),
    "r-part-after-value": (".model 2N2 R\n", "R1 a 0 1k 2N2", True, "2N2"),
    "c-number-after-value": (".model 2p C\n", "C1 a 0 1p 2p", True, "refused"),
    "l-number-after-value": (".model 2 L\n", "L1 a 0 1u 2", True, "refused"),
    "x-number-subcircuit": (".subckt 4093 p\nR1 p 0 1k\n.ends\n", "X1 a 4093", True, "4093"),
}


@pytest.mark.parametrize("case", sorted(_PROBES))
def test_number_model_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    model, line, ngspice_runs, reading = _PROBES[case]
    text = _BASE.format(model=model, line=line)
    result = run(solver, tmp_path, text)
    assert result.ok is ngspice_runs, result.log
    if not ngspice_runs:
        assert _STOPS[line[0]] in result.log.lower(), result.log
    assert _reading(text) == reading


@pytest.mark.parametrize(
    ("model", "line", "parameter", "value"),
    [
        (".model 2 R", "R1 a 0 1k 2", "resistance", 2.0),
        (".model 4093 R", "R1 a 0 1k 4093", "resistance", 4093.0),
        (".model 2p C", "C1 a 0 1p 2p", "capacitance", 2e-12),
    ],
)
def test_a_number_after_a_value_is_the_value(
    solver: Solver, tmp_path: Path, model: str, line: str, parameter: str, value: float
) -> None:
    # ngspice reads R1 a 0 1k 4093 as a 4093 ohm resistor, not as a model 4093: the library
    # refuses the line rather than misreading it (decision 0024).
    designator = line.split()[0].lower()
    text = f"probe\nV1 a 0 1\n{model}\n{line}\n.save all @{designator}[{parameter}]\n.op\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert result.device(designator, parameter) == pytest.approx(value)
    assert _reading(text) == "refused"


def test_a_bar_in_a_node_and_a_model_name_runs_and_loads(solver: Solver, tmp_path: Path) -> None:
    # The manual's excluded characters do not include `|`, and ngspice 47 runs it (M20 5.1
    # point 7; NG-NOD-001).
    text = (
        "probe\nV1 a|b 0 1\nR1 a|b k 1k\n.model d|x D(IS=1e-14)\nD1 k 0 d|x\n"
        ".save all @r1[resistance]\n.op\n.end\n"
    )
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert 0.0 < result.voltage("k") < 1.0
    items = parse(SourceText(text), Dialect.NGSPICE).items
    assert [node.name for node in getattr(items[1], "nodes")] == ["a|b", "0"]
    assert [node.name for node in getattr(items[2], "nodes")] == ["a|b", "k"]
    assert getattr(items[4], "model").model_name == "d|x"
