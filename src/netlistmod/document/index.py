"""Definition scopes, symbol tables and read-only reference resolution (architecture §8).

The scope model is ``docs/grammars/ngspice/scoping.md`` (decision 0006 items 3-5):

- A scope is the top level or one subcircuit definition, addressed by its path of folded
  subcircuit names (``()``, ``("amp",)``, ``("amp", "inner")``). Definitions are scopes, not
  expanded instances: the R1 of ``("amp",)`` is shared by every instance of ``amp``.
- A top-level ``.param`` is global. A definition's defaults and body ``.param`` lines are local
  and mask global names. Models and subcircuits are local to the scope that defines them and
  visible in its nested definitions.
- A model, subcircuit or parameter reference is looked up in its own scope, then each
  enclosing scope, independent of file order. A repeated ``.param`` resolves to the last
  assignment of the scope; a repeated model or subcircuit to the first (ngspice 47 ignores a
  redefinition). Element references (``K`` inductors, ``.dc`` sources, ``.save i(src)``) are
  looked up in their own scope only.

Items inside opaque ``.if`` blocks and ``.include``/``.lib`` files are not seen (§7.8).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, fields, is_dataclass
from types import MappingProxyType
from typing import Literal, TypeVar

from netlistmod.document.lines import Line, Lines, ScopePath
from netlistmod.document.names import fold
from netlistmod.grammar.formula import parse_formula
from netlistmod.model.nodes import (
    Capacitor,
    Component,
    DcDirective,
    Diode,
    Inductor,
    ModelStatement,
    MutualCoupling,
    OpaqueStatement,
    ParamStatement,
    Resistor,
    SaveDirective,
    SubcktDefinition,
    SubcktInstance,
    TopLevelItem,
)
from netlistmod.model.values import Formula, ParamAssignment
from netlistmod.source import SourceText, Span

_T = TypeVar("_T")

ReferenceKind = Literal["model", "subckt", "param", "subckt_param", "element"]
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
        "display",
        "elements",
        "has_opaque_include",
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
    ) -> None:
        """Build the tables of one scope; the builder adds the children."""
        self.path = path
        self.display = display
        self.definition = definition
        self.lines = lines
        self.parent = parent
        self._children: tuple[Scope, ...] = ()
        params: dict[str, list[ParamAssignment]] = {}
        for assignment in definition.params if definition is not None else ():
            params.setdefault(fold(assignment.name), []).append(assignment)
        models: dict[str, list[ModelStatement]] = {}
        subckts: dict[str, list[SubcktDefinition]] = {}
        elements: dict[str, list[Component]] = {}
        include = False
        for line in lines:
            item = line.item
            if isinstance(item, ParamStatement):
                for assignment in item.assignments:
                    params.setdefault(fold(assignment.name), []).append(assignment)
            elif isinstance(item, ModelStatement):
                models.setdefault(fold(item.name), []).append(item)
            elif isinstance(item, SubcktDefinition):
                subckts.setdefault(fold(item.name), []).append(item)
            elif isinstance(item, Component):
                elements.setdefault(fold(item.designator), []).append(item)
            elif isinstance(item, OpaqueStatement):
                include = True
        self.params = _frozen(params)
        self.models = _frozen(models)
        self.subckts = _frozen(subckts)
        self.elements = _frozen(elements)
        self.has_opaque_include = include

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

    def __init__(self, items: tuple[TopLevelItem, ...], source: SourceText) -> None:
        """Build lines, scopes and references for a parsed netlist."""
        self.lines = build_lines(items, (), source)
        self.root = _build_scope(self.lines, (), (), None, None)
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
        folded = tuple(fold(name) for name in path)
        try:
            return self._by_path[folded]
        except KeyError:
            raise KeyError(f"no subcircuit definition scope {tuple(path)!r}") from None


def build_lines(items: tuple[TopLevelItem, ...], path: ScopePath, source: SourceText) -> Lines:
    """Wrap parsed items as lines with physical line numbers; bodies become nested lines."""
    lines: list[Line] = []
    for item in items:
        span = item.span
        first = source.position(span.start)[0]
        last = source.position(max(span.end - 1, span.start))[0]
        body = None
        if isinstance(item, SubcktDefinition):
            body = build_lines(item.body, (*path, fold(item.name)), source)
        lines.append(Line(item, span, first, last, path, body))
    return Lines(lines)


def _build_scope(
    lines: Lines,
    path: ScopePath,
    display: tuple[str, ...],
    definition: SubcktDefinition | None,
    parent: Scope | None,
) -> Scope:
    scope = Scope(path, display, definition, lines, parent)
    children = []
    for line in lines:
        if isinstance(line.item, SubcktDefinition) and line.body is not None:
            name = line.item.name
            children.append(
                _build_scope(line.body, (*path, fold(name)), (*display, name), line.item, scope)
            )
    scope._children = tuple(children)
    return scope


def _lookup(
    scope: Scope, table: Literal["params", "models", "subckts"], name: str
) -> tuple[Scope, tuple[object, ...]] | None:
    key = fold(name)
    for candidate in scope.chain():
        definitions: Mapping[str, tuple[object, ...]] = getattr(candidate, table)
        if key in definitions:
            return candidate, definitions[key]
    return None


def _collect(scope: Scope, references: list[Reference], late: list[Reference]) -> None:
    """Add the references made from ``scope`` (not from nested definitions)."""
    if scope.definition is not None:
        for assignment in scope.definition.params:
            _formula_references(scope, scope.definition, assignment, references, late)
    for line in scope.lines:
        item = line.item
        if isinstance(item, SubcktDefinition):
            continue  # its header and body belong to the nested scope
        if isinstance(item, Resistor | Capacitor | Inductor | Diode) and item.model is not None:
            found = _lookup(scope, "models", item.model.model_name)
            target = found[1][0] if found else None
            references.append(
                Reference("model", item.model.model_name, item.model.span, scope.path, item, target)
            )
        elif isinstance(item, SubcktInstance):
            _instance_references(scope, item, references)
        elif isinstance(item, MutualCoupling):
            for inductor in item.inductors:
                references.append(
                    _element_reference(scope, item, inductor.designator, inductor.span)
                )
        elif isinstance(item, DcDirective):
            for sweep in item.sweeps:
                if fold(sweep.source) != _DC_TEMPERATURE:
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
        _formula_references(scope, item, item, references, late)


def _instance_references(scope: Scope, item: SubcktInstance, references: list[Reference]) -> None:
    found = _lookup(scope, "subckts", item.subckt.name)
    definition = found[1][0] if found else None
    assert definition is None or isinstance(definition, SubcktDefinition)
    references.append(
        Reference("subckt", item.subckt.name, item.subckt.span, scope.path, item, definition)
    )
    defaults = {fold(p.name): p for p in definition.params} if definition is not None else {}
    for param in item.params:
        target = defaults.get(fold(param.name))
        references.append(
            Reference("subckt_param", param.name, param.name_span, scope.path, item, target)
        )


def _element_reference(scope: Scope, owner: TopLevelItem, name: str, span: Span) -> Reference:
    elements = scope.elements.get(fold(name), ())
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
        tokens = parse_formula(formula.text)
        for token in tokens or ():
            if token.kind != "parameter":
                continue
            start = formula.span.start + 1 + token.start
            span = Span(start, start + len(token.text))
            found = _lookup(scope, "params", token.text)
            target = found[1][-1] if found else None
            reference = Reference("param", token.text, span, scope.path, owner, target)
            references.append(reference)
            if found:
                first = found[1][0]
                assert isinstance(first, ParamAssignment)
                if first.name_span.start > span.start:
                    late.append(reference)


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
