"""XyceNF 7.10 probes of the closed list of dot-commands, `.PREPROCESS ADDRESISTORS` and
`REMOVEUNUSED`, and directives in a subcircuit body (X-M2 B6; decision 0028 items 1 and 2;
xm2-tasks 5.1 points 1 to 5).

Each probe is a minimal netlist authored here and run with ``Xyce`` through
``tests/support/xyce.py``, in a temporary folder; nothing Xyce writes is committed (the files a
command writes, such as `<netlist>_xyce.cir` or a `.SAVE` file, stay in the folder). `.HB`, `.LIN`
and `.EMBEDDEDSAMPLING` abort under ``-r`` ("-r and -a outputs are not supported"), so they run
in the harness's ``print`` mode. `.INITCOND` without arguments hangs Xyce 7.10 and is never run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import DiagnosticCode, Netlist, ParseError, UnknownDirective, UnsupportedConstruct
from netlistmod.dialects import _XYCE
from tests.support.solvers import Solver
from tests.support.xyce import Mode, Run, names, op, run

pytestmark = pytest.mark.solver("xyce")

_DIVIDER = "probe\nV1 1 0 2 AC 1\nR1 1 2 1k\nR2 2 0 1k\nC1 2 0 1n\n"
_SINE = "probe\nV1 1 0 SIN(0 1 1k)\nR1 1 2 1k\nR2 2 0 1k\nC1 2 0 1n\n"


def _library(text: str) -> Netlist:
    return Netlist.from_text(text, dialect=_XYCE)


def _refused(text: str) -> str:
    with pytest.raises(ParseError) as captured:
        _library(text)
    return captured.value.reason


def _messages(result: Run) -> str:
    return " | ".join(item.message for item in result.diagnostics)


def _files(result: Run) -> set[str]:
    return {path.name for path in result.netlist.parent.iterdir()}


# The untyped commands (XY-DIR-001, XY-SAV-001)

_UNTYPED: dict[str, tuple[str, str, Mode, str]] = {
    # name: (head, lines, mode, a file the run writes)
    ".PRINT": (_DIVIDER, ".print tran v(2)\n.tran 1u 10u", "print", "probe.cir.prn"),
    ".FOUR": (_SINE, ".four 1k v(2)\n.tran 1u 1m", "run", "probe.cir.four0"),
    ".FFT": (_SINE, ".fft v(2)\n.tran 1u 1m", "run", "probe.cir.fft0"),
    ".RESULT": (_DIVIDER, ".result {v(2)}\n.step R1 1k 2k 1k\n.op", "run", "probe.cir.res"),
    ".SAVE": (_DIVIDER, ".save type=ic file=saved.ic\n.op", "run", "saved.ic"),
    ".SENS": (
        _DIVIDER,
        ".sens objfunc={v(2)} param=R1:R\n.print sens v(2)\n.dc V1 2 2 1",
        "print",
        "probe.cir.SENS.prn",
    ),
    ".NOISE": (
        _DIVIDER,
        ".noise v(2) V1 dec 5 1k 1meg\n.print noise inoise onoise",
        "print",
        "probe.cir.NOISE.prn",
    ),
    ".HB": (_SINE, ".print hb v(2)\n.hb 1k", "print", "probe.cir.HB.FD.prn"),
    ".LIN": (
        _DIVIDER,
        ".lin sparcalc=0\n.ac dec 5 1k 1meg\n.print ac v(2)",
        "print",
        "probe.cir.FD.prn",
    ),
    ".SAMPLING": (
        _DIVIDER,
        ".sampling param=R1 type=normal means=1k std_deviations=100\n"
        ".options samples numsamples=3\n.op",
        "run",
        "probe.cir.res",
    ),
    ".EMBEDDEDSAMPLING": (
        _DIVIDER,
        ".embeddedsampling param=R1 type=normal means=1k std_deviations=100\n"
        ".options embeddedsamples numsamples=3 outputs={v(2)}\n.dc V1 2 2 1",
        "print",
        "probe.cir_ensemble.dat",
    ),
}


@pytest.mark.parametrize("name", sorted(_UNTYPED))
def test_each_untyped_command_runs(solver: Solver, tmp_path: Path, name: str) -> None:
    """Each of the closed list's untyped commands runs and writes its output ([xyce-ref]
    §2.1.31, §2.1.9, §2.1.8, §2.1.32, §2.1.34, §2.1.35, §2.1.23, §2.1.13, §2.1.17, §2.1.33,
    §2.1.5; point 3), with no "Unrecognized dot line" warning; the library reads it as an
    `UnknownDirective` with `UNTYPED_DIRECTIVE_PRESERVED`."""
    head, lines, mode, written = _UNTYPED[name]
    text = f"{head}{lines}\n.end\n"
    result = run(solver, tmp_path, text, mode=mode)
    assert result.ok, f"{result.log}\n{result.stderr}"
    assert "Unrecognized dot line" not in _messages(result)
    assert written in _files(result)
    # The transient source functions are X-M3's, so the library reads the lines under test
    # with the divider's DC source.
    netlist = _library(f"{_DIVIDER}{lines}\n.end\n")
    found = [line.item for line in netlist.lines if isinstance(line.item, UnknownDirective)]
    assert name.lower() in {item.name.lower() for item in found}
    assert DiagnosticCode.UNTYPED_DIRECTIVE_PRESERVED in [d.code for d in netlist.diagnostics]


@pytest.mark.parametrize("name", [".HB", ".LIN", ".EMBEDDEDSAMPLING"])
def test_some_analyses_abort_with_a_raw_file(solver: Solver, tmp_path: Path, name: str) -> None:
    """`.HB`, `.LIN` and `.EMBEDDEDSAMPLING` abort under `-r` ("-r and -a outputs are not
    supported"), which the corpus solver test uses, so a corpus file holding one needs a
    `solver` field (a discrepancies.md row)."""
    head, lines, _, _ = _UNTYPED[name]
    if name == ".LIN":
        lines = ".lin\n.ac dec 5 1k 1meg"
    result = run(solver, tmp_path, f"{head}{lines}\n.end\n")
    assert result.returncode != 0
    assert "-r and -a outputs are not supported" in result.log + result.stderr


def test_pce_is_unrecognized_by_this_build(solver: Solver, tmp_path: Path) -> None:
    """`.PCE` is in the manual ([xyce-ref] §2.1.27 p122) but this build warns "Unrecognized dot
    line" and ignores it, and its `.OPTIONS PCES` package too; the library reads both (a
    discrepancies.md row)."""
    lines = ".pce param=R1 type=normal means=1k std_deviations=100\n.options pces foo=1\n.op"
    result = run(solver, tmp_path, f"{_DIVIDER}{lines}\n.end\n")
    assert result.ok
    assert result.warnings_at(6) and "Unrecognized dot line" in result.warnings_at(6)[0].message
    assert "Unrecognized .OPTIONS package or parameter PCES" in _messages(result)
    _library(f"{_DIVIDER}{lines}\n.end\n")


def test_a_print_line_continues(solver: Solver, tmp_path: Path) -> None:
    """A `+` line continues `.PRINT` ([xyce-ug] §4.1.3.2 p43): both vectors are printed."""
    text = f"{_DIVIDER}.print tran v(2)\n+ v(1)\n.tran 1u 10u\n.end\n"
    result = run(solver, tmp_path, text, mode="print")
    assert result.ok and result.prn_bytes is not None
    assert result.prn_bytes.decode().splitlines()[0].split() == ["Index", "TIME", "V(2)", "V(1)"]
    (printed,) = [
        line.item for line in _library(text).lines if isinstance(line.item, UnknownDirective)
    ]
    assert "v(1)" in printed.raw


def test_an_ngspice_save_stops_xyce(solver: Solver, tmp_path: Path) -> None:
    """`.SAVE` writes an operating point file and takes no vectors ([xyce-ref] §2.1.34 p152):
    ngspice's `.save v(2)` stops Xyce ("Unrecognized field in .SAVE line"). The library reads it
    as an `UnknownDirective`, never a `SaveDirective` (point 3; a discrepancies.md row)."""
    text = f"{_DIVIDER}.save v(2)\n.op\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.returncode != 0 and "Unrecognized field in .SAVE line" in _messages(result)
    items = [line.item for line in _library(text).lines]
    assert any(isinstance(item, UnknownDirective) and item.name == ".save" for item in items)


# Every other dot-command (XY-DIR-002)

_IGNORED = [
    ".TEMP 50",
    ".tf v(2) V1",
    ".probe",
    ".pz v(1) v(2) cur pol",
    ".disto dec 10 1k 1meg",
    ".mc 10 dc v(2)",
    ".plot dc v(2)",
    ".wcase dc v(2) dev",
    ".vector",
    ".watch",
    ".autoconverge",
    ".distribution x",
    ".loadbias x",
    ".savebias x",
    ".stimulus x",
    ".text x",
    ".title foo",
    ".backanno",
    ".opt reltol=1e-3",
    ".tarn 1n 2n",
    ".optoins device temp=50",
    ".frobnicate a b c",
]


@pytest.mark.parametrize("line", _IGNORED)
def test_another_dot_command_is_warned_and_ignored(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    """Table 6-1's commands ([xyce-ref] p847–848), `.title`, `.backanno`, misspellings and an
    unknown word: Xyce warns "Unrecognized dot line will be ignored" at the line and runs as if it
    were not there (point 2). The library refuses each, "not an Xyce dot-command"
    (discrepancies.md)."""
    text = f"{_DIVIDER}{line}\n.op\n.end\n"
    result = run(solver, tmp_path / "run", text)
    assert result.ok
    (warning,) = result.warnings_at(6)
    assert "Unrecognized dot line will be ignored" in warning.message
    assert op(solver, tmp_path / "op", text)["v(2)"] == pytest.approx(1.0)
    assert "not an Xyce dot-command" in _refused(text)


def test_a_misspelt_tran_leaves_no_analysis(solver: Solver, tmp_path: Path) -> None:
    """There is no prefix matching: `.tarn` is ignored, so Xyce stops with "No analysis
    specified" (point 1)."""
    result = run(solver, tmp_path, f"{_DIVIDER}.tarn 1n 2n\n.end\n")
    assert result.returncode != 0 and "No analysis specified" in _messages(result)


