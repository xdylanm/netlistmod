"""XyceNF 7.10 probes of netlist structure: comments, continuation, title, ``.END`` and ground
(X-M0 tasks A4 and B4; section 5.1 item 4).

Each probe is a minimal netlist authored here and run with ``Xyce`` through
``tests/support/xyce.py``; nothing Xyce writes is committed. A probe reads the solver's view of
the circuit from the operating point (``op``) or from ``-namesfile`` (``nodes``), so a line Xyce
ignores shows as a node or a current that is missing. The citations are to the manuals by printed
page; the manuals are paraphrased, never quoted at length (P10, architecture §11.3).

What the library reads for these lines is checked by the grammar tests of the hidden xyce
dialect, not here: X-M0's xyce reads only a title, comment lines, blank lines and ``.END``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.solvers import Solver
from tests.support.xyce import names, nodes, op, run, syntax

pytestmark = pytest.mark.solver("xyce")

# A divider: v(2) is 1 with both resistors, 2 without R2.
_DIVIDER = "V1 1 0 2\nR1 1 2 1k\nR2 2 0 1k\n"


def test_an_unknown_dot_command_warns_and_is_ignored(solver: Solver, tmp_path: Path) -> None:
    """An unknown dot-command is a warning placed at its line, and the run goes on as if it were
    not there. The manual lists the dot-commands ([xyce-ref] §2.1); its only word on others is
    that PSpice's ``.TEMP`` is ignored ([xyce-ref] Table 6-1 p848). The binary is more lenient
    than a closed list (section 5.1 item 4, a discrepancy row; the list is decided in X-M2)."""
    text = "unknown dot-command\n" + _DIVIDER + ".frobnicate a b c\n.op\n.end\n"
    result = run(solver, tmp_path / "run", text)
    assert result.ok and result.returncode == 0
    (warning,) = result.warnings_at(5)
    assert "Unrecognized dot line" in warning.message
    assert syntax(solver, tmp_path / "syntax", text).returncode == 0
    assert op(solver, tmp_path / "op", text)["v(2)"] == pytest.approx(1.0)


def test_an_indented_element_line_is_a_comment(solver: Solver, tmp_path: Path) -> None:
    """A line that begins with whitespace is a comment unless its first non-blank character is
    ``+`` ([xyce-ug] §4.1.3.1 p43; decision X-D1): an indented ``R3`` adds no node and an
    indented ``R2`` no load, silently."""
    new_node = "indented element\nV1 1 0 2\nR1 1 0 1k\n R3 3 0 1k\n.op\n.end\n"
    assert nodes(solver, tmp_path / "names", new_node) == {"1"}
    result = run(solver, tmp_path / "run", new_node)
    assert result.ok and not result.warnings_at(4)
    divider = "indented element\nV1 1 0 2\nR1 1 2 1k\n R2 2 0 1k\nR3 2 0 1k\n.op\n.end\n"
    assert op(solver, tmp_path / "op", divider)["v(2)"] == pytest.approx(1.0)


def test_an_indented_param_line_is_a_comment(solver: Solver, tmp_path: Path) -> None:
    """An indented ``.param`` is a comment too ([xyce-ug] §4.1.3.1 p43): it does not redefine
    ``r`` (a repeated ``.param`` would take the last value, [xyce-ref] §2.1.26 p120), and without
    the first ``.param`` the circuit has no ``r`` at all and fails."""
    redefined = "indented param\n.param r=1k\nV1 1 0 2\nR1 1 2 1k\nR2 2 0 {r}\n .param r=3k\n.op\n"
    assert op(solver, tmp_path / "op", redefined + ".end\n")["v(2)"] == pytest.approx(1.0)
    undefined = "indented param\nV1 1 0 2\nR1 1 2 1k\nR2 2 0 {r}\n .param r=3k\n.op\n.end\n"
    assert run(solver, tmp_path / "undefined", undefined).returncode == 1


def test_an_indented_end_line_is_a_comment(solver: Solver, tmp_path: Path) -> None:
    """An indented ``.END`` does not end the netlist ([xyce-ug] §4.1.3.1 p43): ``R2`` after it
    is read."""
    text = "indented end\nV1 1 0 2\nR1 1 2 1k\n .end\nR2 2 0 1k\n.op\n.end\n"
    assert op(solver, tmp_path, text)["v(2)"] == pytest.approx(1.0)


def test_a_continuation_joins_across_comments_and_blank_lines(
    solver: Solver, tmp_path: Path
) -> None:
    """A ``+`` line joins the last non-comment line, across comment lines and blank lines
    ([xyce-ug] §4.1.3.2 p43): ``R1``'s value comes after a ``*`` line and a blank line."""
    text = "continuation\nV1 1 0 2\nR1 1 2\n* a comment\n\n+ 1k\nR2 2 0 1k\n.op\n.end\n"
    assert op(solver, tmp_path, text)["v(2)"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    "title",
    ["continuation after the title", "V1 1 0 2"],
    ids=["a-title", "an-element-as-title"],
)
def test_a_continuation_never_joins_the_title(solver: Solver, tmp_path: Path, title: str) -> None:
    """A ``+`` line on line 2 joins nothing: the title is not a line it continues, even when the
    title reads as an element ([xyce-ug] §4.1.1 p40, §4.1.3.2 p43). Xyce reports line 2 and
    fails."""
    text = f"{title}\n+ R9 1 0 1k\nV2 1 0 2\nR1 1 0 1k\n.op\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.returncode == 1
    (error,) = result.errors_at(2)
    assert "Unrecognized line" in error.message


