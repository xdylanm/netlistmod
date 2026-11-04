"""Source functions on V and I lines, on both dialects (M12 T2-T5; decision 0013)."""

from __future__ import annotations

import pytest

from netlistmod import (
    CurrentSource,
    Dialect,
    Formula,
    Identifier,
    Netlist,
    NumericValue,
    ParseError,
    SourceSpec,
    VoltageSource,
)

_PULSE = "0 1 1u 1u 1u 2u 5u"

_BOTH_ACCEPT = [
    f"V1 a 0 PULSE({_PULSE})",
    "V1 a 0 pulse(0 1)",
    "V1 a 0 PuLsE(0 1)",
    "V1 a 0 PULSE(0,1,1u)",
    "V1 a 0 PULSE(0, 1, 1u)",
    f"V1 a 0 PULSE ({_PULSE})",
    f"V1 a 0 PULSE( {_PULSE} )",
    "V1 a 0 PULSE\n+ (0 1 1u)",
    "V1 a 0\n+ PULSE(0 1 1u)",
    "V1 a 0 PULSE(0 1\n+ 1u 1u)",
    "V1 a 0 PULSE(0 1 ; c\n+ 1u)",
    "V1 a 0 PULSE(0 1) ; c",
    "V1 a 0 PULSE(1)",
    f"V1 a 0 PULSE({_PULSE} 2 9 9 9)",
    "V1 a 0 PULSE(0 {x} 1u)",
    "V1 a 0 PULSE(0 'x*2' 1u)",
    "V1 a 0 PULSE(-1 +1)",
    "V1 a 0 SIN(0 1 1MEG)",
    "V1 a 0 SIN(0V 1V 1kHz)",
    "V1 a 0 SINE(0 1 1k)",
    "V1 a 0 EXP(0 1 1u)",
    "V1 a 0 SFFM(0 1 100k)",
    "V1 a 0 PWL(0 0 5u 1)",
    "V1 a 0 PWL(0 0 5u)",
    "V1 a 0 PWL(0,0 5u,1)",
    "V1 a 0 PWL(0 0 +1u 1)",
    "I1 a 0 PULSE(0 1)",
    "I1 a 0 DC 1 SIN(0 1)",
    "I1 a 0 SIN(0 1) AC 1",
]
_NGSPICE_ACCEPT = [
    "V1 a 0 AM(1 0 1k 100k)",
    "V1 a 0 TRNOISE(1m 1u 0 0)",
    "V1 a 0 dc 0 trrandom (2 10m 0 1)",
    "V1 a 0 external",
    "V1 a 0 dc 0 external",
    "I1 a 0 dc 0 external m=2",
    "I1 a 0 dc 0 external m = 2",
    "V1 a 0 PWL(0 0 5u 1) r=0 td=1u",
    "V1 a 0 PWL(0 -7 1n -7)\n+ r=0 td=15NS",
    "V1 a 0 PWL(0 0 1 1) td=1u AC 1",
    "V1 a 0 PULSE(0 1 \\\\\n1u)",
    "V1 a 0 \\\\\nPULSE(-1 1 \\\\\n2NS)",
    "V1 a 0,PULSE(0 1)",
]
_LTSPICE_ACCEPT = [
    "V1 a 0 PULSE(0 1) Rser=1 Cpar=1p",
    "V1 a 0 Rser=1 PULSE(0 1)",
    "V1 a 0 1 Rser=1 PULSE(0 1) AC 1",
    "V1 a 0 AC 1 Rser=1 PULSE(0 1)",
    "V1 a 0 PULSE(0 1) Trigger=V(a)>0.5",
    "V1 a 0 PULSE(0 1) Trigger=V(a)>0.5 tripdv=1m tripdt=1u",
    "I1 a 0 PULSE(0 1) Trigger=V(a)>0",
    "V1 a 0 SIN(0 1 1k) AC 1 Rser=1",
    "V1 a 0 SIN(0 1 1k) Rser=1 AC 1",
    "V1 a 0 SIN(0 1 1k) AC=1",
    "V1 a 0 SINE(0 1 1k 0 0 0 3)",
    "V1 a 0 PULSE(1k5 2R2)",
    "V1 a 0 PWL REPEAT FOR 2 (0 0 1u 0) ENDREPEAT",
    "V1 a 0 PWL REPEAT FOREVER (0 0 1u 0) ENDREPEAT",
    "V1 a 0 PWL TIME_SCALE_FACTOR=2 VALUE_SCALE_FACTOR=3 (0 0 1u 1)",
    "V1 a 0 PWL file=x.txt",
    'V1 a 0 PWL file="x y.txt"',
    "V1 a 0 wavefile=x.wav chan=0",
    'V1 a 0 wavefile="x.wav"',
    "I1 a 0 tbl=(0 0, 1 1)",
    "I1 a 0 tbl=(0,0,1,1)",
    "I1 a 0 1 step(1,2,3)",
    "I1 a 0 1 step(1 2 3)",
    "I1 a 0 step(1,2,3)",
    "I1 a 0 1 step(1,2,3) load",
    "I1 a 0 PULSE(0 1) load",
]
_BOTH_REJECT = [
    ("V1 a 0 PULSE 0 1 1u", "no parentheses"),
    ("V1 a 0 PULSE()", "empty list"),
    ("V1 a 0 PULSE(0 x)", "bare name"),
    ("V1 a 0 PULSE(0 x*2)", "bare expression"),
    ("V1 a 0 PULSE(0 1", "unclosed"),
    ("V1 a 0 SIN(0 1) 1", "value after a function"),
    ("V1 a 0 SIN(0 1) PULSE(0 1)", "two functions"),
    ("V1 a 0 DC 1 SIN(0 1) DC 2", "two DC parts"),
    ("V1 a 0 AC 1 SIN(0 1) AC 2", "two AC parts"),
    ("V1 a 0 PWL(file=x.txt)", "file in a list"),
    ("V1 a 0 PULSE(0 1) m=2", "m on a function that has none"),
]
_NGSPICE_REJECT = [
    ("V1 a 0 PULSE(0 1) r=0", "r on PULSE"),
    ("V1 a 0 PULSE(0 1) td=1", "td on PULSE"),
    ("V1 a 0 PWL(0 0 1 1) m=2", "m on PWL"),
    ("V1 a 0 PWL file=x.txt", "LTspice's file form"),
    ("V1 a 0 wavefile=x", "LTspice's wave form"),
    ("I1 a 0 tbl=(0 0)", "LTspice's table"),
    ("V1 a 0 DISTOF2 1 DISTOF1 2", "distortion inputs out of order"),
    ("V1 a 0 PAT(0 1)", "not in the manual"),
    ("V1 a 0 PORT 1", "not in the manual"),
    ("I1 a 0 dc 0 ac 1 portnum 1", "RF port on I"),
]
_LTSPICE_REJECT = [
    ("V1 a 0 AM(1 0)", "ngspice's AM"),
    ("V1 a 0 TRNOISE(1)", "ngspice's TRNOISE"),
    ("V1 a 0 DISTOF1 1", "ngspice's DISTOF1"),
    ("V1 a 0 external", "ngspice's EXTERNAL"),
    ("V1 a 0 PWL(0 0 1 1) r=0", "ngspice's r"),
    ("V1 a 0 PWL(0 0 1 1) TIME_SCALE_FACTOR=2", "a factor after the list"),
    ("V1 a 0 PWL file=x TIME_SCALE_FACTOR=2", "a factor after a file"),
    ("I1 a 0 PULSE(0 1) Rser=1", "Rser on I"),
    ("V1 a 0 1 Rser=1 AC 1", "Rser before AC with no function"),
    ("V1 a 0 tbl=(0 0)", "a table on V"),
    ("V1 a 0 step(1)", "a step on V"),
    ("V1 a 0 Trigger=1", "a trigger with no function"),
    ("V1 a 0 PULSE(0 1) chan=0", "chan on PULSE"),
    ("V1 a 0 wavefile=x Rser=1 chan=0", "chan away from its function"),
]
_ORDERS = [
    ("V1 a 0 AC 1 SIN(0 1)", False, True),
    ("V1 a 0 DC 1 SIN(0 1)", True, False),
    ("V1 a 0 1 SIN(0 1)", True, False),
    ("V1 a 0 DC 1 AC 1 SIN(0 1)", True, True),
    ("V1 a 0 SIN(0 1) AC 1", False, True),
    ("V1 a 0 SIN(0 1) AC 1 45", False, True),
    ("V1 a 0 SIN(0 1) DC 1", True, False),
    ("V1 a 0 SIN(0 1) DC 1 AC 1", True, True),
    ("V1 a 0 SIN(0 1) AC 1 DC 1", True, True),
    ("V1 a 0 DC 1 SIN(0 1) AC 1", True, True),
    ("V1 a 0 AC 1 SIN(0 1) DC 1", True, True),
]