@pytest.mark.parametrize(
    "block",
    [".foo\nR3 2 0 1k\n.endfoo", ".if (1)\nR3 2 0 1k\n.endif", ".aliases\nR3 2 0 1k\n.endaliases"],
)
def test_the_lines_of_an_unknown_block_are_read(solver: Solver, tmp_path: Path, block: str) -> None:
    """An unknown block is no block: its opening and closing lines are each warned and ignored,
    and the lines between are circuit lines, so R3 loads node 2 (point 1). The library refuses
    the opener, so the lines between are never read."""
    text = f"{_DIVIDER}{block}\n.op\n.end\n"
    result = run(solver, tmp_path / "run", text)
    assert result.ok and len(result.warnings_at(6)) == 1 and len(result.warnings_at(8)) == 1
    assert op(solver, tmp_path / "op", text)["v(2)"] == pytest.approx(2 / 3)
    assert "not an Xyce dot-command" in _refused(text)


def test_a_control_block_stops_on_its_commands(solver: Solver, tmp_path: Path) -> None:
    """ngspice's `.control` block: Xyce reads `run` as a device line and stops ("Not enough
    fields on input line for device RUN")."""
    result = run(solver, tmp_path, f"{_DIVIDER}.control\nrun\n.endc\n.op\n.end\n")
    assert result.returncode != 0 and "device RUN" in _messages(result)


