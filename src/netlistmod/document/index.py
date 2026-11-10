"""Definition scopes, symbol tables and read-only reference resolution (architecture §8).

The scope model is ``docs/grammars/<dialect>/scoping.md`` (decision 0006 items 3-5):

- A scope is the top level or one subcircuit definition, addressed by its path of folded
  subcircuit names (``()``, ``("amp",)``, ``("amp", "inner")``). Definitions are scopes, not
  expanded instances: the R1 of ``("amp",)`` is shared by every instance of ``amp``.
- A top-level ``.param`` is global. A definition's defaults and body ``.param`` lines are local
  and mask global names. Models and subcircuits are local to the scope that defines them and
  visible in its nested definitions.
- A model, subcircuit or parameter reference is looked up in its own scope, then each
  enclosing scope, independent of file order. A repeated ``.param`` resolves to the last
  assignment of the scope; a repeated model or subcircuit to the first (ngspice 47 ignores a
  redefinition; LTspice 26.1.1 stops at one that is used, ``scoping.md`` S7). A parameter swept by
  an LTspice
  ``.step param`` is defined by that line. Element references (``K`` inductors, ``.dc`` sources,
  ``.save i(src)``) are
  looked up in their own scope only.

Items inside opaque ``.if`` blocks and ``.include``/``.lib`` files are not seen (§7.8).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, fields, is_dataclass
from types import MappingProxyType
from typing import Literal, TypeVar

from netlistmod.dialects import Dialect
from netlistmod.document.lines import Line, Lines, ScopePath
from netlistmod.document.names import fold, is_automatic_global, is_ground, net_name
from netlistmod.grammar.formula import parse_formula
from netlistmod.model.nodes import (
    BehavioralSource,
    Capacitor,
    Cccs,
    Ccvs,
    CodeModelDevice,
    Component,
    ControlledSource,
    CoupledLine,
    CurrentSwitch,
    DcDirective,
    Diode,
    FraProbe,
    FrequencyAnalyzer,
    GlobalDirective,
    IcDirective,
    Inductor,
    LossyLine,
    ModelStatement,
    MutualCoupling,
    OpaqueBlock,
    OpaqueStatement,
    OsdiDevice,
    ParamStatement,
    RcLine,
    Resistor,
    SaveDirective,
    StepDirective,
    SubcktDefinition,
    SubcktInstance,
    Switch,
    TopLevelItem,
    Transistor,
    TxlLine,
)
from netlistmod.model.values import Formula, ParamAssignment
from netlistmod.source import SourceText, Span

_T = TypeVar("_T")
# The transmission lines that refer to a model (T has none; decision 0019).
_MODEL_LINES = LossyLine | RcLine | TxlLine | CoupledLine
# The ngspice devices whose model may be any type that is not built in (decision 0020).
_OPEN_MODEL = CodeModelDevice | OsdiDevice

ReferenceKind = Literal["model", "subckt", "param", "subckt_param", "element", "node"]
"""What a reference names: a ``.model``, a ``.subckt``, a parameter, a subcircuit default
(an ``X`` line's ``name=value``) or an element (``K`` inductor, ``.dc`` source,
``.save i(src)``)."""

# The swept name of `.dc TEMP ...` is the temperature, not an element (§11.3.2).
_DC_TEMPERATURE = "temp"


@dataclass(frozen=True, slots=True, eq=False)
class Reference:
    """A name in the netlist that refers to a definition elsewhere; compares by identity.

    ``span`` covers the name as written; ``scope`` is the scope it is resolved from; ``owner``
    is the item that holds it. ``target`` is the resolved node (a ``ModelStatement``,
    ``SubcktDefinition``, ``ParamAssignment`` or ``Component``), or ``None`` if unresolved.
    """

    kind: ReferenceKind
    name: str
    span: Span
    scope: ScopePath
    owner: TopLevelItem
    target: object | None


class Scope:
    """The top level or one subcircuit definition, with its lines and symbol tables.

    The tables map a folded name to every definition in this scope, in source order:
    ``params`` (defaults first, then ``.param`` assignments), ``models``, ``subckts`` and
    ``elements`` (the components of this scope, not of nested definitions).
    """

    __slots__ = (
        "_children",
        "definition",
        "dialect",
        "display",
        "elements",
        "may_define_elsewhere",
        "lines",
        "models",
        "params",
        "parent",
        "path",
        "subckts",
    )

    def __init__(
        self,
        path: ScopePath,
        display: tuple[str, ...],
        definition: SubcktDefinition | None,
        lines: Lines,
        parent: Scope | None,
        dialect: Dialect,
    ) -> None:
        """Build the tables of one scope; the builder adds the children."""
        self.dialect = dialect
        self.path = path
        self.display = display
        self.definition = definition
        self.lines = lines
        self.parent = parent
        self._children: tuple[Scope, ...] = ()
        params: dict[str, list[ParamAssignment]] = {}
        for assignment in definition.params if definition is not None else ():
            params.setdefault(self.fold(assignment.name), []).append(assignment)
        models: dict[str, list[ModelStatement]] = {}
        subckts: dict[str, list[SubcktDefinition]] = {}
        elements: dict[str, list[Component]] = {}
        elsewhere = False
        for line in lines:
            item = line.item
            if isinstance(item, ParamStatement):
                for assignment in item.assignments:
                    params.setdefault(self.fold(assignment.name), []).append(assignment)
            elif isinstance(item, ModelStatement):
                models.setdefault(self.fold(item.name), []).append(item)
            elif isinstance(item, SubcktDefinition):
                subckts.setdefault(self.fold(item.name), []).append(item)
            elif isinstance(item, Component):
                elements.setdefault(self.fold(item.designator), []).append(item)
            elif isinstance(item, OpaqueStatement) or (
                isinstance(item, OpaqueBlock) and item.kind != "control"
            ):
                elsewhere = True
        self.params = _frozen(params)
        self.models = _frozen(models)
        self.subckts = _frozen(subckts)
        self.elements = _frozen(elements)
        self.may_define_elsewhere = elsewhere

    def fold(self, name: str) -> str:
        """``name`` in the form this netlist's dialect compares names in."""
        return fold(name, self.dialect)

    @property
    def children(self) -> tuple[Scope, ...]:
        """The scopes of the definitions in this scope, in source order."""
        return self._children

    def chain(self) -> Iterator[Scope]:
        """This scope, then each enclosing scope up to the top level."""
        scope: Scope | None = self
        while scope is not None:
            yield scope
            scope = scope.parent

    def walk(self) -> Iterator[Scope]:
        """This scope and every nested scope, depth first in source order."""
        yield self
        for child in self._children:
            yield from child.walk()

    def describe(self) -> str:
        """A human-readable name for messages: ``top level`` or ``subcircuit `a > b```."""
        if not self.display:
            return "top level"
        return f"subcircuit `{' > '.join(self.display)}`"

    def __repr__(self) -> str:
        """Show the path."""
        return f"Scope({self.path!r})"


