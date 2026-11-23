"""xyce MOSFET lines (X-M4 B3; decision 0031 items 1 to 4; xm4-tasks 5.1 points 2, 4, 7, 8, 9
and 11).

M takes Q's line shape (`XY-XTR-001`): 3 to 7 nodes, then names, the last of which is the model,
then flags and parameters; it has no area. Its instance parameters are a closed list, the union
of the instance tables of every M level in the reference guide (`XY-MOS-001`).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from netlistmod import (
    Flag,
    Formula,
    ModelReference,
    Mosfet,
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

# The instance-parameter tables of every M level ([xyce-ref] §2.3.20 p304–745), read from the
# manual's PDF table by table. The MVS levels (Tables 2-138 and 2-139) have model tables only.
TABLES = {
    "2-92": "ad as dtemp ic1 ic2 ic3 l m nrd nrs off pd ps temp w",
    "2-94": "ad as dtemp ic1 ic2 ic3 l m nrd nrs off pd ps temp w",
    "2-96": "ad as dtemp ic1 ic2 ic3 l m nrd nrs off pd ps temp w",
    "2-98": "ad as dtemp ic1 ic2 ic3 l m nrd nrs off pd ps temp w",
    "2-100": "ad as ic1 ic2 ic3 l m nqsmod nrd nrs off pd ps temp w",
    "2-102": (
        "ad aebcp agbcp as bjtoff cth0 debug dtemp frbody ic1 ic2 ic3 ic4 ic5 l m nbc nrb nrd "
        "nrs nseg off pd pdbcp ps psbcp rgatemod rth0 soimod temp tnodeout vbsusr vldebug w"
    ),
    "2-104": (
        "acnqsmod ad as delvt0 delvto dtemp geomod ic1 ic2 ic3 l m min nf ngcon nrd nrs off pd "
        "ps rbdb rbodymod rbpb rbpd rbps rbsb rgatemod rgeomod sa sb sc sca scb scc sd temp "
        "trnqsmod w xgw"
    ),
    "2-106": "ad as dtemp l m nrd nrs pd ps temp w",
    "2-108": (
        "ad aebcp agbcp agbcp2 agbcpd as bjtoff cth0 debug delvto dtemp frbody l m nbc nf nrb "
        "nrd nrs nseg off pd pdbcp ps psbcp rbdb rbsb rth0 sa sb sd shmod soimod tnodeout w"
    ),
    "2-111": (
        "ad aebcp agbcp agbcp2 agbcpd as bjtoff cth0 delvto dtemp frbody l m nbc nf nrb nrd nrs "
        "nseg off pd pdbcp ps psbcp rbdb rbsb rth0 sa sb sd shmod soimod tnodeout w"
    ),
    "2-114": (
        "ad as geomod l m minz nf ngcon nrd nrs pd ps rbdb rbodymod rbpb rbpd rbps rbsb "
        "rgatemod rgeomod sa sb sc sca scb scc sd vfbsdoff w xgw"
    ),
    "2-117": (
        "abdrain absource ad as delvto factuo l lgdrain lgsource lsdrain lssource m mult nf "
        "ngcon pd ps sa sb sc sca scb scc sd w xgw"
    ),
    "2-120": (
        "abdrain absource ad as delvto delvtoedge dta factuo factuoedge jw l lgdrain lgsource "
        "lsdrain lssource m mult nf ngcon nrd nrs pd ps sa sb sc sca scb scc sd w xgw"
    ),
    "2-123": (
        "abdrain absource ad as delvto delvtoedge dta factuo factuoedge jw l lgdrain lgsource "
        "lsdrain lssource m mult nf ngcon nrd nrs pd ps sa sb sc sca scb scc sd w xgw"
    ),
    "2-126": (
        "adej adeo asej aseo cdsp cgdp cgsp covd covs d dach1 dach2 dach3 dach4 dach5 dach6 "
        "delvtrand dtemp dws1 dws2 dws3 dws4 dws5 dws6 fpitch hpff ids0mult igb0mult igc0mult l "
        "lrsd m mobscmod nf nfin nfinnom ngaa ngcon nrd nrs pdej pdeo psej pseo subbandmod tfin "
        "tgaa tsus u0mult wgaa xl xw"
    ),
    "2-129": (
        "adej adeo asej aseo cdsp cgdp cgsp covd covs d fpitch l lrsd m nf nfin nfinnom ngcon "
        "nrd nrs pdej pdeo psej pseo tfin"
    ),
    "2-132": (
        "adej adeo asej aseo cdsp cgdp cgsp covd covs d fpitch l lrsd nfin ngcon nrd nrs pdej "
        "pdeo psej pseo tfin"
    ),
    "2-135": (
        "adej adeo asej aseo cdsp cgdp cgsp covd covs d fpitch l lrsd m nf nfin ngcon nrd nrs "
        "pdej pdeo psej pseo tfin"
    ),
    "2-140": "dtemp l ngf w",
    "2-143": "ad as l m ns pd ps w",
    "2-145": "ad as l m nf pd ps sa sb sd w",
    "2-147": "adrain asource delvto factuo l m mult nf pdrain psource sa sb sd w",
}
# The closed list: the tables' union without `OFF`, a flag, and with the vector `IC` of IC1 to IC5
# ([xyce-ref] §2.3.20 p296).
M_NAMES = tuple(
    """
    abdrain absource acnqsmod ad adej adeo adrain aebcp agbcp agbcp2 agbcpd as asej aseo
    asource bjtoff cdsp cgdp cgsp covd covs cth0 d dach1 dach2 dach3 dach4 dach5 dach6 debug
    delvt0 delvto delvtoedge delvtrand dta dtemp dws1 dws2 dws3 dws4 dws5 dws6 factuo
    factuoedge fpitch frbody geomod hpff ic ic1 ic2 ic3 ic4 ic5 ids0mult igb0mult igc0mult jw l
    lgdrain lgsource lrsd lsdrain lssource m min minz mobscmod mult nbc nf nfin nfinnom ngaa
    ngcon ngf nqsmod nrb nrd nrs ns nseg pd pdbcp pdej pdeo pdrain ps psbcp psej pseo psource
    rbdb rbodymod rbpb rbpd rbps rbsb rgatemod rgeomod rth0 sa sb sc sca scb scc sd shmod
    soimod subbandmod temp tfin tgaa tnodeout trnqsmod tsus u0mult vbsusr vfbsdoff vldebug w
    wgaa xgw xl xw    """.split()
)


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


def _shape(line: str) -> tuple[list[str], str]:
    element = _element(line)
    assert isinstance(element, Mosfet)
    assert element.area is None
    return [node.name for node in element.nodes], element.model.model_name


# The line shape (XY-XTR-001, XY-MOS-001)


@pytest.mark.parametrize(
    ("line", "nodes", "model"),
    [
        # MVS's three nodes, the bulk, then BSIM-SOI's body contacts and temperature node.
        ("M1 d g s nm", ["d", "g", "s"], "nm"),
        ("M1 d g s b nm", ["d", "g", "s", "b"], "nm"),
        ("M1 d g s e p nm", ["d", "g", "s", "e", "p"], "nm"),
        ("M1 d g s e p b nm", ["d", "g", "s", "e", "p", "b"], "nm"),
        ("M1 d g s e p b t nm L=1u", ["d", "g", "s", "e", "p", "b", "t"], "nm"),
        ("M1 1 2 3 4 5 6 7 nm", ["1", "2", "3", "4", "5", "6", "7"], "nm"),
        # The manual's examples (§2.3.20 p292).
        ("M5 4 12 3 0 PNOM L=20u W=10u", ["4", "12", "3", "0"], "PNOM"),
        ("M3 5 13 10 0 PSTRONG", ["5", "13", "10", "0"], "PSTRONG"),
        ("M6 7 13 10 0 PSTRONG M=2", ["7", "13", "10", "0"], "PSTRONG"),
        # A number after a name is a node when a name follows it.
        ("M1 d g s b nm 2 x", ["d", "g", "s", "b", "nm", "2"], "x"),
        ("M1 d g s b 2 nm", ["d", "g", "s", "b", "2"], "nm"),
        ("M1 X1:d g s [b] nm", ["X1:d", "g", "s", "[b]"], "nm"),
        ("m1 D G S B NM", ["D", "G", "S", "B"], "NM"),
        # `offx` and `tnodeoutx` are names, not the keywords.
        ("M1 d g s b nm offx", ["d", "g", "s", "b", "nm"], "offx"),
        ("M1 d g s b nm tnodeoutx", ["d", "g", "s", "b", "nm"], "tnodeoutx"),
    ],
)
def test_the_model_is_the_last_name(line: str, nodes: list[str], model: str) -> None:
    assert _shape(line) == (nodes, model)


def test_off_tnodeout_and_thermal_right_after_the_fixed_nodes_are_nodes() -> None:
    # 5.1 point 4: right after the fixed nodes only a name may stand.
    for word in ("off", "tnodeout", "thermal", "OFF"):
        assert _shape(f"M1 d g s {word} nm") == (["d", "g", "s", word], "nm")
    mosfet = _element("M1 d g s b nm off")
    assert mosfet.flags == (Flag("off", Span(16, 19)),)
    # After a name a flag may stand, so `off` there is the flag and the name before it the model.
    assert _element("M1 d g s b off").model.model_name == "b"


@pytest.mark.parametrize(
    ("line", "column", "message"),
    [
        ("M1 d g s 2", 11, "ends too early"),
        ("M1 a b c 1 2 3 4 5", 18, "a model name cannot be a number"),
        ("M1 a b c 1 2 3 4 5k", 18, "a model name cannot be a number"),
        ("M1 d g s off", 10, "a model name cannot be the keyword `off`"),
        ("M1 d g s tnodeout", 10, "a model name cannot be the keyword `tnodeout`"),
        ("M1 d g s TNODEOUT L=1u", 10, "a model name cannot be the keyword `tnodeout`"),
        ("M1 d g s b x:m", 12, "a model name cannot hold `:`"),
    ],
)
def test_a_number_off_tnodeout_or_a_colon_in_the_models_place_is_refused(
    line: str, column: int, message: str
) -> None:
    # Decision 0031 item 2: decision 0014 item 4, with `tnodeout` on M.
    error = _error(line)
    assert error.column == column
    assert message in str(error)


@pytest.mark.parametrize(
    "line",
    ["M1 a b c d e f g h nm", "M1 a b c d e f g h i nm L=1u", "M1 d g", "M1 d g s"],
)
def test_node_counts_outside_3_to_7_are_refused(line: str) -> None:
    # Decision 0031 item 1: M takes 3 to 7 nodes, by letter.
    _error(line)


def test_continued_mosfet_lines_join() -> None:
    # The manual's example (§2.3.20 p292), and `+` lines across a comment line.
    mosfet = _element(
        "M8 10 12 100 100 NWEAK L=30u W=20u\n+ AD=288p AS=288p PD=60u PS=60u NRD=14 NRS=24"
    )
    assert [p.name for p in mosfet.params] == ["L", "W", "AD", "AS", "PD", "PS", "NRD", "NRS"]
    assert _shape("M1 d g\n* c\n+ s b nm\n+ off") == (["d", "g", "s", "b"], "nm")
    assert _element("M1 d g s b nm ; c\n+ IC=1, 2").params[0].name == "IC"


# No area (decision 0031 item 3)


@pytest.mark.parametrize(
    ("line", "column", "message"),
    [
        ("M1 d g s b nm 2", 15, "`2` after the model"),
        ("M1 d g s b nm {a}", 15, "`{a}` after the model"),
        ("M1 d g s b nm 'a'", 15, "`'a'` after the model"),
        ("M1 d g s nm 2 L=1u", 13, "`2` after the model"),
        ("M1 d g s b 1k", 12, "`1k` after the model"),
        ("M1 d g s b nm L=1u 2", 20, "`2` after a flag or parameter"),
        ("M1 d g s b nm off {2}", 19, "`{2}` after a flag or parameter"),
        ("M1 d g s b nm area=2", 15, "`area=`"),
        ("M1 d g s b nm L=1u AREA = 2", 20, "`AREA=`"),
    ],
)
def test_a_mosfet_has_no_area(line: str, column: int, message: str) -> None:
    # 5.1 point 5: Xyce stops on both forms, as the library refuses them.
    error = _error(line)
    assert error.column == column
    assert error.reason.startswith(message)
    assert "a Xyce MOSFET has no area, and Xyce stops on it" in error.reason


# Flags, IC= and parameters (XY-MOS-001)


def test_the_mosfet_forms() -> None:
    mosfet = _element("M1 d g s b nm OFF=1 M=2 IC = 0.6 , 5 TNODEOUT=1 nfin={n}")
    assert isinstance(mosfet, Mosfet)
    assert mosfet.model == ModelReference("nm", Span(13, 15))
    assert mosfet.nodes[3] == Node("b", Span(11, 12))
    assert mosfet.area is None
    assert mosfet.flags == (Flag("OFF", Span(16, 21), NumericValue("1", Span(20, 21))),)
    m, ic, tnodeout, nfin = mosfet.params
    assert m == ParamAssignment("M", NumericValue("2", Span(24, 25)), Span(22, 25), Span(22, 23))
    assert isinstance(ic.value, ValueList)
    assert [value.text for value in ic.value.values] == ["0.6", "5"]
    assert tnodeout == ParamAssignment(
        "TNODEOUT", NumericValue("1", Span(48, 49)), Span(39, 49), Span(39, 47)
    )
    assert nfin.value == Formula("n", "{", Span(55, 58))


@pytest.mark.parametrize("name", M_NAMES)
def test_each_listed_name_is_read_in_any_case(name: str) -> None:
    for spelling in (name, name.upper()):
        mosfet = _element(f"M1 a b c d mod {spelling}=1")
        assert [param.name for param in mosfet.params] == [spelling]


def test_the_grammar_and_the_message_hold_the_same_list() -> None:
    union: set[str] = set().union(*(set(names.split()) for names in TABLES.values()))
    assert tuple(sorted((union - {"off"}) | {"ic"})) == M_NAMES
    assert len(M_NAMES) == 126
    text = GRAMMAR.read_text(encoding="utf-8")
    match = re.search(r"^M_PARAM_KW\.4: /\(\?:([a-z0-9_|]+)\)", text, re.MULTILINE)
    assert match is not None
    assert tuple(sorted(set(match.group(1).split("|")) | {"ic"})) == M_NAMES
    device, tables, names = _PARAM_LISTS["m"]
    assert device == "MOSFET"
    assert set(re.findall(r"2-\d+", tables)) == set(TABLES)
    # The message writes IC1 to IC5 as a range.
    words = set(re.findall(r"[a-z_0-9]+", names)) - {"and", "or", "to"}
    assert words | {"ic2", "ic3", "ic4"} == set(M_NAMES) | {"off"}


@pytest.mark.parametrize(
    "line",
    [
        "M1 d g s b nm foo=1",
        "M1 d g s b nm vto=1",  # a model parameter
        "M1 d g s b nm dt=1",  # a Q parameter
        "M1 d g s b nm thermal=1",
        "M1 d g s b nm L=1u off level=2",
    ],
)
def test_a_name_outside_the_list_is_refused_at_the_name(line: str) -> None:
    # 5.1 point 8: Xyce stops on an unknown name.
    error = _error(line)
    name = line.split()[-1].split("=")[0]
    assert error.column == line.rindex(name) + 1
    assert "is not a parameter of a Xyce MOSFET" in error.reason
    assert "The reference guide lists abdrain, absource" in error.reason
    assert "Tables 2-92, 2-94" in error.reason


@pytest.mark.parametrize(
    ("line", "values"),
    [
        ("M1 d g s b nm IC=1", ["1"]),
        ("M1 d g s b nm IC=1,2,3,4,5", ["1", "2", "3", "4", "5"]),
        ("M1 d g s b nm ic = {a} , 'b',3", ["a", "b", "3"]),
    ],
)
def test_ic_forms(line: str, values: list[str]) -> None:
    # 5.1 point 9: blanks around `=` and `,` and expressions run; at most 5 values.
    (ic,) = _element(line).params
    assert isinstance(ic.value, ValueList)
    assert [value.text for value in ic.value.values] == values
    assert [p.name for p in _element("M1 d g s b nm IC1=1 ic5=2").params] == ["IC1", "ic5"]


@pytest.mark.parametrize(
    ("line", "column", "message"),
    [
        ("M1 d g s b nm IC=1,2,3,4,5,6", 28, "on an M takes at most five values"),
        ("M1 d g s b nm IC=1,", 20, "ends too early"),
        ("M1 d g s b nm IC=1,,2", 20, ""),
        ("M1 d g s b nm IC=,1", 18, ""),
    ],
)
def test_ic_forms_are_refused(line: str, column: int, message: str) -> None:
    # 5.1 point 9: a trailing or empty element stops Xyce.
    error = _error(line)
    assert error.column == column
    assert message in str(error)


@pytest.mark.parametrize(
    ("line", "column"),
    [
        # The manual's own form (§2.3.20 p292), after the model, a parameter or on a `+` line.
        ("M1 d g s e nm TNODEOUT", 15),
        ("M1 d g s e p b t nm tnodeout", 21),
        ("M1 d g s e nm L=1u tnodeout W=1u", 20),
        ("M1 d g s e nm\n+ TNODEOUT", 3),
        ("M1 d g s b tnodeout", 12),
    ],
)
def test_tnodeout_forms(line: str, column: int) -> None:
    # Decision 0031 item 4: `TNODEOUT=v` is a listed parameter; a bare `TNODEOUT` stops Xyce.
    error = _error(line)
    assert error.column == column
    assert "without a value: Xyce stops on it" in error.reason
    assert error.reason.endswith("write `TNODEOUT=1`")
    for written in ("TNODEOUT=1", "tnodeout = 0", "TNodeOut={t}"):
        mosfet = _element(f"M1 d g s e p b t nm {written}")
        assert len(mosfet.nodes) == 7
        assert [param.name for param in mosfet.params] == [written.split("=")[0].strip()]


@pytest.mark.parametrize(
    ("line", "column"), [("M1 d g s nm thermal", 13), ("M1 d g s b nm L=1u THERMAL", 20)]
)
def test_thermal_is_refused(line: str, column: int) -> None:
    # Decision 0031 item 4: ngspice's VDMOS flag; a Xyce VDMOS is NMOS or PMOS at LEVEL=18.
    error = _error(line)
    assert error.column == column
    assert "is ngspice's VDMOS flag, not a flag of a Xyce MOSFET" in error.reason


@pytest.mark.parametrize(
    ("line", "second"),
    [
        ("M1 d g s b nm l=1 L=2", "L=2"),
        ("M1 d g s b nm IC=1 ic=2", "ic=2"),
        ("M1 d g s b nm TNODEOUT=1 tnodeout=0", "tnodeout=0"),
        ("M1 d g s b nm m=1\n+ M=2", "M=2"),
        ("M1 d g s b nm off off", "off"),
        ("M1 d g s b nm OFF=1 off", "off"),
        ("M1 d g s b nm off\n+ OFF=0", "OFF=0"),
    ],
)
def test_a_parameter_or_off_written_twice_is_refused(line: str, second: str) -> None:
    # 5.1 point 8: Xyce runs it with one of them (the repeat row).
    error = _error(line)
    assert "is written twice on this line" in error.reason
    last_line = line.splitlines()[-1]
    assert error.column == last_line.rindex(second) + 1


# The other dialects


@pytest.mark.parametrize("dialect", [Dialect.NGSPICE, Dialect.LTSPICE])
def test_the_other_dialects_keep_their_own_mosfet_lines(dialect: Dialect) -> None:
    def read(line: str) -> Any:
        return parse(SourceText(f"t\n{line}\n.end\n"), dialect).items[1]

    # A number after the model is refused as the model; ngspice reads `tnodeout` as the model.
    with pytest.raises(ParseError):
        read("M1 d g s b nm 2")
    with pytest.raises(ParseError):
        read("M1 a b c d e f nm")
    if dialect is Dialect.NGSPICE:
        assert read("M1 d g s b nm tnodeout").model.model_name == "tnodeout"
        assert read("M1 d g s b nm thermal").flags[0].name == "thermal"
        assert read("M1 d g s b nm foo=1").params[0].name == "foo"
