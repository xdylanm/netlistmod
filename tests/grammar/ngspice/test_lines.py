"""ngspice transmission lines T, O, U, Y and P, and the ``.model`` forms they need (M16,
decision 0019)."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    CoupledLine,
    Dialect,
    Flag,
    LosslessLine,
    LossyLine,
    ModelStatement,
    ParseError,
    RcLine,
    SourceText,
    Span,
    TransmissionLine,
    TxlLine,
    UnsupportedConstruct,
    ValueList,
    parse,
)


def _item(line: str) -> Any:
    text = f"title\n{line}\n.end\n"
    result = parse(SourceText(text), Dialect.NGSPICE)
    assert len(result.items) == 3, result.items
    item = result.items[1]
    assert item.span == Span(6, 6 + len(line) + 1)
    return item


def _reject(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"title\n{line}\n.end\n"), Dialect.NGSPICE)
    return captured.value


def _params(item: Any) -> list[tuple[str, str]]:
    return [(param.name, param.value.text) for param in item.params]


@pytest.mark.parametrize(
    ("line", "params"),
    [
        ("T1 a 0 b 0 Z0=50 TD=1n", [("Z0", "50"), ("TD", "1n")]),
        ("T1 a 0 b 0 TD=1NS ZO=50", [("TD", "1NS"), ("ZO", "50")]),
        ("T1 a 0 b 0 z0={z} td='td'", [("z0", "z"), ("td", "td")]),
        ("T1 a 0 b 0 Z0 = 50 TD = 1n", [("Z0", "50"), ("TD", "1n")]),
        ("T1 a 0 b 0 Z0=50, TD=1n", [("Z0", "50"), ("TD", "1n")]),
        ("T1 a 0 b 0 Z0=50\n+ TD=1n", [("Z0", "50"), ("TD", "1n")]),
        ("T1 a 0 b 0 Z0=50 F=100meg NL=0.1", [("Z0", "50"), ("F", "100meg"), ("NL", "0.1")]),
        ("T1 a 0 b 0 Z0=50 NL=0.1 F=100meg", [("Z0", "50"), ("NL", "0.1"), ("F", "100meg")]),
        ("T1 a 0 b 0 Z0=50 F=100meg", [("Z0", "50"), ("F", "100meg")]),
        (
            "T1 a 0 b 0 Z0=50 TD=1n IC=0, 0, 0, 0",
            [("Z0", "50"), ("TD", "1n"), ("IC", "0, 0, 0, 0")],
        ),
        ("T1 a 0 b 0 Z0=50 TD=1n IC=0,0,0,0", [("Z0", "50"), ("TD", "1n"), ("IC", "0,0,0,0")]),
    ],
)
def test_t_takes_its_closed_parameter_list(line: str, params: list[tuple[str, str]]) -> None:
    item = _item(line)
    assert type(item) is LosslessLine and isinstance(item, TransmissionLine)
    assert [node.name for node in item.nodes] == ["a", "0", "b", "0"]
    assert [node.name for node in item.port1] == ["a", "0"]
    assert [node.name for node in item.port2] == ["b", "0"]
    assert _params(item) == params


def test_ic_is_a_list_of_four_values() -> None:
    item = _item("T1 a 0 b 0 Z0=50 TD=1n IC=1, 2m, 0, 0")
    value = item.params[-1].value
    assert isinstance(value, ValueList)
    assert [v.text for v in value.values] == ["1", "2m", "0", "0"]


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("T1 a 0 b 0 z0=50", 17, "the line's length must be given"),
        ("T1 a 0 b 0 z0=50 td=1n f=100meg", 24, "as `TD=` and as `F=`"),
        ("T1 a 0 b 0 z0=50 f=100meg td=1n", 27, "as `TD=` and as `F=`"),
        ("T1 a 0 b 0 z0=50 nl=0.25", 18, "without `F=`"),
        ("T1 a 0 b 0 td=1n", 17, "`Z0=` (or `Zo=`) must be given"),
        ("T1 a 0 b 0 z0=50 zo=75 td=1n", 18, "`Z0=` and `Zo=` are one parameter"),
        ("T1 a 0 b 0 Z0=50 Z0=75 td=1n", 18, "repeats the impedance"),
        ("T1 a 0 b 0 z0=50 td=1n rel=1", 24, "does not list it for T"),
        ("T1 a 0 b 0 z0=50 td=1n abs=1", 24, "does not list it for T"),
        ("T1 a 0 b 0 z0=50 td=1n ic=0,0", 24, "holds 2 values"),
        ("T1 a 0 b 0 z0=50 td=1n ic=1", 24, "holds 1 values"),
        ("T1 a 0 b 0 z0=50 td=1n ic=0,0,0,0,0", 24, "holds 5 values"),
    ],
)
def test_refused_t_lines_name_the_rule(line: str, column: int, reason: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("T1 a 0 b 0 z0=50 td=1n foo=1", 24),
        ("T1 a 0 b 0 z0=50 td=1n m=2", 24),
        ("T1 a 0 b 0 50 1n", 12),
        ("T1 a 0 b 0 z0=50 td=1n off", 24),
        ("T1 a 0 b z0=50 td=1n", 12),
        ("T1 a 0 b 0 z0=50 td=1n ic=0 0 0 0", 29),
        ("T1 a 0 b 0 z0=z td=1n", 15),
    ],
)
def test_other_t_forms_are_syntax_errors(line: str, column: int) -> None:
    assert (_reject(line).line, _reject(line).column) == (2, column)


@pytest.mark.parametrize(
    "line", ["O1 a 0 b 0 lmod", "O1 a 0 b 0 lmod ; note", "O1 a 0\n+ b 0 lmod", "O1 a,0 b,0 lmod"]
)
def test_o_takes_four_nodes_and_a_model(line: str) -> None:
    item = _item(line)
    assert type(item) is LossyLine
    assert [node.name for node in item.nodes] == ["a", "0", "b", "0"]
    assert item.model.model_name == "lmod"
    assert item.params == ()


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("O1 a 0 b 0 lmod len=2", 17, "nothing after it"),
        ("O1 a 0 b 0 lmod m=2", 17, "nothing after it"),
        ("O1 a 0 b 0 lmod LTRA", 17, "nothing after it"),
        ("O1 a 0 b 0 5", 12, "cannot be a number"),
    ],
)
def test_refused_o_lines(line: str, column: int, reason: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


def test_o_needs_four_nodes_and_a_model() -> None:
    for line in ("O1 a 0 b lmod", "O1 a 0 b 0"):
        _reject(line)


@pytest.mark.parametrize(
    ("line", "params"),
    [
        ("U1 a b 0 umod l=5", [("l", "5")]),
        ("U1 a b 0 umod L=5 n=6", [("L", "5"), ("n", "6")]),
        ("U1 a b 0 umod n=6 l=5", [("n", "6"), ("l", "5")]),
        ("U1 a b 0 umod l={len*5}", [("l", "len*5")]),
        ("U1 a b 0 umod l = 5", [("l", "5")]),
        ("U1 a b 0 umod n=6.5 l=5", [("n", "6.5"), ("l", "5")]),
        ("U1 inv b 0 umod l=5", [("l", "5")]),
        ("U1 a b 0 umod\n+ l=5", [("l", "5")]),
    ],
)
def test_u_is_a_urc_line_with_four_names(line: str, params: list[tuple[str, str]]) -> None:
    item = _item(line)
    assert type(item) is RcLine
    assert len(item.nodes) == 3
    assert item.model.model_name == "umod"
    assert _params(item) == params


@pytest.mark.parametrize(
    "line",
    [
        "U1 inv p n a b d0 dmio",
        "U1 a b 0 c umod l=5",
        "U1 and(2) a b c d0 dm",
        "U1 a b c",
        "U1 buf vdd vss in out d0 dmio mntymxdly=1",
    ],
)
def test_any_other_u_shape_is_the_digital_u(line: str) -> None:
    with pytest.raises(UnsupportedConstruct) as captured:
        parse(SourceText(f"title\n{line}\n.end\n"), Dialect.NGSPICE)
    assert captured.value.construct == "ngspice digital U device, out of scope for v1"
    assert (captured.value.line, captured.value.column) == (2, 1)


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("U1 a b 0 umod", 14, "`l=` must be given"),
        ("U1 a b 0 umod n=6", 18, "`l=` must be given"),
        ("U1 a b 0 umod 5", 15, "positional length"),
        ("U1 a b 0 umod off", 15, "takes no flag"),
        ("U1 a b 0 umod l=5 m=2", 19, "`l=` and `n=` only"),
        ("U1 a b 0 umod l=5 x", 19, "after the parameters"),
        ("U1 a b 0 5 l=5", 10, "cannot be a number"),
    ],
)
def test_refused_u_lines(line: str, column: int, reason: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


@pytest.mark.parametrize(
    ("line", "params"),
    [
        ("Y1 a 0 b 0 ymod", []),
        ("Y1 a 0 b 0 ymod len=1", [("len", "1")]),
        ("Y1 a gnd b GND ymod LEN={2*k}", [("LEN", "2*k")]),
    ],
)
def test_y_takes_four_nodes_a_model_and_len(line: str, params: list[tuple[str, str]]) -> None:
    item = _item(line)
    assert type(item) is TxlLine
    assert item.model.model_name == "ymod"
    assert _params(item) == params
    assert len(item.port1) == len(item.port2) == 2


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("Y1 a x b 0 ymod", 6, "reference node of the Y line"),
        ("Y1 a 0 b x ymod", 10, "reference node of the Y line"),
        ("Y1 a 00 b 0 ymod", 6, "write `0`"),
        ("Y1 a 0 b 0 5", 12, "cannot be a number"),
    ],
)
def test_refused_y_lines(line: str, column: int, reason: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


@pytest.mark.parametrize(
    ("line", "column"), [("Y1 a 0 b 0 ymod m=2", 17), ("Y1 a 0 b 0 ymod 2", 17)]
)
def test_other_y_fields_are_syntax_errors(line: str, column: int) -> None:
    assert (_reject(line).line, _reject(line).column) == (2, column)


def test_a_y_reference_node_must_be_ground_inside_a_subcircuit_too() -> None:
    with pytest.raises(ParseError):
        parse(SourceText("title\n.subckt s a r\nY1 a r b 0 ymod\n.ends\n.end\n"), Dialect.NGSPICE)


@pytest.mark.parametrize(
    ("line", "conductors"),
    [
        ("P1 a 0 b 0 pmod", 1),
        ("P1 a1 a2 0 b1 b2 0 pmod len=2", 2),
        ("P1 a1 a2 gnd\n+ b1 b2 0 pmod", 2),
        (
            "P1 "
            + " ".join(f"a{i}" for i in range(8))
            + " 0 "
            + " ".join(f"b{i}" for i in range(8))
            + " 0 pmod",
            8,
        ),
    ],
)
def test_p_takes_2x_plus_2_nodes_then_its_model(line: str, conductors: int) -> None:
    item = _item(line)
    assert type(item) is CoupledLine
    assert item.conductors == conductors
    assert len(item.nodes) == 2 * conductors + 2
    assert item.port1 == item.nodes[: conductors + 1]
    assert item.port2 == item.nodes[conductors + 1 :]
    assert item.model.model_name == "pmod"


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("P1 a1 a2 0 b1 b2 pmod", 22, "has 5 nodes"),
        ("P1 a 0 pmod", 12, "has 2 nodes"),
        (
            "P1 "
            + " ".join(f"a{i}" for i in range(9))
            + " 0 "
            + " ".join(f"b{i}" for i in range(9))
            + " 0 pmod",
            None,
            "has 20 nodes",
        ),
        ("P1 a x b 0 pmod", 6, "reference node of the P line"),
        ("P1 a1 a2 0 b1 b2 x pmod", 18, "reference node of the P line"),
        ("P1 a 0 b 0 pmod 2", 17, "cannot be a number"),
    ],
)
def test_refused_p_lines(line: str, column: int | None, reason: str) -> None:
    error = _reject(line)
    if column is not None:
        assert (error.line, error.column) == (2, column)
    assert reason in error.reason


def test_p_m_is_a_syntax_error() -> None:
    error = _reject("P1 a 0 b 0 pmod m=2")
    assert error.line == 2


def _model(line: str) -> ModelStatement:
    item = _item(line)
    assert isinstance(item, ModelStatement)
    return item


@pytest.mark.parametrize(
    ("line", "flags", "params"),
    [
        (
            ".model lm ltra r=1 l=50n c=20p len=1 nosteplimit",
            ["nosteplimit"],
            ["r", "l", "c", "len"],
        ),
        (".model lm ltra(nosteplimit r=1 len=1)", ["nosteplimit"], ["r", "len"]),
        (".model lm LTRA(r=1 len=1 STEPLIMIT LININTERP)", ["STEPLIMIT", "LININTERP"], ["r", "len"]),
        (
            ".model lm ltra r=1 len=1 nocontrol mixedinterp truncnr truncdontcut",
            ["nocontrol", "mixedinterp", "truncnr", "truncdontcut"],
            ["r", "len"],
        ),
    ],
)
def test_an_ltra_model_takes_its_flags(line: str, flags: list[str], params: list[str]) -> None:
    model = _model(line)
    assert [flag.name for flag in model.flags] == flags
    assert all(isinstance(flag, Flag) for flag in model.flags)
    assert [param.name for param in model.params] == params


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        (".model dm d nosteplimit", 13, "a flag of an LTRA model"),
        (".model dm d(lininterp)", 13, "a flag of an LTRA model"),
        (".model dm d is=1e-14 1e-15", 22, "a second value for `is=`"),
        (".model pm cpl length=1 2", 24, "a second value for `length=`"),
        (".model dm d pchan 1", 19, "a value without a name"),
    ],
)
def test_ltra_flags_and_lists_stay_on_their_model_types(
    line: str, column: int, reason: str
) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


def test_two_words_of_no_control_are_not_a_flag() -> None:
    _reject(".model lm ltra r=1 no control")


@pytest.mark.parametrize(
    ("line", "matrices"),
    [
        (".model pm cpl R=1 0 1 L=1n 0 1n", {"R": "1 0 1", "L": "1n 0 1n"}),
        (".model pm CPL(R=1, 0, 1 C={c1} 2p 'c2')", {"R": "1, 0, 1", "C": "{c1} 2p 'c2'"}),
        (".model pm cpl\n+R=1 0\n+ 1 G=0", {"R": "1 0\n+ 1", "G": "0"}),
        (".model pm cpl r=10 length=1", {"r": "10", "length": "1"}),
    ],
)
def test_a_cpl_matrix_is_a_value_list(line: str, matrices: dict[str, str]) -> None:
    model = _model(line)
    assert {param.name: param.value.text for param in model.params} == matrices
    for param in model.params:
        if param.value.text.count(" ") or "," in param.value.text:
            assert isinstance(param.value, ValueList)
            assert param.span.end == param.value.span.end
