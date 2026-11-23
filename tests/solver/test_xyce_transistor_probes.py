"""XyceNF 7.10 probes of the transistor lines Q, M, J and Z (X-M4 B5; decision 0031 items 1 to 4;
xm4-tasks 5.1 points 1 to 10 and 22).

Each probe is a minimal netlist authored here and run with ``Xyce`` through
``tests/support/xyce.py``, in a temporary folder; nothing Xyce writes is committed. Each test
states the library's reading of a line beside what Xyce does with it: the forms on which the two
agree, and the forms of the ``discrepancies.md`` rows. Probes that need a node to be absent from
the circuit read Xyce's names file (``-namesfile``), where a node Xyce drops does not appear.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import (
    BipolarTransistor,
    DiagnosticCode,
    Flag,
    Jfet,
    Mesfet,
    Mosfet,
    Netlist,
    NumericValue,
    ParseError,
)
from netlistmod.dialects import _XYCE
from tests.support.solvers import Solver
from tests.support.xyce import nodes, op, run

pytestmark = pytest.mark.solver("xyce")

_TRANSISTORS = (BipolarTransistor, Mosfet, Jfet, Mesfet)


def _q(lines: str, models: str = ".model qn npn") -> str:
    """A Q line between fixed collector and base voltages; `s`, `t` and `x` are held at 0 V when
    a line uses them, so that a node Xyce joins or takes has a DC path."""
    return f"q\nVC c 0 5\nVB b 0 0.7\n{lines}\n{models}\n.op\n.end\n"


def _jz(lines: str, models: str = ".model jm njf\n.model zm nmf vto=-1") -> str:
    return f"jz\nVD d 0 5\nVG g 0 0\n{lines}\n{models}\n.op\n.end\n"


def _m(lines: str, models: str = ".model nm nmos level=1") -> str:
    return f"m\nVD d 0 1\nVG g 0 2\n{lines}\n{models}\n.op\n.end\n"


def _netlist(text: str) -> Netlist:
    return Netlist.from_text(text, dialect=_XYCE)


def _element(text: str, name: str) -> BipolarTransistor | Mosfet | Jfet | Mesfet:
    element = _netlist(text).element(name)
    assert isinstance(element, _TRANSISTORS)
    return element


def _refused(text: str) -> None:
    with pytest.raises(ParseError):
        _netlist(text)


def _codes(text: str) -> set[DiagnosticCode]:
    return {item.code for item in _netlist(text).diagnostics}


def _current(solver: Solver, folder: Path, text: str, source: str) -> float:
    """The current into the circuit from ``source`` (minus its branch current)."""
    return -op(solver, folder, text)[f"{source.lower()}#branch"]


# Node counts by letter (decision 0031 item 1; 5.1 points 1 to 3).


@pytest.mark.parametrize(
    ("lines", "written"),
    [
        ("Q1 c b 0 qn", ["c", "b", "0"]),
        ("Q1 c b 0 s qn\nVS s 0 0", ["c", "b", "0", "s"]),
        ("Q1 c b 0 0 qn", ["c", "b", "0", "0"]),
        ("Q1 c b 0 s t qn\nVS s 0 0\nVT t 0 0", ["c", "b", "0", "s", "t"]),
    ],
    ids=["three", "substrate", "numeric-substrate", "five"],
)
def test_q_takes_three_to_five_nodes(
    solver: Solver, tmp_path: Path, lines: str, written: list[str]
) -> None:
    """3 to 5 nodes are read, the last name before the area being the model; an unbracketed 4th
    node, a name or a number, is the substrate. Xyce runs each on a level whose count it is (level
    1 takes 3 or 4, VBIC level 12 takes 4 or 5)."""
    models = ".model qn npn level=12" if len(written) == 5 else ".model qn npn"
    text = _q(lines, models)
    element = _element(text, "Q1")
    assert [node.name for node in element.nodes] == written
    assert element.model.model_name == "qn"
    assert run(solver, tmp_path, text).ok


@pytest.mark.parametrize("level", [11, 12, 23, 230, 504, 505])
def test_a_sixth_q_node_is_refused_and_xyce_runs_it(
    solver: Solver, tmp_path: Path, level: int
) -> None:
    """A 6th node is a `ParseError`, as the manual writes at most five; Xyce runs it on these
    levels, dropping or joining the extra nodes (the row `refuses/runs`, `manual`)."""
    lines = "Q1 c b 0 n4 n5 n6 qn\nV4 n4 0 0\nV5 n5 0 0\nV6 n6 0 0"
    text = _q(lines, f".model qn npn level={level}")
    _refused(text)
    assert run(solver, tmp_path, text).ok


def test_a_bracketed_substrate_is_a_node_named_with_its_brackets(
    solver: Solver, tmp_path: Path
) -> None:
    """The manual brackets a named substrate (`[s]`); Xyce reads `[s]` as a node of that name,
    beside a node `s`, and the library reads it so (the row `reads/runs`, `manual-error`). An
    unbracketed name is the substrate (above)."""
    text = _q("Q1 c b 0 [s] qn\nVS s 0 0\nR1 [s] 0 1k")
    element = _element(text, "Q1")
    assert [node.name for node in element.nodes] == ["c", "b", "0", "[s]"]
    assert nodes(solver, tmp_path, text) >= {"[s]", "s"}


def test_the_manuals_vbic_example_with_an_unbracketed_thermal_node_runs(
    solver: Solver, tmp_path: Path
) -> None:
    """VBIC level 11 takes a 4th node as its thermal node; Xyce runs the line, which the library
    reads as four nodes and the model."""
    text = _q("Q1 c b 0 dt qv\nVT dt 0 0", ".model qv npn level=11")
    assert [node.name for node in _element(text, "Q1").nodes] == ["c", "b", "0", "dt"]
    assert run(solver, tmp_path, text).ok


@pytest.mark.parametrize(
    ("text", "extra"),
    [
        (_m("M1 d g 0 0 n5 n6 n7 n8 nm"), {"n5", "n6", "n7", "n8"}),
        (_jz("J1 d g 0 x jm"), {"x"}),
        (_jz("J1 d g 0 x y jm"), {"x", "y"}),
        (_jz("Z1 d g 0 x zm"), {"x"}),
    ],
    ids=["m-eight", "j-four", "j-five", "z-four"],
)
def test_xyce_drops_nodes_past_the_letters_count(
    solver: Solver, tmp_path: Path, text: str, extra: set[str]
) -> None:
    """An 8th node on M, and a 4th or 5th on J and Z, are a `ParseError`; Xyce runs the line and
    the extra nodes are not in its circuit (the rows `refuses/ignores`, `manual`)."""
    _refused(text)
    assert not extra & nodes(solver, tmp_path, text)


# The boundary rule (decision 0031 item 2; 5.1 point 4).


def test_a_node_naming_a_model_ends_the_nodes_for_xyce(solver: Solver, tmp_path: Path) -> None:
    """`Q1 c b 0 s qn` with `.model s npn`: the library reads `s` as the substrate and `qn` as the
    model, as decision 0014's boundary rule says, and warns (`NODE_COUNT_MISMATCH`); Xyce takes
    `s` as the model, level 1 taking three nodes, and stops on `qn` (the row `reads/stops`,
    `library-limit`)."""
    text = _q("Q1 c b 0 s qn", ".model qn npn\n.model s npn")
    element = _element(text, "Q1")
    assert element.model.model_name == "qn"
    assert DiagnosticCode.NODE_COUNT_MISMATCH in _codes(text)
    assert not run(solver, tmp_path, text).ok


@pytest.mark.parametrize(
    "text",
    [
        _q("Q1 c b 0 2", ".model 2 npn"),
        _q("Q1 c b 0 off", ".model off npn"),
        _jz("J1 d g 0 4", ".model 4 njf"),
        _jz("Z1 d g 0 4", ".model 4 nmf"),
        _m("M1 d g 0 0 3", ".model 3 nmos level=1"),
    ],
    ids=["q-number", "q-off", "j-number", "z-number", "m-number"],
)
def test_a_number_or_off_in_the_models_place_is_refused_and_xyce_runs_it(
    solver: Solver, tmp_path: Path, text: str
) -> None:
    """A model named by a number, or `off`, is refused (decision 0014 item 4); Xyce runs it (the
    row `refuses/runs`, `imprecise`)."""
    _refused(text)
    assert run(solver, tmp_path, text).ok


@pytest.mark.parametrize(
    ("text", "node"),
    [
        (_q("Q1 c b off qn\nVoff off 0 0"), "off"),
        (_jz("J1 d g off jm\nVoff off 0 0"), "off"),
        (_m("M1 d g 0 off nm\nVoff off 0 0"), "off"),
        (_m("M1 d g 0 tnodeout nm\nVt tnodeout 0 0"), "tnodeout"),
    ],
    ids=["q-off", "j-off", "m-off", "m-tnodeout"],
)
def test_off_or_tnodeout_right_after_the_fixed_nodes_is_a_node(
    solver: Solver, tmp_path: Path, text: str, node: str
) -> None:
    """Right after the fixed nodes `off` (and `tnodeout` on M) is a node, as the library reads it;
    Xyce has it in its circuit."""
    element = _element(text, text.splitlines()[3].split()[0])
    assert node in [item.name for item in element.nodes]
    assert node in nodes(solver, tmp_path, text)


# The area (decision 0031 item 3; 5.1 points 5, 6 and 22).


@pytest.mark.parametrize(
    ("text", "source"),
    [
        (_q("Q1 c b 0 qn 2"), "VC"),
        (_q("Q1 c b 0 qn area=2"), "VC"),
        (_q("Q1 c b 0 qn {2}"), "VC"),
        (_jz("J1 d g 0 jm 2"), "VD"),
        (_jz("J1 d g 0 jm area=2"), "VD"),
        (_jz("Z1 d g 0 zm 2", ".model zm nmf vto=-1"), "VD"),
        (_jz("Z1 d g 0 zm area=2", ".model zm nmf vto=-1"), "VD"),
    ],
    ids=[
        "q-positional",
        "q-named",
        "q-expression",
        "j-positional",
        "j-named",
        "z-positional",
        "z-named",
    ],
)
def test_an_area_of_two_doubles_the_current(
    solver: Solver, tmp_path: Path, text: str, source: str
) -> None:
    """A positional area or `area=` on Q (level 1), J and Z: the current is twice the one without
    it."""
    element = _element(text, text.splitlines()[3].split()[0])
    written = element.area if element.area is not None else element.params[0].value
    assert written is not None
    plain = text.replace(" area=2", "").replace(" {2}", "").replace(" 2\n", "\n")
    assert _current(solver, tmp_path / "area", text, source) == pytest.approx(
        2 * _current(solver, tmp_path / "plain", plain, source)
    )


@pytest.mark.parametrize(
    "text",
    [_q("Q1 c b 0 qn 2 area=3"), _jz("J1 d g 0 jm 2 area=3")],
    ids=["q", "j"],
)
def test_both_area_forms_are_refused_and_xyce_stops(
    solver: Solver, tmp_path: Path, text: str
) -> None:
    _refused(text)
    assert not run(solver, tmp_path, text).ok


@pytest.mark.parametrize(
    ("text", "source", "factor"),
    [
        (_q("Q1 c b 0 qn area=2 area=3"), "VC", 3),
        (_jz("J1 d g 0 jm area=2 area=3"), "VD", 3),
        (_q("Q1 c b 0 qn temp=27 2"), "VC", 2),
        (_jz("J1 d g 0 jm temp=27 2"), "VD", 2),
        (_jz("Z1 d g 0 zm temp=27 2", ".model zm nmf vto=-1"), "VD", 2),
    ],
    ids=[
        "q-area-twice",
        "j-area-twice",
        "q-area-after-a-parameter",
        "j-area-after-a-parameter",
        "z-area-after-a-parameter",
    ],
)
def test_xyce_runs_area_forms_the_library_refuses(
    solver: Solver, tmp_path: Path, text: str, source: str, factor: int
) -> None:
    """`area=` written twice runs with the last value (the repeat row), and a positional area
    after a parameter runs as the area (`refuses/runs`, `manual`): the current is that many times
    the one with neither."""
    _refused(text)
    first = text.splitlines()[3]
    plain = text.replace(first, " ".join(first.split()[:5]))
    assert _current(solver, tmp_path / "area", text, source) == pytest.approx(
        factor * _current(solver, tmp_path / "plain", plain, source)
    )


@pytest.mark.parametrize(
    "text",
    [
        _q("Q1 c b 0 qn 2 m=2"),
        _q("Q1 c b 0 qn 2 off=1"),
        _jz("J1 d g 0 jm 2 dtemp=5"),
        _jz("Z1 d g 0 zm 2 dtemp=1"),
    ],
    ids=["q-m", "q-off-value", "j-dtemp", "z-dtemp"],
)
def test_a_positional_area_then_parameters_is_read_and_xyce_stops(
    solver: Solver, tmp_path: Path, text: str
) -> None:
    """The manual writes `<model> [area] [params]` (the J and Z forms); the library reads it
    (G1 point 6 (a)) and Xyce stops on it (the row `reads/stops`, `manual`)."""
    element = _element(text, text.splitlines()[3].split()[0])
    assert isinstance(element.area, NumericValue) and element.area.text == "2"
    assert not run(solver, tmp_path, text).ok


@pytest.mark.parametrize(
    "text",
    [_q("Q1 c b 0 qn 2 temp=50"), _jz("J1 d g 0 jm 2 temp=50"), _jz("Z1 d g 0 zm 2 temp=50")],
    ids=["q", "j", "z"],
)
def test_a_positional_area_then_a_lone_temp_runs(solver: Solver, tmp_path: Path, text: str) -> None:
    """The exception to the row above: `<area> temp=` alone runs."""
    element = _element(text, text.splitlines()[3].split()[0])
    assert element.area is not None
    assert run(solver, tmp_path, text).ok


_LATCH = (
    "latch\nVCC vcc 0 5\nR1 vcc c1 1k\nR2 vcc c2 1k\nR3 c1 b2 10k\nR4 c2 b1 10k\n"
    "{q1}\nQ2 c2 b2 0 qn\n.model qn npn bf=100\n.op\n.end\n"
)


def test_off_after_a_positional_area_is_read_and_xyce_ignores_it(
    solver: Solver, tmp_path: Path
) -> None:
    """A symmetric latch settles in its middle point; `off` on Q1 makes Q1 the side that is off
    (its collector high). After `area=1` it does so; after a positional `1`, Xyce runs the line
    and ignores `off` (the row `reads/ignores`, `manual`; 5.1 point 22)."""
    middle = op(solver, tmp_path / "none", _LATCH.format(q1="Q1 c1 b1 0 qn"))
    named = op(solver, tmp_path / "named", _LATCH.format(q1="Q1 c1 b1 0 qn area=1 off"))
    text = _LATCH.format(q1="Q1 c1 b1 0 qn 1 off")
    element = _element(text, "Q1")
    assert element.area is not None and [flag.name for flag in element.flags] == ["off"]
    positional = op(solver, tmp_path / "positional", text)
    assert named["c1"] > middle["c1"] + 1
    assert positional["c1"] == pytest.approx(middle["c1"])


def test_an_area_on_a_level_without_one_is_read_and_xyce_stops(
    solver: Solver, tmp_path: Path
) -> None:
    """VBIC, FBH, HICUM and MEXTRAM have no area: Xyce stops on either form at VBIC level 11,
    which the library reads, as the level is the model's (the level row, `reads/stops`,
    `library-limit`)."""
    for name, line in {"positional": "Q1 c b 0 qn 2", "named": "Q1 c b 0 qn area=2"}.items():
        text = _q(line, ".model qn npn level=11")
        _netlist(text)
        assert not run(solver, tmp_path / name, text).ok


@pytest.mark.parametrize(
    "text",
    [_m("M1 d g 0 0 nm 2"), _m("M1 d g 0 0 nm area=2")],
    ids=["positional", "named"],
)
def test_m_has_no_area(solver: Solver, tmp_path: Path, text: str) -> None:
    _refused(text)
    assert not run(solver, tmp_path, text).ok


# Instance parameters, `off` and their repeats (decision 0031 item 4; 5.1 points 7 and 8).


@pytest.mark.parametrize(
    "text",
    [
        _q("Q1 c b 0 qn foo=1"),
        _jz("J1 d g 0 jm foo=1"),
        _jz("Z1 d g 0 zm foo=1"),
        _m("M1 d g 0 0 nm foo=1"),
        _m("M1 d g 0 0 nm thermal"),
        _jz("J1 d g 0 jm m=2"),
        _jz("Z1 d g 0 zm m=2"),
        _jz("J1 d g 0 jm off"),
        _jz("J1 d g 0 jm off=1"),
        _jz("Z1 d g 0 zm off"),
        _jz("J1 d g 0 jm ic=1,0"),
        _jz("Z1 d g 0 zm ic=1,0"),
    ],
    ids=[
        "q-unknown",
        "j-unknown",
        "z-unknown",
        "m-unknown",
        "m-thermal",
        "j-m",
        "z-m",
        "j-off",
        "j-off-value",
        "z-off",
        "j-ic",
        "z-ic",
    ],
)
def test_a_name_outside_the_letters_list_is_refused_and_xyce_stops(
    solver: Solver, tmp_path: Path, text: str
) -> None:
    """The lists are closed (decision 0031 item 4): an unknown name, ngspice's `thermal`, and
    `M=`, `off` and `IC=` on J and Z; Xyce stops on each, so no row."""
    _refused(text)
    assert not run(solver, tmp_path, text).ok


@pytest.mark.parametrize(
    "text",
    [
        _q("Q1 c b 0 qn sw_et=0"),
        _q("Q1 c b 0 qn dt=1"),
        _m("M1 d g 0 0 nm bjtoff=1"),
    ],
    ids=["q-vbic-sw-et-on-level-1", "q-hicum-dt-on-level-1", "m-soi-bjtoff-on-level-1"],
)
def test_a_name_of_another_level_is_read_and_xyce_stops(
    solver: Solver, tmp_path: Path, text: str
) -> None:
    """Each list is the union of the letter's level tables; Xyce takes only the model's level's
    (the level row, `reads/stops`, `library-limit`)."""
    _netlist(text)
    assert not run(solver, tmp_path, text).ok


@pytest.mark.parametrize(
    ("text", "source", "factor"),
    [
        (_q("Q1 c b 0 qn m=2 m=3"), "VC", 3),
        (_m("M1 d g 0 0 nm m=2 m=3"), "VD", 3),
        (_jz("J1 d g 0 jm area=1 area=2"), "VD", 2),
    ],
    ids=["q-m", "m-m", "j-area"],
)
def test_a_parameter_written_twice_is_refused_and_xyce_takes_the_last(
    solver: Solver, tmp_path: Path, text: str, source: str, factor: int
) -> None:
    """The repeat row (`refuses/runs`, `manual`), on the transistors: the last value rules."""
    _refused(text)
    first = text.splitlines()[3]
    plain = text.replace(first, " ".join(first.split()[: 6 if first[0] == "M" else 5]))
    assert _current(solver, tmp_path / "twice", text, source) == pytest.approx(
        factor * _current(solver, tmp_path / "plain", plain, source)
    )


def test_m_takes_its_parameters_and_m(solver: Solver, tmp_path: Path) -> None:
    """`M=2` doubles an M's current; `L=`, `W=` and the geometry names are read."""
    text = _m("M1 d g 0 0 nm L=2u W=10u AD=1p AS=1p PD=1u PS=1u NRD=1 NRS=1 m=2")
    assert len(_element(text, "M1").params) == 9
    assert run(solver, tmp_path / "geometry", text).ok
    doubled = _m("M1 d g 0 0 nm m=2")
    assert _current(solver, tmp_path / "m", doubled, "VD") == pytest.approx(
        2 * _current(solver, tmp_path / "plain", _m("M1 d g 0 0 nm"), "VD")
    )


