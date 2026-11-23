"""xyce transistor lines: Q, J and Z (X-M4 B2; decision 0031 items 1 to 4; xm4-tasks 5.1 points
1 to 10 and 22). M is test_xyce_mosfet.py's (B3).

The line shape is decision 0014 item 1's: the fixed nodes, then names, the last of which is the
model, then an optional positional area, then flags and parameters. Each letter's instance
parameters are a closed list, as on R, C, L and D (`XY-IPN-001`).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from netlistmod import (
    BipolarTransistor,
    Flag,
    Formula,
    Jfet,
    Mesfet,
    ModelReference,
    Node,
    NumericValue,
    ParamAssignment,
    ParseError,
    SourceText,
    Span,
    ValueList,
    parse,
)
from netlistmod.dialects import _XYCE, Dialect
from netlistmod.model._rules_xyce import _PARAM_LISTS

GRAMMAR = Path(__file__).parents[3] / "src" / "netlistmod" / "grammar" / "xyce.lark"

# [xyce-ref] §2.3.17 p247–279: Tables 2-67 (level 1), 2-69 and 2-71 (VBIC), 2-73 (FBH HBT_X), 2-75
# (HICUM L0), 2-80 and 2-83 (MEXTRAM), with the vector `IC` of IC1 and IC2 (p241) and without
# `OFF`, a flag. J: Tables 2-86 and 2-88 (§2.3.18 p287–288); Z: Table 2-90 (§2.3.19 p291).
Q_NAMES = (
    "area",
    "dt",
    "dta",
    "dtemp",
    "ic",
    "ic1",
    "ic2",
    "l",
    "m",
    "mult",
    "n",
    "sw_et",
    "sw_noise",
    "temp",
    "trise",
    "w",
)
JZ_NAMES = ("area", "dtemp", "temp")


def _parse(text: str) -> Any:
    return parse(SourceText(text), _XYCE)


def _element(line: str) -> Any:
    text = f"t\n{line}\n.END\n"
    items = _parse(text).items
    position = 0
    for item in items:
        assert item.span.start == position
        position = item.span.end
    assert position == len(text)
    return items[1]


def _error(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        _parse(f"t\n{line}\n.END\n")
    return captured.value


def _shape(line: str) -> tuple[list[str], str, str | None]:
    element = _element(line)
    area = element.area
    text = None if area is None else line[area.span.start - 2 : area.span.end - 2]
    return [node.name for node in element.nodes], element.model.model_name, text


# The line shape (XY-XTR-001)


@pytest.mark.parametrize(
    ("line", "nodes", "model", "area"),
    [
        ("Q1 c b e qm", ["c", "b", "e"], "qm", None),
        ("Q1 c b e s qm", ["c", "b", "e", "s"], "qm", None),
        ("Q1 c b e s dt qm", ["c", "b", "e", "s", "dt"], "qm", None),
        # The manual's examples (§2.3.17 p241): a numeric substrate, a bracketed one, VBIC's.
        ("Q12 14 2 0 1 NPN2 2.0", ["14", "2", "0", "1"], "NPN2", "2.0"),
        ("Q6 VC 4 11 [SUB] LAXPNP", ["VC", "4", "11", "[SUB]"], "LAXPNP", None),
        ("Q7 Coll Base Emit DT VBIC13MODEL2", ["Coll", "Base", "Emit", "DT"], "VBIC13MODEL2", None),
        ("Q1 c b e qm 2", ["c", "b", "e"], "qm", "2"),
        ("Q1 c b e s qm {a*2}", ["c", "b", "e", "s"], "qm", "{a*2}"),
        ("Q1 c b e s t qm 'a'", ["c", "b", "e", "s", "t"], "qm", "'a'"),
        ("Q1 c b e qm 2 qx", ["c", "b", "e", "qm", "2"], "qx", None),
        ("Q1 X1:c b e qm", ["X1:c", "b", "e"], "qm", None),
        ("q1 C B E QM", ["C", "B", "E"], "QM", None),
        ("J1 d g s jm", ["d", "g", "s"], "jm", None),
        ("J13 22 14 23 JNOM 2.0", ["22", "14", "23"], "JNOM", "2.0"),
        ("J1 1 2 0 2N5114", ["1", "2", "0"], "2N5114", None),
        ("Z1 d g s zm {2}", ["d", "g", "s"], "zm", "{2}"),
    ],
)
def test_the_model_is_the_last_name_before_the_area(
    line: str, nodes: list[str], model: str, area: str | None
) -> None:
    assert _shape(line) == (nodes, model, area)


def test_off_before_the_model_is_a_node_and_after_it_a_flag() -> None:
    # 5.1 point 4: right after the fixed nodes only a name may stand, so `off` is a node.
    assert _shape("Q1 c b e off qm") == (["c", "b", "e", "off"], "qm", None)
    transistor = _element("Q1 c b e qm off")
    assert transistor.flags == (Flag("off", Span(14, 17)),)


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("Q1 c b e 2", "ends too early"),
        ("Q1 c b e 1 2 3", "a model name cannot be a number"),
        ("Q1 c b e 1 2 3k", "a model name cannot be a number"),
        ("Q1 c b e off", "a model name cannot be the keyword `off`"),
        ("Q1 c b e 1 2 OFF", "a model name cannot be the keyword `off`"),
        ("Q1 c b e s a:m", "a model name cannot hold `:`"),
        ("J1 d g s 2", "a model name cannot be a number"),
        ("J1 d g s off", "a model name cannot be the keyword `off`"),
        ("Z1 d g s 1k", "a model name cannot be a number"),
        ("Z1 d g s x:z", "a model name cannot hold `:`"),
    ],
)
def test_a_number_off_or_a_colon_in_the_models_place_is_refused(line: str, message: str) -> None:
    # Decision 0031 item 2: Xyce runs `.model 2 npn` (a `refuses/runs` row); the library keeps
    # decision 0014 item 4.
    assert message in str(_error(line))


@pytest.mark.parametrize(
    "line",
    [
        "Q1 c b e s t u qm",
        "Q1 c b e s t u v qm",
        "J1 d g s b jm",
        "Z1 d g s b zm",
        "Q1 c b",
        "J1 d g s",
    ],
)
def test_node_counts_outside_the_letters_range_are_refused(line: str) -> None:
    # Decision 0031 item 1: Q 3 to 5 nodes, J and Z exactly 3, by letter.
    _error(line)


def test_continued_transistor_lines_join() -> None:
    transistor = _element("Q1 c b e\n+ qm 2 ; area\n+ temp=27")
    assert _shape("Q1 c b e\n+ qm 2") == (["c", "b", "e"], "qm", "2")
    assert [param.name for param in transistor.params] == ["temp"]
    assert isinstance(_element("J1 d g\n* c\n+ s jm area=2"), Jfet)


# The area


def test_the_area_is_positional_or_named() -> None:
    transistor = _element("Q1 c b e qm 2 off temp=3")
    assert transistor.area == NumericValue("2", Span(14, 15))
    assert transistor.flags == (Flag("off", Span(16, 19)),)
    named = _element("J1 d g s jm area=2 dtemp=1")
    assert named.area is None
    assert [param.name for param in named.params] == ["area", "dtemp"]
    assert _element("Z1 d g s zm {a}").area == Formula("a", "{", Span(14, 17))
    # G1 6 (a): a positional area followed by parameters, the manual's J and Z form.
    assert _element("J1 d g s jm 2 temp=1 dtemp=2").area == NumericValue("2", Span(14, 15))


@pytest.mark.parametrize(
    ("line", "column", "message"),
    [
        ("Q1 c b e qm 2 area=3", 15, "the area is given twice"),
        ("J1 d g s jm {2} AREA=3", 17, "the area is given twice"),
        ("Q1 c b e qm temp=1 2", 20, "a positional area stands right after the model"),
        ("Q1 c b e qm off 2", 17, "a positional area stands right after the model"),
        ("J1 d g s jm temp=1 {2}", 20, "a positional area stands right after the model"),
        ("Z1 d g s zm dtemp=1 2", 21, "a positional area stands right after the model"),
        ("J1 d g s jm 2 3", 15, ""),
    ],
)
def test_area_forms_are_refused(line: str, column: int, message: str) -> None:
    # 5.1 point 5: both forms stop Xyce; a positional area after a parameter runs as the area
    # (a `refuses/runs` row).
    error = _error(line)
    assert error.column == column
    assert message in error.reason


# Flags, IC= and parameters (XY-BJT-001, XY-JFT-001, XY-MES-001)


def test_the_bjt_forms() -> None:
    transistor = _element("Q1 c b e s qm 2 OFF=1 M=2 IC = 0.6 , 5")
    assert isinstance(transistor, BipolarTransistor)
    assert transistor.model == ModelReference("qm", Span(13, 15))
    assert transistor.nodes[3] == Node("s", Span(11, 12))
    assert transistor.flags == (Flag("OFF", Span(18, 23), NumericValue("1", Span(22, 23))),)
    m, ic = transistor.params
    assert m == ParamAssignment("M", NumericValue("2", Span(26, 27)), Span(24, 27), Span(24, 25))
    assert ic.name == "IC"
    assert isinstance(ic.value, ValueList)
    assert [value.text for value in ic.value.values] == ["0.6", "5"]
    assert [p.name for p in _element("Q1 c b e qm IC={v1}").params] == ["IC"]


def test_the_jfet_and_mesfet_forms() -> None:
    jfet = _element("J1 d g s jm 2 TEMP=30 dtemp=1")
    assert isinstance(jfet, Jfet)
    assert jfet.flags == ()
    assert [param.name for param in jfet.params] == ["TEMP", "dtemp"]
    mesfet = _element("Z1 d g s zm area={a}")
    assert isinstance(mesfet, Mesfet)
    assert mesfet.params[0].value == Formula("a", "{", Span(19, 22))


@pytest.mark.parametrize(
    ("letter", "name"),
    [("Q", n) for n in Q_NAMES] + [(letter, n) for letter in "JZ" for n in JZ_NAMES],
)
def test_each_listed_name_is_read_in_any_case(letter: str, name: str) -> None:
    for spelling in (name, name.upper()):
        element = _element(f"{letter}1 a b c mod {spelling}=1")
        assert [param.name for param in element.params] == [spelling]


def test_the_grammar_and_the_message_hold_the_same_lists() -> None:
    text = GRAMMAR.read_text(encoding="utf-8")
    for terminal, names, key, extra in (
        ("Q_PARAM_KW", Q_NAMES, "q", {"off"}),
        ("JZ_PARAM_KW", JZ_NAMES, "jz", set()),
    ):
        match = re.search(rf"^{terminal}\.4: /\(\?:([a-z0-9_|]+)\)", text, re.MULTILINE)
        assert match is not None
        listed = set(match.group(1).split("|")) | ({"ic"} if key == "q" else set())
        assert tuple(sorted(listed)) == names
        words = set(re.findall(r"[a-z_0-9]+", _PARAM_LISTS[key][2])) - {"and", "or"}
        assert words == set(names) | extra


@pytest.mark.parametrize(
    ("line", "device"),
    [
        ("Q1 c b e qm foo=1", "bipolar transistor"),
        ("Q1 c b e qm bf=100", "bipolar transistor"),  # a model parameter
        ("Q1 c b e qm thermal=1", "bipolar transistor"),
        ("Q1 c b e qm 2 off temp=1 tnom=27", "bipolar transistor"),
        ("J1 d g s jm m=2", "JFET or MESFET"),
        ("J1 d g s jm IC=1", "JFET or MESFET"),
        ("J1 d g s jm OFF=1", "JFET or MESFET"),
        ("Z1 d g s zm 2 mult=2", "JFET or MESFET"),
    ],
)
def test_a_name_outside_the_list_is_refused_at_the_name(line: str, device: str) -> None:
    # 5.1 point 8: Xyce stops on an unknown name on every letter.
    error = _error(line)
    name = line.split()[-1].split("=")[0]
    assert error.column == line.rindex(name) + 1
    assert f"is not a parameter of a Xyce {device}" in error.reason
    assert "The reference guide lists" in error.reason


@pytest.mark.parametrize("line", ["J1 d g s jm off", "Z1 d g s zm 2 OFF", "J1 d g s jm temp=1 off"])
def test_off_is_refused_on_j_and_z(line: str) -> None:
    error = _error(line)
    assert error.column == line.lower().rindex("off") + 1
    assert "is not a flag of a Xyce J or Z line" in error.reason


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("Q1 c b e qm IC=1,2,3", "takes at most two values"),
        ("Q1 c b e qm IC=1,", "ends too early"),
        ("Q1 c b e qm IC=1,,2", ""),
        ("Q1 c b e qm IC=,1", ""),
    ],
)
def test_ic_forms_are_refused(line: str, message: str) -> None:
    # 5.1 point 9: a trailing or empty element stops Xyce; Q takes at most two values.
    assert message in str(_error(line))


@pytest.mark.parametrize(
    ("line", "second"),
    [
        ("Q1 c b e qm temp=1 TEMP=2", "TEMP=2"),
        ("Q1 c b e qm IC=1 ic=2", "ic=2"),
        ("Q1 c b e qm area=1\n+ area=2", "area=2"),
        ("J1 d g s jm dtemp=1 dtemp=2", "dtemp=2"),
        ("Z1 d g s zm area=1 AREA=2", "AREA=2"),
    ],
)
def test_a_parameter_written_twice_is_refused(line: str, second: str) -> None:
    # 5.1 point 8: Xyce runs it with the last (the repeat row).
    error = _error(line)
    assert "is written twice on this line" in error.reason
    last_line = line.splitlines()[-1]
    assert error.column == last_line.rindex(second) + 1


@pytest.mark.parametrize(
    ("line", "column", "written"),
    [
        ("Q1 c b e qm off off", 17, "`off`"),
        ("Q1 c b e qm OFF OFF=1", 17, "`OFF=`"),
        ("Q1 c b e qm OFF=1 off", 19, "`off`"),
        ("Q1 c b e qm OFF=0 OFF=1", 19, "`OFF=`"),
        ("Q1 c b e qm 2 off temp=1\n+ OFF", 3, "`OFF`"),
    ],
)
def test_off_written_twice_is_refused_at_the_second(line: str, column: int, written: str) -> None:
    # 5.1 point 8: Xyce runs it (the repeat row); the flag counts once, bare or with a value.
    error = _error(line)
    assert error.column == column
    assert f"{written} is written twice on this line" in error.reason
    assert "write it once" in error.reason


def test_a_diode_still_reads_off_twice() -> None:
    # D is unchanged by X-M4 B2.
    assert len(_parse("t\nD1 a b dm off OFF=1\n.END\n").items[1].flags) == 2


# The other dialects


@pytest.mark.parametrize("dialect", [Dialect.NGSPICE, Dialect.LTSPICE])
def test_the_other_dialects_keep_their_own_transistor_lines(dialect: Dialect) -> None:
    text = "t\nJ1 d g s jm 2 foo=1\n.end\n"
    if dialect is Dialect.LTSPICE:
        with pytest.raises(ParseError):
            parse(SourceText(text), Dialect.LTSPICE)
    else:
        assert parse(SourceText(text), Dialect.NGSPICE).items[1].params[0].name == "foo"
    with pytest.raises(ParseError, match="an ngspice Q writes its area as `area=2`"):
        parse(SourceText("t\nQ1 c b e qm 2\n.end\n"), Dialect.NGSPICE)
