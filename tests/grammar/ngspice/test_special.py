"""ngspice code models (A), OSDI devices (N) and code-model .model values (M17 T4 to T6;
decision 0020 items 4 to 6)."""

from __future__ import annotations

import pytest

from netlistmod import (
    CodeModelDevice,
    Dialect,
    Formula,
    Identifier,
    ModelStatement,
    OsdiDevice,
    ParseError,
    SourceText,
    ValueList,
    parse,
)


def _items(body: str) -> tuple[object, ...]:
    return parse(SourceText(f"title\n{body}\n.end\n"), Dialect.NGSPICE).items[1:-1]


def _a(line: str) -> CodeModelDevice:
    item = _items(line)[0]
    assert isinstance(item, CodeModelDevice)
    return item


def _reject(body: str) -> ParseError:
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"title\n{body}\n.end\n"), Dialect.NGSPICE)
    return captured.value


def _ports(item: CodeModelDevice) -> list[tuple[object, ...]]:
    return [
        (
            port.vector,
            port.port_type,
            [
                (c.port_type, [n.name for n in c.nodes], c.inverted, c.null)
                for c in port.connections
            ],
        )
        for port in item.ports
    ]


@pytest.mark.parametrize(
    ("line", "ports"),
    [
        (
            "a1 in out amp",
            [
                (False, None, [(None, ["in"], False, False)]),
                (False, None, [(None, ["out"], False, False)]),
            ],
        ),
        (
            "a1 %v(in) %V(out) amp",
            [
                (False, None, [("%v", ["in"], False, False)]),
                (False, None, [("%V", ["out"], False, False)]),
            ],
        ),
        (
            "a1 %v in %v (out) amp",
            [
                (False, None, [("%v", ["in"], False, False)]),
                (False, None, [("%v", ["out"], False, False)]),
            ],
        ),
        (
            "a1 %vd(in 0) %vd in 0 (out) amp",
            [
                (False, None, [("%vd", ["in", "0"], False, False)]),
                (False, None, [("%vd", ["in", "0"], False, False)]),
                (False, None, [(None, ["out"], False, False)]),
            ],
        ),
        (
            "a1 %vd (in 0) out amp",
            [
                (False, None, [("%vd", ["in", "0"], False, False)]),
                (False, None, [(None, ["out"], False, False)]),
            ],
        ),
        (
            "a1 [ in1 in2 ] out sum",
            [
                (True, None, [(None, ["in1"], False, False), (None, ["in2"], False, False)]),
                (False, None, [(None, ["out"], False, False)]),
            ],
        ),
        (
            "a1 %i[1 %vd(2 5) 7] 3 sum",
            [
                (
                    True,
                    "%i",
                    [
                        (None, ["1"], False, False),
                        ("%vd", ["2", "5"], False, False),
                        (None, ["7"], False, False),
                    ],
                ),
                (False, None, [(None, ["3"], False, False)]),
            ],
        ),
        (
            "a1 %vd [1 2 3 4] 5 sum",
            [
                (True, "%vd", [(None, ["1", "2"], False, False), (None, ["3", "4"], False, False)]),
                (False, None, [(None, ["5"], False, False)]),
            ],
        ),
        (
            "a1 %v [1 2 %vd 3 4] 5 sum",
            [
                (
                    True,
                    "%v",
                    [
                        (None, ["1"], False, False),
                        (None, ["2"], False, False),
                        ("%vd", ["3", "4"], False, False),
                    ],
                ),
                (False, None, [(None, ["5"], False, False)]),
            ],
        ),
        (
            "a1 [~1 2] 3 nand",
            [
                (True, None, [(None, ["1"], True, False), (None, ["2"], False, False)]),
                (False, None, [(None, ["3"], False, False)]),
            ],
        ),
        (
            "a1 d clk null NULL q ~qb ff",
            [
                (False, None, [(None, ["d"], False, False)]),
                (False, None, [(None, ["clk"], False, False)]),
                (False, None, [(None, [], False, True)]),
                (False, None, [(None, [], False, True)]),
                (False, None, [(None, ["q"], False, False)]),
                (False, None, [(None, ["qb"], True, False)]),
            ],
        ),
        (
            "a1 in, out amp",
            [
                (False, None, [(None, ["in"], False, False)]),
                (False, None, [(None, ["out"], False, False)]),
            ],
        ),
    ],
)
def test_ports_and_connections(line: str, ports: list[tuple[object, ...]]) -> None:
    item = _a(line)
    assert _ports(item) == ports
    assert item.nodes == tuple(n for p in item.ports for c in p.connections for n in c.nodes)
    assert item.model.model_name == line.split()[-1]
    assert item.params == ()


