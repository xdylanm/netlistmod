"""Name comparison and net identity, per dialect (``docs/grammars/<dialect>/names.md``).

ngspice: designators, model, subcircuit, parameter and node names compare case-insensitively by
ASCII lower-casing. LTspice: they compare by Unicode case folding after NFC normalisation, so
canonically equivalent spellings are the same name (decision 0009). In both, ``0`` and ``gnd``
(any case) are the one ground net, ``"0"``, and ``00`` is a different net. Xyce folds ASCII case;
``0`` is its only ground unless ``.PREPROCESS REPLACEGROUND TRUE`` makes ``GND``, ``GND!`` and
``GROUND`` aliases of it across the netlist (``replace_ground``; decision 0027 item 3). These
functions compare names; they never classify syntax (P13).
"""

from __future__ import annotations

from typing import Final

from netlistmod.dialects import _XYCE, Dialect, fold_name, is_ground_name

GROUND: Final = "0"
"""The canonical name of the ground net."""

_LTSPICE_BLOCK_PREFIX: Final = "x§"
# The folded prefix that makes a node global by its name alone: LTspice's `$G_` (names.md N9) and
# Xyce's `$G` (decision X-D3; [xyce-ref] §2.3.1.1 p182). ngspice has none.
_GLOBAL_PREFIXES: Final[dict[Dialect, str | None]] = {
    Dialect.NGSPICE: None,
    Dialect.LTSPICE: "$g_",
    _XYCE: "$g",
}
# The folded names `.PREPROCESS REPLACEGROUND TRUE` makes aliases of `0` ([xyce-ref] §2.1.28
# p125); `GROUND!` is not one (xm1-tasks 5.1 point 5). Only xyce has the statement.
_REPLACED_GROUNDS: Final[dict[Dialect, frozenset[str]]] = {
    _XYCE: frozenset({"gnd", "gnd!", "ground"}),
}


def fold(name: str, dialect: Dialect) -> str:
    """Return ``name`` in the form the dialect compares names in."""
    return fold_name(name, dialect)


def is_ground(name: str, dialect: Dialect, *, replace_ground: bool = False) -> bool:
    """Whether a node name is the ground net (``0`` or ``gnd`` in any case, not ``00``; on xyce
    ``0``, and ``GND``, ``GND!`` or ``GROUND`` when ``replace_ground``)."""
    if is_ground_name(name, dialect):
        return True
    return replace_ground and fold(name, dialect) in _REPLACED_GROUNDS[dialect]


def net_name(name: str, dialect: Dialect, *, replace_ground: bool = False) -> str:
    """The canonical net name of a node: ``"0"`` for ground, otherwise the folded name."""
    if is_ground(name, dialect, replace_ground=replace_ground):
        return GROUND
    return fold(name, dialect)


def instance_name(designator: str, dialect: Dialect) -> str:
    """The folded name an LTspice node path uses for an ``X`` line: ``X§U1`` is ``u1``."""
    return fold(designator, dialect).removeprefix(_LTSPICE_BLOCK_PREFIX)


def is_automatic_global(name: str, dialect: Dialect) -> bool:
    """Whether a node is global by its name alone: LTspice's ``$G_*`` and Xyce's ``$G*`` nodes,
    in any case."""
    prefix = _GLOBAL_PREFIXES[dialect]
    return prefix is not None and fold(name, dialect).startswith(prefix)
