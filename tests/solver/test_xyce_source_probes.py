"""XyceNF 7.10 probes of the transient source functions PULSE, SIN, EXP, SFFM, PAT and PWL (X-M3
B5; decision 0030 items 1 to 5 and 7; xm3-tasks 5.1 points 1 to 15).

Each probe is a minimal netlist authored here and run with ``Xyce`` through
``tests/support/xyce.py``, in a temporary folder; nothing Xyce writes is committed. ``V1`` drives
node 1 alone across a resistor, so ``v(1)`` is the source's value. Where the library reads a line,
the probe computes the waveform from the arguments the library holds (the manual's formulas,
[xyce-ref] §2.3.10 p226–230) and compares it with what Xyce writes; where it refuses one, the
probe records what Xyce does instead (``docs/grammars/xyce/discrepancies.md``).
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import pytest

from netlistmod import Netlist, ParseError, SourceSpec, VoltageSource
from netlistmod.dialects import _XYCE
from tests.support.solvers import Solver
from tests.support.xyce import Run, run

pytestmark = pytest.mark.solver("xyce")

_SCALE = {"meg": 1e6, "k": 1e3, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12}


def _text(line: str, tran: str = ".tran 0.1n 20n", extra: str = "") -> str:
    return f"probe\n{extra}{line}\nR1 1 0 1k\n{tran}\n.end\n"


def _number(text: str) -> float:
    lowered = text.lower()
    for unit in ("s", "v"):  # the units the probes write: 1ns, 0V
        if lowered.endswith(unit) and not lowered[:-1].replace(".", "").isdigit():
            lowered = lowered[:-1]
        elif lowered.endswith(unit):
            lowered = lowered[:-1]
    for suffix in ("meg", "k", "m", "u", "n", "p"):
        if lowered.endswith(suffix):
            return float(lowered[: -len(suffix)]) * _SCALE[suffix]
    return float(lowered)


def _spec(text: str) -> SourceSpec:
    source = Netlist.from_text(text, dialect=_XYCE).element("V1")
    assert isinstance(source, VoltageSource) and source.stimulus is not None
    return source.stimulus


def _waveform(result: Run) -> list[tuple[float, float]]:
    assert result.ok, f"{result.log}\n{result.stderr}"
    plot = result.plot("Transient")
    names = [name.lower() for name in plot.variables]
    time, value = names.index("time"), names.index("v(1)")
    return [(float(row[time].real), float(row[value].real)) for row in plot.rows]


def _pulse(a: list[float], t: float) -> float:
    v1, v2, td, tr, tf, pw, per = a
    local = (t - td) % per if t >= td else -1.0
    if local < 0:
        return v1
    if local < tr:
        return v1 + (v2 - v1) * local / tr
    if local < tr + pw:
        return v2
    if local < tr + pw + tf:
        return v2 + (v1 - v2) * (local - tr - pw) / tf
    return v1


def _sin(a: list[float], t: float) -> float:
    v0, va, freq, td, theta, phase = a
    shift = math.radians(phase)
    if t < td:
        return v0 + va * math.sin(shift)
    return v0 + va * math.exp(-(t - td) * theta) * math.sin(2 * math.pi * freq * (t - td) + shift)


def _exp(a: list[float], t: float) -> float:
    v1, v2, td1, tau1, td2, tau2 = a
    value = v1
    if t > td1:
        value += (v2 - v1) * (1 - math.exp(-(t - td1) / tau1))
    if t > td2:
        value += (v1 - v2) * (1 - math.exp(-(t - td2) / tau2))
    return value


def _sffm(a: list[float], t: float) -> float:
    v0, va, fc, mdi, fs = a
    return v0 + va * math.sin(2 * math.pi * fc * t + mdi * math.sin(2 * math.pi * fs * t))


def _pwl(a: list[float], t: float) -> float:
    points = list(zip(a[::2], a[1::2], strict=True))
    if t <= points[0][0]:
        return points[0][1]
    for (t0, v0), (t1, v1) in zip(points, points[1:], strict=False):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return points[-1][1]


_FORMULAS = {"pulse": _pulse, "sin": _sin, "exp": _exp, "sffm": _sffm, "pwl": _pwl}


@pytest.mark.parametrize(
    "line",
    [
        "V1 1 0 PULSE(0 1 1n 1n 1n 5n 10n)",
        "V1 1 0 pulse 0 1 1n 1n 1n 5n 10n",
        "V1 1 0 PULSE( 0 1 1ns 1ns 1ns 5ns 10ns )",
        "V1 1 0 PULSE({lo} {hi*2} 1n 1n 1n 5n 10n)",
        "V1 1 0 PULSE(0 1 1n\n+ 1n 1n 5n 10n)",
        "V1 1 0 SIN(0 1 100meg 2n 0 90)",
        "V1 1 0 Sin 0.5 1 100meg 0 1e7 0",
        "V1 1 0 EXP(0 1 2n 1n 10n 2n)",
        "V1 1 0 exp (0 1 2n 1n 10n 2n)",
        "V1 1 0 SFFM (0 1 100meg 2 10meg)",
        "V1 1 0 SFFM 0 1 100meg 2 10meg",
        "V1 1 0 PWL 0 0 10n 1",
        "V1 1 0 PWL(0 0 2n 3 3n 2 4n 2 4.01n 5)",
        "V1 1 0 PWL 0S 0V 10nS 1V",
        "V1 1 0 pwl 0 0\n+ 10n 1",
    ],
)
def test_functions_run_as_the_library_reads_them(solver: Solver, tmp_path: Path, line: str) -> None:
    """Parentheses or none, the device-field units, braced expressions and `+` lines (decision
    0030 item 2): Xyce's waveform is the manual's formula of the arguments the library reads."""
    text = _text(line, extra=".param lo=0 hi=0.5\n")
    spec = _spec(text)
    params = {"lo": 0.0, "hi*2": 1.0}
    args = [params[arg.text] if arg.text in params else _number(arg.text) for arg in spec.args]
    formula = _FORMULAS[spec.name.lower()]
    for time, value in _waveform(run(solver, tmp_path, text)):
        assert value == pytest.approx(formula(args, time), abs=1e-6), time


def test_pat_follows_its_bit_string(solver: Solver, tmp_path: Path) -> None:
    """PAT(VHI VLO TD TR TF TSAMPLE DATA) ([xyce-ref] §2.3.10 p227): each bit holds for TSAMPLE;
    the bits the library reads are the levels Xyce writes in the middle of each sample."""
    text = _text("V1 1 0 PAT(5 0 0 1n 1n 5n b0110)", tran=".tran 0.1n 20n")
    bits = _spec(text).args[6].text[1:]
    points = _waveform(run(solver, tmp_path, text))
    for index, bit in enumerate(bits):
        middle = 5e-9 * index + 2.5e-9
        (_, value) = min(points, key=lambda point: abs(point[0] - middle))
        assert value == pytest.approx(5.0 if bit == "1" else 0.0, abs=1e-3)


def _levels(solver: Solver, folder: Path, line: str, tran: str) -> list[float]:
    return [value for _, value in _waveform(run(solver, folder, _text(line, tran=tran)))]


def test_pat_repeats_with_r_and_ignores_a_positional_r(solver: Solver, tmp_path: Path) -> None:
    """Without `R=` a pattern runs once; `R=` after the list repeats it. A positional eighth field,
    which the manual documents as R, is ignored: the waveform is the one without it (point 9;
    `manual-error`, the library refuses it with the hint `R=`)."""
    tran = ".tran 0.1n 40n"
    once = _levels(solver, tmp_path / "once", "V1 1 0 PAT(5 0 0 1n 1n 5n b10)", tran)
    positional = _levels(solver, tmp_path / "pos", "V1 1 0 PAT(5 0 0 1n 1n 5n b10 3)", tran)
    repeated = _levels(solver, tmp_path / "kw", "V1 1 0 PAT(5 0 0 1n 1n 5n b10) R=3", tran)
    assert max(once[len(once) // 2 :]) == pytest.approx(0.0, abs=1e-6)
    assert positional == pytest.approx(once)
    assert max(repeated[len(repeated) // 2 :]) == pytest.approx(5.0, abs=1e-3)
    _refused("V1 1 0 PAT(5 0 0 1n 1n 5n b10 3)")


def test_pwl_td_and_r_after_the_list(solver: Solver, tmp_path: Path) -> None:
    """`TD=` delays the waveform and `R=` repeats it from that time, in either order, after the
    pairs (decision 0030 item 5)."""
    tran = ".tran 0.1n 20n"
    pairs = "0 0 2n 1 4n 0"
    for name, line in {
        "td-r": f"V1 1 0 PWL {pairs} TD=3n R=0",
        "r-td": f"V1 1 0 PWL({pairs}) R=0 TD=3n",
    }.items():
        spec = _spec(_text(line))
        assert sorted(p.name.lower() for p in spec.params) == ["r", "td"]
        points = _waveform(run(solver, tmp_path / name, _text(line, tran=tran)))
        for time, value in points:
            local = (time - 3e-9) % 4e-9 if time >= 3e-9 else -1.0
            expected = 0.0 if local < 0 else _pwl([0, 0, 2e-9, 1, 4e-9, 0], local)
            assert value == pytest.approx(expected, abs=1e-3), (name, time)


_CSV = "0,0\n2e-9,1\n4e-9,0\n"


@pytest.mark.parametrize(
    "line",
    ['V1 1 0 PWL FILE "g.csv"', "V1 1 0 pwl file g.csv", 'V1 1 0 PWL FILE "g.csv" TD=0 R=0'],
)
def test_pwl_file_reads_its_points(solver: Solver, tmp_path: Path, line: str) -> None:
    """`FILE` and a double-quoted or bare path ([xyce-ref] §2.3.10 p228–229), which the library
    holds as the parameter `FILE` and never reads."""
    text = _text(line, tran=".tran 0.1n 4n")
    (file, *_) = _spec(text).params
    assert file.name.lower() == "file" and file.value.text == "g.csv"
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "g.csv").write_text(_CSV, encoding="utf-8", newline="\n")
    for time, value in _waveform(run(solver, tmp_path, text)):
        assert value == pytest.approx(_pwl([0, 0, 2e-9, 1, 4e-9, 0], time), abs=1e-6)


def test_pwl_file_resolves_against_the_working_directory(solver: Solver, tmp_path: Path) -> None:
    """Xyce looks for a relative path in the working directory, not the netlist's folder, so the
    document layer gives `FILE` no file reference (point 12)."""
    text = _text('V1 1 0 PWL FILE "g.csv"', tran=".tran 0.1n 4n")
    outcomes = {}
    for where in ("netlist", "working"):
        folder = tmp_path / where
        (folder / "sub").mkdir(parents=True)
        (folder / "sub" / "probe.cir").write_text(text, encoding="utf-8", newline="\n")
        data = folder / "sub" / "g.csv" if where == "netlist" else folder / "g.csv"
        data.write_text(_CSV, encoding="utf-8", newline="\n")
        completed = subprocess.run(
            [str(solver.path), str(folder / "sub" / "probe.cir")],
            capture_output=True,
            check=False,
            cwd=folder,
            stdin=subprocess.DEVNULL,
            timeout=60,
        )
        outcomes[where] = completed.returncode
    assert outcomes == {"netlist": 1, "working": 0}


def _refused(line: str, extra: str = "") -> None:
    with pytest.raises(ParseError):
        Netlist.from_text(_text(line, extra=extra), dialect=_XYCE)


@pytest.mark.parametrize(
    "line",
    [
        "V1 1 0 SIN(0 1 100meg) AC 1",
        "V1 1 0 PULSE(0 1 1n 1n 1n 5n 10n",
        "V1 1 0 PULSE 0 1 1n 1n 1n 5n 10n)",
        "V1 1 0 PULSE(V2=1 V1=0.5)",
        "V1 1 0 PULSE(0 1 TD=10n)",
        "V1 1 0 PULSE(0 1) TD=10n",
        "V1 1 0 SIN(0 1 100meg TD=10n)",
        "V1 1 0 PWL 0 0 10n",
        "V1 1 0 PWL TD=5n 0 0 10n 1",
        "V1 1 0 PWL(0 0 2n 1 4n 0 R=0)",
        "V1 1 0 PAT(5 0 0 1n 1n 5n b01 R=1)",
    ],
    ids=[
        "function-before-ac",
        "unclosed",
        "unopened",
        "keywords",
        "keyword-inside",
        "keyword-after",
        "keyword-on-sin",
        "odd-pwl",
        "td-before-the-list",
        "r-inside-the-parentheses",
        "pat-r-inside",
    ],
)
def test_xyce_runs_what_the_library_refuses(solver: Solver, tmp_path: Path, line: str) -> None:
    """Forms Xyce runs that the library refuses (rows `refuses/runs`, `manual` or `imprecise`):
    a function before `AC`, unbalanced parentheses, keyword arguments, an odd PWL count, `TD=` or
    `R=` before the list or inside the parentheses."""
    _refused(line)
    assert run(solver, tmp_path, _text(line)).ok


@pytest.mark.parametrize(
    ("line", "short"),
    [
        ("V1 1 0 PULSE(0 1 1n 1n 1n 5n 10n 7)", "V1 1 0 PULSE(0 1 1n 1n 1n 5n 10n)"),
        ("V1 1 0 SIN(0 1 100meg 0 0 90 9)", "V1 1 0 SIN(0 1 100meg 0 0 90)"),
        ("V1 1 0 EXP(0 1 2n 1n 10n 2n 5)", "V1 1 0 EXP(0 1 2n 1n 10n 2n)"),
        ("V1 1 0 SFFM(0 1 100meg 2 10meg 5)", "V1 1 0 SFFM(0 1 100meg 2 10meg)"),
        ("V1 1 0 PAT(5 0 0 1n 1n 5n b010 1 7)", "V1 1 0 PAT(5 0 0 1n 1n 5n b010)"),
    ],
    ids=["pulse", "sin", "exp", "sffm", "pat"],
)
def test_xyce_ignores_extra_arguments(
    solver: Solver, tmp_path: Path, line: str, short: str
) -> None:
    """A count above the function's most runs as if the extra arguments were not there (point 6;
    `refuses/ignores`)."""
    _refused(line)
    tran = ".tran 0.1n 20n"
    assert _levels(solver, tmp_path / "long", line, tran) == pytest.approx(
        _levels(solver, tmp_path / "short", short, tran), abs=1e-9
    )


@pytest.mark.parametrize(
    "line",
    [
        "V1 1 0 PULSE()",
        "V1 1 0 SIN(0 1)",
        "V1 1 0 EXP(0)",
        "V1 1 0 SFFM(0)",
        "V1 1 0 PAT(5 0 0 1n 1n 5n)",
        "V1 1 0 PAT(5 0 0 1n 1n 5n 010)",
        "V1 1 0 PAT(5 0 0 1n 1n 5n b0120)",
        "V1 1 0 PAT(5 0 0 1n 1n 5n {b010})",
        "V1 1 0 PWL 1",
        "V1 1 0 PWL",
        "V1 1 0 PULSE(0,1,1n,1n,1n,5n,10n)",
        "V1 1 0 PWL 0,0 10n,1",
        "V1 1 0 PWL (0,0) (10n,1)",
        "V1 1 0 PULSE(0 hi 1n 1n 1n 5n 10n)",
        "V1 1 0 SINE(0 1 100meg)",
        "V1 1 0 SIN(0 1 100meg) DC 1",
        "V1 1 0 PWL 0 0 2n 1 4n 0 R",
        'V1 1 0 PWL FILE="g.csv"',
    ],
)
def test_xyce_stops_on(solver: Solver, tmp_path: Path, line: str) -> None:
    """Too few arguments, a DATA field that is not a bit string, a comma, a bare name, `SINE`, a
    function before `DC`, a bare `R` and `FILE=`: Xyce stops, and the library refuses each."""
    _refused(line, extra=".param hi=1\n")
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "g.csv").write_text(_CSV, encoding="utf-8", newline="\n")
    assert not run(solver, tmp_path, _text(line, extra=".param hi=1\n")).ok


@pytest.mark.parametrize(
    "line",
    [
        'V1 1 0 PWL FILE "missing.csv"',
        "V1 1 0 PWL 0 0 2n 1 4n 0 R=10n",
        "V1 1 0 PWL 0 0 4n 1 R=-1n",
    ],
    ids=["missing-file", "r-past-the-last-time", "negative-r"],
)
def test_xyce_stops_on_what_the_library_reads(solver: Solver, tmp_path: Path, line: str) -> None:
    """A missing file and an `R=` outside 0 <= R < the last time stop Xyce; the library reads both,
    since it never reads the file and does not check R's range (rows `reads/stops`,
    `library-limit`)."""
    _spec(_text(line))
    assert not run(solver, tmp_path, _text(line)).ok


@pytest.mark.parametrize(
    "lines",
    [
        'V1 1 0 PWL(FILE "g.csv")',
        'V1 1 0 PWL FILE "g.csv" FILE "h.csv"',
        'V1 1 0 PWL FILE "g.csv" 10n 7',
    ],
    ids=["parentheses", "second-file", "extra-pairs"],
)
def test_xyce_reads_a_file_form_the_library_refuses(
    solver: Solver, tmp_path: Path, lines: str
) -> None:
    """Parentheses around the FILE form run; a second `FILE` or pairs after the path are ignored
    (Xyce reads the first file; rows `refuses/runs` and `refuses/ignores`)."""
    _refused(lines)
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "g.csv").write_text(_CSV, encoding="utf-8", newline="\n")
    (tmp_path / "h.csv").write_text("0,5\n1e-9,5\n", encoding="utf-8", newline="\n")
    points = _waveform(run(solver, tmp_path, _text(lines, tran=".tran 0.1n 4n")))
    for time, value in points:
        assert value == pytest.approx(_pwl([0, 0, 2e-9, 1, 4e-9, 0], time), abs=1e-6)


def test_a_second_function_is_ignored_or_stops(solver: Solver, tmp_path: Path) -> None:
    """Xyce silently ignores a second function after a function with all its arguments (a full
    PULSE, then SIN, runs the PULSE) and stops when the first leaves arguments unwritten, taking
    the next function's fields for them; the library refuses every second function (point 2)."""
    full = "V1 1 0 PULSE(0 1 1n 1n 1n 5n 10n)"
    two = f"{full} SIN(0 1 100meg)"
    _refused(two)
    tran = ".tran 0.1n 20n"
    first = _levels(solver, tmp_path / "first", full, tran)
    assert _levels(solver, tmp_path / "two", two, tran) == pytest.approx(first, abs=1e-9)
    short = "V1 1 0 SIN(0 1 100meg) PULSE(0 1 1n 1n 1n 5n 10n)"
    _refused(short)
    assert not run(solver, tmp_path / "short", _text(short)).ok


