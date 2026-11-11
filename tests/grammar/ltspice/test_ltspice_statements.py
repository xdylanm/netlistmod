"""LTspice statements and directives (M8 T4; decisions 11 and 12)."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import (
    AcDirective,
    DcDirective,
    Dialect,
    Formula,
    GlobalDirective,
    IcDirective,
    Identifier,
    MeasureDirective,
    ModelStatement,
    NodesetDirective,
    NumericValue,
    OpDirective,
    OptionsDirective,
    ParamStatement,
    ParseError,
    SaveDirective,
    SourceText,
    StepDirective,
    TempDirective,
    TitleDirective,
    TranDirective,
    parse,
)


def _item(statement: str) -> Any:
    text = f"title\n{statement}\n.end\n"
    result = parse(SourceText(text), Dialect.LTSPICE)
    assert len(result.items) == 3, result.items
    return result.items[1]


def _reject(statement: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"title\n{statement}\n.end\n"), Dialect.LTSPICE)
    return captured.value


def _text(value: object) -> str | None:
    return getattr(value, "text", None)


@pytest.mark.parametrize(
    ("line", "assignments"),
    [
        (".param x=1k", [("x", "1k")]),
        (".PARAM x = 1k", [("x", "1k")]),
        (".param x 3k", [("x", "3k")]),
        (".param x=1k y=2k", [("x", "1k"), ("y", "2k")]),
        (".param x=1k, y=2k", [("x", "1k"), ("y", "2k")]),
        (".param x 3k y 4k", [("x", "3k"), ("y", "4k")]),
        (".param x=1k5", [("x", "1k5")]),
        (".param x={1k}", [("x", "1k")]),
        (".param x='1k'", [("x", "1k")]),
        ('.param x="text"', [("x", "text")]),
        (".param time=1 temper=2 hertz=3", [("time", "1"), ("temper", "2"), ("hertz", "3")]),
        (
            ".param _a=1 a_b=2 a#b=3 a.b=4 Äb=5",
            [("_a", "1"), ("a_b", "2"), ("a#b", "3")] + [("a.b", "4"), ("Äb", "5")],
        ),
        (".param pi=3 ; c", [("pi", "3")]),
        (".param x=1 $ c", [("x", "1")]),
    ],
)
def test_param_forms(line: str, assignments: list[tuple[str, str]]) -> None:
    statement = _item(line)
    assert isinstance(statement, ParamStatement)
    assert [(a.name, _text(a.value)) for a in statement.assignments] == assignments


@pytest.mark.parametrize(
    ("line", "expressions"),
    [
        (".param x=a+b", ["a+b"]),
        (".param x = a + b", ["a + b"]),
        (".param x 1+1", ["1+1"]),
        (".param x=1k+1k", ["1k+1k"]),
        (".param x=1 + 1 y=2", ["1 + 1", "2"]),
        (".param x=2*pi*100", ["2*pi*100"]),
        (".param x=y", ["y"]),
        (".param x=max(1, 2) y=3", ["max(1, 2)", "3"]),
        (".param x=(1 + 2)", ["(1 + 2)"]),
        ('.param x=select(n, "a", "b")', ['select(n, "a", "b")']),
        (".param x=((1 + 2) * (3 + (4 - 5)))", ["((1 + 2) * (3 + (4 - 5)))"]),
        (".param x=a>=b", ["a>=b"]),
        (".param x=a == b", ["a == b"]),
        (".param x=-a", ["-a"]),
        (".param x=2**3 ; c", ["2**3"]),
    ],
)
def test_bare_expressions_are_formulas_without_a_delimiter(
    line: str, expressions: list[str]
) -> None:
    statement = _item(line)
    assert [_text(a.value) for a in statement.assignments] == expressions
    first = statement.assignments[0].value
    assert isinstance(first, Formula) and first.delimiter == ""
    assert first.span.length == len(first.text)


@pytest.mark.parametrize(
    "line",
    [".param 1k", ".param x=-1", ".param x=+1k", ".param x=1e3", ".param x=1.5k y=2"],
)
def test_a_plain_number_stays_a_number(line: str) -> None:
    if line == ".param 1k":
        _reject(line)
        return
    assert isinstance(_item(line).assignments[0].value, NumericValue)


@pytest.mark.parametrize(
    "line",
    [".param", ".param x", ".param x=", ".param x==1", ".param 1a=1", ".param a!b=1"]
    + [".param a%b=1", ".param a[1]=1", ".param x=1 2", ".param x=1 // c"],
)
def test_malformed_params(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize(
    ("line", "tstep", "tstop", "tstart", "tmax", "uic", "modifiers"),
    [
        (".tran 1m", None, "1m", None, None, False, []),
        (".TRAN 1M", None, "1M", None, None, False, []),
        (".tran 0 1m", "0", "1m", None, None, False, []),
        (".tran 1u 1m 0", "1u", "1m", "0", None, False, []),
        (".tran 1u 1m 0 1u", "1u", "1m", "0", "1u", False, []),
        (".tran 1m uic", None, "1m", None, None, True, []),
        (".tran 1u 1m 0 1u uic", "1u", "1m", "0", "1u", True, []),
        (".tran 1m startup", None, "1m", None, None, False, ["startup"]),
        (".tran 1m steady nodiscard", None, "1m", None, None, False, ["steady", "nodiscard"]),
        (".tran 1m step convreport", None, "1m", None, None, False, ["step", "convreport"]),
        (".tran 1m startup uic", None, "1m", None, None, True, ["startup"]),
        (".tran 1m savestate", None, "1m", None, None, False, ["savestate"]),
        ('.tran 1m savestate="s.st"', None, "1m", None, None, False, ["savestate"]),
        ('.tran 1m loadstate="s.st"', None, "1m", None, None, False, ["loadstate"]),
        (".tran 1m savestatetime=1u", None, "1m", None, None, False, ["savestatetime"]),
    ],
)
def test_tran_forms(
    line: str,
    tstep: str | None,
    tstop: str,
    tstart: str | None,
    tmax: str | None,
    uic: bool,
    modifiers: list[str],
) -> None:
    directive = _item(line)
    assert isinstance(directive, TranDirective)
    assert _text(directive.tstep) == tstep
    assert _text(directive.tstop) == tstop
    assert _text(directive.tstart) == tstart
    assert _text(directive.tmax) == tmax
    assert (directive.uic is not None) == uic
    assert [item.name for item in directive.modifiers] == modifiers


@pytest.mark.parametrize(
    "line", [".tran", ".tran 1u 1m 0 1u 5u", ".tran 1m foo", ".tran uic 1m", ".tran 1u,1m"]
)
def test_malformed_tran(line: str) -> None:
    _reject(line)


def test_ac_forms() -> None:
    ranged = _item(".ac dec 10 1 1k5")
    assert isinstance(ranged, AcDirective)
    assert (ranged.variation, _text(ranged.points), _text(ranged.fstop)) == ("dec", "10", "1k5")
    listed = _item(".ac LIST 1 2 3k")
    assert listed.variation == "LIST" and listed.points is None
    assert [v.text for v in listed.frequencies] == ["1", "2", "3k"]
    from_file = _item(".ac file=freq_list.txt")
    assert from_file.variation == "file" and from_file.file.name == "freq_list.txt"
    assert from_file.fstart is None
    spaced = _item(".ac FILE = freq_list.txt")
    assert spaced.variation == "FILE" and spaced.file.name == "freq_list.txt"


@pytest.mark.parametrize(
    "line",
    [".ac list", ".ac log 1 1 2", ".ac dec 1 1", ".ac dec,1,1,2", ".ac file", ".ac list 1,2"],
)
def test_malformed_ac(line: str) -> None:
    _reject(line)


def test_dc_forms() -> None:
    one = _item(".dc V1 0 5 0.1")
    assert isinstance(one, DcDirective)
    assert one.sweeps[0].source == "V1" and _text(one.sweeps[0].increment) == "0.1"
    assert one.sweeps[0].variation is None
    three = _item(".dc V1 0 1 .5 V2 1 2 1 temp 0 10 5")
    assert [sweep.source for sweep in three.sweeps] == ["V1", "V2", "temp"]
    decade = _item(".dc dec V1 1 100 10 lin V2 1 2 1")
    assert [sweep.variation for sweep in decade.sweeps] == ["dec", "lin"]
    listed = _item(".dc V2 1 2 1 V1 list 1 2.5 5")
    assert listed.sweeps[1].start is None
    assert [v.text for v in listed.sweeps[1].values] == ["1", "2.5", "5"]
    from_file = _item(".dc V1 file=v.txt")
    assert from_file.sweeps[0].file.name == "v.txt"


def test_a_dc_sweep_span_covers_its_fields() -> None:
    text = "t\n.dc V2 1 2 1 V1 list 1 2\n.end\n"
    sweeps = parse(SourceText(text), Dialect.LTSPICE).items[1].sweeps
    assert text[sweeps[0].span.start : sweeps[0].span.end] == "V2 1 2 1"
    assert text[sweeps[1].span.start : sweeps[1].span.end] == "V1 list 1 2"


@pytest.mark.parametrize(
    "line",
    [".dc", ".dc V1", ".dc V1 0 1", ".dc V1,0,1,.5", ".dc V1 0 1 1 V2 0 1 1 V3 0 1 1 V4 0 1 1"]
    + [".dc V1 list 1 2 V2 1 2 1"],
)
def test_malformed_dc(line: str) -> None:
    _reject(line)


def test_op() -> None:
    assert isinstance(_item(".OP"), OpDirective)
    _reject(".op 1")


@pytest.mark.parametrize(
    ("line", "value", "others"),
    [
        (".temp 27", "27", []),
        (".temp {t}", "t", []),
        (".temp -55 25 85 125", "-55", ["25", "85", "125"]),
    ],
)
def test_temp(line: str, value: str, others: list[str]) -> None:
    directive = _item(line)
    assert isinstance(directive, TempDirective)
    assert directive.value.text == value
    assert [v.text for v in directive.others] == others


@pytest.mark.parametrize("line", [".temp", ".temp 1,2"])
def test_malformed_temp(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize(
    ("line", "names"),
    [
        (".options reltol=1m", ["reltol"]),
        (".option reltol=1m", ["reltol"]),
        (".opt reltol=1m", ["reltol"]),
        (".OPTIONS RELTOL=1M", ["RELTOL"]),
        (".options logparams", ["logparams"]),
        (".options reltol=1m abstol=1p", ["reltol", "abstol"]),
        (".options reltol=1m, abstol=1p", ["reltol", "abstol"]),
        (".options method=gear", ["method"]),
        (".options reltol={1m}", ["reltol"]),
        (".options anything=1", ["anything"]),
    ],
)
def test_options(line: str, names: list[str]) -> None:
    directive = _item(line)
    assert isinstance(directive, OptionsDirective)
    assert [item.name for item in directive.options] == names


@pytest.mark.parametrize("line", [".options", ".opti reltol=1m"])
def test_malformed_options(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        (".ic V(a)=1 V(b)=2", IcDirective),
        (".IC V( a )=1", IcDirective),
        (".ic V(a) = {x}", IcDirective),
        (".nodeset V(a)=1", NodesetDirective),
        (".ic V(a[1])=1k5", IcDirective),
    ],
)
def test_initial_conditions(line: str, kind: type) -> None:
    directive = _item(line)
    assert isinstance(directive, kind)
    assert directive.conditions[0].node is not None


@pytest.mark.parametrize(
    ("line", "currents", "voltages"),
    [
        (".ic I(L1)=1", ["L1"], []),
        (".ic i( l1 ) = {x}", ["l1"], []),
        (".ic V(a)=1 I(L1)=1k5 I(L2)=2", ["L1", "L2"], ["a"]),
    ],
)
def test_inductor_currents_in_ic(line: str, currents: list[str], voltages: list[str]) -> None:
    directive = _item(line)
    assert isinstance(directive, IcDirective)
    found = [c.current.designator for c in directive.conditions if c.current is not None]
    assert found == currents
    assert [c.node.name for c in directive.conditions if c.node is not None] == voltages


@pytest.mark.parametrize(
    "line",
    [".ic", ".ic all=1", ".nodeset all=1", ".nodeset V(a)=1 all=2", ".ic a=1", ".ic I(R1)=1"]
    + [".nodeset I(L1)=1", ".ic I(x1:L1)=1", ".ic I(L1)"]
    + [".ic V(a)=1, V(b)=2", ".ic V(a,b)=1", ".nodeset"],
)
def test_malformed_initial_conditions(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize(
    ("line", "texts"),
    [
        (".save V(out)", ["V(out)"]),
        (".save V(out) I(L1) I(R2)", ["V(out)", "I(L1)", "I(R2)"]),
        (".save V(out), I(L1)", ["V(out)", "I(L1)"]),
        (".save V(*) Id(*)", ["V(*)", "Id(*)"]),
        (".save V(x23:*)", ["V(x23:*)"]),
        (".save I(R?)", ["I(R?)"]),
        (
            ".save Ib(Q1) Ic(Q1) Ie(Q1) Ig(M1) Is(M1)",
            ["Ib(Q1)", "Ic(Q1)", "Ie(Q1)", "Ig(M1)", "Is(M1)"],
        ),
        (".save V(in,out)", ["V(in,out)"]),
    ],
)
def test_save(line: str, texts: list[str]) -> None:
    directive = _item(line)
    assert isinstance(directive, SaveDirective)
    assert [vector.text for vector in directive.vectors] == texts


def test_a_wildcard_refers_to_no_single_element() -> None:
    vectors = _item(".save I(R?) I(R1) I(x1:R1)").vectors
    assert vectors[0].source is None
    assert vectors[1].source is not None and vectors[1].source.designator == "R1"
    assert vectors[2].source is None


@pytest.mark.parametrize(
    "line",
    [".save", ".save out", ".save @r1[i]", ".save all", ".save VM(out)", ".save IM(R1)"]
    + [".save dialogbox"],
)
def test_malformed_save(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize(
    ("line", "analysis", "result", "body"),
    [
        (".meas tran y max V(out)", "tran", "y", "max V(out)"),
        (".MEAS TRAN Y AVG V(OUT)", "TRAN", "Y", "AVG V(OUT)"),
        (".meas ac y max mag(V(out))", "ac", "y", "max mag(V(out))"),
        (".meas dc y max V(out)", "dc", "y", "max V(out)"),
        (".meas noise y integ V(onoise)", "noise", "y", "integ V(onoise)"),
        (".meas op y param 1", "op", "y", "param 1"),
        (".meas y param 1", None, "y", "param 1"),
        (".measure y max V(out) ; c", None, "y", "max V(out)"),
        (
            ".meas tran x find V(a) when V(b)=2.5 cross=3",
            "tran",
            "x",
            "find V(a) when V(b)=2.5 cross=3",
        ),
    ],
)
def test_meas(line: str, analysis: str | None, result: str, body: str) -> None:
    directive = _item(line)
    assert isinstance(directive, MeasureDirective)
    found = (directive.analysis, directive.result, directive.body_text.rstrip())
    assert found == (analysis, result, body)
    assert (directive.analysis_span is None) == (analysis is None)


@pytest.mark.parametrize("line", [".meas", ".meas op", ".meas tran", ".meas op y"])
def test_malformed_meas(line: str) -> None:
    _reject(line)


def test_global_and_title() -> None:
    directive = _item(".global VDD VCC RESET")
    assert isinstance(directive, GlobalDirective)
    assert [node.name for node in directive.nodes] == ["VDD", "VCC", "RESET"]
    assert isinstance(_item(".title abc ; d"), TitleDirective)
    _reject(".global")
    _reject(".global a, b")


def test_model_forms() -> None:
    plain = _item(".model dm D")
    assert isinstance(plain, ModelStatement)
    assert (plain.name, plain.model_type, plain.params, plain.ako) == ("dm", "D", (), None)
    assert _item(".model dm D(Is=1n)").parenthesized
    assert [p.name for p in _item(".model dm D(Is=1n, N=1)").params] == ["Is", "N"]
    assert [p.name for p in _item(".model dm D Is=1n, N=1").params] == ["Is", "N"]
    assert _item(".model dm D()").params == ()
    assert _item(".model dm D(Is=1n\n+ N=1)").params[1].name == "N"
    derived = _item(".model slow AKO:fast D(tt=10n)")
    assert derived.model_type == "D" and derived.ako.model_name == "fast"
    assert derived.params[0].name == "tt"


@pytest.mark.parametrize(
    ("line", "values"),
    [
        (
            ".model DX D(Is=1e-14 Iave=1 Vpk=75 mfg=OnSemi type=silicon)",
            [(NumericValue, "1e-14"), (NumericValue, "1"), (NumericValue, "75")]
            + [(Identifier, "OnSemi"), (Identifier, "silicon")],
        ),
        ('.model DX D(mfg="OnSemi")', [(Formula, "OnSemi")]),
        (
            '.model DX D(Is=1n MFG="On Semi, Inc.")',
            [(NumericValue, "1n"), (Formula, "On Semi, Inc.")],
        ),
        (".model DX D mfg=OnSemi TYPE=silicon", [(Identifier, "OnSemi"), (Identifier, "silicon")]),
        ('.model DX D mfg="OnSemi", N=2', [(Formula, "OnSemi"), (NumericValue, "2")]),
        (".model DX D(mfg=On-Semi,type=a/b)", [(Identifier, "On-Semi"), (Identifier, "a/b")]),
        (".model DX D(mfg=3M type=1N4148A)", [(Identifier, "3M"), (Identifier, "1N4148A")]),
        (".model B ako:A D(mfg=x)", [(Identifier, "x")]),
    ],
)
def test_model_text_parameters(line: str, values: list[tuple[type, str]]) -> None:
    statement = _item(line)
    assert [(type(p.value), p.value.text) for p in statement.params] == values


@pytest.mark.parametrize(
    ("line", "word"),
    [
        (".model DX D(Is=x)", "x"),
        (".model DX D(Is=x*1n)", "x*1n"),
        (".model DX D(Is=abc)", "abc"),
        (".model DX D(Is=1n*2)", "1n*2"),
        (".model DX D Is=abc", "abc"),
        (".model DX D(N=1, Is=x)", "x"),
        (".model DX D(pn=1N4148A)", "1N4148A"),
        (".model DX D(pn=word)", "word"),
    ],
)
def test_other_model_parameters_reject_a_bare_word(line: str, word: str) -> None:
    error = _reject(line)
    assert f"{{{word}}}" in str(error) and "`mfg` and `type`" in str(error)
    assert error.column == line.index(word) + 1


@pytest.mark.parametrize(
    "line",
    ['.model DX D(Is="1n")', ".model DX D(mfg={x})", ".model DX D(type='x')", ".model DX D(mfg=)"],
)
def test_text_values_and_numeric_values_do_not_mix(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize(
    "line",
    [
        ".model DX D(Is=1n N=1k5)",
        ".model DX D(Is={x*1n})",
        ".model DX D(Is='x')",
        ".model DX D(Is=-1)",
    ],
)
def test_numbers_and_formulas_stay_as_before(line: str) -> None:
    assert _item(line).params[0].value.text


@pytest.mark.parametrize(
    "line", [".model", ".model dm", ".model dm D(Is=1n N)", ".model dm D(mfg=On Semi)"]
)
def test_malformed_models(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize(
    ("line", "column"),
    [
        (".model x BUF(Vhigh=5)", 10),
        (".model x buf", 10),
        (".model x Ota(G=1m)", 10),
        (".model x SAMPLEHOLD", 10),
        (".model slow ako:fast COUNTER", 22),
    ],
)
def test_a_special_function_is_not_a_model_type(line: str, column: int) -> None:
    # LTspice 26.1.1 stops on the .model line itself, used or not ("Expected model definition";
    # tests/solver/test_ltspice_m18_probes.py); M18 D2.
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert "is a special function, not a model type" in error.reason


def test_digital_is_not_a_model_type() -> None:
    error = _reject(".model x DIGITAL(Vhigh=5)")
    assert (error.line, error.column) == (2, 10)
    assert error.reason.startswith("`DIGITAL` is not an LTspice model type")


@pytest.mark.parametrize("line", [".model buf D", ".model x FOO(a=1)", ".model x D(Is=1n)"])
def test_other_model_types_still_load(line: str) -> None:
    # A special function's name may still name a model; an unknown type is not checked (LTspice
    # stops on `FOO` too: a finding of M18 D2 for the lead).
    assert isinstance(_item(line), ModelStatement)


def test_ngspice_reads_a_function_name_as_any_model_type() -> None:
    result = parse(SourceText("title\n.model x BUF(Vhigh=5)\n.end\n"), Dialect.NGSPICE)
    assert result.items[1].model_type == "BUF"


@pytest.mark.parametrize(
    ("line", "kind", "name", "variation", "bounds", "values"),
    [
        (".step param x 1k 3k 2k", "param", "x", None, ["1k", "3k", "2k"], []),
        (".STEP PARAM X 1 2 1", "param", "X", None, ["1", "2", "1"], []),
        (".step lin param x 1 2 1", "param", "x", "lin", ["1", "2", "1"], []),
        (".step dec param x 1 100 5", "param", "x", "dec", ["1", "100", "5"], []),
        (".step oct param x 1 8 2", "param", "x", "oct", ["1", "8", "2"], []),
        (".step param x list 1k 2k2", "param", "x", None, [], ["1k", "2k2"]),
        (".step V1 0 5 0.5", "source", "V1", None, ["0", "5", "0.5"], []),
        (".step lin I1 1 2 1", "source", "I1", "lin", ["1", "2", "1"], []),
        (".step temp -40 125 5", "temp", "temp", None, ["-40", "125", "5"], []),
        (".step TEMP list 0 27", "temp", "TEMP", None, [], ["0", "27"]),
        (".step dec temp 1 100 1", "temp", "temp", "dec", ["1", "100", "1"], []),
        (".step NPN 2N2222(VAF) 50 200 50", "model", "2N2222(VAF)", None, ["50", "200", "50"], []),
        (".step D dm(Is) 1n 2n 1n", "model", "dm(Is)", None, ["1n", "2n", "1n"], []),
    ],
)
def test_step_forms(
    line: str,
    kind: str,
    name: str,
    variation: str | None,
    bounds: list[str],
    values: list[str],
) -> None:
    step = _item(line)
    assert isinstance(step, StepDirective)
    assert (step.kind, step.name, step.variation) == (kind, name, variation)
    found = [_text(step.start), _text(step.stop), _text(step.increment)]
    assert found == (bounds or [None, None, None])
    assert [value.text for value in step.values] == values
    assert step.file is None


def test_step_slots() -> None:
    text = "t\n.step NPN 2N2222(VAF) 50 200 50 ; c\n.end\n"
    step = parse(SourceText(text), Dialect.LTSPICE).items[1]
    assert text[step.name_span.start : step.name_span.end] == "2N2222(VAF)"
    assert step.model_type.name == "NPN"
    assert step.model.model_name == "2N2222"
    assert text[step.model.span.start : step.model.span.end] == "2N2222"
    assert len(step.trailing_comments) == 1
    from_file = _item(".step param x file=rvalues.txt")
    assert from_file.file.name == "rvalues.txt"
    assert _item(".step param x\n+ 1 2 1").increment.text == "1"


@pytest.mark.parametrize(
    "line",
    [".step", ".step param", ".step param x 1 2", ".step param x 1 2 1 5", ".step param x {1} 2 1"]
    + [".step param x list 1", ".step param x list {1} 2", ".step list param x 1 2"]
    + [".step lin param x list 1 2", ".step param x, 1, 2, 1", ".step param x=1 2 1"]
    + [".step R R1 1 2 1 5"],
)
def test_malformed_step(line: str) -> None:
    _reject(line)


@pytest.mark.parametrize(
    "line",
    [".tran 1m", ".op", ".ac list 1", ".dc V1 0 1 1", ".temp 30", ".options reltol=1m"]
    + [".opt reltol=1m", ".ic V(a)=1", ".nodeset V(a)=1", ".save V(a)", ".meas op y param 1"]
    + [".global vcc", ".step param q 1 2 1", ".title x", ".end"],
)
def test_top_level_statements_are_rejected_in_a_body(line: str) -> None:
    assert "not allowed inside a subcircuit" in str(_reject(f".subckt s a\n{line}\n.ends"))
