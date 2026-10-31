"""Allowed edits keep their meaning in ngspice 47 (M7 T7, T8 tier; decision 0008 item 5).

Hypothesis generates sequences of ``set_value`` and ``params.set`` edits on a three-resistor
ladder with a parameterised leg, applies them one by one or as one ``batch()``, and compares
ngspice's ``v(out)`` with the value computed here. ``derandomize`` makes the 20 examples (about
20 solver runs) the same on every run.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from netlistmod import Dialect, Netlist
from tests.support.ngspice import op
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ngspice")

_LADDER = (
    "ladder\n.param rleg=1k\nV1 in 0 DC 1\nR1 in out 1k\nR2 out 0 {rleg}\nR3 out 0 2k\n.op\n.end\n"
)
_SCALE = {"": 1.0, "k": 1e3}

values = st.builds(
    lambda mantissa, scale: (f"{mantissa}{scale}", float(mantissa) * _SCALE[scale]),
    st.sampled_from(["1", "2.2", "4.7", "10", "33", "100", "470"]),
    st.sampled_from(sorted(_SCALE)),
)
edits = st.lists(st.tuples(st.sampled_from(["R1", "R3", "rleg"]), values), min_size=1, max_size=4)


def _expected(resistances: dict[str, float]) -> float:
    leg = 1 / (1 / resistances["rleg"] + 1 / resistances["R3"])
    return leg / (resistances["R1"] + leg)


def _apply(netlist: Netlist, target: str, text: str) -> Netlist:
    return netlist.params.set(target, text) if target == "rleg" else netlist.set_value(target, text)


@settings(
    max_examples=20,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(sequence=edits, as_batch=st.booleans())
def test_value_and_param_edits_move_the_ladder_as_computed(
    solver: Solver, tmp_path: Path, sequence: list[tuple[str, tuple[str, float]]], as_batch: bool
) -> None:
    netlist = Netlist.from_text(_LADDER, dialect=Dialect.NGSPICE)
    resistances = {"R1": 1e3, "rleg": 1e3, "R3": 2e3}
    if as_batch:
        # One plan may not edit a span twice (decision 0007): the last edit of a target counts.
        last = dict(sequence)
        with netlist.batch() as batch:
            for target, (text, _) in last.items():
                if target == "rleg":
                    batch.params.set(target, text)
                else:
                    batch.set_value(target, text)
        edited = batch.result
        resistances.update({target: value for target, (_, value) in last.items()})
    else:
        edited = netlist
        for target, (text, value) in sequence:
            edited = _apply(edited, target, text)
            resistances[target] = value
    assert edited.signature() == netlist.signature()
    out = op(solver, tmp_path, edited)["v(out)"]
    assert out == pytest.approx(_expected(resistances), rel=1e-6)