def test_a_bracketed_node_is_a_literal_node_name(solver: Solver, tmp_path: Path) -> None:
    """``[1]`` is a node of its own, distinct from ``1``. The manual writes optional fields in
    brackets and brackets a named substrate node ([xyce-ref] §2.3.17 p241), but the binary reads
    the brackets as part of a name (section 5.1 item 4; a discrepancy row for X-M4)."""
    text = "bracketed node\nV1 1 0 2\nR1 1 [1] 1k\nR2 [1] 0 1k\n.op\n.end\n"
    assert nodes(solver, tmp_path / "names", text) == {"1", "[1]"}
    assert op(solver, tmp_path / "op", text)["[1]"] == pytest.approx(1.0)


@pytest.mark.parametrize("comment", [" ; a comment", "; a comment", ";"])
def test_a_semicolon_ends_a_line(solver: Solver, tmp_path: Path, comment: str) -> None:
    """``;`` starts an end-of-line comment ([xyce-ug] §4.1.3.1 p43)."""
    text = f"semicolon\nV1 1 0 2\nR1 1 2 1k{comment}\nR2 2 0 1k\n.op\n.end\n"
    assert op(solver, tmp_path, text)["v(2)"] == pytest.approx(1.0)


@pytest.mark.parametrize("comment", ["$ a comment", "// a comment"], ids=["dollar", "slashes"])
def test_dollar_and_double_slash_do_not_end_a_line(
    solver: Solver, tmp_path: Path, comment: str
) -> None:
    """Neither ``$`` nor ``//`` starts a comment: the rest of the line is read as fields of
    ``R1``, and Xyce fails at that line. The manual's examples write ``//`` after a statement
    ([xyce-ref] §2.2.3 p173), and fail on the binary; the comment rules name only ``;``
    ([xyce-ref] §2.1.39.2 p163, [xyce-ug] §4.1.3.1 p43) (section 5.1 item 4, a discrepancy row);
    ``$`` is an end-of-line comment on ngspice, not on Xyce."""
    text = f"end-of-line comment\nV1 1 0 2\nR1 1 2 1k {comment}\nR2 2 0 1k\n.op\n.end\n"
    result = run(solver, tmp_path, text)
    assert result.returncode == 1
    assert result.errors_at(3)
    assert {item.line for item in result.errors} == {3}


def test_line_one_is_the_title_even_when_it_reads_as_an_element(
    solver: Solver, tmp_path: Path
) -> None:
    """The first line is the title ([xyce-ug] §4.1.1 p40): ``V1`` on line 1 defines no source and
    no node."""
    text = "V1 1 0 2\nV2 2 0 1\nR1 2 0 1k\n.op\n.end\n"
    assert names(solver, tmp_path, text) == {"2", "v2_branch"}


def test_a_blank_line_one_is_the_title(solver: Solver, tmp_path: Path) -> None:
    """A blank first line is the title ([xyce-ug] §4.1.1 p40), so line 2 is the first element:
    ``V1`` on line 2 is read."""
    text = "\nV1 1 0 2\nR1 1 0 1k\n.op\n.end\n"
    assert names(solver, tmp_path, text) == {"1", "v1_branch"}


def test_a_netlist_without_end_runs(solver: Solver, tmp_path: Path) -> None:
    """The manual says the last line must be ``.END`` ([xyce-ug] §4.1.1 p40); the binary runs a
    netlist without one, with no diagnostic placed at a line (section 5.1 item 4, a discrepancy
    row; decided in X-M1)."""
    text = "no end\n" + _DIVIDER + ".op\n"
    result = run(solver, tmp_path / "run", text)
    assert result.ok and all(item.line is None for item in result.diagnostics)
    assert op(solver, tmp_path / "op", text)["v(2)"] == pytest.approx(1.0)


def test_text_after_end_is_ignored(solver: Solver, tmp_path: Path) -> None:
    """Lines after ``.END`` are not read ([xyce-ug] §4.1.1 p40 makes ``.END`` the last line; the
    binary ignores what follows, section 5.1 item 4): neither an element nor a line that is not
    SPICE is reported."""
    text = "after end\n" + _DIVIDER + ".op\n.end\nR3 3 0 1k\nthis is not a netlist line\n"
    result = run(solver, tmp_path / "run", text)
    assert result.ok and all(item.line is None for item in result.diagnostics)
    assert nodes(solver, tmp_path / "names", text) == {"1", "2"}


def test_gnd_is_not_ground_without_replaceground(solver: Solver, tmp_path: Path) -> None:
    """Only ``0`` is ground ([xyce-ref] §2.3.1.1 p182). ``GND`` is an ordinary node, here the
    middle of a divider, unless ``.PREPROCESS REPLACEGROUND`` makes it an alias of ``0``
    ([xyce-ref] §2.1.28 p125)."""
    plain = "gnd\nV1 1 0 2\nR1 1 gnd 1k\nR2 gnd 0 1k\n.op\n.end\n"
    assert nodes(solver, tmp_path / "plain", plain) == {"1", "gnd"}
    assert op(solver, tmp_path / "plain-op", plain)["gnd"] == pytest.approx(1.0)
    replaced = "gnd\n.preprocess replaceground true\nV1 1 0 2\nR1 1 gnd 1k\nR2 1 0 1k\n.op\n.end\n"
    assert nodes(solver, tmp_path / "replaced", replaced) == {"1"}
    assert op(solver, tmp_path / "replaced-op", replaced)["v1#branch"] == pytest.approx(-4e-3)