def _text(line: str) -> str:
    return f"t\n.param x=1\n{line}\nR1 a 0 1k\n.tran 1u 10u\n.end\n"


def _load(line: str, dialect: Dialect) -> Netlist:
    return Netlist.from_text(_text(line), dialect=dialect)


def _source(netlist: Netlist) -> VoltageSource | CurrentSource:
    return netlist.lines.find_all((VoltageSource, CurrentSource))[0].item  # type: ignore[return-value]


@pytest.mark.parametrize("dialect", [Dialect.NGSPICE, Dialect.LTSPICE], ids=lambda d: d.value)
@pytest.mark.parametrize("line", _BOTH_ACCEPT)
def test_both_dialects_accept(dialect: Dialect, line: str) -> None:
    netlist = _load(line, dialect)
    assert _source(netlist).stimulus is not None
    assert netlist.source.text == _text(line)


@pytest.mark.parametrize("line", _NGSPICE_ACCEPT)
def test_ngspice_accepts(line: str) -> None:
    netlist = _load(line, Dialect.NGSPICE)
    assert _source(netlist).stimulus is not None
    assert netlist.source.text == _text(line)


@pytest.mark.parametrize("line", _LTSPICE_ACCEPT)
def test_ltspice_accepts(line: str) -> None:
    netlist = _load(line, Dialect.LTSPICE)
    assert _source(netlist).stimulus is not None
    assert netlist.source.text == _text(line)