@pytest.mark.parametrize(
    "text",
    [_q("Q1 c b 0 qn temp=50 dtemp=1"), _jz("J1 d g 0 jm temp=50 dtemp=1")],
    ids=["q", "j"],
)
def test_temp_with_dtemp_is_read_and_xyce_ignores_dtemp(
    solver: Solver, tmp_path: Path, text: str
) -> None:
    """Both are read; Xyce warns that it ignores `dtemp` beside `temp` (the row `reads/ignores`,
    `imprecise`), and the current is the one with `temp=` alone."""
    assert len(_element(text, text.splitlines()[3].split()[0]).params) == 2
    result = run(solver, tmp_path / "both", text)
    assert result.ok
    assert any("dtemp ignored" in item.message for item in result.warnings)
    source = "VC" if text.startswith("q") else "VD"
    assert _current(solver, tmp_path / "both-op", text, source) == pytest.approx(
        _current(solver, tmp_path / "temp", text.replace(" dtemp=1", ""), source)
    )


@pytest.mark.parametrize(
    "text",
    [
        _q("Q1 c b 0 qn off"),
        _q("Q1 c b 0 qn off=1"),
        _m("M1 d g 0 0 nm off"),
        _m("M1 d g 0 0 nm OFF=1"),
    ],
    ids=["q-off", "q-off-value", "m-off", "m-off-value"],
)
def test_off_bare_or_with_a_value_is_a_flag(solver: Solver, tmp_path: Path, text: str) -> None:
    flags = _element(text, text.splitlines()[3].split()[0]).flags
    assert len(flags) == 1 and isinstance(flags[0], Flag)
    assert run(solver, tmp_path, text).ok


