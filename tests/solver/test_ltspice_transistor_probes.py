"""LTspice 26.1.1 probes for Q, M, J and Z and their .model forms (M13 T4 to T7, decision 0014).

Each probe pairs what LTspice does with what the library reads, as the probes of the M13 task
list (section 3) found. Every circuit is a small bias network with ``.op``. Nothing LTspice writes
is committed (decision 0009 item 2).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import (
    BipolarTransistor,
    Dialect,
    Jfet,
    Mesfet,
    Mosfet,
    ParseError,
    SourceText,
    parse,
)
from tests.support.ltspice import run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ltspice")

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
_KINDS = (BipolarTransistor, Mosfet, Jfet, Mesfet)


def _reading(text: str) -> tuple[list[str], str, str | None] | None:
    """The nodes, model and area the library reads from the transistor line, or None."""
    try:
        items = parse(SourceText(text), Dialect.LTSPICE).items
    except ParseError:
        return None
    item = next(item for item in items if isinstance(item, _KINDS))
    area = item.area.text if item.area is not None else None
    return [node.name for node in item.nodes], item.model.model_name, area


# (circuit, LTspice runs it, the library's reading or None for a refusal)
_PROBES = {
    "q-3-nodes": (_Q.format(model=_QM, line="Q1 c b e qm"), True, (["c", "b", "e"], "qm", None)),
    "q-4-nodes": (
        _Q.format(model=_QM, line="Q1 c b e s qm"),
        True,
        (["c", "b", "e", "s"], "qm", None),
    ),
    "q-5-nodes-vbic": (
        _Q.format(model=".model qm NPN level=4\n", line="Q1 c b e s tj qm"),
        False,
        None,
    ),
    "q-node-named-2": (
        _Q.format(model=_QM, line="Q1 c b e 2 qm"),
        True,
        (["c", "b", "e", "2"], "qm", None),
    ),
    "q-area": (_Q.format(model=_QM, line="Q1 c b e qm 2"), True, (["c", "b", "e"], "qm", "2")),
    "q-4-nodes-area": (
        _Q.format(model=_QM, line="Q1 c b e s qm 2"),
        True,
        (["c", "b", "e", "s"], "qm", "2"),
    ),
    "q-area-off": (
        _Q.format(model=_QM, line="Q1 c b e qm 2 off temp=30"),
        True,
        (["c", "b", "e"], "qm", "2"),
    ),
    "q-node-named-off": (
        _Q.format(model=_QM, line="Q1 c b e off qm"),
        True,
        (["c", "b", "e", "off"], "qm", None),
    ),
    "q-digit-model": (
        _Q.format(model=".model 2N3904 NPN\n", line="Q1 c b e 2N3904 2"),
        True,
        (["c", "b", "e"], "2N3904", "2"),
    ),
    "q-number-model": (_Q.format(model=".model 2 NPN\n", line="Q1 c b e 2"), True, None),
    "q-model-then-name": (
        _Q.format(model=_QM, line="Q1 c b e qm s"),
        False,
        (["c", "b", "e", "qm"], "s", None),
    ),
    "m-4-nodes": (
        _M.format(model=_NM, line="M1 d g s b nm"),
        True,
        (["d", "g", "s", "b"], "nm", None),
    ),
    "m-3-nodes-nmos": (
        _M.format(model=_NM, line="M1 d g s nm"),
        False,
        (["d", "g", "s"], "nm", None),
    ),
    "m-3-nodes-vdmos": (
        _M.format(model=_VD, line="M1 d g s vd"),
        True,
        (["d", "g", "s"], "vd", None),
    ),
    "m-4-nodes-vdmos": (
        _M.format(model=_VD, line="M1 d g s s vd"),
        True,
        (["d", "g", "s", "s"], "vd", None),
    ),
    "m-5-nodes-thermal": (
        _M.format(
            model=".model vd VDMOS(VTO=2 KP=0.3 rthjc=1 cthj=1m)\n",
            line="M1 d g s tj tc vd thermal",
        ),
        False,
        None,
    ),
    "m-pchan-flag": (
        _M.format(model=".model vd VDMOS pchan VTO=-2 KP=0.3\n", line="M1 d g s vd"),
        True,
        (["d", "g", "s"], "vd", None),
    ),
    "m-instance-params": (
        _M.format(
            model=_NM, line="M1 d g s b nm L=2u W=4u AD=1p AS=1p PD=1u PS=1u NRD=1 NRS=1 m=2 off"
        ),
        True,
        (["d", "g", "s", "b"], "nm", None),
    ),
    "m-ic-list": (
        _M.format(model=_NM, line="M1 d g s b nm IC=1, -1"),
        True,
        (["d", "g", "s", "b"], "nm", None),
    ),
    "j-3-nodes": (
        _J.format(model=".model jm NJF\n", line="J1 d g s jm 2 off temp=30"),
        True,
        (["d", "g", "s"], "jm", "2"),
    ),
    "j-4-nodes": (_J.format(model=".model jm NJF\n", line="J1 d g s b jm"), False, None),
    "j-area-param": (_J.format(model=".model jm NJF\n", line="J1 d g s jm area=2"), True, None),
    "z-area-off": (
        _J.format(model=".model zm NMF\n", line="Z1 d g s zm 2 off m=2"),
        True,
        (["d", "g", "s"], "zm", "2"),
    ),
    "z-igbt": (
        "probe\nV1 c 0 5\nV2 g 0 10\nRE e 0 100\n.model zi NIGBT\nZ1 c g e zi\n.op\n.end\n",
        True,
        (["c", "g", "e"], "zi", None),
    ),
}


@pytest.mark.parametrize("case", sorted(_PROBES))
def test_transistor_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    text, ltspice_runs, reading = _PROBES[case]
    result = run(solver, tmp_path, text)
    assert result.ok is ltspice_runs, result.log
    assert _reading(text) == reading


def test_area_scales_the_collector_current(solver: Solver, tmp_path: Path) -> None:
    def drop(params: str, folder: str) -> float:
        text = (
            "probe\nV1 vcc 0 5\nRC vcc c 1k\nV2 b 0 0.7\n.model qm NPN(IS=1e-16)\n"
            f"Q1 c b 0 qm{params}\n.op\n.end\n"
        )
        assert _reading(text) is not None
        result = run(solver, tmp_path / folder, text)
        assert result.ok, result.log
        return 5 - result.voltage("c")

    assert drop(" 2", "two") == pytest.approx(2 * drop("", "one"), rel=1e-3)


def test_a_dotted_model_value_runs(solver: Solver, tmp_path: Path) -> None:
    text = _M.format(model=".model nm NMOS(level=8 version=3.3.0)\n", line="M1 d g s b nm")
    assert run(solver, tmp_path, text).ok
    assert _reading(text) == (["d", "g", "s", "b"], "nm", None)


def test_temp_on_a_bsim_line_loads_and_stops_ltspice(solver: Solver, tmp_path: Path) -> None:
    # The grammar cannot know the level, so temp= loads (M13 T5).
    text = _M.format(model=".model nm NMOS(level=8 version=3.3.0)\n", line="M1 d g s b nm temp=30")
    assert not run(solver, tmp_path, text).ok
    assert _reading(text) == (["d", "g", "s", "b"], "nm", None)
