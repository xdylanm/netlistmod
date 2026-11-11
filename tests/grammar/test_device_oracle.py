"""Independent generator oracle for the phase 2 element letters and forms, on both dialects (M18 D3,
T5 tier).

The generator writes each element line field by field and records what it wrote: every field's
role, offsets and text, the line's structure (form, quantity, table shape, ports …) and the
topology tokens. The expected spans, structure and signature entries are computed from that record
only, never from the parser. Each netlist is also checked for a byte-exact round trip, and for the
mutation property: changing any one topology token (a node, a control node, a controlling source,
an ngspice A port's type, node or count) changes the signature, while changing a value does not.

``tests/edits/test_device_edit_properties.py`` reuses the generator. The two older oracles
(``ngspice/test_element_oracle.py``, ``test_broad_oracle.py``) cover the phase 1 letters and the
source formatting.

Shapes left out on purpose: non-ASCII letters other than ``µ`` (U+00B5) in a positional number
after a transistor model (A1-4, a known defect assigned to D5), nested ``.if`` blocks (A2-19),
LTspice's I-only functions (``tbl=``, ``step``) and the file and wave forms (fixed shapes in
``test_source_functions.py``).
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from netlistmod import Component, Dialect, Netlist, ParseError
from netlistmod.model.nodes import (
    CodeModelDevice,
    FraProbe,
    FrequencyAnalyzer,
    SpecialFunction,
)

NG = Dialect.NGSPICE
LT = Dialect.LTSPICE

_NAMES = ("a", "b", "out", "n1", "12", "7", "x_2", "0", "gnd", "In")
_NUMBERS = ("1", "10k", "-4.7", "2.2u", "1e-3", ".5", "3MEG", "1µ")
_FORMULAS = {NG: ("{k}", "{2*k}", "'k*2'"), LT: ("{k}", "{2*k}")}
_SCOPE = "w"

# The sense sources every netlist writes, in each scope, for the controlled lines to name.
SENSES = ("Vs", "Vt")

# The type of each model family. A netlist writes `<family>1` and `<family>2` for each family its
# lines use, so that set_model has another model to pick and no diagnostic fires.
MODELS: dict[str, str] = {
    "qn": "NPN",
    "mn": "NMOS",
    "jn": "NJF",
    "zn": "NMF",
    "sm": "SW",
    "cm": "CSW",
    "lm": "LTRA(R=1 L=50n C=20p len=1)",
    "um": "URC(Rperl=10 Cperl=1p)",
    "ym": "TXL(R=1 L=50n G=0 C=20p length=1)",
    "pm": "CPL(R=1 0 1 L=50n 1n 50n G=0 0 0 C=20p 1p 20p length=1)",
    "am": "gain(gain=2)",
    "nm": "bsimcmg",
}


def model_lines(families: set[str]) -> list[str]:
    """Two ``.model`` lines (``<family>1`` and ``<family>2``) of each of ``families``."""
    lines = []
    for family, kind in MODELS.items():
        if family in families:
            lines += [f".model {family}1 {kind}", f".model {family}2 {kind}"]
    return lines


@dataclass
class Line:
    """One element line as written, with each field's role and offsets relative to the line."""

    dialect: Dialect
    rng: random.Random
    form: str
    kind: str = ""
    designator: str = ""
    parts: list[str] = field(default_factory=list)
    fields: list[tuple[str, int, int, str]] = field(default_factory=list)
    nodes: list[str] = field(default_factory=list)
    controls: list[str] = field(default_factory=list)
    ports: list[tuple[object, ...]] = field(default_factory=list)
    struct: dict[str, object] = field(default_factory=dict)
    comments: int = 0
    # Topology tokens a mutation may change: (start, end, what), and for an ngspice A line the
    # offset of its model, where a mutation may add a port.
    topology: list[tuple[int, int, str]] = field(default_factory=list)
    model_start: int | None = None
    # Facts the edit properties need, recorded as written.
    models: list[str] = field(default_factory=list)
    params: dict[str, str] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    one_line_points: bool = True
    coefficient_comments: bool = False

    @property
    def text(self) -> str:
        return "".join(self.parts)

    @property
    def ng(self) -> bool:
        return self.dialect is NG

    def lit(self, text: str) -> None:
        self.parts.append(text)

    def add(self, role: str, text: str, topology: str | None = None) -> None:
        start = len(self.text)
        self.parts.append(text)
        self.fields.append((role, start, start + len(text), text))
        if topology is not None:
            self.topology.append((start, start + len(text), topology))

    def node(self, name: str | None = None, what: str = "name") -> None:
        name = name if name is not None else self.rng.choice(_NAMES)
        self.nodes.append(name)
        self.add("node", name, what)

    def control(self, name: str | None = None) -> None:
        name = name if name is not None else self.rng.choice(SENSES)
        self.controls.append(name)
        self.add("control", name, "control")

    def model(self, family: str) -> None:
        name = f"{family}{self.rng.choice('12')}"
        self.models.append(name)
        self.add("model", name)

    def gap(self, comma: bool = False) -> None:
        choice = self.rng.randrange(12)
        if choice == 0:
            self.lit(" ; c\n+ ")
            self.comments += 1
        elif choice == 1:
            self.lit("\n+ ")
        elif choice == 2:
            self.lit("\t")
        elif choice == 3:
            self.lit("  ")
        elif choice == 4 and comma and self.ng:
            self.lit(" , ")
        else:
            self.lit(" ")

    def case(self, word: str) -> str:
        return self.rng.choice((word, word.lower(), word.upper(), word.capitalize()))

    def number(self) -> str:
        return self.rng.choice(_NUMBERS)

    def value(self) -> str:
        return self.rng.choice(_NUMBERS + _FORMULAS[self.dialect])

    def begin(self, letter: str, kind: str, index: int) -> None:
        self.kind = kind
        self.designator = f"{letter}{index}"
        self.add("designator", self.designator)

    def nodes_(self, count: int, comma: bool = True) -> None:
        for _ in range(count):
            self.gap(comma)
            self.node()

    def param(self, name: str, value: str, role: str = "param_value") -> None:
        self.gap()
        self.add("param", name)
        self.lit(self.rng.choice(("=", " = ")) if self.ng else "=")
        self.add(role, value)
        self.params[name] = value

    def params_(self, names: tuple[str, ...], most: int | None = None) -> None:
        count = self.rng.randrange((most if most is not None else len(names)) + 1)
        for name in self.rng.sample(names, min(count, len(names))):
            self.param(name, self.value())

    def finish(self) -> None:
        if self.rng.random() < 0.2:
            self.lit(" ; end" if not self.ng else self.rng.choice((" ; end", " $ end")))
            self.comments += 1


