"""xyce parameter and function scoping in the document layer (X-M1 B3; decision 0027 item 9;
``docs/grammars/xyce/scoping.md``)."""

from __future__ import annotations

from netlistmod import DiagnosticCode, Netlist
from netlistmod.dialects import _XYCE
from netlistmod.model.values import FunctionDefinition


def _netlist(body: str) -> Netlist:
    return Netlist.from_text(f"t\n{body}.END\n", dialect=_XYCE)


def _codes(netlist: Netlist) -> list[tuple[str, str]]:
    return [(d.code.value, d.severity) for d in netlist.diagnostics]


def test_a_repeated_param_resolves_to_the_first_definition() -> None:
    # Xyce 7.10 uses the first (scoping.md S3); the manual says the last (discrepancies.md).
    netlist = _netlist(".param a=1\n.param b={a}\n.param a=2\n")
    (reference,) = netlist.references
    assert reference.kind == "param"
    assert reference.target is netlist.params["a"][0]
    (diagnostic,) = netlist.diagnostics
    assert diagnostic.code is DiagnosticCode.DUPLICATE_DEFINITION
    assert diagnostic.severity == "warning"
    assert "uses the first definition" in diagnostic.message
    assert diagnostic.line == 4


def test_order_does_not_matter() -> None:
    # Parameters and functions may be used before they are defined (scoping.md S4).
    netlist = _netlist(".param b={a+f(1)}\n.param a=1\n.func f(x) {x}\n")
    assert [ref.target is not None for ref in netlist.references] == [True, True]
    assert netlist.diagnostics == ()


def test_param_beats_global_param_whatever_the_order() -> None:
    # scoping.md S5: the `.param` is used, and the `.global_param` reported.
    for body in (".global_param a=1\n.param a=3\n", ".param a=3\n.global_param a=1\n"):
        netlist = _netlist(body + ".param b={a}\n")
        reference = next(ref for ref in netlist.references if ref.name == "a")
        assert reference.target is not None
        assert reference.target.value.text == "3"  # type: ignore[attr-defined]
        (diagnostic,) = netlist.diagnostics
        assert diagnostic.code is DiagnosticCode.DUPLICATE_DEFINITION
        assert "uses the `.param`, not the `.global_param`" in diagnostic.message


def test_a_global_param_is_a_top_level_parameter() -> None:
    netlist = _netlist(".global_param g=1\n.param b={g*2}\n")
    # The `.global_param` assignments follow the `.param` ones in the table (scoping.md S5).
    assert list(netlist.params) == ["b", "g"]
    assert netlist.references[0].target is netlist.params["g"][0]


def test_reserved_words_are_never_references() -> None:
    # scoping.md S7: a definition never masks them, and none can be written.
    netlist = _netlist(".param b={time+freq+temp+vt+gmin+pi+exp+hertz+temper}\n")
    assert netlist.references == ()
    assert netlist.diagnostics == ()


def test_function_calls_are_function_references() -> None:
    netlist = _netlist(".func f(x) {x*a}\n.param a=1 g(y)={y} b={f(1)+g(2)+h(3)+sin(4)+M(5)}\n")
    kinds = [(ref.kind, ref.name, ref.target is not None) for ref in netlist.references]
    # `x` and `y` are arguments, local to their bodies; built-in calls are not references.
    assert kinds == [
        ("param", "a", True),
        ("function", "f", True),
        ("function", "g", True),
        ("function", "h", False),
    ]
    (f, g) = (netlist.references[1].target, netlist.references[2].target)
    assert isinstance(f, FunctionDefinition) and f.name == "f"
    assert isinstance(g, FunctionDefinition) and g.name == "g"
    assert list(netlist.scope()._functions) == ["f", "g"]


def test_a_function_argument_shadows_a_parameter_in_its_body() -> None:
    netlist = _netlist(".param x=1\n.func f(x) {x+1}\n.param b={x}\n")
    assert [(ref.name, ref.span.start) for ref in netlist.references] == [
        ("x", netlist.text.index("{x}") + 1)
    ]


def test_a_repeated_function_is_a_warning() -> None:
    # Xyce stops on it ("Duplicate function definition").
    netlist = _netlist(".func f(x) {x}\n.param F(y)={y}\n")
    (diagnostic,) = netlist.diagnostics
    assert diagnostic.code is DiagnosticCode.DUPLICATE_DEFINITION
    assert diagnostic.severity == "warning"
    assert "function `F` is defined again" in diagnostic.message
    assert "stops with an error" in diagnostic.message


def test_function_names_fold_by_ascii_case() -> None:
    netlist = _netlist(".func Fn(x) {x}\n.param b={FN(1)}\n")
    assert netlist.references[0].target is not None


def test_a_bare_value_is_scanned_from_its_start() -> None:
    netlist = _netlist(".param a=1 b=a*2+c\n")
    spans = [netlist.slice(ref.span) for ref in netlist.references]
    assert spans == ["a", "c"]
    assert _codes(netlist) == [("UNRESOLVED_PARAM", "warning")]


def test_numbers_are_not_value_checked() -> None:
    # RKM_SOLVER_MISMATCH and DIALECT_GATED_SYNTAX are ngspice's.
    assert _netlist(".param a=1k b=2j c=1meg\n").diagnostics == ()
