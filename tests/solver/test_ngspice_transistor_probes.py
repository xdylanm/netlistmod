"""ngspice 47 probes for Q, M, J and Z and their .model forms (M13 T4 to T7, decision 0014).

Each probe pairs what ngspice does with what the library reads, as the probes of the M13 task
list (section 3) found. Every circuit is a small bias network with ``.op``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import Dialect, ParseError, SourceText, Transistor, parse
from tests.support.ngspice import run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ngspice")

_Q = (
    "probe\nV1 c 0 5\nV2 b 0 0.7\nRE e 0 100\nRS s 0 1\nRT tj 0 1\nR9 2 0 1\nR8 off 0 1\n"
    "{model}{line}\n.op\n.end\n"
)
_M = (
    "probe\nV1 d 0 5\nVG g 0 3\nRS s 0 10\nRB b 0 1\nRT tj 0 1\nRC tc 0 1\n"
    "{model}{line}\n.op\n.end\n"
)
_J = "probe\nV1 d 0 5\nV2 g 0 -1\nRS s 0 100\nRB b 0 1\n{model}{line}\n.op\n.end\n"
_QM = ".model qm NPN\n"
_NM = ".model nm NMOS(VTO=1 KP=1m)\n"
_VD = ".model vd VDMOS(VTO=2 KP=0.3)\n"


def _reading(text: str) -> tuple[list[str], str] | None:
    """The nodes and model the library reads from the transistor line, or None if it refuses."""
    try:
        items = parse(SourceText(text), Dialect.NGSPICE).items
    except ParseError:
        return None
    item = next(item for item in items if isinstance(item, Transistor))
    return [node.name for node in item.nodes], item.model.model_name


# (circuit, ngspice runs it, the library's reading or None for a refusal)
_PROBES = {
    "q-3-nodes": (_Q.format(model=_QM, line="Q1 c b e qm"), True, (["c", "b", "e"], "qm")),
    "q-4-nodes": (_Q.format(model=_QM, line="Q1 c b e s qm"), True, (["c", "b", "e", "s"], "qm")),
    "q-5-nodes-vbic": (
        _Q.format(model=".model qm NPN level=4\n", line="Q1 c b e s tj qm"),
        True,
        (["c", "b", "e", "s", "tj"], "qm"),
    ),
    "q-5-nodes-gummel-poon": (
        _Q.format(model=_QM, line="Q1 c b e s tj qm"),
        False,
        (["c", "b", "e", "s", "tj"], "qm"),
    ),
    "q-6-nodes": (
        _Q.format(model=".model qm NPN level=4\n", line="Q1 c b e s tj s qm"),
        False,
        None,
    ),
    "q-node-named-2": (
        _Q.format(model=_QM, line="Q1 c b e 2 qm"),
        True,
        (["c", "b", "e", "2"], "qm"),
    ),
    "q-node-named-off": (
        _Q.format(model=_QM, line="Q1 c b e off qm"),
        False,
        (["c", "b", "e", "off"], "qm"),
    ),
    "q-off-flag": (_Q.format(model=_QM, line="Q1 c b e qm off"), True, (["c", "b", "e"], "qm")),
    "q-digit-model": (
        _Q.format(model=".model 2N3904 NPN\n", line="Q1 c b e 2N3904"),
        True,
        (["c", "b", "e"], "2N3904"),
    ),
    "q-number-model": (_Q.format(model=".model 2 NPN\n", line="Q1 c b e 2"), False, None),
    "q-model-then-name": (
        _Q.format(model=_QM, line="Q1 c b e qm s"),
        False,
        (["c", "b", "e", "qm"], "s"),
    ),
    "q-named-areas": (
        _Q.format(model=_QM, line="Q1 c b e qm area=2 areab=1 areac=3"),
        True,
        (["c", "b", "e"], "qm"),
    ),
    "q-ic-list": (
        _Q.format(model=_QM, line="Q1 c b e qm off ic=0.6, 5.0"),
        True,
        (["c", "b", "e"], "qm"),
    ),
    "m-4-nodes": (_M.format(model=_NM, line="M1 d g s b nm"), True, (["d", "g", "s", "b"], "nm")),
    "m-3-nodes-nmos": (_M.format(model=_NM, line="M1 d g s nm"), False, (["d", "g", "s"], "nm")),
    "m-3-nodes-vdmos": (_M.format(model=_VD, line="M1 d g s vd"), True, (["d", "g", "s"], "vd")),
    "m-4-nodes-vdmos": (
        _M.format(model=_VD, line="M1 d g s s vd"),
        True,
        (["d", "g", "s", "s"], "vd"),
    ),
    "m-5-nodes-thermal": (
        _M.format(
            model=".model vd VDMOS(VTO=2 KP=0.3 rthjc=1 cthj=1m)\n",
            line="M1 d g s tj tc vd thermal",
        ),
        True,
        (["d", "g", "s", "tj", "tc"], "vd"),
    ),
    "m-5-nodes-nmos": (
        _M.format(model=_NM, line="M1 d g s b tj nm"),
        False,
        (["d", "g", "s", "b", "tj"], "nm"),
    ),
    "m-pchan-flag": (
        _M.format(model=".model vd VDMOS pchan VTO=-2 KP=0.3\n", line="M1 d g s vd"),
        True,
        (["d", "g", "s"], "vd"),
    ),
    "m-instance-params": (
        _M.format(
            model=_NM, line="M1 d g s b nm L=2u W=4u AD=1p AS=1p PD=1u PS=1u NRD=1 NRS=1 m=2"
        ),
        True,
        (["d", "g", "s", "b"], "nm"),
    ),
    "j-3-nodes": (
        _J.format(model=".model jm NJF\n", line="J1 d g s jm"),
        True,
        (["d", "g", "s"], "jm"),
    ),
    "j-4-nodes": (_J.format(model=".model jm NJF\n", line="J1 d g s b jm"), False, None),
    "j-area-params": (
        _J.format(model=".model jm NJF\n", line="J1 d g s jm 2 off area=2 m=2 temp=30 ic=1,-1"),
        True,
        (["d", "g", "s"], "jm"),
    ),
    "z-area-off": (
        _J.format(model=".model zm NMF\n", line="Z1 d g s zm 2 off"),
        True,
        (["d", "g", "s"], "zm"),
    ),
}


@pytest.mark.parametrize("case", sorted(_PROBES))
def test_transistor_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    text, ngspice_runs, reading = _PROBES[case]
    result = run(solver, tmp_path, text)
    assert result.ok is ngspice_runs, result.log
    assert _reading(text) == reading


@pytest.mark.parametrize("line", ["Q1 c b e qm 2", "Q1 c b e s qm 2", "Q1 c b e qm 2 off"])
def test_a_positional_area_on_q_runs_and_is_refused(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    # Decision 5: the manual shows only area=, so the library refuses what ngspice also runs,
    # with one message for each form (review R2).
    text = _Q.format(model=_QM, line=line)
    assert run(solver, tmp_path, text).ok
    with pytest.raises(ParseError, match="an ngspice Q writes its area as `area=2`"):
        parse(SourceText(text), Dialect.NGSPICE)


def test_an_igbt_model_is_not_an_ngspice_type(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nV1 c 0 5\nV2 g 0 10\nRE e 0 100\n.model zi NIGBT\nZ1 c g e zi\n.op\n.end\n"
    result = run(solver, tmp_path, text)
    assert not result.ok
    assert "unknown model type" in result.log.lower(), result.log
    assert _reading(text) == (["c", "g", "e"], "zi")


def test_area_scales_the_collector_current(solver: Solver, tmp_path: Path) -> None:
    def drop(params: str) -> float:
        text = (
            "probe\nV1 vcc 0 5\nRC vcc c 1k\nV2 b 0 0.7\n.model qm NPN(IS=1e-16)\n"
            f"Q1 c b 0 qm{params}\n.op\n.end\n"
        )
        result = run(solver, tmp_path / (params.strip().replace("=", "_") or "one"), text)
        assert result.ok, result.log
        return 5 - result.voltage("c")

    assert drop(" area=2") == pytest.approx(2 * drop(""), rel=1e-3)


def test_a_dotted_model_value_runs(solver: Solver, tmp_path: Path) -> None:
    text = _M.format(model=".model nm NMOS(level=8 version=3.3.0)\n", line="M1 d g s b nm")
    assert run(solver, tmp_path, text).ok
    assert _reading(text) == (["d", "g", "s", "b"], "nm")


def test_temp_on_a_bsim_line_loads_and_stops_ngspice(solver: Solver, tmp_path: Path) -> None:
    # The grammar cannot know the level, so temp= loads (M13 T5).
    text = _M.format(model=".model nm NMOS(level=8 version=3.3.0)\n", line="M1 d g s b nm temp=30")
    assert not run(solver, tmp_path, text).ok
    assert _reading(text) == (["d", "g", "s", "b"], "nm")
