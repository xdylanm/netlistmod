"""Table and polynomial operations: the points of TABLE, ``table=``, FREQ and the gates, and the
coefficients of POLY (decision 0017 item 6)."""

from __future__ import annotations

from collections.abc import Sequence

from netlistmod.dialects import Dialect
from netlistmod.document import Netlist, ScopePath
from netlistmod.edit._ops_common import _VALUE, _element, _kind
from netlistmod.edit.plan import Edit, SlotCheck
from netlistmod.errors import EditError
from netlistmod.model._rules_elements import _reads_as_number
from netlistmod.model._rules_nonlinear import _is_plain_frequency
from netlistmod.model.nodes import ControlledSource, Table
from netlistmod.model.values import Formula
from netlistmod.source import Span

_TABLE = SlotCheck((Table,), "a table")
# The fewest coefficients a polynomial takes, by dialect: ngspice stops with fewer than two,
# LTspice runs one (the constant).
_MIN_COEFFICIENTS = {Dialect.NGSPICE: 2, Dialect.LTSPICE: 1}
_DELIMITERS = ("{", "'")


def use_instead(element: ControlledSource) -> str:
    """The operation that edits what an expression-less form holds, for ``set_value``'s message."""
    if element.form == "poly":
        return "set_poly_coefficients"
    if element.table is not None and element.expression is not None:
        return "set_expression for the expression and set_table for the points"
    if element.table is not None:
        return "set_table"
    return "set_expression"


def set_table(
    netlist: Netlist,
    designator: str,
    points: Sequence[Sequence[str]],
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Replace the points of a TABLE, ``table=``, FREQ or gate line.

    ``points`` holds one sequence of value texts for each point: two values, or three for FREQ.
    The new points are written in the layout the line has (each in its own parentheses, or one
    flat list) with the separator written between its first two values, and the number of points
    may change. When the shape is the same, only the values are replaced. The refusals are made
    before verification: a point of the wrong width, fewer points than the form takes (two for a
    gate or ``table=``, one for ngspice TABLE and FREQ), a number that is not a number on ngspice
    TABLE, and a frequency with a unit suffix.
    """
    element = _element(netlist, designator, scope, in_definition)
    if not isinstance(element, ControlledSource) or element.table is None:
        what = (
            "has POLY coefficients, not a table; use set_poly_coefficients"
            if isinstance(element, ControlledSource) and element.form == "poly"
            else f"is a {_kind(element)} line and has no table"
        )
        raise EditError(f"`{designator}` {what}")
    table = element.table
    rows = [tuple(str(value) for value in row) for row in points]
    _check_points(netlist.dialect, element, rows)
    reason = f"set_table {designator}"
    if len(rows) == len(table.points):
        return [
            Edit(old.span, new, reason, (_VALUE,))
            for point, row in zip(table.points, rows)
            for old, new in zip(point.values, row)
        ]
    text = netlist.source.text
    first = table.points[0].values
    separator = ", " if "," in text[first[0].span.end : first[1].span.start] else " "
    return [Edit(table.span, _write_table(table, rows, separator), reason, (_TABLE,))]


def _check_points(dialect: Dialect, element: ControlledSource, rows: list[tuple[str, ...]]) -> None:
    designator = element.designator
    freq = element.form == "freq"
    width = 3 if freq else 2
    for row in rows:
        if len(row) != width:
            raise EditError(
                f"a point of `{designator}` takes {width} values"
                + (" (frequency, magnitude, phase)" if freq else " (x, y)")
                + f", not {len(row)}: {', '.join(row)}"
            )
    gate = element.form in ("and", "or", "nand", "nor")
    ltspice_table = element.form == "table" and dialect is Dialect.LTSPICE
    if gate and len(rows) != 2:
        raise EditError(f"a gate takes exactly two points; `{designator}` was given {len(rows)}")
    if ltspice_table and len(rows) < 2:
        raise EditError(f"`table=` takes at least two points; `{designator}` was given {len(rows)}")
    if not rows:
        raise EditError(f"`{designator}` takes at least one point")
    if element.form == "table" and dialect is Dialect.NGSPICE:
        for row in rows:
            for value in row:
                if not _reads_as_number(value):
                    raise EditError(
                        f"`{value}` is not a number: the points of an ngspice TABLE are numbers "
                        "(parameters are not allowed)"
                    )
    if freq:
        for row in rows:
            if row[0][:1] not in _DELIMITERS and not _is_plain_frequency(row[0]):
                raise EditError(
                    f"`{row[0]}` is a frequency with a unit suffix, which ngspice stops on; "
                    "write a number, with a scale factor at most"
                )


def _write_table(table: Table, rows: list[tuple[str, ...]], separator: str) -> str:
    if table.layout == "pairs":
        return " ".join(f"({separator.join(row)})" for row in rows)
    return f"({separator.join(value for row in rows for value in row)})"


def set_poly_coefficients(
    netlist: Netlist,
    designator: str,
    values: Sequence[str],
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Replace the coefficients of a POLY line, from the first to the last.

    The count may change, down to the fewest the dialect takes (two on ngspice, one on LTspice),
    and the separator already between the coefficients is kept; with the same count only the
    values are replaced. The dimension, the control nodes and sources, and ``m=`` are not edited.
    """
    element = _element(netlist, designator, scope, in_definition)
    if not isinstance(element, ControlledSource) or element.form != "poly":
        raise EditError(f"`{designator}` is not a POLY line and has no coefficients")
    texts = [str(value) for value in values]
    minimum = _MIN_COEFFICIENTS[netlist.dialect]
    if len(texts) < minimum:
        raise EditError(
            f"a POLY line takes at least {minimum} coefficient{'s' if minimum > 1 else ''} on "
            f"{netlist.dialect.display_name}; `{designator}` was given {len(texts)}"
        )
    reason = f"set_poly_coefficients {designator}"
    old = element.coefficients
    if len(texts) == len(old):
        return [Edit(value.span, new, reason, (_VALUE,)) for value, new in zip(old, texts)]
    run = Span(old[0].span.start, old[-1].span.end)
    if any(run.start <= comment.start < run.end for comment in element.trailing_comments):
        raise EditError(
            f"`{designator}` has a comment among its coefficients; change them one for one, or "
            "remove the comment first"
        )
    text = netlist.source.text
    gap = text[old[0].span.end : old[1].span.start] if len(old) > 1 else " "
    separator = gap if gap and "\n" not in gap and ";" not in gap else " "
    written = separator.join(texts)
    slots: list[SlotCheck] = []
    offset = 0
    for item in texts:
        slots.append(
            SlotCheck((Formula, *_VALUE.kinds), "a coefficient", offset, offset + len(item))
        )
        offset += len(item) + len(separator)
    return [Edit(run, written, reason, tuple(slots))]
