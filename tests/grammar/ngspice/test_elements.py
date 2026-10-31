"""Element lines of the phase 1 letters (M3): accept and reject tests, spans and errors."""

from __future__ import annotations

import pytest

from netlistmod import (
    AcSpec,
    Capacitor,
    Component,
    CurrentSource,
    Dialect,
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
    UnsupportedConstruct,
    VoltageSource,
    parse,
)
from netlistmod.grammar.loader import parse_tree


def _parse(text: str, *, rkm: bool = False):
    return parse(SourceText(text), Dialect.NGSPICE, rkm=rkm)


def _element(line: str, *, rkm: bool = False) -> Component:
    text = f"title\n{line}\n.end\n"
    result = _parse(text, rkm=rkm)
    assert len(result.items) == 3
    element = result.items[1]
    assert isinstance(element, Component)
    assert element.span == Span(6, 6 + len(line) + 1)
    return element


def _reject(line: str, *, rkm: bool = False) -> ParseError:
    with pytest.raises(ParseError) as captured:
        _parse(f"title\n{line}\n.end\n", rkm=rkm)
    return captured.value


def _slice(line: str, span: Span) -> str:
    # Spans are offsets in "title\n" + line.
    return f"title\n{line}"[span.start : span.end]


def _names(element: Component) -> list[str]:
    return [node.name for node in element.nodes]


# --- R -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "nodes", "value", "model", "params"),
    [
        ("R1 1 2 100", ["1", "2"], "100", None, []),
        ("RC1 12 17 1K", ["12", "17"], "1K", None, []),
        ("R2 5 7 1K ac=2K", ["5", "7"], "1K", None, [("ac", "2K")]),
        ("RL 1 4 2K m=2", ["1", "4"], "2K", None, [("m", "2")]),
        ("R1 /vin /vout 10k", ["/vin", "/vout"], "10k", None, []),
        ("r1 a b 10kOhm", ["a", "b"], "10kOhm", None, []),
        ("RLOAD 2 10 10K", ["2", "10"], "10K", None, []),
        ("RMOD 3 7 RMODEL L=10u W=1u", ["3", "7"], None, "RMODEL", [("L", "10u"), ("W", "1u")]),
        ("R1 a b 10k rmod tc1=2m", ["a", "b"], "10k", "rmod", [("tc1", "2m")]),
        ("RE1 1 2 800 newres dtemp=5", ["1", "2"], "800", "newres", [("dtemp", "5")]),
        ("Rmd 134 57 1.5k noisy=0", ["134", "57"], "1.5k", None, [("noisy", "0")]),
        ("R1 a b 0", ["a", "b"], "0", None, []),
        ("R1 a b -1k", ["a", "b"], "-1k", None, []),
        ("R1 dc off 1", ["dc", "off"], "1", None, []),
        ("R1 n+ n- 1 tc1 = 2m", ["n+", "n-"], "1", None, [("tc1", "2m")]),
        ("R1 x1.n gnd 1 r=2", ["x1.n", "gnd"], "1", None, [("r", "2")]),
    ],
)
def test_resistor_value_model_and_parameters(
    line: str,
    nodes: list[str],
    value: str | None,
    model: str | None,
    params: list[tuple[str, str]],
) -> None:
    element = _element(line)
    assert isinstance(element, Resistor)
    assert element.designator == line.split()[0]
    assert _names(element) == nodes
    assert (element.value.text if element.value else None) == value
    assert element.value_keyword is None
    assert (element.model.model_name if element.model else None) == model
    assert [(p.name, p.value.text) for p in element.params] == params


@pytest.mark.parametrize(
    ("line", "keyword", "value", "kind"),
    [
        ("R1 a b r=1k", "r", "1k", NumericValue),
        ("R1 a b r = 1k", "r", "1k", NumericValue),
        ("R1 a b R={5k}", "R", "5k", Formula),
        ("R1 a b resistance=1k tc1=2m", "resistance", "1k", NumericValue),
        ("R1 rr 0 r = 'V(rr) < {Vt} ? {R0} : {2*R0}' tc1=2e-03", "r", None, Formula),
        ("C1 a b c=1p", "c", "1p", NumericValue),
        ("C1 cc 0 capacitance='V(cc)*2' tc1=-1e-03", "capacitance", "V(cc)*2", Formula),
        ("L1 a b l=1u", "l", "1u", NumericValue),
        ("L1 l2 lll L = 'i(Vm) < {It} ? {Ll} : {Lh}'", "L", None, Formula),
        ("L1 a b inductance={l0}", "inductance", "l0", Formula),
    ],
)
def test_keyword_value_forms_fill_the_value_slot(
    line: str, keyword: str, value: str | None, kind: type
) -> None:
    element = _element(line)
    assert isinstance(element, Resistor | Capacitor | Inductor)
    assert element.value_keyword == keyword
    assert isinstance(element.value, kind)
    if value is not None:
        assert element.value.text == value
    assert element.model is None


