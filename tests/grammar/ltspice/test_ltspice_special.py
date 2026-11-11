"""LTspice special functions (A), the frequency response analyzer (@) and its probe (&) (M17 T7;
decision 0020 items 3, 7 and 8)."""

from __future__ import annotations

import pytest

from netlistmod import (
    Dialect,
    FraProbe,
    FrequencyAnalyzer,
    Identifier,
    ParseError,
    SourceText,
    SpecialFunction,
    ValueList,
    parse,
)

FUNCTIONS = (
    "BUF AND OR XOR SCHMITT DFLOP SRFLOP VARISTOR MODULATOR OTA PHASEDET COUNTER SAMPLEHOLD"
).split()
NODES = "in 0 0 0 0 nq q com"
COMMA = "LTspice element lines separate their fields with blanks"


def _item(line: str) -> object:
    return parse(SourceText(f"title\n{line}\n.end\n"), Dialect.LTSPICE).items[1]


def _reject(line: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"title\n{line}\n.end\n"), Dialect.LTSPICE)
    return captured.value


@pytest.mark.parametrize("name", [*FUNCTIONS, "buf", "Schmitt"])
def test_each_function_name_loads(name: str) -> None:
    item = _item(f"A1 {NODES} {name}")
    assert isinstance(item, SpecialFunction)
    assert item.function.name == name
    assert [n.name for n in item.inputs] == ["in", "0", "0", "0", "0"]
    assert [n.name for n in item.outputs] == ["nq", "q"]
    assert item.common.name == "com"


def test_parameters_are_open() -> None:
    item = _item(f"A1 {NODES} OTA G=1m Iout=1m Isink={{-1m}} Rout=1k")
    assert isinstance(item, SpecialFunction)
    assert [(p.name, p.value.text) for p in item.params] == [
        ("G", "1m"),
        ("Iout", "1m"),
        ("Isink", "-1m"),
        ("Rout", "1k"),
    ]


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        (f"A1 {NODES} INV", 24, "the INV symbol writes `BUF`"),
        (f"A1 {NODES} MODULATE", 24, "writes `MODULATOR`"),
        (f"A1 {NODES} FOO", 24, "is not a special function name"),
        (f"A1 {NODES} BUF Vhigh=x", 34, "write `{x}`"),
        (f"A1 {NODES} BUF 5", 28, "positional value"),
        (f"A1 {NODES} BUF off", 28, "takes no flag"),
        ("A1 in 0 0 0 0 nq q 0 0 BUF", 22, "is not a special function name"),  # nine nodes
        (f"A1 {NODES} BUF Vhigh=5, Vlow=0", 35, COMMA),
        (f"A1 {NODES} BUF Vhigh=5,Vlow=0", 35, COMMA),
        (f"A1 {NODES} BUF, Vhigh=5", 27, COMMA),
    ],
)
def test_refused_special_function_lines(line: str, column: int, reason: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


def test_seven_nodes_end_the_line_too_early() -> None:
    error = _reject("A1 in 0 0 0 0 q 0 BUF")
    assert (error.line, error.column) == (2, 22)


def test_the_analyzer_reads_lists_flags_and_nets() -> None:
    item = _item(
        "@1 in out zm fstart=1k fend=10k flist=1k 2k\n+ 5k pp=1k 10m 10k 1m ac=1,0 nmax=5"
        " refnode=r intnode=out enabled=0"
    )
    assert isinstance(item, FrequencyAnalyzer)
    assert item.impedance is not None and item.impedance.name == "zm"
    values = {p.name: p.value for p in item.params}
    flist = values["flist"]
    assert isinstance(flist, ValueList) and [v.text for v in flist.values] == ["1k", "2k", "5k"]
    assert isinstance(values["pp"], ValueList) and len(values["pp"].values) == 4
    assert isinstance(values["ac"], ValueList) and values["ac"].text == "1,0"
    assert values["nmax"].text == "5"
    assert isinstance(values["refnode"], Identifier)
    assert item.reference_net is not None and item.reference_net.name == "r"
    assert item.intermediate_net is not None and item.intermediate_net.name == "out"
    assert [n.name for n in item.nodes] == ["in", "out"]


def test_an_analyzer_takes_no_parameter_at_all() -> None:
    item = _item("@1 in out")
    assert isinstance(item, FrequencyAnalyzer) and item.params == () and item.impedance is None


@pytest.mark.parametrize("line", ["@1 a b ac=1,0", "@1 a b ac=1, 0", "@1 a b ac=1 0"])
def test_ac_writes_its_magnitude_and_phase_with_a_comma_or_a_blank(line: str) -> None:
    item = _item(line)
    assert isinstance(item, FrequencyAnalyzer)
    value = item.params[0].value
    assert isinstance(value, ValueList) and [v.text for v in value.values] == ["1", "0"]


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("@1 a b foo=1", 8, "is not a parameter of the frequency response analyzer"),
        ("@1 a b zm ZM", 11, "a second `ZM`"),
        ("@1 a b fend=1k 2k", 16, "only flist=, pp=, nmax= and ac= take a list"),
        ("@1 a b 5", 8, "a value without a name"),
        ("@1 a b fstart=f1", 15, "write `{f1}`"),
        ("@1 a b fstart=1k, fend=2k", 17, COMMA),
        ("@1 a b fstart=1k,fend=2k", 17, COMMA),
        ("@1 a b zm, fstart=1k", 10, COMMA),
        ("@1 a b fstart=1k, zm", 17, COMMA),
        ("@1 a b fstart=1k, refnode=a", 17, COMMA),
        ("@1 a b flist=1k,2k,5k", 16, COMMA),
        ("@1 a b flist=1k, 2k", 16, COMMA),
        ("@1 a b pp=1k, 10m", 13, COMMA),
        ("@1 a b nmax=1k,2", 15, COMMA),
        ("@1 a b ac=1,0, fstart=1k", 14, COMMA),
    ],
)
def test_refused_analyzer_lines(line: str, column: int, reason: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


@pytest.mark.parametrize("line", ["@1 a", "@1 a b c"])
def test_an_analyzer_has_two_nodes(line: str) -> None:
    assert _reject(line).line == 2


def test_a_probe_has_four_nodes_and_names_its_analyzer() -> None:
    item = _item("&a out 0 in 0")
    assert isinstance(item, FraProbe)
    assert item.analyzer.designator == "@a"
    assert [n.name for n in item.output_pair] == ["out", "0"]
    assert [n.name for n in item.input_pair] == ["in", "0"]


@pytest.mark.parametrize("line", ["&1 a 0 b", "&1 a 0 b 0 c", "&1 a 0 b 0 x=1"])
def test_refused_probe_lines(line: str) -> None:
    assert _reject(line).line == 2
