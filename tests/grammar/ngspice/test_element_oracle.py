"""Independent generator oracle for element lines (M3) and statements (M4), T5 tier.

The generator writes each element field by field and records what it wrote, with offsets, so
the expected kinds, designators, nodes and value texts do not come from the parser. The
broader generator (edits) is M9 work.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from hypothesis import given, settings
from hypothesis import strategies as st

from netlistmod import (
    Component,
    Dialect,
    ParamStatement,
    ParseError,
    SourceText,
    SubcktDefinition,
    UnknownDirective,
    UnsupportedConstruct,
    parse,
)

NAMES = ("a", "b", "out", "0", "12", "/vin", "n+", "x1.n", "1n")
NUMBERS = ("1", "10k", "-4.7", "2.2u", "1e-3", "3MEG", "100Ohm", ".5", "1µ")
FORMULAS = ("{rx}", "{2*cval}", "'a+b'", "'V(a)*2'")
MODELS = ("rmod", "dmod", "1n4148", "MODEL_A")


@dataclass
class _Line:
    """One element line as written, with the offsets of each field relative to the line."""

    kind: str
    parts: list[str] = field(default_factory=list)
    fields: list[tuple[str, int, int]] = field(default_factory=list)  # (role, start, end)
    comments: int = 0

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def add(self, role: str, text: str) -> None:
        start = len(self.text)
        self.parts.append(text)
        self.fields.append((role, start, start + len(text)))

    def gap(self, rng: random.Random) -> None:
        choice = rng.randrange(10)
        if choice == 0:
            self.parts.append(" ; c\n+ ")
            self.comments += 1
        elif choice == 1:
            self.parts.append("\n+ ")
        elif choice == 2:
            self.parts.append(" , ")
        elif choice == 3:
            self.parts.append("\t")
        else:
            self.parts.append(" ")


def _value(rng: random.Random) -> str:
    return rng.choice(NUMBERS + FORMULAS)


def _params(line: _Line, rng: random.Random) -> None:
    for index in range(rng.randrange(3)):
        line.gap(rng)
        line.add("param", f"p{index}")
        line.parts.append(rng.choice(("=", " = ")))
        line.add("param_value", _value(rng))


def _element(index: int, rng: random.Random) -> _Line:
    letter = rng.choice("RCLKVIDX")
    designator = f"{letter}{index}"
    kinds = {
        "R": "Resistor",
        "C": "Capacitor",
        "L": "Inductor",
        "K": "MutualCoupling",
        "V": "VoltageSource",
        "I": "CurrentSource",
        "D": "Diode",
        "X": "SubcktInstance",
    }
    line = _Line(kinds[letter])
    line.add("designator", designator)
    if letter == "K":
        for number in range(rng.randrange(2, 4)):
            line.gap(rng)
            line.add("inductor", f"L{number}")
        line.gap(rng)
        line.add("value", _value(rng))
        return line
    node_count = rng.randrange(1, 4) if letter == "X" else 2
    for _ in range(node_count):
        line.gap(rng)
        line.add("node", rng.choice(NAMES))
    if letter in "RCL":
        line.gap(rng)
        if rng.random() < 0.8:
            line.add("value", _value(rng))
            if rng.random() < 0.3:
                line.gap(rng)
                line.add("model", rng.choice(MODELS[:2]))
        else:
            line.add("model", rng.choice(MODELS[:2]))
        _params(line, rng)
    elif letter in "VI":
        if rng.random() < 0.7:
            line.gap(rng)
            if rng.random() < 0.5:
                line.parts.append("DC ")
            line.add("dc", _value(rng))
        if rng.random() < 0.4:
            line.gap(rng)
            line.parts.append("AC ")
            line.add("ac", _value(rng))
    elif letter == "D":
        line.gap(rng)
        line.add("model", rng.choice(MODELS))
        _params(line, rng)
        if rng.random() < 0.3:
            line.parts.append(" off")
    else:
        line.gap(rng)
        line.add("subckt", f"sub{index}")
        _params(line, rng)
    if rng.random() < 0.2:
        line.parts.append(" $ end")
        line.comments += 1
    return line


def _actual_fields(item: Component, text: str, start: int) -> list[tuple[str, int, int]]:
    def rel(span: object) -> tuple[int, int]:
        return span.start - start, span.end - start  # type: ignore[attr-defined]

    found: list[tuple[str, int, int]] = [("designator", *rel(item.designator_span))]
    found += [("node", *rel(node.span)) for node in item.nodes]
    for name in ("inductors",):
        found += [("inductor", *rel(ref.span)) for ref in getattr(item, name, ())]
    for role in ("value", "model", "dc", "subckt"):
        slot = getattr(item, role, None)
        if slot is not None:
            found.append((role, *rel(slot.span)))
    ac = getattr(item, "ac", None)
    if ac is not None:
        found.append(("ac", *rel(ac.magnitude.span)))
    for param in item.params:
        found.append(("param", *rel(param.name_span)))
        found.append(("param_value", *rel(param.value.span)))
    return sorted(found, key=lambda entry: entry[1])


# No deadline: the first example may build and cache the parser.
@settings(max_examples=200, print_blob=True, deadline=None)
@given(seed=st.integers())
def test_generated_element_lines_match_the_generator(seed: int) -> None:
    rng = random.Random(seed)
    title = f"oracle {rng.randrange(1_000_000)}\n"
    pieces = [title]
    expected: list[tuple[_Line, int]] = []
    for index in range(rng.randrange(1, 10)):
        if rng.random() < 0.15:
            pieces.append(f"* comment {index}\n")
            continue
        line = _element(index, rng)
        expected.append((line, sum(map(len, pieces))))
        pieces.append(line.text + "\n")
    pieces.append(".end\n")
    text = "".join(pieces)

    try:
        result = parse(SourceText(text), Dialect.NGSPICE)
    except (ParseError, UnsupportedConstruct) as error:
        raise AssertionError(f"oracle parse failure for seed={seed}:\n{text}\n{error}") from error
    elements = [item for item in result.items if isinstance(item, Component)]
    assert [type(item).__name__ for item in elements] == [line.kind for line, _ in expected]
    for item, (line, start) in zip(elements, expected, strict=True):
        assert item.span.end == start + len(line.text) + 1
        assert _actual_fields(item, text, start) == sorted(line.fields, key=lambda e: e[1])
        for _, field_start, field_end in line.fields:
            assert text[start + field_start : start + field_end].strip()
        assert len(item.trailing_comments) == line.comments


# M4: statements, typed directives and nested subcircuit blocks with element bodies. The
# generator records each item's kind, name and nesting; the parser's tree must match it.

DIRECTIVES = (
    (".tran 1n 1u", "TranDirective"),
    (".tran 1n 1u 0 1n uic", "TranDirective"),
    (".ac dec 10 1 1k", "AcDirective"),
    (".dc v1 0 1 0.1", "DcDirective"),
    (".op", "OpDirective"),
    (".options reltol=1e-3 noacct", "OptionsDirective"),
    (".temp 27", "TempDirective"),
    (".ic v(a)=1", "IcDirective"),
    (".nodeset all=0", "NodesetDirective"),
    (".save v(a) i(v1)", "SaveDirective"),
    (".meas tran t1 MAX v(a)", "MeasureDirective"),
    (".print tran v(a)", "UnknownDirective"),
)

_Tree = tuple[str, str, tuple["_Tree", ...]]


def _statement(index: int, rng: random.Random, depth: int, top: bool) -> tuple[str, _Tree]:
    choice = rng.randrange(6 if top else 4)
    if choice == 0:
        line = _element(index, rng)
        return line.text + "\n", (line.kind, line.text.split(None, 1)[0], ())
    if choice == 1:
        name = f"p{index}"
        gap = rng.choice((" ", "\n+ "))
        return f".param {name}={_value(rng)}{gap}q{index}=1\n", ("ParamStatement", name, ())
    if choice == 2:
        name = f"m{index}"
        params = rng.choice((" is=1", "(is=1\n+ n=2)", " (is=1, n=2)", ""))
        return f".model {name} D{params}\n", ("ModelStatement", name, ())
    if choice == 3 and depth < 2:
        name = f"s{index}_{depth}"
        lines = [f".subckt {name} a b r={_value(rng)}\n"]
        children: list[_Tree] = []
        for child in range(rng.randrange(0, 4)):
            text, tree = _statement(index * 10 + child, rng, depth + 1, top=False)
            lines.append(text)
            children.append(tree)
        lines.append(rng.choice((".ends\n", f".ends {name}\n", ".ENDS ; done\n")))
        return "".join(lines), ("SubcktDefinition", name, tuple(children))
    if choice >= 4:
        text, kind = rng.choice(DIRECTIVES)
        return text + "\n", (kind, text.split(None, 1)[0], ())
    return f"* comment {index}\n", ("CommentLine", "", ())


def _actual_tree(item: object) -> _Tree:
    kind = type(item).__name__
    if isinstance(item, Component):
        return (kind, item.designator, ())
    if isinstance(item, SubcktDefinition):
        return (kind, item.name, tuple(_actual_tree(child) for child in item.body))
    name = getattr(item, "name", None)
    if isinstance(item, ParamStatement):
        name = item.assignments[0].name
    elif isinstance(item, UnknownDirective):
        name = item.name
    elif name is None:
        name = getattr(item, "keyword", "")
    return (kind, name, ())


# No deadline: the first example may build and cache the parser.
@settings(max_examples=200, print_blob=True, deadline=None)
@given(seed=st.integers())
def test_generated_statements_and_subcircuits_match_the_generator(seed: int) -> None:
    rng = random.Random(seed)
    pieces = [f"oracle {rng.randrange(1_000_000)}\n"]
    expected: list[tuple[_Tree, int, int]] = []
    for index in range(rng.randrange(1, 8)):
        text, tree = _statement(index, rng, 0, top=True)
        start = sum(map(len, pieces))
        pieces.append(text)
        expected.append((tree, start, start + len(text)))
    pieces.append(".end\n")
    text = "".join(pieces)

    try:
        result = parse(SourceText(text), Dialect.NGSPICE)
    except (ParseError, UnsupportedConstruct) as error:
        raise AssertionError(f"oracle parse failure for seed={seed}:\n{text}\n{error}") from error
    items = result.items[1:-1]
    assert [_actual_tree(item) for item in items] == [tree for tree, _, _ in expected]
    for item, (_, start, end) in zip(items, expected, strict=True):
        assert (item.span.start, item.span.end) == (start, end)
