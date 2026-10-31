"""Immutable structural and element nodes produced by the ngspice parser."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from netlistmod.model.values import (
    AcSpec,
    ElementReference,
    Flag,
    ModelReference,
    ParamAssignment,
    SubcktReference,
    Value,
)
from netlistmod.source import Span


@dataclass(frozen=True, slots=True)
class Title:
    """The first line of the netlist: an implicit title or an explicit ``.title`` statement.

    The whole title text is a single token; ``;``, ``$`` and ``//`` do not start a comment in it.
    """

    text: str
    explicit: bool
    span: Span


@dataclass(frozen=True, slots=True)
class TitleDirective:
    """A ``.title`` statement after the first line; it replaces the displayed title."""

    text: str
    span: Span


@dataclass(frozen=True, slots=True)
class BlankLine:
    """A whitespace-only physical line."""

    span: Span


@dataclass(frozen=True, slots=True)
class CommentLine:
    """A full-line comment, retained verbatim through its source span."""

    text: str
    span: Span


@dataclass(frozen=True, slots=True)
class UnknownDirective:
    """An untyped dot-command whose exact statement text is preserved.

    ``raw`` runs from the name to the end of the last non-comment text, so it excludes comments
    after that text but includes those on earlier lines of a continued statement.
    ``trailing_comments`` holds every end-of-line comment of the statement in source order.
    """

    name: str
    raw: str
    span: Span
    trailing_comments: tuple[Span, ...] = ()


@dataclass(frozen=True, slots=True)
class OpaqueBlock:
    """A preserved ``.control`` or conditional block."""

    kind: Literal["control", "if"]
    span: Span


@dataclass(frozen=True, slots=True)
class OpaqueStatement:
    """An opaque ``.include`` or ``.lib`` statement; ``raw`` and comments as in UnknownDirective."""

    kind: Literal["include", "lib"]
    raw: str
    span: Span
    trailing_comments: tuple[Span, ...] = ()


@dataclass(frozen=True, slots=True)
class End:
    """The required ``.end`` statement, including its terminator."""

    span: Span


@dataclass(frozen=True, slots=True)
class Node:
    """An element terminal as written; net identity (ground aliases, case) is defined in M5."""

    name: str
    span: Span


@dataclass(frozen=True, slots=True, kw_only=True)
class Component:
    """Base of every element line; only its subclasses are produced by the parser.

    ``span`` is the item span (it tiles the source like every top-level item). The designator,
    each node and each value have their own spans, which slice back to exactly their text.
    ``trailing_comments`` holds every end-of-line comment of the element in source order.
    """

    designator: str
    designator_span: Span
    nodes: tuple[Node, ...]
    params: tuple[ParamAssignment, ...]
    span: Span
    trailing_comments: tuple[Span, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class _TwoTerminal(Component):
    """Fields shared by R, C and L: a value, a model, or both (architecture §5.3).

    ``value_keyword`` is the keyword as written when the value is given as ``r=1k``,
    ``capacitance={c0}`` and similar; it is ``None`` for a positional value.
    """

    value: Value | None
    value_keyword: str | None
    model: ModelReference | None


@dataclass(frozen=True, slots=True, kw_only=True)
class Resistor(_TwoTerminal):
    """An ``R`` line."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Capacitor(_TwoTerminal):
    """A ``C`` line."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Inductor(_TwoTerminal):
    """An ``L`` line."""


@dataclass(frozen=True, slots=True, kw_only=True)
class MutualCoupling(Component):
    """A ``K`` line; its inductor references are topology but not nets, so ``nodes`` is empty."""

    inductors: tuple[ElementReference, ...]
    value: Value


@dataclass(frozen=True, slots=True, kw_only=True)
class _IndependentSource(Component):
    """Fields shared by V and I (phase 1: DC and AC only).

    ``dc_keyword`` records whether ``DC`` was written before the value.
    """

    dc: Value | None
    dc_keyword: bool
    ac: AcSpec | None


@dataclass(frozen=True, slots=True, kw_only=True)
class VoltageSource(_IndependentSource):
    """A ``V`` line."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CurrentSource(_IndependentSource):
    """An ``I`` line."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Diode(Component):
    """A ``D`` line; the model is mandatory and ``flags`` holds ``off``."""

    model: ModelReference
    flags: tuple[Flag, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class SubcktInstance(Component):
    """An ``X`` line: its nodes, the subcircuit name and the parameter overrides."""

    subckt: SubcktReference


TopLevelItem: TypeAlias = (
    Title
    | TitleDirective
    | BlankLine
    | CommentLine
    | UnknownDirective
    | OpaqueBlock
    | OpaqueStatement
    | End
    | Resistor
    | Capacitor
    | Inductor
    | MutualCoupling
    | VoltageSource
    | CurrentSource
    | Diode
    | SubcktInstance
)


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Top-level items whose spans tile the source, ending with :class:`End` and blank lines."""

    items: tuple[TopLevelItem, ...]
