"""XyceNF 7.10 probes of names, ground, globals, `.END` and the two number readers (X-M1 B2;
xm1-tasks 5.1 points 2 to 6, 8 and 19; decision 0027 items 2, 3 and 8).

Each probe is a minimal netlist authored here and run with ``Xyce`` through
``tests/support/xyce.py``; nothing Xyce writes is committed. What the library reads for these
lines is checked by ``tests/grammar/xyce/`` and ``tests/document/test_xyce_names.py``; these
probes show what the solver does, which the spec entries and ``discrepancies.md`` cite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.solvers import Solver
from tests.support.xyce import nodes, op, run

pytestmark = pytest.mark.solver("xyce")

# A divider: v(2) is 1 when R2 equals R1.
_SOURCE = "V1 1 0 2\n"


def _divider(r1: str, r2: str, *, before: str = "") -> str:
    return f"divider\n{before}{_SOURCE}R1 1 2 {r1}\nR2 2 0 {r2}\n.op\n.end\n"


@pytest.mark.parametrize("comment", [" ; a comment", ";a comment", " ;"])
def test_end_may_end_with_a_semicolon_comment(solver: Solver, tmp_path: Path, comment: str) -> None:
    """``;`` may end any line ([xyce-ug] §4.1.3.1 p43), the ``.END`` line too: Xyce runs it
    with no diagnostic placed at a line (decision 0027 item 2)."""
    text = _divider("1k", "1k").replace(".end\n", f".end{comment}\n")
    result = run(solver, tmp_path / "run", text)
    assert result.ok and all(item.line is None for item in result.diagnostics)
    assert op(solver, tmp_path / "op", text)["v(2)"] == pytest.approx(1.0)


def test_end_with_text_after_it_runs(solver: Solver, tmp_path: Path) -> None:
    """Xyce also runs ``.end junk``, which the library refuses (discrepancies.md)."""
    text = _divider("1k", "1k").replace(".end\n", ".end junk\n")
    assert op(solver, tmp_path, text)["v(2)"] == pytest.approx(1.0)


@pytest.mark.parametrize("name", ["GND", "gnd", "Gnd!", "GND!", "ground", "Ground"])
def test_replaceground_makes_the_synonyms_ground(solver: Solver, tmp_path: Path, name: str) -> None:
    """With ``.PREPROCESS REPLACEGROUND TRUE`` the name is node 0 ([xyce-ref] §2.1.28 p125): the
    divider's middle node is ground, so it is no node of the circuit."""
    text = _divider("1k", "1k", before=".preprocess replaceground true\n").replace(
        "R2 2 0", f"R2 2 {name}"
    )
    assert nodes(solver, tmp_path / "names", text) == {"1", "2"}
    assert op(solver, tmp_path / "op", text)["v(2)"] == pytest.approx(1.0)
    grounded = f"synonym\n.preprocess replaceground true\nV1 1 0 2\nR1 1 {name} 1k\n.op\n.end\n"
    assert nodes(solver, tmp_path / "grounded", grounded) == {"1"}


def test_ground_with_a_bang_is_not_a_synonym(solver: Solver, tmp_path: Path) -> None:
    """``GROUND!`` stays a node under REPLACEGROUND (xm1-tasks 5.1 point 5)."""
    text = "bang\n.preprocess replaceground true\nV1 1 0 2\nR1 1 ground! 1k\nR2 ground! 0 1k\n.op\n"
    assert nodes(solver, tmp_path, text + ".end\n") == {"1", "ground!"}


def test_replaceground_false_keeps_gnd_a_node(solver: Solver, tmp_path: Path) -> None:
    text = "false\n.preprocess replaceground false\nV1 1 0 2\nR1 1 gnd 1k\nR2 gnd 0 1k\n.op\n.end\n"
    assert nodes(solver, tmp_path / "names", text) == {"1", "gnd"}
    assert op(solver, tmp_path / "op", text)["gnd"] == pytest.approx(1.0)