@pytest.mark.parametrize(
    "text",
    [_q("Q1 c b 0 qn off off"), _q("Q1 c b 0 qn off off=1"), _m("M1 d g 0 0 nm off off")],
    ids=["q-off-off", "q-off-and-value", "m-off-off"],
)
def test_off_written_twice_is_refused_and_xyce_runs_it(
    solver: Solver, tmp_path: Path, text: str
) -> None:
    """The flag written twice, in either form (the row `refuses/runs`, `manual`)."""
    _refused(text)
    assert run(solver, tmp_path, text).ok


def test_q_off_on_a_latch_turns_that_side_off(solver: Solver, tmp_path: Path) -> None:
    """`off` and `OFF=1` give the latch the state with Q1 off, as the manual says."""
    middle = op(solver, tmp_path / "none", _LATCH.format(q1="Q1 c1 b1 0 qn"))
    for name, line in {"bare": "Q1 c1 b1 0 qn off", "value": "Q1 c1 b1 0 qn OFF=1"}.items():
        state = op(solver, tmp_path / name, _LATCH.format(q1=line))
        assert state["c1"] > middle["c1"] + 1


# TNODEOUT (decision 0031 item 4; 5.1 point 7).


_SOI = ".model nm nmos level=10"
_SEVEN = "M1 d g 0 0 n5 n6 n7 nm{tail}\nV5 n5 0 0\nV6 n6 0 0\nV7 n7 0 0"