def test_vnam_names_a_source_that_is_not_a_node() -> None:
    for line in ("a1 %vnam V1 out amp", "a1 %vnam(V1) out amp", "a1 %VNAM V1 out amp"):
        item = _a(line)
        assert [r.designator for r in item.control] == ["V1"]
        assert [n.name for n in item.nodes] == ["out"]
        connection = item.ports[0].connections[0]
        assert connection.nodes == () and connection.source is not None


def test_spans_slice_back_to_their_text() -> None:
    text = "title\na1 %v [in1 %vd(in2 in1)] ~out amp\n.end\n"
    item = parse(SourceText(text), Dialect.NGSPICE).items[1]
    assert isinstance(item, CodeModelDevice)
    vector, scalar = item.ports
    assert text[vector.span.start : vector.span.end] == "%v [in1 %vd(in2 in1)]"
    assert text[vector.connections[1].span.start : vector.connections[1].span.end] == "%vd(in2 in1)"
    assert text[scalar.span.start : scalar.span.end] == "~out"
    assert text[item.model.span.start : item.model.span.end] == "amp"


def test_comments_inside_a_continued_line_are_kept() -> None:
    item = _a("a1 [in1 ; first\n+ in2] out ; last\n+ sum")
    assert len(item.trailing_comments) == 2
    assert [n.name for n in item.nodes] == ["in1", "in2", "out"]


def test_a_comment_inside_a_differential_connection_is_kept() -> None:
    text = "title\nA1 %vd a ; c\n+ b m\n.end\n"
    item = parse(SourceText(text), Dialect.NGSPICE).items[1]
    assert isinstance(item, CodeModelDevice)
    assert _ports(item) == [(False, None, [("%vd", ["a", "b"], False, False)])]
    (connection,) = item.ports[0].connections
    assert text[connection.span.start : connection.span.end] == "%vd a ; c\n+ b"
    assert [text[s.start : s.end] for s in item.trailing_comments] == ["; c"]
    assert text[item.model.span.start : item.model.span.end] == "m"


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("a1 in out amp gain=2", 15, "takes its parameters on its `.model` line"),
        ("a1 [in, in] out sum", 7, "a comma inside a vector"),
        ("a1 %vd [in 0, in 0] out sum", 13, "a comma inside a vector"),
        ("a1 %vd(in, 0) out amp", 10, "a comma inside a connection's parentheses"),
        ("a1 ~ d y inv", 4, "`~` before a blank"),
        ("a1 in out 5", 11, "a model name cannot be a number"),
        ("a1 amp", 4, "no ports before it"),
        ("a1 in [out]", 7, "ends with its model"),
        ("a1 in ~amp", 7, "ends with its model"),
        ("a1 [%vnam V1 in] out sum", 5, "`%vnam` inside a vector"),
        ("a1 %v null out amp", 4, "`null` after `%v`"),
        ("a1 ~null out amp", 4, "`~null`"),
        ("a1 %vd(in) out amp", 4, "takes two nodes"),
        ("a1 %v(in 0) out amp", 4, "takes one node"),
        ("a1 (in 0) out amp", 4, "takes one node"),
        ("a1 %vd [in 0 in] out sum", 16, "a `%vd` vector holds an odd number of nets"),
    ],
)
def test_refused_code_model_lines(line: str, column: int, reason: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("a1 %vd [in 0 out] 5 sum", 17),
        ("a1 %vd [in] 5 sum", 11),
        ("a1 %id [in 0 out ] 5 sum", 18),
        ("a1 %VD [1 2\n+ 3] 5 sum", 4),
    ],
)
def test_an_odd_count_in_a_differential_vector_has_its_own_message(line: str, column: int) -> None:
    # Carried from M17 (M18 C6): the message, at the `]`, instead of the expected tokens.
    error = _reject(line)
    assert (error.column, error.expected) == (column, ())
    assert "vector holds an odd number of nets: each of its connections is a pair" in error.reason
    assert error.reason.startswith(f"a `{line.split()[1]}` vector")