def test_replaceground_in_a_body_acts_on_the_whole_netlist(solver: Solver, tmp_path: Path) -> None:
    """The statement may stand in a subcircuit body and still makes the top level's ``GND``
    ground (xm1-tasks 5.1 point 5): R2 is a second load on V1."""
    text = (
        "in a body\n.subckt s a b\n.preprocess replaceground true\nR1 a b 1k\n.ends\n"
        "V1 1 0 2\nR2 1 gnd 1k\nX1 1 0 s\n.op\n.end\n"
    )
    assert nodes(solver, tmp_path / "names", text) == {"1"}
    assert op(solver, tmp_path / "op", text)["v1#branch"] == pytest.approx(-4e-3)


@pytest.mark.parametrize(
    "lines",
    [
        ".preprocess replaceground true\n.preprocess replaceground true\n",
        ".preprocess replaceground true\n.preprocess replaceground false\n",
        ".preprocess replaceground 1\n",
        ".preprocess replaceground yes\n",
        ".preprocess replaceground\n",
    ],
    ids=["twice", "true-then-false", "one", "yes", "no-value"],
)
def test_replaceground_stops_on_a_second_line_or_a_bad_value(
    solver: Solver, tmp_path: Path, lines: str
) -> None:
    """Only one statement is allowed ([xyce-ref] §2.1.28 p125), and its value is TRUE or FALSE:
    Xyce stops otherwise (xm1-tasks 5.1 point 5)."""
    text = _divider("1k", "1k", before=lines)
    assert run(solver, tmp_path, text).returncode == 1


@pytest.mark.parametrize("spelling", ["$Gx", "$gx", "$GX"])
def test_a_dollar_g_node_is_global(solver: Solver, tmp_path: Path, spelling: str) -> None:
    """A node whose name begins ``$G`` is global ([xyce-ref] §2.3.1.1 p182; decision X-D3), in
    any case: the subcircuit's ``$gx`` is the top level's node, the middle of a divider."""
    text = (
        f"dollar g\n.subckt s a\nR1 a $gx 1k\n.ends\nV1 1 0 2\nX1 1 s\nR2 {spelling} 0 1k\n"
        ".op\n.end\n"
    )
    assert nodes(solver, tmp_path / "names", text) == {"1", "$gx"}
    assert op(solver, tmp_path / "op", text)["$gx"] == pytest.approx(1.0)


def test_a_dollar_name_without_g_is_local(solver: Solver, tmp_path: Path) -> None:
    text = "dollar\n.subckt s a\nR1 a $vx 1k\n.ends\nV1 1 0 2\nX1 1 s\nR2 $vx 0 1k\n.op\n.end\n"
    assert nodes(solver, tmp_path, text) == {"1", "$vx", "x1:$vx"}


@pytest.mark.parametrize("separator", [" ", ",", ", "], ids=["blank", "comma", "comma-blank"])
def test_global_makes_nodes_global(solver: Solver, tmp_path: Path, separator: str) -> None:
    """``.GLOBAL`` makes its names global ([xyce-ref] §2.1.11 p44). Xyce also takes a comma
    between them, which the manual's form does not show and the library refuses
    (discrepancies.md)."""
    text = (
        f"global\n.global vdd{separator}vss\n.subckt s a\nR1 a vdd 1k\nR3 vss 0 1k\n.ends\n"
        "V1 1 0 2\nX1 1 s\nR2 vdd 0 1k\nVS vss 0 0\n.op\n.end\n"
    )
    assert nodes(solver, tmp_path / "names", text) == {"1", "vdd", "vss"}
    assert op(solver, tmp_path / "op", text)["vdd"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    "name", ["a[1]", "n!", "n#1", "n$", "a/b", "a-b", "a+b", "a.b", "n%", "a&b"]
)
def test_name_characters_of_the_class(solver: Solver, tmp_path: Path, name: str) -> None:
    """Printable ASCII other than ( ) { } , : ; " ' = are name characters ([xyce-ref] §2.3.2
    p184): the node is the divider's middle."""
    text = _divider("1k", "1k").replace(" 2 ", f" {name} ").replace("R2 2", f"R2 {name}")
    assert nodes(solver, tmp_path / "names", text) == {"1", name.lower()}


