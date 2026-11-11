"""Immutable structural and element nodes produced by the dialect parsers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from netlistmod.dialects import Dialect
from netlistmod.model.values import (
    AcSpec,
    ElementReference,
    Flag,
    Formula,
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
    """A ``C`` line. ``charge`` is the expression of the charge form (ngspice ``q=``, LTspice
    ``Q=``; decision 0016), and ``value`` is then ``None``."""

    charge: Formula | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Inductor(_TwoTerminal):
    """An ``L`` line. ``flux`` is the expression of LTspice's ``Flux=`` form (decision 0016), and
    ``value`` is then ``None``; LTspice's hysteretic core has no value and its parameters."""

    flux: Formula | None = None


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
class Transistor(Component):
    """Fields shared by Q, M, J and Z (decision 0014).

    ``nodes`` are the nodes as written: a 3-node Q's substrate is not added, although ngspice
    grounds it (§7.8). ``area`` is a positional area (J and Z, and an LTspice Q); a named
    ``area=`` is a parameter. ``flags`` holds ``off`` and, on an ngspice VDMOS, ``thermal``.
    """

    model: ModelReference
    flags: tuple[Flag, ...]
    area: Value | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class BipolarTransistor(Transistor):
    """A ``Q`` line."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Mosfet(Transistor):
    """An ``M`` line, a MOSFET or a VDMOS."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Jfet(Transistor):
    """A ``J`` line."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Mesfet(Transistor):
    """A ``Z`` line: a MESFET, or on LTspice an IGBT."""


@dataclass(frozen=True, slots=True)
class TablePoint:
    """One point of a :class:`Table`: two values ``(x, y)``, or three for FREQ ``(f, mag, phase)``.

    ``span`` runs from the first value to the last, parentheses excluded.
    """

    values: tuple[Value, ...]
    span: Span


@dataclass(frozen=True, slots=True)
class Table:
    """The points of a TABLE, ``table=``, FREQ or gate line (decision 0017 item 1).

    ``layout`` is ``"pairs"`` when each point is in its own parentheses and ``"flat"`` when one
    parenthesised list holds every value. ``format`` is FREQ's words as written (``DB``, ``MAG``,
    ``DEG``, ``RAD``, ``R_I``), empty for the other forms. ``span`` runs over the points, from the
    first opening parenthesis to the last closing one.
    """

    points: tuple[TablePoint, ...]
    layout: Literal["pairs", "flat"]
    format: tuple[str, ...]
    span: Span


@dataclass(frozen=True, slots=True, kw_only=True)
class ControlledSource(Component):
    """Fields shared by the dependent sources E, F, G and H (decisions 0015, 0016 and 0017).

    A linear line has ``value``, the gain: a voltage gain, transconductance, current gain or
    transresistance. Every other form has ``value`` ``None`` and ``form``, its keyword in lower
    case: ``"vol"``, ``"cur"`` or ``"value"`` (an ``expression``), ``"table"``, ``"poly"``,
    ``"laplace"``, ``"freq"``, ``"and"``, ``"or"``, ``"nand"`` or ``"nor"``.

    ``expression`` is the formula the line writes: the expression forms', ngspice's ``TABLE`` and
    ``FREQ`` input, and LTspice's ``Laplace=`` transfer function. ``table`` holds the points of
    TABLE, ``table=``, FREQ and the gates. ``dimension`` is POLY's or a gate's ``N`` as written,
    and ``coefficients`` POLY's coefficients. ``params`` holds ``m=`` (ngspice G, and F and G
    POLY) and LTspice's ``window=``, ``nfft=`` and ``mtol=``.
    """

    value: Value | None = None
    expression: Formula | None = None
    form: str | None = None
    table: Table | None = None
    dimension: int | None = None
    coefficients: tuple[Value, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Vcvs(ControlledSource):
    """An ``E`` line. ``nodes`` are the output pair, then the control pair."""

    @property
    def control_nodes(self) -> tuple[Node, ...]:
        """The positive and negative control nodes."""
        return self.nodes[2:]


@dataclass(frozen=True, slots=True, kw_only=True)
class Vccs(ControlledSource):
    """A ``G`` line. ``nodes`` are the output pair, then the control pair."""

    @property
    def control_nodes(self) -> tuple[Node, ...]:
        """The positive and negative control nodes."""
        return self.nodes[2:]


@dataclass(frozen=True, slots=True, kw_only=True)
class Cccs(ControlledSource):
    """An ``F`` line. ``control`` names the sources whose currents control it: one for the
    linear form, ``N`` in line order for POLY, and none for an LTspice ``value=`` line (its
    expression reads the currents)."""

    control: tuple[ElementReference, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Ccvs(ControlledSource):
    """An ``H`` line. ``control`` names the sources whose currents control it: one for the
    linear form, ``N`` in line order for POLY, and none for an LTspice ``value=`` line (its
    expression reads the currents)."""

    control: tuple[ElementReference, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Switch(Component):
    """Fields shared by S and W (decision 0015): the model and the initial state in ``flags``."""

    model: ModelReference
    flags: tuple[Flag, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class VoltageSwitch(Switch):
    """An ``S`` line. ``nodes`` are the switch pair, then the control pair."""

    @property
    def control_nodes(self) -> tuple[Node, ...]:
        """The positive and negative control nodes."""
        return self.nodes[2:]


@dataclass(frozen=True, slots=True, kw_only=True)
class CurrentSwitch(Switch):
    """A ``W`` line. ``control`` holds the one source whose current controls it."""

    control: tuple[ElementReference, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class TransmissionLine(Component):
    """Base of the transmission lines T, O, U, Y and P (decision 0019), for ``isinstance``.

    ``nodes`` are every node as written; every one is topology. The named parameters are in
    ``params``.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class _TwoPortLine(TransmissionLine):
    """A line with two ports, each a set of nodes and then its reference node."""

    @property
    def port1(self) -> tuple[Node, ...]:
        """Port 1's nodes: its signal node or nodes, then its reference node."""
        return self.nodes[: len(self.nodes) // 2]

    @property
    def port2(self) -> tuple[Node, ...]:
        """Port 2's nodes: its signal node or nodes, then its reference node."""
        return self.nodes[len(self.nodes) // 2 :]


@dataclass(frozen=True, slots=True, kw_only=True)
class LosslessLine(_TwoPortLine):
    """A ``T`` line: four nodes and no model. ``params`` holds ``Z0=`` (or ``Zo=``), then ``TD=``,
    or ``F=`` with an optional ``NL=``, and on ngspice ``IC=``, whose value is a
    :class:`~netlistmod.model.values.ValueList` of four values (V1, I1, V2, I2)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class LossyLine(_TwoPortLine):
    """An ``O`` line: four nodes and an ``LTRA`` model, and nothing after it."""

    model: ModelReference


@dataclass(frozen=True, slots=True, kw_only=True)
class RcLine(TransmissionLine):
    """A ``U`` line read as a uniform RC line (URC): three nodes (the two ends and the capacitance
    node), a ``URC`` model, then ``l=`` and an optional ``n=`` in ``params``. It has no ports."""

    model: ModelReference


@dataclass(frozen=True, slots=True, kw_only=True)
class TxlLine(_TwoPortLine):
    """An ngspice ``Y`` line: four nodes, whose second and fourth are ground (ngspice ignores
    them), a ``TXL`` model and an optional ``len=`` in ``params``."""

    model: ModelReference


@dataclass(frozen=True, slots=True, kw_only=True)
class CoupledLine(_TwoPortLine):
    """An ngspice ``P`` line: ``2X+2`` nodes for ``X`` coupled lines, a ``CPL`` model and an
    optional ``len=`` in ``params``. Each port is its ``X`` nodes and then its reference node,
    which is ground (ngspice ignores it)."""

    model: ModelReference

    @property
    def conductors(self) -> int:
        """The number of coupled lines, ``X``."""
        return len(self.nodes) // 2 - 1


@dataclass(frozen=True, slots=True, kw_only=True)
class BehavioralSource(Component):
    """A ``B`` line (decision 0016).

    ``quantity`` is the keyword in lower case: ``"v"`` or ``"i"``, and on LTspice also ``"r"`` or
    ``"p"``. ``expression`` is the formula, with ``delimiter`` ``""`` when it is written bare; a
    bare expression's text runs across its continuation lines as written. ``params`` holds the
    trailing parameters (ngspice ``tc1=`` …, LTspice ``ic=`` …).
    """

    quantity: str
    expression: Formula


@dataclass(frozen=True, slots=True)
class CodeModelConnection:
    """One connection of an ngspice code-model port (decision 0020 item 4).

    ``port_type`` is the type as written (``%v``, ``%vd``, ``%vnam`` …), or ``None``. ``nodes``
    holds its node, or two for a differential type, without ``~``: ``inverted`` records a ``~``.
    ``null`` marks an unconnected port, and ``source`` names the source of a ``%vnam``; both have
    no nodes. ``span`` runs from the type (or ``~``, or the node) to the end of the connection.
    """

    port_type: str | None
    nodes: tuple[Node, ...]
    inverted: bool
    null: bool
    source: ElementReference | None
    span: Span


@dataclass(frozen=True, slots=True)
class CodeModelPort:
    """One port of an ngspice code-model line: a connection, or a vector ``[ … ]`` of them.

    ``vector`` is ``True`` for a vector, whose ``span`` includes its brackets. ``port_type`` is a
    type written before the vector (``%v[a b]``), which applies to each of its connections that
    has none of its own; it is ``None`` for a scalar port, whose type is on its connection.
    """

    vector: bool
    connections: tuple[CodeModelConnection, ...]
    span: Span
    port_type: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CodeModelDevice(Component):
    """An ngspice ``A`` line, a code model instance (decision 0020 items 2 and 4).

    ``ports`` holds the ports in order, and ``model`` the model, the last name on the line.
    ``nodes`` is every node of every port in order, without ``null`` and without ``%vnam``
    sources, so the topology queries see it as any other element. The line takes no parameters;
    a code model's values are on its ``.model``.
    """

    model: ModelReference
    ports: tuple[CodeModelPort, ...]

    @property
    def control(self) -> tuple[ElementReference, ...]:
        """The sources of the ``%vnam`` connections, in line order: controlling references, like
        those of F and H (decision 0015 item 3)."""
        return tuple(
            connection.source
            for port in self.ports
            for connection in port.connections
            if connection.source is not None
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class OsdiDevice(Component):
    """An ngspice ``N`` line, an OSDI (Verilog-A) device: nodes, the model, then the named
    instance parameters in ``params`` (decision 0020 item 6). The module defines the node count,
    which the library does not check."""

    model: ModelReference


@dataclass(frozen=True, slots=True, kw_only=True)
class SpecialFunction(Component):
    """An LTspice ``A`` line, a special function (decision 0020 items 2, 3 and 7): eight nodes,
    the ``function`` as written (``BUF``, ``OTA`` …), then the named parameters in ``params``."""

    function: Identifier

    @property
    def inputs(self) -> tuple[Node, ...]:
        """Nodes 1 to 5, the inputs."""
        return self.nodes[:5]

    @property
    def outputs(self) -> tuple[Node, ...]:
        """Nodes 6 and 7, the inverted and the true output."""
        return self.nodes[5:7]

    @property
    def common(self) -> Node:
        """Node 8, the common node the outputs refer to."""
        return self.nodes[7]


@dataclass(frozen=True, slots=True, kw_only=True)
class FrequencyAnalyzer(Component):
    """An LTspice ``@`` line, the frequency response analyzer (decision 0020 items 2 and 7).

    ``nodes`` are its two terminals. ``impedance`` is the ``zm`` flag, or ``None``. ``params``
    holds the named parameters in order; ``flist=``, ``pp=``, ``nmax=`` and ``ac=`` may hold a
    :class:`~netlistmod.model.values.ValueList`. ``refnode=`` and ``intnode=`` are parameters
    whose value is a net name, an :class:`~netlistmod.model.values.Identifier`; the nets they
    name are ``reference_net`` and ``intermediate_net``, which the analyzer measures. They are
    node references, not terminals: they are not in ``nodes`` or the signature.
    """

    impedance: Flag | None
    reference_net: Node | None = None
    intermediate_net: Node | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class FraProbe(Component):
    """An LTspice ``&`` line, a frequency response probe (decision 0020 items 2 and 8): four nodes,
    the output pair and then the input pair.

    ``analyzer`` names the ``@`` with the probe's suffix (``&1`` measures with ``@1``). It is not
    written on the line, so its span is the probe's designator. It is resolved in the probe's
    scope; it is not topology.
    """

    analyzer: ElementReference

    @property
    def output_pair(self) -> tuple[Node, ...]:
        """Nodes 1 and 2."""
        return self.nodes[:2]

    @property
    def input_pair(self) -> tuple[Node, ...]:
        """Nodes 3 and 4."""
        return self.nodes[2:]


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
    ``ako`` is the base model of an LTspice ``.model slow ako:fast d(...)``. ``flags`` holds the
    bare flags in source order: ``pchan`` or ``nchan`` (decision 0014) and, on an ngspice
    ``LTRA`` model, LTRA's flags (``nosteplimit``, ``steplimit``, ``nocontrol``, ``lininterp``,
    ``mixedinterp``, ``truncnr``, ``truncdontcut``; decision 0019 item 8).
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
    | Vcvs
    | Vccs
    | Cccs
    | Ccvs
    | VoltageSwitch
    | CurrentSwitch
    | BehavioralSource
    | LosslessLine
    | LossyLine
    | RcLine
    | TxlLine
    | CoupledLine
    | CodeModelDevice
    | OsdiDevice
    | SpecialFunction
    | FrequencyAnalyzer
    | FraProbe
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


# What messages call each element (review R3): the edit errors and MODEL_TYPE_MISMATCH.
ELEMENT_NAMES: dict[type[Component], str] = {
    Resistor: "resistor",
    Capacitor: "capacitor",
    Inductor: "inductor",
    MutualCoupling: "coupling",
    VoltageSource: "voltage source",
    CurrentSource: "current source",
    Diode: "diode",
    BipolarTransistor: "bipolar transistor",
    Mosfet: "MOSFET",
    Jfet: "JFET",
    Mesfet: "MESFET",
    Vcvs: "voltage-controlled voltage source",
    Vccs: "voltage-controlled current source",
    Cccs: "current-controlled current source",
    Ccvs: "current-controlled voltage source",
    VoltageSwitch: "voltage-controlled switch",
    CurrentSwitch: "current-controlled switch",
    BehavioralSource: "behavioral source",
    LosslessLine: "lossless transmission line",
    LossyLine: "lossy transmission line",
    RcLine: "uniform RC line",
    TxlLine: "TXL transmission line",
    CoupledLine: "coupled transmission line",
    CodeModelDevice: "code model",
    OsdiDevice: "OSDI device",
    SpecialFunction: "special function",
    FrequencyAnalyzer: "frequency response analyzer",
    FraProbe: "frequency response probe",
    SubcktInstance: "subcircuit call",
}


def element_name(element: Component) -> str:
    """The name messages use for ``element``'s kind, such as ``"bipolar transistor"``."""
    return ELEMENT_NAMES.get(type(element), type(element).__name__)


def element_phrase(element: Component) -> str:
    """:func:`element_name` with its article: ``"an inductor"``, ``"a MOSFET"``."""
    name = element_name(element)
    return f"{'an' if name[0] in 'aeiou' else 'a'} {name}"
