"""ngspice 47 probes for code models (A), OSDI devices (N) and code-model .model values (M17 T1,
decision 0020).

Each probe pairs what ngspice does with what the library reads, as the probes of the M17 task
list (section 3.1) found. Every circuit has ``V1 in 0 1``, ``Rin in 0 1k`` and a 1 kΩ load
``Rl out 0 1k``; ``gain=5`` gives ``v(out)`` 5. The OSDI probes load the ``r2_cmc.osdi`` that the
ngspice install ships, through ``pre_osdi`` in a ``.control`` block, and skip with a reason when
it is missing.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from netlistmod import (
    CodeModelDevice,
    Component,
    Dialect,
    Netlist,
    OsdiDevice,
    ParseError,
    UnsupportedConstruct,
)
from tests.support.ngspice import op, run
from tests.support.solvers import Solver, require_osdi

pytestmark = pytest.mark.solver("ngspice")

_BASE = "probe\nV1 in 0 1\nRin in 0 1k\nRl out 0 1k\n{body}\n.op\n.end\n"
_OSDI = ".control\npre_osdi r2_cmc.osdi\n.endc\n.model rmod r2_cmc(rsh=200)\n"


def _text(body: str) -> str:
    return _BASE.format(body=body)


def _reading(text: str) -> str:
    """The library's reading of the A or N line under test: ``refused``, ``unsupported``, or its
    class and its node count."""
    try:
        netlist = Netlist.from_text(text, dialect=Dialect.NGSPICE)
    except UnsupportedConstruct:
        return "unsupported"
    except ParseError:
        return "refused"
    found = [
        line.item
        for line in netlist.lines.walk()
        if isinstance(line.item, CodeModelDevice | OsdiDevice)
    ]
    item = found[-1]
    assert isinstance(item, Component)
    return f"{type(item).__name__} {len(item.nodes)}"


_AMP = ".model amp gain(gain=5)"
_SUM = ".model sum summer"
# (body, ngspice runs it, the library's reading)
_PROBES: dict[str, tuple[str, bool, str]] = {
    "plain": (f"a1 in out amp\n{_AMP}", True, "CodeModelDevice 2"),
    "typed": (f"a1 %v(in) %v(out) amp\n{_AMP}", True, "CodeModelDevice 2"),
    "typed-blank": (f"a1 %v in %v out amp\n{_AMP}", True, "CodeModelDevice 2"),
    "typed-paren-blank": (f"a1 %v (in) out amp\n{_AMP}", True, "CodeModelDevice 2"),
    "typed-upper": (f"a1 %V(in) out amp\n{_AMP}", True, "CodeModelDevice 2"),
    "vd": (f"a1 %vd(in 0) out amp\n{_AMP}", True, "CodeModelDevice 3"),
    "vd-unparenthesised": (f"a1 %vd in 0 out amp\n{_AMP}", True, "CodeModelDevice 3"),
    "vd-blank-paren": (f"a1 %vd (in 0) out amp\n{_AMP}", True, "CodeModelDevice 3"),
    "vd-comma": (f"a1 %vd(in, 0) out amp\n{_AMP}", True, "refused"),
    "untyped-paren": (f"a1 (in) out amp\n{_AMP}", True, "CodeModelDevice 2"),
    "param-on-line": (f"a1 in out amp gain=2\n{_AMP}", False, "refused"),
    "no-model": ("a1 in out", False, "CodeModelDevice 1"),
    "model-number": ("a1 in out 5\n.model 5 gain(gain=5)", False, "refused"),
    "builtin-model": ("a1 in out dm\n.model dm d", False, "CodeModelDevice 2"),
    "vector": (f"a1 [in in] out sum\n{_SUM}", True, "CodeModelDevice 3"),
    "vector-blanks": (f"a1 [ in in ] out sum\n{_SUM}", True, "CodeModelDevice 3"),
    "vector-typed": (f"a1 %v[in in] out sum\n{_SUM}", True, "CodeModelDevice 3"),
    "vector-typed-blank": (f"a1 %v [in in] out sum\n{_SUM}", True, "CodeModelDevice 3"),
    "vector-vd": (f"a1 [in %vd(in 0)] out sum\n{_SUM}", True, "CodeModelDevice 4"),
    "vector-vd-unparenthesised": (f"a1 [in %vd in 0] out sum\n{_SUM}", True, "CodeModelDevice 4"),
    "vector-differential": (f"a1 %vd [in 0 in 0] out sum\n{_SUM}", True, "CodeModelDevice 5"),
    "vector-continued": (f"a1 [in\n+ in] out sum\n{_SUM}", True, "CodeModelDevice 3"),
    "vector-comma": (f"a1 [in, in] out sum\n{_SUM}", True, "refused"),
    "vector-nested": (f"a1 [[in] in] out sum\n{_SUM}", False, "refused"),
    "vector-empty": (f"a1 [] out sum\n{_SUM}", False, "refused"),
    "vnam": (
        "Vs in x 0\nRx x 0 1k\na1 %vnam Vs out amp\n.model amp gain(gain=1000)",
        True,
        "CodeModelDevice 1",
    ),
    "vnam-paren": (
        "Vs in x 0\nRx x 0 1k\na1 %vnam(Vs) out amp\n.model amp gain(gain=1000)",
        True,
        "CodeModelDevice 1",
    ),
    "vnam-in-vector": (
        "Vs in x 0\nRx x 0 1k\na1 [%vnam Vs in] out sum\n.model sum summer(in_gain=[1000 1])",
        False,
        "refused",
    ),
    "current-out": ("a1 in %i(out) amp\n.model amp gain(gain=1m)", True, "CodeModelDevice 2"),
    "null-typed": (f"a1 %v null out amp\n{_AMP}", False, "refused"),
    "tilde-analog": (f"a1 %v ~in out amp\n{_AMP}", False, "CodeModelDevice 2"),
    "tilde-blank": (
        "a0 [in] [d] adc\na1 ~ d e inv\na2 [e] [out] dac\n"
        ".model adc adc_bridge(in_low=0.3 in_high=0.7)\n"
        ".model dac dac_bridge(out_low=0 out_high=1)\n.model inv d_inverter",
        True,
        "refused",
    ),
    "model-vector": (
        ".model sum summer(in_gain=[2.0 1.0])\na1 [in in] out sum",
        True,
        "CodeModelDevice 3",
    ),
    "model-vector-comma": (
        ".model sum summer(in_gain=[2.0, 1.0])\na1 [in in] out sum",
        True,
        "refused",
    ),
    "model-vector-unparenthesised": (
        ".model sum summer in_gain=[2.0 1.0]\na1 [in in] out sum",
        True,
        "CodeModelDevice 3",
    ),
    "model-vector-continued": (
        ".model sum summer(in_gain=[2.0\n+ 1.0])\na1 [in in] out sum",
        True,
        "CodeModelDevice 3",
    ),
    "model-vector-braced": (
        ".param g=2\n.model sum summer(in_gain=[{g} 1.0])\na1 [in in] out sum",
        True,
        "CodeModelDevice 3",
    ),
    "model-vector-empty": (".model sum summer(in_gain=[])\na1 [in in] out sum", False, "refused"),
    "model-false": (
        "a1 in out lim\n.model lim limit(gain=5 out_lower_limit=0 out_upper_limit=3"
        " fraction=FALSE)",
        True,
        "CodeModelDevice 2",
    ),
    "model-true-on-d": (
        "Dx in 0 dm\na1 in out amp\n.model dm d(is=1e-14 foo=TRUE)\n" + _AMP,
        True,
        "refused",
    ),
    "model-string": (f'a1 in out amp\n{_AMP[:-1]} x="abc")', True, "CodeModelDevice 2"),
    "model-bare-word": (f"a1 in out amp\n{_AMP[:-1]} x=abc)", False, "refused"),
    "subcircuit": (
        f"X1 in out s\n.subckt s a b\na1 a b amp\n{_AMP}\n.ends",
        True,
        "CodeModelDevice 2",
    ),
}


@pytest.mark.parametrize("case", sorted(_PROBES))
def test_code_model_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    body, ngspice_runs, reading = _PROBES[case]
    text = _text(body)
    assert run(solver, tmp_path, text).ok is ngspice_runs
    assert _reading(text) == reading


_OSDI_PROBES: dict[str, tuple[str, bool, str]] = {
    "osdi": ("N1 out in rmod w=1u l=20u", True, "OsdiDevice 2"),
    "osdi-braced": (".param len=20u\nN1 out in rmod w=1u l={len}", True, "OsdiDevice 2"),
    "osdi-no-params": ("N1 out in rmod", True, "OsdiDevice 2"),
    "osdi-m": ("N1 out in rmod w=1u l=20u m=2", True, "OsdiDevice 2"),
    "osdi-one-node": ("N1 out rmod w=1u l=20u", True, "OsdiDevice 1"),
    "osdi-three-nodes": ("N1 out in 0 rmod w=1u l=20u", False, "OsdiDevice 3"),
    "osdi-unknown": ("N1 out in rmod w=1u foo=1", False, "OsdiDevice 2"),
    "osdi-positional": ("N1 out in rmod 5", False, "refused"),
    "osdi-flag": ("N1 out in rmod off", False, "refused"),
    "osdi-diode-model": ("N1 out in dm\n.model dm d", False, "OsdiDevice 2"),
    "osdi-subcircuit": (
        "X1 out in s\n.subckt s a b\nN1 a b rmod w=1u l=20u\n.ends",
        True,
        "OsdiDevice 2",
    ),
}


@pytest.mark.parametrize("case", sorted(_OSDI_PROBES))
def test_osdi_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    require_osdi(solver, ["r2_cmc.osdi"])
    body, ngspice_runs, reading = _OSDI_PROBES[case]
    text = _text(f"{body}\n{_OSDI}")
    assert run(solver, tmp_path, text).ok is ngspice_runs
    assert _reading(text) == reading


def test_osdi_needs_pre_osdi(solver: Solver, tmp_path: Path) -> None:
    require_osdi(solver, ["r2_cmc.osdi"])
    text = _text("N1 out in rmod w=1u l=20u\n.model rmod r2_cmc(rsh=200)")
    assert not run(solver, tmp_path, text).ok
    assert _reading(text) == "OsdiDevice 2"


# What ngspice computes for the forms it runs.
_VALUES: list[tuple[str, str, float]] = [
    ("gain", f"a1 in out amp\n{_AMP}", 5.0),
    ("vd", f"a1 %vd(in 0) out amp\n{_AMP}", 5.0),
    ("summer", f"a1 [in in] out sum\n{_SUM}", 2.0),
    ("differential-vector", f"a1 %vd [in 0 in 0] out sum\n{_SUM}", 2.0),
    ("vector-gain", ".model sum summer(in_gain=[2.0 1.0])\na1 [in in] out sum", 3.0),
    ("vnam", "Vs in x 0\nRx x 0 1k\na1 %vnam Vs out amp\n.model amp gain(gain=1000)", 1.0),
    (
        "limit",
        "a1 in out lim\n.model lim limit(gain=5 out_lower_limit=0 out_upper_limit=3"
        " fraction=FALSE)",
        3.0,
    ),
]


@pytest.mark.parametrize(("case", "body", "value"), _VALUES, ids=[v[0] for v in _VALUES])
def test_what_ngspice_computes(
    solver: Solver, tmp_path: Path, case: str, body: str, value: float
) -> None:
    assert op(solver, tmp_path, _text(body))["v(out)"] == pytest.approx(value, abs=1e-3)


# The exit: an edited code-model parameter, a vector among them, an edited OSDI parameter and
# an edited model each move the result (decision 0020 item 9).
_EDITS: list[tuple[str, Callable[[Netlist], Netlist], float, float]] = [
    (f"a1 in out amp\n{_AMP}", lambda n: n.set_model_param("amp", "gain", "2"), 5.0, 2.0),
    (
        ".model sum summer(in_gain=[2.0 1.0])\na1 [in in] out sum",
        lambda n: n.set_model_param("sum", "in_gain", "[3 3]"),
        3.0,
        6.0,
    ),
    (
        "a1 in out lim\n.model lim limit(gain=5 out_lower_limit=0 out_upper_limit=3)",
        lambda n: n.set_model_param("lim", "out_upper_limit", "4"),
        3.0,
        4.0,
    ),
    (
        f"a1 in out amp\n{_AMP}\n.model amp2 gain(gain=3)",
        lambda n: n.set_model("a1", "amp2"),
        5.0,
        3.0,
    ),
]


@pytest.mark.parametrize(("body", "edit", "before", "after"), _EDITS)
def test_a_code_model_edit_moves_the_result(
    solver: Solver,
    tmp_path: Path,
    body: str,
    edit: Callable[[Netlist], Netlist],
    before: float,
    after: float,
) -> None:
    netlist = Netlist.from_text(_text(body), dialect=Dialect.NGSPICE)
    assert op(solver, tmp_path / "before", netlist)["v(out)"] == pytest.approx(before, abs=1e-3)
    assert op(solver, tmp_path / "after", edit(netlist))["v(out)"] == pytest.approx(after, abs=1e-3)


# r2_cmc ignores the model's rsh= (0.3333 with rsh=100, 200 or none) and defaults w= to 1u, so
# neither a model edit nor removing w= moves this circuit; the instance's l= and w= do.
@pytest.mark.parametrize(
    ("edit", "after"),
    [
        (lambda n: n.set_param("N1", "l", "40u"), 0.2),
        (lambda n: n.set_param("N1", "w", "2u"), 0.5),
    ],
)
def test_an_osdi_edit_moves_the_result(
    solver: Solver,
    tmp_path: Path,
    edit: Callable[[Netlist], Netlist],
    after: float | None,
) -> None:
    require_osdi(solver, ["r2_cmc.osdi"])
    netlist = Netlist.from_text(
        _text(f"N1 out in rmod w=1u l=20u\n{_OSDI}"), dialect=Dialect.NGSPICE
    )
    before = op(solver, tmp_path / "before", netlist)["v(out)"]
    assert before == pytest.approx(1 / 3, abs=1e-3)
    moved = op(solver, tmp_path / "after", edit(netlist))["v(out)"]
    assert moved != pytest.approx(before, abs=1e-3)
    if after is not None:
        assert moved == pytest.approx(after, abs=1e-3)
