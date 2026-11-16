"""xyce element lines: R, C, L, K, D, V and I (DC and AC parts) and X (X-M1 B5; decision 0027
items 5 and 6; xm1-tasks 5.1 points 9 to 15, point 10 as amended by the maintainer)."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    AcSpec,
    Capacitor,
    CurrentSource,
    Diode,
    ElementReference,
    End,
    Flag,
    Formula,
    Inductor,
    ModelReference,
    MutualCoupling,
    Node,
    NumericValue,
    ParamAssignment,
    ParseError,
    Resistor,
    SourceText,
    Span,
    SubcktInstance,
    SubcktReference,
    Title,
    UnsupportedConstruct,
    ValueList,
    VoltageSource,
    parse,
)
from netlistmod.dialects import _XYCE, Dialect
from netlistmod.grammar.loader import device_matrix


def _parse(text: str) -> Any:
    return parse(SourceText(text), _XYCE)


def _element(line: str, before: str = "") -> Any:
    text = f"t\n{before}{line}\n.END\n"
    items = _parse(text).items
    position = 0
    for item in items:
        assert item.span.start == position
        position = item.span.end
    assert position == len(text)
    assert isinstance(items[0], Title) and isinstance(items[-1], End)
    return items[-2]


def _error(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        _parse(f"t\n{line}\n.END\n")
    return captured.value


# Names and nodes


def test_a_node_field_takes_a_path_into_an_instance() -> None:
    # Decision X-D2: `X1:m` is a node of its own; B6 reports it.
    resistor = _element("R1 X1:m X1:X2:n 1k")
    assert resistor.nodes == (Node("X1:m", Span(5, 9)), Node("X1:X2:n", Span(10, 17)))


@pytest.mark.parametrize("line", ["R1:a a b 1k", "X1:y a b s", "R1 a b r:mod 1k", "D1 a b d:m"])
def test_designators_and_model_names_take_no_colon(line: str) -> None:
    _error(line)


def test_designators_take_the_name_class() -> None:
    assert _element("R[1]#x a b 1k").designator == "R[1]#x"


@pytest.mark.parametrize("line", ["R1 a b 1k,M=1", "V1 a b 1, AC 1", "K1 L1, L2 0.5"])
def test_fields_take_no_comma(line: str) -> None:
    assert "comma" in _error(line).reason


# R, C and L


def test_a_resistor_takes_the_model_before_the_value() -> None:
    resistor = _element("R1 a b rmod 2k TEMP=27")
    assert isinstance(resistor, Resistor)
    assert resistor.model == ModelReference("rmod", Span(9, 13))
    assert resistor.value == NumericValue("2k", Span(14, 16))
    assert resistor.value_keyword is None
    assert [p.name for p in resistor.params] == ["TEMP"]


@pytest.mark.parametrize(
    ("line", "value", "keyword", "model"),
    [
        ("R1 a b 1k", "1k", None, None),
        ("R1 a b 1kohm", "1kohm", None, None),
        ("R1 a b {r*2}", "r*2", None, None),
        ("R1 a b '1k'", "1k", None, None),
        ("R1 a b R=2k", "2k", "R", None),
        ("R1 a b r=2*q", "2*q", "r", None),
        ("R1 a b rmod R=2k", "2k", "R", "rmod"),
        ("R1 a b 1n4148 1k", "1k", None, "1n4148"),
        ("R1 a b\n+ rmod\n+ 1k", "1k", None, "rmod"),
    ],
)
def test_resistor_value_forms(
    line: str, value: str, keyword: str | None, model: str | None
) -> None:
    resistor = _element(line)
    assert resistor.value.text == value
    assert resistor.value_keyword == keyword
    assert (resistor.model.model_name if resistor.model else None) == model
    assert resistor.params == ()


def test_the_geometry_form_takes_a_model_and_both_l_and_w() -> None:
    # The maintainer's change to point 10: Xyce then takes RSH x L / W from the model.
    resistor = _element("R1 a b rmod L=30u W=1u")
    assert resistor.value is None and resistor.model is not None
    assert [p.name for p in resistor.params] == ["L", "W"]
    # An explicit value replaces the geometry (probe test_the_geometry_form_and_an_explicit_value).
    assert _element("R1 a b rmod 2k L=30u W=1u").value.text == "2k"


@pytest.mark.parametrize(
    "line", ["R1 a b", "R1 a b rmod", "R1 a b rmod L=30u", "R1 a b rmod W=1u", "R1 a b L=1u W=1u"]
)
def test_a_resistor_needs_a_value(line: str) -> None:
    # Xyce runs each with its 1 kΩ default (probe test_xyce_runs); the library refuses them.
    error = _error(line)
    assert (error.line, error.column) == (2, 1)
    assert "has no value" in error.reason


def test_a_bare_name_as_the_value_is_read_as_the_model() -> None:
    # Xyce sorts by lookup (point 9); the library reads the word after the nodes as the model.
    error = _error("R1 a b rv")
    assert "`rv` is read as the model" in error.reason
    assert "{rv}" in error.reason


@pytest.mark.parametrize("line", ["R1 a b 2k rmod", "C1 a b 1p cmod", "L1 a b 1u lmod"])
def test_the_ngspice_order_is_refused_with_a_hint(line: str) -> None:
    error = _error(line)
    assert "Xyce writes the model before the value" in error.reason
    assert error.column == line.rindex(" ") + 2


def test_a_second_value_is_named() -> None:
    assert "second value" in _error("R1 a b 2 3").reason


@pytest.mark.parametrize("line", ["R1 a b 2kfoo 1k", "K1 L1 L2 0.5 2", "D1 a b 1meg"])
def test_a_number_is_never_a_model(line: str) -> None:
    # Decision 0024 item 7: a field that reads as a number is a value, never a model.
    assert "cannot be a number" in _error(line).reason


@pytest.mark.parametrize(
    ("line", "keyword"),
    [
        ("R1 a b 1k R=2k", "R="),
        ("C1 a b 1p C=2p", "C="),
        ("L1 a b 1u L=2u", "L="),
        ("C1 a b 1p Q={1p*v(a)}", "Q="),
        ("C1 a b C=1p Q={1p*v(a)}", "Q="),
    ],
)
def test_a_value_given_twice_is_refused(line: str, keyword: str) -> None:
    # Xyce silently uses one of them (point 10; probe test_xyce_runs).
    error = _error(line)
    assert error.column == line.index(keyword) + 1


@pytest.mark.parametrize(
    "line", ["R1 a b resistance=1k", "C1 a b capacitance=1p", "L1 a b inductance=1u"]
)
def test_the_long_value_keywords_are_refused(line: str) -> None:
    # Xyce stops on them ("Unrecognized parameter"; probe test_xyce_stops_on).
    assert "not a Xyce parameter" in _error(line).reason


def test_tc_takes_one_or_two_values() -> None:
    resistor = _element("R1 a b 1k TC=1m, 2u")
    (tc,) = resistor.params
    assert isinstance(tc.value, ValueList)
    assert [v.text for v in tc.value.values] == ["1m", "2u"]
    assert _element("R1 a b 1k TC={1m}").params[0].value == Formula("1m", "{", Span(15, 19))
    _error("R1 a b 1k TC=1m,2u,3u")


def test_instance_values_may_be_bare_expressions_without_blanks() -> None:
    # Decision X-D5.
    (m,) = _element("R1 a b 1k M=q*2").params
    assert m == ParamAssignment("M", Formula("q*2", "", Span(14, 17)), Span(12, 17), Span(12, 13))
    _error("R1 a b 1k M=q *2")


def test_the_capacitor_forms() -> None:
    capacitor = _element("C1 a b cmod 1p IC=1")
    assert isinstance(capacitor, Capacitor)
    assert (capacitor.model.model_name, capacitor.value.text) == ("cmod", "1p")
    assert _element("C1 a b C=1p").value_keyword == "C"
    charge = _element("C1 a b Q={1p*V(a)}")
    assert charge.value is None and charge.charge == Formula("1p*V(a)", "{", Span(11, 20))
    assert charge.params == ()
    semiconductor = _element("C1 a b cmod L=1u W=1u")
    assert semiconductor.value is None and semiconductor.charge is None


@pytest.mark.parametrize("line", ["C1 a b", "C1 a b cmod", "C1 a b cmod W=1u"])
def test_a_capacitor_needs_a_value_a_charge_or_a_length(line: str) -> None:
    # Xyce: "Could find neither C, Q, nor L parameters in instance" (probe test_xyce_stops_on).
    assert "has no value" in _error(line).reason


def test_a_numeric_charge_is_refused() -> None:
    # Xyce runs `Q=1p`, a constant charge (discrepancies.md).
    assert "expression" in _error("C1 a b Q=1p").reason


def test_the_inductor_forms() -> None:
    inductor = _element("L1 a b lmod 1u IC=2m")
    assert isinstance(inductor, Inductor)
    assert (inductor.model.model_name, inductor.value.text) == ("lmod", "1u")
    assert _element("L1 a b L=1u").value_keyword == "L"
    for line in ("L1 a b", "L1 a b lmod"):
        assert "has no value" in _error(line).reason


# K


def test_a_coupling_takes_inductors_a_value_and_an_optional_model() -> None:
    coupling = _element("K1 L1 L2 L3 0.98 kpot")
    assert isinstance(coupling, MutualCoupling)
    assert coupling.inductors == (
        ElementReference("L1", Span(5, 7)),
        ElementReference("L2", Span(8, 10)),
        ElementReference("L3", Span(11, 13)),
    )
    assert coupling.value == NumericValue("0.98", Span(14, 18))
    assert coupling.model == ModelReference("kpot", Span(19, 23))
    assert _element("K1 L1 L2 {k}").model is None


def test_one_inductor_needs_the_model() -> None:
    # [xyce-ref] §2.3.6 p194; Xyce also runs one without (discrepancies.md).
    assert _element("K1 L1 0.5 core").inductors == (ElementReference("L1", Span(5, 7)),)
    error = _error("K1 L1 0.5")
    assert "needs a CORE model" in error.reason


@pytest.mark.parametrize("line", ["K1 L1 L2 kmod 0.5", "K1 L1 L2 0.5 2", "K1 L1 L2"])
def test_coupling_forms_xyce_stops_on(line: str) -> None:
    _error(line)


def test_the_other_dialects_have_no_coupling_model() -> None:
    for dialect in (Dialect.NGSPICE, Dialect.LTSPICE):
        (_, coupling, _) = parse(SourceText("t\nK1 L1 L2 0.5\n.end\n"), dialect).items
        assert coupling.model is None


# D


def test_the_diode_forms() -> None:
    diode = _element("D1 a b dm 2 OFF AREA=1 IC=0.2")
    assert isinstance(diode, Diode)
    assert diode.model == ModelReference("dm", Span(9, 11))
    assert diode.area == NumericValue("2", Span(12, 13))
    assert diode.flags == (Flag("OFF", Span(14, 17)),)
    assert [p.name for p in diode.params] == ["AREA", "IC"]
    valued = _element("D1 a b dm OFF=1")
    assert valued.flags == (Flag("OFF", Span(12, 17), NumericValue("1", Span(16, 17))),)
    assert _element("D1 a b dm {2}").area == Formula("2", "{", Span(12, 15))


@pytest.mark.parametrize("line", ["D1 a b", "D1 a b 2 dm", "D1 a b 2"])
def test_a_diode_needs_its_model_first(line: str) -> None:
    # Xyce drops a number before the model (point 13; discrepancies.md).
    _error(line)


# V and I


def test_the_source_dc_and_ac_parts() -> None:
    source = _element("V1 a b DC 1 AC 2 45")
    assert isinstance(source, VoltageSource)
    assert (source.dc, source.dc_keyword) == (NumericValue("1", Span(12, 13)), True)
    assert source.ac == AcSpec(
        NumericValue("2", Span(17, 18)), NumericValue("45", Span(19, 21)), Span(14, 21)
    )
    assert source.stimulus is None
    current = _element("I1 a b 1m AC 1")
    assert isinstance(current, CurrentSource)
    assert current.dc_keyword is False and current.ac is not None
    assert current.ac.phase is None


@pytest.mark.parametrize(
    "line", ["V1 a b", "V1 a b {v}", "V1 a b DC '1'", "V1 a b AC 1", "V1 a b 1V", "I1 a b\n+ 1m"]
)
def test_source_forms_are_read(line: str) -> None:
    assert isinstance(_element(line), VoltageSource | CurrentSource)


@pytest.mark.parametrize("line", ["V1 a b AC", "V1 a b 1 AC", "V1 a b DC 1 AC ; c"])
def test_a_bare_ac_is_refused_with_a_hint(line: str) -> None:
    # A strictness exception: the manual makes the magnitude optional (point 14).
    error = _error(line)
    assert "write `AC 0`" in error.reason
    assert error.column == line.index("AC") + 1


@pytest.mark.parametrize(
    "line", ["V1 a b AC 1 DC 2", "V1 a b DC=1", "V1 a b 2*1", "I1 a b 1m M=2", "V1 a b 1 2"]
)
def test_source_forms_are_refused(line: str) -> None:
    _error(line)


@pytest.mark.parametrize(
    ("line", "name"),
    [
        ("V1 a b SIN(0 1 1k)", "SIN"),
        ("V1 a b 1 AC 1 0 PULSE(0 1 0 1n 1n 1u 2u)", "PULSE"),
        ("I1 a b pwl(0 0 1 1)", "pwl"),
        ("V1 a b EXP(0 1)\n+ ; c", "EXP"),
        ("V1 a b SFFM(0 1 1k)", "SFFM"),
        ("V1 a b PAT(1 0 0 1n 1n 1n b101)", "PAT"),
        ("V1 a b SIN(0 1 1k) DC 1", "SIN"),
    ],
)
def test_a_transient_function_is_unsupported_for_now(line: str, name: str) -> None:
    with pytest.raises(UnsupportedConstruct) as captured:
        _parse(f"t\n{line}\n.END\n")
    assert captured.value.construct == (
        f"transient source function `{name}`, not yet supported on Xyce (planned for X-M3)"
    )


# X


def test_the_subcircuit_call_forms() -> None:
    call = _element("X1 a X2:b amp PARAMS: g=2 r=q*2 M=2")
    assert isinstance(call, SubcktInstance)
    assert call.nodes == (Node("a", Span(5, 6)), Node("X2:b", Span(7, 11)))
    assert call.subckt == SubcktReference("amp", Span(12, 15))
    assert [(p.name, p.value.text) for p in call.params] == [
        ("g", "2"),
        ("r", "q*2"),
        ("M", "2"),
    ]
    assert _element("X1 a amp g=2").params[0].name == "g"
    assert _element("X1 a amp").params == ()


def test_a_subcircuit_name_takes_no_colon() -> None:
    error = _error("X1 a b s:t")
    assert "cannot hold `:`" in error.reason
    assert error.column == 8


@pytest.mark.parametrize(
    "line", ["X1 a s PARAMS: r=1k, M=1", "X1 a s r=1k,M=1", "X1 s", "X1 a s r=1 2"]
)
def test_subcircuit_call_forms_are_refused(line: str) -> None:
    _error(line)


# The device table


def test_the_x_m1_letters_are_read() -> None:
    matrix = device_matrix(_XYCE)
    for letter in "RCLKVIDX":
        assert matrix[letter]["status"] == "supported"
