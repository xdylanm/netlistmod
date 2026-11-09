"""ngspice behavioural forms: B, the expression forms of E and G, and C's charge (M15, 0016)."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    BehavioralSource,
    Capacitor,
    Dialect,
    ParseError,
    SourceText,
    Span,
    Vccs,
    Vcvs,
    parse,
)


def _element(line: str) -> Any:
    text = f"title\n{line}\n.end\n"
    result = parse(SourceText(text), Dialect.NGSPICE)
    assert len(result.items) == 3, result.items
    item = result.items[1]
    assert item.span == Span(6, 6 + len(line) + 1)
    return item


def _slice(line: str, span: Span) -> str:
    return f"title\n{line}"[span.start : span.end]


def _reject(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"title\n{line}\n.end\n"), Dialect.NGSPICE)
    return captured.value


@pytest.mark.parametrize(
    ("line", "quantity", "text", "delimiter", "params"),
    [
        ("B1 0 1 I=cos(v(1))+sin(v(2))", "i", "cos(v(1))+sin(v(2))", "", []),
        (
            "B2 0 1 V=ln(cos(log(v(1,2)^2)))-v(3)^4+v(2)^v(1)",
            "v",
            "ln(cos(log(v(1,2)^2)))-v(3)^4+v(2)^v(1)",
            "",
            [],
        ),
        ("B3 3 4 I=17", "i", "17", "", []),
        ("B1 out 0 V = 2 * v(vx)", "v", "2 * v(vx)", "", []),
        ("B1 out 0 v={2*v(vx)}", "v", "2*v(vx)", "{", []),
        ("B1 out 0 v='2*v(vx)'", "v", "2*v(vx)", "'", []),
        ("B1 out 0 V={k}*v(vx)", "v", "{k}*v(vx)", "", []),
        ("B1 out 0 V = 2 * v(vx) tc1=0 tc2=1m", "v", "2 * v(vx)", "", ["tc1", "tc2"]),
        ("B1 out 0 v={2} temp=30 dtemp=1", "v", "2", "{", ["temp", "dtemp"]),
        ("B1 out 0 V = v(a) == 1 ? 2 : 0", "v", "v(a) == 1 ? 2 : 0", "", []),
        (
            "Blimit b 0 V = pwl(v(1), -4,0, -2,2, 2,4, 4,5, 6,5)",
            "v",
            "pwl(v(1), -4,0, -2,2, 2,4, 4,5, 6,5)",
            "",
            [],
        ),
    ],
)
def test_a_b_line_has_a_quantity_and_an_expression(
    line: str, quantity: str, text: str, delimiter: str, params: list[str]
) -> None:
    # The manual's own examples (§5.1.1, §5.1.4), and the forms of decision 0016 item 2.
    item = _element(line)
    assert isinstance(item, BehavioralSource)
    assert (item.quantity, item.expression.text, item.expression.delimiter) == (
        quantity,
        text,
        delimiter,
    )
    assert (
        _slice(line, item.expression.span)
        == f"{delimiter}{text}{'}' if delimiter == '{' else delimiter}"
    )
    assert [param.name for param in item.params] == params
    assert len(item.nodes) == 2


def test_a_bare_expression_runs_over_a_continuation() -> None:
    text = "t\nB5 2 0 V = V(1) < {Vlow} ? {Vlow} :\n+ V(1) > {Vhigh} ? {Vhigh} : V(1)\n.end\n"
    item = parse(SourceText(text), Dialect.NGSPICE).items[1]
    assert item.expression.text == "V(1) < {Vlow} ? {Vlow} :\n+ V(1) > {Vhigh} ? {Vhigh} : V(1)"
    assert text[item.expression.span.start : item.expression.span.end] == item.expression.text


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("B1 out 0 V=2 I=1m", 14, "`I=` is a second quantity: a B source takes one"),
        ("B1 out 0 v={2*v(vx)} i={1m}", 22, "`i=` is a second quantity"),
        ("B1 out 0 r={2k}", 10, "`r=` is an LTspice form: an ngspice B source takes `v=` or `i=`"),
        ("B1 out 0 p=1m", 10, "`p=` is an LTspice form"),
        ("B1 out 0", 9, "this line ends too early"),
    ],
)
def test_malformed_b_lines_are_refused(line: str, column: int, reason: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


@pytest.mark.parametrize(
    ("line", "kind", "form", "text", "params"),
    [
        ("E41 4 0 vol = '2*V(3)*V(3)-Offs'", Vcvs, "vol", "2*V(3)*V(3)-Offs", []),
        ("E1 out 0 vol={2*v(vx)}", Vcvs, "vol", "2*v(vx)", []),
        ("E41 4 0 value = {V(3)*V(3)-Offs}", Vcvs, "value", "V(3)*V(3)-Offs", []),
        ("E1 out 0 value {2*v(vx)}", Vcvs, "value", "2*v(vx)", []),
        ("G51 55 225 cur = 'V(3)*V(3)-Offs' m=2", Vccs, "cur", "V(3)*V(3)-Offs", ["m"]),
        ("G51 55 225 value = 'V(3)*V(3)-Offs'", Vccs, "value", "V(3)*V(3)-Offs", []),
    ],
)
def test_the_expression_forms_of_e_and_g(
    line: str, kind: type, form: str, text: str, params: list[str]
) -> None:
    # The manual's own examples (§5.2.1, §5.2.2, §5.3.1, §5.3.2); value takes = or not.
    item = _element(line)
    assert type(item) is kind
    assert (item.form, item.expression.text, item.value) == (form, text, None)
    assert [node.name for node in item.nodes] == line.split()[1:3]
    assert [param.name for param in item.params] == params


@pytest.mark.parametrize("line", ["E1 out 0 value 0 2", "G1 0 out value 0 1m"])
def test_value_after_the_output_nodes_is_the_keyword(line: str) -> None:
    # ngspice stops: "mal formed E source instance: e1 out 0 vol= 0 2" (review R2).
    error = _reject(line)
    assert (error.line, error.column) == (2, 10)
    assert "`value` here is the keyword of the expression form, and ngspice reads it so" in (
        error.reason
    )


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("E1 value 0 vx 0 2", 4),
        ("E1 out value vx 0 2", 8),
        ("E1 out 0 vx value 2", 13),
        ("E1 out 0 vx VALUE 2", 13),
        ("G1 0 value vx 0 1m", 6),
        ("G1 0 out vx value 1m", 13),
        ("E1 value 0 vol='2*v(vx)'", 4),
    ],
)
def test_a_net_named_value_on_e_or_g_is_refused(line: str, column: int) -> None:
    # ngspice replaces `value` with `vol=` or `cur=` wherever it stands, and stops: "mal formed
    # E source instance: e1  vol= 0 vx 0 2" (review R6).
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert "ngspice reads `value` on an E or G line as the keyword of the expression form" in (
        error.reason
    )


@pytest.mark.parametrize(
    ("line", "names"),
    [
        ("F1 0 out value 2", ["0", "out"]),  # ngspice reads `value` as the controlling source
        ("H1 value 0 Vs 1k", ["value", "0"]),  # ngspice runs it (review R6)
        ("R5 out value 1k", ["out", "value"]),
        ("E1 out 0 vol 0 2", ["out", "0", "vol", "0"]),
        ("E1 out 0 values 0 2", ["out", "0", "values", "0"]),
    ],
)
def test_other_words_there_are_names(line: str, names: list[str]) -> None:
    assert [node.name for node in _element(line).nodes] == names


@pytest.mark.parametrize(
    ("line", "column"),
    [("E1 out 0 vol=2*v(vx)", 14), ("G1 0 out cur=2m*v(vx)", 14)],
)
def test_a_bare_expression_after_vol_or_cur_is_refused(line: str, column: int) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert "only in quotes or braces (ngspice manual §5.2.1)" in error.reason


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("E1 out 0 value={2*\n+ v(vx)}", 16),
        ("E1 out 0 vol='2*\n+ v(vx)'", 14),
        ("B1 out 0 V='2*\n+ v(vx)'", 12),
        ("B1 out 0 V={2*\n+ v(vx)} tc1=0", 12),
    ],
)
def test_a_delimited_expression_over_a_continuation_is_refused(line: str, column: int) -> None:
    # ngspice joins the lines and runs these (review R4); every formula closes on its line here.
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert error.reason == (
        "a braced or quoted expression must close on its line; join the lines, or write the "
        "expression bare (B only)"
    )


def test_laplace_stays_a_parse_error() -> None:
    # The manual says ngspice does not offer LAPLACE (§5.2.5), and ngspice stops.
    error = _reject("E1 out 0 LAPLACE {v(vx)} {2}")
    assert (error.line, error.column) == (2, 18)


@pytest.mark.parametrize(
    ("line", "text", "params"),
    [
        ("C1 a b q = '1u*(4*atan(V(a,b)/4)*2+V(a,b))/3'", "1u*(4*atan(V(a,b)/4)*2+V(a,b))/3", []),
        ("C1 cc 0 q={1n*v(cc)} tc1=-1e-03", "1n*v(cc)", ["tc1"]),
    ],
)
def test_the_charge_form_of_c(line: str, text: str, params: list[str]) -> None:
    item = _element(line)
    assert isinstance(item, Capacitor)
    assert (item.value, item.charge.text) == (None, text)
    assert [param.name for param in item.params] == params