@pytest.mark.parametrize("name", ['a"b', "Äb"], ids=["quote", "non-ascii"])
def test_names_outside_the_manual_class_run(solver: Solver, tmp_path: Path, name: str) -> None:
    """Xyce takes ``"`` and non-ASCII letters in a node name, which the manual's class leaves
    out and the library refuses (discrepancies.md)."""
    text = _divider("1k", "1k").replace(" 2 ", f" {name} ").replace("R2 2", f"R2 {name}")
    result = run(solver, tmp_path, text)
    assert result.ok


def test_case_folds_in_ascii_only(solver: Solver, tmp_path: Path) -> None:
    """Xyce ignores case ([xyce-ug] §4.1.3 p41) in ASCII only: ``AB`` and ``ab`` are one node, and
    ``Äb`` and ``äb`` are two (observed; decision 0027 item 3)."""
    ascii_text = "case\nV1 1 0 2\nR1 1 AB 1k\nR2 ab 0 1k\n.op\n.end\n"
    assert nodes(solver, tmp_path / "ascii", ascii_text) == {"1", "ab"}
    accented = "case\nV1 1 0 2\nR1 1 Äb 1k\nR2 äb 0 1k\nR3 Äb 0 1k\nR4 äb 1 1k\n.op\n.end\n"
    assert len(nodes(solver, tmp_path / "accented", accented)) == 3


@pytest.mark.parametrize(
    ("r1", "r2"),
    [
        ("1k", "1kohm"),
        ("1k", "1KOhm"),
        ("1k", "1000ohm"),
        ("1meg", "1x"),
        ("1meg", "1X"),
        ("1meg", "1Meg"),
        ("1m", "1M"),
        ("25.4u", "1mil"),
        ("1", "1a"),
        ("1", "1amp"),
        ("1k", "1kv"),
        ("1k", "1kvolt"),
        ("1k", "1kvdc"),
        ("1k", "1khz"),
        ("1k", "1khertz"),
        ("1k", "1kh"),
        ("1k", "1khenry"),
        ("1k", "1khy"),
        ("1k", "1kc"),
        ("1k", "1ks"),
        ("1k", "1km"),
        ("1p", "1pfarad"),
        ("1f", "1fa"),
        ("1f", "1ff"),
        ("1u", "1uf"),
    ],
)
def test_device_fields_take_scale_factors_and_units(
    solver: Solver, tmp_path: Path, r1: str, r2: str
) -> None:
    """A device field takes a scale factor ([xyce-ug] Table 4-1 p42, with ``X`` = 1e6 and ``mil``;
    ``M`` is milli) and then a unit of a closed list (observed; decision 0027 item 8)."""
    assert op(solver, tmp_path, _divider(r1, r2))["v(2)"] == pytest.approx(1.0)


@pytest.mark.parametrize("value", ["1kk", "1z", "1µ", "2k7", "1kq", "1kj", "1farad"])
def test_device_fields_refuse_other_letters(solver: Solver, tmp_path: Path, value: str) -> None:
    """Letters outside the lists stop Xyce, and so do RKM values and ``µ``, which the manual's
    table lists (xm1-tasks 5.1 point 19). A letter that begins a scale factor is read as one, so
    ``1farad`` is femto followed by ``arad``, and stops Xyce."""
    assert run(solver, tmp_path, _divider("1k", value)).returncode == 1


@pytest.mark.parametrize("value", ["1keg", "1kmeg", "1e", "1kmhz"])
def test_device_fields_take_lexer_artefacts(solver: Solver, tmp_path: Path, value: str) -> None:
    """Xyce runs these forms, which no table lists; the library refuses them (discrepancies.md)."""
    assert run(solver, tmp_path, _divider("1k", value)).ok


