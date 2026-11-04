"""ngspice 47 probes for the source functions (M12 T3, T7, T8 tier; decision 0013)."""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import Dialect, Netlist, ParseError
from tests.support.ngspice import Run, op, run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ngspice")


def _text(source: str) -> str:
    return f"t\n.param x=2\n{source}\nR1 a 0 1k\n.tran 1u 10u\n.end\n"


def _range(result: Run) -> tuple[float, float]:
    assert result.ok, result.log
    values = result.plot("Transient").real("v(a)")
    return max(values), min(values)


def _netlist(source: str) -> Netlist:
    return Netlist.from_text(_text(source), dialect=Dialect.NGSPICE)


_PULSE = "0 1 1u 1u 1u 2u 5u"


@pytest.mark.parametrize(
    ("source", "high", "low"),
    [
        (f"V1 a 0 PULSE({_PULSE})", 1.0, 0.0),
        ("V1 a 0 PULSE(0,1,1u,1u,1u,2u,5u)", 1.0, 0.0),
        (f"V1 a 0 PULSE ({_PULSE})", 1.0, 0.0),
        ("V1 a 0 PULSE(0 1\n+ 1u 1u 1u 2u 5u)", 1.0, 0.0),
        ("V1 a 0 PULSE(0 {x} 1u 1u 1u 2u 5u)", 2.0, 0.0),
        ("V1 a 0 PULSE(0 'x*2' 1u 1u 1u 2u 5u)", 4.0, 0.0),
        ("V1 a 0 SIN(0 1 1k)", 0.063, 0.0),
        ("V1 a 0 SIN(0 1 1MEG)", 0.999, -0.882),
    ],
)
def test_pulse_and_sin_give_their_waveforms(
    solver: Solver, tmp_path: Path, source: str, high: float, low: float
) -> None:
    assert _range(run(solver, tmp_path, _netlist(source))) == pytest.approx((high, low), abs=2e-3)


def test_sine_reads_as_sin(solver: Solver, tmp_path: Path) -> None:
    sin = _range(run(solver, tmp_path / "sin", _netlist("V1 a 0 SIN(0 1 1MEG)")))
    assert _range(run(solver, tmp_path / "sine", _netlist("V1 a 0 SINE(0 1 1MEG)"))) == sin


def test_exp_gives_its_waveform(solver: Solver, tmp_path: Path) -> None:
    source = "V1 a 0 EXP(0 1 1u 1u 5u 1u)"
    assert _range(run(solver, tmp_path, _netlist(source))) == pytest.approx((0.98, 0.0), abs=0.01)


def test_pwl_gives_its_waveform(solver: Solver, tmp_path: Path) -> None:
    source = "V1 a 0 PWL(0 0 5u 1)"
    assert _range(run(solver, tmp_path, _netlist(source))) == pytest.approx((1.0, 0.0), abs=1e-6)


def test_pwl_r_and_td(solver: Solver, tmp_path: Path) -> None:
    source = "V1 a 0 PWL(0 0 5u 1) r=0 td=1u"
    assert _range(run(solver, tmp_path, _netlist(source))) == pytest.approx((1.0, 0.0), abs=1e-6)


def test_sffm_gives_its_waveform(solver: Solver, tmp_path: Path) -> None:
    source = "V1 a 0 SFFM(0 1 100k 2 10k)"
    assert _range(run(solver, tmp_path, _netlist(source))) == pytest.approx((1.0, -1.0), abs=0.01)


def test_am_runs(solver: Solver, tmp_path: Path) -> None:
    high, low = _range(run(solver, tmp_path, _netlist("V1 a 0 AM(1 0 1k 100k)")))
    assert high > 0 > low


@pytest.mark.parametrize(
    "source",
    ["V1 a 0 TRNOISE(1m 1u 0 0)", "V1 a 0 DC 0 trnoise(1m 1u 0 0)"],
)
def test_trnoise_runs(solver: Solver, tmp_path: Path, source: str) -> None:
    assert run(solver, tmp_path, _netlist(source)).ok


@pytest.mark.parametrize(
    "source",
    ["V1 a 0 TRRANDOM(1 1u 0 1)", "V1 a 0 dc 0 trrandom (2 10m 0 1)"],
)
def test_trrandom_runs(solver: Solver, tmp_path: Path, source: str) -> None:
    assert run(solver, tmp_path, _netlist(source)).ok


def test_external_is_read_and_stops_this_build(solver: Solver, tmp_path: Path) -> None:
    # The manual's form; it needs ngspice as a shared library (manual §4.1.9).
    result = run(solver, tmp_path, _netlist("V1 a 0 dc 0 external"))
    assert result.returncode != 0
    assert "unknown parameter (external)" in result.log