def test_a_bare_tnodeout_is_refused_and_xyce_stops(solver: Solver, tmp_path: Path) -> None:
    """The manual writes a bare `TNODEOUT` flag; Xyce stops on it ("reached end of line while
    looking for parameters"), and the library refuses it with the hint "write `TNODEOUT=1`" (the
    row `refuses/stops`, `manual-error`)."""
    text = _m(_SEVEN.format(tail=" tnodeout"), _SOI)
    with pytest.raises(ParseError, match="TNODEOUT=1"):
        _netlist(text)
    assert not run(solver, tmp_path, text).ok


@pytest.mark.parametrize("value", ["1", "0"])
def test_tnodeout_with_any_value_lets_level_10_take_seven_nodes(
    solver: Solver, tmp_path: Path, value: str
) -> None:
    """Without `TNODEOUT=` BSIM-SOI level 10 takes 4 to 6 nodes and stops on a 7th ("Over 6 nodes
    without tnodeout set"); with it, any value counting as set, it takes 5 to 7. The library reads
    `TNODEOUT=` as a parameter and warns only on the line without it."""
    text = _m(_SEVEN.format(tail=f" tnodeout={value}"), _SOI)
    assert [param.name for param in _element(text, "M1").params] == ["tnodeout"]
    assert DiagnosticCode.NODE_COUNT_MISMATCH not in _codes(text)
    assert run(solver, tmp_path / "set", text).ok
    unset = _m(_SEVEN.format(tail=""), _SOI)
    assert DiagnosticCode.NODE_COUNT_MISMATCH in _codes(unset)
    assert not run(solver, tmp_path / "unset", unset).ok


