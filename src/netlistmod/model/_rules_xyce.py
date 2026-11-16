"""Rules for xyce's statements and element lines: `.SUBCKT` defaults, the includes and `.LIB`
(X-M1 B4; decision 0027 item 7), and the R, C, L, V, I and D forms that differ from the other
dialects (X-M1 B5; decision 0027 items 5 and 6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NoReturn

from lark import Token

from netlistmod.dialects import _XYCE, Dialect, fold_name
from netlistmod.model._numbers import reads_as_number
from netlistmod.model._rules_statements import StatementsRules
from netlistmod.model._tree import (
    _common,
    _Element,
    _Field,
    _field_token,
    _Item,
    _span,
    _XRest,
)
from netlistmod.model.nodes import (
    Capacitor,
    Inductor,
    LibCall,
    OpaqueBlock,
    OpaqueStatement,
    Resistor,
)
from netlistmod.model.values import (
    Flag,
    Formula,
    Identifier,
    ModelReference,
    NumericValue,
    ParamAssignment,
    Value,
)

# Whether R, C and L take xyce's forms (decision 0027 item 5): the model right after the nodes,
# then the value, which may also be written `R=`, `C=` or `L=` (and the charge `Q=` on C). The
# other dialects read their own forms in ElementsRules.
_MODEL_FIRST: dict[Dialect, bool] = {
    Dialect.NGSPICE: False,
    Dialect.LTSPICE: False,
    _XYCE: True,
}
# Whether an instance parameter written twice on an element line is refused (xyce: Xyce 7.10 runs
# `R1 a 0 1k L=1u L=2u` and `X1 a s PARAMS: r=1 r=2`, silently using one of the values; R1
# review). The other dialects read such a line as they always have.
_INSTANCE_REPEAT_REFUSED: dict[Dialect, bool] = {
    Dialect.NGSPICE: False,
    Dialect.LTSPICE: False,
    _XYCE: True,
}
# The long value keywords of ngspice, which Xyce stops on ("Unrecognized parameter").
_LONG_KEYWORDS = {"resistance": "R", "capacitance": "C", "inductance": "L"}
# Each letter's closed instance-parameter list, as the grammar's R_PARAM_KW, C_PARAM_KW,
# L_PARAM_KW and D_PARAM_KW hold it (xm1-tasks 5.1 point 29), for the message that refuses a name
# outside it: the device, the tables, and the names.
_PARAM_LISTS: dict[str, tuple[str, str, str]] = {
    "r": (
        "resistor",
        "Xyce reference manual §2.3.7 p203–205, Tables 2-42 and 2-44",
        "a, density, dtemp, heatcapacity, l, m, outputintvars, r, resistivity, tc (or tc1 and "
        "tc2), tce, temp, thermal_a, thermal_heatcapacity, thermal_l and w",
    ),
    "c": (
        "capacitor",
        "Xyce reference manual §2.3.4 p187, Table 2-37",
        "age, c, d, dtemp, ic, l, m, q, tc (or tc1 and tc2), temp and w",
    ),
    "l": (
        "inductor",
        "Xyce reference manual §2.3.5 p193, Table 2-39",
        "dtemp, ic, l, m, tc (or tc1 and tc2) and temp",
    ),
    "d": (
        "diode",
        "Xyce reference manual §2.3.8 p208–213, Tables 2-46, 2-48 and 2-51",
        "ab, area, dtemp, ic, lg, ls, m, mult, off, perim, pj and temp",
    ),
}
# What a line of each letter needs when it has no value (decision 0027 item 5, as amended).
_VALUE_FORMS: dict[type, str] = {
    Resistor: "a value, positional or `R=`, or a model with `L=`",
    Capacitor: "a value, positional or `C=`, a charge `Q=`, or `L=`",
    Inductor: "a value, positional or `L=`",
}


@dataclass(frozen=True, slots=True)
class _ValueKeyword:
    """An xyce R, C or L value written as its parameter (`R=`, `C=`, `L=`), or a C's charge
    `Q=` (``charge``): the whole assignment, which keeps the keyword's span for the edits."""

    assignment: ParamAssignment
    charge: bool


