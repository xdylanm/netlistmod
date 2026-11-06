"""Shared parts of the transformer: field records, token helpers and the element's fields."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

from lark import Token

from netlistmod.model.nodes import (
    Node,
    TopLevelItem,
)
from netlistmod.model.values import (
    Flag,
    Formula,
    Identifier,
    ModelReference,
    NumericValue,
    ParamAssignment,
    SubcktReference,
    Value,
)
from netlistmod.source import Span

_T = TypeVar("_T")

_FORMULA_DELIMITERS: dict[str, Literal["{", "'", '"']] = {
    "BRACE_FORMULA": "{",
    "QUOTE_FORMULA": "'",
    "STRING_VALUE": '"',
}
_RKM_TERMINALS = frozenset({"RKM_R", "RKM_R_MEGA", "RKM_R_MILLI", "RKM_C", "RKM_C_FARAD"})
_EMBEDDED = "EMBEDDED"  # the LTspice embedded decimal, always LTspice's own reading
_BARE_FORMULA = "BARE_FORMULA"
# Which function takes each fn_param (ngspice manual §4.1.4, §4.1.9; LTspice reference, WAV File).
_FN_PARAM_OWNERS = {"r": "pwl", "td": "pwl", "m": "external", "chan": "wavefile"}
# Text kept as a value and never read: the value of mfg, pn or type, the only parameters whose
# grammar offers WORD; a file's path; a trigger expression.
_TEXT_VALUES = frozenset({"WORD", "FILE_PATH", "TRIGGER_EXPR", "DOTTED_VALUE"})
_MODEL_BARE = "MODEL_BARE"
_STEP_VARIATIONS = frozenset({"DEC_KW", "OCT_KW", "LIN_KW"})
# RKM terminals that ngspice reads differently from IEC 60062 (decision 0004).
_RKM_SOLVER_MISMATCH = frozenset({"RKM_R_MEGA", "RKM_C_FARAD"})
# Field tokens: the token of a field rule that is neither a separator nor a comment.
_GAP_TERMINALS = frozenset({"SEP", "CSEP", "BS_CONT", "TRAILING_COMMENT", "EQ"})
# Names that §2.11.1 reserves and a .param assignment may not define.
_RESERVED_PARAMS = frozenset({"TIME_KW", "TEMPER_KW", "HERTZ_KW"})
_BARE_EXPRESSION = (
    "bare expression in `.param`: write the expression in braces (`{...}`) or single quotes"
)


@dataclass(frozen=True, slots=True)
class _Item:
    """A top-level item waiting for its span.

    Whitespace between items is ignored by the grammar and has no token, so an item's span
    runs from the end of the previous item to ``end``. That keeps the spans contiguous.
    """

    end: int
    build: Callable[[Span], TopLevelItem]


@dataclass(frozen=True, slots=True)
class _Rest:
    """Where a statement's text ends, and its end-of-line comments in source order."""

    text_end: int | None
    comments: tuple[Span, ...]


@dataclass(frozen=True, slots=True)
class _Field:
    """One element field: its node, and the comments of the gap in front of it."""

    node: object
    comments: tuple[Span, ...]


@dataclass(frozen=True, slots=True)
class _KeywordValue:
    """A value written with its keyword (``r=1k``)."""

    keyword: str
    value: Value


@dataclass(frozen=True, slots=True)
class _Dc:
    value: Value
    keyword: bool


@dataclass(frozen=True, slots=True)
class _DcKeyword:
    pass


@dataclass(frozen=True, slots=True)
class _AcMagnitude:
    value: Value
    start: int


@dataclass(frozen=True, slots=True)
class _XRest:
    """The part of an ``X`` line after its first node."""

    nodes: tuple[Node, ...]
    subckt: SubcktReference
    params: tuple[ParamAssignment, ...]
    comments: tuple[Span, ...]
    end: int


@dataclass(frozen=True, slots=True)
class _ListKeyword:
    """The ``list`` keyword of an LTspice ``.ac``, ``.dc`` or ``.step``."""

    span: Span


@dataclass(frozen=True, slots=True)
class _FileArgument:
    """``file=name`` of an LTspice ``.ac``, ``.dc`` or ``.step``."""

    keyword: Token
    name: Identifier


@dataclass(frozen=True, slots=True)
class _ParamsMarker:
    """An LTspice ``params:``, which adds nothing to the node."""


@dataclass(frozen=True, slots=True)
class _StepItem:
    """The swept quantity of ``.step param name`` or ``.step temp``."""

    kind: Literal["param", "temp"]
    token: Token


@dataclass(frozen=True, slots=True)
class _StepModelRef:
    """``2N2222(VAF)``: one token holding the model name and the parameter."""

    name: str
    span: Span
    model: ModelReference


@dataclass(frozen=True, slots=True)
class _StepSweep:
    """The sweep of a ``.step``: a range, a list, or a file."""

    values: tuple[Value, ...]
    listed: bool
    file: Identifier | None


@dataclass(frozen=True, slots=True)
class _FnList:
    """The list of a source function: its values, where it ends, and its comments."""

    args: tuple[Value, ...]
    end: int
    comments: tuple[Span, ...]