# `IC=` (decision 0031 item 4; 5.1 point 9; X-M4 B2 and B3).


@pytest.mark.parametrize(
    "text",
    [
        _q("Q1 c b 0 qn ic=0.7,5"),
        _q("Q1 c b 0 qn ic = 0.7 , 5"),
        _q("Q1 c b 0 qn ic= 0.7 ,5"),
        _q("Q1 c b 0 qn ic1=0.7 ic2=5"),
        _m("M1 d g 0 0 nm IC=1,2,0"),
        _m("M1 d g 0 0 nm IC=1, 2, 0"),
        _m("M1 d g 0 0 nm ic={1+1},2"),
        _m("M1 d g 0 0 nm IC1=1 IC2=2"),
    ],
    ids=[
        "q",
        "q-blanks",
        "q-blank-first",
        "q-ic1-ic2",
        "m",
        "m-blanks",
        "m-expression",
        "m-ic1-ic2",
    ],
)
def test_ic_lists_are_read_and_run(solver: Solver, tmp_path: Path, text: str) -> None:
    """A comma list with blanks around `=` and `,` and expressions, or the scalar `IC1=`, `IC2=`."""
    assert _element(text, text.splitlines()[3].split()[0]).params
    assert run(solver, tmp_path, text).ok


@pytest.mark.parametrize(
    "text",
    [
        _q("Q1 c b 0 qn ic=0.7,5,1"),
        _q("Q1 c b 0 qn ic=0.7,"),
        _q("Q1 c b 0 qn ic=0.7,,5"),
        _m("M1 d g 0 0 nm IC=1,"),
        _m("M1 d g 0 n4 nm IC=1,2,0,0,0,0\nV4 n4 0 0", _SOI),
    ],
    ids=["q-three", "q-trailing-comma", "q-empty-element", "m-trailing-comma", "m-six"],
)
def test_ic_forms_are_refused_and_xyce_stops(solver: Solver, tmp_path: Path, text: str) -> None:
    """More values than the letter takes (Q 2, M 5), a trailing comma and an empty element: the
    library refuses each and Xyce stops, so no row."""
    _refused(text)
    assert not run(solver, tmp_path, text).ok


