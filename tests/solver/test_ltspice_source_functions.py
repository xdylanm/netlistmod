"""LTspice 26.1.1 probes for the source functions (M12 T4, T5, T7, T8 tier; decision 0013).

Nothing LTspice writes is committed (decision 0009 item 2).
"""

from __future__ import annotations

import struct
import wave
from pathlib import Path

import pytest

from netlistmod import Dialect, Netlist, ParseError
from tests.support.ltspice import Run, op, run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ltspice")

CORPUS = Path(__file__).parents[1] / "corpus" / "ltspice"


def _text(source: str) -> str:
    return f"t\n.param x=2\n{source}\nR1 a 0 1k\n.tran 1u 10u\n.end\n"


def _range(result: Run) -> tuple[float, float]:
    assert result.ok, result.log
    values = result.plot("Transient").real("V(a)")
    return max(values), min(values)


def _netlist(source: str) -> Netlist:
    return Netlist.from_text(_text(source), dialect=Dialect.LTSPICE)


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
    ],
)
def test_pulse_gives_its_waveform(
    solver: Solver, tmp_path: Path, source: str, high: float, low: float
) -> None:
    assert _range(run(solver, tmp_path, _netlist(source))) == pytest.approx((high, low), abs=2e-3)


@pytest.mark.parametrize("name", ["SIN", "SINE"])
def test_sine_gives_its_waveform(solver: Solver, tmp_path: Path, name: str) -> None:
    source = f"V1 a 0 {name}(0 1 1k)"
    assert _range(run(solver, tmp_path, _netlist(source))) == pytest.approx((0.063, 0), abs=2e-3)


def test_exp_gives_its_waveform(solver: Solver, tmp_path: Path) -> None:
    source = "V1 a 0 EXP(0 1 1u 1u 5u 1u)"
    assert _range(run(solver, tmp_path, _netlist(source))) == pytest.approx((0.98, 0.0), abs=0.01)


def test_sffm_gives_its_waveform(solver: Solver, tmp_path: Path) -> None:
    source = "V1 a 0 SFFM(0 1 100k 2 10k)"
    assert _range(run(solver, tmp_path, _netlist(source))) == pytest.approx((1.0, -1.0), abs=0.01)


def test_pwl_gives_its_waveform(solver: Solver, tmp_path: Path) -> None:
    source = "V1 a 0 PWL(0 0 5u 1)"
    assert _range(run(solver, tmp_path, _netlist(source))) == pytest.approx((1.0, 0.0), abs=1e-6)


def test_pwl_scale_factors(solver: Solver, tmp_path: Path) -> None:
    source = "V1 a 0 PWL TIME_SCALE_FACTOR=2 VALUE_SCALE_FACTOR=3 (0 0 1u 1)"
    assert _range(run(solver, tmp_path, _netlist(source))) == pytest.approx((3.0, 0.0), abs=1e-6)


@pytest.mark.parametrize("form", ["file=x.txt", 'file="x.txt"', "FILE=x.txt"])
def test_pwl_file(solver: Solver, tmp_path: Path, form: str) -> None:
    (tmp_path / "x.txt").write_text("0 0\n1u 1\n", encoding="utf-8")
    source = f"V1 a 0 PWL {form}"
    assert _range(run(solver, tmp_path, _netlist(source))) == pytest.approx((1.0, 0.0), abs=1e-6)


@pytest.mark.parametrize("repeat", ["FOR 2", "FOREVER"])
def test_pwl_repeat(solver: Solver, tmp_path: Path, repeat: str) -> None:
    source = f"V1 a 0 PWL REPEAT {repeat} (0 0 1u 1 2u 0) ENDREPEAT"
    assert _range(run(solver, tmp_path, _netlist(source))) == pytest.approx((1.0, 0.0), abs=1e-6)


def test_a_nested_pwl_repeat_stops_both(solver: Solver, tmp_path: Path) -> None:
    source = "V1 a 0 PWL REPEAT FOR 2 (0 0 REPEAT FOR 2 (1u 1 2u 0) ENDREPEAT) ENDREPEAT"
    with pytest.raises(ParseError):
        _netlist(source)
    assert run(solver, tmp_path, _text(source)).returncode != 0


@pytest.mark.parametrize(
    "source",
    [
        "V1 a 0 PWL REPEAT FOR 2 (0 0 1u 1 2u 0) ENDREPEAT REPEAT FOR 2 (3u 0 4u 1 5u 0) ENDREPEAT",
    ],
)
def test_forms_that_the_reference_does_not_show_are_refused(
    solver: Solver, tmp_path: Path, source: str
) -> None:
    assert run(solver, tmp_path, _text(source)).ok
    with pytest.raises(ParseError):
        _netlist(source)


