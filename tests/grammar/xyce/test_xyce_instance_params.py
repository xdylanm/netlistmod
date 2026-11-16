"""xyce's closed instance-parameter lists of R, C, L and D (X-M1 B7; xm1-tasks 5.1 point 29).

Each letter takes the names of its instance-parameter tables in the reference guide, for every
level of the device, in any case; any other `name=` is a ParseError at the name, since Xyce stops
on it ("Unrecognized parameter"). X's parameters are the subcircuit's and stay open; K, V and I
take none.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from netlistmod import ParseError, SourceText, parse
from netlistmod.dialects import _XYCE, Dialect
from netlistmod.model._rules_xyce import _PARAM_LISTS

GRAMMAR = Path(__file__).parents[3] / "src" / "netlistmod" / "grammar" / "xyce.lark"

# The tables of [xyce-ref]: R Tables 2-42 and 2-44 (§2.3.7 p203–205), C Table 2-37 (§2.3.4
# p187), L Table 2-39 (§2.3.5 p193), D Tables 2-46, 2-48 and 2-51 (§2.3.8 p208–213). `TC=` is the
# vector form of TC1 and TC2 on R, C and L (p187, p193, p203); D's `OFF` is a flag.
LISTS: dict[str, tuple[str, ...]] = {
    "R": (
        "a",
        "density",
        "dtemp",
        "heatcapacity",
        "l",
        "m",
        "outputintvars",
        "r",
        "resistivity",
        "tc1",
        "tc2",
        "tce",
        "temp",
        "thermal_a",
        "thermal_heatcapacity",
        "thermal_l",
        "w",
    ),
    "C": ("age", "c", "d", "dtemp", "ic", "l", "m", "q", "tc1", "tc2", "temp", "w"),
    "L": ("dtemp", "ic", "l", "m", "tc1", "tc2", "temp"),
    "D": ("ab", "area", "dtemp", "ic", "lg", "ls", "m", "mult", "perim", "pj", "temp"),
}
# A line of each letter that is complete without the parameter under test, and stays valid with
# it: R and C take a value, so that `R=` or `C=` would be the value twice; those are written alone.
_LINES = {"R": "R1 a b rmod 1k", "C": "C1 a b cmod 1p", "L": "L1 a b 1u", "D": "D1 a b dm"}
_VALUE_NAMES = {("R", "r"), ("C", "c"), ("C", "q"), ("L", "l")}


def _parse(text: str) -> Any:
    return parse(SourceText(text), _XYCE)


def _items(line: str) -> Any:
    return _parse(f"t\n{line}\n.END\n").items


def _error(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        _items(line)
    return captured.value


def _listed() -> list[tuple[str, str]]:
    return [(letter, name) for letter, names in LISTS.items() for name in names]


def _line(letter: str, name: str) -> str:
    if (letter, name.lower()) in _VALUE_NAMES:
        return f"{letter}1 a b {name}={{1+0}}" if name.lower() == "q" else f"{letter}1 a b {name}=1"
    return f"{_LINES[letter]} {name}=1"


@pytest.mark.parametrize(("letter", "name"), _listed())
def test_each_listed_name_is_read_in_any_case(letter: str, name: str) -> None:
    for spelling in (name, name.upper()):
        element = _items(_line(letter, spelling))[1]
        names = [param.name for param in element.params]
        if element.__class__.__name__ != "Diode" and (letter, name) in _VALUE_NAMES:
            assert names == []  # the value keyword, or C's charge, is not a parameter
        else:
            assert names == [spelling]


@pytest.mark.parametrize("letter", sorted(LISTS))
def test_the_grammar_and_the_message_hold_the_same_list(letter: str) -> None:
    text = GRAMMAR.read_text(encoding="utf-8")
    match = re.search(rf"^{letter}_PARAM_KW\.4: /\(\?:([a-z0-9_|]+)\)", text, re.MULTILINE)
    assert match is not None
    assert tuple(match.group(1).split("|")) == LISTS[letter]
    message = _PARAM_LISTS[letter.lower()][2]
    words = set(re.findall(r"[a-z_0-9]+", message)) - {"and", "or", "tc"}
    expected = set(LISTS[letter]) | ({"off"} if letter == "D" else set())
    assert words == expected


@pytest.mark.parametrize(
    ("line", "device"),
    [
        ("R1 a b 1k foo=1", "resistor"),
        ("R1 a b 1k RSH=1", "resistor"),  # a model parameter, not an instance one
        ("R1 a b 1k M=1 tnom=27", "resistor"),
        ("C1 a b 1p tce=1", "capacitor"),
        ("C1 a b 1p cj=1", "capacitor"),
        ("L1 a b 1u w=1", "inductor"),
        ("L1 a b 1u AGE=1", "inductor"),
        ("D1 a b dm foo=1", "diode"),
        ("D1 a b dm 2 OFF n=1", "diode"),
    ],
)
def test_a_name_outside_the_list_is_refused_at_the_name(line: str, device: str) -> None:
    # Xyce stops on each ("Unrecognized parameter"; probe test_an_unlisted_name_stops_xyce).
    error = _error(line)
    name = line.split()[-1].split("=")[0]
    assert error.column == line.rindex(name) + 1
    assert f"is not a parameter of a Xyce {device}" in error.reason
    assert "The reference guide lists" in error.reason


def test_a_refused_name_on_a_continuation_line_is_found_there() -> None:
    with pytest.raises(ParseError) as captured:
        _parse("t\nR1 a b 1k\n* a comment\n+ m=2 bogus=1 temp=27\n.END\n")
    assert (captured.value.line, captured.value.column) == (4, 7)


def test_the_long_value_keywords_keep_their_hint() -> None:
    assert "write the value positionally or as `R=`" in _error("R1 a b resistance=1k").reason


@pytest.mark.parametrize("line", ["K1 L1 L2 0.5 m=1", "V1 a b 1 m=1", "I1 a b DC 1 AC 1 foo=2"])
def test_k_v_and_i_take_no_parameter(line: str) -> None:
    # The manual lists no instance parameter for them (§2.3.6 p194, §2.3.9 p221, §2.3.10 p226).
    # The parser stops at the name, or at its `=` where the name could be K's model.
    assert _error(line).column in (line.rindex(" ") + 2, line.rindex("=") + 1)


def test_a_subcircuit_call_takes_any_parameter_name() -> None:
    # X's parameters are the subcircuit's own `PARAMS:` names, so no list closes them.
    (instance,) = _items("X1 a b sub PARAMS: anything=1 m=2")[1:2]
    assert [param.name for param in instance.params] == ["anything", "m"]


@pytest.mark.parametrize("dialect", [Dialect.NGSPICE, Dialect.LTSPICE])
def test_the_other_dialects_keep_their_own_lists(dialect: Dialect) -> None:
    # LTspice keeps its own closed lists, ngspice its open names (unchanged by point 29).
    text = "t\nR1 a b 1k tce=1\n.end\n"
    if dialect is Dialect.LTSPICE:
        with pytest.raises(ParseError):
            parse(SourceText(text), dialect)
    else:
        assert parse(SourceText(text), dialect).items[1].params[0].name == "tce"