def test_an_ic_count_above_the_levels_is_read_and_xyce_stops(
    solver: Solver, tmp_path: Path
) -> None:
    """Level 1 takes three `IC=` values (Vds, Vgs, Vbs); a fourth is within M's five, so the
    library reads it, and Xyce stops (the row `reads/stops`, `library-limit`)."""
    three = _m("M1 d g 0 n4 nm IC=1,2,0\nV4 n4 0 0")
    four = _m("M1 d g 0 n4 nm IC=1,2,0,0\nV4 n4 0 0")
    _netlist(four)
    assert run(solver, tmp_path / "three", three).ok
    assert not run(solver, tmp_path / "four", four).ok


@pytest.mark.parametrize(
    "text",
    [
        _q("Q1 c b 0 qn ic=0.7,5 ic1=0.6"),
        _q("Q1 c b 0 qn ic1=0.6 ic=0.7,5"),
        _q("Q1 c b 0 qn ic=0.7 ic2=4"),
        _m("M1 d g 0 0 nm IC=1,2,0 IC1=0.5"),
        _m("M1 d g 0 0 nm IC1=0.5 IC=1,2,0"),
        _m("M1 d g 0 0 nm IC=1,2 IC3=0"),
    ],
    ids=[
        "q-ic-then-ic1",
        "q-ic1-then-ic",
        "q-ic-and-ic2",
        "m-ic-then-ic1",
        "m-ic1-then-ic",
        "m-ic-and-ic3",
    ],
)
def test_ic_beside_an_icn_is_read_and_xyce_runs_it(
    solver: Solver, tmp_path: Path, text: str
) -> None:
    """`IC=` is the vector of `IC1=`, `IC2=`, … (`[xyce-ref]` §2.3.17 p241, §2.3.20 p296); written
    beside one of its own elements it sets that element twice. The library reads both, as two
    names, and Xyce runs the line without a warning (the row `reads/runs`, `imprecise`; which
    value Xyce uses was not observed: an operating point does not show it)."""
    element = _element(text, text.splitlines()[3].split()[0])
    assert len(element.params) == 2
    result = run(solver, tmp_path, text)
    assert result.ok
    assert not [item for item in result.warnings if "IC" in item.message.upper()]


# Case, `+` lines and comments (5.1 point 10).


@pytest.mark.parametrize(
    "text",
    [
        _q("q1 C\n+ B 0\n+ QN AREA=2"),
        _q("Q1 c b 0\n* a comment\n+ qn 2"),
        _q("Q1 c b 0 qn ; a comment"),
        _m("m1 D\n+ G 0 0\n+ NM w=10U\n+ l=2u"),
    ],
    ids=["q-case-and-continuation", "q-comment-between", "q-trailing-comment", "m-case"],
)
def test_case_continuations_and_comments_fold_as_elsewhere(
    solver: Solver, tmp_path: Path, text: str
) -> None:
    _netlist(text)
    assert run(solver, tmp_path, text).ok
