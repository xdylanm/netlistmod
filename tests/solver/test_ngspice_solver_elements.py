"""ngspice 47 probes for element lines and values (M3, T8 tier).

Each probe pairs what ngspice does with what the library does. Values are read from the device
tables ngspice prints after ``.op`` in batch mode (``resistance``, ``capacitance``).
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from netlistmod import Dialect, NumericValue, ParseError, Resistor, SourceText, parse
from tests.support.solvers import Solver, run_ngspice

pytestmark = pytest.mark.solver("ngspice")

CORPUS = Path(__file__).parents[1] / "corpus" / "ngspice" / "elements_basic"

# Definitions the accept corpus refers to, added before .end so ngspice can load each file.
# rshunt gives every node a path to ground, so the toy circuits have an operating point.
HARNESS = """.param rval=1k cval=1n lval=1u
.model RMODEL R rsh=100
.model newres R tc1=0.001
.model rmod R
.model cstd C cap=3n
.model CMODEL C cj=1e-4
.model indmod1 L ind=3n
.model DIODE1 D
.model DMOD D
.model 1n4148 D
.subckt MULTI 1 2 3 4 5
R1 1 2 1k
R2 3 4 1k
R3 5 0 1k
.ends
.subckt myfilter in out rval=100k cval=100n
R1 in out {rval}
C1 out 0 {cval}
.ends
.subckt sub a b r=1k file="none"
R1 a b {r}
.ends
.options rshunt=1e9
.op
"""


def _run(solver: Solver, tmp_path: Path, text: str, *, lt: bool = False) -> tuple[int, str]:
    if lt:
        (tmp_path / ".spiceinit").write_text("set ngbehavior=lt\n", encoding="utf-8")
    netlist = tmp_path / "probe.cir"
    netlist.write_bytes(text.encode("utf-8"))
    result = run_ngspice(solver, netlist)
    return result.returncode, (tmp_path / "ngspice.log").read_text(encoding="utf-8")


def _device_values(log: str, parameter: str) -> dict[str, float]:
    """Map device name to ``parameter`` from ngspice's device tables."""
    values: dict[str, float] = {}
    devices: list[str] = []
    for line in log.splitlines():
        fields = line.split()
        if fields[:1] == ["device"]:
            devices = fields[1:]
        elif fields[:1] == [parameter] and len(fields) == len(devices) + 1:
            values.update(zip(devices, map(float, fields[1:]), strict=True))
    return values


def _first_row_value(log: str, column: int = 1) -> float:
    match = re.search(r"(?m)^0\t(.+)$", log)
    assert match is not None, log
    return float(match.group(1).split()[column - 1])


def _resistance(solver: Solver, tmp_path: Path, value: str, *, lt: bool = False) -> float:
    code, log = _run(solver, tmp_path, f"probe\nV1 in 0 DC 1\nR1 in 0 {value}\n.op\n.end\n", lt=lt)
    assert code == 0, log
    return _device_values(log, "resistance")["r1"]


def _capacitance(solver: Solver, tmp_path: Path, value: str, *, lt: bool = False) -> float:
    code, log = _run(
        solver,
        tmp_path,
        f"probe\nV1 in 0 DC 1\nR1 in out 1k\nC1 out 0 {value}\n.op\n.end\n",
        lt=lt,
    )
    assert code == 0, log
    return _device_values(log, "capacitance")["c1"]


@pytest.mark.parametrize(
    ("kind", "value", "default"),
    [
        ("R", "2k7", 2e3),
        ("R", "4R7", 4.0),
        ("R", "4L7", 4.0),
        ("R", "4G7", 4e9),
        ("R", "1M0", 1e-3),
        ("C", "4u7", 4e-6),
        ("C", "4F7", 4e-15),
    ],
)
def test_rkm_digits_are_dropped_without_lt_mode(
    solver: Solver, tmp_path: Path, kind: str, value: str, default: float
) -> None:
    # ngspice silently drops the digits after the letter; the library rejects the value.
    measure = _resistance if kind == "R" else _capacitance
    assert measure(solver, tmp_path, value) == pytest.approx(default)
    with pytest.raises(ParseError, match="RKM notation"):
        parse(SourceText(f"t\n{kind}1 a 0 {value}\n.end\n"), Dialect.NGSPICE)


def test_leading_r_rkm_is_an_error_without_lt_mode(solver: Solver, tmp_path: Path) -> None:
    code, log = _run(solver, tmp_path, "probe\nV1 in 0 DC 1\nR1 in 0 R47\n.op\n.end\n")
    assert code != 0, log
    with pytest.raises(ParseError, match="RKM notation"):
        parse(SourceText("t\nR1 in 0 R47\n.end\n"), Dialect.NGSPICE)


@pytest.mark.parametrize(
    ("kind", "value", "lt_reading"),
    [
        ("R", "2k7", 2.7e3),
        ("R", "4R7", 4.7),
        ("R", "R47", 0.47),
        ("R", "4L7", 4.7e-3),
        ("R", "4G7", 4.7e9),
        ("C", "4u7", 4.7e-6),
        ("C", "4p7", 4.7e-12),
    ],
)
def test_lt_mode_reads_rkm_per_iec_60062(
    solver: Solver, tmp_path: Path, kind: str, value: str, lt_reading: float
) -> None:
    measure = _resistance if kind == "R" else _capacitance
    assert measure(solver, tmp_path, value, lt=True) == pytest.approx(lt_reading)
    element = parse(SourceText(f"t\n{kind}1 a 0 {value}\n.end\n"), Dialect.NGSPICE, rkm=True)
    numeric = getattr(element.items[1], "value", None)
    assert isinstance(numeric, NumericValue)
    assert (numeric.notation, numeric.solver_mismatch) == ("rkm", False)


