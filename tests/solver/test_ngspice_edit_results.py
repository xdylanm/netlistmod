"""Edited results against closed forms in ngspice 47 (M7 T6, T8 tier; architecture §10.3 (b)).

One test per M6 operation family (m7-tasks.md section 6), on small circuits whose answer is a
formula. Each test asserts the unedited result as well, so it cannot pass because the edit was
ignored. Results are read from the raw file (15 significant digits): linear DC and AC results
to ``1e-6`` relative, diode, coupling and transient results to ``1e-3`` (ngspice's default
``reltol``).
"""

from __future__ import annotations

import cmath
import math
from pathlib import Path

import pytest

from netlistmod import Dialect, Netlist
from tests.support.ngspice import ac, op, run, tran_rows
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ngspice")

LINEAR = 1e-6
NONLINEAR = 1e-3
# Thermal voltage at 27 °C (300.15 K) from the CODATA constants.
VT = 1.380649e-23 * 300.15 / 1.602176634e-19

_DIVIDER = "divider\nV1 in 0 DC 3\nR1 in out 1k\nR2 out 0 1k\n.op\n.end\n"


def _netlist(text: str) -> Netlist:
    return Netlist.from_text(text, dialect=Dialect.NGSPICE)


def _out(solver: Solver, folder: Path, netlist: Netlist, node: str = "out") -> float:
    return op(solver, folder, netlist)[f"v({node})"]


def _gain(solver: Solver, folder: Path, netlist: Netlist, node: str = "out") -> complex:
    (value,) = ac(solver, folder, netlist)[f"v({node})"]
    return value


