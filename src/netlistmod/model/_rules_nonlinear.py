"""Rules for the nonlinear dependent-source forms: TABLE, POLY, FREQ and the gates (decision 0017).

The grammar recognises each form's keyword and takes the rest of the line as flat fields; this
module counts them. POLY's control nodes and sources are topology and are counted from the
dimension, so the dimension must be an integer literal (decision 0017 item 3). A ``Table`` holds
the points of TABLE, ``table=``, FREQ and the gates; the values are read as the dialect's value
slot reads them, and a form a solver reads differently from the manual is refused here.
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from typing import Any, Literal, NoReturn

from lark import Token

from netlistmod.dialects import Dialect
from netlistmod.model._rules_controlled import ControlledRules
from netlistmod.model._rules_elements import _reads_as_number
from netlistmod.model._tree import (
    _comment_spans,
    _Element,
    _Field,
    _field_token,
    _field_tokens,
    _FnList,
    _Laplace,
    _PolyPair,
    _RParen,
    _span,
    _statement_end,
)
from netlistmod.model.nodes import Node, Table, TablePoint
from netlistmod.model.values import (
    ElementReference,
    Formula,
    NumericValue,
    ParamAssignment,
    Value,
)
from netlistmod.source import Span

_DELIMITED = frozenset({"BRACE_FORMULA", "QUOTE_FORMULA"})

# The scale factors and nothing else after a frequency: a unit suffix (`1e9Hz`) is refused.
_SCALE_FACTORS = frozenset({"", "t", "g", "meg", "mil", "k", "m", "u", "n", "p", "f", "µ"})
_NAME_CHARACTERS = frozenset(string.ascii_letters + string.digits + "_.")
_DIGITS = frozenset(string.digits)
# The most coefficients a form needs to be a polynomial at all, by dialect (decision 0017 item 4).
_MIN_COEFFICIENTS = {Dialect.NGSPICE: 2, Dialect.LTSPICE: 1}


@dataclass(frozen=True, slots=True)
class _Head:
    """The keyword of a nonlinear form: ``keyword`` is its token, ``expression`` the braced or
    quoted formula after it (TABLE, FREQ), ``dimension`` the token of POLY's or a gate's ``(N)``,
    and ``end`` where the head ends."""

    keyword: Token
    expression: Token | None
    dimension: Token | None
    end: int

    @property
    def form(self) -> str:
        """The form's name as ``ControlledSource.form`` holds it."""
        kind = self.keyword.type
        if kind in ("TABLE_KW", "TABLE4_KW"):
            return "table"
        if kind == "POLY_KW":
            return "poly"
        if kind == "FREQ_KW":
            return "freq"
        return str(self.keyword).strip().lower()


@dataclass(frozen=True, slots=True)
class _FormatWord:
    """A FREQ format word as written."""

    token: Token


def _first_reference(text: str) -> int | None:
    """Where a ``V(`` or ``I(`` starts in a formula, for LTspice's ``Laplace=``: it stops on a
    voltage or current reference there ("Voltage reference not allowed here")."""
    for index, character in enumerate(text):
        if character not in "VvIi" or (index and text[index - 1] in _NAME_CHARACTERS):
            continue
        after = index + 1
        while after < len(text) and text[after] in " 	":
            after += 1
        if text[after : after + 1] == "(":
            return index
    return None


def _is_plain_frequency(text: str) -> bool:
    """Whether ``text`` is a number with at most a scale factor after it, no unit suffix."""
    i = 1 if text[:1] in ("+", "-") else 0
    start = i
    while i < len(text) and text[i] in _DIGITS:
        i += 1
    digits = i - start
    if i < len(text) and text[i] == ".":
        i += 1
        while i < len(text) and text[i] in _DIGITS:
            i += 1
            digits += 1
    if digits == 0:
        return False
    if i < len(text) and text[i] in "eE":
        j = i + 1 + (text[i + 1 : i + 2] in ("+", "-"))
        if j < len(text) and text[j] in _DIGITS:
            i = j
            while i < len(text) and text[i] in _DIGITS:
                i += 1
    return text[i:].lower() in _SCALE_FACTORS


def item_end(item: Token | _PolyPair) -> int:
    return item.span.end if isinstance(item, _PolyPair) else _span(item).end