@pytest.mark.parametrize(
    "source",
    ["V1 a 0 DC 0 DISTOF1 0.1", "V1 a 0 DISTOF1 0.1 -90.0", "V1 a 0 DISTOF2 0.01"]
    + ["V1 a 0 SIN(0 1 1k) DISTOF1 0.1"],
)
def test_distortion_inputs_run(solver: Solver, tmp_path: Path, source: str) -> None:
    assert run(solver, tmp_path, _netlist(source)).ok


@pytest.mark.parametrize("source", ["V1 a 0 DISTOF1", "I1 a 0 AC 1 DISTOF1 DISTOF2 0.001"])
def test_manual_distortion_forms_that_stop(solver: Solver, tmp_path: Path, source: str) -> None:
    # The second is the manual's own example; the library follows the manual (discrepancies.md).
    assert _netlist(source) is not None
    assert run(solver, tmp_path, _text(source)).returncode != 0


@pytest.mark.parametrize(
    "source",
    ["V1 a 0 dc 0 ac 1 portnum 1 z0 100", "V1 a 0 dc 0 ac 1 portnum=1 z0=100"]
    + ["V1 a 0 SIN(0 1 1k) portnum 1"],
)
def test_rf_port_parameters_run(solver: Solver, tmp_path: Path, source: str) -> None:
    assert run(solver, tmp_path, _netlist(source)).ok


@pytest.mark.parametrize(
    "source",
    [
        "V1 a 0 SIN(0 1 1k) AC 1",
        "V1 a 0 AC 1 SIN(0 1 1k)",
        "V1 a 0 DC 1 SIN(0 1 1k)",
        "V1 a 0 SIN(0 1 1k) DC 1",
        "V1 a 0 SIN(0 1 1k) DC 1 AC 1",
    ],
)
def test_a_function_runs_before_or_after_dc_and_ac(
    solver: Solver, tmp_path: Path, source: str
) -> None:
    assert _range(run(solver, tmp_path, _netlist(source))) == pytest.approx((0.063, 0), abs=2e-3)


@pytest.mark.parametrize(
    ("source", "reading"),
    [
        (f"V1 a 0 PULSE {_PULSE}", (1.0, 0.0)),
        ("V1 a 0 PULSE(0 x 1u 1u 1u 2u 5u)", (2.0, 0.0)),
        ("V1 a 0 SIN(0 1 1k) 1", (0.0, 0.0)),
        ("V1 a 0 SIN(0 1 1k) PULSE(0 1 1u 1u 1u 2u 5u)", (1.0, 0.0)),
    ],
)
def test_forms_that_run_and_the_library_refuses(
    solver: Solver, tmp_path: Path, source: str, reading: tuple[float, float]
) -> None:
    # No parentheses and a bare name are outside the manual; a value after a function silences it,
    # and of two functions the last wins (discrepancies.md, decision 0013).
    assert _range(run(solver, tmp_path, _text(source))) == pytest.approx(reading, abs=2e-3)
    with pytest.raises(ParseError):
        _netlist(source)


@pytest.mark.parametrize(
    "source", ["V1 a 0 PULSE()", "V1 a 0 PULSE(0 x*2)", "V1 a 0 PWL file=x.txt"]
)
def test_forms_that_stop_and_the_library_refuses(
    solver: Solver, tmp_path: Path, source: str
) -> None:
    assert run(solver, tmp_path, _text(source)).returncode != 0
    with pytest.raises(ParseError):
        _netlist(source)


def test_a_dc_value_beside_a_function_is_the_operating_point(
    solver: Solver, tmp_path: Path
) -> None:
    # Why set_stimulus leaves DC alone (decision 0013): .op reads it, and the function drives .tran.
    netlist = Netlist.from_text(
        "t\nV1 a 0 DC 2 SIN(0 1 1k)\nR1 a 0 1k\n.op\n.end\n", dialect=Dialect.NGSPICE
    )
    assert op(solver, tmp_path, netlist)["v(a)"] == pytest.approx(2.0)


def test_set_stimulus_changes_the_waveform(solver: Solver, tmp_path: Path) -> None:
    edited = _netlist("V1 a 0 DC 0").set_stimulus("V1", f"PULSE({_PULSE})")
    assert _range(run(solver, tmp_path, edited)) == pytest.approx((1.0, 0.0), abs=1e-6)


def test_set_stimulus_arg_changes_the_waveform(solver: Solver, tmp_path: Path) -> None:
    edited = _netlist(f"V1 a 0 PULSE({_PULSE})").set_stimulus_arg("V1", 1, "3")
    assert _range(run(solver, tmp_path, edited)) == pytest.approx((3.0, 0.0), abs=1e-6)


def test_remove_stimulus_leaves_the_dc_value(solver: Solver, tmp_path: Path) -> None:
    edited = _netlist(f"V1 a 0 DC 2 PULSE({_PULSE})").remove_stimulus("V1")
    assert _range(run(solver, tmp_path, edited)) == pytest.approx((2.0, 2.0), abs=1e-6)
