"""A number is never a model name, on every letter of both dialects (decision 0024; decision 0021
item 1; M20 5.1 point 6).

A field the grammar reads as a number (core.lark's FIELD_NUMBER: digits, then letters only) in
the model's place of a D, S or W line, or after the value of an ngspice R, C or L, is a
``ParseError``, as it already is on Q, M, J, Z, U, T, O, A and N. A part number such as
``1n4148`` or ``CD4093`` stays a model, and a subcircuit name is not checked.
"""

from __future__ import annotations

import pytest

from netlistmod import (
    Capacitor,
    Component,
    Dialect,
    Diode,
    Inductor,
    ParseError,
    Resistor,
    SourceText,
    SubcktInstance,
    Switch,
    parse,
)

_BOTH = [Dialect.NGSPICE, Dialect.LTSPICE]
_NUMBERS = ["2", "4093", "1k", "4093B", "1e3", "+2", ".5", "2.5", "1kohm", "2meg", "1N"]
_PARTS = ["1n4148", "2N2222", "1N4148_OJ", "2SK170", "CD4093", "74HC00", "4N25"]


def _parse(line: str, dialect: Dialect) -> Component:
    items = parse(SourceText(f"t\n{line}\n.end\n"), dialect).items
    item = items[1]
    assert isinstance(item, Component)
    return item


def _reject(line: str, dialect: Dialect) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"t\n{line}\n.end\n"), dialect)
    return captured.value


def _check(error: ParseError, line: str, name: str, place: str) -> None:
    assert (error.line, error.column) == (2, line.rindex(f" {name}") + 2)
    assert error.reason == (
        f"`{name}` is in the model's place ({place}), and a model name cannot be a number"
    )


@pytest.mark.parametrize("dialect", _BOTH, ids=lambda dialect: dialect.value)
@pytest.mark.parametrize("name", _NUMBERS)
@pytest.mark.parametrize(
    ("template", "place"),
    [
        ("D1 a 0 {name}", "the name after the two nodes"),
        ("D1 a 0 {name} off", "the name after the two nodes"),
        ("S1 a b c d {name}", "the name after the four nodes"),
        ("S1 a b c d {name} on", "the name after the four nodes"),
        ("W1 a b v1 {name}", "the name after the controlling source"),
    ],
)
def test_a_number_is_not_a_model_name_on_d_s_and_w(
    dialect: Dialect, name: str, template: str, place: str
) -> None:
    line = template.format(name=name)
    _check(_reject(line, dialect), line, name, place)


@pytest.mark.parametrize("name", _NUMBERS)
@pytest.mark.parametrize("template", ["R1 a 0 1k {name}", "C1 a 0 1p {name}", "L1 a 0 1u {name}"])
def test_a_number_after_an_ngspice_value_is_not_a_model_name(name: str, template: str) -> None:
    # ngspice reads `R1 a 0 1k 4093` as a 4093 ohm resistor; the library refuses it rather than
    # reading a model 4093.
    line = template.format(name=name)
    _check(_reject(line, Dialect.NGSPICE), line, name, "the name after the value")


@pytest.mark.parametrize("line", ["R1 a 0 1k 2", "C1 a 0 1p 2p", "L1 a 0 1u 2"])
def test_a_number_after_an_ltspice_value_stays_a_grammar_error(line: str) -> None:
    # LTspice R, C and L take no model, so the grammar refuses any field there (LT-RES-001).
    error = _reject(line, Dialect.LTSPICE)
    assert "model's place" not in error.reason


@pytest.mark.parametrize("dialect", _BOTH, ids=lambda dialect: dialect.value)
@pytest.mark.parametrize("name", _PARTS)
@pytest.mark.parametrize(
    ("template", "kind"),
    [
        ("D1 a 0 {name}", Diode),
        ("D1 a 0 {name} off", Diode),
        ("S1 a b c d {name}", Switch),
        ("W1 a b v1 {name}", Switch),
    ],
)
def test_a_part_number_is_a_model_name(
    dialect: Dialect, name: str, template: str, kind: type
) -> None:
    element = _parse(template.format(name=name), dialect)
    assert isinstance(element, kind)
    assert getattr(element, "model").model_name == name


@pytest.mark.parametrize("name", _PARTS)
@pytest.mark.parametrize(
    ("template", "kind"),
    [
        ("R1 a 0 1k {name}", Resistor),
        ("C1 a 0 1p {name}", Capacitor),
        ("L1 a 0 1u {name}", Inductor),
    ],
)
def test_a_part_number_after_an_ngspice_value_is_a_model_name(
    name: str, template: str, kind: type
) -> None:
    element = _parse(template.format(name=name), Dialect.NGSPICE)
    assert isinstance(element, kind)
    assert getattr(element, "model").model_name == name


@pytest.mark.parametrize("dialect", _BOTH, ids=lambda dialect: dialect.value)
@pytest.mark.parametrize("name", ["2", "4093", "1k", "4093B"])
def test_a_subcircuit_name_may_be_a_number(dialect: Dialect, name: str) -> None:
    element = _parse(f"X1 a 0 {name}", dialect)
    assert isinstance(element, SubcktInstance)
    assert element.subckt.name == name