@pytest.mark.parametrize(
    ("line", "kind", "text"),
    [
        ("R1 a b {Rx*2}", Formula, "Rx*2"),
        ("R1 a b 'Rx*2'", Formula, "Rx*2"),
        ("C1 a b {2*cval}", Formula, "2*cval"),
        ("L1 a b 'V(a)*1u'", Formula, "V(a)*1u"),
    ],
)
def test_expression_values_are_formulas(line: str, kind: type, text: str) -> None:
    element = _element(line)
    assert isinstance(element, Resistor | Capacitor | Inductor)
    assert isinstance(element.value, kind)
    assert element.value.text == text
    assert element.value_keyword is None


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("R1 a b", 7),  # neither value nor model (§3.3.2)
        ("R1 a", 5),
        ("R1", 3),
        ("R1 a b k=", 9),  # parameters need a value or a model first
        ("R1 a b 1k)", 10),
        ("R1 a b (1k)", 8),
        ("R1 a b l=10u", 9),  # parameters need a value or a model first
        ("R1 a b r={x} rmod", 18),  # no model after a keyword value: rmod needs "="
        ("R1 a b 1k rmod rmod2", 21),
        ("R1 a,,b 1k", 6),
        ("R1 a b 1k,", 11),
        ("R1 a b, 1k ,", 13),
        ("R1 a b r", 9),  # r is the value keyword here, so it needs "="
        ("R1 a/ b 1k", 5),
        ("R1 a b 1k m==2", 13),
        ("R1 a b 1k m=", 13),
        ("R1 a b 1k m=x", 13),
        ("R1 a b 1k m='x' n", 18),
    ],
)
def test_malformed_resistor_lines_are_rejected_with_positions(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column), error
    assert error.excerpt.startswith(line)


def test_parse_errors_name_the_expected_tokens() -> None:
    error = _reject("R1 a b ")
    assert "name" in error.expected
    assert "number" in error.expected
    assert "RKM value" in error.expected


@pytest.mark.parametrize(
    "line",
    ["R1 a,b 1k", "R1 a , b 1k", "R1 a, b,1k", "R1 a\t,\tb 1k", "R1,a,b,1k", "R1 a b 1k, m=2"],
)
def test_a_single_comma_separates_fields(line: str) -> None:
    element = _element(line)
    assert _names(element) == ["a", "b"]
    assert isinstance(element, Resistor) and element.value is not None
    assert element.value.text == "1k"


# --- C and L -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "value", "model", "params"),
    [
        ("CBYP 13 0 1UF", "1UF", None, []),
        ("COSC 17 23 10U IC=3V", "10U", None, [("IC", "3V")]),
        ("C1 15 5 cstd", None, "cstd", []),
        ("CLOAD 2 10 10P", "10P", None, []),
        ("CMOD 3 7 CMODEL L=10u W=1u", None, "CMODEL", [("L", "10u"), ("W", "1u")]),
        ("C1 a b 1p cmod m=2", "1p", "cmod", [("m", "2")]),
    ],
)
def test_capacitor_forms(
    line: str, value: str | None, model: str | None, params: list[tuple[str, str]]
) -> None:
    element = _element(line)
    assert isinstance(element, Capacitor)
    assert (element.value.text if element.value else None) == value
    assert (element.model.model_name if element.model else None) == model
    assert [(p.name, p.value.text) for p in element.params] == params


@pytest.mark.parametrize(
    ("line", "value", "model", "params"),
    [
        ("LLINK 42 69 1UH", "1UH", None, []),
        ("LSHUNT 23 51 10U IC=15.7MA", "10U", None, [("IC", "15.7MA")]),
        ("L1 15 5 indmod1", None, "indmod1", []),
        ("L1 a b 1u lmod nt=10", "1u", "lmod", [("nt", "10")]),
    ],
)
def test_inductor_forms(
    line: str, value: str | None, model: str | None, params: list[tuple[str, str]]
) -> None:
    element = _element(line)
    assert isinstance(element, Inductor)
    assert (element.value.text if element.value else None) == value
    assert (element.model.model_name if element.model else None) == model
    assert [(p.name, p.value.text) for p in element.params] == params


