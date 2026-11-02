"""The restricted public edit API (architecture §7.2, decision 0007).

:class:`Netlist` extends the read-only :class:`netlistmod.document.Netlist` with the edit
operations. Editing is immutable and eager: each operation builds a plan against the current
text, applies and verifies it (:mod:`netlistmod.edit.verify`) and returns a **new** netlist;
the old one is unchanged. :meth:`Netlist.batch` collects several operations into one plan with
one verification. Topology has no setter (P4); the forbidden operations of §7.3 have no API.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from types import TracebackType
from typing import Generic, Self, TypeVar

from netlistmod.dialects import Dialect
from netlistmod.document import Line, ScopePath, TopologySignature
from netlistmod.document import Netlist as ReadOnlyNetlist
from netlistmod.edit import conventions, operations
from netlistmod.edit.operations import DirectiveText, UpsertTarget
from netlistmod.edit.placement import Placement
from netlistmod.edit.plan import Edit, EditPlan
from netlistmod.edit.verify import apply_plan
from netlistmod.errors import EditError
from netlistmod.model.nodes import ParseResult
from netlistmod.model.values import ParamAssignment
from netlistmod.source import DEFAULT_FALLBACKS, SourceText

_R = TypeVar("_R")


class _Operations(Generic[_R]):
    """The edit operations, shared by :class:`Netlist` (each returns a new netlist) and
    :class:`Batch` (each adds its edits to the batch and returns ``None``).

    Every element operation addresses its element by designator and definition scope. A
    non-empty ``scope`` edits the definition, and so every instance; it requires
    ``in_definition=True`` (architecture §7.4, P11).
    """

    __slots__ = ()

    def _target(self) -> Netlist:
        raise NotImplementedError

    def _submit(self, edits: Sequence[Edit], target: UpsertTarget | None = None) -> _R:
        raise NotImplementedError

    def set_value(
        self, designator: str, value: str, *, scope: ScopePath = (), in_definition: bool = False
    ) -> _R:
        """Set the value of an R, C or L line (adding it after the nodes when the line has
        only a model), or replace the DC value of a V or I line.

        ``value`` is written as given into exactly the value's span (for ``r=1k``, only
        ``1k``). ``EditError`` for a line without a value slot (D, X; K: use
        :meth:`set_coupling`) or a source without a DC value (use :meth:`set_dc`).
        """
        return self._submit(
            operations.set_value(
                self._target(), designator, value, scope=scope, in_definition=in_definition
            )
        )

    def set_formula(
        self,
        designator: str,
        expression: str,
        *,
        scope: ScopePath = (),
        in_definition: bool = False,
    ) -> _R:
        """Like :meth:`set_value`, writing the value as the brace formula ``{expression}``."""
        return self._submit(
            operations.set_value(
                self._target(),
                designator,
                conventions.formula(expression),
                scope=scope,
                in_definition=in_definition,
                reason=f"set_formula {designator}",
            )
        )

    def set_param(
        self,
        designator: str,
        name: str,
        value: str,
        *,
        scope: ScopePath = (),
        in_definition: bool = False,
    ) -> _R:
        """Set an instance parameter of an R, C, L or D line, or of an LTspice V or I line, or
        add ``name=value`` after the line's last field. On LTspice a flag takes its value in
        place (``noiseless`` → ``noiseless=1``).

        A name that is the line's value keyword (``r``, ``resistance``, …) sets the value when
        it is written that way, otherwise ``EditError`` (use :meth:`set_value`). A repeated
        parameter is an ``EditError``; an X line takes :meth:`set_instance_param`.
        """
        return self._submit(
            operations.set_param(
                self._target(), designator, name, value, scope=scope, in_definition=in_definition
            ),
            operations.upsert_target(self._target(), "set_param", scope, designator, name),
        )

    def set_model(
        self,
        designator: str,
        model: str,
        *,
        scope: ScopePath = (),
        in_definition: bool = False,
        allow_external: bool = False,
    ) -> _R:
        """Replace the model name of an R, C, L or D line, or add one after the value of an
        R, C or L line that has none (``R1 a b 1k`` → ``R1 a b 1k rmod``).

        The model must resolve from the element's scope with a type allowed for the element
        (R → ``R``, C → ``C``, L → ``L``, D → ``D``), otherwise ``EditError``. An unresolved
        model is accepted only with ``allow_external=True`` when an ``.include`` or ``.lib``
        is in a searched scope (decision 0007 item 3). A value written ``r=1k`` takes no
        model. ngspice uses a given value over the model's geometry; see
        :meth:`remove_value`. LTspice has no R, C or L model, so there only a D line takes one,
        and an R, C or L line is an ``EditError``.
        """
        return self._submit(
            operations.set_model(
                self._target(),
                designator,
                model,
                scope=scope,
                in_definition=in_definition,
                allow_external=allow_external,
            )
        )

    def remove_value(
        self, designator: str, *, scope: ScopePath = (), in_definition: bool = False
    ) -> _R:
        """Remove the value of an R, C or L line that names a model, so the model's geometry
        applies (``R1 a b 1k rmod l=20u w=1u`` → ``R1 a b  rmod l=20u w=1u``).

        Only the value's text is removed; the blank before it stays. ``EditError`` if the line
        has no value or no model (it would have neither, which the grammar forbids), and always
        on LTspice, which has no R, C or L model.
        """
        return self._submit(
            operations.remove_value(
                self._target(), designator, scope=scope, in_definition=in_definition
            )
        )

    def set_dc(
        self, designator: str, value: str, *, scope: ScopePath = (), in_definition: bool = False
    ) -> _R:
        """Replace the DC value of a V or I line, or add ``DC value`` after its nodes."""
        return self._submit(
            operations.set_dc(
                self._target(), designator, value, scope=scope, in_definition=in_definition
            ),
            operations.upsert_target(self._target(), "set_dc", scope, designator),
        )

    def set_ac(
        self,
        designator: str,
        magnitude: str,
        phase: str | None = None,
        *,
        scope: ScopePath = (),
        in_definition: bool = False,
    ) -> _R:
        """Set the AC magnitude (and phase, if given) of a V or I line.

        Without an AC part, ``AC magnitude [phase]`` is added after the DC part (or the
        nodes); with one, the magnitude is replaced and the phase replaced or added.
        """
        return self._submit(
            operations.set_ac(
                self._target(),
                designator,
                magnitude,
                phase,
                scope=scope,
                in_definition=in_definition,
            ),
            operations.upsert_target(self._target(), "set_ac", scope, designator),
        )

    def set_coupling(
        self, designator: str, value: str, *, scope: ScopePath = (), in_definition: bool = False
    ) -> _R:
        """Replace the coupling value of a K line."""
        return self._submit(
            operations.set_coupling(
                self._target(), designator, value, scope=scope, in_definition=in_definition
            )
        )

    def set_instance_param(
        self,
        designator: str,
        name: str,
        value: str,
        *,
        scope: ScopePath = (),
        in_definition: bool = False,
    ) -> _R:
        """Set or add a parameter override on an X line, which changes one instance only
        (architecture §7.4). A string value is quoted by the caller (``'"text"'``)."""
        return self._submit(
            operations.set_instance_param(
                self._target(), designator, name, value, scope=scope, in_definition=in_definition
            ),
            operations.upsert_target(self._target(), "set_instance_param", scope, designator, name),
        )

    def set_model_param(
        self,
        model: str,
        name: str,
        value: str,
        *,
        scope: ScopePath = (),
        in_definition: bool = False,
    ) -> _R:
        """Set a parameter of the ``.model`` defined in ``scope``, or add ``name=value`` after
        its last parameter (inside the parentheses, if any)."""
        return self._submit(
            operations.set_model_param(
                self._target(), model, name, value, scope=scope, in_definition=in_definition
            ),
            operations.upsert_target(self._target(), "set_model_param", scope, model, name),
        )

    def add_include(self, path: str, placement: Placement = Placement.AFTER_TITLE) -> _R:
        """Add ``.include "path"`` for a harness file (architecture §7.9).

        The path is written as given and never read; ngspice resolves a relative path from the
        netlist file's folder. An include with the same statement text is an ``EditError``.
        """
        return self._submit(
            operations.add_include(self._target(), path, placement),
            operations.include_target(path),
        )


class ParamTable(Mapping[str, tuple[ParamAssignment, ...]], Generic[_R]):
    """The top-level parameters by folded name (as in the read-only netlist), plus
    :meth:`set`."""

    __slots__ = ("_operations", "_table")

    def __init__(
        self,
        table: Mapping[str, tuple[ParamAssignment, ...]],
        operations_: _Operations[_R],
    ) -> None:
        """Wrap the read-only table and the operations that submit edits."""
        self._table = table
        self._operations = operations_

    def __getitem__(self, name: str) -> tuple[ParamAssignment, ...]:
        """Every assignment of a folded name, in source order."""
        return self._table[name]

    def __iter__(self) -> Iterator[str]:
        """Iterate over the folded names."""
        return iter(self._table)

    def __len__(self) -> int:
        """Return the number of names."""
        return len(self._table)

    def set(
        self,
        name: str,
        value: str,
        *,
        scope: ScopePath = (),
        in_definition: bool = False,
        placement: Placement | None = None,
    ) -> _R:
        """Set a parameter: replace the value of its effective (last) assignment in ``scope``,
        or add ``.param name=value`` (decision 0007 item 7).

        A new line goes to ``placement``: by default after the last ``.param`` of the scope
        (after the title, or at the start of a definition's body, when there is none).
        ``value`` is written as given; a bare expression does not parse (write ``{…}``).
        """
        return self._operations._submit(
            operations.set_param_statement(
                self._operations._target(),
                name,
                value,
                scope=scope,
                in_definition=in_definition,
                placement=placement,
            ),
            operations.upsert_target(self._operations._target(), "params.set", scope, name),
        )


class DirectiveEditor(Generic[_R]):
    """Add, replace, remove and upsert top-level directives and whole opaque items
    (decision 0007 items 6 and 7, review round 1).

    ``text`` is one physical line, or a sequence of physical lines for a continued statement
    or a block (``[".tran 1u 10m", "+ 0 1u"]``); the lines are joined with the line ending of
    the insertion point. It must parse as exactly one typed directive, unknown dot-command,
    whole ``.control`` or ``.if`` block, or ``.lib`` statement. An element, ``.subckt`` or
    ``.global`` is a ``TopologyError``; an ``.include`` is added with ``add_include``; anything
    else is an ``EditError``. The contents of an opaque item are never edited: it is added,
    replaced or removed whole.
    """

    __slots__ = ("_operations",)

    def __init__(self, operations_: _Operations[_R]) -> None:
        """Bind the editor to the operations that submit edits."""
        self._operations = operations_

    def add(self, text: DirectiveText, placement: Placement = Placement.BEFORE_END) -> _R:
        """Insert one directive or opaque item (before ``.end`` by default)."""
        return self._operations._submit(
            operations.add_directive(self._operations._target(), text, placement)
        )

    def replace(self, line: Line | object, text: DirectiveText) -> _R:
        """Replace a whole directive line or opaque item (a ``Line`` or its item) with one
        directive or opaque item."""
        return self._operations._submit(
            operations.replace_directive(self._operations._target(), line, text)
        )

    def remove(self, line: Line | object) -> _R:
        """Remove a whole directive line, ``.control``/``.if`` block or ``.include``/``.lib``
        statement (a ``Line`` or its item). What a removed include defined is not checked
        (architecture §7.8)."""
        return self._operations._submit(
            operations.remove_directive(self._operations._target(), line)
        )

    def set(self, text: DirectiveText) -> _R:
        """Upsert a singleton directive (``.tran``, ``.ac``, ``.dc``, ``.op``, ``.temp``):
        replace the one line of its kind or add one before ``.end``. An LTspice ``.step`` is
        upserted by the quantity it sweeps, so ``.step`` lines of different quantities coexist.

        ``EditError`` with two or more lines of the kind (or of the quantity), or for a
        repeatable kind.
        """
        target = self._operations._target()
        return self._operations._submit(
            operations.set_directive(target, text), operations.directive_target(target, text)
        )


class Netlist(ReadOnlyNetlist, _Operations["Netlist"]):
    """A parsed netlist that can be edited; build it with ``load``, ``from_text`` or
    ``from_source``.

    Every edit method returns a **new** netlist, re-parsed and verified against the topology
    signature taken when the original file was loaded (decision 0007). Lines and nodes belong
    to the netlist they came from: look them up again in the netlist being edited.
    """

    __slots__ = ("_baseline", "_path")

    def __init__(
        self,
        source: SourceText,
        result: ParseResult,
        *,
        dialect: Dialect,
        rkm: bool,
        baseline: TopologySignature | None = None,
        path: Path | None = None,
    ) -> None:
        """Wrap a source and its parse; use the class constructors instead."""
        super().__init__(source, result, dialect=dialect, rkm=rkm)
        self._baseline = self.signature() if baseline is None else baseline
        self._path = path

    @classmethod
    def load(
        cls,
        path: str | os.PathLike[str],
        *,
        dialect: Dialect,
        rkm: bool = False,
        fallback_encodings: Sequence[str] = DEFAULT_FALLBACKS,
    ) -> Self:
        """Read and parse a file; :meth:`save` without a path writes back to it."""
        netlist = super().load(
            path, dialect=dialect, rkm=rkm, fallback_encodings=fallback_encodings
        )
        netlist._path = Path(path)
        return netlist

    @property
    def path(self) -> Path | None:
        """The file the original netlist was loaded from, or ``None``."""
        return self._path

    @property
    def baseline(self) -> TopologySignature:
        """The topology signature of the original load, which every edit is verified against."""
        return self._baseline

    @property
    def params(self) -> ParamTable[Netlist]:
        """Top-level parameters by folded name; ``params.set`` upserts one."""
        return ParamTable(super().params, self)

    @property
    def directives(self) -> DirectiveEditor[Netlist]:
        """Add, replace, remove and upsert directives."""
        return DirectiveEditor(self)

    def batch(self) -> Batch:
        """Collect several operations into one plan, applied with one verification.

        Use it as a context manager; on a clean exit the plan is applied and the new netlist
        is :attr:`Batch.result`. It is all or nothing: if an operation or the verification
        fails, nothing is applied and this netlist is unchanged.
        """
        return Batch(self)

    def apply(self, plan: EditPlan | Iterable[Edit]) -> Netlist:
        """Apply a plan with the full verification (decision 0007 item 8); a new netlist.

        This is the only way a hand-built plan reaches a netlist, so it cannot bypass the
        topology check. An empty plan returns this netlist.
        """
        plan = plan if isinstance(plan, EditPlan) else EditPlan(plan)
        if not plan.edits:
            return self
        return apply_plan(
            self.source,
            self.parse_result,
            plan,
            dialect=self.dialect,
            rkm=self.rkm,
            baseline=self._baseline,
            build=self._derive,
        )

    def verify(self) -> None:
        """Re-parse the current text and compare its signature with the load baseline.

        ``EditError`` if it does not parse, ``TopologyViolation`` if the topology differs.
        """
        apply_plan(
            self.source,
            self.parse_result,
            EditPlan(),
            dialect=self.dialect,
            rkm=self.rkm,
            baseline=self._baseline,
            build=self._derive,
        )

    def save(self, path: str | os.PathLike[str] | None = None) -> None:
        """Verify, then write the text atomically in the original encoding, BOM and line
        endings (P3); ``path`` defaults to the file the netlist was loaded from.

        ``EncodingError`` if the text cannot be encoded, raised before anything is written. An
        unedited netlist writes its original bytes.
        """
        target = path if path is not None else self._path
        if target is None:
            raise EditError("save() needs a path: this netlist was not loaded from a file")
        self.verify()
        self.source.write(target)

    def _derive(self, source: SourceText, result: ParseResult) -> Netlist:
        return Netlist(
            source,
            result,
            dialect=self.dialect,
            rkm=self.rkm,
            baseline=self._baseline,
            path=self._path,
        )

    def _target(self) -> Netlist:
        return self

    def _submit(self, edits: Sequence[Edit], target: UpsertTarget | None = None) -> Netlist:
        return self.apply(EditPlan(edits))


class Batch(_Operations[None]):
    """Operations collected into one plan (decision 0007 item 1).

    Each operation is computed against the netlist the batch was opened on and adds its edits;
    two edits of the same span are an ``EditError`` when the plan is applied. A second upsert
    of one target is an ``EditError`` when it is submitted, whether or not the target exists
    yet (decision 0010 item 5).
    """

    __slots__ = ("_closed", "_edits", "_netlist", "_result", "_targets")

    def __init__(self, netlist: Netlist) -> None:
        """Open a batch on ``netlist``; prefer :meth:`Netlist.batch`."""
        self._netlist = netlist
        self._edits: list[Edit] = []
        self._targets: set[UpsertTarget] = set()
        self._result: Netlist | None = None
        self._closed = False

    def __enter__(self) -> Self:
        """Return the batch."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Apply the collected plan unless the block raised."""
        self._closed = True
        if exc_type is None:
            self._result = self._netlist.apply(EditPlan(self._edits))

    @property
    def params(self) -> ParamTable[None]:
        """The top-level parameters; ``params.set`` adds an upsert to the batch."""
        return ParamTable(self._netlist.params, self)

    @property
    def directives(self) -> DirectiveEditor[None]:
        """Directive operations that add to the batch."""
        return DirectiveEditor(self)

    @property
    def plan(self) -> EditPlan:
        """The edits collected so far."""
        return EditPlan(self._edits)

    @property
    def result(self) -> Netlist:
        """The edited netlist; ``EditError`` until the batch has been applied."""
        if self._result is None:
            raise EditError("the batch has not been applied (use it in a `with` block)")
        return self._result

    def _target(self) -> Netlist:
        return self._netlist

    def _submit(self, edits: Sequence[Edit], target: UpsertTarget | None = None) -> None:
        if self._closed:
            raise EditError("the batch is closed; open a new one with netlist.batch()")
        if target is not None:
            if target in self._targets:
                raise EditError(
                    f"{target.label}: this batch already sets this target, and each operation "
                    "is computed against the netlist the batch was opened on; make one upsert "
                    "per target"
                )
            self._targets.add(target)
        self._edits.extend(edits)