def _frozen(table: dict[str, list[_T]]) -> Mapping[str, tuple[_T, ...]]:
    return MappingProxyType({key: tuple(values) for key, values in table.items()})


class Index:
    """The scopes of a netlist and every reference in it, resolved at construction."""

    def __init__(
        self, items: tuple[TopLevelItem, ...], source: SourceText, dialect: Dialect
    ) -> None:
        """Build lines, scopes and references for a parsed netlist."""
        self.dialect = dialect
        self.lines = build_lines(items, (), source, dialect)
        self.root = _build_scope(self.lines, (), (), None, None, dialect)
        self.scopes = tuple(self.root.walk())
        self._by_path: dict[ScopePath, Scope] = {}
        for scope in self.scopes:
            # A repeated definition name gives a second scope with the same path; the first
            # one is addressed, as ngspice uses the first definition.
            self._by_path.setdefault(scope.path, scope)
        references: list[Reference] = []
        late: list[Reference] = []
        for scope in self.scopes:
            _collect(scope, references, late)
        self.references = tuple(sorted(references, key=lambda ref: ref.span.start))
        self.late_param_uses = frozenset(late)

    def scope(self, path: ScopePath = ()) -> Scope:
        """Return the scope at ``path`` (names compared case-insensitively); ``KeyError``."""
        if isinstance(path, str):
            raise TypeError(f"a scope is a sequence of subcircuit names: write ({path!r},)")
        folded = tuple(fold(name, self.dialect) for name in path)
        try:
            return self._by_path[folded]
        except KeyError:
            raise KeyError(f"no subcircuit definition scope {tuple(path)!r}") from None


