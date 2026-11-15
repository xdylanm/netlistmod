"""LTspice 26.1.1 probes for a number as a model name (M20 5.1 point 6).

Decision 0021 item 1, extended by decision 0024: a field the grammar reads as a number (digits,
then letters only: ``2``, ``4093``, ``1k``, ``4093B``) is never a model name, on every letter.
LTspice runs such a name on D, S and W, as it runs ``Q1 c b e 2``; the library refuses it, which
is stricter than the reference ("any string without blanks") and the solver. Each probe pairs
what LTspice does with what the library reads. Nothing LTspice writes is committed (decision
0009 item 2).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import Dialect, ParseError, SourceText, parse
from tests.support.ltspice import run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ltspice")

_BASE = "probe\nV1 in 0 1\nR9 in a 1k\nV2 c 0 1\n{model}{line}\n.op\n.end\n"


def _reading(text: str) -> str:
    """The model the library reads on the line under test (the last element), or ``refused``."""
    try:
        items = parse(SourceText(text), Dialect.LTSPICE).items
    except ParseError:
        return "refused"
    item = [item for item in items if hasattr(item, "designator")][-1]
    model = getattr(item, "model", None)
    if model is not None:
        return str(model.model_name)
    return str(getattr(item, "subckt").name)


# (.model line, element line, LTspice runs it, the library's reading)
_PROBES = {
    "d-number": (".model 2 D\n", "D1 a 0 2", True, "refused"),
    "d-number-4093": (".model 4093 D\n", "D1 a 0 4093", True, "refused"),
    "d-number-letters": (".model 4093B D\n", "D1 a 0 4093B", True, "refused"),
    "d-part-1n4148": (".model 1n4148 D\n", "D1 a 0 1n4148", True, "1n4148"),
    "d-part-1N4148_OJ": (".model 1N4148_OJ D\n", "D1 a 0 1N4148_OJ", True, "1N4148_OJ"),
    "d-part-CD4093": (".model CD4093 D\n", "D1 a 0 CD4093", True, "CD4093"),
    "d-part-74HC00": (".model 74HC00 D\n", "D1 a 0 74HC00", True, "74HC00"),
    "d-part-4N25": (".model 4N25 D\n", "D1 a 0 4N25", True, "4N25"),
    "s-number": (".model 2 SW\n", "S1 a 0 c 0 2", True, "refused"),
    "s-part": (".model 2N2 SW\n", "S1 a 0 c 0 2N2", True, "2N2"),
    "w-number": (".model 2 CSW\n", "W1 a 0 V2 2", True, "refused"),
    "x-number-subcircuit": (".subckt 4093 p\nR1 p 0 1k\n.ends\n", "X1 a 4093", True, "4093"),
}


@pytest.mark.parametrize("case", sorted(_PROBES))
def test_number_model_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    model, line, ltspice_runs, reading = _PROBES[case]
    text = _BASE.format(model=model, line=line)
    result = run(solver, tmp_path, text)
    assert result.ok is ltspice_runs, result.log
    assert _reading(text) == reading
