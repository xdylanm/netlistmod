"""The document layer on LTspice netlists (M8 T6; decision 8): names, scopes and diagnostics."""

from __future__ import annotations

import pytest

from netlistmod import DiagnosticCode, Dialect, Netlist, StepDirective
from netlistmod.document import fold, is_ground, net_name
from netlistmod.grammar.formula import parse_formula, reserved_words

pytestmark = pytest.mark.ltspice_only


def _netlist(body: str) -> Netlist:
    return Netlist.from_text(f"title\n{body}\n.end\n", dialect=Dialect.LTSPICE)


def _codes(netlist: Netlist) -> list[tuple[DiagnosticCode, str]]:
    return [(d.code, d.severity) for d in netlist.diagnostics]


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("ÄIN", "äin"),
        ("ÄN", "ÄN"),
        ("STRASSE", "straße"),
        ("Σ", "ς"),
        ("K", "k"),
    ],
)
def test_names_fold_by_unicode_case_folding_after_nfc(first: str, second: str) -> None:
    assert fold(first, Dialect.LTSPICE) == fold(second, Dialect.LTSPICE)
    assert fold(first, Dialect.NGSPICE) != fold(second, Dialect.NGSPICE)
    netlist = _netlist(f"R1 {first} 0 1\nR2 {second} 0 1")
    assert len(netlist.nets()) == 2  # the shared net and ground
    assert netlist.nets()[0].spellings == (first, second)
    assert [e.designator for e in netlist.elements_on_net(second)] == ["R1", "R2"]


def test_ground_aliases() -> None:
    assert [is_ground(name, Dialect.LTSPICE) for name in ("0", "GND", "gnd", "Gnd", "00")] == [
        True,
        True,
        True,
        True,
        False,
    ]
    assert net_name("gNd", Dialect.LTSPICE) == "0"
    netlist = _netlist("R1 a GND 1\nR2 a 0 1\nR3 a 00 1")
    assert [net.name for net in netlist.nets()] == ["a", "0", "00"]


def test_bus_names_are_nets() -> None:
    netlist = _netlist("R1 N001 d[0] 1k\nR2 N001 d[1] 2k\nR3 d[0] 0 1k\nR4 d[1] 0 1k")
    assert {"d[0]", "d[1]"} <= {net.name for net in netlist.nets()}


@pytest.mark.parametrize("name", ["$G_x", "$g_X"])
def test_dollar_g_nodes_are_global_by_name(name: str) -> None:
    netlist = _netlist(f"R1 {name} 0 1\nX1 a s\n.subckt s p\nR1 p $G_X 1\n.ends")
    net = netlist.topology.net(name)
    assert net.scope == () and net.global_
    assert netlist.topology.net("$g_x", ("s",)) == net


def test_other_dollar_names_stay_local() -> None:
    netlist = _netlist("R1 $x 0 1\nX1 a s\n.subckt s p\nR1 p $x 1\n.ends")
    assert netlist.topology.net("$x", ("s",)).scope == ("s",)


def test_global_and_local_nets() -> None:
    netlist = _netlist(
        ".global VCC\nV1 vcc 0 3\nX1 in out div\nR9 mid 0 1\n"
        ".subckt div a b\nR1 a mid 1k\nR2 mid b 1k\nR3 vcc 0 1\n.ends"
    )
    assert netlist.topology.net("VCC", ("div",)).scope == ()
    assert netlist.topology.net("mid", ("div",)).scope == ("div",)
    assert netlist.topology.net("mid").scope == ()


def test_scopes_mask_and_resolve_as_in_the_rule_table() -> None:
    netlist = _netlist(
        ".param q=1k\nX1 a 0 div\nR1 a 0 {q}\n"
        ".subckt div p r\n.param q=3k\nR1 p r {q}\nD1 p r dm\n.model dm D\n.ends\n"
    )
    formulas = [r for r in netlist.references if r.kind == "param"]
    assert [(r.scope, r.target.value.text) for r in formulas] == [((), "1k"), (("div",), "3k")]
    assert not netlist.diagnostics


def test_models_and_subcircuits_are_local_to_their_definition() -> None:
    netlist = _netlist(
        "D2 a 0 dm\nX2 a 0 inner\n.subckt s p\n.model dm D\n.subckt inner c e\n.ends\n.ends"
    )
    assert _codes(netlist) == [
        (DiagnosticCode.UNRESOLVED_MODEL, "warning"),
        (DiagnosticCode.UNRESOLVED_SUBCKT, "warning"),
    ]


def test_use_before_definition_is_not_diagnosed() -> None:
    # The reference: line order is irrelevant between the title and .end.
    netlist = _netlist("R1 a 0 {rx}\n.param rx=3k")
    assert not netlist.diagnostics
    assert netlist.references[0].target is not None


@pytest.mark.parametrize(
    ("body", "noun"),
    [
        (".param q=1k\n.param q=3k", "parameter"),
        (".model dm D\n.model dm D", "model"),
        (".subckt s p\n.ends\n.subckt s p\n.ends", "subcircuit"),
    ],
)
def test_a_repeated_definition_stops_ltspice(body: str, noun: str) -> None:
    finding = _netlist(body).diagnostics[0]
    assert (finding.code, finding.severity) == (DiagnosticCode.DUPLICATE_DEFINITION, "warning")
    assert noun in finding.message and "LTspice 26.1.1 stops" in finding.message


def test_a_repeated_designator_names_ltspice() -> None:
    finding = _netlist("R1 a 0 1\nr1 a 0 1").diagnostics[0]
    assert finding.code is DiagnosticCode.DUPLICATE_ELEMENT
    assert "LTspice 26.1.1 stops" in finding.message


