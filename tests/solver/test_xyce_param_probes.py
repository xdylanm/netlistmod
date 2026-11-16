"""XyceNF 7.10 probes of `.PARAM`, `.GLOBAL_PARAM`, `.FUNC`, bare values and scoping (X-M1 B3;
xm1-tasks 5.1 points 20 to 27; decision 0027 items 9 and 10).

Each probe is a minimal netlist authored here and run with ``Xyce`` through
``tests/support/xyce.py``; nothing Xyce writes is committed. A probe reads a parameter through a
divider: ``R2`` takes the value under test, and ``v(2)`` is 1 when it equals ``R1``'s 1k.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.solvers import Solver
from tests.support.xyce import op, run

pytestmark = pytest.mark.solver("xyce")


def _divider(r2: str, lines: str, *, r1: str = "1k") -> str:
    return f"probe\n{lines}V1 1 0 2\nR1 1 2 {r1}\nR2 2 0 {r2}\n.op\n.end\n"


def _v2(solver: Solver, folder: Path, r2: str, lines: str, *, r1: str = "1k") -> float:
    return op(solver, folder, _divider(r2, lines, r1=r1))["v(2)"]


@pytest.mark.parametrize(
    "lines",
    [
        ".param r=1k\n",
        ".PARAM r = 1k\n",
        ".param a=1, r=1k\n",
        ".param a=1 ,r=1k\n",
        ".param a=1,\n+ r=1k\n",
        ".param a=1\n* c\n+ r=1k\n",
        ".param a=1k r={a}\n",
        ".param a=1k r='a'\n",
        ".param a=500 r=a*2\n",
        ".param r=1x/1k\n",
        ".param r=1e3\n",
        ".param a.b=1k r={a.b}\n",
    ],
)
def test_param_forms(solver: Solver, tmp_path: Path, lines: str) -> None:
    """Blanks or commas between assignments, blanks around `=`, braced, quoted and bare values
    ([xyce-ref] §2.1.26 p120, §2.2 p164), and a `.` in a name, which the manual does not mention
    (observed; xm1-tasks 5.1 point 27)."""
    assert _v2(solver, tmp_path, "{r}", lines) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "lines",
    [
        ".param f(x)={x*1k}\n.param r={f(1)}\n",
        ".param f(x) = 'x*1k' r={f(1)}\n",
        ".param a=1, f(x,y)={x*y} r={f(a,1k)}\n",
        ".func f(x) {x*1k}\n.param r={f(1)}\n",
        ".func f(x)={x*1k}\n.param r={f(1)}\n",
        ".func f(x) = 'x*1k'\n.param r={f(1)}\n",
        ".func f(x){x*1k}\n.param r={f(1)}\n",
        ".param r={f(1)}\n.func f(x) {x*1k}\n",
        ".func g(x) {f(x)}\n.func f(x) {x*1k}\n.param r={g(1)}\n",
    ],
)
def test_functions(solver: Solver, tmp_path: Path, lines: str) -> None:
    """Function assignments on `.PARAM`, and `.FUNC` with or without `=` and with a braced or
    quoted body ([xyce-ref] §2.1.10 p42); a function may be used before its definition, which the
    manual's `.FUNC` wording does not allow (xm1-tasks 5.1 point 23)."""
    assert _v2(solver, tmp_path, "{r}", lines) == pytest.approx(1.0)


def test_a_blank_before_the_argument_list_runs(solver: Solver, tmp_path: Path) -> None:
    """Xyce takes `f (x)`, which the manual's form does not write and the library refuses
    (discrepancies.md)."""
    for index, lines in enumerate(
        [".func f (x) {x*1k}\n.param r={f(1)}\n", ".param f (x)={x*1k} r={f(1)}\n"]
    ):
        assert _v2(solver, tmp_path / str(index), "{r}", lines) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "lines",
    [
        ".func f(x) x*1k\n.param r={f(1)}\n",
        ".func f(x) {x} g(y) {y}\n.param r={f(1k)}\n",
        ".func f(x) {x*1k}\n.func f(x) {x*3k}\n.param r={f(1)}\n",
        ".global_param f(x)={x*1k}\n.param r={f(1)}\n",
        '.param s="abc" r=1k\n',
        ".param ,r=1k\n",
        ".param r=1k,,a=1\n",
        ".param b#=1 r=1k\n",
        ".func f() {1k}\n.param r={f()}\n",
    ],
    ids=[
        "bare-body",
        "two-functions",
        "repeated-function",
        "global-param-function",
        "string",
        "leading-comma",
        "two-commas",
        "hash-name",
        "no-arguments",
    ],
)
def test_xyce_stops_on(solver: Solver, tmp_path: Path, lines: str) -> None:
    """A `.FUNC` body must be braced or quoted, one `.FUNC` defines one function, a function
    may not be defined again, `.GLOBAL_PARAM` defines none, and `.PARAM` takes no strings, no
    leading or doubled comma and no `#` in a name (xm1-tasks 5.1 points 20 and 27). Xyce also
    stops on a call to a function of no arguments, which the manual's form allows
    (discrepancies.md)."""
    assert run(solver, tmp_path, _divider("{r}", lines)).returncode == 1