@pytest.mark.parametrize(
    ("line", "warning"),
    [(".mor ports=V1", None), (".enddata", None), (".load x.ic", ".LOAD not supported yet")],
)
def test_commands_the_binary_knows_outside_the_manual(
    solver: Solver, tmp_path: Path, line: str, warning: str | None
) -> None:
    """The binary knows `.MOR` and a lone `.ENDDATA` (silent) and `.LOAD` (a warning), none in
    the manual; the library refuses them (point 2; discrepancies.md rows)."""
    text = f"{_DIVIDER}{line}\n.op\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.ok
    if warning is None:
        assert not result.warnings_at(6) and "Unrecognized" not in _messages(result)
    else:
        assert warning in _messages(result)
    with pytest.raises(ParseError):
        _library(text)


def test_initcond_with_a_file_stops_when_the_file_is_missing(
    solver: Solver, tmp_path: Path
) -> None:
    """`.INITCOND file=x` is known to the binary and stops on a missing file ("Could not open the
    .INITCOND file"); without arguments it hangs, which is never run (discrepancies.md)."""
    result = run(solver, tmp_path, f"{_DIVIDER}.initcond file=x\n.op\n.end\n", timeout=60)
    assert result.returncode != 0 and "Could not open the .INITCOND file" in _messages(result)


