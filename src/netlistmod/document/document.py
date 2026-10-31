"""The read-only netlist document (architecture §3 layer [3], decision 0006).

A :class:`Netlist` holds the source text and its parse (P1). Its lines, scopes, symbol tables,
references, topology and diagnostics are views over that parse; nothing is copied or edited.
Editing and ``save()`` are added by :class:`netlistmod.edit.Netlist`, which extends this class
(decision 0007); ``document/`` does not import ``edit/``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Self

from netlistmod.dialects import Dialect
from netlistmod.document.diagnostics import Diagnostic, collect_diagnostics
from netlistmod.document.index import Index, Reference, Scope
from netlistmod.document.lines import Lines, ScopePath
from netlistmod.document.names import fold
from netlistmod.document.topology import (
    Connection,
    Net,
    TopologySignature,
    TopologyView,
)
from netlistmod.model.nodes import (
    Component,
    ModelStatement,
    ParseResult,
    SubcktDefinition,
)
from netlistmod.model.transform import parse
from netlistmod.model.values import ParamAssignment
from netlistmod.source import DEFAULT_FALLBACKS, SourceText, Span


class Netlist:
    """A parsed netlist with read-only queries; build it with ``load``, ``from_text`` or
    ``from_source``.

    The dialect is always explicit (no default, no detection). ``rkm=True`` accepts RKM values
    (decision 0004). Parsing errors raise ``ParseError`` or ``UnsupportedConstruct``; every
    other finding is a :class:`Diagnostic` in :attr:`diagnostics`.

    Scopes are definition scopes (decision 0006 item 5): ``scope=()`` is the top level and
    ``scope=("amp",)`` the body of ``.subckt amp``, shared by every instance. Names compare
    case-insensitively (``names.md``). Opaque ``.if`` blocks and ``.include``/``.lib`` files
    are not read: their elements, models and parameters are not seen (§7.8).
    """

    __slots__ = ("_diagnostics", "_dialect", "_index", "_result", "_rkm", "_source", "_topology")

    def __init__(
        self, source: SourceText, result: ParseResult, *, dialect: Dialect, rkm: bool
    ) -> None:
        """Wrap a source and its parse; use the class constructors instead."""
        self._source = source
        self._result = result
        self._dialect = dialect
        self._rkm = rkm
        self._index = Index(result.items, source)
        self._topology = TopologyView(self._index)
        self._diagnostics = collect_diagnostics(self._index, source)

    @classmethod
    def load(
        cls,
        path: str | os.PathLike[str],
        *,
        dialect: Dialect,
        rkm: bool = False,
        fallback_encodings: Sequence[str] = DEFAULT_FALLBACKS,
    ) -> Self:
        """Read and parse a file (bytes, no newline translation; decision 0001)."""
        source = SourceText.read(path, fallback_encodings=fallback_encodings)
        return cls.from_source(source, dialect=dialect, rkm=rkm)

    @classmethod
    def from_text(cls, text: str, *, dialect: Dialect, rkm: bool = False) -> Self:
        """Parse decoded text; it is saved as UTF-8 without a BOM."""
        return cls.from_source(SourceText(text), dialect=dialect, rkm=rkm)

    @classmethod
    def from_source(cls, source: SourceText, *, dialect: Dialect, rkm: bool = False) -> Self:
        """Parse a :class:`SourceText`."""
        return cls(source, parse(source, dialect, rkm=rkm), dialect=dialect, rkm=rkm)

    # Source.

    @property
    def source(self) -> SourceText:
        """The source text exactly as read (P1)."""
        return self._source

    @property
    def text(self) -> str:
        """The decoded source text."""
        return self._source.text

    @property
    def dialect(self) -> Dialect:
        """The dialect the netlist was parsed with."""
        return self._dialect

    @property
    def rkm(self) -> bool:
        """Whether RKM values were accepted."""
        return self._rkm

    @property
    def parse_result(self) -> ParseResult:
        """The typed top-level items, whose spans tile the source."""
        return self._result

    def to_bytes(self) -> bytes:
        """The original bytes: encoding, BOM and line endings unchanged (P3)."""
        return self._source.to_bytes()

    def slice(self, span: Span) -> str:
        """The source text of ``span``."""
        return self._source.text[span.start : span.end]

    # Lines and scopes.

    @property
    def lines(self) -> Lines:
        """The top-level logical lines (decision 0006 item 2)."""
        return self._index.lines

    @property
    def scopes(self) -> tuple[Scope, ...]:
        """Every definition scope, depth first in source order, starting with the top level."""
        return self._index.scopes

    def scope(self, path: ScopePath = ()) -> Scope:
        """The scope at ``path``; ``KeyError`` if there is no such definition."""
        return self._index.scope(path)

    # Symbol tables (of the top level; other scopes through ``scope(path)``).

    @property
    def params(self) -> Mapping[str, tuple[ParamAssignment, ...]]:
        """Top-level parameters by folded name, every assignment in source order."""
        return self._index.root.params

    @property
    def models(self) -> Mapping[str, tuple[ModelStatement, ...]]:
        """Top-level models by folded name."""
        return self._index.root.models

    @property
    def subckts(self) -> Mapping[str, tuple[SubcktDefinition, ...]]:
        """Top-level subcircuit definitions by folded name."""
        return self._index.root.subckts

    def element(self, designator: str, scope: ScopePath = ()) -> Component:
        """The element with this designator in a scope (the first one if it is repeated).

        ``KeyError`` if there is none; elements of enclosing or nested scopes are not searched.
        """
        found = self._index.scope(scope)
        elements = found.elements.get(fold(designator))
        if not elements:
            raise KeyError(f"no element {designator!r} in {found.describe()}")
        return elements[0]

    def elements(self, scope: ScopePath = (), *, recursive: bool = False) -> tuple[Component, ...]:
        """The elements of a scope in source order; ``recursive`` adds nested definitions."""
        found = self._index.scope(scope)
        lines = found.lines.walk() if recursive else iter(found.lines)
        return tuple(line.item for line in lines if isinstance(line.item, Component))

    # References.

    @property
    def references(self) -> tuple[Reference, ...]:
        """Every reference in the netlist, in source order, each resolved or not."""
        return self._index.references

    def references_to_param(self, name: str, scope: ScopePath = ()) -> tuple[Reference, ...]:
        """The references that resolve to the parameter ``name`` defined in ``scope``.

        A reference from a nested definition is included unless that definition masks the
        name with its own default or ``.param``.
        """
        definitions = self._index.scope(scope).params.get(fold(name), ())
        return tuple(
            reference
            for reference in self._index.references
            if reference.kind == "param"
            and any(reference.target is definition for definition in definitions)
        )

    def resolve(self, reference: Reference) -> object | None:
        """The definition a reference resolves to, or ``None`` (``reference.target``)."""
        if not any(reference is known for known in self._index.references):
            raise ValueError("the reference does not belong to this netlist")
        return reference.target

    # Topology.

    @property
    def topology(self) -> TopologyView:
        """The read-only topology view."""
        return self._topology

    def nets(self, scope: ScopePath = ()) -> tuple[Net, ...]:
        """The nets used in a scope (see :meth:`TopologyView.nets`)."""
        return self._topology.nets(scope)

    def elements_on_net(self, net: Net | str, scope: ScopePath = ()) -> tuple[Component, ...]:
        """The elements of a scope connected to ``net``."""
        return self._topology.elements_on_net(net, scope)

    def connections(self, designator: str, scope: ScopePath = ()) -> tuple[Connection, ...]:
        """The terminals of one element and their nets."""
        return self._topology.connections(designator, scope)

    def ports(self, subckt: str, scope: ScopePath = ()) -> tuple[Net, ...]:
        """The port nets of a subcircuit definition visible from ``scope``."""
        return self._topology.ports(subckt, scope)

    def signature(self) -> TopologySignature:
        """The topology signature that M6's write-time check compares (§7.7)."""
        return self._topology.signature()

    # Diagnostics.

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        """Every diagnostic, in source order; computed once at load, never raised (§8)."""
        return self._diagnostics

    def __repr__(self) -> str:
        """Show the dialect and size."""
        return f"Netlist({self._dialect.value}, {len(self.lines)} lines)"
