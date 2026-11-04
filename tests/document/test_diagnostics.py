"""Diagnostics as data (M5 T6; decision 0006 items 7 and 8)."""

from __future__ import annotations

import pytest

from netlistmod import Diagnostic, DiagnosticCode, Netlist
from tests.support.dialects import current_dialect

C = DiagnosticCode


# Cases whose text only ngspice reads (tests/support/dialects.py).
NGSPICE_ONLY_CASES = {
    "test_behaviour_table": [
        "R1 a 0 1k rm",
        "C1 a 0 cm",
        "R1 in out {rx}",
        ".param rx=1k",
        ".print tran",
    ],
}


def _netlist(body: str, **options: bool) -> Netlist:
    return Netlist.from_text(f"title\n{body}\n.end\n", dialect=current_dialect(), **options)


def _codes(body: str, **options: bool) -> list[tuple[DiagnosticCode, str, str]]:
    netlist = _netlist(body, **options)
    return [(d.code, d.severity, netlist.slice(d.span)) for d in netlist.diagnostics]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("V1 IN 0 DC 3\nR1 in OUT 1k\nR2 out 0 1k", []),
        ("R1 a b 1\nr1 a b 2", [(C.DUPLICATE_ELEMENT, "warning", "r1")]),
        ("D1 a 0 DMOD\n.model dmod d", []),
        ("D1 a 0 qm\n.model qm npn", [(C.MODEL_TYPE_MISMATCH, "warning", "qm")]),
        ("R1 a 0 1k rm\n.model rm C", [(C.MODEL_TYPE_MISMATCH, "warning", "rm")]),
        ("C1 a 0 cm\n.model cm c\nL1 a 0 lm\n.model lm L\nR1 a 0 rm\n.model rm R", []),
        (
            "D1 a 0 dm\n.subckt s p\nD1 p 0 dm\n.model dm npn\n.ends\n.model dm d",
            [(C.MODEL_TYPE_MISMATCH, "warning", "dm")],
        ),
        ("D1 a 0 dm", [(C.UNRESOLVED_MODEL, "warning", "dm")]),
        ("D1 a 0 dm\n.include models.lib", [(C.UNRESOLVED_MODEL, "info", "dm")]),
        ("X1 in out DIV\n.subckt div a b\nR1 a b 1\n.ends", []),
        (
            "X1 in out extra div\n.subckt div a b\nR1 a b 1\n.ends",
            [(C.SUBCKT_PORT_MISMATCH, "warning", "div")],
        ),
        ("X1 in out nope", [(C.UNRESOLVED_SUBCKT, "warning", "nope")]),
        (
            "R1 in out {rx}\n.param rx=3k",
            [(C.PARAM_USED_BEFORE_DEFINITION, "warning", "rx")],
        ),
        (".param rx=1k\n.param rx=3k", [(C.DUPLICATE_DEFINITION, "info", "rx")]),
        (".model m d\n.model M d", [(C.DUPLICATE_DEFINITION, "warning", "M")]),
        (
            ".subckt s a\n.ends\n.subckt S a\n.ends",
            [(C.DUPLICATE_DEFINITION, "warning", "S")],
        ),
        (
            ".subckt div a b\n.model dm d\n.ends\nD2 out 0 dm",
            [(C.UNRESOLVED_MODEL, "warning", "dm")],
        ),
        ("R1 a b {missing}", [(C.UNRESOLVED_PARAM, "warning", "missing")]),
        ("R1 a b {V(a)*2+gain}", [(C.UNRESOLVED_PARAM, "warning", "gain")]),
        ("L1 a 0 1\nL2 b 0 1\nk1 l1 L2 0.9", []),
        ("L1 a 0 1\nK1 L1 L9 0.9", [(C.UNRESOLVED_ELEMENT, "warning", "L9")]),
        (".dc VIN 0 5 0.1", [(C.UNRESOLVED_ELEMENT, "warning", "VIN")]),
        ("VIN a 0 1\n.dc VIN 0 5 0.1\n.dc TEMP -15 75 5", []),
        (".save i(vx)", [(C.UNRESOLVED_ELEMENT, "warning", "vx")]),
        (".subckt div a b\n.ends other", [(C.ENDS_NAME_MISMATCH, "info", "other")]),
        (".subckt div a b\n.ends DIV", []),
        (".print tran v(1)", [(C.UNTYPED_DIRECTIVE_PRESERVED, "info", ".print")]),
        (".lib x.lib sect\nX1 a b far", [(C.UNRESOLVED_SUBCKT, "info", "far")]),
    ],
)
def test_behaviour_table(body: str, expected: list[tuple[DiagnosticCode, str, str]]) -> None:
    assert _codes(body) == expected