class XyceRules(StatementsRules):
    """Rules for xyce's statements that the other dialects spell differently."""

    def subckt_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    def reserved_default(self, children: list[Any]) -> NoReturn:
        name = _field_token(children)
        raise self._parse_error(
            name,
            f"`{name}` is a reserved word (time, freq, hertz, vt, temp, temper, gmin, pi and exp) "
            "and cannot be a subcircuit parameter (Xyce reference manual §2.1.26 p121); Xyce "
            "stops on time, vt, temp and gmin, and ignores the others",
        )

    def path_field(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: Identifier(str(token), _span(token)))

    def _opaque_raw(self, element: _Element) -> str:
        """The text from the keyword to the end of the last field, across `+` lines."""
        last = element.all(Identifier)[-1]
        return self._source.text[_span(element.designator).start : last.span.end]

    def include_line(self, children: list[Any]) -> _Item:
        element = _Element(children)
        raw = self._opaque_raw(element)
        comments = element.comments
        return _Item(element.end, lambda span: OpaqueStatement("include", raw, span, comments))

    def lib_call(self, children: list[Any]) -> _Item:
        element = _Element(children)
        raw = self._opaque_raw(element)
        comments = element.comments
        entries = element.all(Identifier)[1:]
        return _Item(element.end, lambda span: LibCall("lib", raw, span, comments, entries))

    def lib_open(self, children: list[Any]) -> Identifier:
        field: _Field = children[1]
        assert isinstance(field.node, Identifier)
        return field.node

    def lib_open_end(self, children: list[Any]) -> None:
        return None

    def lib_text(self, children: list[Any]) -> None:
        return None

    def lib_close(self, children: list[Any]) -> tuple[Token, Identifier | None, int]:
        element = _Element(children)
        return element.designator, element.optional(Identifier), element.end

    def lib_section(self, children: list[Any]) -> _Item:
        name: Identifier = children[0]
        keyword, closing, end = children[-1]
        if closing is None:
            raise self._parse_error(
                keyword,
                f"`{keyword}` without a name: it must name the library entry it closes, "
                f"`{keyword} {name.name}` (Xyce reference manual §2.1.16.2 p51); Xyce stops on it",
            )
        if fold_name(closing.name, self._dialect) != fold_name(name.name, self._dialect):
            raise self._error_at(
                closing.span.start,
                f"`{keyword} {closing.name}` closes the library entry `{name.name}`: the names "
                "must match (Xyce reference manual §2.1.16.2 p51); Xyce stops on it",
            )
        return _Item(end, lambda span: OpaqueBlock("lib", span))

    # Element lines (X-M1 B5).

    def inst_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    def r_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    def r_keyword(self, children: list[Any]) -> _Field:
        return self._value_keyword(children, charge=False)

    c_keyword = r_keyword

    l_keyword = r_keyword

    def q_charge(self, children: list[Any]) -> _Field:
        return self._value_keyword(children, charge=True)

    def _value_keyword(self, children: list[Any], *, charge: bool) -> _Field:
        field = self.param(children)
        if isinstance(field.node, _ValueKeyword):
            return field  # the gap before a field on a `+` line, around the inner field
        assert isinstance(field.node, ParamAssignment)
        return _Field(_ValueKeyword(field.node, charge=charge), field.comments)

    def c_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    def l_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    def d_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    def r_unlisted(self, children: list[Any]) -> NoReturn:
        self._unlisted("r", children)

    def c_unlisted(self, children: list[Any]) -> NoReturn:
        self._unlisted("c", children)

    def l_unlisted(self, children: list[Any]) -> NoReturn:
        self._unlisted("l", children)

    def d_unlisted(self, children: list[Any]) -> NoReturn:
        self._unlisted("d", children)

    def _unlisted(self, letter: str, children: list[Any]) -> NoReturn:
        """Refuse a parameter name outside the letter's closed list (xm1-tasks 5.1 point 29)."""
        name = _field_token(children)
        folded = fold_name(str(name), self._dialect)
        if folded in _LONG_KEYWORDS:
            raise self._parse_error(
                name,
                f"`{name}=` is not a Xyce parameter, and Xyce stops on it; write the value "
                f"positionally or as `{_LONG_KEYWORDS[folded]}=`",
            )
        device, tables, names = _PARAM_LISTS[letter]
        raise self._parse_error(
            name,
            f"`{name}=` is not a parameter of a Xyce {device}, and Xyce stops on it "
            f'("Unrecognized parameter"). The reference guide lists {names} ({tables})',
        )

    def xy_tc_param(self, children: list[Any]) -> _Field:
        # `TC=a,b` is a list of two; `TC=a` alone is an ordinary value.
        if any(isinstance(c, Token) and c.type == "CSEP" for c in children):
            return self.tc_param(children)
        return self.param(children)

    def d_flag(self, children: list[Any]) -> _Field:
        return self.flag(children)

    def x_name_node(self, children: list[Any]) -> _Field:
        return self.x_name(children)

    def x_last(self, children: list[Any]) -> _XRest:
        rest = super().x_last(children)
        if _INSTANCE_REPEAT_REFUSED[self._dialect]:
            self._refuse_repeats(rest.params)
        return rest

    def diode(self, children: list[Any]) -> _Item:
        if _INSTANCE_REPEAT_REFUSED[self._dialect]:
            self._refuse_repeats(_Element(children).all(ParamAssignment))
        return super().diode(children)

    def _refuse_repeats(self, params: tuple[ParamAssignment, ...]) -> None:
        """Refuse an instance parameter written twice: Xyce 7.10 runs the line and silently uses
        one of the values (the last on R, the first on X; R1 review)."""
        seen: set[str] = set()
        for param in params:
            folded = fold_name(param.name, self._dialect)
            if folded in seen:
                raise self._error_at(
                    param.name_span.start,
                    f"`{param.name}=` is written twice on this line; "
                    f"{self._dialect.display_name} silently uses one of the values, so write it "
                    "once",
                )
            seen.add(folded)

    def late_model(self, children: list[Any]) -> NoReturn:
        name = _field_token(children)
        if reads_as_number(str(name)):
            raise self._parse_error(name, f"`{name}` is a second value; the line takes one")
        raise self._parse_error(
            name,
            f"`{name}` after the value: Xyce writes the model before the value, right after "
            f"the nodes (`... {name} <value>`; Xyce reference manual §2.3.7 p201)",
        )

    def ac_bare(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        raise self._parse_error(
            keyword,
            f"`{keyword}` without a magnitude: write `{keyword} 0`; the library reads an AC part "
            "only with its magnitude, which the Xyce manual makes optional",
        )

    def src_function(self, children: list[Any]) -> NoReturn:
        name = _field_token(children)
        raise self._unsupported(
            name,
            f"transient source function `{name}`, not yet supported on "
            f"{self._dialect.display_name} (planned for X-M3)",
        )

    def resistor(self, children: list[Any]) -> _Item:
        if not _MODEL_FIRST[self._dialect]:
            return super().resistor(children)
        return self._model_first(Resistor, _Element(children))

    def capacitor(self, children: list[Any]) -> _Item:
        if not _MODEL_FIRST[self._dialect]:
            return super().capacitor(children)
        return self._model_first(Capacitor, _Element(children))

    def inductor(self, children: list[Any]) -> _Item:
        if not _MODEL_FIRST[self._dialect]:
            return super().inductor(children)
        return self._model_first(Inductor, _Element(children))

    def _model_first(self, kind: type[Resistor | Capacitor | Inductor], element: _Element) -> _Item:
        """An xyce R, C or L: the model if any, then the value, positional or as its keyword."""
        params = element.all(ParamAssignment)
        written = element.all(_ValueKeyword)
        keywords = tuple(field.assignment for field in written if not field.charge)
        charges = tuple(field.assignment for field in written if field.charge)
        # Xyce 7.10 runs a parameter or a keyword written twice and silently uses one of them.
        self._refuse_repeats((*params, *keywords, *charges))
        keyword = keywords[0] if keywords else None
        charge = charges[0] if charges else None
        names = {fold_name(param.name, self._dialect) for param in params}
        positional = next(iter(element.values()), None)
        if positional is not None and keyword is not None:
            raise self._error_at(
                keyword.name_span.start,
                f"the value is given twice, positionally and as `{keyword.name}=`; Xyce "
                "silently uses one of them, so write only one",
            )
        value: Value | None = positional
        if keyword is not None:
            assert isinstance(keyword.value, NumericValue | Formula)
            value = keyword.value
        model = element.optional(ModelReference)
        if model is not None:
            model = self._model_not_number(model, "the name after the nodes")
        formula: Formula | None = None
        if charge is not None:
            if value is not None:
                raise self._error_at(
                    charge.name_span.start,
                    f"a capacitance and a charge `{charge.name}=` on one line; Xyce silently uses "
                    "one of them, so write only one",
                )
            if not isinstance(charge.value, Formula):
                raise self._error_at(
                    charge.value.span.start,
                    f"`{charge.name}=` takes the charge as an expression, in braces or quotes "
                    f"(`{charge.name}={{...}}`)",
                )
            formula = charge.value
        if value is None and formula is None:
            self._require_value(kind, model, names, element)
        extra: dict[str, Any] = {"charge": formula} if kind is Capacitor else {}
        return _Item(
            element.end,
            lambda span: kind(
                **_common(element, span, params=params),
                value=value,
                value_keyword=keyword.name if keyword is not None else None,
                value_keyword_span=keyword.name_span if keyword is not None else None,
                model=model,
                flags=element.all(Flag),
                **extra,
            ),
        )

    def _require_value(
        self,
        kind: type[Resistor | Capacitor | Inductor],
        model: ModelReference | None,
        names: set[str],
        element: _Element,
    ) -> None:
        """Refuse an R, C or L line without its value, except the geometry forms: an R with a
        model and `L=` (Xyce takes RSH x L / W from the model, and the model's DEFW for a missing
        `W=`; [xyce-ref] §2.3.7 p203), and a C with `L=` (decision 0027 item 5, as amended and
        corrected at R1)."""
        if kind is Resistor and model is not None and "l" in names:
            return
        if kind is Capacitor and "l" in names:
            return
        letter = str(element.designator)[0].upper()
        hint = ""
        if model is not None:
            hint = (
                f"; `{model.model_name}` is read as the model, since a name right after the "
                f"nodes is one: write `{{{model.model_name}}}` for a parameter"
            )
        raise self._error_at(
            _span(element.designator).start,
            f"this {letter} line has no value: it needs {_VALUE_FORMS[kind]}{hint}",
        )
