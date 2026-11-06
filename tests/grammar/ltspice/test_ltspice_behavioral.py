"""LTspice behavioural forms: B, value= on E to H, C's Q=, and L's Flux= and hysteretic core."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    BehavioralSource,
    Capacitor,
    Cccs,
    Ccvs,
    Dialect,
    Inductor,
    ParseError,
    SourceText,
    Span,
    UnsupportedConstruct,
    Vccs,
    Vcvs,
    parse,
)


def _element(line: str) -> Any:
    text = f"title\n{line}\n.end\n"
    result = parse(SourceText(text), Dialect.LTSPICE)
    assert len(result.items) == 3, result.items
    item = result.items[1]
    assert item.span == Span(6, 6 + len(line) + 1)
    return item


def _reject(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"title\n{line}\n.end\n"), Dialect.LTSPICE)
    return captured.value


@pytest.mark.parametrize(
    ("line", "quantity", "text", "params"),
    [
        ("B1 out 0 V=2*V(vx)", "v", "2*V(vx)", []),
        ("B1 out 0 V = 2 * V(vx)", "v", "2 * V(vx)", []),
        ("B1 out 0 V={2*V(vx)}", "v", "2*V(vx)", []),
        ("B1 0 out I=2m*V(vx) Rpar=1Meg", "i", "2m*V(vx)", ["Rpar"]),
        ("B1 out vx R=1k Rpar=1Meg", "r", "1k", ["Rpar"]),
        ("B1 out 0 V=2*V(vx) vprx=1", "v", "2*V(vx)", ["vprx"]),
        ("B1 out 0 R=500+V(vx)*500", "r", "500+V(vx)*500", []),
        ("B1 out 0 P=4m vprx=1", "p", "4m", ["vprx"]),
        ("B1 out 0 V=2*V(vx) ic=0 tripdv=1m tripdt=1n", "v", "2*V(vx)", ["ic", "tripdv", "tripdt"]),
        ("B1 out 0 V=if(V(vx)>0.5,2,0)", "v", "if(V(vx)>0.5,2,0)", []),
        ("B1 out 0 V=2*(~0)+time", "v", "2*(~0)+time", []),
    ],
)
def test_a_b_line_has_a_quantity_and_an_expression(
    line: str, quantity: str, text: str, params: list[str]
) -> None:
    item = _element(line)
    assert isinstance(item, BehavioralSource)
    assert (item.quantity, item.expression.text) == (quantity, text)
    assert [param.name for param in item.params] == params


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("B1 out 0 V=2 I=1m", 14, "`I=` is a second quantity"),
        ("B1 out 0", 9, "this line ends too early"),
        ("B1 out 0 V = 2 * V(vx) tc1=0", 24, ""),  # not an LTspice B parameter
        ("B1 out 0 V=2*V(vx) Rpar=1Meg", 20, "`Rpar=` is a parameter of a current B source"),
        ("B1 out 0 P=4m Rpar=1Meg", 15, "not of `P=`"),
    ],
)
def test_malformed_b_lines_are_refused(line: str, column: int, reason: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


def test_laplace_on_b_is_m15b() -> None:
    with pytest.raises(UnsupportedConstruct) as captured:
        parse(SourceText("t\nB1 out 0 V=2*V(vx) laplace=1/(1+s)\n.end\n"), Dialect.LTSPICE)
    assert captured.value.column == 20
    assert captured.value.construct == "LTspice behavioral source form (laplace)"


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("E1 out 0 value={2*V(vx)}", Vcvs),
        ("E1 out 0 value=2*V(vx)", Vcvs),
        ("G1 0 out value={2m*V(vx)}", Vccs),
        ("F1 0 out value={2*I(Vs)}", Cccs),
        ("H1 out 0 value={1k*I(Vs)}", Ccvs),
    ],
)
def test_value_on_e_to_h(line: str, kind: type) -> None:
    item = _element(line)
    assert type(item) is kind
    assert (item.form, item.value, getattr(item, "control", None)) == ("value", None, None)
    assert "V(vx)" in item.expression.text or "I(Vs)" in item.expression.text


def test_ngspice_forms_are_refused_on_ltspice() -> None:
    assert _reject("E1 out 0 vol='2*V(vx)'").column == 13
    # LTspice runs ngspice's TABLE form, which its reference does not show (decision 0016 item 9).
    assert _reject("E1 out 0 TABLE {V(vx)} = (0,0) (1,2)").column == 16


@pytest.mark.parametrize(
    ("line", "text", "params"),
    [
        ("C9 out 0 Q=1u*x", "1u*x", []),
        ("C9 out 0 Q=1u*x ic=0 m=2", "1u*x", ["ic", "m"]),
        ("C9 out 0 Q={1u*x}", "1u*x", []),
    ],
)
def test_the_charge_form_of_c(line: str, text: str, params: list[str]) -> None:
    item = _element(line)
    assert isinstance(item, Capacitor)
    assert (item.value, item.charge.text) == (None, text)
    assert [param.name for param in item.params] == params


def test_the_flux_and_hysteretic_forms_of_l() -> None:
    flux = _element("L9 out n9 Flux=1m*tanh(5*x)")
    assert isinstance(flux, Inductor)
    assert (flux.value, flux.flux.text) == (None, "1m*tanh(5*x)")
    core = _element("L9 out n9 Hc=16 Bs=.44 Br=.10 A=0.0000251 Lm=0.0198 Lg=0.0006858 N=1000")
    assert (core.value, core.flux) == (None, None)
    assert [param.name for param in core.params] == ["Hc", "Bs", "Br", "A", "Lm", "Lg", "N"]