@pytest.mark.parametrize(
    "value", ["1k", "1K", "1kv", "1khz", "1kh", "1kf", "1ks", "1km", "1ka", "1000", "1e3"]
)
def test_expressions_take_their_units(solver: Solver, tmp_path: Path, value: str) -> None:
    """In a ``.PARAM`` value a unit of a, f, h, hz, m, s or v may follow the scale factor
    (observed; decision 0027 item 8)."""
    text = _divider("1k", "{r}", before=f".param r={value}\n")
    assert op(solver, tmp_path, text)["v(2)"] == pytest.approx(1.0)


@pytest.mark.parametrize("value", ["1kohm", "1kvolt", "1kamp", "1kvdc", "1kk", "1µ", "1farad"])
def test_expressions_refuse_the_device_units(solver: Solver, tmp_path: Path, value: str) -> None:
    """``.param r=1kohm`` stops Xyce: the expression reader has the shorter list."""
    text = _divider("1k", "{r}", before=f".param r={value}\n")
    assert run(solver, tmp_path, text).returncode == 1


@pytest.mark.parametrize("value", ["2j", "1.0+2.0J", "{1+2j}", "1kj"])
def test_expressions_take_an_imaginary_part(solver: Solver, tmp_path: Path, value: str) -> None:
    """``J`` marks the imaginary part of a parameter ([xyce-ref] §2.2.1 p172); a real device
    parameter takes the real part."""
    text = _divider("1k", "1k", before=f".param c={value}\n")
    assert op(solver, tmp_path, text)["v(2)"] == pytest.approx(1.0)


# Node paths into an instance (decision X-D2, decision 0027 item 4; names.md N7). `X1` is a
# 1k + 1k divider from node 1 to ground, `R3` 1k from the path to ground: joined to the divider's
# middle, the source sees 1.5k; as a net of its own, R3 hangs from it and the source sees 2k.
_DIV = ".subckt div a b\nR1 a m 1k\nR2 m b 1k\n.ends\n"
_JOINED = 1 / 1.5e3
_SEPARATE = 1 / 2e3


def _path_current(solver: Solver, folder: Path, body: str) -> float:
    return -op(solver, folder, f"paths\nV1 1 0 1\n{body}.op\n.end\n")["v1#branch"]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (f"X1 1 0 div\n{_DIV}R3 X1:m 0 1k\n", _JOINED),
        (f"R3 x1:M 0 1k\nX1 1 0 div\n{_DIV}", _JOINED),
        (f"X1 1 0 div\n{_DIV}R3 X1:a 0 1k\n", _SEPARATE),
        (f"X1 1 0 div\n{_DIV}R3 X1:zz 0 1k\n", _SEPARATE),
        (f"X1 1 0 div\n{_DIV}R3 X7:m 0 1k\n", _SEPARATE),
        (
            f"X1 1 0 top\n.subckt top p q\nX2 p q div\n.ends\n{_DIV}R3 X1:X2:m 0 1k\n",
            _JOINED,
        ),
        (f"X1 1 0 top\n.subckt top p q\nX2 p q div\nR3 X2:m q 1k\n.ends\n{_DIV}", _JOINED),
        (f"X1 1 0 div\nX9 1 0 top\n.subckt top p q\nR3 X1:m q 1k\n.ends\n{_DIV}", _SEPARATE),
    ],
    ids=[
        "internal",
        "internal-any-case-before-the-instance",
        "port",
        "missing-node",
        "missing-instance",
        "nested",
        "from-a-body",
        "relative-to-its-scope",
    ],
)
def test_a_node_path_into_an_instance(
    solver: Solver, tmp_path: Path, body: str, expected: float
) -> None:
    """A path joins an internal node of the instance, relative to the scope it is written in;
    a port, a missing node or a missing instance is a net of its own ([xyce-ref] §2.3.1.2
    p182-183; the port and missing cases rest on the binary)."""
    assert _path_current(solver, tmp_path, body) == pytest.approx(expected, rel=1e-6)