def test_a_wave_file(solver: Solver, tmp_path: Path) -> None:
    with wave.open(str(tmp_path / "x.wav"), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(1_000_000)
        file.writeframes(struct.pack("<20h", *([16384] * 20)))
    high, low = _range(run(solver, tmp_path, _netlist("V1 a 0 wavefile=x.wav chan=0")))
    assert high == pytest.approx(0.5, abs=0.01)
    assert low <= high


@pytest.mark.parametrize(
    "source",
    ["V1 a 0 PULSE(0 1 1u 1u 1u 2u 5u) Rser=1 Cpar=1p", "V1 a 0 Rser=1 PULSE(0 1 1u 1u 1u 2u 5u)"]
    + [
        "V1 a 0 SIN(0 1 1k) AC 1 Rser=1",
        "V1 a 0 SIN(0 1 1k) Rser=1 AC 1",
        "V1 a 0 SIN(0 1 1k) AC=1",
    ]
    + ["V1 a 0 1 SIN(0 1 1k)", "V1 a 0 SIN(0 1 1k) DC 1", "V1 a 0 AC 1 SIN(0 1 1k)"],
)
def test_a_function_mixes_with_dc_ac_rser_and_cpar(
    solver: Solver, tmp_path: Path, source: str
) -> None:
    assert run(solver, tmp_path, _netlist(source)).ok


def test_the_trigger_parameters_run(solver: Solver, tmp_path: Path) -> None:
    source = "V1 a 0 PULSE(0 1 1u 1u 1u 2u 5u) Trigger=V(a)>0.5 tripdv=1m tripdt=1u"
    assert run(solver, tmp_path, _netlist(source)).ok


@pytest.mark.parametrize(
    "source",
    ["I1 a 0 tbl=(0 0, 1 1)", "I1 a 0 tbl=(0,0,1,1)"],
)
def test_a_table_runs(solver: Solver, tmp_path: Path, source: str) -> None:
    assert run(solver, tmp_path, _netlist(source)).ok


@pytest.mark.parametrize(
    "source",
    ["I1 a 0 1 step(1,2,3)", "I1 a 0 step(1,2,3)", "I1 a 0 1 step(1 2 3) load"],
)
def test_a_step_load_runs(solver: Solver, tmp_path: Path, source: str) -> None:
    assert run(solver, tmp_path, _netlist(source)).ok


def test_load_after_a_function_runs(solver: Solver, tmp_path: Path) -> None:
    assert run(solver, tmp_path, _netlist("I1 a 0 PULSE(0 1 1u 1u 1u 2u 5u) load")).ok


@pytest.mark.parametrize(
    "source",
    [
        f"V1 a 0 PULSE {_PULSE}",
        "V1 a 0 PWL(file=x.txt)",
        "V1 a 0 PULSE(0 1 1u 1u 1u 2u 5u) m=2",
    ],
)
def test_forms_that_run_and_the_library_refuses(
    solver: Solver, tmp_path: Path, source: str
) -> None:
    # Outside the reference (discrepancies.md, decision 0013).
    (tmp_path / "x.txt").write_text("0 0\n1u 1\n", encoding="utf-8")
    assert run(solver, tmp_path, _text(source)).ok
    with pytest.raises(ParseError):
        _netlist(source)


@pytest.mark.parametrize(
    "source",
    [
        "V1 a 0 PULSE()",
        "V1 a 0 PULSE(0 x 1u)",
        "V1 a 0 PULSE(0 x*2 1u)",
        "V1 a 0 SIN(0 1 1k) 1",
        "V1 a 0 SIN(0 1 1k) PULSE(0 1)",
        "V1 a 0 PWL(0 0 1u 1) TIME_SCALE_FACTOR=2",
        "I1 a 0 PULSE(0 1 1u 1u 1u 2u 5u) Rser=1",
    ],
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
    # Why set_stimulus leaves DC alone (decision 0013).
    netlist = Netlist.from_text(
        "t\nV1 a 0 DC 2 SIN(0 1 1k)\nR1 a 0 1k\n.op\n.end\n", dialect=Dialect.LTSPICE
    )
    assert op(solver, tmp_path, netlist)["v(a)"] == pytest.approx(2.0)


def test_set_stimulus_changes_the_waveform(solver: Solver, tmp_path: Path) -> None:
    edited = _netlist("V1 a 0 0").set_stimulus("V1", f"PULSE({_PULSE})")
    assert _range(run(solver, tmp_path, edited)) == pytest.approx((1.0, 0.0), abs=1e-6)


def test_set_stimulus_arg_changes_the_waveform(solver: Solver, tmp_path: Path) -> None:
    edited = _netlist(f"V1 a 0 PULSE({_PULSE})").set_stimulus_arg("V1", 1, "3")
    assert _range(run(solver, tmp_path, edited)) == pytest.approx((3.0, 0.0), abs=1e-6)


def test_remove_stimulus_leaves_the_dc_value(solver: Solver, tmp_path: Path) -> None:
    edited = _netlist(f"V1 a 0 2 PULSE({_PULSE})").remove_stimulus("V1")
    assert _range(run(solver, tmp_path, edited)) == pytest.approx((2.0, 2.0), abs=1e-6)


def test_the_half_rectifier_export_loads_and_edits(solver: Solver, tmp_path: Path) -> None:
    netlist = Netlist.load(
        CORPUS / "contributed_examples" / "half_rectifier.net", dialect=Dialect.LTSPICE
    )
    before = max(run(solver, tmp_path / "before", netlist).plot("Transient").real("V(vout)"))
    edited = netlist.set_stimulus_arg("V1", 1, "2")
    after = max(run(solver, tmp_path / "after", edited).plot("Transient").real("V(vout)"))
    assert after > before
    assert edited.signature() == netlist.signature()


def _half_scale_wave(path: Path) -> None:
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(1_000_000)
        file.writeframes(struct.pack("<20h", *([16384] * 20)))


def test_a_wave_file_on_an_i_line(solver: Solver, tmp_path: Path) -> None:
    _half_scale_wave(tmp_path / "x.wav")
    high, low = _range(run(solver, tmp_path, _netlist("I1 a 0 wavefile=x.wav chan=0")))
    assert low == pytest.approx(-500, abs=5)
    assert high <= 0


@pytest.mark.parametrize(
    "source",
    [
        "I1 a 0 PULSE(0 1 1u 1u 1u 2u 5u) Trigger=V(a)>0.5",
        "I1 a 0 PULSE(0 1 1u 1u 1u 2u 5u) tripdv=1m",
    ],
)
def test_a_trigger_on_an_i_line_stops_ltspice(solver: Solver, tmp_path: Path, source: str) -> None:
    # The reference says all time-dependent sources support it, so the library follows it.
    assert _netlist(source) is not None
    result = run(solver, tmp_path, _text(source))
    assert result.returncode != 0
    assert "Unknown parameter" in result.log


@pytest.mark.parametrize(
    "tail",
    [
        "FILE=x.txt",
        "REPEAT FOR 2 (0 0 1u 1 2u 0) ENDREPEAT",
        "REPEAT FOREVER (0 0 1u 1 2u 0) ENDREPEAT",
    ],
)
def test_a_scale_factor_before_a_file_or_a_repeat(
    solver: Solver, tmp_path: Path, tail: str
) -> None:
    (tmp_path / "x.txt").write_text("0 0\n1u 1\n", encoding="utf-8")
    source = f"V1 a 0 PWL VALUE_SCALE_FACTOR=3 {tail}"
    assert _range(run(solver, tmp_path, _netlist(source))) == pytest.approx((3.0, 0.0), abs=1e-6)


@pytest.mark.parametrize(
    "tail",
    ["PWL(0 0 1u 1) VALUE_SCALE_FACTOR=3", "PWL FILE=x.txt VALUE_SCALE_FACTOR=3"],
)
def test_a_scale_factor_after_the_list_or_a_file_stops_both(
    solver: Solver, tmp_path: Path, tail: str
) -> None:
    (tmp_path / "x.txt").write_text("0 0\n1u 1\n", encoding="utf-8")
    source = f"V1 a 0 {tail}"
    assert run(solver, tmp_path, _text(source)).returncode != 0
    with pytest.raises(ParseError):
        _netlist(source)


@pytest.mark.parametrize(
    "source",
    [
        "I1 a 0 load PULSE(0 1 1u 1u 1u 2u 5u)",
        "I1 a 0 1 load PULSE(0 1 1u 1u 1u 2u 5u)",
        "I1 a 0 load DC 1 PULSE(0 1 1u 1u 1u 2u 5u)",
        "I1 a 0 1 tbl=(0 0, 1 1)",
        "I1 a 0 AC 1 tbl=(0 0, 1 1)",
        "I1 a 0 tbl=(0 0, 1 1) DC 1",
        "I1 a 0 tbl=(0 0, 1 1) AC 1",
        "I1 a 0 tbl=(0 0, 1 1) load",
        "V1 a 0 PULSE(0 1 1u 1u 1u 2u 5u) Trigger=V(a) > 0.5",
    ],
)
def test_forms_outside_the_reference_that_run_and_the_library_refuses(
    solver: Solver, tmp_path: Path, source: str
) -> None:
    assert run(solver, tmp_path, _text(source)).ok
    with pytest.raises(ParseError):
        _netlist(source)