@pytest.mark.parametrize(
    ("kind", "value", "ngspice_reading", "iec_reading"),
    [
        ("R", "1M0", 1e-3, 1e6),
        ("R", "4M7", 4.7e-3, 4.7e6),
        ("C", "4F7", 4.7e-15, 4.7),
    ],
)
def test_rkm_mismatches_with_iec_60062_are_marked(
    solver: Solver,
    tmp_path: Path,
    kind: str,
    value: str,
    ngspice_reading: float,
    iec_reading: float,
) -> None:
    # Discrepancy evidence (decision 0004): ngspice reads M on R as milli and F on C as femto,
    # even in LT mode; IEC 60062 reads them as mega and farad. The library marks the value.
    measure = _resistance if kind == "R" else _capacitance
    reading = measure(solver, tmp_path, value, lt=True)
    assert reading == pytest.approx(ngspice_reading)
    assert reading != pytest.approx(iec_reading)
    element = parse(SourceText(f"t\n{kind}1 a 0 {value}\n.end\n"), Dialect.NGSPICE, rkm=True)
    numeric = getattr(element.items[1], "value", None)
    assert isinstance(numeric, NumericValue) and numeric.solver_mismatch


@pytest.mark.parametrize("lt", [False, True])
def test_exponent_is_not_an_rkm_code_in_either_mode(
    solver: Solver, tmp_path: Path, lt: bool
) -> None:
    assert _resistance(solver, tmp_path, "4E7", lt=lt) == pytest.approx(4e7)
    for rkm in (False, True):
        result = parse(SourceText("t\nR1 a 0 4E7\n.end\n"), Dialect.NGSPICE, rkm=rkm)
        assert result.items[1].value.notation == "standard"  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("value", "reading"),
    [
        ("1µ", 1e-6),
        ("1u", 1e-6),
        ("1kOhm", 1e3),
        ("1kk", 1e3),
        (".5k", 500.0),
        ("5.", 5.0),
        ("+1k", 1e3),
        ("1e3k", 1e6),
        ("1mil", 25.4e-6),
        ("1a", 1e-18),
    ],
)
def test_standard_numbers_agree_with_solver(
    solver: Solver, tmp_path: Path, value: str, reading: float
) -> None:
    assert _resistance(solver, tmp_path, value) == pytest.approx(reading)
    element = parse(SourceText(f"t\nR1 a 0 {value}\n.end\n"), Dialect.NGSPICE).items[1]
    assert isinstance(element, Resistor) and element.value is not None
    assert element.value.text == value


@pytest.mark.parametrize(
    "line",
    ["R1 in,out 1k", "R1 in out r=1k", "R1 in out r = 1k", "R1 in out\n+ 1k"],
)
def test_separators_and_keyword_value_agree_with_solver(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    text = f"probe\nV1 in 0 DC 3\n{line}\nR2 out 0 1k\n.op\n.print op v(out)\n.end\n"
    code, log = _run(solver, tmp_path, text)
    assert code == 0, log
    assert _device_values(log, "resistance")["r1"] == pytest.approx(1e3)
    resistor = parse(SourceText(text), Dialect.NGSPICE).items[2]
    assert isinstance(resistor, Resistor) and resistor.value is not None
    assert [n.name for n in resistor.nodes] == ["in", "out"]
    assert resistor.value.text == "1k"


def test_digit_leading_model_name_agrees_with_solver(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nV1 a 0 DC 1\nR1 a k 1k\nD1 k 0 1n4148\n.model 1n4148 d\n.op\n.end\n"
    code, log = _run(solver, tmp_path, text)
    assert code == 0, log
    assert "can't find model" not in log, log
    diode = parse(SourceText(text), Dialect.NGSPICE).items[3]
    assert getattr(diode, "model").model_name == "1n4148"


@pytest.mark.parametrize("path", sorted(CORPUS.glob("*.cir")), ids=lambda path: path.name)
def test_accept_corpus_runs_in_ngspice(solver: Solver, tmp_path: Path, path: Path) -> None:
    text = path.read_bytes().decode("utf-8")
    parse(SourceText(text), Dialect.NGSPICE)
    head, end, tail = text.rpartition(".end")
    code, log = _run(solver, tmp_path, head + HARNESS + end + tail)
    assert code == 0, log
    assert "error" not in log.lower(), log
    assert "can't find" not in log, log


def test_divider_matches_its_closed_form(solver: Solver, tmp_path: Path) -> None:
    text = "divider\nV1 in 0 DC 3\nR1 in out 2k\nR2 out 0 1k\n.op\n.print op v(out)\n.end\n"
    code, log = _run(solver, tmp_path, text)
    assert code == 0, log
    assert _first_row_value(log) == pytest.approx(3 * 1e3 / (2e3 + 1e3))
    parse(SourceText(text), Dialect.NGSPICE)


def test_rc_filter_is_at_minus_3_db_at_its_corner(solver: Solver, tmp_path: Path) -> None:
    corner = 1 / (2 * math.pi * 10e3 * 1e-9)
    text = (
        f"rc\nV1 in 0 DC 0 AC 1\nR1 in out 10k\nC1 out 0 1n\n"
        f".ac lin 1 {corner} {corner}\n.print ac vm(out)\n.end\n"
    )
    code, log = _run(solver, tmp_path, text)
    assert code == 0, log
    assert _first_row_value(log, column=2) == pytest.approx(1 / math.sqrt(2), rel=1e-4)
    parse(SourceText(text), Dialect.NGSPICE)
