"""The base of the transformer's rule mixins (architecture P13 (b))."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lark import Token

from netlistmod.dialects import Dialect
from netlistmod.errors import ParseError, UnsupportedConstruct
from netlistmod.model._tree import (
    _BARE_FORMULA,
    _EMBEDDED,
    _FORMULA_DELIMITERS,
    _MODEL_BARE,
    _RKM_SOLVER_MISMATCH,
    _RKM_TERMINALS,
    _TEXT_VALUES,
    _comment_spans,
    _Field,
    _field_token,
    _span,
)
from netlistmod.model.values import (
    Formula,
    Identifier,
    NumericValue,
    Value,
)
from netlistmod.source import SourceText, Span


class _Rules:
    """The parse a rule mixin works on, and the helpers every family uses."""

    _source: SourceText
    _dialect: Dialect
    _rkm: bool

    def _field(self, children: list[Any], build: Callable[[Token], object]) -> _Field:
        if len(children) == 2 and isinstance(children[1], Token):
            # The common case: one separator, then the field token.
            return _Field(build(children[1]), ())
        comments = _comment_spans(children)
        inner = children[-1]
        if isinstance(inner, _Field):
            return _Field(inner.node, (*comments, *inner.comments))
        return _Field(build(_field_token(children)), comments)

    def _value(self, token: Token) -> Value:
        if token.type in _FORMULA_DELIMITERS:
            span = _span(token)
            # The grammar guarantees exactly one delimiter character at each end of the token.
            text = self._source.text[span.start + 1 : span.end - 1]
            return Formula(text, _FORMULA_DELIMITERS[token.type], span)
        if token.type == _BARE_FORMULA:
            return Formula(str(token), "", _span(token))
        if token.type in (_EMBEDDED, "FIELD_EMBEDDED"):
            return NumericValue(str(token), _span(token), "rkm")
        if token.type in _RKM_TERMINALS:
            return self._rkm_value(token)
        return NumericValue(str(token), _span(token))

    def _param_value(self, token: Token) -> Value | Identifier:
        """A parameter value; an LTspice bare word stays a name, never a formula (review R8)."""
        if token.type in _TEXT_VALUES:
            return Identifier(str(token), _span(token))
        if token.type == _MODEL_BARE:
            raise self._parse_error(
                token,
                f"`{token}`: LTspice reads a bare word in this `.model` parameter as a parameter "
                f"reference; write `{{{token}}}`. Only `mfg` and `type` take a bare word",
            )
        return self._value(token)

    def _rkm_value(self, token: Token) -> NumericValue:
        if token.type == "RKM_R_MILLI":
            raise self._parse_error(
                token,
                f"`{token}`: lowercase `m` is not an RKM code for a resistor; write `L` for "
                "milli (for example `4L7`) or use standard notation",
            )
        if not self._rkm:
            raise self._parse_error(
                token,
                f"`{token}` is RKM notation, which is accepted only with parse(..., rkm=True); "
                "ngspice reads it only in LT compatibility mode",
            )
        return NumericValue(str(token), _span(token), "rkm", token.type in _RKM_SOLVER_MISMATCH)

    def _parse_error(self, token: Token, reason: str) -> ParseError:
        return self._error_at(_span(token).start, reason)

    def _error_at(self, offset: int, reason: str) -> ParseError:
        source = self._source
        line, column = source.position(offset)
        return ParseError(line, column, source.excerpt(offset), (), reason)

    def _unsupported(self, token: Token, construct: str) -> UnsupportedConstruct:
        source = self._source
        offset = _span(token).start
        line, column = source.position(offset)
        return UnsupportedConstruct(construct, line, column, source.excerpt(offset))

    def _statement(self, children: list[Any]) -> tuple[str, str, tuple[Span, ...]]:
        name, rest = children[0], children[1]
        raw = self._source.text[name.start_pos : rest.text_end or name.end_pos]
        return str(name), raw, rest.comments