def test_set_value_on_a_resistor(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist(_DIVIDER)
    assert _out(solver, tmp_path / "before", netlist) == pytest.approx(1.5, rel=LINEAR)
    edited = netlist.set_value("R2", "3k")
    assert _out(solver, tmp_path / "after", edited) == pytest.approx(2.25, rel=LINEAR)


def test_set_value_on_a_capacitor(solver: Solver, tmp_path: Path) -> None:
    corner = 1 / (2 * math.pi * 1e3 * 1e-6)
    netlist = _netlist(
        f"rc\nV1 in 0 DC 0 AC 1\nR1 in out 1k\nC1 out 0 1u\n.ac lin 1 {corner} {corner}\n.end\n"
    )
    before = _gain(solver, tmp_path / "before", netlist)
    assert abs(before) == pytest.approx(1 / math.sqrt(2), rel=LINEAR)
    after = _gain(solver, tmp_path / "after", netlist.set_value("C1", "2u"))
    assert abs(after) == pytest.approx(1 / math.sqrt(5), rel=LINEAR)


def test_set_value_on_an_inductor(solver: Solver, tmp_path: Path) -> None:
    corner = 1e3 / (2 * math.pi * 1e-3)
    netlist = _netlist(
        f"rl\nV1 in 0 DC 0 AC 1\nL1 in out 1m\nR1 out 0 1k\n.ac lin 1 {corner} {corner}\n.end\n"
    )
    before = _gain(solver, tmp_path / "before", netlist)
    assert abs(before) == pytest.approx(1 / math.sqrt(2), rel=LINEAR)
    after = _gain(solver, tmp_path / "after", netlist.set_value("L1", "2m"))
    assert abs(after) == pytest.approx(1 / math.sqrt(5), rel=LINEAR)


def test_set_formula_with_an_added_param(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist(_DIVIDER)
    assert _out(solver, tmp_path / "before", netlist) == pytest.approx(1.5, rel=LINEAR)
    with netlist.batch() as batch:
        batch.set_formula("R2", "rx")
        batch.params.set("rx", "3k")
    assert _out(solver, tmp_path / "after", batch.result) == pytest.approx(2.25, rel=LINEAR)


def test_params_set_replaces_a_top_level_param_used_twice(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist(
        "two dividers\n.param rx=1k\nV1 in 0 DC 3\nR1 in out 1k\nR2 out 0 {rx}\n"
        "R3 in out2 1k\nR4 out2 0 {rx}\n.op\n.end\n"
    )
    before = op(solver, tmp_path / "before", netlist)
    assert (before["v(out)"], before["v(out2)"]) == pytest.approx((1.5, 1.5), rel=LINEAR)
    after = op(solver, tmp_path / "after", netlist.params.set("rx", "3k"))
    assert (after["v(out)"], after["v(out2)"]) == pytest.approx((2.25, 2.25), rel=LINEAR)


_INSTANCES = (
    "instances\nV1 in 0 DC 3\nX1 in o1 div\nX2 in o2 div\n"
    ".subckt div a b{defaults}\n{body}R1 a b 1k\nR2 b 0 {{rb}}\n.ends div\n.op\n.end\n"
)


def test_params_set_in_a_definition_moves_every_instance(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist(_INSTANCES.format(defaults="", body=".param rb=1k\n"))
    before = op(solver, tmp_path / "before", netlist)
    assert (before["v(o1)"], before["v(o2)"]) == pytest.approx((1.5, 1.5), rel=LINEAR)
    edited = netlist.params.set("rb", "3k", scope=("div",), in_definition=True)
    after = op(solver, tmp_path / "after", edited)
    assert (after["v(o1)"], after["v(o2)"]) == pytest.approx((2.25, 2.25), rel=LINEAR)


def test_set_instance_param_moves_only_that_instance(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist(_INSTANCES.format(defaults=" rb=1k", body=""))
    before = op(solver, tmp_path / "before", netlist)
    assert (before["v(o1)"], before["v(o2)"]) == pytest.approx((1.5, 1.5), rel=LINEAR)
    after = op(solver, tmp_path / "after", netlist.set_instance_param("X2", "rb", "3k"))
    assert (after["v(o1)"], after["v(o2)"]) == pytest.approx((1.5, 2.25), rel=LINEAR)


def test_set_param_multiplier_on_a_resistor(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist(_DIVIDER)
    assert _out(solver, tmp_path / "before", netlist) == pytest.approx(1.5, rel=LINEAR)
    edited = netlist.set_param("R1", "m", "2")  # two 1k in parallel: 500
    assert _out(solver, tmp_path / "after", edited) == pytest.approx(2.0, rel=LINEAR)


def test_set_param_temperature_coefficient_on_a_resistor(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist(_DIVIDER.replace(".op\n", ".temp 127\n.op\n"))
    assert _out(solver, tmp_path / "before", netlist) == pytest.approx(1.5, rel=LINEAR)
    edited = netlist.set_param("R1", "tc1", "0.01")  # 1k * (1 + 0.01 * (127 - 27)) = 2k
    assert _out(solver, tmp_path / "after", edited) == pytest.approx(1.0, rel=LINEAR)


_DIODE = (
    "diode\nI1 0 a DC 1m\nD1 a 0 {model}\n.model dsmall d is=1e-14\n.model dlarge d is=1e-12\n"
    ".op\n.end\n"
)


def _diode_voltage(saturation: float) -> float:
    return VT * math.log(1e-3 / saturation + 1)


def test_set_model_on_a_diode(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist(_DIODE.format(model="dsmall"))
    before = _out(solver, tmp_path / "before", netlist, "a")
    assert before == pytest.approx(_diode_voltage(1e-14), rel=NONLINEAR)
    after = _out(solver, tmp_path / "after", netlist.set_model("D1", "dlarge"), "a")
    assert before - after == pytest.approx(VT * math.log(100), rel=NONLINEAR)


def test_set_model_param_on_a_diode_model(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist(_DIODE.format(model="dsmall"))
    before = _out(solver, tmp_path / "before", netlist, "a")
    edited = netlist.set_model_param("dsmall", "is", "1e-12")
    after = _out(solver, tmp_path / "after", edited, "a")
    assert after == pytest.approx(_diode_voltage(1e-12), rel=NONLINEAR)
    assert before - after == pytest.approx(VT * math.log(100), rel=NONLINEAR)


def test_set_model_and_remove_value_switch_a_resistor_to_its_geometry(
    solver: Solver, tmp_path: Path
) -> None:
    netlist = _netlist(_DIVIDER.replace(".op\n", ".model rmod r rsh=100\n.op\n"))
    with netlist.batch() as batch:
        batch.set_model("R2", "rmod")
        batch.set_param("R2", "l", "20u")
        batch.set_param("R2", "w", "1u")
    # Moved from test_ngspice_solver_edits.py (M6 review round 1): the value still wins over
    # the geometry; removing it leaves rsh * l / w = 2k.
    assert _out(solver, tmp_path / "before", batch.result) == pytest.approx(1.5, rel=LINEAR)
    edited = batch.result.remove_value("R2")
    assert _out(solver, tmp_path / "after", edited) == pytest.approx(2.0, rel=LINEAR)


def test_set_dc_on_voltage_and_current_sources(solver: Solver, tmp_path: Path) -> None:
    divider = _netlist(_DIVIDER)
    assert _out(solver, tmp_path / "v0", divider) == pytest.approx(1.5, rel=LINEAR)
    assert _out(solver, tmp_path / "v1", divider.set_dc("V1", "6")) == pytest.approx(3.0)
    current = _netlist("source\nI1 0 a DC 1m\nR1 a 0 1k\n.op\n.end\n")
    assert _out(solver, tmp_path / "i0", current, "a") == pytest.approx(1.0, rel=LINEAR)
    edited = current.set_dc("I1", "2m")
    assert _out(solver, tmp_path / "i1", edited, "a") == pytest.approx(2.0, rel=LINEAR)


def test_set_ac_magnitude_and_phase(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist(
        "ac divider\nV1 in 0 DC 0 AC 1\nR1 in out 1k\nR2 out 0 1k\n.ac lin 1 1k 1k\n.end\n"
    )
    assert _gain(solver, tmp_path / "before", netlist) == pytest.approx(0.5, rel=LINEAR)
    doubled = _gain(solver, tmp_path / "magnitude", netlist.set_ac("V1", "2"))
    assert abs(doubled) == pytest.approx(1.0, rel=LINEAR)
    turned = _gain(solver, tmp_path / "phase", netlist.set_ac("V1", "1", phase="90"))
    assert abs(turned) == pytest.approx(0.5, rel=LINEAR)
    assert cmath.phase(turned) == pytest.approx(math.pi / 2, rel=LINEAR)


def test_set_coupling_on_a_transformer(solver: Solver, tmp_path: Path) -> None:
    # Equal inductances, an open secondary (1 GΩ): the secondary voltage is k times the primary.
    netlist = _netlist(
        "coupled\nV1 p 0 DC 0 AC 1\nL1 p 0 1m\nL2 s 0 1m\nR2 s 0 1G\nK1 L1 L2 0.5\n"
        ".ac lin 1 1k 1k\n.end\n"
    )
    assert abs(_gain(solver, tmp_path / "before", netlist, "s")) == pytest.approx(
        0.5, rel=NONLINEAR
    )
    after = _gain(solver, tmp_path / "after", netlist.set_coupling("K1", "0.9"), "s")
    assert abs(after) == pytest.approx(0.9, rel=NONLINEAR)


def test_directives_set_moves_the_tran_end_time(solver: Solver, tmp_path: Path) -> None:
    # RC charge from DC 1 with the capacitor held at 0 V (uic): v = 1 - exp(-t / tau), tau = 1m.
    netlist = _netlist(
        "charge\nV1 in 0 DC 1\nR1 in out 1k\nC1 out 0 1u\n.ic v(out)=0\n.tran 10u 1m uic\n.end\n"
    )
    before = tran_rows(solver, tmp_path / "before", netlist)[-1]
    assert before["time"] == pytest.approx(1e-3, rel=LINEAR)
    assert before["v(out)"] == pytest.approx(1 - math.exp(-1), rel=NONLINEAR)
    edited = netlist.directives.set(".tran 10u 2m uic")
    after = tran_rows(solver, tmp_path / "after", edited)[-1]
    assert after["time"] == pytest.approx(2e-3, rel=LINEAR)
    assert after["v(out)"] == pytest.approx(1 - math.exp(-2), rel=NONLINEAR)


def test_directives_set_moves_the_temperature(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist(_DIVIDER.replace("R1 in out 1k", "R1 in out 1k tc1=0.01"))
    netlist = netlist.directives.set(".temp 27")
    assert _out(solver, tmp_path / "before", netlist) == pytest.approx(1.5, rel=LINEAR)
    edited = netlist.directives.set(".temp 127")
    assert _out(solver, tmp_path / "after", edited) == pytest.approx(1.0, rel=LINEAR)


def test_directives_add_a_dc_sweep(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist(_DIVIDER)
    before = run(solver, tmp_path / "before", netlist)
    assert [plot.name for plot in before.plots] == ["Operating Point"]
    result = run(solver, tmp_path / "after", netlist.directives.add(".dc V1 0 3 1"))
    assert result.ok, result.log
    sweep = result.plot("DC transfer")
    assert sweep.real("v(out)") == pytest.approx((0.0, 0.5, 1.0, 1.5), abs=1e-12)


def test_add_include_brings_in_a_harness(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist("bare\nV1 in 0 DC 3\nR1 in out 1k\nR2 out 0 1k\n.op\n.end\n")
    before = run(solver, tmp_path, netlist)
    assert "v(in)" in before.plot("Operating Point").variables
    # The harness adds a load and saves only v(out); the netlist only gains the .include.
    (tmp_path / "harness.inc").write_bytes(b"R3 out 0 1k\n.save v(out)\n")
    result = run(solver, tmp_path, netlist.add_include("harness.inc"))
    assert result.ok, result.log
    assert result.plot("Operating Point").variables == ("v(out)",)
    assert result.voltage("out") == pytest.approx(1.0, rel=LINEAR)


def test_a_batch_of_three_edits_gives_the_combined_result(solver: Solver, tmp_path: Path) -> None:
    netlist = _netlist(_DIVIDER)
    before = run(solver, tmp_path / "before", netlist)
    assert [plot.name for plot in before.plots] == ["Operating Point"]
    with netlist.batch() as batch:
        batch.set_formula("R2", "rx")
        batch.params.set("rx", "3k")
        batch.directives.set(".tran 1u 10u")
    result = run(solver, tmp_path / "after", batch.result)
    assert result.ok, result.log
    assert result.voltage("out") == pytest.approx(2.25, rel=LINEAR)
    assert result.plot("Transient").real("v(out)") == pytest.approx(
        [2.25] * len(result.plot("Transient").rows), rel=LINEAR
    )
