"""Independent oracle over source formatting and generated edits, on both dialects (M9 T8, T5 tier).

The generator writes a netlist piece by piece and records what it wrote, with offsets: every item's
kind and extent, each value, each comment, and the line ending before each insertion point. The
expected parse and the expected text after an edit are computed from that record, by splicing
strings, and never from the parser. It covers what ``ngspice/test_element_oracle.py`` does not: LF,
CRLF and mixed endings, every continuation and comment form of the dialect, indentation,
whitespace-only lines and block variants.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from netlistmod import Component, Dialect, End, Netlist, SourceText, StepDirective, parse

_VALUES = ("1k", "2.2u", "1e-3", "10", "{rx}")
_COMMENTS = {
    Dialect.NGSPICE: (" ; c", ";c", " $ c", " // c"),
    Dialect.LTSPICE: (" ; c", ";c", " $ c"),
}
_BLOCKS = (
    ".control\nrun\n.endc\n",
    ".CONTROL\n* inside\n.ENDC\n",
    ".if (1)\nR99 x 0 1k\n.endif\n",
    ".if (a)\n.if (b)\n.else\n.endif\n.elseif (c)\nR98 y 0 1k\n.endif\n",
)
_ENDINGS = ("lf", "crlf", "mixed")


@dataclass
class _Item:
    """One item as written; offsets are absolute."""

    kind: str
    start: int
    end: int = 0
    designator: str = ""
    value: tuple[int, int] = (0, 0)
    comments: list[str] = field(default_factory=list)
    ending: str = ""


@dataclass
class _Writer:
    dialect: Dialect
    rng: random.Random
    endings: str
    text: str = ""
    items: list[_Item] = field(default_factory=list)

    def eol(self) -> str:
        if self.endings == "mixed":
            return self.rng.choice(("\n", "\r\n"))
        return "\n" if self.endings == "lf" else "\r\n"

    def begin(self, kind: str) -> _Item:
        item = _Item(kind, len(self.text))
        self.items.append(item)
        if self.rng.random() < 0.2:
            self.text += self.rng.choice(("  ", "\t", " \t "))
        return item

    def finish(self, item: _Item, *, comment: bool = True) -> None:
        if comment and self.rng.random() < 0.3:
            self._comment(item)
        self.line_end(item)

    def line_end(self, item: _Item) -> None:
        item.ending = self.eol()
        self.text += item.ending
        item.end = len(self.text)

    def _comment(self, item: _Item) -> None:
        written = self.rng.choice(_COMMENTS[self.dialect])
        self.text += written
        item.comments.append(written.lstrip())

    def gap(self, item: _Item) -> None:
        choice = self.rng.randrange(8)
        if choice == 0:
            self._comment(item)
            self.text += f"{self.eol()}+ "
        elif choice == 1:
            self.text += f"{self.eol()}+\t"
        elif choice == 2 and self.dialect is Dialect.NGSPICE:
            self.text += f" \\\\{self.eol()}"
        elif choice == 3 and self.dialect is Dialect.NGSPICE:
            self.text += " , "
        elif choice == 4:
            self.text += "\t"
        else:
            self.text += " " * self.rng.randrange(1, 3)

    def element(self, letter: str, index: int) -> None:
        kinds = {"R": "Resistor", "C": "Capacitor", "L": "Inductor", "V": "VoltageSource"}
        item = self.begin(kinds[letter])
        item.designator = f"{letter}{index}"
        self.text += item.designator
        for node in ("a", "0"):
            self.gap(item)
            self.text += node
        self.gap(item)
        if letter == "V" and self.rng.random() < 0.5:
            self.text += "DC "
        value = self.rng.choice(_VALUES)
        item.value = (len(self.text), len(self.text) + len(value))
        self.text += value
        self.finish(item)

    def dot_command(self, kind: str, text: str) -> None:
        item = self.begin(kind)
        self.text += text
        self.finish(item)

    def comment_line(self) -> None:
        item = self.begin("CommentLine")
        marker = "*" if self.dialect is Dialect.NGSPICE else self.rng.choice("*;")
        self.text += f"{marker} note"
        self.finish(item, comment=False)

    def blank(self) -> None:
        item = self.begin("BlankLine")
        self.finish(item, comment=False)

    def block(self) -> None:
        item = _Item("OpaqueBlock", len(self.text))
        self.items.append(item)
        for line in self.rng.choice(_BLOCKS).splitlines():
            self.text += line
            self.line_end(item)


def _write(dialect: Dialect, seed: int) -> _Writer:
    rng = random.Random(seed)
    writer = _Writer(dialect, rng, rng.choice(_ENDINGS))
    title = _Item("Title", 0)
    writer.items.append(title)
    writer.text = "oracle title"
    writer.line_end(title)
    writer.element("R", 0)
    writer.element("V", 0)
    for index in range(1, rng.randrange(2, 12)):
        choice = rng.randrange(9)
        if choice < 3:
            writer.element(rng.choice("RCLV"), index)
        elif choice == 3:
            writer.dot_command("ParamStatement", f".param p{index}=1k")
        elif choice == 4:
            writer.dot_command("TranDirective", ".tran 1n 1u")
        elif choice == 5:
            writer.dot_command("SaveDirective", ".save v(a)")
        elif choice == 6:
            writer.comment_line()
        elif choice == 7:
            writer.blank()
        elif dialect is Dialect.NGSPICE:
            writer.block()
    end = writer.begin("End")
    writer.text += rng.choice((".end", ".END"))
    if rng.random() < 0.3:
        end.end = len(writer.text)
    else:
        writer.line_end(end)
    return writer


def _splice(text: str, edits: list[tuple[int, int, str]]) -> str:
    for start, end, new in sorted(edits, reverse=True):
        text = text[:start] + new + text[end:]
    return text


_both = pytest.mark.parametrize("dialect", list(Dialect))


@_both
@settings(max_examples=150, print_blob=True, deadline=None)
@given(seed=st.integers())
def test_generated_formatting_matches_the_generator(dialect: Dialect, seed: int) -> None:
    written = _write(dialect, seed)
    text = written.text
    items = parse(SourceText(text), dialect).items
    assert [type(item).__name__ for item in items] == [item.kind for item in written.items]
    for item, expected in zip(items, written.items, strict=True):
        assert (item.span.start, item.span.end) == (expected.start, expected.end)
        comments = getattr(item, "trailing_comments", ())
        assert [text[span.start : span.end] for span in comments] == expected.comments
        if isinstance(item, Component):
            assert item.designator == expected.designator
            slot = getattr(item, "value", None) or getattr(item, "dc", None)
            assert (slot.span.start, slot.span.end) == expected.value
    netlist = Netlist.from_text(text, dialect=dialect)
    assert netlist.to_bytes() == text.encode("utf-8")


def _named(written: _Writer, kind: str) -> list[_Item]:
    return [item for item in written.items if item.kind == kind]


Edit = Callable[[Netlist], Netlist]


def _pick_edit(written: _Writer, rng: random.Random) -> tuple[Edit, list[tuple[int, int, str]]]:
    """One allowed operation, with the splices it must amount to."""
    resistor = rng.choice(_named(written, "Resistor"))
    source = rng.choice(_named(written, "VoltageSource"))
    name = resistor.designator
    start, end = resistor.value
    params = _named(written, "ParamStatement")
    after = params[-1] if params else written.items[0]
    before_end = written.items[-1].start
    before = next(item.ending for item in reversed(written.items) if item.end == before_end)
    table: list[tuple[Edit, list[tuple[int, int, str]]]] = [
        (lambda n: n.set_value(name, "4700"), [(start, end, "4700")]),
        (lambda n: n.set_formula(name, "rx*2"), [(start, end, "{rx*2}")]),
        (lambda n: n.set_param(name, "m", "2"), [(end, end, " m=2")]),
        (
            lambda n: n.set_dc(source.designator, "5"),
            [(source.value[0], source.value[1], "5")],
        ),
        (
            lambda n: n.params.set("newp", "1"),
            [(after.end, after.end, f".param newp=1{after.ending}")],
        ),
        (
            lambda n: n.directives.add(".save v(a)"),
            [(before_end, before_end, f".save v(a){before}")],
        ),
    ]
    return rng.choice(table)


@_both
@settings(max_examples=150, print_blob=True, deadline=None)
@given(seed=st.integers())
def test_generated_edits_splice_exactly(dialect: Dialect, seed: int) -> None:
    written = _write(dialect, seed)
    rng = random.Random(seed ^ 0x5EED)
    netlist = Netlist.from_text(written.text, dialect=dialect)
    edit, splices = _pick_edit(written, rng)
    edited = edit(netlist)
    assert edited.text == _splice(written.text, splices)
    assert edited.signature() == netlist.signature()
    assert netlist.text == written.text


@_both
@settings(max_examples=100, print_blob=True, deadline=None)
@given(seed=st.integers())
def test_generated_batches_splice_exactly(dialect: Dialect, seed: int) -> None:
    written = _write(dialect, seed)
    netlist = Netlist.from_text(written.text, dialect=dialect)
    resistor = written.items[1]
    source = written.items[2]
    with netlist.batch() as batch:
        batch.set_value(resistor.designator, "3k")
        batch.set_param(resistor.designator, "m", "2")
        batch.set_dc(source.designator, "7")
    assert batch.result.text == _splice(
        written.text,
        [
            (*resistor.value, "3k"),
            (resistor.value[1], resistor.value[1], " m=2"),
            (*source.value, "7"),
        ],
    )


@_both
@pytest.mark.parametrize("tail", ["  ", "\t"])
def test_blanks_after_a_final_end_belong_to_it(dialect: Dialect, tail: str) -> None:
    text = f"t\n.end{tail}"
    end = parse(SourceText(text), dialect).items[-1]
    assert isinstance(end, End)
    assert end.span.end == len(text)


@pytest.mark.parametrize(
    ("item", "kind"), [("param x", "param"), ("temp", "temp"), ("V1", "source")]
)
def test_a_comment_before_a_step_item_is_kept(item: str, kind: str) -> None:
    text = f"t\n.step ; c\n+ {item} 1 2 1\n.op\n.end\n"
    step = parse(SourceText(text), Dialect.LTSPICE).items[1]
    assert isinstance(step, StepDirective)
    assert step.kind == kind
    assert [text[span.start : span.end] for span in step.trailing_comments] == ["; c"]