# .PREPROCESS ADDRESISTORS (XY-PRE-002) and REMOVEUNUSED (XY-UNS-001)

_DANGLING = f"{_DIVIDER}R3 2 3 1k\n"
_FLOATING = f"{_DIVIDER}C3 2 3 1n\nC4 3 0 1n\n"


@pytest.mark.parametrize(
    ("head", "line", "warning"),
    [
        (_DANGLING, ".preprocess addresistors oneterminal 1g", "connected to only 1 device"),
        (_FLOATING, ".PREPROCESS ADDRESISTORS NODCPATH 1g", "does not have a DC path"),
    ],
)
def test_addresistors_writes_a_copy_and_leaves_the_run(
    solver: Solver, tmp_path: Path, head: str, line: str, warning: str
) -> None:
    """ADDRESISTORS writes `<netlist>_xyce.cir` with the resistors added and runs the netlist as
    it is ([xyce-ref] §2.1.30 p127; point 4): the same operating point, and the warning about
    node 3 that the run alone gives."""
    text = f"{head}{line}\n.op\n.end\n"
    result = run(solver, tmp_path / "with", text)
    assert result.ok and "probe.cir_xyce.cir" in _files(result)
    assert warning in _messages(result)
    plain = f"{head}.op\n.end\n"
    assert op(solver, tmp_path / "op", text) == op(solver, tmp_path / "plain", plain)
    (directive,) = [
        line.item for line in _library(text).lines if isinstance(line.item, UnknownDirective)
    ]
    assert directive.name.lower() == ".preprocess"


def test_one_addresistors_of_each_kind_runs(solver: Solver, tmp_path: Path) -> None:
    lines = ".preprocess addresistors oneterminal 1g\n.preprocess addresistors nodcpath 1g\n"
    text = f"{_DANGLING}{lines}.op\n.end\n"
    assert run(solver, tmp_path, text).ok
    _library(text)


def test_a_second_addresistors_of_one_kind_stops_xyce(solver: Solver, tmp_path: Path) -> None:
    """ "Multiple .PREPROCESS ADDRESISTORS ONETERMINAL statements" stops Xyce, as the library's
    refusal says."""
    lines = ".preprocess addresistors oneterminal 1g\n.preprocess addresistors oneterminal 1meg\n"
    text = f"{_DANGLING}{lines}.op\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.returncode != 0 and "Multiple .PREPROCESS ADDRESISTORS" in _messages(result)
    assert "stops on another" in _refused(text)


def test_addresistors_runs_in_a_body(solver: Solver, tmp_path: Path) -> None:
    """In a body it acts on the netlist, as `.PREPROCESS` does (point 4)."""
    text = (
        f"{_DANGLING}.subckt s a\nR5 a 0 1meg\n.preprocess addresistors oneterminal 1g\n.ends\n"
        "X1 2 s\n.op\n.end\n"
    )
    result = run(solver, tmp_path, text)
    assert result.ok and "probe.cir_xyce.cir" in _files(result)
    _library(text)


