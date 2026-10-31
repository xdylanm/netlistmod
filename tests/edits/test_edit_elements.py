"""Element operations (M6 T3; decision 0007 items 2, 3 and 5; m6-edits.md §2)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from netlistmod import DiagnosticCode, Dialect, EditError, Netlist


def _netlist(body: str, *, rkm: bool = False) -> Netlist:
    return Netlist.from_text(f"title\n{body}\n.end\n", dialect=Dialect.NGSPICE, rkm=rkm)


def _body(netlist: Netlist) -> str:
    return netlist.text.removeprefix("title\n").removesuffix("\n.end\n")


Operation = Callable[[Netlist], Netlist]

_CASES: list[tuple[str, str, Operation, str]] = [
    ("value", "R22 a b 1k", lambda n: n.set_value("R22", "2.2k"), "R22 a b 2.2k"),
    ("keyword formula", "R1 a b r=10k", lambda n: n.set_formula("R1", "Rx"), "R1 a b r={Rx}"),
    (
        "value after nodes",
        "R1 a b rmod\n.model rmod r",
        lambda n: n.set_value("R1", "1k"),
        "R1 a b 1k rmod\n.model rmod r",
    ),
    ("capacitor", "C1 a 0 1p", lambda n: n.set_value("c1", "2p"), "C1 a 0 2p"),
    (
        "inductor keyword",
        "L1 a 0 inductance=1u",
        lambda n: n.set_param("L1", "INDUCTANCE", "2u"),
        "L1 a 0 inductance=2u",
    ),
    ("param", "R1 a b 1k", lambda n: n.set_param("R1", "tc1", "2m"), "R1 a b 1k tc1=2m"),
    (
        "param before comment",
        "R1 a b 1k ; note",
        lambda n: n.set_param("R1", "tc1", "2m"),
        "R1 a b 1k tc1=2m ; note",
    ),
    (
        "param on continuation",
        "R1 a b 1k\n+ tc1=1m",
        lambda n: n.set_param("R1", "TC1", "2m"),
        "R1 a b 1k\n+ tc1=2m",
    ),
    (
        "param after last field on continuation",
        "R1 a b 1k ; first\n+ tc1=1m $ second",
        lambda n: n.set_param("R1", "tc2", "0"),
        "R1 a b 1k ; first\n+ tc1=1m tc2=0 $ second",
    ),
    (
        "param after backslash continuation",
        "R1 a b \\\\\n1k",
        lambda n: n.set_param("R1", "tc1", "1m"),
        "R1 a b \\\\\n1k tc1=1m",
    ),
    (
        "diode param after flag",
        "D1 a k dm off\n.model dm d",
        lambda n: n.set_param("D1", "area", "2"),
        "D1 a k dm off area=2\n.model dm d",
    ),
    (
        "model",
        "D1 a k dm\n.model dm d\n.model dm2 D",
        lambda n: n.set_model("D1", "dm2"),
        "D1 a k dm2\n.model dm d\n.model dm2 D",
    ),
    (
        "resistor model",
        "R1 a b 1k rm\n.model rm r\n.model rm2 R",
        lambda n: n.set_model("R1", "RM2"),
        "R1 a b 1k RM2\n.model rm r\n.model rm2 R",
    ),
    ("dc", "V1 in 0 DC 3", lambda n: n.set_dc("V1", "5"), "V1 in 0 DC 5"),
    ("dc add", "V1 in 0 AC 1", lambda n: n.set_dc("V1", "2"), "V1 in 0 DC 2 AC 1"),
    ("value on source", "I1 in 0 3", lambda n: n.set_value("I1", "4"), "I1 in 0 4"),
    ("ac add", "V1 in 0 DC 3", lambda n: n.set_ac("V1", "1"), "V1 in 0 DC 3 AC 1"),
    ("ac add phase", "V1 in 0", lambda n: n.set_ac("V1", "1", "45"), "V1 in 0 AC 1 45"),
    ("ac replace", "V1 in 0 ac 1 10", lambda n: n.set_ac("V1", "2"), "V1 in 0 ac 2 10"),
    ("ac phase", "V1 in 0 AC 1 10", lambda n: n.set_ac("V1", "2", "90"), "V1 in 0 AC 2 90"),
    ("ac phase add", "V1 in 0 AC 1", lambda n: n.set_ac("V1", "1", "90"), "V1 in 0 AC 1 90"),
    (
        "coupling",
        "L1 a 0 1u\nL2 b 0 1u\nK1 L1 L2 0.9",
        lambda n: n.set_coupling("K1", "0.95"),
        "L1 a 0 1u\nL2 b 0 1u\nK1 L1 L2 0.95",
    ),
    (
        "instance param",
        "X1 in out div\n.subckt div a b r2=1k\nR1 a b {r2}\n.ends",
        lambda n: n.set_instance_param("X1", "r2", "5k"),
        "X1 in out div r2=5k\n.subckt div a b r2=1k\nR1 a b {r2}\n.ends",
    ),
    (
        "instance param replace and string",
        'X1 in out div r2=1k\n.subckt div a b r2=1k s="x"\nR1 a b {r2}\n.ends',
        lambda n: n.set_instance_param("X1", "s", '"y"'),
        'X1 in out div r2=1k s="y"\n.subckt div a b r2=1k s="x"\nR1 a b {r2}\n.ends',
    ),
    (
        "body edit",
        ".subckt amp a b\nR1 a b 1k\n.ends",
        lambda n: n.set_value("R1", "5k", scope=("AMP",), in_definition=True),
        ".subckt amp a b\nR1 a b 5k\n.ends",
    ),
    (
        "add a model after the value",
        "R1 a b 1k ; c\n.model rm r rsh=100",
        lambda n: n.set_model("R1", "rm"),
        "R1 a b 1k rm ; c\n.model rm r rsh=100",
    ),
    (
        "add a model before parameters",
        "C1 a 0 1p m=2\n.model cm c",
        lambda n: n.set_model("C1", "cm"),
        "C1 a 0 1p cm m=2\n.model cm c",
    ),
]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("R1 a b 1k rm l=20u w=1u", "R1 a b  rm l=20u w=1u"),
        ("R1 a b\n+ 1k rm", "R1 a b\n+  rm"),
        ("C1 a b {c0} cm\n.param c0=1p", "C1 a b  cm\n.param c0=1p"),
    ],
)
def test_remove_value(body: str, expected: str) -> None:
    models = "\n.model rm r rsh=100\n.model cm c"
    edited = _netlist(body + models).remove_value(body[:2])
    assert _body(edited) == expected + models
    with pytest.raises(EditError, match="no value to remove"):
        edited.remove_value(body[:2])


def test_switch_a_resistor_to_its_semiconductor_model() -> None:
    netlist = _netlist("R2 out 0 1k\n.model rmod r rsh=100")
    with netlist.batch() as batch:
        batch.set_model("R2", "rmod")
        batch.set_param("R2", "l", "20u")
        batch.set_param("R2", "w", "1u")
    edited = batch.result.remove_value("R2")
    assert _body(edited) == "R2 out 0  rmod l=20u w=1u\n.model rmod r rsh=100"
    back = edited.set_value("R2", "1k")
    assert _body(back) == "R2 out 0 1k  rmod l=20u w=1u\n.model rmod r rsh=100"


@pytest.mark.parametrize(
    ("body", "operation", "expected"),
    [case[1:] for case in _CASES],
    ids=[case[0] for case in _CASES],
)
def test_element_operation(body: str, operation: Operation, expected: str) -> None:
    netlist = _netlist(body)
    edited = operation(netlist)
    assert _body(edited) == expected
    assert _body(netlist) == body  # the original is unchanged
    assert edited.signature() == netlist.signature()
    assert _body(operation(edited)) == expected  # idempotent


def test_read_back_after_an_edit() -> None:
    edited = _netlist("R1 a b 1k").set_formula("R1", "Rx*2")
    value = edited.element("R1").value
    assert value is not None and value.text == "Rx*2"
    assert [reference.name for reference in edited.references] == ["Rx"]


def test_rkm_values_need_the_option() -> None:
    with pytest.raises(EditError, match="rkm=True"):
        _netlist("R1 a b 1k").set_value("R1", "2k7")
    edited = _netlist("R1 a b 1k", rkm=True).set_value("R1", "2k7")
    assert _body(edited) == "R1 a b 2k7"


def test_external_model_needs_an_include_and_the_flag() -> None:
    body = "D1 a k dm\n.model dm d\n.include m.lib"
    with pytest.raises(EditError, match="allow_external=True"):
        _netlist(body).set_model("D1", "dm2")
    edited = _netlist(body).set_model("D1", "dm2", allow_external=True)
    assert _body(edited).startswith("D1 a k dm2\n")
    unresolved = [d for d in edited.diagnostics if d.code is DiagnosticCode.UNRESOLVED_MODEL]
    assert [d.severity for d in unresolved] == ["info"]
    with pytest.raises(EditError, match="is not defined \\(searched: top level\\)$"):
        _netlist("D1 a k dm\n.model dm d").set_model("D1", "dm2", allow_external=True)


def test_set_model_resolves_through_enclosing_scopes() -> None:
    body = ".model dm2 d\n.subckt amp a b\nD1 a b dm\n.model dm d\n.ends"
    edited = _netlist(body).set_model("D1", "dm2", scope=("amp",), in_definition=True)
    assert "D1 a b dm2\n" in edited.text


@pytest.mark.parametrize(
    ("body", "operation", "message"),
    [
        (
            "D1 a k dm\n.model dm d\n.model dm2 npn",
            lambda n: n.set_model("D1", "dm2"),
            "type `npn`",
        ),
        ("R1 a b r=1k\n.model rm r", lambda n: n.set_model("R1", "rm"), "takes no model"),
        ("R1 a b 1k\n.model rm c", lambda n: n.set_model("R1", "rm"), "type `c`"),
        ("R1 a b 1k", lambda n: n.remove_value("R1"), "has no model, so it needs its value"),
        ("D1 a k dm\n.model dm d", lambda n: n.remove_value("D1"), "only R, C and L"),
        ("V1 a 0 1", lambda n: n.set_model("V1", "x"), "voltage source line and has no model"),
        ("D1 a k dm\n.model dm d", lambda n: n.set_value("D1", "1"), "diode line and has no value"),
        ("X1 a b s\n.subckt s p q\n.ends", lambda n: n.set_value("X1", "1"), "subcircuit call"),
        ("L1 a 0 1u\nL2 b 0 1u\nK1 L1 L2 0.9", lambda n: n.set_value("K1", "1"), "set_coupling"),
        ("V1 a 0 AC 1", lambda n: n.set_value("V1", "1"), "use set_dc"),
        ("R1 a b 1k", lambda n: n.set_param("R1", "r", "2k"), "use set_value"),
        (
            "X1 a b s\n.subckt s p q\n.ends",
            lambda n: n.set_param("X1", "k", "1"),
            "set_instance_param",
        ),
        ("V1 a 0 1", lambda n: n.set_param("V1", "k", "1"), "takes no parameters"),
        ("R1 a b 1k", lambda n: n.set_instance_param("R1", "k", "1"), "use set_param"),
        ("R1 a b 1k tc1=1 tc1=2", lambda n: n.set_param("R1", "tc1", "3"), "repeated"),
        ("R1 a b 1k", lambda n: n.set_dc("R1", "1"), "not an independent source"),
        ("R1 a b 1k", lambda n: n.set_ac("R1", "1"), "not an independent source"),
        ("R1 a b 1k", lambda n: n.set_coupling("R1", "1"), "not a coupling"),
        ("R1 a b 1k", lambda n: n.set_value("R9", "1"), "no element `R9` in top level"),
        ("R1 a b 1k\nr1 b 0 1k", lambda n: n.set_value("R1", "1"), "repeated"),
        ("R1 a b 1k", lambda n: n.set_value("R1", "1", scope=("x",)), "no subcircuit"),
        (
            ".subckt amp a b\nR1 a b 1k\n.ends",
            lambda n: n.set_value("R1", "5k", scope=("amp",)),
            "in_definition=True",
        ),
    ],
)
def test_element_operation_errors(body: str, operation: Operation, message: str) -> None:
    with pytest.raises(EditError, match=message):
        operation(_netlist(body))
