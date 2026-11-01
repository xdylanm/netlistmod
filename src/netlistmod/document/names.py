"""Name comparison and net identity, per dialect (``docs/grammars/<dialect>/names.md``).

ngspice: designators, model, subcircuit, parameter and node names compare case-insensitively by
ASCII lower-casing. LTspice: they compare by Unicode case folding after NFC normalisation, so
canonically equivalent spellings are the same name (decision 0009). In both, ``0`` and ``gnd``
(any case) are the one ground net, ``"0"``, and ``00`` is a different net. These functions compare
names; they never classify syntax (P13).
"""

from __future__ import annotations

from string import ascii_lowercase, ascii_uppercase
from typing import Final
from unicodedata import normalize

from netlistmod.dialects import Dialect

GROUND: Final = "0"
"""The canonical name of the ground net."""

_ASCII_LOWER: Final = str.maketrans(ascii_uppercase, ascii_lowercase)
_GROUND_NAMES: Final = frozenset({"0", "gnd"})
_LTSPICE_GLOBAL_PREFIX: Final = "$g_"


def fold(name: str, dialect: Dialect) -> str:
    """Return ``name`` in the form the dialect compares names in."""
    if dialect is Dialect.LTSPICE:
        return normalize("NFC", name).casefold()
    return name.translate(_ASCII_LOWER)


def is_ground(name: str, dialect: Dialect) -> bool:
    """Whether a node name is the ground net (``0`` or ``gnd`` in any case, not ``00``)."""
    return fold(name, dialect) in _GROUND_NAMES


def net_name(name: str, dialect: Dialect) -> str:
    """The canonical net name of a node: ``"0"`` for ground, otherwise the folded name."""
    return GROUND if is_ground(name, dialect) else fold(name, dialect)


def is_automatic_global(name: str, dialect: Dialect) -> bool:
    """Whether a node is global by its name alone: LTspice's ``$G_*`` nodes."""
    return dialect is Dialect.LTSPICE and fold(name, dialect).startswith(_LTSPICE_GLOBAL_PREFIX)
