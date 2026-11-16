"""XyceNF 7.10 probes of `.SUBCKT`/`.ENDS`, `.MODEL`, the includes and `.LIB` (X-M1 B4;
xm1-tasks 5.1 points 16 to 18 and 28; decision 0027 item 7).

Each probe is a minimal netlist authored here and run with ``Xyce`` through
``tests/support/xyce.py``; nothing Xyce writes is committed, and the include and library files are
written into the probe's own folder. A probe reads a resistance through a divider: ``V1`` is 2 V
over ``R1`` (1k) and the resistance under test from node 2 to ground, so ``v(2)`` is 1 when that
resistance is 1k.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.solvers import Solver
from tests.support.xyce import op, run

pytestmark = pytest.mark.solver("xyce")

_LIBRARY = "* corners\n.lib low\nR5 2 0 1k\n.endl low\n.lib nom\nR5 2 0 3k\n.endl nom\n"


def _divider(lines: str) -> str:
    return f"probe\nV1 1 0 2\nR1 1 2 1k\n{lines}.op\n.end\n"


def _v2(solver: Solver, folder: Path, lines: str, files: dict[str, str] | None = None) -> float:
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in (files or {}).items():
        (folder / name).write_text(text, encoding="utf-8")
    return op(solver, folder, _divider(lines))["v(2)"]


@pytest.mark.parametrize(
    "lines",
    [
        ".subckt s a params: r=1k\nR1 a 0 {r}\n.ends\nX1 2 s\n",
        ".SUBCKT s a PARAMS: r=1k\nR1 a 0 {r}\n.ENDS\nX1 2 s\n",
        ".subckt s a r=1k\nR1 a 0 {r}\n.ends\nX1 2 s\n",
        ".subckt s a\n+ params: r=1k\nR1 a 0 {r}\n.ends\nX1 2 s\n",
        ".subckt s a params: r=1kohm\nR1 a 0 {r}\n.ends\nX1 2 s\n",
        ".subckt s a params: r={500*2}\nR1 a 0 {r}\n.ends\nX1 2 s\n",
        ".subckt s a params:\nR1 a 0 1k\n.ends\nX1 2 s\n",
        ".subckt s a\nR1 a 0 1k\n.ends s\nX1 2 s\n",
        ".subckt s a\nR1 a 0 1k\n.ends other\nX1 2 s\n",
    ],
    ids=[
        "params",
        "upper-case",
        "no-params-keyword",
        "params-on-a-plus-line",
        "device-unit",
        "braced",
        "params-keyword-alone",
        "ends-name",
        "ends-other-name",
    ],
)
def test_subckt_forms(solver: Solver, tmp_path: Path, lines: str) -> None:
    """`PARAMS:` is optional and may stand alone; a default reads as a device field (`1kohm`) or
    a braced expression ([xyce-ref] §2.1.37 p159); `.ENDS` may name any subcircuit, which Xyce does
    not check (xm1-tasks 5.1 point 16)."""
    assert _v2(solver, tmp_path, lines) == pytest.approx(1.0)


def test_definitions_nest_and_are_local(solver: Solver, tmp_path: Path) -> None:
    """A definition inside another is used there, and is not visible at the top level
    ([xyce-ref] §2.1.37 p160)."""
    nested = ".subckt s a\n.subckt t b\nR1 b 0 1k\n.ends\nX2 a t\n.ends\n"
    assert _v2(solver, tmp_path / "inside", nested + "X1 2 s\n") == pytest.approx(1.0)
    outside = run(solver, tmp_path / "outside", _divider(nested + "X1 2 t\n"))
    assert outside.returncode == 1


@pytest.mark.parametrize(
    "lines",
    [
        ".subckt s\nR1 1 0 1k\n.ends\nX1 s\n",
        ".subckt s 0 a\nR1 a 0 1k\n.ends\nX1 2 2 s\n",
        ".subckt s a params: r=1k, q=2\nR1 a 0 {r}\n.ends\nX1 2 s\n",
        ".subckt s a params: r=2*500\nR1 a 0 {r}\n.ends\nX1 2 s\n",
        ".subckt s a\nR1 a 0 1k\n.global g\n.ends\nX1 2 s\n",
        ".subckt s a\nR1 a 0 1k\n.global_param g=1\n.ends\nX1 2 s\n",
        ".subckt s a\nR1 a 0 1k\n.ends\n.subckt s a\nR1 a 0 3k\n.ends\nX1 2 s\n",
        ".model rmod R R=2, TC1=0\nR5 2 0 rmod 1k\n",
        ".model rmod R (R=2) (TC1=0)\nR5 2 0 rmod 1k\n",
        ".model rmod R (R=2 R=3)\nR5 2 0 rmod 1k\n",
        ".model rmod R R=2\n.model rmod R R=3\nR5 2 0 rmod 1k\n",
        ".model rmod R R=2*1\nR5 2 0 rmod 1k\n",
        ".lib x\nR5 2 0 1k\n.endl y\n",
        ".lib x\nR5 2 0 1k\n.endl\n",
    ],
    ids=[
        "no-ports",
        "ground-port",
        "params-comma",
        "bare-default",
        "global-in-body",
        "global-param-in-body",
        "repeated-subckt",
        "model-comma",
        "model-two-parentheses",
        "repeated-model-parameter",
        "repeated-model",
        "bare-model-value",
        "endl-other-name",
        "endl-no-name",
    ],
)
def test_xyce_stops_on(solver: Solver, tmp_path: Path, lines: str) -> None:
    """A subcircuit needs a port other than `0`; `PARAMS:` takes no comma (the manual's own
    example writes one) and no bare default; `.GLOBAL` and `.GLOBAL_PARAM` stay at the top level;
    a subcircuit or model may not be defined twice, nor a model parameter written twice; `.MODEL`
    takes no comma, one pair of parentheses and no bare value; `.ENDL` names its entry
    (xm1-tasks 5.1 points 16 to 18 and 28)."""
    assert run(solver, tmp_path, _divider(lines)).returncode == 1


@pytest.mark.parametrize(
    "lines",
    [
        ".model rmod R (R=1)\nR5 2 0 rmod 1k\n",
        ".MODEL rmod R(R=1)\nR5 2 0 rmod 1k\n",
        ".model rmod R R=1\nR5 2 0 rmod 1k\n",
        ".model rmod R\n+ R=1\nR5 2 0 rmod 1k\n",
        ".model rmod R\nR5 2 0 rmod 1k\n",
        ".model rmod R ()\nR5 2 0 rmod 1k\n",
        ".model rmod RES R={1}\nR5 2 0 rmod 1k\n",
        ".model r.1 R R=1\nR5 2 0 r.1 1k\n",
        ".model rmod R R=1ohm\nR5 2 0 rmod 1k\n",
    ],
    ids=[
        "parentheses",
        "parentheses-glued",
        "no-parentheses",
        "continued",
        "no-parameters",
        "empty-parentheses",
        "res-braced",
        "dotted-name",
        "device-unit",
    ],
)
def test_model_forms(solver: Solver, tmp_path: Path, lines: str) -> None:
    """Parameters with or without one pair of parentheses, `RES` beside `R`, a name with a `.`
    (MOSFET bins, [xyce-ref] §2.1.21.2 p90), a device-field number ([xyce-ref] §2.1.21 p89;
    xm1-tasks 5.1 point 18). The model's `R` multiplies the instance value."""
    assert _v2(solver, tmp_path, lines) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "line",
    [
        ".inc part.cir",
        '.inc "part.cir"',
        ".incl 'part.cir'",
        ".INCLUDE part.cir",
        ".include\n+ part.cir",
        ".inc part.cir ; a comment",
    ],
)
def test_include_forms(solver: Solver, tmp_path: Path, line: str) -> None:
    """`.INC`, `.INCL` and `.INCLUDE` take a path, quoted or not, and may be continued
    ([xyce-ref] §2.1.15 p49; xm1-tasks 5.1 point 17)."""
    files = {"part.cir": "R5 2 0 1k\n"}
    assert _v2(solver, tmp_path, f"{line}\n", files) == pytest.approx(1.0)


