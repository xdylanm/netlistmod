"""Immutable structural and element nodes produced by the dialect parsers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from netlistmod.dialects import Dialect
from netlistmod.model.values import (
    AcSpec,
    ElementReference,
    Flag,
    Identifier,
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
    ``name_span`` covers the name (the parser always sets it; M5 places diagnostics there).
    """

    name: str
    raw: str
    span: Span
    trailing_comments: tuple[Span, ...] = ()
    name_span: Span | None = None


@dataclass(frozen=True, slots=True)
class OpaqueBlock:
    """A preserved ``.control``, conditional or ``.lib`` … ``.endl`` block."""

    kind: Literal["control", "if", "lib"]
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


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """A source function of a V or I line (decision 0013), such as ``PULSE(0 1 1u)``.

    ``name`` is as written. ``args`` holds the values of its list in order, and ``params`` what it
    writes by name: a PWL's ``r=``, ``td=``, scale factors, ``file=`` and repeat count (``for``), a
    wave file's ``wavefile=`` and ``chan=``, and EXTERNAL's ``m=``. A file's path is an
    :class:`Identifier` or a quoted :class:`Formula`, and is never read. ``forever`` marks ``PWL
    REPEAT FOREVER``. ``span`` runs from the name to the end of the last part.
    """

    name: str
    name_span: Span
    args: tuple[Value, ...]
    params: tuple[ParamAssignment, ...]
    span: Span
    forever: bool = False


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
    ``capacitance={c0}`` and similar; it is ``None`` for a positional value. ``flags`` holds an
    LTspice ``noiseless``.
    """

    value: Value | None
    value_keyword: str | None
    model: ModelReference | None
    flags: tuple[Flag, ...] = ()


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
    """Fields shared by V and I.

    ``dc_keyword`` records whether ``DC`` was written before the value. ``flags`` holds an
    LTspice current source's ``load``. ``stimulus`` is the source function, and ``distortion``
    holds ngspice's ``DISTOF1`` and ``DISTOF2``.
    """

    dc: Value | None
    dc_keyword: bool
    ac: AcSpec | None
    flags: tuple[Flag, ...] = ()
    stimulus: SourceSpec | None = None
    distortion: tuple[SourceSpec, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class VoltageSource(_IndependentSource):
    """A ``V`` line."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CurrentSource(_IndependentSource):
    """An ``I`` line."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Diode(Component):
    """A ``D`` line; the model is mandatory and ``flags`` holds ``off``.

    ``area`` is the positional area of an LTspice diode (``D1 a b dm 2``).
    """

    model: ModelReference
    flags: tuple[Flag, ...]
    area: Value | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class _Transistor(Component):
    """Fields shared by Q, M, J and Z (decision 0014).

    ``nodes`` are the nodes as written: an omitted substrate is not added, although ngspice
    grounds it (§7.8). ``area`` is a positional area (J and Z, and an LTspice Q); a named
    ``area=`` is a parameter. ``flags`` holds ``off`` and, on an ngspice VDMOS, ``thermal``.
    """

    model: ModelReference
    flags: tuple[Flag, ...]
    area: Value | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class BipolarTransistor(_Transistor):
    """A ``Q`` line."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Mosfet(_Transistor):
    """An ``M`` line, a MOSFET or a VDMOS."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Jfet(_Transistor):
    """A ``J`` line."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Mesfet(_Transistor):
    """A ``Z`` line: a MESFET, or on LTspice an IGBT."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SubcktInstance(Component):
    """An ``X`` line: its nodes, the subcircuit name and the parameter overrides."""

    subckt: SubcktReference


@dataclass(frozen=True, slots=True, kw_only=True)
class _DotCommand:
    """Fields shared by every typed dot-command (decision 0005).

    ``keyword`` is the keyword as written (``.TRAN``); ``span`` is the item span, which tiles
    the source like every item, and ``trailing_comments`` holds every end-of-line comment of
    the statement in source order. Sub-spans cover exactly their text, never a separator.
    """

    keyword: str
    keyword_span: Span
    span: Span
    trailing_comments: tuple[Span, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ParamStatement(_DotCommand):
    """A ``.param`` line: one or more ``name=value`` assignments."""

    assignments: tuple[ParamAssignment, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelStatement(_DotCommand):
    """A ``.model`` line; ``parenthesized`` records whether the parameters are in ``( … )``.

    ``model_type`` is the type as written (``D``, ``npn``, an XSPICE type); it is not checked.
    ``open_paren_span`` and ``close_paren_span`` cover the ``(`` and ``)`` tokens of a
    parenthesized line (``None`` otherwise), so a parameter can be added to ``d()`` (M6).
    ``ako`` is the base model of an LTspice ``.model slow ako:fast d(...)``. ``flags`` holds a
    bare ``pchan`` or ``nchan`` (decision 0014).
    """

    name: str
    name_span: Span
    model_type: str
    model_type_span: Span
    params: tuple[ParamAssignment, ...]
    parenthesized: bool
    open_paren_span: Span | None = None
    close_paren_span: Span | None = None
    ako: ModelReference | None = None
    flags: tuple[Flag, ...] = ()


@dataclass(frozen=True, slots=True)
class EndsLine:
    """The ``.ends`` line closing a subcircuit definition.

    ``name`` is the optional name as written; it is not checked against the definition.
    """

    name: str | None
    name_span: Span | None
    span: Span
    trailing_comments: tuple[Span, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class SubcktDefinition(_DotCommand):
    """A ``.subckt`` … ``.ends`` block, which contains its body.

    ``header_span`` covers the ``.subckt`` line (with its continuations), the ``body`` items
    tile the text between the header and the ``.ends`` line, and ``ends`` covers that line.
    ``params`` holds the default parameter values; ``trailing_comments`` those of the header.
    """

    name: str
    name_span: Span
    ports: tuple[Node, ...]
    params: tuple[ParamAssignment, ...]
    body: tuple[BodyItem, ...]
    ends: EndsLine
    header_span: Span


@dataclass(frozen=True, slots=True, kw_only=True)
class Directive(_DotCommand):
    """Base of the typed analysis, option and output directives (top level only)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class TranDirective(Directive):
    """``.tran tstep tstop [tstart [tmax]] [uic]``.

    In LTspice ``tstep`` may be left out (``.tran 1m``), and ``modifiers`` holds the other
    keywords (``startup``, ``steady``, ``savestate=...``).
    """

    tstep: Value | None
    tstop: Value
    tstart: Value | None
    tmax: Value | None
    uic: Flag | None
    modifiers: tuple[OptionItem, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class AcDirective(Directive):
    """``.ac dec|oct|lin points fstart fstop``; ``variation`` is the keyword as written.

    LTspice also has ``.ac list f1 f2 ...`` (``frequencies``, the range fields ``None``) and
    ``.ac file=name`` (``file``, ``variation`` is ``file``).
    """

    variation: str
    variation_span: Span
    points: Value | None
    fstart: Value | None
    fstop: Value | None
    frequencies: tuple[Value, ...] = ()
    file: Identifier | None = None


@dataclass(frozen=True, slots=True)
class DcSweep:
    """One ``.dc`` sweep: the swept name and its range; ``span`` runs from source to increment.

    An LTspice sweep may name a ``variation`` before the source, or hold a ``values`` list or a
    ``file`` in place of the range (``span`` then ends with the last of them).
    """

    source: str
    source_span: Span
    start: Value | None
    stop: Value | None
    increment: Value | None
    span: Span
    variation: str | None = None
    values: tuple[Value, ...] = ()
    file: Identifier | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DcDirective(Directive):
    """``.dc`` with one or two sweeps (up to three in LTspice)."""

    sweeps: tuple[DcSweep, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class OpDirective(Directive):
    """``.op``."""


@dataclass(frozen=True, slots=True)
class OptionItem:
    """One ``.options`` item, ``name`` or ``name=value``; ``span`` covers both."""

    name: str
    name_span: Span
    value: Value | Identifier | None
    span: Span


@dataclass(frozen=True, slots=True, kw_only=True)
class OptionsDirective(Directive):
    """``.options`` or ``.option`` with one or more items."""

    options: tuple[OptionItem, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class TempDirective(Directive):
    """``.temp value``; LTspice allows more values (``others``)."""

    value: Value
    others: tuple[Value, ...] = ()


@dataclass(frozen=True, slots=True)
class NodeCondition:
    """``v(node)=value``, ``all=value`` (``node is None``, ngspice ``.nodeset`` only), or an
    inductor current ``i(L1)=value`` (``current`` is set, LTspice ``.ic`` only).

    ``span`` runs from ``v(`` (or ``all``, or ``i(``) to the end of the value.
    """

    node: Node | None
    value: Value
    span: Span
    current: ElementReference | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class IcDirective(Directive):
    """``.ic v(node)=value …``."""

    conditions: tuple[NodeCondition, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class NodesetDirective(Directive):
    """``.nodeset v(node)=value …`` or ``.nodeset all=value``."""

    conditions: tuple[NodeCondition, ...]


@dataclass(frozen=True, slots=True)
class OutputVector:
    """One ``.save`` vector; ``text`` is the source slice of ``span`` (blanks included).

    For the standard forms ``v(n)``, ``v(n1, n2)``, their AC variants (``vr``, ``vi``, ``vm``,
    ``vp``, ``vdb``) and ``i(src)``, ``function`` is the function name as written and
    ``nodes`` (voltages) or ``source`` (current) hold the arguments with their spans. A plain
    name (a node, ``src#branch`` or ``all``) and ``@dev[param]`` have ``function=None`` and are
    resolved in M5 from ``text``.
    """

    text: str
    span: Span
    function: str | None = None
    nodes: tuple[Node, ...] = ()
    source: ElementReference | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SaveDirective(Directive):
    """``.save`` with one or more output vectors."""

    vectors: tuple[OutputVector, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class MeasureDirective(Directive):
    """``.meas`` or ``.measure``, typed shallowly.

    ``analysis`` (``dc``, ``ac``, ``tran``, ``sp``; in LTspice also ``noise`` and ``op``, or
    ``None`` when it is left out; as written) and ``result`` are fields; the
    rest of the statement is ``body_text``, the source slice of ``body_span``, which runs from
    the first to the last text token (comments on earlier lines of a continued statement are
    inside it; those are also listed in ``trailing_comments``).
    """

    analysis: str | None
    analysis_span: Span | None
    result: str
    result_span: Span
    body_text: str
    body_span: Span


@dataclass(frozen=True, slots=True, kw_only=True)
class StepDirective(Directive):
    """An LTspice ``.step`` (decision 0009): one nested sweep of one quantity.

    ``kind`` says what ``name`` is: a parameter (``.step param x``), a source (``.step V1``), the
    temperature (``.step temp``) or a model parameter (``.step NPN 2N2222(VAF)``; ``model_type``
    is then ``NPN``, ``name`` is ``2N2222(VAF)`` and ``model`` refers to ``2N2222``).
    ``variation`` is ``oct``, ``dec`` or ``lin``
    as written, if any. The sweep is a range (``start``, ``stop``, ``increment``), a ``values``
    list or a ``file``.
    """

    kind: Literal["param", "source", "temp", "model"]
    name: str
    name_span: Span
    model_type: Identifier | None
    model: ModelReference | None
    variation: str | None
    variation_span: Span | None
    start: Value | None
    stop: Value | None
    increment: Value | None
    values: tuple[Value, ...]
    file: Identifier | None


@dataclass(frozen=True, slots=True, kw_only=True)
class GlobalDirective(_DotCommand):
    """``.global node …`` (top level only): nodes shared by every subcircuit definition.

    It changes connectivity, so it is topology (decision 0006), not a :class:`Directive`.
    """

    nodes: tuple[Node, ...]


BodyItem: TypeAlias = (
    BlankLine
    | CommentLine
    | UnknownDirective
    | OpaqueBlock
    | OpaqueStatement
    | ParamStatement
    | ModelStatement
    | SubcktDefinition
    | Resistor
    | Capacitor
    | Inductor
    | MutualCoupling
    | VoltageSource
    | CurrentSource
    | Diode
    | BipolarTransistor
    | Mosfet
    | Jfet
    | Mesfet
    | SubcktInstance
)
"""An item allowed in a subcircuit body (decision 0005); ``OpaqueBlock`` is an ``.if`` block."""

TopLevelItem: TypeAlias = (
    BodyItem
    | Title
    | TitleDirective
    | End
    | TranDirective
    | AcDirective
    | DcDirective
    | OpDirective
    | OptionsDirective
    | TempDirective
    | IcDirective
    | NodesetDirective
    | SaveDirective
    | MeasureDirective
    | StepDirective
    | GlobalDirective
)


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Top-level items whose spans tile the source, ending with :class:`End` and blank lines.

    ``dialect`` is the dialect the source was parsed with, so the document layer's name rules
    follow it.
    """

    items: tuple[TopLevelItem, ...]
    dialect: Dialect
