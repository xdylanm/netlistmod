"""Name comparison and net identity for ngspice (``docs/grammars/ngspice/names.md``).

Designators, model, subcircuit, parameter and node names compare case-insensitively by ASCII
lower-casing, as ngspice does. ``0`` and ``gnd`` (any case) are the one ground net, ``"0"``;
``00`` is a different net (§2.1.3.5). These functions compare names; they never classify
syntax (P13).
"""

from __future__ import annotations

from string import ascii_lowercase, ascii_uppercase
from typing import Final

GROUND: Final = "0"
"""The canonical name of the ground net."""

_ASCII_LOWER: Final = str.maketrans(ascii_uppercase, ascii_lowercase)
_GROUND_NAMES: Final = frozenset({"0", "gnd"})


def fold(name: str) -> str:
    """Return ``name`` with ASCII letters lower-cased; other characters are unchanged."""
    return name.translate(_ASCII_LOWER)


def is_ground(name: str) -> bool:
    """Whether a node name is the ground net (``0`` or ``gnd`` in any case, not ``00``)."""
    return fold(name) in _GROUND_NAMES


def net_name(name: str) -> str:
    """The canonical net name of a node: ``"0"`` for ground, otherwise the folded name."""
    return GROUND if is_ground(name) else fold(name)
