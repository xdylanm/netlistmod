"""XyceNF 7.10 probes of the P port (X-M3 B5; decision 0030 items 6 and 7; xm3-tasks 5.1 points
16 to 26).

Each probe is a minimal netlist authored here and run with ``Xyce`` through
``tests/support/xyce.py``, in a temporary folder; nothing Xyce writes is committed. Outside
`.LIN` a port is a V source in series with Z0 ([xyce-ref] §2.3.11 p231): with a 50 Ohm load on
node 1, ``v(1)`` is ``V * 50 / (50 + Z0)``, which the probes compute from the fields the library
reads. `.LIN` needs print mode (no ``-r``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import Netlist, NumericValue, ParseError
from netlistmod.dialects import _XYCE
from netlistmod.model.nodes import PortSource
from tests.support.solvers import Solver
from tests.support.xyce import op, run

pytestmark = pytest.mark.solver("xyce")


def _text(lines: str, analysis: str = ".op") -> str:
    return f"probe\n.param zz=100 n=1\n{lines}\nR1 1 0 50\n{analysis}\n.end\n"


def _port(text: str) -> PortSource:
    port = Netlist.from_text(text, dialect=_XYCE).element("P1")
    assert isinstance(port, PortSource)
    return port


def _refused(lines: str) -> None:
    with pytest.raises(ParseError):
        Netlist.from_text(_text(lines), dialect=_XYCE)


@pytest.mark.parametrize(
    ("lines", "z0"),
    [
        ("P1 1 0 1 port=1", 50.0),
        ("P1 1 0 DC 1 port=1", 50.0),
        ("P1 1 0 1 port = 1 Z0 = 100", 100.0),
        ("P1 1 0 1 z0=100 PORT=1", 100.0),
        ("P1 1 0 1 port=1 z0={zz}", 100.0),
        ("P1 1 0 1 port={n} z0='zz'", 100.0),
        ("P1 1 0 1 port=1 z0=100ohm", 100.0),
        ("P1 1 0 1 port=1 z0=0", 0.0),
        ("p1 1 0 1\n+ port=1\n+ z0=100", 100.0),
        ("P1 1 0 1 port=1 z0=100 AC 1 30 SIN(0 1 1k)", 100.0),
    ],
)
def test_a_port_is_a_source_behind_z0(
    solver: Solver, tmp_path: Path, lines: str, z0: float
) -> None:
    """DC, then `port=` and `Z0=` in either order (default 50), then AC and the function: the
    operating point is the DC value behind Z0 (decision 0030 item 6)."""
    text = _text(lines)
    port = _port(text)
    written = [p for p in port.params if p.name.lower() == "z0"]
    assert port.dc is not None and port.dc.text == "1"
    if written and isinstance(written[0].value, NumericValue):
        assert written[0].value.text.lower().removesuffix("ohm") == f"{z0:g}"
    assert op(solver, tmp_path, text)["v(1)"] == pytest.approx(50 / (50 + z0))


def test_a_port_runs_under_dc_tran_and_ac(solver: Solver, tmp_path: Path) -> None:
    """`.DC P1` sweeps the port's DC value, `.TRAN` runs its function and `.AC` its AC part, as on
    a V source (point 22)."""
    dc = run(solver, tmp_path / "dc", _text("P1 1 0 0 port=1", ".dc P1 0 2 1"))
    assert dc.ok, dc.log
    assert [float(v.real) for v in dc.plot("DC").column("v(1)")] == pytest.approx([0, 0.5, 1])
    tran = run(solver, tmp_path / "tran", _text("P1 1 0 port=1 PWL 0 0 1n 2", ".tran 0.1n 1n"))
    assert tran.ok, tran.log
    assert float(tran.plot("Transient").column("v(1)")[-1].real) == pytest.approx(1.0)
    ac = run(solver, tmp_path / "ac", _text("P1 1 0 port=1 AC 1", ".ac lin 1 1k 1k"))
    assert ac.ok, ac.log
    assert abs(ac.plot("AC").column("v(1)")[0]) == pytest.approx(0.5)


def test_a_port_stands_in_a_subcircuit_body(solver: Solver, tmp_path: Path) -> None:
    text = _text(".subckt pp a\nP1 a 0 1 port=1\n.ends\nX1 1 pp")
    Netlist.from_text(text, dialect=_XYCE)
    assert op(solver, tmp_path, text)["v(1)"] == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("lines", "v1"),
    [
        ("P1 1 0 1", 1.0),
        ("P1 1 0 1 z0=100", 1.0),
        ("P1 1 0 1 port=0", 0.5),
        ("P1 1 0 1 port=-1", 0.5),
        ("P1 1 0 1 port=+1", 0.5),
        ("P1 1 0 1 port=1.0", 0.5),
        ("P1 1 0 1 port 1", 0.5),
        ("P1 1 0 1 port=1 z0=100+10j", 1 / 3),
        ("P1 1 0 1 port=1 z0 100", 1 / 3),
        ("P1 1 0 1 AC 1 port=1", 0.5),
        ("P1 1 0 1 SIN(0 1 1k) port=1", 0.5),
        ("P1 1 0 1, port=1", 0.5),
        ("P1 1 0 1 port=1 AC", 0.5),
    ],
    ids=[
        "no-port",
        "no-port-with-z0",
        "port-0",
        "port-negative",
        "port-signed",
        "port-decimal",
        "port-without-equals",
        "complex-z0",
        "z0-without-equals",
        "ac-before-port",
        "function-before-port",
        "comma",
        "bare-ac",
    ],
)
def test_xyce_runs_what_the_library_refuses(
    solver: Solver, tmp_path: Path, lines: str, v1: float
) -> None:
    """Forms Xyce runs that the library refuses (rows `refuses/runs`): without `port=` it is a
    plain V source (no Z0); a port number of 0, a negative, a signed or decimal one; `port 1`
    and `Z0 100` without `=`; a complex Z0, whose imaginary part Xyce drops; `port=` after the AC
    part or the function; a comma; a bare `AC`."""
    _refused(lines)
    assert op(solver, tmp_path, _text(lines))["v(1)"] == pytest.approx(v1)


@pytest.mark.parametrize(
    "lines",
    [
        "P1 1 0 1 port=1.5",
        "P1 1 0 1 port=1e0",
        "P1 1 0 1 port=1k",
        "P1 1 0 1 port=n",
        "P1 1 0 1 port=1 port=2",
        "P1 1 0 1 port=1 z0=100 z0=25",
        "P1 1 0 1 port=1 z0=zz",
        "P1 1 0 1 port=1 zo=100",
        "P1 1 0 1 port=1 M=2",
        "P1 1 0 1 port=1 foo=2",
        "P1 1 0 port=1 DC 1",
        "P1 1 0 port=1 1",
        "P1 1 0 z0=100 1 port=1",
        "P1 1 port=1",
    ],
)
def test_xyce_stops_on(solver: Solver, tmp_path: Path, lines: str) -> None:
    """A port number that is not an integer literal or a formula, a second `port=` or `Z0=`, a bare
    name, `ZO`, another parameter, the DC part after `port=` or `Z0=`, and one node: Xyce stops,
    and the library refuses each."""
    _refused(lines)
    assert not run(solver, tmp_path, _text(lines)).ok


@pytest.mark.parametrize(
    ("lines", "v1"),
    [("V1 1 0 1 port=1", 0.5), ("V1 1 0 1 z0=100", 1.0), ("V1 1 0 1 port=1 z0=100", 1 / 3)],
    ids=["port", "z0", "port-and-z0"],
)
def test_v_runs_port_and_ignores_z0(solver: Solver, tmp_path: Path, lines: str, v1: float) -> None:
    """Undocumented: `port=` on a V line runs and makes V a port, behind its `Z0=` (50 Ohm by
    default) and a `.LIN` port (below); `Z0=` on V without `port=` is ignored. The library
    refuses both on V (point 24)."""
    _refused(lines)
    assert op(solver, tmp_path, _text(lines))["v(1)"] == pytest.approx(v1)


_LIN = "lin\n{lines}R1 1 2 50\n.AC LIN 1 1k 1k\n.LIN sparcalc=1 format=touchstone\n.end\n"


@pytest.mark.parametrize(
    ("lines", "ok"),
    [
        ("P1 1 0 port=1\nP2 2 0 port=2\n", True),
        ("P2 1 0 port=2\nP1 2 0 port=1\n", True),
        ("V1 1 0 port=1\nP2 2 0 port=2\n", True),
        ("P1 1 0 port=1\nP2 2 0 port=3\n", False),
        ("P1 1 0 port=1\nP2 2 0 port=1\n", False),
        ("P1 1 0 port=2\nP2 2 0 port=3\n", False),
        (".subckt pp a\nP1 a 0 port=1\n.ends\nX1 1 pp\nX2 2 pp\n", False),
    ],
    ids=["one-two", "any-order", "v-port", "gap", "repeat", "from-two", "twice-in-a-body"],
)
def test_lin_needs_the_ports_numbered_one_to_n(
    solver: Solver, tmp_path: Path, lines: str, ok: bool
) -> None:
    """`.LIN` aborts unless the ports of the flattened netlist are numbered exactly 1..N, in any
    order; without `.LIN` any numbering runs. The library does not check it (a row, `reads/stops`,
    `library-limit`; decision 0030 item 7), and reads each P line; a V line with `port=` is a
    port to `.LIN` too, which the library refuses."""
    text = _LIN.format(lines=lines)
    if lines.startswith("V1"):
        with pytest.raises(ParseError):
            Netlist.from_text(text, dialect=_XYCE)
    else:
        Netlist.from_text(text, dialect=_XYCE)
    assert run(solver, tmp_path, text, mode="print").ok is ok
