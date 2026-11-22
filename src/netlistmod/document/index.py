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
  assignment of the scope (on xyce to the first, as Xyce 7.10 does); a repeated model or
  subcircuit to the first (ngspice 47 ignores a redefinition; LTspice 26.1.1 stops at one that is
  used, ``scoping.md`` S7). An xyce ``.FUNC`` (or a ``.PARAM`` function) is looked up like a
  model, and a call to it is a ``function`` reference. A parameter swept by
  an LTspice
  ``.step param`` is defined by that line. Element references (``K`` inductors, ``.dc`` sources,
  ``.save i(src)``) are
  looked up in their own scope only.
- On xyce (decision 0028 items 4, 6 and 8), a ``.DC`` or ``.STEP`` target is resolved as Xyce
  resolves it: a plain name as a parameter first, then an element (a device's primary parameter);
  ``head:param`` as an element (``X1:R5`` through the instances) or a model; ``TEMP`` is no
  reference. A ``DATA=`` field is a ``data`` reference to a top-level ``.DATA`` table (the last of
  a repeated name), and each node of an ``.IC``, ``.DCVOLT`` or ``.NODESET`` condition is a
  ``node`` reference in the scope of its line.

Items inside opaque ``.if`` blocks and ``.include``/``.lib`` files are not seen (§7.8).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, fields, is_dataclass
from types import MappingProxyType
from typing import Literal, TypeVar

from netlistmod.dialects import _XYCE, Dialect
from netlistmod.document.lines import Line, Lines, ScopePath
from netlistmod.document.names import fold, is_automatic_global, is_ground, net_name
from netlistmod.grammar.formula import builtin_functions, parse_formula
from netlistmod.model.nodes import (
    AcDirective,
    BehavioralSource,
    Capacitor,
    Cccs,
    Ccvs,
    CodeModelDevice,
    Component,
    ControlledSource,
    CoupledLine,
    CurrentSource,
    CurrentSwitch,
    DataTable,
    DcDirective,
    Diode,
    FraProbe,
    FrequencyAnalyzer,
    FuncStatement,
    GlobalDirective,
    GlobalParamStatement,
    IcDirective,
    Inductor,
    LossyLine,
    ModelStatement,
    MutualCoupling,
    NodesetDirective,
    OpaqueBlock,
    OpaqueStatement,
    OsdiDevice,
    ParamStatement,
    PreprocessDirective,
    RcLine,
    Resistor,
    SaveDirective,
    StepDirective,
    SubcktDefinition,
    SubcktInstance,
    Switch,
    TopLevelItem,
    TranDirective,
    Transistor,
    TxlLine,
    VoltageSource,
)
from netlistmod.model.values import Formula, FunctionDefinition, ParamAssignment
from netlistmod.source import SourceText, Span

_T = TypeVar("_T")
# The transmission lines that refer to a model (T has none; decision 0019).
_MODEL_LINES = LossyLine | RcLine | TxlLine | CoupledLine
# The ngspice devices whose model may be any type that is not built in (decision 0020).
_OPEN_MODEL = CodeModelDevice | OsdiDevice

ReferenceKind = Literal[
    "model", "subckt", "param", "subckt_param", "element", "node", "function", "data"
]
"""What a reference names: a ``.model``, a ``.subckt``, a parameter, a subcircuit default
(an ``X`` line's ``name=value``), an element (``K`` inductor, ``.dc`` source,
``.save i(src)``), a node an expression reads (or, on xyce, a node an initial condition sets), an
xyce user-defined function (a call), or an xyce ``.DATA`` table (a ``DATA=`` field)."""

# Whether a parameter used before its definition in its own scope is reported (scoping.md of each
# dialect): ngspice reads the netlist in order; LTspice and Xyce do not mind.
_ORDER_MATTERS: dict[Dialect, bool] = {Dialect.NGSPICE: True, Dialect.LTSPICE: False, _XYCE: False}
# Which definition a repeated parameter resolves to, and so which assignment params.set edits
# (edit/_ops_statements.py): the last on ngspice and LTspice, the first on
# Xyce 7.10, as its own warning says (xyce scoping.md S3; the manual says the last).
_FIRST_PARAM_WINS: dict[Dialect, bool] = {
    Dialect.NGSPICE: False,
    Dialect.LTSPICE: False,
    _XYCE: True,
}
# Whether formulas may call user-defined functions, so a call is a reference (xyce's `.FUNC`).
_USER_FUNCTIONS: dict[Dialect, bool] = {Dialect.NGSPICE: False, Dialect.LTSPICE: False, _XYCE: True}

# The swept name of `.dc TEMP ...` is the temperature, not an element (§11.3.2).
_DC_TEMPERATURE = "temp"
# Whether `.DC` and `.STEP` targets are resolved as Xyce resolves them (decision 0028 item 4): a
# plain name as a parameter first, then an element; `head:param` as an element or a model. On
# ngspice and LTspice a `.dc` target is an element (or `TEMP`), and `.step` says what it sweeps.
_SWEEP_LOOKUP: dict[Dialect, bool] = {Dialect.NGSPICE: False, Dialect.LTSPICE: False, _XYCE: True}
# Whether the nodes of `.ic` and `.nodeset` conditions are references (decision 0028 item 6).
_CONDITION_NODES: dict[Dialect, bool] = {
    Dialect.NGSPICE: False,
    Dialect.LTSPICE: False,
    _XYCE: True,
}
# The primary parameter of a device that an xyce `.STEP` or `.DC` sweeps by its name alone, so
# that `R2` and `R2:R` are one quantity (xm2-tasks 5.1 point 16; [xyce-ref] §2.1.36 p155).
_PRIMARY_PARAMS: dict[type, str] = {
    Resistor: "r",
    Capacitor: "c",
    Inductor: "l",
    VoltageSource: "dcv0",
    CurrentSource: "dcv0",
}


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


@dataclass(frozen=True, slots=True)
class SweepTarget:
    """What an xyce ``.DC`` or ``.STEP`` target may name (decision 0028 item 4), for the message
    of one that does not resolve: ``noun`` (``parameter or element``, ``element or model``), and
    ``included``, whether a path such as ``X1:R5`` runs into an instance whose definition the
    netlist does not hold, while a searched scope has an ``.include`` or ``.lib``; ``device``,
    whether the target is a path to a device without its parameter (``X1:R5``), which Xyce does
    not resolve."""

    noun: str
    included: bool = False
    device: bool = False


class Scope:
    """The top level or one subcircuit definition, with its lines and symbol tables.

    The tables map a folded name to every definition in this scope, in source order:
    ``params`` (defaults first, then ``.param`` assignments), ``models``, ``subckts`` and
    ``elements`` (the components of this scope, not of nested definitions).

    Two xyce attributes are internal until X-M8 names them (decision 0026; xm1-tasks 5.1 point
    31): ``_functions``, the user-defined functions by folded name in source order (an xyce
    ``.FUNC`` line, or a function on a ``.PARAM`` line; empty on the other dialects), and
    ``_replace_ground``, whether ``GND``, ``GND!`` and ``GROUND`` are the ground net (an xyce
    netlist with ``.PREPROCESS REPLACEGROUND TRUE`` anywhere in it; the same in every scope).
    A third, ``_data``, holds the xyce ``.DATA`` tables by folded name in source order (X-M2;
    only the top level has any, since a table in a body is refused). Other modules read the three
    through this module's ``scope_functions``, ``scope_replaces_ground`` and ``scope_data``.
    """

    __slots__ = (
        "_children",
        "_data",
        "_definition",
        "_dialect",
        "_display",
        "_elements",
        "_functions",
        "_lines",
        "_may_define_elsewhere",
        "_models",
        "_params",
        "_parent",
        "_path",
        "_replace_ground",
        "_subckts",
    )

    def __init__(
        self,
        path: ScopePath,
        display: tuple[str, ...],
        definition: SubcktDefinition | None,
        lines: Lines,
        parent: Scope | None,
        dialect: Dialect,
        *,
        replace_ground: bool = False,
    ) -> None:
        """Build the tables of one scope; the builder adds the children."""
        self._dialect = dialect
        self._replace_ground = replace_ground
        self._path = path
        self._display = display
        self._definition = definition
        self._lines = lines
        self._parent = parent
        self._children: tuple[Scope, ...] = ()
        params: dict[str, list[ParamAssignment]] = {}
        for assignment in definition.params if definition is not None else ():
            params.setdefault(self.fold(assignment.name), []).append(assignment)
        models: dict[str, list[ModelStatement]] = {}
        subckts: dict[str, list[SubcktDefinition]] = {}
        elements: dict[str, list[Component]] = {}
        functions: dict[str, list[FunctionDefinition]] = {}
        data: dict[str, list[DataTable]] = {}
        # An xyce `.GLOBAL_PARAM` loses to a `.PARAM` of the same name wherever it stands
        # (scoping.md S5), so its assignments follow the `.PARAM` ones in the table.
        late_params: list[ParamAssignment] = []
        elsewhere = False
        for line in lines:
            item = line.item
            if isinstance(item, ParamStatement):
                kept = late_params if isinstance(item, GlobalParamStatement) else None
                for assignment in item.assignments:
                    if kept is not None:
                        kept.append(assignment)
                    else:
                        params.setdefault(self.fold(assignment.name), []).append(assignment)
                for function in item.functions:
                    functions.setdefault(self.fold(function.name), []).append(function)
            elif isinstance(item, FuncStatement):
                functions.setdefault(self.fold(item.function.name), []).append(item.function)
            elif isinstance(item, ModelStatement):
                models.setdefault(self.fold(item.name), []).append(item)
            elif isinstance(item, SubcktDefinition):
                subckts.setdefault(self.fold(item.name), []).append(item)
            elif isinstance(item, Component):
                elements.setdefault(self.fold(item.designator), []).append(item)
            elif isinstance(item, DataTable):
                data.setdefault(self.fold(item.name.name), []).append(item)
            elif isinstance(item, OpaqueStatement) or (
                isinstance(item, OpaqueBlock) and item.kind not in ("control", "data")
            ):
                elsewhere = True
        for assignment in late_params:
            params.setdefault(self.fold(assignment.name), []).append(assignment)
        self._params = _frozen(params)
        self._functions = _frozen(functions)
        self._data = _frozen(data)
        self._models = _frozen(models)
        self._subckts = _frozen(subckts)
        self._elements = _frozen(elements)
        self._may_define_elsewhere = elsewhere

    @property
    def path(self) -> ScopePath:
        """The folded subcircuit names from the top level; ``()`` for the top level."""
        return self._path

    @property
    def display(self) -> tuple[str, ...]:
        """The subcircuit names of ``path`` as the definitions write them."""
        return self._display

    @property
    def definition(self) -> SubcktDefinition | None:
        """The ``.subckt`` definition of this scope; ``None`` for the top level."""
        return self._definition

    @property
    def lines(self) -> Lines:
        """The logical lines of this scope (for a definition, its body)."""
        return self._lines

    @property
    def parent(self) -> Scope | None:
        """The enclosing scope; ``None`` for the top level."""
        return self._parent

    @property
    def dialect(self) -> Dialect:
        """The dialect of the netlist, which sets how names are folded."""
        return self._dialect

    @property
    def params(self) -> Mapping[str, tuple[ParamAssignment, ...]]:
        """Parameters by folded name: the definition's defaults, then ``.param`` assignments."""
        return self._params

    @property
    def models(self) -> Mapping[str, tuple[ModelStatement, ...]]:
        """Models by folded name, in source order."""
        return self._models

    @property
    def subckts(self) -> Mapping[str, tuple[SubcktDefinition, ...]]:
        """Subcircuit definitions by folded name, in source order."""
        return self._subckts

    @property
    def elements(self) -> Mapping[str, tuple[Component, ...]]:
        """The components of this scope (not of nested definitions) by folded designator."""
        return self._elements

    @property
    def may_define_elsewhere(self) -> bool:
        """Whether this scope holds an opaque item that may define names its tables do not show:
        an ``.include`` or ``.lib`` statement, or an ``.if`` or ``.lib`` block (§7.8)."""
        return self._may_define_elsewhere

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


# Read-only accessors for the xyce tables of a scope (X-M2.1 C4; X-M2 review R1 N6). The tables
# stay private attributes of `Scope`, a public class, so that its public surface does not grow
# while the dialect is hidden (decision 0026 item 4; xm1-tasks 5.1 point 31); the other modules
# of the package read them through these functions, as they do `step_quantity`. X-M8 decides
# whether they become properties of `Scope` (xyce-plan.md section 8.2).


def scope_functions(scope: Scope) -> Mapping[str, tuple[FunctionDefinition, ...]]:
    """The user-defined functions of ``scope`` by folded name, in source order: xyce ``.FUNC``
    lines and the functions of ``.PARAM`` lines; empty on the other dialects."""
    return scope._functions


def scope_data(scope: Scope) -> Mapping[str, tuple[DataTable, ...]]:
    """The xyce ``.DATA`` tables of ``scope`` by folded name, in source order; only the top level
    has any, since a table in a body is refused."""
    return scope._data


def scope_replaces_ground(scope: Scope) -> bool:
    """Whether ``GND``, ``GND!`` and ``GROUND`` are the ground net in ``scope``: an xyce netlist
    with ``.PREPROCESS REPLACEGROUND TRUE`` anywhere in it, the same in every scope."""
    return scope._replace_ground


class Index:
    """The scopes of a netlist and every reference in it, resolved at construction."""

    def __init__(
        self, items: tuple[TopLevelItem, ...], source: SourceText, dialect: Dialect
    ) -> None:
        """Build lines, scopes and references for a parsed netlist."""
        self.dialect = dialect
        self.lines = build_lines(items, (), source, dialect)
        # `.PREPROCESS REPLACEGROUND` acts on the whole netlist, wherever it stands (decision
        # 0027 item 3); the grammar admits one.
        self.preprocess = tuple(
            line.item for line in self.lines.walk() if isinstance(line.item, PreprocessDirective)
        )
        self.replace_ground = any(directive.enabled for directive in self.preprocess)
        self.root = _build_scope(
            self.lines, (), (), None, None, dialect, replace_ground=self.replace_ground
        )
        self.scopes = tuple(self.root.walk())
        self._by_path: dict[ScopePath, Scope] = {}
        for scope in self.scopes:
            # A repeated definition name gives a second scope with the same path; the first
            # one is addressed, as ngspice uses the first definition.
            self._by_path.setdefault(scope.path, scope)
        references: list[Reference] = []
        late: list[Reference] = []
        targets: dict[Reference, SweepTarget] = {}
        conditions: list[Reference] = []
        for scope in self.scopes:
            _collect(scope, references, late, targets, conditions)
        self.references = tuple(sorted(references, key=lambda ref: ref.span.start))
        self.late_param_uses = frozenset(late)
        # The xyce `.DC` and `.STEP` targets among the references, with what they may name.
        self.sweep_targets: Mapping[Reference, SweepTarget] = MappingProxyType(targets)
        # The nodes that xyce `.IC`, `.DCVOLT` and `.NODESET` conditions set; a node that an
        # expression in a condition's value reads is an ordinary expression node, not one of these.
        self.condition_nodes = frozenset(conditions)

    def scope(self, path: ScopePath = ()) -> Scope:
        """Return the scope at ``path`` (names compared case-insensitively); ``KeyError``.

        ``TypeError`` for a ``str`` (write a one-name tuple) or a ``Scope`` (pass its ``path``).
        """
        if isinstance(path, str):
            raise TypeError(f"a scope is a sequence of subcircuit names: write ({path!r},)")
        if isinstance(path, Scope):
            raise TypeError(
                f"a scope is given by its path, not a Scope object: pass Scope.path ({path.path!r})"
            )
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
    *,
    replace_ground: bool,
) -> Scope:
    scope = Scope(path, display, definition, lines, parent, dialect, replace_ground=replace_ground)
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
                    replace_ground=replace_ground,
                )
            )
    scope._children = tuple(children)
    return scope


