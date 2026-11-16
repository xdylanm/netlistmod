"""Rules for xyce's statements and element lines: `.SUBCKT` defaults, the includes and `.LIB`
(X-M1 B4; decision 0027 item 7), and the R, C, L, V, I and D forms that differ from the other
dialects (X-M1 B5; decision 0027 items 5 and 6)."""

from __future__ import annotations

from typing import Any, NoReturn

from lark import Token

from netlistmod.dialects import _XYCE, Dialect, fold_name
from netlistmod.model._rules_elements import _reads_as_number
from netlistmod.model._rules_statements import StatementsRules
from netlistmod.model._tree import (
    _common,
    _Element,
    _Field,
    _field_token,
    _Item,
    _span,
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
# The parameter that holds each letter's value ([xyce-ref] Tables 2-37, 2-39 and 2-42).
_VALUE_KEYWORDS: dict[type, str] = {Resistor: "r", Capacitor: "c", Inductor: "l"}
# The long value keywords of ngspice, which Xyce stops on ("Unrecognized parameter").
_LONG_KEYWORDS = {"resistance": "R", "capacitance": "C", "inductance": "L"}
# What a line of each letter needs when it has no value (decision 0027 item 5, as amended).
_VALUE_FORMS: dict[type, str] = {
    Resistor: "a value, positional or `R=`, or a model with both `L=` and `W=`",
    Capacitor: "a value, positional or `C=`, a charge `Q=`, or `L=`",
    Inductor: "a value, positional or `L=`",
}


class XyceRules(StatementsRules):
    """Rules for xyce's statements that the other dialects spell differently."""

    def subckt_param(self, children: list[Any]) -> _Field:
        return self.param(children)

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

    def xy_tc_param(self, children: list[Any]) -> _Field:
        # `TC=a,b` is a list of two; `TC=a` alone is an ordinary value.
        if any(isinstance(c, Token) and c.type == "CSEP" for c in children):
            return self.tc_param(children)
        return self.param(children)

    def d_flag(self, children: list[Any]) -> _Field:
        return self.flag(children)

    def x_name_node(self, children: list[Any]) -> _Field:
        return self.x_name(children)

    def late_model(self, children: list[Any]) -> NoReturn:
        name = _field_token(children)
        if _reads_as_number(str(name)):
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
        """An xyce R, C or L: the model if any, then the value, positional or as a keyword."""
        params: list[ParamAssignment] = []
        keyword: ParamAssignment | None = None
        charge: ParamAssignment | None = None
        names: set[str] = set()
        for param in element.all(ParamAssignment):
            name = fold_name(param.name, self._dialect)
            if name in _LONG_KEYWORDS:
                raise self._error_at(
                    param.name_span.start,
                    f"`{param.name}=` is not a Xyce parameter, and Xyce stops on it; write the "
                    f"value positionally or as `{_LONG_KEYWORDS[name]}=`",
                )
            if name == _VALUE_KEYWORDS[kind] and keyword is None:
                keyword = param
            elif kind is Capacitor and name == "q" and charge is None:
                charge = param
            else:
                params.append(param)
            names.add(name)
        positional = next(iter(element.values()), None)
        if positional is not None and keyword is not None:
            raise self._error_at(
                keyword.name_span.start,
                f"the value is given twice, positionally and as `{keyword.name}=`; Xyce "
                "silently uses one of them, so write only one",
            )
        value: Value | None = positional
        value_keyword: str | None = None
        if keyword is not None:
            assert isinstance(keyword.value, NumericValue | Formula)
            value = keyword.value
            value_keyword = keyword.name
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
                **_common(element, span, params=tuple(params)),
                value=value,
                value_keyword=value_keyword,
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
        model and both `L=` and `W=` (Xyce takes RSH x L / W from the model), and a C with `L=`
        (decision 0027 item 5, as amended)."""
        if kind is Resistor and model is not None and {"l", "w"} <= names:
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