def build_lines(
    items: tuple[TopLevelItem, ...], path: ScopePath, source: SourceText, dialect: Dialect
) -> Lines:
    """Wrap parsed items as lines with physical line numbers; bodies become nested lines."""
    lines: list[Line] = []
    for item in items:
        span = item.span
        first = source.position(span.start)[0]
        last = source.position(max(span.end - 1, span.start))[0]
        body = None
        if isinstance(item, SubcktDefinition):
            body = build_lines(item.body, (*path, fold(item.name, dialect)), source, dialect)
        lines.append(Line(item, span, first, last, path, body))
    return Lines(lines)


def _build_scope(
    lines: Lines,
    path: ScopePath,
    display: tuple[str, ...],
    definition: SubcktDefinition | None,
    parent: Scope | None,
    dialect: Dialect,
) -> Scope:
    scope = Scope(path, display, definition, lines, parent, dialect)
    children = []
    for line in lines:
        if isinstance(line.item, SubcktDefinition) and line.body is not None:
            name = line.item.name
            children.append(
                _build_scope(
                    line.body,
                    (*path, fold(name, dialect)),
                    (*display, name),
                    line.item,
                    scope,
                    dialect,
                )
            )
    scope._children = tuple(children)
    return scope


def _lookup(
    scope: Scope, table: Literal["params", "models", "subckts"], name: str
) -> tuple[Scope, tuple[object, ...]] | None:
    key = scope.fold(name)
    for candidate in scope.chain():
        definitions: Mapping[str, tuple[object, ...]] = getattr(candidate, table)
        if key in definitions:
            return candidate, definitions[key]
    return None


def definition_scope(scope: Scope, name: str) -> Scope | None:
    """The scope of the subcircuit ``name`` as seen from ``scope``, if the netlist defines it."""
    found = _lookup(scope, "subckts", name)
    if found is None:
        return None
    return next(child for child in found[0].children if child.definition is found[1][0])


def _collect(scope: Scope, references: list[Reference], late: list[Reference]) -> None:
    """Add the references made from ``scope`` (not from nested definitions)."""
    if scope.definition is not None:
        for assignment in scope.definition.params:
            _formula_references(scope, scope.definition, assignment, references, late)
    for line in scope.lines:
        item = line.item
        if isinstance(item, SubcktDefinition):
            continue  # its header and body belong to the nested scope
        if (
            isinstance(
                item,
                Resistor
                | Capacitor
                | Inductor
                | Diode
                | Transistor
                | Switch
                | _MODEL_LINES
                | _OPEN_MODEL,
            )
            and item.model is not None
        ):
            found = _lookup(scope, "models", item.model.model_name)
            target = found[1][0] if found else None
            references.append(
                Reference("model", item.model.model_name, item.model.span, scope.path, item, target)
            )
        elif isinstance(item, SubcktInstance):
            _instance_references(scope, item, references)
        # A new chain on purpose: a W line needs both its model reference above and this one.
        if isinstance(item, Cccs | Ccvs | CurrentSwitch | CodeModelDevice):
            # The controlling sources, in the element's own scope only (decision 0015 item 4); an
            # A line's %vnam sources are controlling references too (decision 0020 item 4).
            for source in item.control:
                references.append(_element_reference(scope, item, source.designator, source.span))
        elif isinstance(item, FraProbe):
            references.append(_analyzer_reference(scope, item))
        elif isinstance(item, FrequencyAnalyzer):
            # refnode= and intnode= name nets the analyzer measures (decision 0020 item 7).
            for net in (item.reference_net, item.intermediate_net):
                if net is not None:
                    references.append(_node_reference(scope, item, net.name, net.span))
        elif isinstance(item, MutualCoupling):
            for inductor in item.inductors:
                references.append(
                    _element_reference(scope, item, inductor.designator, inductor.span)
                )
        elif isinstance(item, DcDirective):
            for sweep in item.sweeps:
                if scope.fold(sweep.source) != _DC_TEMPERATURE:
                    references.append(
                        _element_reference(scope, item, sweep.source, sweep.source_span)
                    )
        elif isinstance(item, SaveDirective):
            for vector in item.vectors:
                if vector.source is not None:
                    references.append(
                        _element_reference(
                            scope, item, vector.source.designator, vector.source.span
                        )
                    )
        elif isinstance(item, IcDirective):
            for condition in item.conditions:
                if condition.current is not None:
                    references.append(
                        _element_reference(
                            scope, item, condition.current.designator, condition.current.span
                        )
                    )
        elif isinstance(item, StepDirective):
            _step_references(scope, item, references)
        elif isinstance(item, ModelStatement) and item.ako is not None:
            found = _lookup(scope, "models", item.ako.model_name)
            target = found[1][0] if found else None
            references.append(
                Reference("model", item.ako.model_name, item.ako.span, scope.path, item, target)
            )
        _formula_references(scope, item, item, references, late)