@pytest.mark.parametrize(
    ("line", "column"),
    [("C1 a b", 7), ("L1 a b", 7), ("C1 a b 1p 2p 3p", 16), ("L1 a b {x", 8)],
)
def test_malformed_capacitor_and_inductor_lines_are_rejected(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("C1 a b q='1u*V(a,b)'", 8),
        ("C1 a b Q = '1u*(4*atan(V(a,b)/4)*2+V(a,b))/3'", 8),
        ("C1 a b\n+ q='x' ; c", 3),
    ],
)
def test_charge_form_of_a_capacitor_is_unsupported_at_q(line: str, column: int) -> None:
    with pytest.raises(UnsupportedConstruct) as captured:
        _parse(f"title\n{line}\n.end\n")
    error = captured.value
    assert error.construct == "ngspice behavioral capacitor charge form (q=)"
    assert (error.line, error.column) == (2 + line.count("\n"), column)


# --- K -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "inductors", "value"),
    [
        ("K43 LAA LBB 0.999", ["LAA", "LBB"], "0.999"),
        ("KXFRMR L1 L2 0.87", ["L1", "L2"], "0.87"),
        ("K123 L1 L2 L3 0.97", ["L1", "L2", "L3"], "0.97"),
        ("K1 l1 l2 {k}", ["l1", "l2"], "k"),
    ],
)
def test_mutual_coupling_references_inductors(line: str, inductors: list[str], value: str) -> None:
    element = _element(line)
    assert isinstance(element, MutualCoupling)
    assert element.nodes == () and element.params == ()
    assert [ref.designator for ref in element.inductors] == inductors
    assert all(_slice(line, ref.span) == ref.designator for ref in element.inductors)
    assert element.value.text == value


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("K1 L1 0.9", 7),
        ("K1 L1 R2 0.9", 7),
        ("K1 L1 L2", 9),
        ("K1 a b 0.9", 4),
        ("K1 L1 L2 0.9 0.8", 14),
        ("K1 L1 L2 k=0.9", 10),
    ],
)
def test_malformed_mutual_coupling_is_rejected(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)


# --- V and I -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "dc", "dc_keyword", "ac"),
    [
        ("VCC 10 0 DC 6", "6", True, None),
        ("VIN 13 2 0.001 AC 1", "0.001", False, ("1", None)),
        ("ISRC 23 21 AC 0.333 45.0", None, False, ("0.333", "45.0")),
        ("VMEAS 12 9", None, False, None),
        ("V1 /vin 0 DC 0 AC 1  ", "0", True, ("1", None)),
        ("V1 a 0 dc {vdd} ac 'amp' -90", "vdd", True, ("amp", "-90")),
        ("I1 a 0 1m", "1m", False, None),
    ],
)
def test_sources_have_dc_and_ac_slots(
    line: str, dc: str | None, dc_keyword: bool, ac: tuple[str, str | None] | None
) -> None:
    element = _element(line)
    assert isinstance(element, VoltageSource | CurrentSource)
    assert isinstance(element, CurrentSource) == line.startswith("I")
    assert (element.dc.text if element.dc else None) == dc
    assert element.dc_keyword is dc_keyword
    if ac is None:
        assert element.ac is None
    else:
        assert element.ac is not None
        assert element.ac.magnitude.text == ac[0]
        assert (element.ac.phase.text if element.ac.phase else None) == ac[1]
        assert _slice(line, element.ac.span).upper().startswith("AC")
    assert element.params == ()


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("V1 a 0 DC", 10),  # DC needs a value
        ("V1 a 0 AC", 10),  # AC needs a magnitude (§4.1)
        ("V1 a 0 DC 1 DC 2", 13),
        ("V1 a 0 1 2", 10),
        ("V1 a 0 AC 1 DC 2", 13),  # DC before AC, per the general form
        ("V1 a 0 AC 1 2 3", 15),
        ("V1 a 0 abc", 8),
        ("V1 a 0 DC 2k7", 13),
        ("V1 a", 5),
    ],
)
def test_malformed_sources_are_rejected(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)