# --- the forms -------------------------------------------------------------------------------

_FUNCTIONS = {
    NG: (
        ("PULSE", 1, 7),
        ("SIN", 2, 5),
        ("EXP", 2, 6),
        ("PWL", 2, 6),
        ("SFFM", 2, 5),
        ("AM", 2, 5),
        ("TRNOISE", 2, 4),
        ("TRRANDOM", 2, 4),
    ),
    LT: (("PULSE", 1, 8), ("SIN", 2, 7), ("SINE", 2, 7), ("EXP", 2, 6), ("PWL", 2, 6)),
}


def _source(line: Line, letter: str, index: int) -> None:
    line.begin(letter, "VoltageSource" if letter == "V" else "CurrentSource", index)
    line.nodes_(2)
    if line.rng.random() < 0.5:
        line.gap()
        keyword = line.rng.random() < 0.5
        if keyword:
            line.lit(line.case("DC") + " ")
        line.add("value", line.value())
    name, low, high = line.rng.choice(_FUNCTIONS[line.dialect])
    count = line.rng.randrange(low, high + 1)
    if name == "PWL":
        count -= count % 2
    line.gap()
    written = line.case(name)
    line.add("function", written)
    line.lit(line.rng.choice(("(", " (", "( ")))
    for position in range(count):
        if position:
            line.lit(line.rng.choice((" ", ", ", ",", "  ")))
        line.add("arg", line.value())
    line.lit(")")
    line.struct.update(stimulus=written, args=count)
    if name == "PWL" and line.ng:
        for word in line.rng.sample(("r", "td"), line.rng.randrange(3)):
            line.param(word, line.number())
    if line.rng.random() < 0.4:
        line.gap()
        line.lit(line.case("AC") + " ")
        line.add("ac", line.value())
        if line.rng.random() < 0.5:
            line.gap()
            line.add("ac_phase", line.number())
    distortion: list[str] = []
    if line.ng and line.rng.random() < 0.3:
        for word in ("DISTOF1", "DISTOF2"):
            if line.rng.random() < 0.6:
                line.gap()
                written = line.case(word)
                line.add("function", written)
                for _ in range(line.rng.randrange(1, 3)):
                    line.gap()
                    line.add("arg", line.number())
                distortion.append(written)
    line.struct["distortion"] = tuple(distortion)
    if letter == "V" and not line.ng:
        line.params_(("Rser", "Cpar"))


_TRANSISTOR = {"Q": "BipolarTransistor", "M": "Mosfet", "J": "Jfet", "Z": "Mesfet"}


def transistor_params(letter: str, dialect: Dialect) -> tuple[str, ...]:
    """The instance parameters each dialect takes on ``letter`` (decision 0014 item 6)."""
    if dialect is NG:
        return ("temp", "m", *{"Q": ("area",), "M": ("W",)}.get(letter, ()))
    return {"Q": ("temp",), "M": ("temp", "m", "W"), "J": ("temp",), "Z": ("temp", "m")}[letter]


def positional_area(letter: str, dialect: Dialect) -> bool:
    return letter in "JZ" or (letter == "Q" and dialect is LT)


def _transistor(line: Line, letter: str, index: int) -> None:
    line.begin(letter, _TRANSISTOR[letter], index)
    counts = (3,) if letter in "JZ" else ((3, 4, 5) if line.ng else (3, 4))
    line.nodes_(line.rng.choice(counts))
    line.gap()
    line.model(letter.lower() + "n")
    if positional_area(letter, line.dialect) and line.rng.random() < 0.5:
        line.gap()
        line.add("value", line.value())
        line.struct["area"] = True
    if line.rng.random() < 0.4:
        line.gap()
        flag = line.case("off")
        line.add("flag", flag)
        line.flags.append(flag)
    line.params_(transistor_params(letter, line.dialect))
    line.struct["flags"] = tuple(line.flags)


_CONTROLLED = {"E": "Vcvs", "G": "Vccs", "F": "Cccs", "H": "Ccvs"}


def _linear(line: Line, letter: str, index: int) -> None:
    line.begin(letter, _CONTROLLED[letter], index)
    line.nodes_(2)
    if letter in "EG":
        line.nodes_(2)
    else:
        line.gap(comma=True)
        line.control()
    line.gap(comma=True)
    line.add("value", line.value())
    line.struct["form"] = None
    if line.ng and letter in "FG" and line.rng.random() < 0.5:
        line.param("m", line.number())