def _instance_references(scope: Scope, item: SubcktInstance, references: list[Reference]) -> None:
    found = _lookup(scope, "subckts", item.subckt.name)
    definition = found[1][0] if found else None
    assert definition is None or isinstance(definition, SubcktDefinition)
    references.append(
        Reference("subckt", item.subckt.name, item.subckt.span, scope.path, item, definition)
    )
    defaults = {scope.fold(p.name): p for p in definition.params} if definition is not None else {}
    for param in item.params:
        target = defaults.get(scope.fold(param.name))
        references.append(
            Reference("subckt_param", param.name, param.name_span, scope.path, item, target)
        )


def _step_references(scope: Scope, item: StepDirective, references: list[Reference]) -> None:
    """A ``.step`` sweeps a source, a model parameter or a parameter it defines itself, so a
    parameter name is a reference only when a ``.param`` line defines it as well."""
    if item.kind == "source":
        references.append(_element_reference(scope, item, item.name, item.name_span))
    elif item.kind == "model" and item.model is not None:
        found = _lookup(scope, "models", item.model.model_name)
        target = found[1][0] if found else None
        references.append(
            Reference("model", item.model.model_name, item.model.span, scope.path, item, target)
        )
    elif item.kind == "param":
        found = _lookup(scope, "params", item.name)
        if found:
            references.append(
                Reference("param", item.name, item.name_span, scope.path, item, found[1][-1])
            )


def _stepped_parameter(scope: Scope, name: str) -> StepDirective | None:
    """The top-level ``.step param`` that defines ``name``, if any."""
    root = next(candidate for candidate in scope.chain() if candidate.parent is None)
    for line in root.lines:
        if (
            isinstance(line.item, StepDirective)
            and line.item.kind == "param"
            and scope.fold(line.item.name) == scope.fold(name)
        ):
            return line.item
    return None


def _analyzer_reference(scope: Scope, probe: FraProbe) -> Reference:
    """The ``@`` a probe measures with: the one of its suffix in its scope, or else the scope's
    only ``@``, which LTspice then uses (decision 0020 item 8)."""
    reference = _element_reference(scope, probe, probe.analyzer.designator, probe.analyzer.span)
    if reference.target is None:
        analyzers = [
            element
            for elements in scope.elements.values()
            for element in elements
            if isinstance(element, FrequencyAnalyzer)
        ]
        if len(analyzers) == 1:
            return Reference(
                "element", reference.name, reference.span, scope.path, probe, analyzers[0]
            )
    return reference


def _element_reference(scope: Scope, owner: TopLevelItem, name: str, span: Span) -> Reference:
    elements = scope.elements.get(scope.fold(name), ())
    return Reference("element", name, span, scope.path, owner, elements[0] if elements else None)


