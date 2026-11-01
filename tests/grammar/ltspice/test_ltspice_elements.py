"""LTspice element lines and numbers (M8 T5; decisions 6, 7 and 13)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from netlistmod import (
    Capacitor,
    CurrentSource,
    Dialect,
    Diode,
    Flag,
    Formula,
    Identifier,
    Inductor,
    MutualCoupling,
    NumericValue,
    ParamAssignment,
    ParseError,
    Resistor,
    SourceText,
    SubcktDefinition,
    SubcktInstance,
    UnsupportedConstruct,
    ValueList,
    VoltageSource,
    parse,
)
from netlistmod.grammar.loader import device_matrix

ROOT = Path(__file__).parents[3]


def _parse(text: str) -> Any:
    return parse(SourceText(text), Dialect.LTSPICE)


def _element(line: str) -> Any:
    result = _parse(f"title\n{line}\n.end\n")
    assert len(result.items) == 3, result.items
    return result.items[1]


def _reject(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        _parse(f"title\n{line}\n.end\n")
    return captured.value


def _unsupported(line: str) -> UnsupportedConstruct:
    with pytest.raises(UnsupportedConstruct) as captured:
        _parse(f"title\n{line}\n.end\n")
    return captured.value


EMBEDDED = ["2k2", "2K2", "1meg5", "2MEG2", "2R2", "1r5", "1M0", "1m5", "1u5", "1n5", "1p5"]
EMBEDDED += ["1f5", "1T5", "1G5", "1mil5", "1µ5", "1μ5", "1000u5", "10m5", "6K34"]


@pytest.mark.parametrize("text", EMBEDDED)
def test_embedded_decimal_is_recorded_as_rkm_without_an_option(text: str) -> None:
    value = _element(f"R1 a 0 {text}").value
    assert value == NumericValue(text, value.span, "rkm", False)
    assert value.span.length == len(text)


@pytest.mark.parametrize(
    "text",
    ["1k", "1K", "1MEG", "1Meg", "1M", "1mil", "100R", "4R", "1a", "1F", "5V", "5Volts", "4Farads"]
    + ["1kOhm", "1kΩ", "1µ", "1μ", "2e3", "1.5", "+1k", "-1", ".5k", "5.", "1e3k", "1kk", "2.5e-3"],
)
def test_standard_numbers_with_any_trailing_letters(text: str) -> None:
    value = _element(f"R1 a 0 {text}").value
    assert value == NumericValue(text, value.span, "standard", False)


@pytest.mark.parametrize(
    "text",
    ["1k5x", "1k5k", "1k5.5", "1x5", "1a5", "1l5", "1kohm5", "2.2k2", "1.5k5", "1e3k2", "1V5"],
)
def test_digits_after_other_letters_are_rejected(text: str) -> None:
    # LTspice reads some of these (discrepancies.md); none is a documented form.
    _reject(f"R1 a 0 {text}")


# One line per value slot; `{}` holds the embedded decimal (settled by probe per slot, T5).
EMBEDDED_SLOTS = [
    "R1 a 0 {}",
    "R1 a 0 1k m={}",
    "R1 a 0 1k tc={}",
    "R1 a 0 1k tc=1m,{}",
    "C1 a 0 {}",
    "C1 a 0 1u Rser={}",
    "L1 a 0 {}",
    "L1 a 0 1m Rser={}",
    "V1 a 0 {}",
    "V1 a 0 DC {}",
    "V1 a 0 1 AC {}",
    "V1 a 0 1 AC=1k5",
    "V1 a 0 1 AC 1 {}",
    "V1 a 0 1 Rser={}",
    "I1 a 0 {}",
    "I1 a 0 R={}",
    "D1 a 0 dm {}",
    "D1 a 0 dm m={}",
    "X1 a 0 s r={}",
    "K1 L1 L2 {}",
    ".subckt s a r={}\n.ends",
    ".model dm D(Is={})",
    ".model dm D Is={}",
    ".param x={}",
    ".param x {}",
    ".tran {}",
    ".tran {} 1m",
    ".ac dec 1 1 {}",
    ".ac list {}",
    ".dc V1 0 {} 1",
    ".temp {}",
    ".ic V(a)={}",
    ".nodeset V(a)={}",
    ".options reltol={}",
    ".step param x {} 3k 1k",
    ".step param x list {} 3k",
]


def _values(node: object) -> list[NumericValue]:
    if isinstance(node, NumericValue):
        return [node]
    if isinstance(node, tuple):
        return [value for element in node for value in _values(element)]
    if hasattr(node, "__dataclass_fields__"):
        names = node.__dataclass_fields__
        return [value for name in names for value in _values(getattr(node, name))]
    return []


@pytest.mark.parametrize("template", EMBEDDED_SLOTS)
def test_the_embedded_decimal_is_accepted_in_every_value_slot(template: str) -> None:
    line = template.format("1k5")
    assert any(value.text == "1k5" and value.notation == "rkm" for value in _values(_element(line)))


def test_resistor_parameters() -> None:
    element = _element("R1 a b 10k tc=0.01, 0.001 temp=30 m=2")
    assert isinstance(element, Resistor)
    assert element.value.text == "10k"
    tc, temp, m = element.params
    assert (tc.name, temp.name, m.name) == ("tc", "temp", "m")
    assert isinstance(tc.value, ValueList)
    assert [value.text for value in tc.value.values] == ["0.01", "0.001"]
    assert tc.value.span.length == len("0.01, 0.001")
    assert tc.value.text == "0.01, 0.001"
    assert tc.span.length == len("tc=0.01, 0.001")
    assert element.model is None and element.value_keyword is None


@pytest.mark.parametrize(
    "line", ["R1 a b 1k tc=1m", "R1 a b 1k tc = 1m , 1u", "R1 a b 1k TC={a},2"]
)
def test_tc_forms(line: str) -> None:
    assert isinstance(_element(line).params[0].value, ValueList)


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("R1 a b 1k tc=1m 1u", 17),
        ("R1 a b 1k foo=1", 11),
        ("R1 a b 1k r=2k", 11),
        ("R1 a b 1k rm", 11),
        ("R1 a b 1k Rsr=1", 11),
        ('R1 a b 1k type="x"', 11),
        ("R1 a b 1k noiseless=x", 21),
        ("R1 a b 1k 5k", 11),
        ("R1 a b", 7),
        ("R1 a", 5),
    ],
)
def test_malformed_resistor_lines(line: str, column: int) -> None:
    assert _reject(line).column == column


@pytest.mark.parametrize("line", ["R1 a b R47", "R1 a b x", "R1 a b x*3", "C1 a b c0", "L1 a b l0"])
def test_a_bare_name_for_a_value_says_what_is_wrong(line: str) -> None:
    error = _reject(line)
    assert "not an LTspice value" in str(error)
    assert error.column == 8


@pytest.mark.parametrize(
    "line",
    ["R1 a b R=1k", "R1 a b r=1k", "R1 a b resistance=1k", "C1 a b C=1u", "L1 a b inductance=1m"],
)
def test_keyword_values_are_not_ltspice_forms(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize("name", ["tol", "pwr", "tc1", "tc2", "temp", "m"])
def test_resistor_database_parameters(name: str) -> None:
    element = _element(f"R1 a b 1k {name}=1")
    assert element.params[0].name == name
    assert element.params[0].value.text == "1"


@pytest.mark.parametrize(
    ("line", "flags", "params"),
    [
        ("R1 a b 1k noiseless", ["noiseless"], []),
        ("R1 a b 1k NOISELESS tol=1", ["NOISELESS"], ["tol"]),
        ("R1 a b 1k tol=1 noiseless m=2", ["noiseless"], ["tol", "m"]),
        ("L1 a b 1m noiseless Rser=1", ["noiseless"], ["Rser"]),
    ],
)
def test_noiseless_flag(line: str, flags: list[str], params: list[str]) -> None:
    element = _element(line)
    assert [flag.name for flag in element.flags] == flags
    assert [param.name for param in element.params] == params


@pytest.mark.parametrize(
    ("line", "name", "value"),
    [
        ("R1 a b 1k noiseless=1", "noiseless", "1"),
        ("R1 a b 1k NOISELESS = 0 tol=1", "NOISELESS", "0"),
        ("L1 a b 1m noiseless={x}", "noiseless", "x"),
        ("C1 a b 1n noiseless=0.5", "noiseless", "0.5"),
        ("C1 a b 1n noiseless Rser=1", "noiseless", None),
        ("I1 a b 1m load=1", "load", "1"),
        ("I1 a b 1m AC 1 load=0", "load", "0"),
        ("D1 a b dm off=1", "off", "1"),
        ("D1 a b dm 2 off=0 m=2", "off", "0"),
    ],
)
def test_flags_may_take_a_value(line: str, name: str, value: str | None) -> None:
    flag = _element(line).flags[0]
    assert flag.name == name
    assert (flag.value.text if flag.value is not None else None) == value


def test_a_flag_span_runs_to_its_value() -> None:
    text = "t\nR1 a b 1k noiseless = 1 tol=1\n.end\n"
    flag = _parse(text).items[1].flags[0]
    assert text[flag.span.start : flag.span.end] == "noiseless = 1"


@pytest.mark.parametrize(
    "line", ['R1 a 0 1k noiseless="1"', "R1 a 0 1k noiseless=x", "D1 a 0 dm off=x"]
)
def test_a_flag_value_is_a_number_or_a_formula(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize(
    ("line", "kinds"),
    [
        ('R1 a 0 1k mfg="Vishay, Inc." pn=CRCW0603', [Formula, Identifier]),
        ("R1 a 0 1k PN=1N4148 tol=1", [Identifier, NumericValue]),
        ("D1 a 0 dm Rpar=1k", [NumericValue]),
        ("D1 a 0 dm 2 off RPAR={x} m=2", [Formula, NumericValue]),
    ],
)
def test_names_verified_in_review(line: str, kinds: list[type]) -> None:
    assert [type(param.value) for param in _element(line).params] == kinds


@pytest.mark.parametrize(
    ("line", "kind", "text"),
    [
        ('C1 a 0 1u mfg="TDK"', '"', "TDK"),
        ('C1 a 0 1u pn="C3216" ', '"', "C3216"),
        ('C1 a 0 1u type="Al electrolytic"', '"', "Al electrolytic"),
        ('L1 a 0 1m mfg="Bourns, Inc."', '"', "Bourns, Inc."),
        ('L1 a 0 1m pn=""', '"', ""),
        ('C1 a 0 1u mfg="a;b $ c"', '"', "a;b $ c"),
        ("C1 a 0 1u mfg=word", None, "word"),
        ("C1 a 0 1u pn=1N4148", None, "1N4148"),
        ("L1 a 0 1m MFG=a-b", None, "a-b"),
    ],
)
def test_database_text_parameters(line: str, kind: str | None, text: str) -> None:
    value = _element(line).params[0].value
    assert value.text == text
    if kind is None:
        assert isinstance(value, Identifier)
    else:
        assert isinstance(value, Formula) and value.delimiter == kind


def test_a_database_line_holds_every_kind_of_slot() -> None:
    text = 't\nC1 b 0 10µ V=6.3 Irms=1.2 Rser=0.002 Lser=0 mfg="TDK" pn="C3216" type="X5R"\n.end\n'
    element = _parse(text).items[1]
    names = [param.name for param in element.params]
    assert names == ["V", "Irms", "Rser", "Lser", "mfg", "pn", "type"]
    for param in element.params:
        assert text[param.span.start : param.span.end].startswith(param.name)
    assert isinstance(element.params[0].value, NumericValue)


@pytest.mark.parametrize(
    "line",
    ['C1 a 0 1u V="6.3"', "C1 a 0 1u mfg=two words", "C1 a 0 1u mfg='abc'", "C1 a 0 1u mfg={abc}"]
    + ['L1 a 0 1m type="x"', "L1 a 0 1m V=1", "C1 a 0 1u Ipk=1", "D1 a 0 dm ic=1"]
    + ['R1 a 0 1k type="x"', "R1 a 0 1k Irms=1", "D1 a 0 dm tol=1", "V1 a 0 1 tol=1"],
)
def test_the_lists_stay_closed(line: str) -> None:
    _reject(line)


def test_a_parameter_name_is_not_read_from_the_start_of_another() -> None:
    assert _element("C1 a 0 1u m=2").params[0].name == "m"
    assert _element("C1 a 0 1u mfg=x").params[0].name == "mfg"
    assert _element("R1 a 0 1k temp=1 tol=2").params[1].name == "tol"
    _reject("C1 a 0 1u mfgx=1")
    _reject("C1 a 0 1u temperature=1")


@pytest.mark.parametrize("name", ["ic", "Rser", "Lser", "Rpar", "Cpar", "m", "RLshunt", "temp"])
def test_capacitor_parameters(name: str) -> None:
    element = _element(f"C1 a 0 1u {name}=1")
    assert isinstance(element, Capacitor)
    assert element.params[0].name == name
    assert isinstance(element.params[0].value, NumericValue)


@pytest.mark.parametrize("name", ["ic", "Rser", "Rpar", "Cpar", "m", "temp", "tc1", "tc2"])
def test_inductor_parameters(name: str) -> None:
    element = _element(f"L1 a 0 1m {name}={{x}}")
    assert isinstance(element, Inductor)
    assert element.params[0].name == name
    assert isinstance(element.params[0].value, Formula)


@pytest.mark.parametrize("line", ["C1 a 0 1u foo=1", "C1 a 0 1u tc=1", "L1 a 0 1m Lser=1n"])
def test_other_parameters_are_rejected(line: str) -> None:
    assert _reject(line).column == 11


def test_voltage_sources() -> None:
    element = _element("V1 a 0 DC 3 AC 1 45 Rser=1 Cpar=1p")
    assert isinstance(element, VoltageSource)
    assert element.dc is not None and element.dc.text == "3" and element.dc_keyword
    assert element.ac is not None and element.ac.magnitude.text == "1"
    assert element.ac.phase is not None and element.ac.phase.text == "45"
    assert [param.name for param in element.params] == ["Rser", "Cpar"]


@pytest.mark.parametrize(
    ("line", "dc", "magnitude", "phase", "params"),
    [
        ("V1 a 0", None, None, None, []),
        ("V1 a 0 3", "3", None, None, []),
        ("V1 a 0 {x}", "x", None, None, []),
        ("V1 a 0 AC 1", None, "1", None, []),
        ("V1 a 0 3 AC=1", "3", "1", None, []),
        ("V1 a 0 3 AC=1 45", "3", "1", "45", []),
        ("V1 a 0 1 AC 1 Rser=10m", "1", "1", None, ["Rser"]),
        ("V1 a 0 3 Cpar=1p Rser=1", "3", None, None, ["Cpar", "Rser"]),
        ("V1 a 0 Rser=1", None, None, None, ["Rser"]),
    ],
)
def test_voltage_source_forms(
    line: str, dc: str | None, magnitude: str | None, phase: str | None, params: list[str]
) -> None:
    element = _element(line)
    assert (element.dc.text if element.dc else None) == dc
    assert (element.ac.magnitude.text if element.ac else None) == magnitude
    assert (element.ac.phase.text if element.ac and element.ac.phase else None) == phase
    assert [param.name for param in element.params] == params


def test_the_ac_span_runs_from_keyword_to_last_value() -> None:
    text = "title\nV1 a 0 3 AC=1 45\n.end\n"
    ac = _parse(text).items[1].ac
    assert text[ac.span.start : ac.span.end] == "AC=1 45"


@pytest.mark.parametrize(
    "line",
    ["V1 a 0 3 AC", "V1 a 0 3 foo=1", "V1 a 0 3 m=2", "V1 a 0 DC=3", "V1 a 0 AC 1 DC 3"]
    + ["V1 a 0 3 Rser=1 AC 1", "V1 a 0 3 tc=1", "V1 a,0 3", "V1 a 0 3, AC 1"],
)
def test_malformed_voltage_sources(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize(
    ("line", "dc", "flags", "params"),
    [
        ("I1 a 0 1m", "1m", [], []),
        ("I1 a 0 DC 1m", "1m", [], []),
        ("I1 a 0 1m AC 1 45", "1m", [], []),
        ("I1 a 0 1m AC=1", "1m", [], []),
        ("I1 a 0 AC 1", None, [], []),
        ("I1 a 0 1m load", "1m", ["load"], []),
        ("I1 a 0 1m AC 1 LOAD", "1m", ["LOAD"], []),
        ("I1 a 0 R=1k", None, [], ["R"]),
        ("I1 a 0 R=1k AC 1", None, [], ["R"]),
    ],
)
def test_current_sources(line: str, dc: str | None, flags: list[str], params: list[str]) -> None:
    element = _element(line)
    assert isinstance(element, CurrentSource)
    assert (element.dc.text if element.dc else None) == dc
    assert [flag.name for flag in element.flags] == flags
    assert [param.name for param in element.params] == params


@pytest.mark.parametrize(
    "line",
    ["I1 a 0", "I1 a 0 1m Rser=1", "I1 a 0 1m Cpar=1p", "I1 a 0 1m m=2"] + ["I1 a 0 1m load AC 1"],
)
def test_malformed_current_sources(line: str) -> None:
    _reject(line)


def test_diodes() -> None:
    element = _element("D1 a b dm 2 off m=2 n=2 temp=30")
    assert isinstance(element, Diode)
    assert element.model.model_name == "dm"
    assert element.area is not None and element.area.text == "2"
    assert element.flags == (Flag("off", element.flags[0].span),)
    assert [param.name for param in element.params] == ["m", "n", "temp"]
    assert _element("D1 a b dm").area is None
    assert _element("D1 a b dm {x}").area.text == "x"
    assert _element("D1 a b 1N4148").model.model_name == "1N4148"
    assert [p.name for p in _element("D1 a b dm m=2 off n=3").params] == ["m", "n"]
    written = _element("D1 a b dm off area=2")
    assert written.area is None and written.params[0].name == "area"
    assert _element("D1 a b dm 2 area=3").area.text == "2"


@pytest.mark.parametrize(
    "line", ["D1 a b", "D1 a b dm off 2", "D1 a b dm foo=1", "D1 a b dm area=2 3", "D1 a b dm ic=1"]
)
def test_malformed_diodes(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize(
    ("line", "inductors", "value"),
    [
        ("K1 L1 L2 0.5", 2, "0.5"),
        ("K1 L1 L2 L3 0.5", 3, "0.5"),
        ("K1 L1 L2 L3 L4 1.0", 4, "1.0"),
        ("k1 l1 L2 {k}", 2, "k"),
        ("K1 L1 L2 0m5", 2, "0m5"),
    ],
)
def test_couplings_take_two_or_more_inductors(line: str, inductors: int, value: str) -> None:
    element = _element(line)
    assert isinstance(element, MutualCoupling)
    assert len(element.inductors) == inductors and element.value.text == value


@pytest.mark.parametrize("line", ["K1 L1 0.5", "K1 L1,L2,.5", "K1 L1 L2", "K1 L1 R2 0.5"])
def test_malformed_couplings(line: str) -> None:
    _reject(line)


def test_subcircuit_calls() -> None:
    element = _element("X§U1 vin vout BasicR rval=1k ;§pnba r1)r2")
    assert isinstance(element, SubcktInstance)
    assert element.designator == "X§U1"
    assert [node.name for node in element.nodes] == ["vin", "vout"]
    assert element.subckt.name == "BasicR"
    assert element.params[0].name == "rval"
    assert len(element.trailing_comments) == 1


@pytest.mark.parametrize(
    ("line", "params"),
    [
        ("X1 a b s", []),
        ("X1 a b s r=1k", ["r"]),
        ("X1 a b s params: r=1k q=2", ["r", "q"]),
        ("X1 a b s PARAMS: r=1k", ["r"]),
        ("X1 a b s params:", []),
        ('X1 a b s r="text"', ["r"]),
        ("X1 a b s r=1k, q=2", ["r", "q"]),
    ],
)
def test_subcircuit_parameters(line: str, params: list[str]) -> None:
    element = _element(line)
    assert element.subckt.name == "s"
    assert [param.name for param in element.params] == params


@pytest.mark.parametrize("line", ["X1 a,b s", "X1 a b {name}", "X1 {n} b s", "X1 a b s r=2*1k"])
def test_malformed_subcircuit_calls(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize(
    ("header", "params"),
    [
        (".subckt s a b", []),
        (".subckt s a b r=1k", ["r"]),
        (".subckt s a b params: r=1k", ["r"]),
        (".SUBCKT s a b r=1k, q=2", ["r", "q"]),
    ],
)
def test_subcircuit_headers(header: str, params: list[str]) -> None:
    definition = _element(f"{header}\n.ends s")
    assert isinstance(definition, SubcktDefinition)
    assert [param.name for param in definition.params] == params


def test_a_port_cannot_be_zero() -> None:
    assert "cannot be `0`" in str(_reject(".subckt s a 0\n.ends"))


@pytest.mark.parametrize(
    "line",
    ["V1 a 0 SINE(0 1 1k)", "V1 a 0 sin(0 1 1k)", "V1 a 0 PULSE(0 1)", "V1 a 0 EXP(0 1)"]
    + ["V1 a 0 SFFM(0 1)", "V1 a 0 PWL(0 0 1 1)", "V1 a 0 wavefile=x.wav", "V1 a 0 1 SINE(0 1 1k)"]
    + ["I1 a 0 PULSE(0 1)", "I1 a 0 tbl=(0,0,1,1m)", "I1 a 0 1m step(1m,2m)"],
)
def test_source_functions_are_unsupported(line: str) -> None:
    assert "LTspice" in str(_unsupported(line))


@pytest.mark.parametrize("line", ["V1 a 0 trnoise 1", "V1 a 0 am 1"])
def test_ngspice_source_functions_are_not_ltspice_syntax(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize(
    "line", ["C1 a 0 Q=1u*x", "L1 a 0 Flux=1m*x", "L1 a 0 Hc=16 Bs=.44 Br=.1 A=1 Lm=1 Lg=1 N=1"]
)
def test_nonlinear_forms_are_unsupported(line: str) -> None:
    assert "LTspice" in str(_unsupported(line))


@pytest.mark.parametrize("letter", list("ABEFGHJMOQSTUWZ@&"))
def test_phase_2_letters_are_unsupported(letter: str) -> None:
    error = _unsupported(f"{letter}1 a b c")
    assert f"LTspice {letter} device" in str(error)
    assert (error.line, error.column) == (2, 1)


@pytest.mark.parametrize("letter", list("NPY"))
def test_letters_ltspice_does_not_have_are_syntax_errors(letter: str) -> None:
    assert (_reject(f"{letter}1 a b c").line, _reject(f"{letter}1 a b c").column) == (2, 1)


def test_the_device_matrix_matches_its_document() -> None:
    matrix = device_matrix(Dialect.LTSPICE)
    packaged = json.loads(
        (ROOT / "src/netlistmod/grammar/ltspice-devices.json").read_text(encoding="utf-8")
    )
    assert matrix == packaged
    assert {k for k, v in matrix.items() if v["status"] == "supported"} == set("RCLVIDXK")


def test_param_assignment_spans_slice_back() -> None:
    text = "t\nC1 a 0 1u Rser = 1k5\n.end\n"
    param: ParamAssignment = _parse(text).items[1].params[0]
    assert text[param.span.start : param.span.end] == "Rser = 1k5"
    assert text[param.name_span.start : param.name_span.end] == "Rser"
    assert text[param.value.span.start : param.value.span.end] == "1k5"
