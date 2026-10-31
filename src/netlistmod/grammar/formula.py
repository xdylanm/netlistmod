"""Find the names a formula refers to, with the strict formula grammar (``formula.lark``).

This is the best-effort identifier scan of architecture §8, done by a grammar (P13): the
tokens come from a parse of the formula text, never from string scanning. The document layer
maps each token's offsets (relative to the formula text) to source spans.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Literal

from lark import Lark, Token, Tree
from lark.exceptions import LarkError

_RESERVED = "formula-reserved.json"

FormulaTokenKind = Literal["parameter", "reserved", "function", "node", "source"]


@dataclass(frozen=True, slots=True)
class FormulaToken:
    """A name in a formula; ``start`` and ``end`` are offsets into the formula text.

    ``kind`` is ``"parameter"`` for a bare identifier that may name a parameter,
    ``"reserved"`` for a bare word of the §2.11.6 reserved list, ``"function"`` for the name of
    a call, and ``"node"`` or ``"source"`` for the argument of ``v(...)`` or ``i(...)``.
    """

    kind: FormulaTokenKind
    text: str
    start: int
    end: int


@lru_cache(maxsize=1)
def build_formula_parser() -> Lark:
    """Build or retrieve the strict LALR parser of the formula grammar."""
    return Lark.open_from_package(
        "netlistmod.grammar",
        "formula.lark",
        parser="lalr",
        lexer="contextual",
        propagate_positions=True,
        strict=True,
    )


@lru_cache(maxsize=1)
def reserved_words() -> frozenset[str]:
    """The lower-case words that are never parameter names (§2.11.5 functions, §2.11.6)."""
    resource = files("netlistmod.grammar") / _RESERVED
    parsed = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict) or not isinstance(parsed.get("words"), list):
        raise ValueError("formula-reserved.json must contain a list of words")
    return frozenset(str(word).lower() for word in parsed["words"])


def parse_formula(text: str) -> tuple[FormulaToken, ...] | None:
    """Return the names in ``text`` in source order, or ``None`` if it does not parse.

    A formula the grammar does not accept is not an error here: the scan is best effort, and
    the solver is the judge of an expression (non-goal 6).
    """
    try:
        tree = build_formula_parser().parse(text)
    except LarkError:
        return None
    tokens: list[FormulaToken] = []
    if isinstance(tree, Token):
        tokens.extend(_leaf(tree, None))
    else:
        _collect(tree, tokens)
    return tuple(sorted(tokens, key=lambda token: token.start))


def _collect(tree: Tree[Token], tokens: list[FormulaToken]) -> None:
    for child in tree.children:
        if isinstance(child, Tree):
            _collect(child, tokens)
        else:
            tokens.extend(_leaf(child, tree.data))


def _leaf(token: Token, rule: str | None) -> tuple[FormulaToken, ...]:
    """The name a token stands for in the rule that holds it, if any."""
    kind: FormulaTokenKind
    if token.type == "IDENT":
        if rule == "call":
            kind = "function"
        elif str(token).lower() in reserved_words():
            kind = "reserved"
        else:
            kind = "parameter"
    elif token.type == "NAME":
        kind = "source" if rule == "current" else "node"
    else:
        return ()
    start = int(token.start_pos or 0)
    return (FormulaToken(kind, str(token), start, start + len(token)),)
