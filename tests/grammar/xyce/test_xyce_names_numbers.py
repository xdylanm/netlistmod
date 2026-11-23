"""The xyce names, `.GLOBAL`, `.PREPROCESS REPLACEGROUND` and the two number readers (X-M1 B2;
decision 0027 items 3 and 8)."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import pytest
from lark import Lark

from netlistmod import (
    End,
    GlobalDirective,
    Identifier,
    Node,
    ParseError,
    SourceText,
    Span,
    Title,
    UnknownDirective,
    parse,
)
from netlistmod.dialects import _XYCE
from netlistmod.model.nodes import PreprocessDirective


def _parse(text: str) -> Any:
    return parse(SourceText(text), _XYCE)


def _tiles(text: str) -> None:
    position = 0
    for item in _parse(text).items:
        assert item.span.start == position
        position = item.span.end
    assert position == len(text)


@lru_cache(maxsize=None)
def _terminals() -> Lark:
    # The lexer-only build keeps every terminal, also those no rule of B2 uses yet (NUMBER and
    # NODE_WORD are the element lines' of B5, EXPR_NUMBER the `.PARAM` values' of B3).
    return Lark.open_from_package("netlistmod.grammar", "xyce.lark", parser=None, lexer="basic")


def _matches(terminal: str, text: str) -> bool:
    pattern = _terminals().get_terminal(terminal).pattern
    return re.fullmatch(pattern.to_regexp(), text) is not None


# Names: printable ASCII except blanks and ( ) { } , : ; " ' = ([xyce-ref] §2.3.2 p184).
_NAMES = ["a", "N1", "0", "00", "[s]", "a[1]", "$GVDD", "gnd!", "x.y", "a-b", "a+b", "a/b", "a\\b"]
_NAMES += ["a*b", "a#b", "a@b", "a%b", "a&b", "a^b", "a~b", "a|b", "a<b>", "a?b", "a`b", "*a", "+a"]


@pytest.mark.parametrize("name", _NAMES)
def test_a_global_node_takes_the_name_class(name: str) -> None:
    text = f"t\n.GLOBAL {name}\n.END\n"
    (title, directive, end) = _parse(text).items
    assert isinstance(directive, GlobalDirective)
    assert directive.nodes == (Node(name, Span(10, 10 + len(name))),)
    assert directive.keyword == ".GLOBAL"
    _tiles(text)


@pytest.mark.parametrize(
    "name", ['a"b', "a'b", "a(b", "a)b", "a{b", "a}b", "a=b", "a:b", "äb", "µ"]
)
def test_a_name_outside_the_class_is_rejected(name: str) -> None:
    # `"` and non-ASCII are refused although Xyce takes them (discrepancies.md); `:` is only an
    # element node field's (decision X-D2).
    with pytest.raises(ParseError) as captured:
        _parse(f"t\n.global {name}\n.END\n")
    assert captured.value.line == 2


def test_the_node_field_terminal_also_takes_a_colon() -> None:
    # The element lines of B5 read their nodes with NODE_WORD (decision X-D2); `.GLOBAL` with WORD.
    for name in ("X1:m", "X1:X2:m", "a", "[s]"):
        assert _matches("NODE_WORD", name)
    for name in ("a b", "a,b", "a;b", "a=b", "äb"):
        assert not _matches("NODE_WORD", name)
    assert not _matches("WORD", "X1:m")


def test_global_takes_several_names_and_continues() -> None:
    text = "t\n.global a b ; c\n+ c\n.END\n"
    (title, directive, end) = _parse(text).items
    assert [node.name for node in directive.nodes] == ["a", "b", "c"]
    assert directive.trailing_comments == (Span(14, 17),)
    _tiles(text)


@pytest.mark.parametrize("text", [".global", ".global a,b", ".global a , b", ".global a=1"])
def test_a_global_without_names_or_with_commas_is_rejected(text: str) -> None:
    # Xyce accepts `.global a,b` (discrepancies.md); the manual's form has no comma (§2.1.11 p44).
    with pytest.raises(ParseError):
        _parse(f"t\n{text}\n.END\n")


@pytest.mark.parametrize("value", ["TRUE", "true", "False", "FALSE"])
def test_preprocess_replaceground_is_typed(value: str) -> None:
    text = f"t\n.PREPROCESS REPLACEGROUND {value} ; c\n.END\n"
    (title, directive, end) = _parse(text).items
    assert directive == PreprocessDirective(
        keyword=".PREPROCESS",
        keyword_span=Span(2, 13),
        span=Span(2, text.index(".END")),
        trailing_comments=(Span(29 + len(value), 32 + len(value)),),
        option=Identifier("REPLACEGROUND", Span(14, 27)),
        value=Identifier(value, Span(28, 28 + len(value))),
        enabled=value in ("TRUE", "true"),
    )
    _tiles(text)


def test_preprocess_replaceground_continues() -> None:
    text = "t\n.preprocess\n* c\n+ replaceground\n+ true\n.END\n"
    (title, directive, end) = _parse(text).items
    assert isinstance(directive, PreprocessDirective)
    assert directive.enabled
    _tiles(text)


@pytest.mark.parametrize(
    "line",
    [
        ".preprocess replaceground",
        ".preprocess replaceground 1",
        ".preprocess replaceground yes",
        ".preprocess replaceground true false",
        ".preprocess replaceground truex",
        ".preprocess",
    ],
)
def test_a_preprocess_replaceground_without_a_boolean_is_rejected(line: str) -> None:
    # Xyce stops on a missing value, on `1` and on `yes` (xm1-tasks 5.1 point 5).
    with pytest.raises(ParseError) as captured:
        _parse(f"t\n{line}\n.END\n")
    assert captured.value.line == 2


def test_a_second_preprocess_replaceground_is_rejected() -> None:
    # Only one is allowed in a netlist ([xyce-ref] §2.1.28 p125); Xyce stops on a second.
    text = "t\n.preprocess replaceground true\n* c\n.PREPROCESS REPLACEGROUND false\n.END\n"
    with pytest.raises(ParseError, match="a second `.PREPROCESS REPLACEGROUND`") as captured:
        _parse(text)
    assert (captured.value.line, captured.value.column) == (4, 1)


@pytest.mark.parametrize("line", [".preprocess removeunused r,c", ".Preprocess\n+ removeunused v"])
def test_removeunused_is_read_as_an_untyped_preprocess_form(line: str) -> None:
    # Read since X-M4 (decision 0031 item 10, amending decision 0028 item 1), as ADDRESISTORS is;
    # its list and refusals are XY-PRE-003's (test_xyce_closed_list.py).
    items = _parse(f"t\n{line}\n.END\n").items
    assert [type(item) for item in items] == [Title, UnknownDirective, End]
    with pytest.raises(ParseError, match="lists no device letter"):
        _parse("t\n.PREPROCESS REMOVEUNUSED\n.END\n")


def test_structure_items_tile_with_the_new_statements() -> None:
    text = "t\n.preprocess replaceground false\n.global a\n.END"
    assert [type(item) for item in _parse(text).items] == [
        Title,
        PreprocessDirective,
        GlobalDirective,
        End,
    ]
    _tiles(text)


# The device-field reader ([xyce-ug] Table 4-1 p42; observed on XyceNF 7.10.0, decision 0027
# item 8): scale factors, then one unit of the closed list.
_DEVICE_ACCEPTED = [
    "1",
    "-1.5",
    "+2",
    ".5",
    "1e3",
    "1E-3",
    "2.",
    "1k",
    "1K",
    "1meg",
    "1MEG",
    "1Meg",
]
_DEVICE_ACCEPTED += ["1x", "1X", "1mil", "1m", "1M", "1u", "1n", "1p", "1f", "1t", "1g"]
_DEVICE_ACCEPTED += ["1a", "1amp", "1c", "1pfarad", "1fa", "1henry", "1hertz", "1hy", "1hz", "1h"]
_DEVICE_ACCEPTED += ["1m", "1ohm", "1s", "1v", "1vdc", "1volt", "1kohm", "1KOhm", "1megohm"]
_DEVICE_ACCEPTED += ["1uf", "1nF", "1mh", "1mA", "1kHz", "1mamp", "1ff", "1mm", "1mega", "1milohm"]
# A letter that begins a scale factor is read as one: `1farad` is femto and `arad` (observed).
_REFUSED_BY_BOTH = ["1kk", "1z", "1µ", "1µF", "2k7", "4n7", "1R5", "1.5.3", "1fz", "1farad"]
_ARTEFACTS = ["1keg", "1kmeg", "1e", "1kmhz"]


@pytest.mark.parametrize("text", _DEVICE_ACCEPTED)
def test_the_device_field_reader_takes_scale_factors_and_units(text: str) -> None:
    assert _matches("NUMBER", text)


@pytest.mark.parametrize("text", [*_REFUSED_BY_BOTH, *_ARTEFACTS, "1j", "1kj", "1kvj", "a", "1 k"])
def test_the_device_field_reader_refuses_other_letters(text: str) -> None:
    # The binary also takes 1keg, 1kmeg and 1e (discrepancies.md); RKM and µ are refused.
    assert not _matches("NUMBER", text)


@pytest.mark.parametrize(
    "text",
    ["1", "-2.5e-3", "1k", "1Meg", "1x", "1mil", "1a", "1f", "1h", "1hz", "1m", "1s", "1v"]
    + ["2j", "2J", "1kj", "1.0j", "1mvj", "1kHz", "1ma"],
)
def test_the_expression_reader_takes_its_units_and_j(text: str) -> None:
    assert _matches("EXPR_NUMBER", text)


@pytest.mark.parametrize(
    "text",
    [*_REFUSED_BY_BOTH, *_ARTEFACTS, "1kohm", "1amp", "1farad", "1volt", "1vdc", "1c", "1jj"],
)
def test_the_expression_reader_refuses_the_device_units(text: str) -> None:
    # `.param r=1kohm` stops Xyce (xm1-tasks 5.1 point 19).
    assert not _matches("EXPR_NUMBER", text)