@pytest.mark.ngspice_only
@pytest.mark.parametrize(
    ("body", "expected"),
    [
        # A body is expanded where it is called, so an outer .param later in the file is fine.
        (".subckt div a b\nR1 a b {rx}\n.ends\n.param rx=1k\nX1 in out div", []),
        # Within one scope, order still counts: the body's own .param after its use.
        (
            ".subckt div a b\nR1 a b {k}\n.param k=1k\n.ends\nX1 in out div",
            [(C.PARAM_USED_BEFORE_DEFINITION, "warning", "k")],
        ),
        # The top-level case is unchanged.
        ("R1 in out {rx}\n.param rx=3k", [(C.PARAM_USED_BEFORE_DEFINITION, "warning", "rx")]),
        # A nested definition using its parent's .param, defined after the nested one.
        (
            ".subckt outer a b\n.subckt inner p q\nR1 p q {k}\n.ends\n.param k=1k\n"
            "X1 a b inner\n.ends\nX2 in out outer",
            [],
        ),
    ],
)
def test_used_before_definition_is_judged_within_one_scope(
    body: str, expected: list[tuple[DiagnosticCode, str, str]]
) -> None:
    assert _codes(body) == expected


@pytest.mark.ngspice_only
def test_rkm_values_are_gated_syntax_and_some_are_read_differently() -> None:
    assert _codes("R1 a b 1M0\nR2 a b 2k7\nC1 a 0 4F7", rkm=True) == [
        (C.DIALECT_GATED_SYNTAX, "info", "1M0"),
        (C.RKM_SOLVER_MISMATCH, "warning", "1M0"),
        (C.DIALECT_GATED_SYNTAX, "info", "2k7"),
        (C.DIALECT_GATED_SYNTAX, "info", "4F7"),
        (C.RKM_SOLVER_MISMATCH, "warning", "4F7"),
    ]


@pytest.mark.ngspice_only
def test_rkm_values_inside_a_body_are_reported_once() -> None:
    assert _codes(".subckt d a b\nR1 a b 2k7\n.ends", rkm=True) == [
        (C.DIALECT_GATED_SYNTAX, "info", "2k7")
    ]


def test_include_in_an_enclosing_scope_softens_a_nested_unresolved_reference() -> None:
    netlist = _netlist(".include m.lib\n.subckt d a b\nD1 a b dx\nK1 L1 L2 1\n.ends")
    model, inductor, other = netlist.diagnostics
    assert (model.code, model.severity) == (C.UNRESOLVED_MODEL, "info")
    assert "searched: subcircuit `d`, top level" in model.message
    assert "may be defined in an `.include` or `.lib` file" in model.message
    # Element references are searched in their own scope only, which has no include.
    assert (inductor.code, inductor.severity) == (C.UNRESOLVED_ELEMENT, "warning")
    assert "searched: subcircuit `d`)" in inductor.message
    assert other.code == C.UNRESOLVED_ELEMENT


@pytest.mark.ngspice_only
def test_diagnostics_carry_positions_and_are_in_source_order() -> None:
    netlist = _netlist(".print x\nR1 a b {q}\nR1 a b 1")
    assert [(d.line, d.column, d.code) for d in netlist.diagnostics] == [
        (2, 1, C.UNTYPED_DIRECTIVE_PRESERVED),
        (3, 9, C.UNRESOLVED_PARAM),
        (4, 1, C.DUPLICATE_ELEMENT),
    ]
    assert all(isinstance(d, Diagnostic) for d in netlist.diagnostics)
    assert netlist.diagnostics is netlist.diagnostics
    assert C.UNRESOLVED_MODEL == "UNRESOLVED_MODEL"


def test_messages_name_the_construct_and_the_scopes_searched() -> None:
    netlist = _netlist(".subckt amp a b\n.subckt inner x y\nR1 x y {g}\n.ends\n.ends")
    (diagnostic,) = netlist.diagnostics
    assert diagnostic.message == (
        "parameter `g` is not defined (searched: subcircuit `amp > inner`, subcircuit `amp`, "
        "top level)"
    )
    duplicate = _netlist("R1 a b 1\nR1 a b 2").diagnostics[0]
    assert "element `R1` repeats a designator in top level" in duplicate.message
    mismatch = _netlist("X1 a b c s\n.subckt s p q\n.ends").diagnostics[0]
    assert mismatch.message == "`X1` connects 3 nodes, but subcircuit `s` has 2 ports"
