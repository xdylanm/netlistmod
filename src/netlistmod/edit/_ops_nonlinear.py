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
from netlistmod.model.nodes import ControlledSource, Table
from netlistmod.model.values import Formula
from netlistmod.source import Span

_TABLE = SlotCheck((Table,), "a table")
_NEWLINE = "\n"
# The fewest coefficients a polynomial takes, by dialect: ngspice stops with fewer than two,
# LTspice runs one (the constant).
_MIN_COEFFICIENTS = {Dialect.NGSPICE: 2, Dialect.LTSPICE: 1}


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
    flat list), reusing as written the text between the first two values, between the first two
    points and around the first point's values, and the number of points may change. When the
    count is the same, only the values are replaced. A count change is refused over a comment
    among the points, and over several lines unless each point is on a line of its own. The
    other refusals are made before verification: a point of the wrong width, fewer points than
    the form takes (two for a gate or ``table=``, one for ngspice TABLE and FREQ), and a value
    that is not a number on ngspice TABLE.
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
    if any(
        table.span.start <= comment.start < table.span.end for comment in element.trailing_comments
    ):
        raise EditError(
            f"`{designator}` has a comment among its points; change them one for one, or "
            "remove the comment first"
        )
    text = netlist.source.text
    return [Edit(table.span, _write_table(text, table, rows, designator), reason, (_TABLE,))]


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


def _write_table(text: str, table: Table, rows: list[tuple[str, ...]], designator: str) -> str:
    """The points rewritten as the line wrote them: the text between its first two values, between
    its first two points, and around the first point's values are reused as written."""
    first = table.points[0].values
    start = table.span.start
    opener = text[start : first[0].span.start]  # "(" and any blanks before the first value
    closer_at = text.index(")", first[-1].span.end) + 1
    closer = text[first[-1].span.end : closer_at]
    inner = text[first[0].span.end : first[1].span.start]
    if table.layout == "flat":
        if "\n" in text[table.span.start : table.span.end]:
            raise _several_lines(designator)
        body = inner.join(value for row in rows for value in row)
        last = table.points[-1].values[-1].span.end
        return f"{opener}{body}{text[last : table.span.end]}"
    if _NEWLINE not in text[start : table.span.end]:
        gap = " "
        if len(table.points) > 1:
            second = table.points[1].values[0].span.start
            gap = text[closer_at : text.rindex("(", 0, second)]
        return gap.join(f"{opener}{inner.join(row)}{closer}" for row in rows)
    # The line continues: each point must stand on a line of its own, and each new point is
    # written on a continuation line like the first (the text between the first two points).
    groups = [
        (
            text.rindex("(", 0, point.values[0].span.start),
            text.index(")", point.values[-1].span.end) + 1,
        )
        for point in table.points
    ]
    gaps = [text[groups[i][1] : groups[i + 1][0]] for i in range(len(groups) - 1)]
    if (
        not gaps
        or not all(_NEWLINE in gap for gap in gaps)
        or any(_NEWLINE in text[a:b] for a, b in groups)
    ):
        raise _several_lines(designator)
    return gaps[0].join(f"{opener}{inner.join(row)}{closer}" for row in rows)


def _several_lines(designator: str) -> EditError:
    return EditError(
        f"the points of `{designator}` are not each on a line of their own, and the line "
        "continues; change them one for one (the same number of points), or write the table "
        "on one line first"
    )


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
    if "\n" in text[run.start : run.end]:
        raise EditError(
            f"the coefficients of `{designator}` continue on another line; change them one for "
            "one (the same number of coefficients), or write them on one line first"
        )
    gap = text[old[0].span.end : old[1].span.start] if len(old) > 1 else " "
    separator = gap or " "
    written = separator.join(texts)
    slots: list[SlotCheck] = []
    offset = 0
    for item in texts:
        slots.append(
            SlotCheck((Formula, *_VALUE.kinds), "a coefficient", offset, offset + len(item))
        )
        offset += len(item) + len(separator)
    return [Edit(run, written, reason, tuple(slots))]
