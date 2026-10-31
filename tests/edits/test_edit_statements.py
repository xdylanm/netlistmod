"""`.param` upserts and `.model` parameters (M6 T4; decision 0007 items 4, 6 and 7)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from netlistmod import DiagnosticCode, Dialect, EditError, Netlist, Placement


def _netlist(text: str) -> Netlist:
    return Netlist.from_text(text, dialect=Dialect.NGSPICE)


Operation = Callable[[Netlist], Netlist]

_CASES: list[tuple[str, str, Operation, str]] = [
    (
        "replace",
        "t\n.param Rx=1k\n.end\n",
        lambda n: n.params.set("Rx", "22k"),
        "t\n.param Rx=22k\n.end\n",
    ),
    (
        "add after title",
        "t\nR1 a 0 {Rx}\n.end\n",
        lambda n: n.params.set("Rx", "22k"),
        "t\n.param Rx=22k\nR1 a 0 {Rx}\n.end\n",
    ),
    (
        "add after last param",
        "t\n.param a=1\nR1 a 0 1k\n.param b=2\n.end\n",
        lambda n: n.params.set("c", "3"),
        "t\n.param a=1\nR1 a 0 1k\n.param b=2\n.param c=3\n.end\n",
    ),
    (
        "effective assignment",
        "t\n.param rx=1k\n.param RX=2k ry=3k\n.end\n",
        lambda n: n.params.set("Rx", "5k"),
        "t\n.param rx=1k\n.param RX=5k ry=3k\n.end\n",
    ),
    (
        "crlf",
        "t\r\nR1 a 0 1k\r\n.end\r\n",
        lambda n: n.params.set("Rx", "1"),
        "t\r\n.param Rx=1\r\nR1 a 0 1k\r\n.end\r\n",
    ),
    (
        "placement before end",
        "t\n.end",
        lambda n: n.params.set("k", "{2*3}", placement=Placement.BEFORE_END),
        "t\n.param k={2*3}\n.end",
    ),
    (
        "string value",
        "t\n.end\n",
        lambda n: n.params.set("s", '"text"'),
        't\n.param s="text"\n.end\n',
    ),
    (
        "body add at start",
        "t\n.subckt amp a b\nR1 a b {k}\n.ends\n.end\n",
        lambda n: n.params.set("k", "2", scope=("amp",), in_definition=True),
        "t\n.subckt amp a b\n.param k=2\nR1 a b {k}\n.ends\n.end\n",
    ),
    (
        "body add after body param",
        "t\n.subckt amp a b\n  .param j=1\nR1 a b {k}\n.ends\n.end\n",
        lambda n: n.params.set("k", "2", scope=("amp",), in_definition=True),
        "t\n.subckt amp a b\n  .param j=1\n.param k=2\nR1 a b {k}\n.ends\n.end\n",
    ),
    (
        "body default",
        "t\n.subckt amp a b k=1\nR1 a b {k}\n.ends\n.end\n",
        lambda n: n.params.set("K", "2", scope=("amp",), in_definition=True),
        "t\n.subckt amp a b k=2\nR1 a b {k}\n.ends\n.end\n",
    ),
    (
        "model param add",
        "t\n.model dm d(is=1e-14)\n.end\n",
        lambda n: n.set_model_param("dm", "n", "1.5"),
        "t\n.model dm d(is=1e-14 n=1.5)\n.end\n",
    ),
    (
        "model param replace",
        "t\n.model dm d(is=1e-14, n=1)\n.end\n",
        lambda n: n.set_model_param("DM", "N", "1.5"),
        "t\n.model dm d(is=1e-14, n=1.5)\n.end\n",
    ),
    (
        "model param without parentheses",
        "t\n.model dm d\n.end\n",
        lambda n: n.set_model_param("dm", "n", "1.5"),
        "t\n.model dm d n=1.5\n.end\n",
    ),
    (
        "model param in body",
        "t\n.subckt amp a b\nD1 a b dm\n.model dm d is=1\n.ends\n.end\n",
        lambda n: n.set_model_param("dm", "rs", "2", scope=("amp",), in_definition=True),
        "t\n.subckt amp a b\nD1 a b dm\n.model dm d is=1 rs=2\n.ends\n.end\n",
    ),
]


@pytest.mark.parametrize(
    ("text", "operation", "expected"),
    [case[1:] for case in _CASES],
    ids=[case[0] for case in _CASES],
)
def test_statement_operation(text: str, operation: Operation, expected: str) -> None:
    edited = operation(_netlist(text))
    assert edited.text == expected
    assert operation(edited).text == expected  # idempotent


def test_params_is_still_the_read_only_table() -> None:
    netlist = _netlist("t\n.param Rx=1k\n.end\n")
    assert list(netlist.params) == ["rx"]
    assert len(netlist.params) == 1
    assert netlist.params["rx"][0].value.text == "1k"


def test_read_back_after_adding_a_param() -> None:
    netlist = _netlist("t\nR1 a 0 {Rx}\n.end\n")
    assert [d.code for d in netlist.diagnostics] == [DiagnosticCode.UNRESOLVED_PARAM]
    edited = netlist.params.set("Rx", "22k")
    assert len(edited.references_to_param("rx")) == 1
    assert edited.diagnostics == ()


def test_earlier_repeats_are_left_as_they_are() -> None:
    edited = _netlist("t\n.param a=1\n.param a=2\n.end\n").params.set("a", "3")
    assert edited.text == "t\n.param a=1\n.param a=3\n.end\n"
    assert [d.code for d in edited.diagnostics] == [DiagnosticCode.DUPLICATE_DEFINITION]


@pytest.mark.parametrize(
    ("text", "operation", "message"),
    [
        ("t\n.end\n", lambda n: n.params.set("Rx", "1k+a"), "braces"),
        ("t\n.end\n", lambda n: n.params.set("time", "1"), "reserved name"),
        ("t\n.end\n", lambda n: n.params.set("Rx", "1k 2k"), "does not parse"),
        (
            "t\n.subckt amp a b\n.ends\n.end\n",
            lambda n: n.params.set("k", "1", scope=("amp",)),
            "in_definition=True",
        ),
        (
            "t\n.subckt amp a b\n.ends\n.end\n",
            lambda n: n.params.set(
                "k", "1", scope=("amp",), in_definition=True, placement=Placement.BEFORE_END
            ),
            "does not apply inside subcircuit `amp`",
        ),
        ("t\n.end\n", lambda n: n.set_model_param("dm", "n", "1"), "no model `dm` in top level"),
        (
            "t\n.model dm d()\n.end\n",
            lambda n: n.set_model_param("dm", "n", "1"),
            "empty parentheses",
        ),
        (
            "t\n.model dm d is=1 is=2\n.end\n",
            lambda n: n.set_model_param("dm", "is", "3"),
            "repeated",
        ),
        (
            "t\n.subckt amp a b\n.model dm d\n.ends\n.end\n",
            lambda n: n.set_model_param("dm", "is", "3"),
            "no model `dm` in top level",
        ),
    ],
)
def test_statement_operation_errors(text: str, operation: Operation, message: str) -> None:
    with pytest.raises(EditError, match=message):
        operation(_netlist(text))


def test_a_body_param_can_be_placed_by_a_body_anchor() -> None:
    netlist = _netlist("t\n.subckt amp a b\nR1 a b {k}\nR2 b 0 1\n.ends\n.end\n")
    body = netlist.scope(("amp",)).lines
    scope = {"scope": ("amp",), "in_definition": True}
    before = netlist.params.set("k", "2", placement=Placement.before(body[1]), **scope)
    after = netlist.params.set("k", "2", placement=Placement.after(body[0]), **scope)
    expected = "t\n.subckt amp a b\nR1 a b {k}\n.param k=2\nR2 b 0 1\n.ends\n.end\n"
    assert before.text == after.text == expected
    with pytest.raises(EditError, match="not a line of the body of subcircuit `amp`"):
        netlist.params.set("k", "2", placement=Placement.after(netlist.lines[0]), **scope)