def _lookup(
    scope: Scope, table: Literal["params", "models", "subckts", "_functions"], name: str
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


def _collect(
    scope: Scope,
    references: list[Reference],
    late: list[Reference],
    targets: dict[Reference, SweepTarget],
    conditions: list[Reference],
) -> None:
    """Add the references made from ``scope`` (not from nested definitions); the nodes that
    initial conditions set go in ``conditions`` as well."""
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
                | MutualCoupling
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
        elif isinstance(item, DcDirective) and _SWEEP_LOOKUP[scope.dialect]:
            for sweep in item.sweeps:
                _sweep_target(scope, item, sweep.source, sweep.source_span, references, targets)
            if item.data is not None:
                references.append(_data_reference(scope, item, item.data.name, item.data.span))
        elif isinstance(item, DcDirective):
            for sweep in item.sweeps:
                if scope.fold(sweep.source) != _DC_TEMPERATURE:
                    references.append(
                        _element_reference(scope, item, sweep.source, sweep.source_span)
                    )
        elif isinstance(item, AcDirective) and item.data is not None:
            references.append(_data_reference(scope, item, item.data.name, item.data.span))
        elif isinstance(item, SaveDirective):
            for vector in item.vectors:
                if vector.source is not None:
                    references.append(
                        _element_reference(
                            scope, item, vector.source.designator, vector.source.span
                        )
                    )
        elif isinstance(item, IcDirective | NodesetDirective):
            for condition in item.conditions:
                if condition.current is not None:
                    references.append(
                        _element_reference(
                            scope, item, condition.current.designator, condition.current.span
                        )
                    )
                if condition.node is not None and _CONDITION_NODES[scope.dialect]:
                    node = condition.node
                    reference = _node_reference(scope, item, node.name, node.span)
                    references.append(reference)
                    conditions.append(reference)
        elif isinstance(item, StepDirective):
            _step_references(scope, item, references, targets)
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


def _step_references(
    scope: Scope,
    item: StepDirective,
    references: list[Reference],
    targets: dict[Reference, SweepTarget],
) -> None:
    """An LTspice ``.step`` sweeps a source, a model parameter or a parameter it defines itself,
    so a parameter name is a reference only when a ``.param`` line defines it as well. An xyce
    target is resolved as a ``.DC`` target, and ``DATA=`` names a table."""
    if item.kind in ("name", "qualified"):
        _sweep_target(scope, item, item.name, item.name_span, references, targets)
    elif item.kind == "data":
        references.append(_data_reference(scope, item, item.name, item.name_span))
    elif item.kind == "source":
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


def _sweep_target(
    scope: Scope,
    owner: TopLevelItem,
    name: str,
    span: Span,
    references: list[Reference],
    targets: dict[Reference, SweepTarget],
) -> None:
    """An xyce ``.DC`` or ``.STEP`` target, resolved as Xyce resolves it (decision 0028 item 4;
    xm2-tasks 5.1 points 12 and 14): ``TEMP`` is no reference; a plain name is a parameter (the
    effective assignment) or else an element, and unresolved a parameter reference, since Xyce
    reports it as an undefined variable; in ``head:param``, split at the last ``:``, the head is
    an element (a path ``X1:R5`` through the instances) or else a model, and unresolved an
    element reference. A path whose last part is a device of the instance (``X1:R5``, the device
    without its parameter) is an unresolved element reference for the whole target, as Xyce stops
    on it ("X1:R5 is not defined")."""
    if scope.fold(name) == _DC_TEMPERATURE:
        return
    head, colon, _ = name.rpartition(":")
    included = False
    reference: Reference
    if not colon:
        found = _lookup(scope, "params", name)
        elements = scope.elements.get(scope.fold(name), ())
        if found:
            target = found[1][0] if _FIRST_PARAM_WINS[scope.dialect] else found[1][-1]
            reference = Reference("param", name, span, scope.path, owner, target)
        elif elements:
            reference = Reference("element", name, span, scope.path, owner, elements[0])
        else:
            reference = Reference("param", name, span, scope.path, owner, None)
        noun = "parameter or element"
    elif _path_element(scope, name)[0] is not None:
        reference = Reference("element", name, span, scope.path, owner, None)
        references.append(reference)
        targets[reference] = SweepTarget("element parameter", device=True)
        return
    else:
        head_span = Span(span.start, span.start + len(head))
        noun = "element or model"
        if ":" in head:
            noun = "element"
            element, included = _path_element(scope, head)
            reference = Reference("element", head, head_span, scope.path, owner, element)
        elif scope.elements.get(scope.fold(head)):
            reference = _element_reference(scope, owner, head, head_span)
        elif (model := _lookup(scope, "models", head)) is not None:
            reference = Reference("model", head, head_span, scope.path, owner, model[1][0])
        else:
            reference = Reference("element", head, head_span, scope.path, owner, None)
    references.append(reference)
    targets[reference] = SweepTarget(noun, included)


def _path_element(scope: Scope, path: str) -> tuple[Component | None, bool]:
    """The element an xyce path such as ``X1:X2:R5`` names through the ``X`` lines of ``scope``
    and of each definition, and whether the walk stopped at a definition the netlist does not
    hold while a searched scope may define it elsewhere (an include)."""
    *instances, last = path.split(":")
    current = scope
    for name in instances:
        instance = next(iter(current.elements.get(current.fold(name), ())), None)
        if not isinstance(instance, SubcktInstance):
            return None, False
        child = definition_scope(current, instance.subckt.name)
        if child is None:
            return None, any(candidate.may_define_elsewhere for candidate in current.chain())
        current = child
    found = current.elements.get(current.fold(last), ())
    return (found[0] if found else None), False


def step_quantity(scope: Scope, step: StepDirective) -> tuple[str, ...]:
    """What an xyce ``.STEP`` sweeps, as a key that two lines share when Xyce sweeps one quantity
    (xm2-tasks 5.1 point 16): a device's name alone means its primary parameter (``R2`` is
    ``R2:R``, ``V1`` is ``V1:DCV0``), only when the name resolves to that device and not to a
    parameter, which Xyce looks up first; a ``DATA=`` step is keyed by its table."""
    fold = scope.fold
    if step.kind == "data":
        return ("data", fold(step.name))
    if step.kind == "temp":
        return ("temp",)
    head, colon, parameter = step.name.rpartition(":")
    if colon:
        return ("target", fold(head), fold(parameter))
    if _lookup(scope, "params", step.name) is None:
        elements = scope.elements.get(fold(step.name), ())
        primary = _PRIMARY_PARAMS.get(type(elements[0])) if elements else None
        if primary is not None:
            return ("target", fold(step.name), primary)
    return ("target", fold(step.name))


def _data_reference(scope: Scope, owner: TopLevelItem, name: str, span: Span) -> Reference:
    """A ``DATA=`` field: the top-level ``.DATA`` table of that name, the last of a repeated one,
    as Xyce uses (xm2-tasks 5.1 point 27)."""
    tables = scope_data(scope).get(scope.fold(name), ())
    return Reference("data", name, span, scope.path, owner, tables[-1] if tables else None)


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
            if token.kind == "function" and _USER_FUNCTIONS[scope.dialect]:
                if _is_schedule(owner, formula, token.text):
                    continue  # the `.TRAN` field's own keyword; its arguments are read
                if token.text.lower() not in builtin_functions(scope.dialect):
                    start = text_start + token.start
                    called = _lookup(scope, "_functions", token.text)
                    references.append(
                        Reference(
                            "function",
                            token.text,
                            Span(start, start + len(token.text)),
                            scope.path,
                            owner,
                            called[1][0] if called else None,
                        )
                    )
                continue
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
            target: object | None = None
            if found:
                target = found[1][0] if _FIRST_PARAM_WINS[scope.dialect] else found[1][-1]
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
            if found and found[0] is scope and _ORDER_MATTERS[scope.dialect]:
                first = found[1][0]
                assert isinstance(first, ParamAssignment)
                if first.name_span.start > span.start:
                    late.append(reference)


def _is_schedule(owner: object, formula: Formula, name: str) -> bool:
    """Whether ``name`` is the ``schedule`` of an xyce ``.TRAN`` schedule field (decision 0028
    item 3): the field's own word, not a function of the netlist, so no reference. It is not made
    a built-in function, since Xyce knows it nowhere else."""
    return (
        isinstance(owner, TranDirective)
        and formula is owner.schedule
        and name.lower() == "schedule"
    )


def _node_reference(scope: Scope, owner: TopLevelItem, name: str, span: Span) -> Reference:
    """A net an expression reads: resolved when ground, global, a port or an element's node in
    the scope; the target is the first node or port that names it."""
    return Reference("node", name, span, scope.path, owner, _net_node(scope, name))


def _net_node(scope: Scope, name: str) -> object | None:
    dialect = scope.dialect
    grounds = scope_replaces_ground(scope)
    if is_ground(name, dialect, replace_ground=grounds) or is_automatic_global(name, dialect):
        return name
    key = net_name(name, dialect, replace_ground=grounds)
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
    return next(
        (node for node in nodes if net_name(node.name, dialect, replace_ground=grounds) == key),
        None,
    )


def _context_words(owner: object, formula: Formula, dialect: Dialect) -> frozenset[str]:
    """The words an LTspice expression gives a meaning of its own (decision 0016 item 5).

    ``time`` in a B expression or a ``value=`` form, and ``x`` (the device's voltage or current)
    in C's ``Q=`` and L's ``Flux=``, read the simulation; a ``.param`` of the same name does not
    mask them there (m8-tasks 13.2). ngspice's ``time``, ``temper`` and ``hertz`` are reserved
    words everywhere already.
    """
    # A function's arguments are local to its body (xyce scoping.md S8).
    for function in walk_nodes(owner, FunctionDefinition, bodies=False):
        if formula is function.body:
            return frozenset(arg.name.lower() for arg in function.args)
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
