"""XyceNF 7.10 probes of `.PRINT` (X-M2.1 C3; decision 0029 item 5; `XY-PRT-001`).

Each probe is a minimal netlist authored here and run with ``Xyce`` through
``tests/support/xyce.py`` in the harness's ``print`` mode (no ``-r``, so `.PRINT` writes its
files), in a temporary folder; nothing Xyce writes is committed. Xyce runs a netlist with a `SIN`
source, which `.HB` needs; the library reads the same lines with a DC source, since the transient
source functions are X-M3's. The probes back `PRINT_TYPE_MISMATCH`: Xyce checks every `.PRINT`
type against the first analysis line other than `.OP` and stops on a type that does not agree
with it, and writes nothing for an analysis's type when another analysis runs. The library's own
side is pinned by ``tests/grammar/xyce/test_xyce_print.py`` and
``tests/document/test_xyce_directive_findings.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import DiagnosticCode, Netlist, ParseError
from netlistmod.dialects import _XYCE
from netlistmod.model.nodes import PrintDirective
from tests.grammar.xyce.test_xyce_print import PRINT_TYPES
from tests.support.solvers import Solver
from tests.support.xyce import Run, run

pytestmark = pytest.mark.solver("xyce")

_SOLVER_HEAD = "probe\nV1 1 0 DC 1 AC 1 SIN(0 1 1k)\nR1 1 2 1k\nR2 2 0 1k\nC1 2 0 1n\n"
_LIBRARY_HEAD = "probe\nV1 1 0 DC 1 AC 1\nR1 1 2 1k\nR2 2 0 1k\nC1 2 0 1n\n"
_ANALYSES = {
    "tran": ".tran 1u 10u",
    "ac": ".ac dec 1 1 10",
    "dc": ".dc V1 0 1 1",
    "op": ".op",
    "noise": ".noise v(2) V1 dec 1 1 10",
    "hb": ".hb 1k",
}


def _xyce(solver: Solver, folder: Path, lines: str) -> Run:
    return run(solver, folder, f"{_SOLVER_HEAD}{lines}\n.end\n", mode="print")


def _library(lines: str) -> Netlist:
    return Netlist.from_text(f"{_LIBRARY_HEAD}{lines}\n.end\n", dialect=_XYCE)


def _mismatches(lines: str) -> list[str]:
    return [
        d.message
        for d in _library(lines).diagnostics
        if d.code is DiagnosticCode.PRINT_TYPE_MISMATCH
    ]


def _refused(lines: str) -> str:
    with pytest.raises(ParseError) as captured:
        _library(lines)
    return captured.value.reason


def _messages(result: Run) -> str:
    return " | ".join(item.message for item in result.diagnostics)


def _written(result: Run) -> set[str]:
    """The files the run wrote beside the netlist, by their suffix after `probe.cir`."""
    names = {path.name for path in result.netlist.parent.iterdir()}
    return {name.removeprefix("probe.cir") for name in names} - {""}


# What each type writes with its own analysis, where the type alone decides it.
_OWN_RUN = {
    "TRAN": ("tran", ".prn"),
    "AC": ("ac", ".FD.prn"),
    "AC_IC": ("ac\n.op", ".TD.prn"),
    "DC": ("dc", ".prn"),
    "NOISE": ("noise", ".NOISE.prn"),
    "HB": ("hb", ".HB.FD.prn"),
    "HB_FD": ("hb", ".HB.FD.prn"),
    "HB_IC": ("hb", ".hb_ic.prn"),
    "HB_STARTUP": ("hb", None),
    "HB_TD": ("hb", ".HB.TD.prn"),
    "ES": ("dc", None),
    "PCE": ("dc", None),
    "HOMOTOPY": ("tran", None),
    "SENS": ("tran", None),
    "TRANADJOINT": ("tran", None),
}


def _lines(analysis: str) -> str:
    """The analysis lines of `_OWN_RUN`'s key, `ac\\n.op` for AC_IC."""
    first, *rest = analysis.split("\n")
    return "\n".join([_ANALYSES[first], *rest])