def test_an_extra_include_field_is_ignored(solver: Solver, tmp_path: Path) -> None:
    """Xyce warns on a second field ("Extraneous data on .INCLUDE ignored") and runs, which the
    library refuses (discrepancies.md)."""
    (tmp_path / "part.cir").write_text("R5 2 0 1k\n", encoding="utf-8")
    result = run(solver, tmp_path, _divider(".inc part.cir other\n"))
    assert result.ok
    assert any("Extraneous data" in w.message for w in result.warnings_at(4))


@pytest.mark.parametrize(
    "line",
    [".lib corners.lib low", '.LIB "corners.lib" low', ".lib corners.lib\n+ low"],
)
def test_lib_call_forms(solver: Solver, tmp_path: Path, line: str) -> None:
    """A call reads the named entry of a library file ([xyce-ref] §2.1.16 p50)."""
    files = {"corners.lib": _LIBRARY}
    assert _v2(solver, tmp_path, f"{line}\n", files) == pytest.approx(1.0)


def test_a_lib_call_loads_only_its_first_entry(solver: Solver, tmp_path: Path) -> None:
    """With two entries Xyce warns ("Extraneous data on .LIB ignored") and loads only the first,
    which the manual allows ("the section or sections"); the library reports it (xm1-tasks 5.1
    point 17)."""
    (tmp_path / "corners.lib").write_text(_LIBRARY, encoding="utf-8")
    result = run(solver, tmp_path, _divider(".lib corners.lib low nom\n"))
    assert result.ok
    assert any("Extraneous data" in w.message for w in result.warnings_at(4))
    assert _v2(
        solver, tmp_path / "again", ".lib corners.lib low nom\n", {"corners.lib": _LIBRARY}
    ) == (pytest.approx(1.0))


