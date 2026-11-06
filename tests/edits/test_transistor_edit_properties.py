"""Edit invariants on generated transistor lines (M13 T9, T5 tier, Hypothesis).

Q, M, J and Z lines with every node count the dialect allows, a positional area where it
writes one, flags, parameters, blanks, tabs, ``+`` continuations and trailing comments. No
sequence of the transistor edits may change the signature, and each edit is idempotent.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from hypothesis import given, settings
from hypothesis import strategies as st

from netlistmod import BipolarTransistor, Dialect, Jfet, Mesfet, Mosfet, Netlist
from tests.support.dialects import current_dialect

Operation = Callable[[Netlist], Netlist]
_VALUES = ["2", "3.3", "{k}"]
_MODELS = {"Q": ("NPN", "PNP"), "M": ("NMOS", "PMOS"), "J": ("NJF", "PJF"), "Z": ("NMF", "PMF")}


@dataclass(frozen=True)
class _Line:
    letter: str
    nodes: int
    area: bool
    params: tuple[str, ...]
    off: bool


def _node_counts(letter: str, dialect: Dialect) -> list[int]:
    if letter in "JZ":
        return [3]
    return [3, 4, 5] if dialect is Dialect.NGSPICE else [3, 4]


def _params(letter: str, dialect: Dialect) -> list[str]:
    """Instance parameters each dialect accepts on ``letter`` (decision 0014 item 6)."""
    if dialect is Dialect.NGSPICE:
        extra = {"Q": ["area"], "M": ["W"]}.get(letter, [])
        return ["temp", "m", *extra]
    return {"Q": ["temp"], "M": ["temp", "m", "W"], "J": ["temp"], "Z": ["temp", "m"]}[letter]


def _positional_area(letter: str, dialect: Dialect) -> bool:
    return letter in "JZ" or (letter == "Q" and dialect is Dialect.LTSPICE)


@st.composite
def _lines(draw: st.DrawFn, letter: str, dialect: Dialect) -> _Line:
    names = _params(letter, dialect)
    return _Line(
        letter,
        draw(st.sampled_from(_node_counts(letter, dialect))),
        _positional_area(letter, dialect) and draw(st.booleans()),
        tuple(draw(st.lists(st.sampled_from(names), unique=True, max_size=len(names)))),
        draw(st.booleans()),
    )


@st.composite
def _netlists(draw: st.DrawFn) -> tuple[str, list[_Line]]:
    dialect = current_dialect()
    lines = [draw(_lines(letter, dialect)) for letter in "QMJZ"]
    gap = st.sampled_from([" ", "  ", "\t", " \t "])
    out = ["generated transistors", ".param k=2"]
    for index, line in enumerate(lines):
        nodes = [f"{line.letter.lower()}n{i}" for i in range(line.nodes)]
        if line.nodes > 3 and draw(st.booleans()):
            nodes[3] = "0"
        fields = [f"{line.letter}{index}", *nodes, f"{line.letter.lower()}a"]
        if line.area:
            fields.append("2")
        if line.off:
            fields.append("off")
        fields += [f"{name}=1" for name in line.params]
        text = fields[0]
        for field in fields[1:]:
            text += ("\n+ " if draw(st.integers(0, 5)) == 0 else draw(gap)) + field
        if draw(st.booleans()):
            text += " ; note"
        out.append(text)
        first, second = _MODELS[line.letter]
        out.append(f".model {line.letter.lower()}a {first}")
        out.append(f".model {line.letter.lower()}b {second}")
    out += [".op", ".end", ""]
    return "\n".join(out), lines


@st.composite
def _operations(draw: st.DrawFn, lines: list[_Line]) -> tuple[str, Operation]:
    dialect = current_dialect()
    value = draw(st.sampled_from(_VALUES))
    choices: list[tuple[str, Operation]] = []
    for index, line in enumerate(lines):
        name = f"{line.letter}{index}"
        model = f"{line.letter.lower()}b"
        choices.append((f"set_model {name}", lambda n, d=name, m=model: n.set_model(d, m)))
        for param in _params(line.letter, dialect):
            choices.append(
                (f"set_param {name} {param}", lambda n, d=name, p=param: n.set_param(d, p, value))
            )
        if _positional_area(line.letter, dialect):
            choices.append((f"area {name}", lambda n, d=name: n.set_param(d, "area", value)))
        choices.append(
            (
                f"set_model_param {model}",
                lambda n, m=model: n.set_model_param(m, "kp", value),
            )
        )
    return draw(st.sampled_from(choices))


@st.composite
def _cases(draw: st.DrawFn) -> tuple[str, list[tuple[str, Operation]]]:
    text, lines = draw(_netlists())
    return text, draw(st.lists(_operations(lines), min_size=1, max_size=5))


@settings(max_examples=150, deadline=None)
@given(_cases())
def test_no_sequence_of_transistor_edits_changes_the_signature(
    case: tuple[str, list[tuple[str, Operation]]],
) -> None:
    text, steps = case
    netlist = Netlist.from_text(text, dialect=current_dialect())
    signature = netlist.signature()
    for description, operation in steps:
        edited = operation(netlist)
        assert edited.signature() == signature, description
        assert operation(edited).to_bytes() == edited.to_bytes(), f"{description} twice"
        netlist = edited


@settings(max_examples=60, deadline=None)
@given(_netlists())
def test_generated_transistor_lines_round_trip(case: tuple[str, list[_Line]]) -> None:
    text, lines = case
    netlist = Netlist.from_text(text, dialect=current_dialect())
    assert netlist.to_bytes() == text.encode("utf-8")
    kinds = (BipolarTransistor, Mosfet, Jfet, Mesfet)
    transistors = [line.item for line in netlist.lines if isinstance(line.item, kinds)]
    assert [len(item.nodes) for item in transistors] == [line.nodes for line in lines]
