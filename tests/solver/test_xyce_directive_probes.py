"""XyceNF 7.10 probes of `.OPTIONS`, `.IC`, `.DCVOLT`, `.NODESET`, `.MEASURE` and the `.DATA`
table (X-M2 B6; decision 0028 items 5 to 8; xm2-tasks 5.1 points 18 to 27, 32 and 33).

Each probe is a minimal netlist authored here and run with ``Xyce`` through
``tests/support/xyce.py``, in a temporary folder; nothing Xyce writes is committed. Where Xyce
writes what a directive sets (a node voltage at time 0, a measurement, a table's sweep points),
the probe compares it with the value the library reads from the line. An `.IC` or `.NODESET`
with an odd number of `node value` fields, and `.INITCOND` without arguments, hang Xyce 7.10 and
are never run here (discrepancies.md).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypeVar

import pytest

from netlistmod import (
    DiagnosticCode,
    IcDirective,
    MeasureDirective,
    Netlist,
    NodesetDirective,
    NumericValue,
    OptionsDirective,
    ParseError,
    Value,
)
from netlistmod.dialects import _XYCE
from tests.support.solvers import Solver
from tests.support.xyce import Plot, Run, run

pytestmark = pytest.mark.solver("xyce")

_T = TypeVar("_T")
_MEASURE = re.compile(r"^(\w+) = (\S+)", re.MULTILINE)
_PAIR = re.compile(r"name = (\S+) value = (\S+)")


def _library(text: str) -> Netlist:
    return Netlist.from_text(text, dialect=_XYCE)


def _codes(text: str) -> list[DiagnosticCode]:
    return [item.code for item in _library(text).diagnostics]


def _refused(text: str) -> str:
    with pytest.raises(ParseError) as captured:
        _library(text)
    return captured.value.reason


def _items(text: str, kind: type[_T]) -> list[_T]:
    return [line.item for line in _library(text).lines.walk() if isinstance(line.item, kind)]


def _plain(value: Value | None) -> float:
    assert isinstance(value, NumericValue), value
    text = value.text.lower().removesuffix("v")
    return float(text[:-1]) * 1e-3 if text.endswith("m") else float(text)


def _ok(solver: Solver, folder: Path, text: str) -> Run:
    result = run(solver, folder, text)
    assert result.ok, f"{result.log}\n{result.stderr}"
    return result


def _messages(result: Run) -> str:
    return " | ".join(item.message for item in result.diagnostics)


def _at(plot: Plot, name: str, row: int = 0) -> float:
    index = [variable.lower() for variable in plot.variables].index(name.lower())
    return float(plot.rows[row][index].real)


def _measures(result: Run) -> dict[str, str]:
    return {name.lower(): value for name, value in _MEASURE.findall(result.log)}


# .OPTIONS (XY-OPT-001, XY-OPT-002). R1's TC1 makes it 2k at 127 degrees and 1.27k at TNOM=0, so
# v(2) of the divider shows which temperature Xyce used: 1 at 27, 2/3 at 127.

_HOT = "probe\nV1 1 0 2\nR1 1 2 1k TC1=0.01\nR2 2 0 1k\n"


def _v2(solver: Solver, folder: Path, lines: str, head: str = _HOT) -> float:
    return _at(_ok(solver, folder, f"{head}{lines}\n.op\n.end\n").plots[0], "v(2)")


@pytest.mark.parametrize(
    "line",
    [
        ".options device temp=127",
        ".OPTIONS DEVICE TEMP = 127",
        ".Options Device Temp=127",
        ".options device\n+ temp=127",
    ],
)
def test_an_option_applies(solver: Solver, tmp_path: Path, line: str) -> None:
    """A package and `name=value` items, in any case, blanks around `=`, continued
    ([xyce-ref] §2.1.25 p96, §2.1.25.1 p97): DEVICE TEMP=127 makes R1 2k."""
    (options,) = _items(f"{_HOT}{line}\n.op\n.end\n", OptionsDirective)
    assert options.package is not None and options.package.name.lower() == "device"
    assert _v2(solver, tmp_path, line) == pytest.approx(2 / 3)


def test_option_is_a_full_synonym(solver: Solver, tmp_path: Path) -> None:
    """`.OPTION` acts as `.OPTIONS` does, which the manual does not say (point 18, observed)."""
    assert _v2(solver, tmp_path, ".option device temp=127") == pytest.approx(2 / 3)


@pytest.mark.parametrize(
    "line",
    [
        ".options timeint reltol=1e-3 abstol=1e-6",
        ".options timeint method=gear",
        ".options nonlin-tran maxstep=20",
        ".options linsol type=klu",
        ".option scale=1",
        ".options parser scale=1",
    ],
)
def test_listed_packages_run(solver: Solver, tmp_path: Path, line: str) -> None:
    """Items of several of the manual's packages, and `.OPTION SCALE=` without one
    ([xyce-ref] §2.1.25.21 p119), run with no warning at their line."""
    result = _ok(solver, tmp_path, f"{_HOT}{line}\n.op\n.end\n")
    assert not result.warnings_at(5)


@pytest.mark.parametrize(
    ("lines", "value"),
    [
        (".options device temp=127\n.options device temp=27", 127),
        (".options device temp=27\n.options device temp=127", 27),
        (".options device temp=127 temp=27", 127),
    ],
)
def test_a_repeated_option_uses_the_first_value(
    solver: Solver, tmp_path: Path, lines: str, value: int
) -> None:
    """Xyce uses the first value of a repeated item, with a warning ("duplicate DEVICE
    parameter"), as the library's `DUPLICATE_DEFINITION` says (point 21)."""
    text = f"{_HOT}{lines}\n.op\n.end\n"
    result = _ok(solver, tmp_path, text)
    assert f"Using the first value found = {value}" in _messages(result)
    assert _at(result.plots[0], "v(2)") == pytest.approx(2 / 3 if value == 127 else 1.0)
    assert DiagnosticCode.DUPLICATE_DEFINITION in _codes(text)


def test_two_output_lines_both_apply_and_a_repeated_item_takes_the_last(
    solver: Solver, tmp_path: Path
) -> None:
    """The manual allows one `.OPTIONS OUTPUT` line ([xyce-ref] §2.1.25.9 p110); Xyce applies
    each, and an item on two OUTPUT lines takes the last line's value (2 ns: six points to 10 ns,
    with the header and footer), unlike the other packages (a discrepancies.md row). The library
    reports no repeat on OUTPUT (point 21)."""
    tail = ".tran 0.1n 10n\n.print tran v(2)\n.end\n"
    lines = ".options output initial_interval=1n\n.options output initial_interval=2n\n"
    text = f"{_HOT}{lines}{tail}"
    result = run(solver, tmp_path / "repeat", text, mode="print")
    assert result.ok and result.prn_bytes is not None
    assert len(result.prn_bytes.decode().splitlines()) == 8
    assert DiagnosticCode.DUPLICATE_DEFINITION not in _codes(text)
    both = ".options output printheader=false\n.options output printfooter=false\n"
    result = run(solver, tmp_path / "both", f"{_HOT}{both}{tail}", mode="print")
    assert result.ok and result.prn_bytes is not None
    rows = result.prn_bytes.decode().splitlines()
    assert not rows[0].startswith("Index") and "End of Xyce" not in rows[-1]


def test_an_unknown_package_is_ignored_with_a_warning(solver: Solver, tmp_path: Path) -> None:
    """Xyce ignores a line with another package, with a warning, as the library's refusal says;
    `PCES` is in the manual ([xyce-ref] §2.1.25.15 p114) but unrecognized by this build, which the
    library reads (a discrepancies.md row)."""
    result = _ok(solver, tmp_path / "devise", f"{_HOT}.options devise temp=127\n.op\n.end\n")
    assert "Unrecognized .OPTIONS package" in _messages(result)
    assert _at(result.plots[0], "v(2)") == pytest.approx(1.0)
    assert "with a warning" in _refused(f"{_HOT}.options devise temp=127\n.op\n.end\n")
    pces = _ok(solver, tmp_path / "pces", f"{_HOT}.options pces foo=1\n.op\n.end\n")
    assert "Unrecognized .OPTIONS package or parameter PCES" in _messages(pces)
    _library(f"{_HOT}.options pces foo=1\n.op\n.end\n")


@pytest.mark.parametrize("line", [".options temp=127", ".OPTIONS TEMP=127", ".option tnom=0"])
def test_temp_or_tnom_alone_applies_without_a_package(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    """A package-less line whose only item is `TEMP=` or `TNOM=` is applied, silently (observed;
    the manual gives every item a package, [xyce-ref] §2.1.25 p96): 127 degrees make R1 2k, and
    TNOM=0 makes it 1.27k at 27. The library refuses it with the DEVICE hint (a discrepancies.md
    row)."""
    result = _ok(solver, tmp_path, f"{_HOT}{line}\n.op\n.end\n")
    assert not result.warnings_at(5)
    expected = 2 / 3 if "temp" in line.lower() else 2 / 2.27
    assert _at(result.plots[0], "v(2)") == pytest.approx(expected, rel=1e-4)
    folded = "TNOM" if "tnom" in line.lower() else "TEMP"
    assert f"write `.OPTIONS DEVICE {folded}=`" in _refused(f"{_HOT}{line}\n.op\n.end\n")


@pytest.mark.parametrize(
    "line", [".options reltol=1e-3", ".options gmin=1e-12", ".options temp=127 reltol=1e-3"]
)
def test_another_packageless_line_is_ignored_with_a_warning(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    """Any other package-less line is ignored ("SPICE-style option not supported in Xyce"), as
    the library's refusal says (point 18)."""
    result = _ok(solver, tmp_path, f"{_HOT}{line}\n.op\n.end\n")
    assert "SPICE-style option not supported" in _messages(result)
    assert _at(result.plots[0], "v(2)") == pytest.approx(1.0)
    assert _refused(f"{_HOT}{line}\n.op\n.end\n").endswith("with a warning")


def test_the_plural_scale_without_a_package_runs(solver: Solver, tmp_path: Path) -> None:
    """`.OPTIONS SCALE=` runs silently, though the manual writes the singular for the
    package-less form ([xyce-ref] §2.1.25.21 p119); the library refuses it (a discrepancies.md
    row)."""
    result = _ok(solver, tmp_path, f"{_HOT}.options scale=1\n.op\n.end\n")
    assert not result.warnings_at(5)


def test_option_scale_is_parsers_scale(solver: Solver, tmp_path: Path) -> None:
    """Xyce reads `.OPTION SCALE=` as PARSER's SCALE ([xyce-ref] §2.1.25.21 p119): beside
    `.OPTIONS PARSER SCALE=` it is a repeat, the first value used, with a warning. The library
    keys the package-less item apart and reports no repeat (a discrepancies.md row)."""
    text = f"{_HOT}.option scale=1\n.options parser scale=2\n.op\n.end\n"
    result = _ok(solver, tmp_path, text)
    assert "duplicate PARSER parameter.  Using the first value found = 1" in _messages(result)
    assert DiagnosticCode.DUPLICATE_DEFINITION not in _codes(text)


@pytest.mark.parametrize(
    ("line", "message"),
    [
        (".options", ".OPTIONS line missing package name"),
        (".options device temp={127}", "Expressions are not supported"),
        (".options device temp=127, gmin=1e-12", "has comma in value"),
        (".options device temp=127 1 2", "Misformatted"),
        (".options device junk temp=127", "Misformatted"),
    ],
)
def test_options_stop_xyce_on(solver: Solver, tmp_path: Path, line: str, message: str) -> None:
    """A bare `.OPTIONS`, braces outside SAMPLES, a comma between items, a blank-separated list
    and a leading bare word stop Xyce (point 20), as the library refuses them."""
    result = run(solver, tmp_path, f"{_HOT}{line}\n.op\n.end\n")
    assert result.returncode != 0 and message in _messages(result)


def test_a_bare_word_after_an_item_is_dropped(solver: Solver, tmp_path: Path) -> None:
    """A bare word after an item is dropped silently and the item applies (point 20); the library
    refuses it (a discrepancies.md row). A package with no item is ignored with a warning."""
    assert _v2(solver, tmp_path / "junk", ".options device temp=127 junk") == pytest.approx(2 / 3)
    result = _ok(solver, tmp_path / "empty", f"{_HOT}.options device\n.op\n.end\n")
    assert "missing one or more required parameters" in _messages(result)


def test_samples_take_braced_outputs(solver: Solver, tmp_path: Path) -> None:
    """Braced expressions in a SAMPLES list (`OUTPUTS={V(2)},{V(1)}`, [xyce-ref] §2.1.25.13
    p113) run."""
    lines = (
        ".options samples numsamples=2 outputs={V(2)},{V(1)}\n"
        ".sampling param=R2 type=normal means=1k std_deviations=10"
    )
    assert len(_ok(solver, tmp_path, f"{_HOT}{lines}\n.op\n.end\n").plots) == 2


def test_initial_interval_takes_pairs(solver: Solver, tmp_path: Path) -> None:
    """OUTPUT's `INITIAL_INTERVAL=i t i` ([xyce-ref] §2.1.25.9 p110) runs: 1 ns to 5 ns, then
    0.5 ns, the pairs the library reads."""
    line = ".options output initial_interval=1n 5n 0.5n"
    (options,) = _items(f"{_HOT}{line}\n.op\n.end\n", OptionsDirective)
    assert [(t.text, i.text) for t, i in options.options[0].pairs] == [("5n", "0.5n")]
    text = f"{_HOT}{line}\n.tran 0.1n 10n\n.print tran v(2)\n.end\n"
    result = run(solver, tmp_path, text, mode="print")
    assert result.ok and result.prn_bytes is not None
    assert len(result.prn_bytes.decode().splitlines()) == 18


# .IC, .DCVOLT (XY-ICN-001) and .NODESET (XY-NOD-001). C1 across R2 holds v(2) at its initial
# condition at time 0; without one it is 0.8 (the operating point of R1, R2 and X1's 2k).

_HELD = (
    "probe\nV1 1 0 2\nR1 1 2 1k\nC1 2 0 1u\nR2 2 0 1k\n.subckt s a\nRs a m 1k\nCs m 0 1u\n"
    "Rt m 0 1k\n.ends\nX1 2 s\n"
)


def _start(solver: Solver, folder: Path, lines: str, head: str = _HELD) -> Plot:
    return _ok(solver, folder, f"{head}{lines}\n.tran 1n 1n\n.end\n").plot("Transient")


@pytest.mark.parametrize(
    "line",
    [
        ".ic v(2)=0.5",
        ".IC V(2) = 0.5",
        ".ic v( 2 )=0.5",
        ".ic 2 0.5",
        ".dcvolt v(2)=0.5",
        ".DCVOLT 2 0.5",
        ".ic v(2)={0.25*2}",
        ".ic v(2)='0.5'",
        ".ic v(2)=500m",
        ".ic v(2)=0.5v",
        ".ic v(1)=2\n+ v(2)=0.5",
    ],
)
def test_an_initial_condition_holds_its_node(solver: Solver, tmp_path: Path, line: str) -> None:
    """`V(node)=value` (blanks around `=` and inside the parentheses) or `node value`, on `.IC`
    and its synonym `.DCVOLT` ([xyce-ref] §2.1.14 p48, §2.1.4 p29; point 24): v(2) starts at the
    value the library reads."""
    text = f"{_HELD}{line}\n.tran 1n 1n\n.end\n"
    (ic,) = _items(text, IcDirective)
    condition = next(item for item in ic.conditions if item.node and item.node.name == "2")
    expected = 0.5 if not isinstance(condition.value, NumericValue) else _plain(condition.value)
    assert expected == pytest.approx(0.5)
    assert _at(_start(solver, tmp_path, line), "v(2)") == pytest.approx(0.5)


def test_without_a_condition_the_operating_point_holds(solver: Solver, tmp_path: Path) -> None:
    assert _at(_start(solver, tmp_path, ""), "v(2)") == pytest.approx(0.8, rel=1e-3)


@pytest.mark.parametrize(
    ("line", "message"),
    [
        (".ic v(2)=0.5 x1:m 0.3", "Unrecognized .IC and/or .DCVOLT specification"),
        (".ic v(2)=0.5, v(x1:m)=0.3", "Unrecognized .IC and/or .DCVOLT specification"),
        (".ic i(C1)=1m", "Unsupported current specification"),
        (".dcvolt v(2,0)=0.5", "Unrecognized parenthetical specification"),
        (".ic 2=0.5", "Unrecognized .IC and/or .DCVOLT specification"),
        (".ic all=0.5", "Unrecognized .IC and/or .DCVOLT specification"),
        (".DCVOLT ALL = 0.5", "Unrecognized .IC and/or .DCVOLT specification"),
    ],
)
def test_ic_ignores_what_it_cannot_read_with_a_warning(
    solver: Solver, tmp_path: Path, line: str, message: str
) -> None:
    """Mixed forms, commas, a current, a difference, `2=0.5` and `all=` on `.IC` or `.DCVOLT`:
    Xyce warns and ignores the field (point 24), as the library's refusal says; the
    conditions it can read before them still apply."""
    result = _ok(solver, tmp_path, f"{_HELD}{line}\n.tran 1n 1n\n.end\n")
    assert message in _messages(result)
    held = _at(result.plot("Transient"), "v(2)")
    assert held == pytest.approx(0.5 if line.startswith(".ic v(2)=0.5") else 0.8, rel=1e-3)
    reason = _refused(f"{_HELD}{line}\n.tran 1n 1n\n.end\n")
    if line.split()[1].lower().startswith(("all", "i(", "v(2,")):
        assert reason.endswith("with a warning")


@pytest.mark.parametrize(
    ("line", "message"),
    [
        (".nodeset all=0.5", "Unrecognized .NODESET specification"),
        (".nodeset i(C1)=1m", "Unsupported current specification"),
        (".nodeset v(2,0)=0.5", "Unrecognized parenthetical specification"),
        (".nodeset v(2)=0.5 x1:m 0.3", "Unrecognized .NODESET specification"),
        (".nodeset 2=0.5", "Unrecognized .NODESET specification"),
    ],
)
def test_nodeset_stops_on_what_it_cannot_read(
    solver: Solver, tmp_path: Path, line: str, message: str
) -> None:
    """The same fields stop Xyce on `.NODESET` ([xyce-ref] §2.1.22 p92), as the library's
    refusal says."""
    result = run(solver, tmp_path, f"{_HELD}{line}\n.tran 1n 1n\n.end\n")
    assert result.returncode != 0 and message in _messages(result)
    if "=0.5 " not in line and "2=0.5" not in line:
        assert "Xyce stops on" in _refused(f"{_HELD}{line}\n.tran 1n 1n\n.end\n")


@pytest.mark.parametrize("line", [".nodeset v(2)=0.5", ".NODESET 2 0.5"])
def test_nodeset_forms_run(solver: Solver, tmp_path: Path, line: str) -> None:
    """`.NODESET` takes the forms of `.IC` ([xyce-ref] §2.1.22 p92): a guess, so the linear
    circuit's operating point is unchanged."""
    text = f"{_HELD}{line}\n.tran 1n 1n\n.end\n"
    assert len(_items(text, NodesetDirective)) == 1
    assert _at(_start(solver, tmp_path, line), "v(2)") == pytest.approx(0.8, rel=1e-3)


@pytest.mark.parametrize("lines", [".ic v(2)=0.5\n.ic v(2)=0.7", ".ic v(2)=0.5 v(2)=0.7"])
def test_a_repeated_condition_uses_the_last_value(
    solver: Solver, tmp_path: Path, lines: str
) -> None:
    """A node given twice takes the last value, silently, as the library's `DUPLICATE_DEFINITION`
    says (point 24)."""
    assert _at(_start(solver, tmp_path, lines), "v(2)") == pytest.approx(0.7)
    assert DiagnosticCode.DUPLICATE_DEFINITION in _codes(f"{_HELD}{lines}\n.tran 1n 1n\n.end\n")


def test_ic_with_nodeset_aborts(solver: Solver, tmp_path: Path) -> None:
    """`.IC` and `.NODESET` in one netlist abort Xyce ("Cannot set both .IC and .NODESET
    simultaneously"), as `IC_WITH_NODESET` warns (point 24)."""
    text = f"{_HELD}.ic v(2)=0.5\n.nodeset v(2)=0.5\n.tran 1n 1n\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.returncode != 0
    assert "Cannot set both .IC and .NODESET" in result.log + result.stderr
    assert DiagnosticCode.IC_WITH_NODESET in _codes(text)


@pytest.mark.parametrize("line", [".ic v(x1:m)=0.3", ".ic x1:m 0.3", ".ic V(X1:M)=0.3"])
def test_a_path_reaches_the_internal_node(solver: Solver, tmp_path: Path, line: str) -> None:
    """`V(X1:m)` at the top level sets X1's internal node m (point 25), as `NODE_INTO_INSTANCE`
    says."""
    plot = _start(solver, tmp_path, line)
    assert _at(plot, "x1:m") == pytest.approx(0.3)
    assert DiagnosticCode.NODE_INTO_INSTANCE in _codes(f"{_HELD}{line}\n.tran 1n 1n\n.end\n")


def test_a_condition_on_an_unconnected_node_is_ignored(solver: Solver, tmp_path: Path) -> None:
    """Xyce warns "Initial conditions specified at nodes not present in circuit" and ignores the
    condition, as `UNRESOLVED_NODE` says (point 25)."""
    result = _ok(solver, tmp_path, f"{_HELD}.ic v(nosuch)=0.5\n.tran 1n 1n\n.end\n")
    assert "nodes not present in circuit" in _messages(result)
    assert DiagnosticCode.UNRESOLVED_NODE in _codes(f"{_HELD}.ic v(nosuch)=0.5\n.op\n.end\n")


def test_a_body_condition_applies_in_every_instance(solver: Solver, tmp_path: Path) -> None:
    """`.IC` in a body ([xyce-ref] §2.1.14 p48) holds the node of each instance (decision 0028
    item 2): X1:m and X2:m both start at 0.3; a port's condition holds the top-level node."""
    head = _HELD.replace("Rt m 0 1k\n", "Rt m 0 1k\n.ic v(m)=0.3\n") + "X2 2 s\n"
    plot = _start(solver, tmp_path / "internal", "", head)
    assert (_at(plot, "x1:m"), _at(plot, "x2:m")) == pytest.approx((0.3, 0.3))
    port = _HELD.replace("Rt m 0 1k\n", "Rt m 0 1k\n.ic v(a)=0.3\n")
    assert _at(_start(solver, tmp_path / "port", "", port), "v(2)") == pytest.approx(0.3)


_GLOBAL_HEADS = {
    "dollar-g": (
        "probe\nV1 1 0 2\nR1 1 $g1 1k\nC1 $g1 0 1u\nR2 $g1 0 1k\n.subckt s a\nRs a m 1k\n"
        "Cs m 0 1u\nRt m 0 1k\n.ic v($g1)=0.3\n.ends\nX1 $g1 s\n",
        "$g1",
        "on global node $G1 inside subcircuit S",
    ),
    "global": (
        "probe\n.global vdd\nV1 1 0 2\nR1 1 vdd 1k\nC1 vdd 0 1u\nR2 vdd 0 1k\n.subckt s a\n"
        "Rs a m 1k\nCs m 0 1u\nRt m 0 1k\n.ic v(vdd)=0.3\n.ends\nX1 vdd s\n",
        "vdd",
        "nodes not present in circuit",
    ),
}


@pytest.mark.parametrize("case", sorted(_GLOBAL_HEADS))
def test_a_global_node_in_a_body_condition_is_ignored(
    solver: Solver, tmp_path: Path, case: str
) -> None:
    """A `$G` node or a `.GLOBAL` node in a body's `.IC` is ignored with a warning (Xyce reads the
    `.GLOBAL` one as `X1:VDD`), as `CONDITION_IGNORED` says (points 5 and 33): the node keeps
    its operating point, 0.8."""
    head, node, message = _GLOBAL_HEADS[case]
    result = _ok(solver, tmp_path, f"{head}.tran 1n 1n\n.end\n")
    assert message in _messages(result)
    assert _at(result.plot("Transient"), node) == pytest.approx(0.8)
    assert DiagnosticCode.CONDITION_IGNORED in _codes(f"{head}.tran 1n 1n\n.end\n")


def test_a_top_level_condition_on_a_dollar_g_node_applies(solver: Solver, tmp_path: Path) -> None:
    head = _GLOBAL_HEADS["dollar-g"][0].replace(".ic v($g1)=0.3\n", "")
    plot = _start(solver, tmp_path, ".ic v($g1)=0.3", head)
    assert _at(plot, "$g1") == pytest.approx(0.3)
    assert DiagnosticCode.CONDITION_IGNORED not in _codes(f"{head}.ic v($g1)=0.3\n.op\n.end\n")


# .MEASURE (XY-MEA-001)

_MEAS = "probe\nV1 1 0 2 AC 1\nR1 1 2 1k\nR2 2 0 1k\nC1 2 0 1n\n"


def _measure(solver: Solver, folder: Path, lines: str) -> Run:
    return run(solver, folder, f"{_MEAS}{lines}\n.end\n")


@pytest.mark.parametrize(
    ("lines", "result", "value"),
    [
        (".tran 1n 2n\n.meas tran va find v(1) at=1n", "va", "2.000000e+00"),
        (".tran 1n 2n\n.MEASURE TRAN va max v(2)", "va", "1.000000e+00"),
        (".dc V1 0 2 1\n.meas dc va max v(2)", "va", "1.000000e+00"),
        (".ac dec 1 1 10\n.meas ac va max vm(2)", "va", "5.000000e-01"),
        (".noise v(2) V1 dec 1 1 10\n.meas noise va max onoise", "va", ""),
        (".tran 1n 2n\n.meas tran_cont va find v(1) at=1n", "va", "2.000000e+00"),
        (".dc V1 0 2 1\n.meas dc_cont va find v(2) at=2", "va", "1.000000e+00"),
        (".ac dec 1 1 10\n.meas ac_cont va find vm(2) at=10", "va", "5.000000e-01"),
        (".tran 1n 10n\n.fft v(2)\n.meas fft va enob v(2)", "va", ""),
    ],
)
def test_each_measure_mode_runs(
    solver: Solver, tmp_path: Path, lines: str, result: str, value: str
) -> None:
    """The modes TRAN, DC, AC, NOISE, FFT and the `_CONT` forms with their analysis
    ([xyce-ref] §2.1.18 p54, §2.1.19 p78, §2.1.20 p84): Xyce writes the result the library
    names."""
    (measure,) = _items(f"{_MEAS}{lines}\n.end\n", MeasureDirective)
    found = _measures(_measure(solver, tmp_path, lines))
    assert measure.result.lower() in found
    assert found[result].startswith(value)


def test_tr_runs_as_tran(solver: Solver, tmp_path: Path) -> None:
    """`TR` runs as `TRAN`, though the manual lists only TRAN; the library refuses it with a hint
    (a discrepancies.md row)."""
    found = _measures(_measure(solver, tmp_path, ".tran 1n 2n\n.meas tr va find v(1) at=1n"))
    assert found["va"].startswith("2.0")
    assert "write `TRAN`" in _refused(f"{_MEAS}.meas tr va find v(1) at=1n\n.end\n")


@pytest.mark.parametrize(
    ("line", "message"),
    [
        (".meas hb va max v(2)", "Unknown mode in .MEASURE line"),
        (".meas va max v(2)", "Unknown mode in .MEASURE line"),
    ],
)
def test_a_mode_outside_the_list_stops_xyce(
    solver: Solver, tmp_path: Path, line: str, message: str
) -> None:
    result = _measure(solver, tmp_path, f".tran 1n 2n\n{line}")
    assert result.returncode != 0 and message in _messages(result)


@pytest.mark.parametrize(
    "lines",
    [
        ".tran 1n 2n\n.ac dec 1 1 10\n.meas tran va max v(2)",
        ".op\n.meas tran va max v(2)",
        ".op\n.meas ac va max vm(2)",
        ".dc V1 0 1 1\n.tran 1n 2n\n.meas dc va max v(2)",
        ".tran 1n 2n\n.meas dc_cont va find v(2) at=1",
        ".noise v(2) V1 dec 1 1 10\n.tran 1n 2n\n.meas noise va max onoise",
    ],
)
def test_a_mode_whose_analysis_does_not_run_stops_xyce(
    solver: Solver, tmp_path: Path, lines: str
) -> None:
    """A mode whose analysis is not the one Xyce runs stops it ("… do not agree"), as
    `MEASURE_MODE_MISMATCH` says (points 26 and 32)."""
    result = _measure(solver, tmp_path, lines)
    assert result.returncode != 0 and "do not agree" in _messages(result)
    text = f"{_MEAS}{lines}\n.end\n"
    mismatch = [
        d for d in _library(text).diagnostics if d.code is DiagnosticCode.MEASURE_MODE_MISMATCH
    ]
    assert mismatch and "it stops" in mismatch[0].message


def test_a_dc_mode_under_op_reports_failed(solver: Solver, tmp_path: Path) -> None:
    """A DC mode under `.OP` runs and reports the measurement as FAILED, the milder message of
    `MEASURE_MODE_MISMATCH` (point 32)."""
    result = _measure(solver, tmp_path, ".op\n.meas dc va max v(2)")
    assert result.ok and _measures(result)["va"] == "FAILED"
    (finding,) = [
        d
        for d in _library(f"{_MEAS}.op\n.meas dc va max v(2)\n.end\n").diagnostics
        if d.code is DiagnosticCode.MEASURE_MODE_MISMATCH
    ]
    assert "FAILED" in finding.message


def test_fft_without_an_fft_line_stops_xyce(solver: Solver, tmp_path: Path) -> None:
    result = _measure(solver, tmp_path, ".tran 1n 10n\n.meas fft va enob v(2)")
    assert result.returncode != 0 and "No .FFT statement" in result.log + result.stderr
    assert DiagnosticCode.MEASURE_MODE_MISMATCH in _codes(
        f"{_MEAS}.tran 1n 10n\n.meas fft va enob v(2)\n.end\n"
    )


@pytest.mark.parametrize("mode", ["tran_cont", "dc_cont"])
def test_a_cont_mode_takes_only_some_types(solver: Solver, tmp_path: Path, mode: str) -> None:
    """The `_CONT` modes take only DERIV, FIND, TRIG, TARG and WHEN: `MAX` stops Xyce; the library
    keeps the body as text and does not check it (a discrepancies.md row)."""
    analysis = ".tran 1n 2n" if mode == "tran_cont" else ".dc V1 0 1 1"
    lines = f"{analysis}\n.meas {mode} va max v(2)"
    result = _measure(solver, tmp_path, lines)
    assert result.returncode != 0
    assert "Only DERIV, FIND, TRIG, TARG and WHEN" in _messages(result)
    _library(f"{_MEAS}{lines}\n.end\n")


def test_a_repeated_measurement_uses_the_last(solver: Solver, tmp_path: Path) -> None:
    """Xyce warns that the measure is redefined and uses the last definition, as the library's
    `DUPLICATE_DEFINITION` says (point 26)."""
    lines = ".tran 1n 2n\n.meas tran va find v(2) at=1n\n.meas tran va find v(1) at=1n"
    result = _measure(solver, tmp_path, lines)
    assert result.ok and "redefined" in _messages(result)
    assert _measures(result)["va"].startswith("2.0")
    assert DiagnosticCode.DUPLICATE_DEFINITION in _codes(f"{_MEAS}{lines}\n.end\n")


# .DATA (XY-DAT-001) and DATA= (XY-DCA-002)

_TABLE = ".data t\n+ r1 r2\n+ 1k 1k\n+ 1k 3k\n.enddata\n"
_DIVIDER = "probe\nV1 1 0 2 AC 1\nR1 1 2 1k\nR2 2 0 1k\nC1 2 0 1n\n"


def _sweep(result: Run) -> list[dict[str, float]]:
    return [{n: float(v) for n, v in _PAIR.findall(plot.name)} for plot in result.plots]


@pytest.mark.parametrize(
    "table",
    [
        _TABLE,
        ".DATA T\n+ R1 R2\n+ 1k 1k\n+ 1k 3k\n.ENDDATA\n",
        ".data t r1 r2\n+ 1k 1k 1k 3k\n.enddata\n",
        ".data t\n+ r1 r2\n+ 1000 1000\n+ 1e3 3e3\n.enddata\n",
    ],
)
def test_dc_data_sweeps_the_rows(solver: Solver, tmp_path: Path, table: str) -> None:
    """`.DC DATA=t` sweeps the table's rows ([xyce-ref] §2.1.2 p26, §2.1.3 p27): the column names
    on the `.DATA` line or a `+` line, the values a stream, any case; v(2) is 1, then 1.5."""
    text = f"{_DIVIDER}{table}.dc data=t\n.end\n"
    plot = _ok(solver, tmp_path, text).plot("DC Sweep")
    assert _column_v2(plot) == pytest.approx([1.0, 1.5])
    assert "name = R1" in plot.name and "name = R2" in plot.name


def _column_v2(plot: Plot) -> list[float]:
    index = [variable.lower() for variable in plot.variables].index("v(2)")
    return [float(row[index].real) for row in plot.rows]


def test_step_data_steps_the_rows(solver: Solver, tmp_path: Path) -> None:
    text = f"{_DIVIDER}{_TABLE}.step data=t\n.op\n.end\n"
    assert _sweep(_ok(solver, tmp_path, text)) == [
        {"R1": 1000.0, "R2": 1000.0},
        {"R1": 1000.0, "R2": 3000.0},
    ]


@pytest.mark.parametrize("analysis", [".ac data=t", ".noise v(2) V1 data=t"])
def test_ac_and_noise_data_take_the_frequencies(
    solver: Solver, tmp_path: Path, analysis: str
) -> None:
    table = ".data t\n+ freq\n+ 1k\n+ 2k\n.enddata\n"
    plot = _ok(solver, tmp_path, f"{_DIVIDER}{table}{analysis}\n.end\n").plots[0]
    assert len(plot.rows) == 2


def test_tran_takes_no_data(solver: Solver, tmp_path: Path) -> None:
    """`DATA=` is not a `.TRAN` field: Xyce stops on it, and the library refuses it."""
    result = run(solver, tmp_path, f"{_DIVIDER}{_TABLE}.tran 1n 2n data=t\n.end\n")
    assert result.returncode != 0
    with pytest.raises(ParseError):
        _library(f"{_DIVIDER}{_TABLE}.tran 1n 2n data=t\n.end\n")


@pytest.mark.parametrize("analysis", [".dc data=nosuch", ".step data=nosuch\n.op"])
def test_an_unknown_table_stops_xyce(solver: Solver, tmp_path: Path, analysis: str) -> None:
    """A `DATA=` name that no table has stops Xyce ("Invalid table name"), as `UNRESOLVED_DATA`
    says (point 27)."""
    text = f"{_DIVIDER}{_TABLE}{analysis}\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.returncode != 0 and "Invalid table name" in _messages(result)
    (finding,) = [d for d in _library(text).diagnostics if d.code is DiagnosticCode.UNRESOLVED_DATA]
    assert "stops on it" in finding.message


def test_a_repeated_table_uses_the_last(solver: Solver, tmp_path: Path) -> None:
    """Of two tables of one name (in any case), Xyce uses the last, as `DUPLICATE_DEFINITION`
    says (point 27): one row, R1 = 2k."""
    text = (
        f"{_DIVIDER}.data t\n+ r1 r2\n+ 1k 1k\n.enddata\n.data T\n+ r1\n+ 2k\n.enddata\n"
        ".dc data=t\n.end\n"
    )
    plot = _ok(solver, tmp_path, text).plot("DC Sweep")
    assert _column_v2(plot) == pytest.approx([2 / 3])
    assert DiagnosticCode.DUPLICATE_DEFINITION in _codes(text)


def test_a_table_may_stand_after_its_user(solver: Solver, tmp_path: Path) -> None:
    text = f"{_DIVIDER}.dc data=t\n{_TABLE}.end\n"
    assert _column_v2(_ok(solver, tmp_path, text).plot("DC Sweep")) == pytest.approx([1.0, 1.5])
    assert DiagnosticCode.UNRESOLVED_DATA not in _codes(text)


def test_the_first_word_is_the_name(solver: Solver, tmp_path: Path) -> None:
    """Xyce reads the first word after `.DATA` as the name, even on a `+` line, so the manual's
    optional name cannot be left out (point 27; a discrepancies.md row): `+ t r1 r2` is table
    `t`."""
    text = f"{_DIVIDER}.data\n+ t r1 r2\n+ 1k 1k\n.enddata\n.dc data=t\n.end\n"
    assert _column_v2(_ok(solver, tmp_path, text).plot("DC Sweep")) == pytest.approx([1.0])


@pytest.mark.parametrize(
    "table",
    [
        ".data t\n+ r1 r2\n+ 1k 1k\n+ 1k 3k\n",
        ".data t\n+ r1 r2\n+ 1k 1k\n+ 1k 3k\n.enddata t\n",
        ".data t\n+ r1 r2\n+ 1k 1k\n+ 1k 3k\n.enddata\n.enddata\n",
    ],
    ids=["missing", "named", "doubled"],
)
def test_enddata_is_a_no_op(solver: Solver, tmp_path: Path, table: str) -> None:
    """A missing, named or doubled `.ENDDATA` runs: Xyce ends a table at its last `+` line; the
    library requires one bare `.ENDDATA` (a discrepancies.md row)."""
    text = f"{_DIVIDER}{table}.dc data=t\n.end\n"
    assert _column_v2(_ok(solver, tmp_path, text).plot("DC Sweep")) == pytest.approx([1.0, 1.5])
    with pytest.raises(ParseError):
        _library(text)


@pytest.mark.parametrize(
    ("table", "message"),
    [
        (".data t\n+ r1 r2\n+ 1k 1k\n+ 1k\n.enddata\n", "not formatted correctly"),
        (".data t\n+ r1 r2\n+ {1k} 1k\n.enddata\n", "not formatted correctly"),
        (".data t\nr1 r2\n1k 1k\n.enddata\n", "lacks enough fields"),
    ],
    ids=["count", "expression", "no-plus"],
)
def test_a_malformed_table_stops_xyce(
    solver: Solver, tmp_path: Path, table: str, message: str
) -> None:
    """A value count that is not a multiple of the columns, an expression, and rows without `+`
    stop Xyce, even when nothing uses the table (point 27), as the library refuses them."""
    result = run(solver, tmp_path, f"{_DIVIDER}{table}.op\n.end\n")
    assert result.returncode != 0 and message in _messages(result)
    with pytest.raises(ParseError):
        _library(f"{_DIVIDER}{table}.op\n.end\n")