@pytest.mark.parametrize("dialect", [Dialect.NGSPICE, Dialect.LTSPICE], ids=lambda d: d.value)
@pytest.mark.parametrize(("line", "why"), _BOTH_REJECT, ids=[why for _, why in _BOTH_REJECT])
def test_both_dialects_refuse(dialect: Dialect, line: str, why: str) -> None:
    with pytest.raises(ParseError) as captured:
        _load(line, dialect)
    assert captured.value.line >= 3, why


@pytest.mark.parametrize(("line", "why"), _NGSPICE_REJECT, ids=[why for _, why in _NGSPICE_REJECT])
def test_ngspice_refuses(line: str, why: str) -> None:
    with pytest.raises(ParseError):
        _load(line, Dialect.NGSPICE)


@pytest.mark.parametrize(("line", "why"), _LTSPICE_REJECT, ids=[why for _, why in _LTSPICE_REJECT])
def test_ltspice_refuses(line: str, why: str) -> None:
    with pytest.raises(ParseError):
        _load(line, Dialect.LTSPICE)


@pytest.mark.parametrize("dialect", [Dialect.NGSPICE, Dialect.LTSPICE], ids=lambda d: d.value)
@pytest.mark.parametrize(("line", "has_dc", "has_ac"), _ORDERS)
def test_a_function_stands_before_or_after_dc_and_ac(
    dialect: Dialect, line: str, has_dc: bool, has_ac: bool
) -> None:
    source = _source(_load(line, dialect))
    assert (source.dc is not None, source.ac is not None) == (has_dc, has_ac)
    assert source.stimulus is not None
    assert source.stimulus.name == "SIN"


def test_the_phase_stays_with_the_ac_part() -> None:
    source = _source(_load("V1 a 0 SIN(0 1) AC 1 45", Dialect.NGSPICE))
    assert source.ac is not None
    assert source.ac.phase is not None
    assert source.ac.phase.text == "45"


def test_a_function_has_typed_arguments_with_spans() -> None:
    netlist = _load("V1 a 0 PULSE(0, {x} 'x*2'\n+ 1u) ; c", Dialect.NGSPICE)
    spec = _source(netlist).stimulus
    assert isinstance(spec, SourceSpec)
    assert spec.name == "PULSE"
    text = netlist.source.text
    assert text[spec.name_span.start : spec.name_span.end] == "PULSE"
    assert [text[arg.span.start : arg.span.end] for arg in spec.args] == [
        "0",
        "{x}",
        "'x*2'",
        "1u",
    ]
    assert [type(arg) for arg in spec.args] == [NumericValue, Formula, Formula, NumericValue]
    assert text[spec.span.start : spec.span.end] == "PULSE(0, {x} 'x*2'\n+ 1u)"


def test_a_function_is_not_topology() -> None:
    for dialect in (Dialect.NGSPICE, Dialect.LTSPICE):
        plain = Netlist.from_text("t\nV1 a 0 1\n.end\n", dialect=dialect)
        with_function = Netlist.from_text("t\nV1 a 0 1 SIN(0 {x} 1)\n.end\n", dialect=dialect)
        assert with_function.signature() == plain.signature()