def _formula_references(
    scope: Scope,
    owner: TopLevelItem,
    node: object,
    references: list[Reference],
    late: list[Reference],
) -> None:
    """Add a parameter reference for each parameter name in the formulas of ``node``."""
    for formula in walk_nodes(node, Formula, bodies=False):
        if formula.delimiter == '"':
            continue  # a string value, not an expression
        tokens = parse_formula(formula.text, scope.dialect)
        # A bare LTspice expression has no delimiter in front of its text.
        text_start = formula.span.start + (1 if formula.delimiter else 0)
        context = _context_words(owner, formula, scope.dialect)
        for token in tokens or ():
            if token.kind in ("node", "source"):
                # What the expression reads (decision 0016 item 6): a net, or an element.
                start = text_start + token.start
                read = Span(start, start + len(token.text))
                if token.kind == "source":
                    references.append(_element_reference(scope, owner, token.text, read))
                else:
                    references.append(_node_reference(scope, owner, token.text, read))
                continue
            if token.kind not in ("parameter", "reserved"):
                continue
            if token.text.lower() in context:
                continue  # the simulation's own variable, which no definition masks
            start = text_start + token.start
            span = Span(start, start + len(token.text))
            found = _lookup(scope, "params", token.text)
            target: object | None = found[1][-1] if found else None
            if target is None:
                target = _stepped_parameter(scope, token.text)
            # A definition in scope masks an LTspice constant (scoping.md S11); otherwise a
            # reserved word is not a reference.
            if token.kind == "reserved" and (
                target is None or scope.dialect is not Dialect.LTSPICE
            ):
                continue
            reference = Reference("param", token.text, span, scope.path, owner, target)
            references.append(reference)
            # Order is only meaningful within one scope: a body is expanded where it is
            # called, not where it is defined (§2.11.1; M5 review R1). In LTspice line order
            # never matters (reference, Netlist Structure).
            if found and found[0] is scope and scope.dialect is not Dialect.LTSPICE:
                first = found[1][0]
                assert isinstance(first, ParamAssignment)
                if first.name_span.start > span.start:
                    late.append(reference)


def _node_reference(scope: Scope, owner: TopLevelItem, name: str, span: Span) -> Reference:
    """A net an expression reads: resolved when ground, global, a port or an element's node in
    the scope; the target is the first node or port that names it."""
    return Reference("node", name, span, scope.path, owner, _net_node(scope, name))


def _net_node(scope: Scope, name: str) -> object | None:
    dialect = scope.dialect
    if is_ground(name, dialect) or is_automatic_global(name, dialect):
        return name
    key = net_name(name, dialect)
    nodes = [*(scope.definition.ports if scope.definition is not None else ())]
    for line in scope.lines:
        if isinstance(line.item, Component):
            nodes.extend(line.item.nodes)
    root = scope
    while root.parent is not None:
        root = root.parent
    for line in root.lines:
        if isinstance(line.item, GlobalDirective):
            nodes.extend(line.item.nodes)
    return next((node for node in nodes if net_name(node.name, dialect) == key), None)


def _context_words(owner: object, formula: Formula, dialect: Dialect) -> frozenset[str]:
    """The words an LTspice expression gives a meaning of its own (decision 0016 item 5).

    ``time`` in a B expression or a ``value=`` form, and ``x`` (the device's voltage or current)
    in C's ``Q=`` and L's ``Flux=``, read the simulation; a ``.param`` of the same name does not
    mask them there (m8-tasks 13.2). ngspice's ``time``, ``temper`` and ``hertz`` are reserved
    words everywhere already.
    """
    if dialect is not Dialect.LTSPICE:
        return frozenset()
    if formula is getattr(owner, "charge", None) or formula is getattr(owner, "flux", None):
        return _DEVICE_WORDS
    # `s` in Laplace= and laplace= is the Laplace variable, not a parameter (decision 0017 item 7).
    if isinstance(owner, ControlledSource) and owner.form == "laplace":
        if formula is owner.expression:
            return _LAPLACE_WORDS
    if isinstance(owner, BehavioralSource) and any(
        param.name.lower() == "laplace" and param.value is formula for param in owner.params
    ):
        return _LAPLACE_WORDS
    if isinstance(owner, BehavioralSource | ControlledSource) and formula is owner.expression:
        return _EXPRESSION_WORDS
    return frozenset()


_EXPRESSION_WORDS = frozenset({"time"})
_LAPLACE_WORDS = frozenset({"s"})
_DEVICE_WORDS = frozenset({"time", "x"})


def walk_nodes(node: object, kind: type[_T], *, bodies: bool) -> Iterator[_T]:
    """Yield every value of type ``kind`` inside a node's fields, in field order.

    This walks typed nodes, not source text. With ``bodies=False`` a subcircuit definition's
    body and ``.ends`` line are not entered.
    """
    if isinstance(node, kind):
        yield node
        return
    if isinstance(node, tuple):
        for element in node:
            yield from walk_nodes(element, kind, bodies=bodies)
    elif is_dataclass(node) and not isinstance(node, type):
        for field in fields(node):
            if not bodies and isinstance(node, SubcktDefinition) and field.name in {"body", "ends"}:
                continue
            yield from walk_nodes(getattr(node, field.name), kind, bodies=bodies)