def test_removeunused_deletes_devices(solver: Solver, tmp_path: Path) -> None:
    """REMOVEUNUSED deletes a device whose terminals share a node ([xyce-ref] §2.1.29 p126), so
    V2 across node 3 is gone, and its branch with it; that changes the circuit (P4), so the
    library keeps the line `UnsupportedConstruct` (point 4). A second line stops Xyce."""
    head = f"{_DIVIDER}R3 2 2 1k\nV2 3 3 1\nR4 3 0 1k\n"
    kept = names(solver, tmp_path / "kept", f"{head}.op\n.end\n")
    removed = names(
        solver, tmp_path / "removed", f"{head}.preprocess removeunused r,v\n.op\n.end\n"
    )
    assert "v2_branch" in kept and "v2_branch" not in removed
    with pytest.raises(UnsupportedConstruct):
        _library(f"{head}.preprocess removeunused r,v\n.op\n.end\n")
    twice = f"{head}.preprocess removeunused v\n.preprocess removeunused r\n.op\n.end\n"
    result = run(solver, tmp_path / "twice", twice)
    assert result.returncode != 0 and "Multiple .PREPROCESS REMOVEUNUSED" in _messages(result)


# Directives in a subcircuit body (XY-DIR-003)


def _body(directive: str, top: str = ".op") -> str:
    return (
        "probe\nV1 1 0 2 AC 1\nR1 1 2 1k TC1=0.01\nR2 2 0 1k\n.subckt s a\nR5 a 0 1meg\n"
        f"{directive}\n.ends\nX1 2 s\n{top}\n.end\n"
    )


@pytest.mark.parametrize(
    ("directive", "top", "plot"),
    [
        (".tran 1n 2n", ".op", "DC transfer"),
        (".ac dec 1 1 10", ".op", "DC transfer"),
        (".dc V1 0 1 1", ".op", "DC transfer"),
        (".op", ".tran 1n 2n", "Transient"),
        (".step R1 1k 2k 1k", ".op", "DC transfer"),
        (".options device temp=127", ".op", "DC transfer"),
        (".meas dc va max v(2)", ".op", "DC transfer"),
        (".four 1k v(2)", ".tran 1n 2n", "Transient"),
        (".save type=ic file=saved.ic", ".op", "DC transfer"),
    ],
)
def test_a_directive_in_a_body_is_ignored(
    solver: Solver, tmp_path: Path, directive: str, top: str, plot: str
) -> None:
    """In a body Xyce silently ignores the analyses, `.STEP`, `.OPTIONS`, `.MEAS` and the outputs
    (decision 0028 item 2, which corrects xm1-tasks 5.1 point 16; [xyce-ref] §2.1.37 p160 allows
    only devices, `.MODEL`, `.PARAM` and `.FUNC` there): one plot of the top level's analysis, no
    step, R1 still 1k (v(2) 0.9995 with X1's 1 MΩ), no measurement, no output file. The library
    refuses each, saying Xyce ignores it there."""
    text = _body(directive, top)
    result = run(solver, tmp_path, text)
    assert result.ok and not [item for item in result.warnings if item.line is not None]
    (found,) = result.plots
    assert found.name.startswith(plot)
    index = [variable.lower() for variable in found.variables].index("v(2)")
    assert float(found.rows[0][index].real) == pytest.approx(0.9995, rel=1e-4)
    assert _files(result) == {"probe.cir", "probe.cir.raw"}
    assert " = " not in "".join(line for line in result.log.splitlines() if line.startswith("VA"))
    assert "ignores it there" in _refused(text)


def test_a_print_in_a_body_writes_nothing(solver: Solver, tmp_path: Path) -> None:
    result = run(solver, tmp_path, _body(".print dc v(2)"), mode="print")
    assert result.ok and result.prn_bytes is None


def test_a_body_table_is_invisible_at_the_top_level(solver: Solver, tmp_path: Path) -> None:
    """A `.DATA` table in a body is not the top level's: `.DC DATA=t` stops Xyce."""
    result = run(solver, tmp_path, _body(".data t\n+ r1\n+ 2k\n.enddata", ".dc data=t"))
    assert result.returncode != 0 and "Invalid sweep parameter name" in _messages(result)


def test_end_in_a_body_stops_xyce(solver: Solver, tmp_path: Path) -> None:
    result = run(solver, tmp_path, _body(".end"))
    assert result.returncode != 0 and "missing .ENDS" in _messages(result)