# `.HB` and a DC sweep of a function source (point 15; open from X-M2): print mode, as `.HB` needs.
_HB = "probe\nV1 1 0 DC 1 SIN(0.3 1 1k)\nR1 1 2 1k\nR2 2 0 1k\n{lines}.print dc v(1)\n.end\n"


def _prn_column(result: Run, name: str) -> list[float]:
    assert result.ok and result.prn_bytes is not None, f"{result.log}\n{result.stderr}"
    rows = result.prn_bytes.decode().splitlines()
    index = [word.lower() for word in rows[0].split()].index(name)
    return [float(row.split()[index]) for row in rows[1:] if row[:1].isdigit()]


def test_under_hb_a_dc_sweep_uses_the_functions_time_zero_value(
    solver: Solver, tmp_path: Path
) -> None:
    """With a `.HB` line, a `.DC` sweep of a source with a function writes the function's value at
    time 0 (here SIN's offset, 0.3), not the swept DC value; without `.HB` it follows the sweep.
    The two `.DC` lines join into one sweep, the first innermost, and `.PRINT DC` agrees with the
    first analysis line. The manual is silent (a row, `imprecise`; no diagnostic, decision 0030
    item 7)."""
    sweeps = ".dc V1 0 1 0.5\n{hb}.dc R1 1k 2k 1k\n"
    plain = run(solver, tmp_path / "plain", _HB.format(lines=sweeps.format(hb="")), mode="print")
    assert _prn_column(plain, "v(1)") == pytest.approx([0.0, 0.5, 1.0] * 2)
    text = _HB.format(lines=sweeps.format(hb=".hb 1k\n"))
    Netlist.from_text(text, dialect=_XYCE)
    with_hb = run(solver, tmp_path / "hb", text, mode="print")
    assert _prn_column(with_hb, "v(1)") == pytest.approx([0.3] * 6)
