"""Directives, placement and `.include` (M6 T5; decision 0007 items 4, 6, 7 and 9)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from netlistmod import (
    Dialect,
    EditError,
    Netlist,
    OpDirective,
    OptionsDirective,
    Placement,
    SaveDirective,
    TopologyError,
    TranDirective,
    UnknownDirective,
)


def _netlist(text: str) -> Netlist:
    return Netlist.from_text(text, dialect=Dialect.NGSPICE)


Operation = Callable[[Netlist], Netlist]

_CASES: list[tuple[str, str, Operation, str]] = [
    (
        "set replaces",
        "t\n.tran 1u 5u\n.end\n",
        lambda n: n.directives.set(".tran 1u 10m"),
        "t\n.tran 1u 10m\n.end\n",
    ),
    (
        "set replaces with comment",
        "t\n  .TRAN 1u 5u ; old\n.end\n",
        lambda n: n.directives.set(".tran 1u 10m"),
        "t\n.tran 1u 10m\n.end\n",
    ),
    (
        "set adds",
        "t\nR1 a 0 1k\n.end\n",
        lambda n: n.directives.set(".op"),
        "t\nR1 a 0 1k\n.op\n.end\n",
    ),
    (
        "set temp",
        "t\n.temp 27\n.end\n",
        lambda n: n.directives.set(".temp 50"),
        "t\n.temp 50\n.end\n",
    ),
    (
        "add before end",
        "t\nR1 a 0 1k\n.end\n",
        lambda n: n.directives.add(".save v(a)"),
        "t\nR1 a 0 1k\n.save v(a)\n.end\n",
    ),
    (
        "add unknown",
        "t\n.end\n",
        lambda n: n.directives.add(".probe v(a)"),
        "t\n.probe v(a)\n.end\n",
    ),
    (
        "add after title",
        "t\nR1 a 0 1k\n.end\n",
        lambda n: n.directives.add(".options reltol=1e-4", Placement.AFTER_TITLE),
        "t\n.options reltol=1e-4\nR1 a 0 1k\n.end\n",
    ),
    (
        "add after last param",
        "t\n.param a=1\nR1 a 0 {a}\n.end\n",
        lambda n: n.directives.add(".op", Placement.AFTER_LAST_PARAM),
        "t\n.param a=1\n.op\nR1 a 0 {a}\n.end\n",
    ),
    (
        "add before anchor",
        "t\nR1 a 0 1k\n.op\n.end\n",
        lambda n: n.directives.add(".save all", Placement.before(_find(n, OpDirective))),
        "t\nR1 a 0 1k\n.save all\n.op\n.end\n",
    ),
    (
        "add after anchor",
        "t\nR1 a 0 1k\n.op\n.end\n",
        lambda n: n.directives.add(".save all", Placement.after(_find(n, OpDirective))),
        "t\nR1 a 0 1k\n.op\n.save all\n.end\n",
    ),
    (
        "add with crlf",
        "t\r\nR1 a 0 1k\r\n.end\r\n",
        lambda n: n.directives.add(".op"),
        "t\r\nR1 a 0 1k\r\n.op\r\n.end\r\n",
    ),
    (
        "mixed endings follow the preceding line",
        "t\r\nR1 a 0 1k\n.end\r\n",
        lambda n: n.directives.add(".op"),
        "t\r\nR1 a 0 1k\n.op\n.end\r\n",
    ),
    (
        "missing final newline",
        "t\nR1 a 0 1k\n.end",
        lambda n: n.directives.add(".op"),
        "t\nR1 a 0 1k\n.op\n.end",
    ),
    (
        "replace",
        "t\n.save v(a)\n.end\n",
        lambda n: n.directives.replace(_find(n, SaveDirective), ".save v(b)"),
        "t\n.save v(b)\n.end\n",
    ),
    (
        "replace by item with another kind",
        "t\n.op\n.end\n",
        lambda n: n.directives.replace(_find(n, OpDirective).item, ".tran 1u 1m"),
        "t\n.tran 1u 1m\n.end\n",
    ),
    (
        "remove",
        "t\nR1 a 0 1k\n.options gmin=1e-12\n+ reltol=1e-3\n.end\n",
        lambda n: n.directives.remove(_find(n, OptionsDirective)),
        "t\nR1 a 0 1k\n.end\n",
    ),
    (
        "remove unknown",
        "t\n.print dc v(a)\n.end\n",
        lambda n: n.directives.remove(_find(n, UnknownDirective)),
        "t\n.end\n",
    ),
    (
        "include",
        "t\nR1 a 0 1k\n.end\n",
        lambda n: n.add_include("harness.cir"),
        't\n.include "harness.cir"\nR1 a 0 1k\n.end\n',
    ),
    (
        "include with blanks and slashes",
        "t\r\n.end\r\n",
        lambda n: n.add_include("my dir//h.inc", Placement.BEFORE_END),
        't\r\n.include "my dir//h.inc"\r\n.end\r\n',
    ),
    # Review round 1: continued text as a list of lines, and whole opaque items.
    (
        "continued tran as lines",
        "t\r\n.tran 1u 5u\r\n.end\r\n",
        lambda n: n.directives.set([".tran 1u 10m", "+ 0 1u"]),
        "t\r\n.tran 1u 10m\r\n+ 0 1u\r\n.end\r\n",
    ),
    (
        "backslash continuation as lines",
        "t\n.end\n",
        lambda n: n.directives.add([".save v(a) \\\\", "v(b)"]),
        "t\n.save v(a) \\\\\nv(b)\n.end\n",
    ),
    (
        "add a control block",
        "t\r\nR1 a 0 1k\r\n.end\r\n",
        lambda n: n.directives.add([".control", "op", "print v(a)", ".endc"]),
        "t\r\nR1 a 0 1k\r\n.control\r\nop\r\nprint v(a)\r\n.endc\r\n.end\r\n",
    ),
    (
        "remove a control block",
        "t\n.control\nrun\n.endc\n.end\n",
        lambda n: n.directives.remove(n.lines[1]),
        "t\n.end\n",
    ),
    (
        "add an if block",
        "t\n.end\n",
        lambda n: n.directives.add([".if (1)", ".endif"], Placement.AFTER_TITLE),
        "t\n.if (1)\n.endif\n.end\n",
    ),
    (
        "replace an if block",
        "t\n.if (1)\n.endif\n.end\n",
        lambda n: n.directives.replace(n.lines[1], ".op"),
        "t\n.op\n.end\n",
    ),
    (
        "remove an include",
        "t\n.include x.lib\nR1 a 0 1k\n.end\n",
        lambda n: n.directives.remove(n.lines[1]),
        "t\nR1 a 0 1k\n.end\n",
    ),
    (
        "swap an include for a lib",
        "t\n.include x.lib\n.end\n",
        lambda n: n.directives.replace(n.lines[1], ".lib models.lib tt"),
        "t\n.lib models.lib tt\n.end\n",
    ),
    ("add a lib", "t\n.end\n", lambda n: n.directives.add(".lib m.lib"), "t\n.lib m.lib\n.end\n"),
]


def _find(netlist: Netlist, kind: type) -> object:
    line = netlist.lines.find(kind)
    assert line is not None
    return line


@pytest.mark.parametrize(
    ("text", "operation", "expected"),
    [case[1:] for case in _CASES],
    ids=[case[0] for case in _CASES],
)
def test_directive_operation(text: str, operation: Operation, expected: str) -> None:
    netlist = _netlist(text)
    edited = operation(netlist)
    assert edited.text == expected
    assert edited.signature() == netlist.signature()


def test_set_is_idempotent() -> None:
    once = _netlist("t\n.end\n").directives.set(".tran 1u 10m")
    assert once.directives.set(".tran 1u 10m").text == once.text
    assert isinstance(once.lines[1].item, TranDirective)


@pytest.mark.parametrize(
    ("text", "operation", "message"),
    [
        (
            "t\n.tran 1u 5u\n.tran 1u 6u\n.end\n",
            lambda n: n.directives.set(".tran 1u 1m"),
            "ambiguous",
        ),
        ("t\n.end\n", lambda n: n.directives.set(".options reltol=1e-4"), "repeatable"),
        ("t\n.end\n", lambda n: n.directives.set(".save all"), "repeatable"),
        ("t\n.end\n", lambda n: n.directives.set(".probe v(a)"), "repeatable"),
        ("t\n.end\n", lambda n: n.directives.add(".op\n.save all"), "pass a list"),
        ("t\n.end\n", lambda n: n.directives.add(".save v(a)\n+ v(b)"), "pass a list"),
        ("t\n.end\n", lambda n: n.directives.add([".op", ".save all"]), "exactly one statement"),
        ("t\n.end\n", lambda n: n.directives.add([".save v(a)\n+ v(b)"]), "exactly one"),
        ("t\n.end\n", lambda n: n.directives.add([]), "no text"),
        ("t\n.end\n", lambda n: n.directives.add(".include x.lib"), "add_include"),
        ("t\n.op\n.end\n", lambda n: n.directives.replace(n.lines[1], ".include x"), "add_include"),
        ("t\n.end\n", lambda n: n.directives.set(".lib m.lib"), "opaque item"),
        ("t\n.end\n", lambda n: n.directives.add([".control", "run"]), "does not parse"),
        ("t\n.end\n", lambda n: n.directives.add(".tran 1u"), "does not parse"),
        ("t\n.end\n", lambda n: n.directives.add(".param a=1"), "use params.set"),
        (
            "t\n.end\n",
            lambda n: n.directives.add(".model dm d"),
            "use params.set or set_model_param",
        ),
        ("t\n.end\n", lambda n: n.directives.add("* comment"), "comment line, not a directive"),
        ("t\n.end\n", lambda n: n.directives.add(".title other"), "`.title` line"),
        ("t\n.param a=1\n.end\n", lambda n: n.directives.remove(n.lines[1]), "edited, not removed"),
        ("t\n.end\n", lambda n: n.directives.remove(n.lines[0]), "title line"),
        ("t\n\n.end\n", lambda n: n.directives.remove(n.lines[1]), "blank line"),
        ("t\n.end\n", lambda n: n.directives.remove(n.lines[1]), "`.end` line"),
        (
            "t\n.end\n",
            lambda n: n.directives.add(".op", Placement.before(n.lines[0])),
            "before the title",
        ),
        (
            "t\n.end\n",
            lambda n: n.directives.add(".op", Placement.after(n.lines[1])),
            "after `.end`",
        ),
        (
            "t\n.subckt s a\n.print x\n.ends\n.end\n",
            lambda n: n.directives.remove(n.scope(("s",)).lines[0]),
            "inside a subcircuit",
        ),
        (
            "t\n.subckt s a\nR1 a 0 1\n.ends\n.end\n",
            lambda n: n.directives.add(".op", Placement.after(n.scope(("s",)).lines[0])),
            "not a line of the top level",
        ),
        ('t\n.include "h.cir"\n.end\n', lambda n: n.add_include("h.cir"), "already includes"),
        ("t\n.end\n", lambda n: n.add_include('a"b'), "does not parse"),
    ],
)
def test_directive_operation_errors(text: str, operation: Operation, message: str) -> None:
    with pytest.raises(EditError, match=message):
        operation(_netlist(text))


@pytest.mark.parametrize(
    ("text", "operation", "message"),
    [
        ("t\n.end\n", lambda n: n.directives.add("R9 a 0 1k"), "resistor line"),
        ("t\n.end\n", lambda n: n.directives.set("V9 a 0 1"), "voltage source line"),
        ("t\n.end\n", lambda n: n.directives.add(".global vcc"), "`.global` line"),
        ("t\n.end\n", lambda n: n.directives.add([".subckt s a", ".ends"]), "subcircuit"),
        ("t\nR1 a 0 1k\n.end\n", lambda n: n.directives.remove(n.lines[1]), "resistor line"),
        (
            "t\nR1 a 0 1k\n.end\n",
            lambda n: n.directives.replace(n.lines[1], ".op"),
            "resistor line",
        ),
        ("t\n.global vcc\n.end\n", lambda n: n.directives.remove(n.lines[1]), "`.global` line"),
        (
            "t\n.subckt s a\n.ends\n.end\n",
            lambda n: n.directives.remove(n.lines[1]),
            "subcircuit definition",
        ),
    ],
)
def test_forbidden_directive_operations_are_topology_errors(
    text: str, operation: Operation, message: str
) -> None:
    with pytest.raises(TopologyError, match=message):
        operation(_netlist(text))


def test_placement_repr() -> None:
    netlist = _netlist("t\n.op\n.end\n")
    assert repr(Placement.BEFORE_END) == "Placement.BEFORE_END"
    assert repr(Placement.after(netlist.lines[1])) == "Placement.after(line 2)"