@pytest.mark.parametrize(
    ("line", "keyword"),
    [
        ("VIN 3 0 PULSE(-1 1 2NS 2NS 2NS 50NS 100NS 5)", "PULSE"),
        ("VIN 13 2 0.001 AC 1 SIN(0 1 1MEG)", "SIN"),
        ("ISRC 23 21 AC 0.333 45.0 SFFM(0 1 10K 5 1K)", "SFFM"),
        ("V1 a 0 exp(0 1)", "EXP"),
        ("V1 a 0 pwl(0 0 1n 1)", "PWL"),
        ("V1 a 0 DC 1 am(1 0 1k 10)", "AM"),
        ("V1 a 0 TRNOISE(1n 1n 0 0)", "TRNOISE"),
        ("V1 a 0 TRRANDOM(1 1n)", "TRRANDOM"),
        ("V1 a 0 EXTERNAL", "EXTERNAL"),
        ("V1 a 0 PORT 1", "PORT"),
        ("VCARRIER 1 0 DISTOF1 0.1 -90.0", "DISTOF1"),
        ("VMODULATOR 2 0 DISTOF2 0.01", "DISTOF2"),
        ("IIN1 1 5 AC 1 DISTOF1 DISTOF2 0.001", "DISTOF1"),
    ],
)
def test_stimulus_functions_and_distof_are_unsupported_at_the_keyword(
    line: str, keyword: str
) -> None:
    with pytest.raises(UnsupportedConstruct) as captured:
        _parse(f"title\n{line}\n.end\n")
    error = captured.value
    assert error.construct.startswith(f"ngspice {keyword} source")
    assert (error.line, error.column) == (2, line.upper().index(keyword) + 1)


@pytest.mark.parametrize(
    "lines",
    [
        "VIN 3 0 PULSE(-1 1\n+ 2NS 2NS) ; c\n+ 5",
        "VIN 3 0 \\\\\nPULSE(-1 1 \\\\\n2NS)",
        "VIN 3 0\n+ PULSE(-1 1 2NS) $ c",
    ],
)
def test_continued_stimulus_is_unsupported_at_the_keyword(lines: str) -> None:
    text = f"title\n{lines}\n.end\n"
    with pytest.raises(UnsupportedConstruct) as captured:
        _parse(text)
    offset = text.index("PULSE")
    assert (captured.value.line, captured.value.column) == SourceText(text).position(offset)


def test_unsupported_source_does_not_swallow_the_next_statement() -> None:
    # The stimulus text ends at its line end: at grammar level the next line is still parsed
    # as its own statement, and a malformed next line is reported there.
    tree = parse_tree(SourceText("title\nV1 a 0 PULSE(0 1)\nR1 a b 1\n.end\n"), Dialect.NGSPICE)
    assert [child.data for child in tree.children[1:3]] == ["voltage_source", "resistor"]
    with pytest.raises(ParseError) as captured:
        parse_tree(SourceText("title\nV1 a 0 PULSE(0 1)\nR1 a\n.end\n"), Dialect.NGSPICE)
    assert (captured.value.line, captured.value.column) == (3, 5)
    # The full parse finds every syntax error before it rejects a recognised form, so the
    # malformed line 3 is reported, not the unsupported function on line 2.
    with pytest.raises(ParseError) as full:
        _parse("title\nV1 a 0 PULSE(0 1)\nR1 a\n.end\n")
    assert (full.value.line, full.value.column) == (3, 5)


# --- D -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "model", "params", "flags"),
    [
        ("DBRIDGE 2 10 DIODE1", "DIODE1", [], []),
        ("DCLMP aa cc DMOD AREA=3.0 IC=0.2", "DMOD", [("AREA", "3.0"), ("IC", "0.2")], []),
        ("D1 a k 1n4148 off", "1n4148", [], ["off"]),
        (
            "D1 a k dmod area=2 OFF ic=0.6 temp=27",
            "dmod",
            [("area", "2"), ("ic", "0.6"), ("temp", "27")],
            ["OFF"],
        ),
        ("D1 a k off", "off", [], []),
        (
            "D1 a k dmod pj=1 m=2 dtemp=1 lm=1u wm=1u lp=1u wp=1u",
            "dmod",
            [
                ("pj", "1"),
                ("m", "2"),
                ("dtemp", "1"),
                ("lm", "1u"),
                ("wm", "1u"),
                ("lp", "1u"),
                ("wp", "1u"),
            ],
            [],
        ),
    ],
)
def test_diode_model_parameters_and_off_flag(
    line: str, model: str, params: list[tuple[str, str]], flags: list[str]
) -> None:
    element = _element(line)
    assert isinstance(element, Diode)
    assert element.model.model_name == model
    assert [(p.name, p.value.text) for p in element.params] == params
    assert [flag.name for flag in element.flags] == flags
    assert all(_slice(line, flag.span) == flag.name for flag in element.flags)


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("D1 a b", 7),
        ("D1 a b dmod 3.0", 16),  # the area is a named parameter only
        ("D1 a b dmod off=1", 16),
        ("D1 a b {dmod}", 8),
    ],
)
def test_malformed_diode_lines_are_rejected(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)