@pytest.mark.parametrize("kind", PRINT_TYPES)
def test_each_print_type_runs_with_its_analysis(solver: Solver, tmp_path: Path, kind: str) -> None:
    """Each type of the manual's list ([xyce-ref] §2.1.31 p128) runs under an analysis it agrees
    with, and an analysis's type writes its file there; the library reads it as a
    `PrintDirective` and reports no mismatch."""
    analysis, written = _OWN_RUN[kind]
    lines = f".print {kind} v(2)\n{_lines(analysis)}"
    result = _xyce(solver, tmp_path, lines)
    assert result.ok, f"{result.log}\n{result.stderr}"
    if written is not None:
        assert written in _written(result)
    printed = [line.item for line in _library(lines).lines if isinstance(line.item, PrintDirective)]
    assert [item.print_type for item in printed] == [kind]
    assert _mismatches(lines) == []


@pytest.mark.parametrize("kind", ["tran", "Tran", "hb_fd", "Ac_Ic"])
def test_a_print_type_is_read_in_any_case(solver: Solver, tmp_path: Path, kind: str) -> None:
    analysis, written = _OWN_RUN[kind.upper()]
    result = _xyce(solver, tmp_path, f".print {kind} v(2)\n{_lines(analysis)}")
    assert result.ok and written in _written(result)


@pytest.mark.parametrize("first", sorted(_ANALYSES))
@pytest.mark.parametrize("kind", PRINT_TYPES)
def test_the_first_analysis_decides_whether_xyce_stops(
    solver: Solver, tmp_path: Path, kind: str, first: str
) -> None:
    """Xyce stops ("Analysis type … and print type … are inconsistent") exactly where the
    library's `PRINT_TYPE_MISMATCH` says it does, for every type under every analysis."""
    lines = f".print {kind} v(2)\n{_ANALYSES[first]}"
    result = _xyce(solver, tmp_path, lines)
    inconsistent = f"Analysis type {first.upper()} and print type {kind} are inconsistent"
    stops = [message for message in _mismatches(lines) if "and stops" in message]
    if stops:
        assert result.returncode != 0 and inconsistent in _messages(result)
        assert f'("{inconsistent}")' in stops[0]
    else:
        assert result.ok, f"{result.log}\n{result.stderr}"


@pytest.mark.parametrize(
    ("lines", "inconsistent"),
    [
        (".op\n.tran 1u 10u\n.print ac v(2)", "TRAN and print type AC"),
        (".tran 1u 10u\n.op\n.print dc v(2)", "TRAN and print type DC"),
        (".tran 1u 10u\n.ac dec 1 1 10\n.print ac v(2)", "TRAN and print type AC"),
        (".hb 1k\n.tran 1u 10u\n.print tran v(2)", "HB and print type TRAN"),
        (
            ".ac dec 1 1 10\n.tran 1u 10u\n.print ac v(2)\n.print tran v(2)",
            "AC and print type TRAN",
        ),
    ],
)
def test_the_first_analysis_but_op_is_the_one_checked(
    solver: Solver, tmp_path: Path, lines: str, inconsistent: str
) -> None:
    """`.OP` is checked only when it is the only analysis; every `.PRINT` line is checked."""
    result = _xyce(solver, tmp_path, lines)
    assert result.returncode != 0
    assert f"Analysis type {inconsistent} are inconsistent" in _messages(result)
    assert any(f"type {inconsistent} are inconsistent" in m for m in _mismatches(lines))