def test_a_mismatched_ends_name_names_ltspice() -> None:
    finding = _netlist(".subckt s p\n.ends other").diagnostics[0]
    assert finding.code is DiagnosticCode.ENDS_NAME_MISMATCH
    assert "LTspice" in finding.message and "§" not in finding.message


def test_port_mismatch_and_undefined_subcircuit() -> None:
    netlist = _netlist("X1 a b c s\nX2 a nope\n.subckt s p q\n.ends")
    assert [d.code for d in netlist.diagnostics] == [
        DiagnosticCode.SUBCKT_PORT_MISMATCH,
        DiagnosticCode.UNRESOLVED_SUBCKT,
    ]


def test_unresolved_is_info_when_an_include_is_in_scope() -> None:
    netlist = _netlist(".lib h.inc\nD1 a 0 dm")
    assert _codes(netlist) == [(DiagnosticCode.UNRESOLVED_MODEL, "info")]


def test_the_embedded_decimal_is_not_gated_syntax() -> None:
    netlist = _netlist("R1 a 0 1M0\nC1 a 0 4F7\nR2 a 0 2k2\n.param x=1k5")
    assert not netlist.diagnostics


def test_untyped_commands_are_reported_as_preserved() -> None:
    assert _codes(_netlist(".backanno")) == [(DiagnosticCode.UNKNOWN_DIRECTIVE_PRESERVED, "info")]


def test_a_stepped_parameter_is_defined_by_its_step() -> None:
    netlist = _netlist("R1 a 0 {x}\n.step param X 1k 3k 2k")
    formula = next(r for r in netlist.references if r.kind == "param")
    assert isinstance(formula.target, StepDirective)
    assert not netlist.diagnostics


def test_a_step_refers_to_the_param_line_of_its_quantity() -> None:
    netlist = _netlist(".param x=1k\nR1 a 0 {x}\n.step param x 1k 3k 2k")
    assert len(netlist.references_to_param("x")) == 2
    assert not netlist.diagnostics


def test_a_step_refers_to_its_source_and_model() -> None:
    netlist = _netlist("V1 a 0 1\nR1 a 0 1\n.step V1 1 2 1\n.step V2 1 2 1\n.step D nope(Is) 1 2 1")
    assert [d.code for d in netlist.diagnostics] == [
        DiagnosticCode.UNRESOLVED_ELEMENT,
        DiagnosticCode.UNRESOLVED_MODEL,
    ]
    assert not _netlist("R1 a 0 1\n.step temp 1 2 1").diagnostics


def test_sweeping_a_quantity_twice_is_diagnosed() -> None:
    finding = _netlist("R1 a 0 {x}\n.step param x 1 2 1\n.step param X 3 4 1").diagnostics[0]
    assert finding.code is DiagnosticCode.DUPLICATE_DEFINITION
    assert "LTspice 26.1.1 stops" in finding.message
    assert finding.line == 4


def test_an_ako_model_refers_to_its_base() -> None:
    netlist = _netlist(".model fast D\n.model slow ako:fast D(tt=1n)\n.model bad ako:nope D")
    assert [d.code for d in netlist.diagnostics] == [DiagnosticCode.UNRESOLVED_MODEL]
    assert netlist.references[0].target is netlist.models["fast"][0]


def test_bare_expressions_refer_to_parameters_with_exact_spans() -> None:
    netlist = _netlist(".param a=1\n.param b = a + c")
    a, c = [r for r in netlist.references if r.kind == "param"]
    assert netlist.slice(a.span) == "a" and a.target is not None
    assert netlist.slice(c.span) == "c" and c.target is None
    assert netlist.diagnostics[0].code is DiagnosticCode.UNRESOLVED_PARAM


def test_formula_words_follow_the_dialect() -> None:
    assert {"pi", "boltz", "if", "select", "time"} <= reserved_words(Dialect.LTSPICE)
    assert "pi" not in reserved_words(Dialect.NGSPICE)
    tokens = parse_formula("pi*r", Dialect.LTSPICE)
    assert tokens is not None
    assert [(t.kind, t.text) for t in tokens] == [("reserved", "pi"), ("parameter", "r")]
    assert not _netlist(".param x=2*pi*100").diagnostics
    logical = parse_formula("a&b|c", Dialect.LTSPICE)
    assert logical is not None
    assert [t.text for t in logical] == ["a", "b", "c"]


def test_a_model_text_value_is_not_a_reference() -> None:
    netlist = _netlist(".param x=2\n.model DX D(mfg=x type=x)")
    assert netlist.references == () and netlist.diagnostics == ()


def test_a_model_formula_is_a_reference() -> None:
    netlist = _netlist(".param x=2\n.model DX D(Is={x*1n})")
    assert len(netlist.references_to_param("x")) == 1


def test_a_formula_in_a_flag_value_is_a_reference() -> None:
    netlist = _netlist(".param x=1\nR1 a 0 1k noiseless={x}")
    assert len(netlist.references_to_param("x")) == 1


def test_an_ic_current_is_indexed_like_a_saved_current() -> None:
    netlist = _netlist("L1 a 0 1m\nR1 a 0 1\n.ic I(l1)=1 I(L9)=1")
    known, missing = netlist.references
    assert (known.kind, known.name) == ("element", "l1") and known.target is netlist.element("L1")
    assert missing.target is None
    finding = netlist.diagnostics[0]
    assert finding.code is DiagnosticCode.UNRESOLVED_ELEMENT
    assert netlist.slice(finding.span) == "L9"


def test_saved_currents_reference_elements_unless_they_are_patterns() -> None:
    netlist = _netlist("R1 a 0 1\n.save I(R1) I(R9) I(R?) V(*) Id(x1:D1)")
    assert [d.code for d in netlist.diagnostics] == [DiagnosticCode.UNRESOLVED_ELEMENT]
