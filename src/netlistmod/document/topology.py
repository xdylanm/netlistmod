"""Read-only topology queries and the topology signature (architecture §7.7, decision 0006).

Net identity follows ``docs/grammars/<dialect>/names.md``: node names compare case-insensitively;
``0`` and ``gnd`` are the one ground net ``"0"``; a net inside a subcircuit definition is local
to that definition unless it is ground, a ``.global`` node or an LTspice ``$G_*`` node, which are
shared by every scope.
A definition's ports are nets of its own scope. Elements inside opaque ``.if`` blocks and
included files are not seen (§7.8).

The signature, unlike the queries, uses the exact text of every topology token, so a change
that only alters case (``GND`` to ``gnd``) is caught by M6's write-time check.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass, field

from netlistmod.document.index import Index, Scope
from netlistmod.document.lines import ScopePath
from netlistmod.document.names import GROUND, is_automatic_global, is_ground, net_name
from netlistmod.model.nodes import (
    Cccs,
    Ccvs,
    Component,
    CurrentSwitch,
    GlobalDirective,
    MutualCoupling,
    Node,
    SubcktDefinition,
    SubcktInstance,
)

SignatureEntry = tuple[object, ...]


@dataclass(frozen=True, slots=True)
class Net:
    """A net: its canonical name and the scope it belongs to.

    ``name`` is folded (``"0"`` for ground). ``scope`` is ``()`` for a net that is shared by
    every scope (``global_``: ground, a ``.global`` node or an LTspice ``$G_*`` node), otherwise
    the definition scope.
    ``spellings`` lists the names as written, in first-seen order; nets compare by name and
    scope only.
    """

    name: str
    scope: ScopePath
    spellings: tuple[str, ...] = field(compare=False)
    global_: bool = field(compare=False)


@dataclass(frozen=True, slots=True)
class Connection:
    """One terminal of an element: its 0-based position, the node as written and its net."""

    element: Component
    terminal: int
    node: Node
    net: Net


@dataclass(frozen=True, slots=True)
class TopologySignature:
    """The ordered topology entries of a netlist; equal signatures mean equal topology.

    Entries hold the exact text of every topology token: each element's scope, designator,
    type and ordered nodes; each definition's name and ordered ports; each ``X`` line's nodes
    and subcircuit name; each ``K`` line's inductors; each F, H and W line's controlling
    source; and the ``.global`` node set.
    """

    entries: tuple[SignatureEntry, ...]

    def digest(self) -> str:
        """A stable SHA-256 hex digest of a canonical JSON encoding of the entries."""
        encoded = json.dumps(self.entries, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class TopologyView:
    """Nets, connections and ports of a netlist, by definition scope."""

    def __init__(self, index: Index) -> None:
        """Compute the nets of every scope."""
        self._index = index
        self._dialect = index.dialect
        self._globals = frozenset(
            index.root.fold(node.name)
            for line in index.lines
            if isinstance(line.item, GlobalDirective)
            for node in line.item.nodes
        )
        spellings: dict[tuple[ScopePath, str], dict[str, None]] = {}
        self._scope_nets: dict[int, dict[tuple[ScopePath, str], None]] = {}
        for scope in index.scopes:
            used: dict[tuple[ScopePath, str], None] = {}
            for node in self._scope_nodes(scope):
                key = self._key(scope, node.name)
                used.setdefault(key, None)
                spellings.setdefault(key, {}).setdefault(node.name, None)
            self._scope_nets[id(scope)] = used
        self._nets = {
            key: Net(key[1], key[0], tuple(names), global_=not key[0] and self._shared(key[1]))
            for key, names in spellings.items()
        }

    def nets(self, scope: ScopePath = ()) -> tuple[Net, ...]:
        """The nets used in a scope, in first-use order (ports first in a definition).

        A scope's nets come from its ports, its elements' nodes and, at the top level, the
        ``.global`` nodes; ground and ``.global`` nets are listed in each scope that uses them.
        """
        found = self._index.scope(scope)
        return tuple(self._nets[key] for key in self._scope_nets[id(found)])

    def net(self, name: str, scope: ScopePath = ()) -> Net:
        """The net a node name denotes in a scope; ``KeyError`` if no element uses it there."""
        found = self._index.scope(scope)
        key = self._key(found, name)
        if key not in self._scope_nets[id(found)]:
            raise KeyError(f"no net {name!r} in {found.describe()}")
        return self._nets[key]

    def elements_on_net(self, net: Net | str, scope: ScopePath = ()) -> tuple[Component, ...]:
        """The elements of a scope with at least one terminal on ``net``, in source order."""
        found = self._index.scope(scope)
        key = (net.scope, net.name) if isinstance(net, Net) else self._key(found, net)
        return tuple(
            element
            for element in _components(found)
            if any(self._key(found, node.name) == key for node in element.nodes)
        )

    def connections(self, designator: str, scope: ScopePath = ()) -> tuple[Connection, ...]:
        """The terminals of one element (a ``K`` line has none); ``KeyError`` if absent."""
        found = self._index.scope(scope)
        elements = found.elements.get(found.fold(designator))
        if not elements:
            raise KeyError(f"no element {designator!r} in {found.describe()}")
        element = elements[0]
        return tuple(
            Connection(element, terminal, node, self._nets[self._key(found, node.name)])
            for terminal, node in enumerate(element.nodes)
        )

    def ports(self, subckt: str, scope: ScopePath = ()) -> tuple[Net, ...]:
        """The port nets of the definition ``subckt`` visible from ``scope``, in order.

        The name is resolved like an ``X`` line's (own scope, then enclosing scopes); the nets
        belong to the definition's scope. ``KeyError`` if no such definition is visible.
        """
        found = self._index.scope(scope)
        for candidate in found.chain():
            for child in candidate.children:
                if child.path[-1] == found.fold(subckt):
                    assert child.definition is not None
                    return tuple(
                        self._nets[self._key(child, port.name)] for port in child.definition.ports
                    )
        raise KeyError(f"no subcircuit {subckt!r} visible from {found.describe()}")

    def signature(self) -> TopologySignature:
        """The topology signature (see :class:`TopologySignature`)."""
        entries: list[SignatureEntry] = []
        _signature_entries(self._index.root, entries)
        global_nodes = sorted(
            {
                node.name
                for line in self._index.lines
                if isinstance(line.item, GlobalDirective)
                for node in line.item.nodes
            }
        )
        entries.append(("global", tuple(global_nodes)))
        return TopologySignature(tuple(entries))

    def _shared(self, name: str) -> bool:
        return name == GROUND or name in self._globals or is_automatic_global(name, self._dialect)

    def _key(self, scope: Scope, name: str) -> tuple[ScopePath, str]:
        canonical = net_name(name, self._dialect)
        if (
            is_ground(name, self._dialect)
            or canonical in self._globals
            or is_automatic_global(name, self._dialect)
        ):
            return ((), canonical)
        return (scope.path, canonical)

    def _scope_nodes(self, scope: Scope) -> Iterator[Node]:
        if scope.definition is not None:
            yield from scope.definition.ports
        for line in scope.lines:
            if isinstance(line.item, Component | GlobalDirective):
                yield from line.item.nodes


def _components(scope: Scope) -> Iterator[Component]:
    for line in scope.lines:
        if isinstance(line.item, Component):
            yield line.item


def _signature_entries(scope: Scope, entries: list[SignatureEntry]) -> None:
    children = iter(scope.children)
    for line in scope.lines:
        item = line.item
        if isinstance(item, SubcktDefinition):
            entries.append(
                ("subckt", scope.display, item.name, tuple(port.name for port in item.ports))
            )
            _signature_entries(next(children), entries)
        elif isinstance(item, SubcktInstance):
            nodes = tuple(node.name for node in item.nodes)
            entries.append(("instance", scope.display, item.designator, nodes, item.subckt.name))
        elif isinstance(item, MutualCoupling):
            inductors = tuple(inductor.designator for inductor in item.inductors)
            entries.append(("coupling", scope.display, item.designator, inductors))
        elif isinstance(item, Component):
            nodes = tuple(node.name for node in item.nodes)
            entries.append(("element", scope.display, item.designator, type(item).__name__, nodes))
            if isinstance(item, Cccs | Ccvs | CurrentSwitch):
                # A controlling source is topology but not a net (decision 0015 item 3).
                entries.append(("control", scope.display, item.designator, item.control.designator))