# --- X -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "nodes", "subckt", "params"),
    [
        ("X1 2 4 17 3 1 MULTI", ["2", "4", "17", "3", "1"], "MULTI", []),
        (
            "X1 input output myfilter rval=1k cval=1n",
            ["input", "output"],
            "myfilter",
            [("rval", "1k"), ("cval", "1n")],
        ),
        ("X1 a sub", ["a"], "sub", []),
        (
            'X1 a b sub m=2 r={2*rp} s="file.txt"',
            ["a", "b"],
            "sub",
            [("m", "2"), ("r", "2*rp"), ("s", "file.txt")],
        ),
        ("X1 a b sub r = 1k", ["a", "b"], "sub", [("r", "1k")]),
        ("X1 off dc ac sub", ["off", "dc", "ac"], "sub", []),
    ],
)
def test_subcircuit_call_nodes_name_and_parameters(
    line: str, nodes: list[str], subckt: str, params: list[tuple[str, str]]
) -> None:
    element = _element(line)
    assert isinstance(element, SubcktInstance)
    assert _names(element) == nodes
    assert element.subckt == SubcktReference(subckt, element.subckt.span)
    assert _slice(line, element.subckt.span) == subckt
    assert [(p.name, p.value.text) for p in element.params] == params


@pytest.mark.parametrize(
    ("line", "kind", "model"),
    [
        ("R1 a b 1k 2k", Resistor, "2k"),
        ("C1 a b 1p 2p", Capacitor, "2p"),
        ("D1 a b 1n", Diode, "1n"),
    ],
)
def test_a_digit_leading_name_is_a_model_where_no_value_can_stand(
    line: str, kind: type, model: str
) -> None:
    # Decision 0004: after a value (and in the diode's model slot) only a name can follow, so
    # a digit-leading field there is a model name (ngspice accepts 1n4148 as a model name).
    element = _element(line)
    assert isinstance(element, kind)
    assert element.model == ModelReference(model, element.model.span)  # type: ignore[attr-defined]