def test_a_formula_argument_is_a_reference() -> None:
    netlist = _load("V1 a 0 PULSE(0 {undefined_name})", Dialect.NGSPICE)
    assert "undefined_name" in {reference.name for reference in netlist.references}
    assert any(item.code.value == "UNRESOLVED_PARAM" for item in netlist.diagnostics)


def test_a_comment_inside_a_function_is_a_trailing_comment() -> None:
    netlist = _load("V1 a 0 PULSE(0 1 ; inner\n+ 1u) ; outer", Dialect.NGSPICE)
    source = _source(netlist)
    comments = [netlist.source.text[span.start : span.end] for span in source.trailing_comments]
    assert comments == ["; inner", "; outer"]


def test_ngspice_named_parameters_belong_to_the_function() -> None:
    netlist = _load("V1 a 0 PWL(0 0 5u 1) r=0 td=1u AC 1", Dialect.NGSPICE)
    source = _source(netlist)
    assert source.stimulus is not None
    assert [param.name for param in source.stimulus.params] == ["r", "td"]
    assert source.params == ()
    span = source.stimulus.span
    assert netlist.source.text[span.start : span.end] == "PWL(0 0 5u 1) r=0 td=1u"


def test_external_takes_m() -> None:
    source = _source(_load("I1 a 0 dc 0 external m=2", Dialect.NGSPICE))
    assert source.stimulus is not None
    assert source.stimulus.name == "external"
    assert source.stimulus.args == ()
    assert [param.name for param in source.stimulus.params] == ["m"]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("V1 a 0 DC 0 DISTOF1 0.1", [("DISTOF1", ["0.1"])]),
        ("V1 a 0 DISTOF1 0.1 -90.0", [("DISTOF1", ["0.1", "-90.0"])]),
        ("V1 a 0 DISTOF2 0.01", [("DISTOF2", ["0.01"])]),
        ("V1 a 0 DISTOF1", [("DISTOF1", [])]),
        ("I1 a 0 AC 1 DISTOF1 DISTOF2 0.001", [("DISTOF1", []), ("DISTOF2", ["0.001"])]),
        (
            "V1 a 0 DISTOF1 0.1 2 DISTOF2 0.2 3",
            [("DISTOF1", ["0.1", "2"]), ("DISTOF2", ["0.2", "3"])],
        ),
        ("V1 a 0 SIN(0 1) DISTOF1 0.1", [("DISTOF1", ["0.1"])]),
    ],
)
def test_distortion_inputs(line: str, expected: list[tuple[str, list[str]]]) -> None:
    source = _source(_load(line, Dialect.NGSPICE))
    found = [(spec.name, [str(arg.text) for arg in spec.args]) for spec in source.distortion]
    assert found == expected


@pytest.mark.parametrize(
    "line",
    ["V1 a 0 dc 0 ac 1 portnum 1 z0 100", "V1 a 0 dc 0 ac 1 portnum=1 z0=100"],
)
def test_rf_port_parameters_are_line_parameters(line: str) -> None:
    source = _source(_load(line, Dialect.NGSPICE))
    assert [(param.name, param.value.text) for param in source.params] == [
        ("portnum", "1"),
        ("z0", "100"),
    ]


def test_rf_port_after_a_function() -> None:
    source = _source(_load("V1 a 0 SIN(0 1) portnum 1", Dialect.NGSPICE))
    assert source.stimulus is not None
    assert [param.name for param in source.params] == ["portnum"]


def test_ltspice_line_parameters_stay_on_the_line() -> None:
    source = _source(_load("V1 a 0 PULSE(0 1) Rser=1 Trigger=V(a)>0.5", Dialect.LTSPICE))
    assert source.stimulus is not None
    assert source.stimulus.params == ()
    assert [param.name for param in source.params] == ["Rser", "Trigger"]
    trigger = source.params[1].value
    assert isinstance(trigger, Identifier)
    assert trigger.text == "V(a)>0.5"


@pytest.mark.parametrize(
    ("line", "name", "value", "kind"),
    [
        ("V1 a 0 PWL file=x.txt", "file", "x.txt", Identifier),
        ('V1 a 0 PWL file="x y.txt"', "file", "x y.txt", Formula),
        ("V1 a 0 wavefile=x.wav", "wavefile", "x.wav", Identifier),
    ],
)
def test_ltspice_file_paths_are_text(line: str, name: str, value: str, kind: type) -> None:
    source = _source(_load(line, Dialect.LTSPICE))
    assert source.stimulus is not None
    assert source.stimulus.args == ()
    param = source.stimulus.params[0]
    assert param.name == name
    assert isinstance(param.value, kind)
    assert param.value.text == value


