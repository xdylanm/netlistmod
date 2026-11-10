"""Name comparison and net identity, per dialect (``docs/grammars/<dialect>/names.md``).

ngspice: designators, model, subcircuit, parameter and node names compare case-insensitively by
ASCII lower-casing. LTspice: they compare by Unicode case folding after NFC normalisation, so
canonically equivalent spellings are the same name (decision 0009). In both, ``0`` and ``gnd``
(any case) are the one ground net, ``"0"``, and ``00`` is a different net. These functions compare
names; they never classify syntax (P13).
"""

from __future__ import annotations

from typing import Final

from netlistmod.dialects import Dialect, fold_name, is_ground_name

GROUND: Final = "0"
"""The canonical name of the ground net."""

_LTSPICE_GLOBAL_PREFIX: Final = "$g_"
_LTSPICE_BLOCK_PREFIX: Final = "x§"


def fold(name: str, dialect: Dialect) -> str:
    """Return ``name`` in the form the dialect compares names in."""
    return fold_name(name, dialect)


def is_ground(name: str, dialect: Dialect) -> bool:
    """Whether a node name is the ground net (``0`` or ``gnd`` in any case, not ``00``)."""
    return is_ground_name(name, dialect)


def net_name(name: str, dialect: Dialect) -> str:
    """The canonical net name of a node: ``"0"`` for ground, otherwise the folded name."""
    return GROUND if is_ground(name, dialect) else fold(name, dialect)


def instance_name(designator: str, dialect: Dialect) -> str:
    """The folded name an LTspice node path uses for an ``X`` line: ``X§U1`` is ``u1``."""
    return fold(designator, dialect).removeprefix(_LTSPICE_BLOCK_PREFIX)


def is_automatic_global(name: str, dialect: Dialect) -> bool:
    """Whether a node is global by its name alone: LTspice's ``$G_*`` nodes."""
    return dialect is Dialect.LTSPICE and fold(name, dialect).startswith(_LTSPICE_GLOBAL_PREFIX)
