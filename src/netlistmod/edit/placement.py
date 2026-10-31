"""Where an added line goes (architecture §7.2, decision 0007 item 6).

A :class:`Placement` resolves to a zero-width insertion point at a physical-line boundary of
the netlist it is applied to. Placements never resolve after ``.end``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

from netlistmod.document import Line, Lines, Netlist, ScopePath
from netlistmod.errors import EditError
from netlistmod.model.nodes import End, ParamStatement, SubcktDefinition, Title

PlacementKind = Literal["after_title", "after_last_param", "before_end", "before", "after"]


@dataclass(frozen=True, slots=True, eq=False)
class Placement:
    """An insertion strategy: one of the constants, or ``before(line)`` / ``after(line)``.

    - ``AFTER_TITLE``: right after the title line.
    - ``AFTER_LAST_PARAM``: after the last top-level ``.param`` line, or after the title when
      there is none. In a subcircuit definition: after the body's last ``.param``, or at the
      start of the body.
    - ``BEFORE_END``: right before the ``.end`` line.
    - ``before(line)`` / ``after(line)``: next to a line of the netlist being edited (a line
      from another netlist is an ``EditError``).
    """

    kind: PlacementKind
    anchor: Line | None = None

    AFTER_TITLE: ClassVar[Placement]
    AFTER_LAST_PARAM: ClassVar[Placement]
    BEFORE_END: ClassVar[Placement]

    @classmethod
    def before(cls, line: Line) -> Placement:
        """Insert right before ``line`` (at the start of its first physical line)."""
        return cls("before", line)

    @classmethod
    def after(cls, line: Line) -> Placement:
        """Insert right after ``line`` (after its terminator)."""
        return cls("after", line)

    def __repr__(self) -> str:
        """Show the kind and, for an anchor, its physical line."""
        if self.anchor is None:
            return f"Placement.{self.kind.upper()}"
        return f"Placement.{self.kind}(line {self.anchor.first_line})"


Placement.AFTER_TITLE = Placement("after_title")
Placement.AFTER_LAST_PARAM = Placement("after_last_param")
Placement.BEFORE_END = Placement("before_end")


def insertion_point(placement: Placement, netlist: Netlist, scope: ScopePath = ()) -> int:
    """Resolve ``placement`` to an offset in ``netlist``'s text for a line of ``scope``.

    Directives and ``.include`` lines go to the top level (``scope=()``); a ``.param`` may go
    into a definition's body, where only ``AFTER_LAST_PARAM`` and anchors of that body apply.
    """
    if scope:
        definition_scope = netlist.scope(scope)
        definition = definition_scope.definition
        assert definition is not None
        return _in_body(placement, definition, definition_scope.lines, scope)
    lines = netlist.lines
    if placement.kind == "after_title":
        return _title(lines).span.end
    if placement.kind == "after_last_param":
        params = lines.find_all(ParamStatement)
        return params[-1].span.end if params else _title(lines).span.end
    if placement.kind == "before_end":
        end = lines.find(End)
        assert end is not None  # the grammar requires .end
        return end.span.start
    anchor = _anchor(placement, lines, "the top level")
    if placement.kind == "before":
        if isinstance(anchor.item, Title):
            raise EditError("cannot insert before the title: the first line is always the title")
        return anchor.span.start
    if isinstance(anchor.item, End):
        raise EditError("cannot insert after `.end`: the netlist ends there (decision 0007)")
    return anchor.span.end


def _in_body(
    placement: Placement, definition: SubcktDefinition, body: Lines, scope: ScopePath
) -> int:
    if placement.kind == "after_last_param":
        params = body.find_all(ParamStatement)
        return params[-1].span.end if params else definition.header_span.end
    if placement.anchor is None:
        raise EditError(
            f"{placement!r} does not apply inside subcircuit `{definition.name}`; use "
            "AFTER_LAST_PARAM or a line of its body"
        )
    anchor = _anchor(placement, body, f"the body of subcircuit `{definition.name}`")
    return anchor.span.start if placement.kind == "before" else anchor.span.end


def _anchor(placement: Placement, lines: Lines, where: str) -> Line:
    anchor = placement.anchor
    assert anchor is not None
    if not any(line is anchor for line in lines):
        raise EditError(
            f"the anchor line (line {anchor.first_line}) is not a line of {where} of this "
            "netlist; look the line up again in the netlist being edited"
        )
    return anchor


def _title(lines: Lines) -> Line:
    title = lines[0]
    assert isinstance(title.item, Title)  # the grammar makes the first line the title
    return title