def test_ltspice_repeat_forms() -> None:
    counted = _source(_load("V1 a 0 PWL REPEAT FOR 2 (0 0 1u 0) ENDREPEAT", Dialect.LTSPICE))
    assert counted.stimulus is not None
    assert [(p.name, p.value.text) for p in counted.stimulus.params] == [("FOR", "2")]
    assert len(counted.stimulus.args) == 4
    assert not counted.stimulus.forever
    forever = _source(_load("V1 a 0 PWL REPEAT FOREVER (0 0 1u 0) ENDREPEAT", Dialect.LTSPICE))
    assert forever.stimulus is not None
    assert forever.stimulus.forever
    assert forever.stimulus.span.end == forever.span.end - 1


def test_ltspice_scale_factors_and_wave_channel() -> None:
    scaled = _source(_load("V1 a 0 PWL TIME_SCALE_FACTOR=2 (0 0 1u 1)", Dialect.LTSPICE))
    assert scaled.stimulus is not None
    assert [param.name for param in scaled.stimulus.params] == ["TIME_SCALE_FACTOR"]
    wave = _source(_load("V1 a 0 wavefile=x.wav chan=3", Dialect.LTSPICE))
    assert wave.stimulus is not None
    assert [param.name for param in wave.stimulus.params] == ["wavefile", "chan"]


def test_ltspice_table_and_step_load() -> None:
    table = _source(_load("I1 a 0 tbl=(0 0, 1 1)", Dialect.LTSPICE))
    assert table.stimulus is not None
    assert (table.stimulus.name, len(table.stimulus.args)) == ("tbl", 4)
    step = _source(_load("I1 a 0 1 step(1,2,3) load", Dialect.LTSPICE))
    assert step.stimulus is not None
    assert step.dc is not None
    assert (step.stimulus.name, len(step.stimulus.args)) == ("step", 3)
    assert [flag.name for flag in step.flags] == ["load"]


def test_sine_is_accepted_on_ngspice_as_its_own_name() -> None:
    source = _source(_load("V1 a 0 SINE(0 1 1k)", Dialect.NGSPICE))
    assert source.stimulus is not None
    assert source.stimulus.name == "SINE"


def test_a_wrong_named_parameter_says_which_function_takes_it() -> None:
    with pytest.raises(ParseError, match="applies only to `PWL`"):
        _load("V1 a 0 PULSE(0 1) r=0", Dialect.NGSPICE)
    with pytest.raises(ParseError, match="for a V line"):
        _load("I1 a 0 dc 0 ac 1 portnum 1", Dialect.NGSPICE)
    with pytest.raises(ParseError, match="applies only to `WAVEFILE`"):
        _load("V1 a 0 PULSE(0 1) chan=0", Dialect.LTSPICE)
    with pytest.raises(ParseError, match="must follow"):
        _load("V1 a 0 wavefile=x Rser=1 chan=0", Dialect.LTSPICE)


def test_crlf_round_trips() -> None:
    for dialect in (Dialect.NGSPICE, Dialect.LTSPICE):
        text = "t\r\nV1 a 0 PULSE(0 1\r\n+ 1u) AC 1\r\n.end\r\n"
        assert Netlist.from_text(text, dialect=dialect).source.text == text


@pytest.mark.parametrize(
    "line",
    [
        "V1 a 0 ; c\n+ wavefile=x.wav",
        "V1 a 0 PWL ; c\n+ REPEAT FOR 2 (0 0 1u 0) ; d\n+ ENDREPEAT",
        "V1 a 0 PWL ; c\n+ file=x.txt",
        "V1 a 0 PWL ; c\n+ TIME_SCALE_FACTOR=2 ; d\n+ (0 0 1u 1)",
        "I1 a 0 ; c\n+ tbl=(0 0)",
        "I1 a 0 ; c\n+ step(1)",
    ],
)
def test_comments_between_the_parts_of_an_ltspice_function(line: str) -> None:
    netlist = _load(line, Dialect.LTSPICE)
    source = _source(netlist)
    assert source.stimulus is not None
    assert source.trailing_comments
    assert netlist.source.text == _text(line)