def test_string_parameter_is_a_double_quoted_formula() -> None:
    element = _element('X1 a b sub s="text"')
    assert element.params[0].value == Formula("text", '"', Span(19, 25))


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("X1 a b sub params: r=1", 12, "params:"),
        ("X1", 3, ""),
        ("X1 sub", 7, ""),
        ("X1 a b sub r=1 c", 17, ""),
        ("X1 a b sub r=x", 14, ""),
    ],
)
def test_malformed_subcircuit_calls_are_rejected(line: str, column: int, reason: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


# --- Fields, continuation, comments and spans --------------------------------------------------


@pytest.mark.parametrize(
    "lines",
    [
        "R1 a b\n+ 1k",
        "R1 a b\r\n+ 1k",
        "R1 a\n+b\n+1k",
        "R1 a b \\\\\n1k",
        "R1 a b\\\\\n  1k",
        "R1 a b \\\\\r\n1k",
        "R1 a b\n+ \\\\\n1k",
        "R1 a b\n+\n+ 1k",
        "R1 a ; first\n+ b $ second\n+ 1k // third",
        "R1 a,\n+ b 1k",
        "R1 a b ;c\n+ ,1k",
    ],
)
def test_continued_elements_are_one_item_with_exact_spans(lines: str) -> None:
    text = f"title\n{lines}\n.end\n"
    result = _parse(text)
    assert [type(item) for item in result.items[1:]] == [Resistor, End]
    element = result.items[1]
    assert isinstance(element, Resistor)
    assert element.span == Span(6, len(text) - len(".end\n"))
    assert [text[n.span.start : n.span.end] for n in element.nodes] == ["a", "b"]
    assert element.value is not None
    assert text[element.value.span.start : element.value.span.end] == "1k"


@pytest.mark.parametrize(
    ("lines", "line", "column"),
    [
        ("R1 a b\n\n+ 1k", 2, 7),
        ("R1 a b\n* c\n+ 1k", 2, 7),
        ("R1 a b \\\\\n\n", 2, 8),
        ("R1 a b \\\\\n* c\n", 2, 8),
        ("R1 a b ; c \\\\\n1k", 2, 14),
        ("R1 a b \\\\  \n1k", 2, 8),
    ],
)
def test_continuations_that_do_not_continue_are_rejected(
    lines: str, line: int, column: int
) -> None:
    with pytest.raises(ParseError) as captured:
        _parse(f"title\n{lines}\n.end\n")
    assert (captured.value.line, captured.value.column) == (line, column)


@pytest.mark.parametrize(
    ("line", "comments"),
    [
        ("R1 a b 1k ; one", ["; one"]),
        ("R1 a b 1k;one", [";one"]),
        ("R1 a b 1k $ one", ["$ one"]),
        ("R1 a b 1k // one", ["// one"]),
        ("R1 a b 1k//one", ["//one"]),
        ("R1 a b ; one\n+ 1k $ two", ["; one", "$ two"]),
        (
            "X1 a ; one\n+ b ; two\n+ sub ; three\n+ r=1 ; four",
            ["; one", "; two", "; three", "; four"],
        ),
    ],
)
def test_trailing_comments_are_recorded_in_source_order(line: str, comments: list[str]) -> None:
    text = f"title\n{line}\n.end\n"
    element = _parse(text).items[1]
    assert isinstance(element, Component)
    assert [text[s.start : s.end] for s in element.trailing_comments] == comments


def test_every_sub_span_slices_back_to_its_text() -> None:
    line = "R1 n1 n2 10k rmod tc1=2m  m = {mult} ; note"
    element = _element(line)
    assert isinstance(element, Resistor)
    assert _slice(line, element.designator_span) == "R1"
    assert [_slice(line, n.span) for n in element.nodes] == ["n1", "n2"]
    assert element.value is not None and element.model is not None
    assert _slice(line, element.value.span) == "10k"
    assert _slice(line, element.model.span) == "rmod"
    assert [_slice(line, p.name_span) for p in element.params] == ["tc1", "m"]
    assert [_slice(line, p.value.span) for p in element.params] == ["2m", "{mult}"]
    assert [_slice(line, p.span) for p in element.params] == ["tc1=2m", "m = {mult}"]
    assert [_slice(line, s) for s in element.trailing_comments] == ["; note"]


def test_element_nodes_are_typed_values() -> None:
    element = _element("D1 a k dmod off area=2")
    assert element == Diode(
        designator="D1",
        designator_span=Span(6, 8),
        nodes=(Node("a", Span(9, 10)), Node("k", Span(11, 12))),
        params=(
            ParamAssignment("area", NumericValue("2", Span(27, 28)), Span(22, 28), Span(22, 26)),
        ),
        span=Span(6, 29),
        trailing_comments=(),
        model=ModelReference("dmod", Span(13, 17)),
        flags=(Flag("off", Span(18, 21)),),
    )
    coupling = _element("K1 L1 L2 1")
    assert isinstance(coupling, MutualCoupling)
    assert coupling.inductors[0] == ElementReference("L1", Span(9, 11))
    source = _element("V1 a 0 AC 1 2")
    assert isinstance(source, VoltageSource)
    assert source.ac == AcSpec(
        NumericValue("1", Span(16, 17)), NumericValue("2", Span(18, 19)), Span(13, 19)
    )


def test_leading_whitespace_and_case_of_designators() -> None:
    text = "title\n  r1 a b 1\n\tvx a 0 dc 1\n.end\n"
    result = _parse(text)
    assert isinstance(result.items[1], Resistor)
    assert isinstance(result.items[2], VoltageSource)
    assert result.items[1].span == Span(6, 17)
    assert text[result.items[1].designator_span.start : result.items[1].designator_span.end] == (
        "r1"
    )


def test_supported_letters_after_end_are_parse_errors() -> None:
    with pytest.raises(ParseError) as captured:
        _parse("title\n.end\nR1 a b 1k\n")
    assert (captured.value.line, captured.value.column) == (3, 1)