@dataclass(frozen=True, slots=True)
class _Forever:
    """``FOREVER`` in a PWL repeat."""

    span: Span


@dataclass(frozen=True, slots=True)
class _SpecParam:
    """A parameter of the source function before it, not of the line."""

    param: ParamAssignment


@dataclass(frozen=True, slots=True)
class _DistortionHead:
    """``DISTOF1`` or ``DISTOF2``; the plain values after it are its magnitude and phase."""

    token: Token


@dataclass(frozen=True, slots=True)
class _Name:
    """A name on a transistor line, a node or the model: the last one is the model."""

    token: Token


@dataclass(frozen=True, slots=True)
class _Eol:
    end: int
    comments: tuple[Span, ...]


@dataclass(frozen=True, slots=True)
class _Tail:
    """A last field whose rule also holds the end of the statement."""

    field: _Field
    end: int
    comments: tuple[Span, ...]


@dataclass(frozen=True, slots=True)
class _Bare:
    """A bare ``.param`` expression, recognised only to be rejected; ``span`` covers its text."""

    span: Span


@dataclass(frozen=True, slots=True)
class _ModelParams:
    """The parenthesized parameter list of a ``.model`` line and its parenthesis tokens."""

    params: tuple[ParamAssignment, ...]
    open_span: Span
    close_span: Span
    flags: tuple[Flag, ...] = ()


@dataclass(frozen=True, slots=True)
class _RParen:
    span: Span


@dataclass(frozen=True, slots=True)
class _MeasBody:
    text: str
    span: Span


@dataclass(frozen=True, slots=True)
class _Header:
    """A ``.subckt`` line: its fields and comments, and where it ends."""

    element: _Element


@dataclass(frozen=True, slots=True)
class _Ends:
    name: Token | None
    comments: tuple[Span, ...]
    end: int


def _span(token: Token) -> Span:
    if token.start_pos is None or token.end_pos is None:
        raise ValueError(f"Lark did not propagate positions for {token.type}")
    return Span(token.start_pos, token.end_pos)


def _end(children: list[Any]) -> int:
    """The end of the last token: every top-level rule ends with one."""
    for child in reversed(children):
        if isinstance(child, Token) and child.end_pos is not None:
            return child.end_pos
    raise ValueError("Lark did not propagate statement positions")


def _statement_end(terminator: Token | _Eol) -> tuple[int, tuple[Span, ...]]:
    """Where a statement ends and the comments of its end, from its NL token or ``eol``."""
    if isinstance(terminator, _Eol):
        return terminator.end, terminator.comments
    return _end([terminator]), ()


def _comment_spans(children: list[Any]) -> tuple[Span, ...]:
    return tuple(
        _span(child)
        for child in children
        if isinstance(child, Token) and child.type == "TRAILING_COMMENT"
    )


def _field_token(children: list[Any]) -> Token:
    return next(c for c in children if isinstance(c, Token) and c.type not in _GAP_TERMINALS)


class _Element:
    """The fields of one element line, in source order, with all of their comments."""

    def __init__(self, children: list[Any]) -> None:
        self.designator: Token = children[0]
        self.fields: list[object] = []
        comments: list[Span] = []
        end = 0
        for child in children[1:]:
            if isinstance(child, _Field):
                self.fields.append(child.node)
                comments.extend(child.comments)
            elif isinstance(child, _Eol):
                comments.extend(child.comments)
                end = child.end
            elif isinstance(child, _XRest):
                self.fields.append(child)
                comments.extend(child.comments)
                end = child.end
            elif isinstance(child, _Tail):
                self.fields.append(child.field.node)
                comments.extend((*child.field.comments, *child.comments))
                end = child.end
        self.comments = tuple(comments)
        self.end = end or _end(children)

    def all(self, kind: type[_T]) -> tuple[_T, ...]:
        return tuple(node for node in self.fields if isinstance(node, kind))

    def optional(self, kind: type[_T]) -> _T | None:
        return next((node for node in self.fields if isinstance(node, kind)), None)

    def values(self) -> tuple[Value, ...]:
        """The positional values (a keyword value, a DC value or a parameter is wrapped)."""
        return tuple(node for node in self.fields if isinstance(node, NumericValue | Formula))


def _common(
    element: _Element,
    span: Span,
    *,
    nodes: tuple[Node, ...] | None = None,
    params: tuple[ParamAssignment, ...] | None = None,
) -> dict[str, Any]:
    return {
        "designator": str(element.designator),
        "designator_span": _span(element.designator),
        "nodes": element.all(Node) if nodes is None else nodes,
        "params": element.all(ParamAssignment) if params is None else params,
        "span": span,
        "trailing_comments": element.comments,
    }


def _dot(element: _Element, span: Span) -> dict[str, Any]:
    """The fields of a typed dot-command; its keyword stands where an element's designator is."""
    return {
        "keyword": str(element.designator),
        "keyword_span": _span(element.designator),
        "span": span,
        "trailing_comments": element.comments,
    }


def _field_tokens(children: list[Any]) -> list[Token]:
    """The tokens of a field rule that are neither separators, comments nor ``=``."""
    return [c for c in children if isinstance(c, Token) and c.type not in _GAP_TERMINALS]