def _switch(line: Line, letter: str, index: int) -> None:
    line.begin(letter, "VoltageSwitch" if letter == "S" else "CurrentSwitch", index)
    line.nodes_(2)
    if letter == "S":
        line.nodes_(2)
    else:
        line.gap(comma=True)
        line.control()
    line.gap()
    line.model("sm" if letter == "S" else "cm")
    if line.rng.random() < 0.6:
        line.gap()
        states = ("on", "off") if line.ng else ("on", "off", "off=1")
        state = line.rng.choice(states)
        word, _, rest = state.partition("=")
        flag = line.case(word) + ("=" + rest if rest else "")
        line.add("flag", flag)
        line.flags.append(flag)
    line.struct["flags"] = tuple(line.flags)


def _expression(line: Line, reads: str, bare_ok: bool = True) -> None:
    """An expression with a drawn delimiter, recorded with its delimiters (``Formula.span``)."""
    body = line.rng.choice((f"2*{reads}", f"k*{reads}+1", f"{reads}*{reads}"))
    delimiters = ["{"] + (["'"] if line.ng else []) + ([""] if bare_ok else [])
    delimiter = line.rng.choice(delimiters)
    closing = {"{": "}", "'": "'", "": ""}[delimiter]
    line.add("expression", f"{delimiter}{body}{closing}")
    line.struct.update(delimiter=delimiter, expression=body)


def _behavioral(line: Line, index: int) -> None:
    line.begin("B", "BehavioralSource", index)
    line.nodes_(2)
    quantities = ("V", "I") if line.ng else ("V", "I", "R", "P")
    quantity = line.rng.choice(quantities)
    line.gap()
    line.lit(line.case(quantity) if line.ng else quantity)
    line.lit(line.rng.choice(("=", " = ")))
    _expression(line, "v(vs)" if line.ng else "V(vs)")
    line.struct["quantity"] = quantity.lower()
    if line.ng:
        line.params_(("tc1", "tc2", "temp", "dtemp"), most=2)
        return
    names = {"V": ("ic", "tripdv", "tripdt"), "I": ("Rpar",), "R": ("Rpar",), "P": ("vprx",)}
    line.params_(names[quantity], most=2)
    if quantity in "VI" and line.rng.random() < 0.3:
        line.param("laplace", line.rng.choice(("1/(1+s/1k)", "{1/(1+s/1k)}")))


def _expression_form(line: Line, letter: str, index: int, keyword: str) -> None:
    line.begin(letter, _CONTROLLED[letter], index)
    line.nodes_(2)
    line.gap()
    line.lit(line.case(keyword) + "=")
    reads = "I(Vs)" if letter in "FH" else ("v(vs)" if line.ng else "V(vs)")
    # ngspice reads these expressions only in braces or quotes (ngspice manual 5.2.1).
    _expression(line, reads, bare_ok=not line.ng)
    line.struct["form"] = keyword.lower()


def _charge(line: Line, index: int) -> None:
    line.begin("C", "Capacitor", index)
    line.nodes_(2)
    line.gap()
    line.lit(("q" if line.ng else "Q") + "=")
    _expression(line, "v(a)" if line.ng else "x", bare_ok=not line.ng)
    line.params_(("tc1",) if line.ng else ("ic", "m"))


def _flux(line: Line, index: int) -> None:
    line.begin("L", "Inductor", index)
    line.nodes_(2)
    line.gap()
    line.lit("Flux=")
    _expression(line, "x")


def _points(line: Line, rows: list[tuple[str, ...]], separator: str, between: bool) -> None:
    """Points in pairs layout: ``(x, y)`` each, a blank or a ``+`` line between them."""
    for position, row in enumerate(rows):
        if position:
            if between and line.rng.random() < 0.3:
                line.lit("\n+ ")
                line.one_line_points = False
            else:
                line.lit(line.rng.choice((" ", "")) if between else " ")
        line.lit("(")
        for column, value in enumerate(row):
            if column:
                line.lit(separator)
            line.add("point_value", value)
        line.lit(")")
    line.struct.update(points=len(rows), widths=tuple(len(row) for row in rows), layout="pairs")


def _flat(line: Line, rows: list[tuple[str, ...]], separator: str) -> None:
    line.lit("(")
    first = True
    for row in rows:
        for value in row:
            if not first:
                line.lit(separator)
            first = False
            line.add("point_value", value)
    line.lit(")")
    line.struct.update(points=len(rows), widths=tuple(len(row) for row in rows), layout="flat")


def _rows(line: Line, width: int, low: int, high: int) -> list[tuple[str, ...]]:
    count = line.rng.randrange(low, high + 1)
    pool = ("0", "1", "2.5", "-1", "4m", "10")
    return [tuple(line.rng.choice(pool) for _ in range(width)) for _ in range(count)]


def _table(line: Line, letter: str, index: int) -> None:
    line.begin(letter, _CONTROLLED[letter], index)
    line.nodes_(2)
    line.gap()
    line.lit(line.case("TABLE") + " ")
    body = "v(vs)"
    delimiter = line.rng.choice(("{", "'"))
    closing = "}" if delimiter == "{" else "'"
    line.add("expression", f"{delimiter}{body}{closing}")
    line.lit(line.rng.choice((" = ", "=", " =")))
    _points(line, _rows(line, 2, 1, 4), line.rng.choice((",", ", ")), between=True)
    line.struct.update(form="table", expression=body, delimiter=delimiter, format=())
    if letter == "G" and line.rng.random() < 0.5:
        line.param("m", line.number())


