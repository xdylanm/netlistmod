"""Rules for the transmission lines T, O, U, Y and P (decision 0019)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NoReturn

from lark import Token

from netlistmod.dialects import Dialect, fold_name, is_ground_name
from netlistmod.model._rules_elements import ElementsRules, _reads_as_number
from netlistmod.model._tree import (
    _common,
    _Element,
    _Field,
    _field_token,
    _Item,
    _Name,
    _span,
)
from netlistmod.model.nodes import (
    CoupledLine,
    LosslessLine,
    LossyLine,
    Node,
    RcLine,
    TxlLine,
)
from netlistmod.model.values import (
    ModelReference,
    ParamAssignment,
    ValueList,
)
from netlistmod.source import Span

# P holds one to eight coupled lines (ngspice manual §6.4.2; ngspice 47 crashes on nine).
_MOST_CONDUCTORS = 8
# What the IC= of an ngspice T holds: V1, I1, V2 and I2 (§6.1).
_IC_VALUES = 4
_IMPEDANCE = frozenset({"z0", "zo"})


@dataclass(frozen=True, slots=True)
class _UWord:
    """A name before the first ``name=value`` of an ngspice U line."""

    token: Token


@dataclass(frozen=True, slots=True)
class _UOther:
    """A field after the parameters of an ngspice U line."""

    token: Token


class LinesRules(ElementsRules):
    """Rules for the transmission-line letters."""

    def t_param(self, children: list[Any]) -> _Field:
        token = children[-1]
        if isinstance(token, Token) and token.type == "LINE_BARE":
            # LTspice reads a bare name as a parameter reference (review R2, decision 0019).
            raise self._parse_error(
                token,
                f"`{token}`: LTspice reads a bare name in a value as a parameter reference; "
                f"write `{{{token}}}`. Only `.param` takes a bare expression",
            )
        return self.param(children)

    line_len = t_param

    u_param = t_param

    def u_word(self, children: list[Any]) -> _Field:
        return self._field(children, _UWord)

    def u_other(self, children: list[Any]) -> _Field:
        return self._field(children, _UOther)

    def t_unlisted(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        if self._dialect is Dialect.LTSPICE:
            why = (
                "LTspice runs it, but the reference lists only `Zo=` (or `Z0=`) and `Td=` for T; "
                "write the delay as `Td=`"
            )
        else:
            why = "ngspice runs it, but the ngspice manual §6.1 does not list it for T"
        raise self._parse_error(keyword, f"`{keyword}=`: {why}")

    def line_extra(self, children: list[Any]) -> NoReturn:
        token = _field_token(children)
        raise self._parse_error(
            token,
            f"`{token}` after the model: an O line takes four nodes and its LTRA model, and "
            "nothing after it",
        )

    def lossless_line(self, children: list[Any]) -> _Item:
        element = _Element(children)
        params = element.all(ParamAssignment)
        end = self._fields_end(element)
        found: dict[str, list[ParamAssignment]] = {}
        for param in params:
            name = self._fold(param.name)
            found.setdefault("z0" if name in _IMPEDANCE else name, []).append(param)
        impedance = found.get("z0", [])
        if not impedance:
            raise self._error_at(end, "`Z0=` (or `Zo=`) must be given: the line's impedance")
        if len(impedance) > 1:
            first, second = impedance[:2]
            raise self._error_at(
                second.name_span.start,
                f"`{second.name}=` repeats the impedance `{first.name}=`: `Z0=` and `Zo=` are one "
                "parameter, so the line would have two impedances",
            )
        delay, frequency, length = (found.get(key, []) for key in ("td", "f", "nl"))
        if delay and frequency:
            later = max(delay[0], frequency[0], key=lambda param: param.span.start)
            raise self._error_at(
                later.name_span.start,
                f"`{later.name}=`: the line gives its length as `TD=` and as `F=`; write one of "
                "the two (the solvers use `TD=` and ignore the other)",
            )
        if length and not frequency:
            raise self._error_at(
                length[0].name_span.start,
                f"`{length[0].name}=` without `F=`: the normalised length is a length at the "
                "frequency `F=`",
            )
        if not delay and not frequency:
            dialect_form = "`Td=`" if self._dialect is Dialect.LTSPICE else "`TD=`, or `F=`"
            raise self._error_at(
                end,
                f"the line's length must be given, as {dialect_form} (the solvers would use a "
                "default delay)",
            )
        for param in found.get("ic", []):
            assert isinstance(param.value, ValueList)
            if len(param.value.values) != _IC_VALUES:
                raise self._error_at(
                    param.name_span.start,
                    f"`{param.name}=` holds {len(param.value.values)} values; it takes four, "
                    "comma-separated: V1, I1, V2 and I2",
                )
        return _Item(element.end, lambda span: LosslessLine(**_common(element, span)))

    def lossy_line(self, children: list[Any]) -> _Item:
        element = _Element(children)
        model = self._line_model(element.all(ModelReference)[0])
        return _Item(element.end, lambda span: LossyLine(**_common(element, span), model=model))

    def rc_line(self, children: list[Any]) -> _Item:
        element = _Element(children)
        words = element.all(_UWord)
        if words:
            nodes, model = self._urc_shape(element, words)
        else:
            nodes = element.all(Node)
            model = self._line_model(element.all(ModelReference)[0])
        params = element.all(ParamAssignment)
        for param in params:
            if self._fold(param.name) not in ("l", "n"):
                raise self._error_at(
                    param.name_span.start,
                    f"`{param.name}=`: a URC line takes `l=` and `n=` only",
                )
        if not any(self._fold(param.name) == "l" for param in params):
            outcome = (
                "LTspice stops without it"
                if self._dialect is Dialect.LTSPICE
                else "ngspice would use a near-zero length"
            )
            raise self._error_at(
                self._fields_end(element),
                f"`l=` must be given: the line's length ({outcome})",
            )
        return _Item(
            element.end,
            lambda span: RcLine(**_common(element, span, nodes=nodes), model=model),
        )

    def txl_line(self, children: list[Any]) -> _Item:
        element = _Element(children)
        nodes = element.all(Node)
        self._check_references(nodes, (nodes[1], nodes[3]), "Y")
        model = self._line_model(element.all(ModelReference)[0])
        return _Item(element.end, lambda span: TxlLine(**_common(element, span), model=model))

    def coupled_line(self, children: list[Any]) -> _Item:
        element = _Element(children)
        names = [name.token for name in element.all(_Name)]
        model = self._line_model(ModelReference(str(names[-1]), _span(names[-1])))
        nodes = tuple(Node(str(token), _span(token)) for token in names[:-1])
        count = len(nodes)
        if count % 2 or not 4 <= count <= 2 * _MOST_CONDUCTORS + 2:
            raise self._error_at(
                self._fields_end(element),
                f"a P line has {count} nodes before its model `{model.model_name}`; it takes "
                "2X+2 for X coupled lines (one to eight): each port's X nodes, then its "
                "reference node",
            )
        half = count // 2
        self._check_references(nodes, (nodes[half - 1], nodes[-1]), "P")
        return _Item(
            element.end,
            lambda span: CoupledLine(**_common(element, span, nodes=nodes), model=model),
        )

    def _urc_shape(
        self, element: _Element, words: tuple[_UWord, ...]
    ) -> tuple[tuple[Node, ...], ModelReference]:
        """Classify an ngspice U line (decision 0019): three nodes and a model is a URC line, and
        any other shape is the digital U of M17."""
        tokens = [word.token for word in words]
        shaped = not any("(" in str(token) or ")" in str(token) for token in tokens)
        if shaped and len(tokens) == 5 and _reads_as_number(str(tokens[4])):
            raise self._parse_error(
                tokens[4],
                f"`{tokens[4]}` after the model is a positional length, which ngspice ignores; "
                f"write `l={tokens[4]}`",
            )
        if shaped and len(tokens) == 5 and str(tokens[4]).lower() == "off":
            raise self._parse_error(tokens[4], "`off`: a URC line takes no flag")
        if not shaped or len(tokens) != 4:
            raise self._unsupported(element.designator, "ngspice digital U device")
        other = element.optional(_UOther)
        if other is not None:
            raise self._parse_error(
                other.token,
                f"`{other.token}` after the parameters: a URC line takes three nodes, its model, "
                "then `l=` and `n=`",
            )
        nodes = tuple(Node(str(token), _span(token)) for token in tokens[:3])
        return nodes, self._line_model(ModelReference(str(tokens[3]), _span(tokens[3])))

    def _line_model(self, model: ModelReference) -> ModelReference:
        if _reads_as_number(model.model_name):
            raise self._error_at(
                model.span.start,
                f"`{model.model_name}` is in the model's place, and a model name cannot be a "
                "number",
            )
        return model

    def _check_references(
        self, nodes: tuple[Node, ...], references: tuple[Node, ...], letter: str
    ) -> None:
        """A Y or P line's reference nodes must be ground: ngspice ignores them (decision 0019)."""
        for node in references:
            if not is_ground_name(node.name, self._dialect):
                raise self._error_at(
                    node.span.start,
                    f"`{node.name}` is a reference node of the {letter} line, which ngspice "
                    "ignores (the line is computed against ground); write `0`",
                )

    def _fold(self, name: str) -> str:
        return fold_name(name, self._dialect)

    def _fields_end(self, element: _Element) -> int:
        """Where the last field of a line ends (before its comments and line end)."""
        end = _span(element.designator).end
        for node in element.fields:
            span = getattr(node, "span", None)
            if isinstance(span, Span):
                end = max(end, span.end)
            token = getattr(node, "token", None)
            if isinstance(token, Token):
                end = max(end, _span(token).end)
        return end