def test_global_param_is_top_level_only(solver: Solver, tmp_path: Path) -> None:
    """`.GLOBAL_PARAM` stops Xyce in a subcircuit body ([xyce-ref] §2.1.12 p46)."""
    text = (
        "body\n.subckt s a b\n.global_param q=1k\nR1 a b {q}\n.ends\nV1 1 0 2\nX1 1 0 s\n"
        ".op\n.end\n"
    )
    assert run(solver, tmp_path, text).returncode == 1
    top = ".global_param r=1k\n"
    assert _v2(solver, tmp_path / "top", "{r}", top) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "lines",
    [
        ".param r=1k\n.param r=3k\n",
        ".global_param r=1k\n.global_param r=3k\n",
        ".global_param r=3k\n.param r=1k\n",
        ".param r=1k\n.global_param r=3k\n",
    ],
    ids=["param", "global-param", "global-then-param", "param-then-global"],
)
def test_the_first_definition_wins_and_param_beats_global_param(
    solver: Solver, tmp_path: Path, lines: str
) -> None:
    """A repeated `.PARAM` or `.GLOBAL_PARAM` takes the first value, as Xyce 7.10's own warning
    says, where the manual says the last (discrepancies.md); a `.PARAM` wins over a
    `.GLOBAL_PARAM` of the same name in either order (xm1-tasks 5.1 points 22 and 24)."""
    assert _v2(solver, tmp_path, "{r}", lines) == pytest.approx(1.0)


def test_a_body_param_is_shadowed_by_a_params_default(solver: Solver, tmp_path: Path) -> None:
    """In a subcircuit, a `.PARAM` that repeats a `PARAMS:` name loses to the default and to the
    instance's value (xm1-tasks 5.1 point 24)."""
    text = (
        "shadow\n.subckt s a b params: r=1k\n.param r=3k\nR1 a b {r}\n.ends\n"
        "V1 1 0 2\nR1 1 2 1k\nX1 2 0 s\n.op\n.end\n"
    )
    assert op(solver, tmp_path / "default", text)["v(2)"] == pytest.approx(1.0)
    instance = text.replace("X1 2 0 s", "X1 2 0 s params: r=1k").replace(
        "r=1k\n.param", "r=5k\n.param"
    )
    assert op(solver, tmp_path / "instance", instance)["v(2)"] == pytest.approx(1.0)


def test_a_bare_value_loses_its_blanks(solver: Solver, tmp_path: Path) -> None:
    """Xyce deletes every blank inside a bare `.PARAM` value, so `r=1 000` is 1000 and
    `a = 500 + 500` is 1000; the library refuses a blank in a bare value (decision X-D5,
    discrepancies.md)."""
    for index, lines in enumerate(
        [".param r=1 000\n", ".param r = 500 + 500\n", ".param r=max(1k, 0)\n"]
    ):
        assert _v2(solver, tmp_path / str(index), "{r}", lines) == pytest.approx(1.0)


@pytest.mark.parametrize("word", ["time", "freq", "vt", "temp", "gmin"])
def test_a_reserved_word_parameter_stops_xyce(solver: Solver, tmp_path: Path, word: str) -> None:
    """Five reserved words stop Xyce as a parameter name ([xyce-ref] §2.1.26 p121)."""
    assert run(solver, tmp_path, _divider("1k", f".param {word}=1\n")).returncode == 1


@pytest.mark.parametrize("word", ["hertz", "temper", "pi", "exp"])
def test_some_reserved_words_are_ignored(solver: Solver, tmp_path: Path, word: str) -> None:
    """`hertz`, `temper`, `pi` and `exp` as a parameter name are silently ignored: the line runs,
    which the library refuses (discrepancies.md; xm1-tasks 5.1 point 25)."""
    assert run(solver, tmp_path, _divider("1k", f".param {word}=1\n")).ok


def test_a_builtin_function_name_is_ignored(solver: Solver, tmp_path: Path) -> None:
    """A `.FUNC` of a built-in name is ignored: `abs` stays the built-in ([xyce-ref] §2.1.10 p42
    forbids the name; discrepancies.md)."""
    lines = ".func abs(x) {3k}\n.param r={abs(-1k)}\n"
    assert _v2(solver, tmp_path, "{r}", lines) == pytest.approx(1.0)


def test_pi_as_an_argument_is_ignored(solver: Solver, tmp_path: Path) -> None:
    """`pi` as a `.FUNC` argument stays the constant: `f(1)` is pi, not 1 ([xyce-ref] §2.1.10
    p42 forbids it; discrepancies.md)."""
    lines = ".func f(pi) {pi*1k}\n.param r={f(1)}\n"
    assert _v2(solver, tmp_path, "{r}", lines, r1="3.14159265k") == pytest.approx(1.0)


@pytest.mark.parametrize("expression", ["{2**3*125}", "{(1^0)*1k}", "{(1|0)*1k}", "{(1&1)*1k}"])
def test_expression_operators(solver: Solver, tmp_path: Path, expression: str) -> None:
    """`**` is the power and `^` a boolean XOR beside `|` and `&` ([xyce-ref] Table 2-32 p164;
    xm1-tasks 5.1 point 26)."""
    assert _v2(solver, tmp_path, expression, "") == pytest.approx(1.0)