class NonlinearRules(ControlledRules):
    """Rules for the nonlinear forms of E, F, G and H."""

    # --- grammar rules --------------------------------------------------------------------

    def table_form(self, children: list[Any]) -> _Field:
        return self._head(children)

    table4_form = table_form
    freq_form = table_form
    poly_form = table_form
    gate_form = table_form

    def table_bare(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        raise self._parse_error(
            keyword,
            "ngspice reads `TABLE` only with its expression in braces or quotes: with a bare "
            "expression it runs but reads something else (ngspice manual §5.2.3); write "
            "`TABLE {expression} = ...`",
        )

    def poly_field(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: token)

    def poly_pn(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: token)

    def poly_pair(self, children: list[Any]) -> _Field:
        inner = children[-1]
        if isinstance(inner, _Field) and isinstance(inner.node, _PolyPair):
            return _Field(inner.node, (*_comment_spans(children), *inner.comments))
        fields = [child for child in children if isinstance(child, _Field)]
        names = [field.node for field in fields if isinstance(field.node, Token)]
        opener = next(c for c in children if isinstance(c, Token) and c.type == "LPAR")
        close = fields[-1].node
        assert isinstance(close, _RParen)
        comments = tuple(span for field in fields for span in field.comments)
        pair = _PolyPair((names[0], names[1]), Span(_span(opener).start, close.span.end))
        return _Field(pair, comments)

    lap_param = ControlledRules.ctl_m

    def laplace_clause(self, children: list[Any]) -> _Laplace:
        inner = children[-1]
        if isinstance(inner, _Laplace):
            return _Laplace(
                inner.keyword,
                inner.formula,
                inner.params,
                (*_comment_spans(children), *inner.comments),
                inner.end,
            )
        keyword = next(c for c in children if isinstance(c, Token) and c.type == "LAPLACE_KW")
        formula = self._expression(children)
        params = [c for c in children if isinstance(c, _Field)]
        end, end_comments = _statement_end(children[-1])
        comments = (
            *_comment_spans(children),
            *(span for field in params for span in field.comments),
            *end_comments,
        )
        nodes = tuple(f.node for f in params if isinstance(f.node, ParamAssignment))
        return _Laplace(keyword, formula, nodes, comments, end)

    def freq_fmt(self, children: list[Any]) -> _Field:
        return self._field(children, _FormatWord)

    def _head(self, children: list[Any]) -> _Field:
        inner = children[-1]
        if isinstance(inner, _Field) and isinstance(inner.node, _Head):
            return _Field(inner.node, (*_comment_spans(children), *inner.comments))
        tokens = _field_tokens(children)
        keyword = tokens[0]
        expression = next((t for t in tokens[1:] if t.type in _DELIMITED), None)
        dimension = next((t for t in tokens[1:] if t.type == "POLY_DIM"), None)
        end = _span(tokens[-1]).end
        if isinstance(inner, _Field) and isinstance(inner.node, _RParen):
            end = inner.node.span.end
        return _Field(_Head(keyword, expression, dimension, end), _comment_spans(children))

    # --- the form's fields ----------------------------------------------------------------

    def _form_fields(self, element: _Element, children: list[Any]) -> dict[str, Any]:
        laplace = element.optional(_Laplace)
        if laplace is not None:
            formula = laplace.formula
            found = _first_reference(formula.text)
            if found is not None:
                # E and G only: B's laplace= was not probed (decision 0017 item 4).
                raise self._error_at(
                    formula.span.start + (1 if formula.delimiter else 0) + found,
                    f"`{formula.text[found]}(` in a `Laplace=` formula: LTspice stops on a "
                    'voltage or current reference there ("Voltage reference not allowed '
                    'here"); the formula takes `s` and the parameters only',
                )
            return {
                "form": "laplace",
                "expression": laplace.formula,
                "params": (*element.all(ParamAssignment), *laplace.params),
            }
        head = element.optional(_Head)
        if head is None:
            return super()._form_fields(element, children)
        if head.form == "table":
            return self._table_fields(element, head)
        if head.form == "poly":
            return self._poly_fields(element, head)
        if head.form == "freq":
            return self._freq_fields(element, head)
        return self._gate_fields(element, head)

    def _expression_of(self, head: _Head) -> Formula:
        assert head.expression is not None
        value = self._value(head.expression)
        assert isinstance(value, Formula)
        return value

    def _table_fields(self, element: _Element, head: _Head) -> dict[str, Any]:
        table = self._table(element.lists, head, width=2, formats=())
        fields: dict[str, Any] = {"form": "table", "table": table}
        if self._dialect is Dialect.NGSPICE:
            if head.expression is not None:
                fields["expression"] = self._expression_of(head)
            self._check_numbers(table)
        elif len(table.points) < 2:
            # LTspice stops with fewer than two pairs ("Pairs of numbers expected").
            raise self._error_at(
                table.span.start,
                "`table=` takes at least two pairs, one flat list of at least four values; "
                "LTspice stops on one pair",
            )
        return fields

    def _check_numbers(self, table: Table) -> None:
        """ngspice's TABLE points are numbers: ``parameters are not allowed`` (manual §5.2.3), and
        ngspice reads some parameter forms wrongly (decision 0017 item 4)."""
        for point in table.points:
            for value in point.values:
                if isinstance(value, Formula):
                    raise self._error_at(
                        value.span.start,
                        f"`{value.text}` in a TABLE point: ngspice's manual allows numbers "
                        "only, and ngspice reads some parameter forms in a point wrongly "
                        "(`{2*k}` gives another table); write the number",
                    )

    def _freq_fields(self, element: _Element, head: _Head) -> dict[str, Any]:
        words = tuple(str(word.token) for word in element.all(_FormatWord))
        table = self._table(element.lists, head, width=3, formats=words)
        for point in table.points:
            frequency = point.values[0]
            if isinstance(frequency, NumericValue) and not _is_plain_frequency(frequency.text):
                raise self._error_at(
                    frequency.span.start,
                    f"`{frequency.text}`: the manual's own FREQ example writes a unit suffix "
                    "(`1.0e+07Hz`), and ngspice stops on it; write the frequency as a number, "
                    "with a scale factor at most",
                )
        return {
            "form": "freq",
            "expression": self._expression_of(head),
            "table": table,
        }

    def _gate_fields(self, element: _Element, head: _Head) -> dict[str, Any]:
        count = self._dimension(head)
        nodes = element.all(Node)
        inputs = len(nodes) - 2
        if inputs < 4 or inputs % 2:
            raise self._error_at(
                self._first_point_start(element),
                f"`{head.keyword}` takes the input node pairs before its two points, and "
                f"the line has {inputs} names there: ngspice stops on fewer than two pairs "
                "and on an odd count",
            )
        if inputs != 2 * count:
            assert head.dimension is not None
            raise self._parse_error(
                head.dimension,
                f"`({count})` does not match the {inputs} input nodes before the points: "
                "ngspice ignores the dimension and counts the inputs, so "
                f"`{head.keyword}({count})` must have {2 * count}",
            )
        table = self._table(element.lists, head, width=2, formats=())
        self._check_gate_points(element, table)
        return {"form": head.form, "dimension": count, "table": table}

    def _first_point_start(self, element: _Element) -> int:
        return element.lists[0].start if element.lists else element.end

    def _check_gate_points(self, element: _Element, table: Table) -> None:
        text = self._source.text
        if len(table.points) != 2 or table.layout != "pairs":
            raise self._error_at(
                table.span.start,
                "a gate takes exactly two points, `(x, y) (x, y)`; ngspice stops on any other "
                "number (ngspice manual §5.2.7)",
            )
        for point in table.points:
            first, second = point.values
            if "," not in text[first.span.end : second.span.start]:
                raise self._error_at(
                    point.span.start,
                    "a gate's point is written with a comma, `(x, y)`; ngspice stops on a point "
                    "without one",
                )
        between = text[element.lists[0].end : element.lists[1].start]
        if not between or "," in between:
            raise self._error_at(
                element.lists[1].start,
                "a gate's two points are separated by a blank, `(x, y) (x, y)`; ngspice stops on "
                "points written without one",
            )

    # --- points ---------------------------------------------------------------------------

    def _table(
        self, groups: list[_FnList], head: _Head, *, width: int, formats: tuple[str, ...]
    ) -> Table:
        if head.form == "freq" and not formats:
            raise self._error_at(
                groups[0].start,
                "FREQ takes a format word (`DB`, `MAG`, `DEG`, `RAD` or `R_I`) before its "
                "points; ngspice stops without one (ngspice manual §5.2.6)",
            )
        counts = [len(group.args) for group in groups]
        points: list[TablePoint]
        layout: Literal["pairs", "flat"]
        if len(groups) == 1 and counts[0] > width:
            values = groups[0].args
            if len(values) % width:
                raise self._error_at(
                    values[-1].span.start,
                    f"a flat list holds a multiple of {width} values, one point after the other; "
                    f"this one holds {len(values)}",
                )
            points = [
                TablePoint(
                    chunk := values[index : index + width],
                    Span(chunk[0].span.start, chunk[-1].span.end),
                )
                for index in range(0, len(values), width)
            ]
            layout = "flat"
        else:
            points = []
            for group in groups:
                if len(group.args) != width:
                    written = ", ".join(value.text for value in group.args)
                    raise self._error_at(
                        group.args[0].span.start,
                        f"a point holds {width} values, `({written})` holds {len(group.args)}",
                    )
                points.append(
                    TablePoint(group.args, Span(group.args[0].span.start, group.args[-1].span.end))
                )
            layout = "pairs"
        return Table(
            tuple(points),
            layout,
            formats,
            Span(groups[0].start, groups[-1].end),
        )

    # --- POLY -----------------------------------------------------------------------------

    def _dimension(self, head: _Head) -> int:
        token = head.dimension
        assert token is not None
        text = str(token)
        if not (text.isascii() and text.isdigit() and int(text) >= 1):
            raise self._parse_error(
                token,
                f"`{text}` is not a dimension: `{head.keyword.value.strip()}(N)` takes an integer "
                "literal of at least 1, because N decides how many control nodes or sources "
                "follow and so the topology; write the number itself",
            )
        return int(text)

    def _poly_fields(self, element: _Element, head: _Head) -> dict[str, Any]:
        count = self._dimension(head)
        items = [f for f in element.fields if isinstance(f, Token | _PolyPair)]
        letter = str(element.designator)[0].upper()
        voltage_controlled = letter in "EG"
        need = 2 * count if voltage_controlled else count
        end = max([head.end, *(item_end(i) for i in items)])
        # A control pair "(n+,n-)" counts as two names (LTspice, decision 0017 item 3).
        names: list[Token] = []
        used = 0
        while used < len(items) and len(names) < need:
            item = items[used]
            used += 1
            if isinstance(item, _PolyPair):
                if len(names) + 2 > need:
                    raise self._error_at(
                        item.span.start, "a `(n+,n-)` pair would run past POLY's control nodes"
                    )
                names.extend(item.names)
            else:
                names.append(item)
        rest = items[used:]
        if len(names) < need:
            what = "control nodes" if voltage_controlled else "controlling sources"
            raise self._error_at(
                end,
                f"POLY({count}) takes {need} {what} after it, and the line has "
                f"{len(names)} of them",
            )
        for pair in rest:
            if isinstance(pair, _PolyPair):
                raise self._error_at(
                    pair.span.start,
                    "a `(n+,n-)` pair is a control pair, and the coefficients follow the "
                    "control nodes",
                )
        coefficients = [token for token in rest if isinstance(token, Token)]
        fields: dict[str, Any] = {"form": "poly", "dimension": count}
        for token in names:
            if token.type in _DELIMITED:
                kind = "node" if voltage_controlled else "source"
                raise self._parse_error(
                    token, f"`{token}` is a formula, but a POLY control {kind} is a name"
                )
        if voltage_controlled:
            fields["nodes"] = (
                *element.all(Node),
                *(Node(str(token), _span(token)) for token in names),
            )
        else:
            fields["control"] = tuple(ElementReference(str(t), _span(t)) for t in names)
        fields["coefficients"] = self._coefficients(coefficients, end)
        return fields

    def _coefficients(self, tokens: list[Token], end: int) -> tuple[Value, ...]:
        values: list[Value] = []
        for token in tokens:
            if token.type == "WORD" and not _reads_as_number(str(token)):
                raise self._parse_error(
                    token,
                    f"`{token}` is a name where a coefficient goes: a coefficient is a number "
                    "or a `{...}` expression, as a dependent source's gain is",
                )
            values.append(self._value(token))
        minimum = _MIN_COEFFICIENTS[self._dialect]
        if len(values) < minimum:
            raise self._error_at(
                end,
                f"POLY needs at least {minimum} coefficient{'s' if minimum > 1 else ''}; the line "
                f"has {len(values)}",
            )
        return tuple(values)