def test_a_lib_with_one_field_opens_a_block(solver: Solver, tmp_path: Path) -> None:
    """One field is a definition: a call to a file stops Xyce, which asks for `.ENDL`, and a
    block in the netlist is skipped; `.ENDL` matches its name in any case ([xyce-ref] §2.1.16.2
    p50–51)."""
    (tmp_path / "corners.lib").write_text(_LIBRARY, encoding="utf-8")
    result = run(solver, tmp_path, _divider(".lib corners.lib\n"))
    assert result.returncode == 1
    assert any(".ENDL" in error.message for error in result.errors)
    block = ".lib x\nR5 2 0 3k\n.endl X\nR6 2 0 1k\n"
    assert _v2(solver, tmp_path / "block", block) == pytest.approx(1.0)


def test_a_directive_runs_in_a_body(solver: Solver, tmp_path: Path) -> None:
    """Xyce runs an analysis directive written in a subcircuit body, which the manual says a body
    should not hold ([xyce-ref] §2.1.37 p160); the library refuses it there (discrepancies.md)."""
    lines = ".subckt s a\nR1 a 0 1k\n.options timeint reltol=1e-3\n.ends\nX1 2 s\n"
    assert _v2(solver, tmp_path, lines) == pytest.approx(1.0)


@pytest.mark.parametrize("word", ["time", "vt", "temp", "gmin"])
def test_a_reserved_default_stops_xyce(solver: Solver, tmp_path: Path, word: str) -> None:
    """Four reserved words stop Xyce as a `PARAMS:` name ("not allowed in subcircuit parameter
    list"; scoping.md S7), with or without `PARAMS:`."""
    for folder, marker in (("marked", "params: "), ("unmarked", "")):
        lines = f".subckt s a {marker}{word}=1\nR1 a 0 1k\n.ends\nX1 2 s\n"
        assert run(solver, tmp_path / folder, _divider(lines)).returncode == 1


@pytest.mark.parametrize("word", ["freq", "hertz", "temper", "pi", "exp"])
def test_some_reserved_defaults_are_ignored(solver: Solver, tmp_path: Path, word: str) -> None:
    """`freq`, `hertz`, `temper`, `pi` and `exp` as a `PARAMS:` name are silently ignored: the
    netlist runs, which the library refuses (discrepancies.md; scoping.md S7)."""
    lines = f".subckt s a params: {word}=2\nR1 a 0 1k\n.ends\nX1 2 s\n"
    assert _v2(solver, tmp_path, lines) == pytest.approx(1.0)


def test_a_default_name_outside_the_parameter_class_stops_xyce(
    solver: Solver, tmp_path: Path
) -> None:
    """`PARAMS: 1x=1` stops Xyce ("contains illegal character(s)"); `a.b` is a name (XY-PRM-001,
    observed)."""
    bad = ".subckt s a params: 1x=1\nR1 a 0 1k\n.ends\nX1 2 s\n"
    assert run(solver, tmp_path / "digit", _divider(bad)).returncode == 1
    dotted = ".subckt s a params: a.b=1k\nR1 a 0 {a.b}\n.ends\nX1 2 s\n"
    assert _v2(solver, tmp_path / "dot", dotted) == pytest.approx(1.0)