@pytest.mark.parametrize("line", ["a1 [[in] in] out sum", "a1 [] out sum", "a1 %foo in out amp"])
def test_malformed_code_model_lines_are_syntax_errors(line: str) -> None:
    assert _reject(line).line == 2


def _model(text: str) -> ModelStatement:
    item = _items(text)[0]
    assert isinstance(item, ModelStatement)
    return item


def test_code_model_values() -> None:
    text = (
        ".model sum summer(in_offset=[0.1 -0.2] in_gain=[2.0 {g}]\n"
        '+ out_gain=5 fraction=FALSE log=true file="in.txt")'
    )
    model = _model(text)
    values = {param.name: param.value for param in model.params}
    offset = values["in_offset"]
    assert isinstance(offset, ValueList) and offset.text == "[0.1 -0.2]"
    assert [v.text for v in offset.values] == ["0.1", "-0.2"]
    gain = values["in_gain"]
    assert isinstance(gain, ValueList) and isinstance(gain.values[1], Formula)
    assert isinstance(values["fraction"], Identifier) and values["fraction"].name == "FALSE"
    assert isinstance(values["log"], Identifier)
    path = values["file"]
    assert isinstance(path, Formula) and path.delimiter == '"' and path.text == "in.txt"


def test_a_vector_may_be_first_or_over_a_continuation_line() -> None:
    first = _model(".model sum summer(in_gain=[1 1])")
    assert isinstance(first.params[0].value, ValueList)
    over = _model(".model sum summer in_gain=[ 1\n+ 2 ] out_gain=1")
    vector = over.params[0].value
    assert isinstance(vector, ValueList) and len(vector.values) == 2
    assert over.params[1].name == "out_gain"


@pytest.mark.parametrize(
    ("text", "value", "kind"),
    [
        (".model m mycm(k=1 ; c\n+ j=[1 2])", "[1 2]", ValueList),
        (".model m mycm k=1 ; c\n+ j=[1 2]", "[1 2]", ValueList),
        ('.model m mycm(k=1 ; c\n+ j="x")', '"x"', Formula),
    ],
)
def test_a_comment_before_a_code_model_value_is_kept(text: str, value: str, kind: type) -> None:
    source = f"title\n{text}\n.end\n"
    model = _model(text)
    assert [param.name for param in model.params] == ["k", "j"]
    second = model.params[1].value
    assert isinstance(second, kind)
    assert source[second.span.start : second.span.end] == value
    assert [source[s.start : s.end] for s in model.trailing_comments] == ["; c"]


@pytest.mark.parametrize(
    ("text", "column", "reason"),
    [
        (".model dm d(is=[1e-14 2e-14])", 16, "on a `d` model"),
        (".model dm d(foo=TRUE)", 17, "a boolean"),
        ('.model dm npn bf=100 file="x"', 27, "a quoted string"),
        (".model sum summer(in_gain=[2.0, 1.0])", 31, "a comma between a vector's values"),
    ],
)
def test_refused_model_values(text: str, column: int, reason: str) -> None:
    error = _reject(text)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


@pytest.mark.parametrize(
    "text", [".model sum summer(in_gain=[])", ".model a gain(x=abc)", ".model a gain(x=[a b])"]
)
def test_malformed_model_values_are_syntax_errors(text: str) -> None:
    assert _reject(text).line == 2


def test_an_osdi_device() -> None:
    item = _items("N1 d g s b bsim l=0.1u w=1u\n+ as=1p m=2")[0]
    assert isinstance(item, OsdiDevice)
    assert [n.name for n in item.nodes] == ["d", "g", "s", "b"]
    assert item.model.model_name == "bsim"
    assert [p.name for p in item.params] == ["l", "w", "as", "m"]
    one = _items("N1 out rmod")[0]
    assert isinstance(one, OsdiDevice) and [n.name for n in one.nodes] == ["out"]


@pytest.mark.parametrize(
    ("line", "column", "reason"),
    [
        ("N1 a b rmod 5", 13, "takes no positional value"),
        ("N1 a b 5 w=1u", 8, "a model name cannot be a number"),
        ("N1 a b rmod off", 13, "takes no flag"),
    ],
)
def test_refused_osdi_lines(line: str, column: int, reason: str) -> None:
    error = _reject(line)
    assert (error.line, error.column) == (2, column)
    assert reason in error.reason


def test_an_osdi_line_needs_a_node_and_a_model() -> None:
    assert _reject("N1 rmod").line == 2
