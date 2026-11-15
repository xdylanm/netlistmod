"""Forbidden and misused operations (M6 T10, T6 tier; architecture §7.3).

Topology has no setter, so each forbidden operation is attempted with a crafted plan through
``apply(plan)``, which must raise ``TopologyViolation`` and return nothing. API misuse raises
``TopologyError`` or ``EditError`` before any plan is applied.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path

import pytest

from netlistmod import (
    Edit,
    EditError,
    Line,
    Netlist,
    OpaqueBlock,
    OpaqueStatement,
    Placement,
    Resistor,
    Span,
    SubcktDefinition,
    TopologyError,
    TopologyViolation,
)
from tests.support.dialects import current_dialect, is_ltspice

_TEXT = (
    "negative\n"
    ".global vcc\n"
    ".param rx=1k\n"
    "V1 in 0 DC 3\n"
    "R1 in out {rx}\n"
    "R2 out 0 1k\n"
    "L1 a 0 1u\n"
    "L2 b 0 1u\n"
    "K1 L1 L2 0.9\n"
    "X1 in out div\n"
    ".subckt div p q\n"
    "Ra p q 1k\n"
    ".ends\n"
    ".include models.lib\n"
    ".control\n"
    "run\n"
    ".endc\n"
    ".if (1)\n"
    "Rc out 0 1k\n"
    ".endif\n"
    ".op\n"
    ".end\n"
)

_NGSPICE_BLOCKS = ".control\nrun\n.endc\n.if (1)\nRc out 0 1k\n.endif\n"


# Cases whose text only ngspice reads (tests/support/dialects.py).
NGSPICE_ONLY_CASES = {
    "test_crafted_plans_that_change_topology_raise": [".control", ".if"],
    "test_whole_opaque_items_may_be_added_or_removed": [
        ".control",
        ".if",
        "conditional",
        "block after",
    ],
}


def _netlist() -> Netlist:
    # LTspice has no .control or .if block.
    text = _TEXT.replace(_NGSPICE_BLOCKS, "") if is_ltspice() else _TEXT
    return Netlist.from_text(text, dialect=current_dialect())


def _span(netlist: Netlist, text: str, occurrence: int = 0) -> Span:
    """The span of the ``occurrence``-th ``text`` in the fixture (test-side lookup only)."""
    start = -1
    for _ in range(occurrence + 1):
        start = netlist.text.index(text, start + 1)
    return Span(start, start + len(text))


def _line(netlist: Netlist, kind: type, index: int = 0) -> Span:
    return netlist.lines.find_all(kind, recursive=True)[index].span


def _point(netlist: Netlist, text: str) -> Span:
    start = _span(netlist, text).start
    return Span(start, start)


Crafted = Callable[[Netlist], list[Edit]]

_CRAFTED: list[tuple[str, Crafted]] = [
    ("add an element", lambda n: [Edit(_point(n, ".op\n"), "R9 out 0 1k\n")]),
    ("remove an element", lambda n: [Edit(_line(n, Resistor, 1), "")]),
    (
        "reorder elements",
        lambda n: [
            Edit(_line(n, Resistor, 0), n.slice(_line(n, Resistor, 1))),
            Edit(_line(n, Resistor, 1), n.slice(_line(n, Resistor, 0))),
        ],
    ),
    ("change a node", lambda n: [Edit(n.element("R2").nodes[0].span, "mid")]),
    ("change a node's case", lambda n: [Edit(n.element("R2").nodes[0].span, "OUT")]),
    ("change a type", lambda n: [Edit(n.element("R2").designator_span, "C2")]),
    ("change a designator", lambda n: [Edit(n.element("R2").designator_span, "R3")]),
    (
        "rename a net",
        lambda n: [
            Edit(n.element("R1").nodes[1].span, "o"),
            Edit(n.element("R2").nodes[0].span, "o"),
        ],
    ),
    ("change a coupling target", lambda n: [Edit(_span(n, "L2 0.9"), "L1 0.9")]),
    ("change a subcircuit call", lambda n: [Edit(_span(n, "div\n.subckt"), "dv\n.subckt")]),
    ("change subcircuit ports", lambda n: [Edit(_span(n, "p q\nRa"), "p q r\nRa")]),
    ("remove a subcircuit", lambda n: [Edit(_line(n, SubcktDefinition), "")]),
    (
        "add a subcircuit",
        lambda n: [Edit(_point(n, ".op\n"), ".subckt extra a\nRz a 0 1\n.ends\n")],
    ),
    ("remove .global", lambda n: [Edit(_span(n, ".global vcc\n"), "")]),
    ("edit a .control block", lambda n: [Edit(_span(n, "run"), "tran 1u 1m")]),
    ("insert into a .control block", lambda n: [Edit(_point(n, "run"), "op\n")]),
    ("cut a .control block in half", lambda n: [Edit(_span(n, ".control\nrun\n"), "")]),
    ("change an .include", lambda n: [Edit(_span(n, "models.lib"), "other.lib")]),
    ("edit inside an .if block", lambda n: [Edit(_span(n, "Rc out 0 1k"), "Rc out 0 2k")]),
]

# Whole opaque items may be added, removed or replaced (review round 1): what they contain is
# not verified (architecture §7.8), so these are allowed even though they may change the circuit.
_WHOLE_OPAQUE: list[tuple[str, Crafted]] = [
    ("remove a .control block", lambda n: [Edit(_line(n, OpaqueBlock), "")]),
    ("remove an .if block", lambda n: [Edit(_line(n, OpaqueBlock, 1), "")]),
    ("remove an .include", lambda n: [Edit(_line(n, OpaqueStatement), "")]),
    ("add an .include", lambda n: [Edit(_point(n, ".op\n"), ".include harness.cir\n")]),
    ("add a .lib", lambda n: [Edit(_point(n, ".op\n"), ".lib models.lib tt\n")]),
    (
        "add a conditional block",
        lambda n: [Edit(_point(n, ".op\n"), ".if (1)\nR9 out 0 1k\n.endif\n")],
    ),
    (
        "replace a .control block",
        lambda n: [Edit(_line(n, OpaqueBlock), ".control\ntran 1u 1m\n.endc\n")],
    ),
    (
        "remove a directive and the block after it",
        lambda n: [Edit(_line(n, OpaqueStatement).hull(_line(n, OpaqueBlock)), "")],
    ),
]


@pytest.mark.parametrize(
    "craft", [case[1] for case in _CRAFTED], ids=[case[0] for case in _CRAFTED]
)
def test_crafted_plans_that_change_topology_raise(craft: Crafted, tmp_path: Path) -> None:
    netlist = _netlist()
    with pytest.raises(TopologyViolation, match="nothing was written"):
        netlist.apply(craft(netlist))
    with pytest.raises(TopologyViolation):
        with netlist.batch() as batch:
            batch.set_dc("V1", "5")
            batch._edits.extend(craft(netlist))
    assert netlist.text == _netlist().text
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "craft", [case[1] for case in _WHOLE_OPAQUE], ids=[case[0] for case in _WHOLE_OPAQUE]
)
def test_whole_opaque_items_may_be_added_or_removed(craft: Crafted) -> None:
    netlist = _netlist()
    edited = netlist.apply(craft(netlist))
    assert edited.signature() == netlist.signature()
    assert edited.text != netlist.text


Misuse = Callable[[Netlist], object]

_TOPOLOGY_ERRORS: list[tuple[str, Misuse]] = [
    ("replace an element line", lambda n: n.directives.replace(n.lines.find(Resistor), ".op")),
    ("remove an element line", lambda n: n.directives.remove(n.lines.find(Resistor))),
    ("add an element as a directive", lambda n: n.directives.add("R9 a 0 1k")),
    ("add an element as a list", lambda n: n.directives.add(["R9 a 0", "+ 1k"])),
    ("add a .subckt as a directive", lambda n: n.directives.add(".subckt s a\n.ends")),
    ("remove .global", lambda n: n.directives.remove(n.lines[1])),
    ("remove a subcircuit", lambda n: n.directives.remove(n.lines.find(SubcktDefinition))),
]


@pytest.mark.parametrize(
    "misuse", [c[1] for c in _TOPOLOGY_ERRORS], ids=[c[0] for c in _TOPOLOGY_ERRORS]
)
def test_directive_api_rejects_topology(misuse: Misuse) -> None:
    with pytest.raises(TopologyError):
        misuse(_netlist())


_EDIT_ERRORS: list[tuple[str, Misuse, str]] = [
    ("set_value on a diode", lambda n: _diode(n).set_value("D1", "1"), "no value slot"),
    ("set_model on a source", lambda n: n.set_model("V1", "dm"), "has no model"),
    (
        "unresolved model",
        lambda n: _diode(n, ".model dm d").set_model("D1", "nope"),
        "allow_external",
    ),
    (
        "wrong model type",
        lambda n: _diode(n, ".model dm d\n.model q npn").set_model("D1", "q"),
        "type `npn`",
    ),
    (
        "scope without in_definition",
        lambda n: n.set_value("Ra", "2k", scope=("div",)),
        "in_definition",
    ),
    (
        "ambiguous directives.set",
        lambda n: n.directives.add(".op").directives.set(".op"),
        "ambiguous",
    ),
    (
        "stale handle",
        lambda n: n.set_value("R2", "2k").directives.remove(n.lines[-2]),
        "does not belong",
    ),
    ("overlapping edits", lambda n: _overlap(n), "overlapping"),
    ("anchor in another netlist", lambda n: _foreign_anchor(n), "not a line of the top level"),
]


def _diode(netlist: Netlist, models: str = "") -> Netlist:
    text = netlist.text.replace(
        ".op\n", f"D1 out 0 dm\n{models}\n.op\n" if models else "D1 out 0 dm\n.op\n"
    )
    return Netlist.from_text(text, dialect=current_dialect())


def _overlap(netlist: Netlist) -> object:
    with netlist.batch() as batch:
        batch.set_value("R2", "2k")
        batch.set_formula("R2", "rx")
    return batch.result


def _foreign_anchor(netlist: Netlist) -> object:
    other = _netlist()
    return netlist.directives.add(".save v(out)", placement=Placement.before(other.lines[-1]))


def _body_line(netlist: Netlist) -> Line:
    line = netlist.lines.find(SubcktDefinition)
    assert line is not None and line.body is not None
    return line.body[0]


def test_adding_a_model_says_there_is_no_api_for_it() -> None:
    with pytest.raises(EditError) as captured:
        _netlist().directives.add(".model d1 D")
    assert "a `.model` line cannot be added" in str(captured.value)
    assert "set_model_param edits an existing one" in str(captured.value)
    assert "params.set" not in str(captured.value)


def test_a_body_line_as_a_directive_anchor_is_named_as_such() -> None:
    netlist = _netlist()
    with pytest.raises(EditError) as captured:
        netlist.directives.add(".op", placement=Placement.after(_body_line(netlist)))
    assert "is inside subcircuit `div`" in str(captured.value)
    assert "go to the top level" in str(captured.value)
    assert "look the line up again" not in str(captured.value)


def test_a_stale_body_line_as_an_anchor_says_to_look_it_up_again() -> None:
    netlist = _netlist()
    with pytest.raises(EditError, match="look the line up again"):
        netlist.directives.add(".op", placement=Placement.after(_body_line(_netlist())))


@pytest.mark.parametrize(
    ("misuse", "message"),
    [c[1:] for c in _EDIT_ERRORS],
    ids=[c[0] for c in _EDIT_ERRORS],
)
def test_misuse_is_an_edit_error(misuse: Misuse, message: str) -> None:
    with pytest.raises(EditError, match=message):
        misuse(_netlist())


# --- scope and placement arguments (M20 D2: A1-6, A1-10, A1-14) --------------------------------

_SCOPED = "t\n.subckt amp a b\nR1 a b 1k\n.model dm D\n.ends\nR1 a 0 1k\n.model dm D\n.end\n"

# Every edit method that takes in_definition, with arguments that would otherwise reach it.
_IN_DEFINITION: dict[str, Callable[..., object]] = {
    "set_value": lambda n, **k: n.set_value("R1", "2k", **k),
    "set_formula": lambda n, **k: n.set_formula("R1", "rx", **k),
    "set_param": lambda n, **k: n.set_param("R1", "tc1", "1", **k),
    "set_model": lambda n, **k: n.set_model("R1", "dm", **k),
    "set_expression": lambda n, **k: n.set_expression("R1", "1", **k),
    "set_table": lambda n, **k: n.set_table("R1", [("0", "0"), ("1", "1")], **k),
    "set_poly_coefficients": lambda n, **k: n.set_poly_coefficients("R1", ["0", "1"], **k),
    "set_switch_state": lambda n, **k: n.set_switch_state("R1", "on", **k),
    "remove_value": lambda n, **k: n.remove_value("R1", **k),
    "remove_param": lambda n, **k: n.remove_param("R1", "tc1", **k),
    "remove_model_param": lambda n, **k: n.remove_model_param("dm", "is", **k),
    "set_dc": lambda n, **k: n.set_dc("R1", "1", **k),
    "set_ac": lambda n, **k: n.set_ac("R1", "1", **k),
    "set_stimulus": lambda n, **k: n.set_stimulus("R1", "SIN(0 1 1k)", **k),
    "set_stimulus_arg": lambda n, **k: n.set_stimulus_arg("R1", 0, "1", **k),
    "remove_stimulus": lambda n, **k: n.remove_stimulus("R1", **k),
    "set_coupling": lambda n, **k: n.set_coupling("R1", "1", **k),
    "set_instance_param": lambda n, **k: n.set_instance_param("R1", "k", "1", **k),
    "set_model_param": lambda n, **k: n.set_model_param("dm", "is", "1", **k),
    "params.set": lambda n, **k: n.params.set("k", "1", **k),
}


def test_the_in_definition_cases_cover_every_edit_method() -> None:
    taking = {
        name
        for name, member in inspect.getmembers(Netlist, inspect.isfunction)
        if "in_definition" in inspect.signature(member).parameters
    }
    assert taking | {"params.set"} == set(_IN_DEFINITION)


@pytest.mark.parametrize("edit", list(_IN_DEFINITION.values()), ids=list(_IN_DEFINITION))
def test_in_definition_at_the_top_level_is_an_edit_error(edit: Callable[..., object]) -> None:
    netlist = Netlist.from_text(_SCOPED, dialect=current_dialect())
    with pytest.raises(EditError, match=r"in_definition=True needs a definition scope"):
        edit(netlist, in_definition=True)
    with pytest.raises(EditError, match=r"in_definition=True needs a definition scope"):
        edit(netlist, scope=(), in_definition=True)
    with (
        pytest.raises(EditError, match=r"in_definition=True needs a definition scope"),
        netlist.batch() as batch,
    ):
        edit(batch, in_definition=True)


@pytest.mark.parametrize("edit", list(_IN_DEFINITION.values()), ids=list(_IN_DEFINITION))
def test_a_scope_object_as_scope_names_its_path(edit: Callable[..., object]) -> None:
    netlist = Netlist.from_text(_SCOPED, dialect=current_dialect())
    scope = netlist.scope(("amp",))
    with pytest.raises(TypeError, match=r"not a Scope object: pass Scope\.path \(\('amp',\)\)"):
        edit(netlist, scope=scope, in_definition=True)
    with pytest.raises(TypeError, match=r"write \('amp',\)"):
        edit(netlist, scope="amp", in_definition=True)


def test_in_definition_with_a_definition_scope_still_edits() -> None:
    netlist = Netlist.from_text(_SCOPED, dialect=current_dialect())
    edited = netlist.set_value("R1", "2k", scope=("amp",), in_definition=True)
    assert "R1 a b 2k\n" in edited.text
    assert "R1 a 0 1k\n" in edited.text


@pytest.mark.parametrize(
    ("build", "message"),
    [
        (lambda: Placement("bogus"), "unknown placement kind 'bogus'"),  # type: ignore[arg-type]
        (lambda: Placement("before"), r"Placement\('before'\) needs an anchor line"),
        (lambda: Placement("after"), r"Placement\('after'\) needs an anchor line"),
        (
            lambda: Placement("after", "R1 a 0 1k"),  # type: ignore[arg-type]
            r"Placement\('after'\) needs an anchor line",
        ),
        (
            lambda: Placement("before_end", _netlist().lines[0]),
            r"Placement\('before_end'\) takes no anchor line; use Placement\.BEFORE_END",
        ),
    ],
    ids=[
        "unknown kind",
        "before without a line",
        "after without a line",
        "a str anchor",
        "a constant with a line",
    ],
)
def test_a_placement_is_checked_when_built(build: Callable[[], Placement], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build()


def test_the_placement_constants_and_constructors_build() -> None:
    line = _netlist().lines[1]
    assert Placement.AFTER_TITLE.kind == "after_title"
    assert Placement.AFTER_LAST_PARAM.kind == "after_last_param"
    assert Placement.BEFORE_END.kind == "before_end"
    assert Placement.before(line).anchor is line
    assert Placement.after(line).kind == "after"