@pytest.mark.parametrize(
    "lines",
    [
        ".tran 1u 10u\n.ac dec 1 1 10\n.print tran v(2)",
        ".ac dec 1 1 10\n.tran 1u 10u\n.print ac v(2)",
        ".ac dec 1 1 10\n.noise v(2) V1 dec 1 1 10\n.print ac v(2)",
        ".dc V1 0 1 1\n.tran 1u 10u\n.print dc v(2)",
        ".noise v(2) V1 dec 1 1 10\n.tran 1u 10u\n.print noise v(2)",
        ".hb 1k\n.tran 1u 10u\n.print hb v(2)",
        ".tran 1u 10u\n.hb 1k\n.print tran v(2)",
        ".op\n.print tran v(2)",
        ".op\n.print ac v(2)",
        ".op\n.print ac_ic v(2)",
        ".op\n.print noise v(2)",
        ".op\n.print hb_fd v(2)",
    ],
)
def test_a_type_whose_analysis_does_not_run_writes_nothing(
    solver: Solver, tmp_path: Path, lines: str
) -> None:
    """Xyce runs the last analysis (`.HB` taking part) and writes no `.PRINT` file for a type of
    another analysis; the library says so. (`.NOISE` writes its own `_noise.dat` whatever the
    `.PRINT` lines.)"""
    result = _xyce(solver, tmp_path, lines)
    assert result.ok, f"{result.log}\n{result.stderr}"
    assert not {name for name in _written(result) if name.endswith((".prn", ".csv"))}
    (message,) = _mismatches(lines)
    assert message.endswith("and writes nothing for this line")


def test_a_dc_type_under_op_writes_its_file(solver: Solver, tmp_path: Path) -> None:
    result = _xyce(solver, tmp_path, ".op\n.print dc v(2)")
    assert result.ok and result.prn_bytes is not None
    assert _mismatches(".op\n.print dc v(2)") == []


def test_tr_runs_as_tran(solver: Solver, tmp_path: Path) -> None:
    """`.PRINT TR` runs as TRAN, though the manual's type is TRAN; the library refuses it with the
    hint "write `TRAN`" (a discrepancies.md row)."""
    result = _xyce(solver, tmp_path, ".print tr v(2)\n.tran 1u 10u")
    assert result.ok and result.prn_bytes is not None
    assert "(write `TRAN`)" in _refused(".print tr v(2)\n.tran 1u 10u")


@pytest.mark.parametrize(
    "kind", ["foo", "transient", "op", "sp", "noise_ic", "mpde", "format=csv tran"]
)
def test_a_type_outside_the_list_stops_xyce(solver: Solver, tmp_path: Path, kind: str) -> None:
    """A word outside the manual's list in the type's place stops Xyce, as the library refuses
    it."""
    lines = f".print {kind} v(2)\n.tran 1u 10u"
    result = _xyce(solver, tmp_path, lines)
    assert result.returncode != 0 and "are inconsistent" in _messages(result)
    assert "is not a `.PRINT` type" in _refused(lines)


def test_a_print_without_a_variable_runs(solver: Solver, tmp_path: Path) -> None:
    """`.PRINT TRAN` alone runs and writes only the index and the time; the manual writes at
    least one output variable, and the library refuses it (a discrepancies.md row)."""
    result = _xyce(solver, tmp_path, ".print tran\n.tran 1u 10u")
    assert result.ok and result.prn_bytes is not None
    assert result.prn_bytes.decode().splitlines()[0].split() == ["Index", "TIME"]
    assert "has no output variable" in _refused(".print tran\n.tran 1u 10u")


# A `.PRINT` without a print type is never run: Xyce 7.10 crashed on one probe and hung on
# another (a discrepancies.md row, as for the conditions that hang it).


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("v(2), v(1)", "undefined symbol in .PRINT command: ,"),
        ("v(99)", "undefined symbol in .PRINT command: node 99"),
    ],
)
def test_the_body_is_not_checked(solver: Solver, tmp_path: Path, body: str, message: str) -> None:
    """Xyce stops on a comma or an unknown node among the output variables; the library keeps the
    body as text and does not check it (a discrepancies.md row)."""
    lines = f".print tran {body}\n.tran 1u 10u"
    result = _xyce(solver, tmp_path, lines)
    assert result.returncode != 0 and message in _messages(result)
    (printed,) = [
        line.item for line in _library(lines).lines if isinstance(line.item, PrintDirective)
    ]
    assert printed.body_text == body