def _four_node_table(line: Line, letter: str, index: int) -> None:
    line.begin(letter, _CONTROLLED[letter], index)
    line.nodes_(4)
    line.gap()
    line.lit(line.case("TABLE") + line.rng.choice((" = ", "=")))
    _flat(line, _rows(line, 2, 2, 4), line.rng.choice((" ", ",", ", ")))
    line.struct.update(form="table", format=())


def _freq(line: Line, index: int) -> None:
    line.begin("E", "Vcvs", index)
    line.nodes_(2)
    line.gap()
    line.lit(line.case("FREQ") + " ")
    line.add("expression", "{v(vs)}")
    line.lit(line.rng.choice((" = ", "= ", " ")))
    # A format word is required: ngspice stops without one (the library refuses it).
    formats = line.rng.choice((("DB",), ("MAG", "DEG"), ("R_I",), ("DB", "RAD"), ("mag",)))
    for word in formats:
        line.lit(word + " ")
    count = line.rng.randrange(1, 4)
    pool = ("6.02", "0", "-3", "1")
    rows: list[tuple[str, ...]] = [
        (frequency, line.rng.choice(pool), line.rng.choice(pool))
        for frequency in ("1", "1e3", "1e6", "1e9")[:count]
    ]
    _points(line, rows, ", ", between=False)
    line.struct.update(form="freq", expression="v(vs)", delimiter="{", format=formats)


def _gate(line: Line, index: int) -> None:
    # E only: ngspice stops on a gate on G, and the library refuses it.
    line.begin("E", "Vcvs", index)
    line.nodes_(2)
    word = line.rng.choice(("and", "or", "nand", "nor"))
    dimension = line.rng.randrange(2, 4)  # ngspice stops on fewer than two pairs
    line.gap()
    line.lit(f"{line.case(word)}({dimension})")
    line.nodes_(2 * dimension, comma=False)
    line.gap()
    # The two points are separated by a blank: ngspice stops otherwise.
    _points(line, [("0.5", "0"), ("0.9", line.rng.choice(("1", "2", "5")))], ", ", between=False)
    line.struct.update(form=word, dimension=dimension, format=())


def _poly(line: Line, letter: str, index: int) -> None:
    line.begin(letter, _CONTROLLED[letter], index)
    line.nodes_(2)
    dimension = line.rng.randrange(1, 3)
    line.gap()
    line.lit(line.case("POLY") + line.rng.choice(("", " ")) + f"({dimension})")
    for _ in range(dimension):
        line.gap()
        if letter in "FH":
            line.control()
        elif not line.ng and line.rng.random() < 0.4:
            line.lit("(")
            line.node()
            line.lit(line.rng.choice((",", " ")))
            line.node()
            line.lit(")")
        else:
            line.node()
            line.gap(comma=False)
            line.node()
    low = 2 if line.ng else 1
    count = line.rng.randrange(low, low + 3)
    for position in range(count):
        if position and line.rng.random() < 0.15:
            line.lit(" ; c\n+ ")
            line.comments += 1
            line.coefficient_comments = True
        else:
            line.lit(" ")
        line.add("coefficient", line.rng.choice(("0", "1", "2.5", "-1", "3m")))
    line.struct.update(form="poly", dimension=dimension, coefficients=count)
    if line.ng and letter in "FG" and line.rng.random() < 0.4:
        line.param("m", line.number())


def _lt_table(line: Line, letter: str, index: int) -> None:
    line.begin(letter, _CONTROLLED[letter], index)
    line.nodes_(4)
    line.gap()
    line.lit(line.case("table") + line.rng.choice(("=", " = ", "")))
    _flat(line, _rows(line, 2, 2, 4), line.rng.choice((", ", ",", " ")))
    line.struct.update(form="table", format=())


def _laplace(line: Line, letter: str, index: int) -> None:
    line.begin(letter, _CONTROLLED[letter], index)
    line.nodes_(4)
    line.gap()
    line.lit(line.case("Laplace") + line.rng.choice(("=", " = ")))
    body = line.rng.choice(("2/(1+s/1k)", "1/(1+s*1u)", "k/(s+1)"))
    delimiter = line.rng.choice(("{", ""))
    closing = "}" if delimiter else ""
    line.add("expression", f"{delimiter}{body}{closing}")
    line.struct.update(form="laplace", expression=body, delimiter=delimiter)
    line.params_(("window", "nfft", "mtol"))


def _lossless(line: Line, index: int) -> None:
    line.begin("T", "LosslessLine", index)
    line.nodes_(4)
    impedance = line.rng.choice(("Z0", "Zo", "z0"))
    line.param(impedance, line.number())
    # LTspice's reference lists only `Td=` for the delay, and the library refuses `F=` there.
    if not line.ng or line.rng.random() < 0.5:
        line.param(line.case("TD"), line.number())
    else:
        line.param(line.case("F"), line.number())
        if line.rng.random() < 0.5:
            line.param(line.case("NL"), line.number())
    if line.ng and line.rng.random() < 0.4:
        line.param("IC", line.rng.choice(("0,0,0,0", "1,0,1,0")))


