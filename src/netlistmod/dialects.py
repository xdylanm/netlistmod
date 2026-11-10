"""SPICE dialect names supported by netlistmod, and the name rules both the model and the document
layers use (``docs/grammars/<dialect>/names.md``)."""

from enum import Enum
from string import ascii_lowercase, ascii_uppercase
from typing import Final
from unicodedata import normalize

_ASCII_LOWER: Final = str.maketrans(ascii_uppercase, ascii_lowercase)
GROUND_NAMES: Final = frozenset({"0", "gnd"})
"""The folded names of the ground net (names.md N2)."""


class Dialect(str, Enum):
    """A supported SPICE dialect; callers must select one explicitly."""

    NGSPICE = "ngspice"
    LTSPICE = "ltspice"

    @property
    def display_name(self) -> str:
        """Return the conventional display name for this dialect."""
        return "LTspice" if self is Dialect.LTSPICE else "ngspice"

    @classmethod
    def from_name(cls, name: str) -> "Dialect":
        """Parse a dialect value or enum name, without regard to case."""
        normalized = name.strip().casefold()
        for dialect in cls:
            if normalized in {dialect.value.casefold(), dialect.name.casefold()}:
                return dialect
        valid_names = ", ".join(dialect.value for dialect in cls)
        raise ValueError(f"Unknown dialect {name!r}; valid names are: {valid_names}")


def fold_name(name: str, dialect: Dialect) -> str:
    """``name`` in the form the dialect compares names in: ASCII lower case on ngspice, Unicode
    case folding after NFC normalisation on LTspice (decision 0009)."""
    if dialect is Dialect.LTSPICE:
        return normalize("NFC", name).casefold()
    return name.translate(_ASCII_LOWER)


def is_ground_name(name: str, dialect: Dialect) -> bool:
    """Whether a node name is the ground net (``0`` or ``gnd`` in any case, not ``00``)."""
    return fold_name(name, dialect) in GROUND_NAMES