def _model_line(
    line: Line, letter: str, kind: str, index: int, count: int, family: str, grounds: bool = False
) -> None:
    """Nodes, then the model. With ``grounds``, the last node of each half is ``0``: the reference
    node of a Y or P port, which ngspice ignores (the library asks for ground there)."""
    line.begin(letter, kind, index)
    for position in range(count):
        line.gap(comma=True)
        if grounds and position % (count // 2) == count // 2 - 1:
            line.node("0", "ground")  # a mutation may only write another ground spelling
        else:
            line.node()
    line.gap()
    line.model(family)


def _rc(line: Line, index: int) -> None:
    _model_line(line, "U", "RcLine", index, 3, "um")
    line.param(line.case("l"), line.number())
    if line.rng.random() < 0.5:
        line.param(line.case("n"), line.rng.choice(("3", "6", "10")))


def _txl(line: Line, index: int) -> None:
    _model_line(line, "Y", "TxlLine", index, 4, "ym", grounds=True)
    if line.rng.random() < 0.6:
        line.param("len", line.number())


def _cpl(line: Line, index: int) -> None:
    conductors = line.rng.randrange(1, 4)
    _model_line(line, "P", "CoupledLine", index, 2 * conductors + 2, "pm", grounds=True)
    line.struct["conductors"] = conductors
    if line.rng.random() < 0.6:
        line.param("len", line.number())


def _code_model(line: Line, index: int) -> None:
    line.begin("A", "CodeModelDevice", index)
    for position in range(line.rng.randrange(1, 5)):
        line.gap(comma=position > 0)
        start = len(line.text)
        choice = line.rng.randrange(8)
        connections: list[tuple[object, ...]] = []
        vector, before = False, None
        if choice == 0:
            line.node()
            connections.append((None, (line.nodes[-1],), False))
        elif choice in (1, 2):
            single = choice == 1
            options = ("%v", "%i", "%g") if single else ("%vd", "%id")
            written = line.case(options[line.rng.randrange(len(options))])
            line.add("port_type", written, "port_type")
            style = line.rng.randrange(3)
            line.lit(("(", " ", " (")[style])
            line.node()
            names = [line.nodes[-1]]
            if not single:
                line.lit(" ")
                line.node()
                names.append(line.nodes[-1])
            if style != 1:
                line.lit(")")
            connections.append((written, tuple(names), False))
        elif choice == 3:
            line.lit("~")
            line.node()
            connections.append((None, (line.nodes[-1],), False))
        elif choice == 4:
            line.add("null", line.rng.choice(("null", "NULL")))
            connections.append((None, (), True))
        elif choice == 5:
            written = line.case("%vnam")
            line.lit(written)
            line.lit(line.rng.choice((" ", "(")))
            line.control()
            if line.text[-len(line.controls[-1]) - 1] == "(":
                line.lit(")")
            connections.append((written, (), False))
        else:
            vector = True
            if choice == 7:
                before = line.rng.choice(("%v", "%i"))
                line.add("port_type", before, "port_type")
                line.lit(line.rng.choice(("", " ")))
            line.lit(line.rng.choice(("[", "[ ")))
            members = line.rng.randrange(1, 4)
            for member in range(members):
                if member:
                    line.lit(" ")
                cstart = len(line.text)
                if before is None and line.rng.random() < 0.3:
                    line.lit("~")
                line.node()
                line.fields.append(("connection", cstart, len(line.text), line.text[cstart:]))
                connections.append((None, (line.nodes[-1],), False))
            line.lit(line.rng.choice(("]", " ]")))
        if not vector:
            end = len(line.text)
            line.fields.append(("connection", start, end, line.text[start:]))
        line.fields.append(("port", start, len(line.text), line.text[start:]))
        line.ports.append((position, vector, before, tuple(connections)))
    line.gap(comma=True)
    line.model_start = len(line.text)
    line.model("am")


def _osdi(line: Line, index: int) -> None:
    _model_line(line, "N", "OsdiDevice", index, line.rng.randrange(1, 5), "nm")
    for name in line.rng.sample(("l", "w", "m", "as"), line.rng.randrange(3)):
        line.param(name, line.number())


_SPECIAL = (
    "BUF AND OR XOR SCHMITT DFLOP SRFLOP VARISTOR MODULATOR OTA PHASEDET COUNTER SAMPLEHOLD"
).split()


def _special(line: Line, index: int) -> None:
    line.begin("A", "SpecialFunction", index)
    line.nodes_(8)
    line.gap()
    written = line.case(line.rng.choice(_SPECIAL))
    line.add("function", written)
    line.struct["function"] = written
    line.params_(("Vhigh", "Vlow", "Td", "Ref", "Rout", "G"), most=3)


def _analyzer(line: Line, index: int) -> None:
    line.begin("@", "FrequencyAnalyzer", index)
    line.nodes_(2)
    impedance = None
    if line.rng.random() < 0.4:
        line.gap()
        impedance = line.case("zm")
        line.add("flag", impedance)
    line.struct["impedance"] = impedance
    nets: dict[str, str | None] = {"refnode": None, "intnode": None}
    names = ("fstart", "fend", "flist", "nmax", "refnode", "intnode")
    for name in line.rng.sample(names, line.rng.randrange(4)):
        if name in nets:
            net = line.rng.choice(("a", "out", "n1"))
            line.param(name, net)
            nets[name] = net
        elif name == "flist":
            values = " ".join(line.rng.choice(("1k", "2k", "10k")) for _ in range(3))
            line.param(name, values)
        else:
            line.param(name, line.rng.choice(("1", "1k", "{k}")))
    line.struct.update(reference_net=nets["refnode"], intermediate_net=nets["intnode"])


def _probe(line: Line, index: int) -> None:
    line.begin("&", "FraProbe", index)
    line.nodes_(4)
    line.struct["analyzer"] = f"@{index}"


Writer = Callable[[Line, int], None]

_BOTH: dict[str, Writer] = {
    "V-stimulus": lambda line, i: _source(line, "V", i),
    "I-stimulus": lambda line, i: _source(line, "I", i),
    **{
        f"{letter}-transistor": (lambda x: lambda line, i: _transistor(line, x, i))(letter)
        for letter in "QMJZ"
    },
    **{
        f"{letter}-linear": (lambda x: lambda line, i: _linear(line, x, i))(letter)
        for letter in "EGFH"
    },
    "S-switch": lambda line, i: _switch(line, "S", i),
    "W-switch": lambda line, i: _switch(line, "W", i),
    "B-behavioral": _behavioral,
    "C-charge": _charge,
    **{
        f"{letter}-poly": (lambda x: lambda line, i: _poly(line, x, i))(letter) for letter in "EGFH"
    },
    "T-lossless": _lossless,
    "O-lossy": lambda line, i: _model_line(line, "O", "LossyLine", i, 4, "lm"),
    "U-rc": _rc,
}
FORMS: dict[Dialect, dict[str, Writer]] = {
    NG: {
        **_BOTH,
        "E-vol": lambda line, i: _expression_form(line, "E", i, "vol"),
        "G-cur": lambda line, i: _expression_form(line, "G", i, "cur"),
        "E-value": lambda line, i: _expression_form(line, "E", i, "value"),
        "G-value": lambda line, i: _expression_form(line, "G", i, "value"),
        "E-table": lambda line, i: _table(line, "E", i),
        "G-table": lambda line, i: _table(line, "G", i),
        "E-table4": lambda line, i: _four_node_table(line, "E", i),
        "E-freq": _freq,
        "E-gate": _gate,
        "Y-txl": _txl,
        "P-cpl": _cpl,
        "A-code-model": _code_model,
        "N-osdi": _osdi,
    },
    LT: {
        **_BOTH,
        **{
            f"{letter}-value": (lambda x: lambda line, i: _expression_form(line, x, i, "value"))(
                letter
            )
            for letter in "EGFH"
        },
        "L-flux": _flux,
        "E-table": lambda line, i: _lt_table(line, "E", i),
        "G-table": lambda line, i: _lt_table(line, "G", i),
        "E-laplace": lambda line, i: _laplace(line, "E", i),
        "G-laplace": lambda line, i: _laplace(line, "G", i),
        "A-special": _special,
        "@-analyzer": _analyzer,
        "&-probe": _probe,
    },
}


def write_line(dialect: Dialect, form: str, index: int, rng: random.Random) -> Line:
    """One element line of ``form``, designated with ``index``."""
    line = Line(dialect, rng, form)
    FORMS[dialect][form](line, index)
    line.finish()
    return line


# --- the netlist -----------------------------------------------------------------------------


@dataclass
class Written:
    """A generated netlist: its text, and each element with its scope and absolute offset."""

    dialect: Dialect
    text: str
    elements: list[tuple[Line, tuple[str, ...], int]]
    senses: list[tuple[tuple[str, ...], str, tuple[str, str]]]
    scoped: bool


def write_netlist(dialect: Dialect, forms: list[str], rng: random.Random) -> Written:
    """A netlist holding one line of each of ``forms``; some go in a ``.subckt`` when there are
    several."""
    pieces = ["device oracle\n", ".param k=2\n"]
    senses: list[tuple[tuple[str, ...], str, tuple[str, str]]] = []
    elements: list[tuple[Line, tuple[str, ...], int]] = []

    def put(text: str) -> int:
        start = sum(map(len, pieces))
        pieces.append(text)
        return start

    def sense(scope: tuple[str, ...]) -> None:
        for name in SENSES:
            nodes = (name.lower(), "0")
            put(f"{name} {nodes[0]} {nodes[1]} 0\n")
            senses.append((scope, name, nodes))

    sense(())
    inner = [rng.random() < 0.4 for _ in forms] if len(forms) > 1 else [False]
    for index, (form, nested) in enumerate(zip(forms, inner, strict=True)):
        if not nested:
            line = write_line(dialect, form, index + 1, rng)
            elements.append((line, (), put(line.text + "\n")))
    scoped = any(inner)
    if scoped:
        put(f".subckt {_SCOPE} p q\n")
        senses.append(((_SCOPE,), "", ("p", "q")))
        sense((_SCOPE,))
        for index, (form, nested) in enumerate(zip(forms, inner, strict=True)):
            if nested:
                line = write_line(dialect, form, index + 1, rng)
                elements.append((line, (_SCOPE,), put(line.text + "\n")))
        put(rng.choice((".ends\n", f".ends {_SCOPE}\n")))
    families = {model[:-1] for line, _, _ in elements for model in line.models}
    for model in model_lines(families):
        put(model + "\n")
    put(".op\n.end\n")
    return Written(dialect, "".join(pieces), elements, senses, scoped)


def expected_signature(written: Written) -> tuple[tuple[object, ...], ...]:
    """The signature computed from the record: the sense sources, the definition and each line's
    element, port and control entries, in source order."""
    entries: list[tuple[object, ...]] = []
    top = [(scope, name, nodes) for scope, name, nodes in written.senses if not scope]
    for _, name, nodes in top:
        entries.append(("element", (), name, "VoltageSource", nodes))
    for line, scope, _ in written.elements:
        if not scope:
            entries += _line_entries(line, scope)
    if written.scoped:
        ports = next(nodes for scope, name, nodes in written.senses if scope and not name)
        entries.append(("subckt", (), _SCOPE, ports))
        for scope, name, nodes in written.senses:
            if scope and name:
                entries.append(("element", scope, name, "VoltageSource", nodes))
        for line, scope, _ in written.elements:
            if scope:
                entries += _line_entries(line, scope)
    entries.append(("global", ()))
    return tuple(entries)


def _line_entries(line: Line, scope: tuple[str, ...]) -> list[tuple[object, ...]]:
    entries: list[tuple[object, ...]] = [
        ("element", scope, line.designator, line.kind, tuple(line.nodes))
    ]
    if line.kind == "CodeModelDevice":
        entries.append(("ports", scope, line.designator, tuple(line.ports)))
    if line.kind in ("Cccs", "Ccvs", "CurrentSwitch", "CodeModelDevice"):
        entries += [("control", scope, line.designator, name) for name in line.controls]
    return entries


# --- what the parser gives -------------------------------------------------------------------


def _actual_fields(item: Component, base: int) -> list[tuple[str, int, int]]:
    found: list[tuple[str, int, int]] = []

    def put(role: str, span: Any) -> None:
        found.append((role, span.start - base, span.end - base))

    put("designator", item.designator_span)
    if isinstance(item, CodeModelDevice):
        for port in item.ports:
            put("port", port.span)
            for connection in port.connections:
                put("connection", connection.span)
                for node in connection.nodes:
                    put("node", node.span)
                if connection.null:
                    put("null", connection.span)
                if connection.source is not None:
                    put("control", connection.source.span)
    else:
        for node in item.nodes:
            put("node", node.span)
    for name in ("model", "function", "value", "area", "dc", "expression", "charge", "flux"):
        slot = getattr(item, name, None)
        if slot is not None and not isinstance(slot, str):
            role = {"function": "function", "model": "model"}.get(name, "value")
            put("expression" if name in ("expression", "charge", "flux") else role, slot.span)
    ac = getattr(item, "ac", None)
    if ac is not None:
        put("ac", ac.magnitude.span)
        if ac.phase is not None:
            put("ac_phase", ac.phase.span)
    for spec in [getattr(item, "stimulus", None), *getattr(item, "distortion", ())]:
        if spec is None:
            continue
        put("function", spec.name_span)
        for arg in spec.args:
            put("arg", arg.span)
        for param in spec.params:
            put("param", param.name_span)
            put("param_value", param.value.span)
    for flag in getattr(item, "flags", ()):
        put("flag", flag.span)
    impedance = getattr(item, "impedance", None)
    if impedance is not None:
        put("flag", impedance.span)
    for reference in getattr(item, "control", ()) if not isinstance(item, CodeModelDevice) else ():
        put("control", reference.span)
    table = getattr(item, "table", None)
    if table is not None:
        for point in table.points:
            for value in point.values:
                put("point_value", value.span)
    for coefficient in getattr(item, "coefficients", ()):
        put("coefficient", coefficient.span)
    for param in item.params:
        put("param", param.name_span)
        put("param_value", param.value.span)
    return sorted(found)


def _expected_fields(line: Line) -> list[tuple[str, int, int]]:
    # A port type has no span of its own: it is the start of its connection or vector span.
    return sorted((role, start, end) for role, start, end, _ in line.fields if role != "port_type")


def _actual_struct(item: Component, keys: set[str]) -> dict[str, object]:
    table = getattr(item, "table", None)
    expression = getattr(item, "expression", None) or getattr(item, "charge", None)
    expression = expression or getattr(item, "flux", None)
    stimulus = getattr(item, "stimulus", None)
    getters: dict[str, Callable[[], object]] = {
        "form": lambda: getattr(item, "form", None),
        "quantity": lambda: getattr(item, "quantity", None),
        "dimension": lambda: getattr(item, "dimension", None),
        "points": lambda: len(table.points) if table else None,
        "widths": lambda: tuple(len(p.values) for p in table.points) if table else None,
        "layout": lambda: table.layout if table else None,
        "format": lambda: table.format if table else None,
        "coefficients": lambda: len(getattr(item, "coefficients", ())),
        "expression": lambda: expression.text if expression else None,
        "delimiter": lambda: expression.delimiter if expression else None,
        "stimulus": lambda: stimulus.name if stimulus else None,
        "args": lambda: len(stimulus.args) if stimulus else None,
        "distortion": lambda: tuple(spec.name for spec in getattr(item, "distortion", ())),
        "flags": lambda: tuple(_flag_text(item)),
        "area": lambda: getattr(item, "area", None) is not None,
        "function": lambda: item.function.name if isinstance(item, SpecialFunction) else None,
        "impedance": lambda: (
            item.impedance.name
            if isinstance(item, FrequencyAnalyzer) and item.impedance is not None
            else None
        ),
        "reference_net": lambda: _net(item, "reference_net"),
        "intermediate_net": lambda: _net(item, "intermediate_net"),
        "analyzer": lambda: item.analyzer.designator if isinstance(item, FraProbe) else None,
        "conductors": lambda: getattr(item, "conductors", None),
    }
    return {key: getters[key]() for key in keys}


_SOURCE: list[str] = [""]


def _flag_text(item: Component) -> list[str]:
    text = _SOURCE[0]
    return [text[flag.span.start : flag.span.end] for flag in getattr(item, "flags", ())]


def _net(item: Component, name: str) -> str | None:
    node = getattr(item, name, None)
    return None if node is None else str(node.name)


def check(written: Written) -> Netlist:
    """Every assertion of the oracle on one generated netlist; returns the loaded netlist."""
    text = written.text
    try:
        netlist = Netlist.from_text(text, dialect=written.dialect)
    except ParseError as error:
        raise AssertionError(f"oracle parse failure:\n{text}\n{error}") from error
    result = netlist.parse_result
    _SOURCE[0] = text
    assert netlist.to_bytes() == text.encode("utf-8")
    by_designator = {
        (scope, item.designator): item for scope, item in _components(result.items, ())
    }
    for line, scope, start in written.elements:
        item = by_designator[(scope, line.designator)]
        context = f"{line.form}: {line.text!r}"
        assert type(item).__name__ == line.kind, context
        assert (item.span.start, item.span.end) == (start, start + len(line.text) + 1), context
        assert _actual_fields(item, start) == _expected_fields(line), context
        for _, field_start, field_end, written_text in line.fields:
            assert text[start + field_start : start + field_end] == written_text, context
        assert _actual_struct(item, set(line.struct)) == line.struct, context
        assert len(item.trailing_comments) == line.comments, context
        if isinstance(item, FrequencyAnalyzer):
            for name in ("reference_net", "intermediate_net"):
                node = getattr(item, name)
                if node is not None:
                    assert text[node.span.start : node.span.end] == node.name
        if isinstance(item, FraProbe):
            assert item.analyzer.span == item.designator_span, context
    assert netlist.signature().entries == expected_signature(written)
    return netlist


def _components(items: Any, scope: tuple[str, ...]) -> list[tuple[tuple[str, ...], Component]]:
    found: list[tuple[tuple[str, ...], Component]] = []
    for item in items:
        if isinstance(item, Component):
            found.append((scope, item))
        body = getattr(item, "body", None)
        if body is not None and hasattr(item, "ends"):
            found += _components(body, (*scope, item.name))
    return found


# --- the tests -------------------------------------------------------------------------------

_CASES = [(dialect, form) for dialect in (NG, LT) for form in FORMS[dialect]]


@pytest.mark.parametrize(("dialect", "form"), _CASES, ids=[f"{d.value}-{f}" for d, f in _CASES])
@settings(max_examples=15, print_blob=True, deadline=None)
@given(seed=st.integers())
def test_each_form_matches_the_generator(dialect: Dialect, form: str, seed: int) -> None:
    check(write_netlist(dialect, [form], random.Random(seed)))


@pytest.mark.parametrize("dialect", [NG, LT], ids=["ngspice", "ltspice"])
@settings(max_examples=100, print_blob=True, deadline=None)
@given(seed=st.integers())
def test_mixed_netlists_match_the_generator(dialect: Dialect, seed: int) -> None:
    rng = random.Random(seed)
    forms = [rng.choice(list(FORMS[dialect])) for _ in range(rng.randrange(2, 7))]
    check(write_netlist(dialect, forms, rng))


def _mutate(written: Written, rng: random.Random) -> tuple[str, str] | None:
    """The text with one topology token changed, and what was changed; ``None`` if the netlist
    has no such token."""
    choices: list[tuple[int, int, str, Line]] = []
    for line, _, start in written.elements:
        choices += [(start + s, start + e, what, line) for s, e, what in line.topology]
        if line.model_start is not None:
            choices.append((start + line.model_start, start + line.model_start, "port", line))
    if not choices:
        return None
    start, end, what, line = rng.choice(choices)
    old = written.text[start:end]
    if what == "name":
        new = "mut9"
    elif what == "ground":
        new = "GND"
    elif what == "control":
        new = _other(old)
    elif what == "port_type":
        swaps = {"%v": "%i", "%i": "%v", "%g": "%v", "%vd": "%id", "%id": "%vd"}
        new = swaps[old.lower()]
    else:
        new = "mutp "
    return written.text[:start] + new + written.text[end:], f"{what} {old!r} -> {new!r}"


def _other(name: str) -> str:
    return SENSES[1 - SENSES.index(name)]


@pytest.mark.parametrize("dialect", [NG, LT], ids=["ngspice", "ltspice"])
@settings(max_examples=150, print_blob=True, deadline=None)
@given(seed=st.integers())
def test_changing_any_topology_token_changes_the_signature(dialect: Dialect, seed: int) -> None:
    rng = random.Random(seed)
    forms = [rng.choice(list(FORMS[dialect])) for _ in range(rng.randrange(1, 4))]
    written = write_netlist(dialect, forms, rng)
    baseline = Netlist.from_text(written.text, dialect=dialect).signature()
    mutated = _mutate(written, rng)
    assert mutated is not None
    text, what = mutated
    try:
        changed = Netlist.from_text(text, dialect=dialect)
    except ParseError as error:
        raise AssertionError(f"mutated text does not parse ({what}):\n{text}\n{error}") from error
    assert changed.signature() != baseline, what
    assert changed.signature().digest() != baseline.digest(), what


@pytest.mark.parametrize("dialect", [NG, LT], ids=["ngspice", "ltspice"])
@settings(max_examples=60, print_blob=True, deadline=None)
@given(seed=st.integers())
def test_changing_a_value_keeps_the_signature(dialect: Dialect, seed: int) -> None:
    # The converse: a value, an argument, a point, a coefficient or an `@` line's `refnode=` net
    # is not topology (architecture §7.8; decision 0020 item 7).
    rng = random.Random(seed)
    forms = [rng.choice(list(FORMS[dialect])) for _ in range(rng.randrange(1, 4))]
    written = write_netlist(dialect, forms, rng)
    baseline = Netlist.from_text(written.text, dialect=dialect).signature()
    roles = ("value", "arg", "point_value", "coefficient", "ac")
    choices = [
        (start + s, start + e, line)
        for line, _, start in written.elements
        for role, s, e, text in line.fields
        if role in roles or (role == "param_value" and text in ("a", "out", "n1"))
    ]
    if not choices:
        return
    start, end, line = rng.choice(choices)
    replacement = "n1" if written.text[start:end] in ("a", "out") else "7"
    text = written.text[:start] + replacement + written.text[end:]
    assert Netlist.from_text(text, dialect=dialect).signature() == baseline, line.form
