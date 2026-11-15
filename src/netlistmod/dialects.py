"""SPICE dialect names supported by netlistmod, and the name rules both the model and the document
layers use (``docs/grammars/<dialect>/names.md``)."""

from collections.abc import Callable
from enum import StrEnum
from string import ascii_lowercase, ascii_uppercase
from typing import Final
from unicodedata import normalize

_ASCII_LOWER: Final = str.maketrans(ascii_uppercase, ascii_lowercase)
GROUND_NAMES: Final = frozenset({"0", "gnd"})
"""The folded names of the ground net on ngspice and LTspice (names.md N2)."""


class Dialect(StrEnum):
    """A supported SPICE dialect; callers must select one explicitly.

    A ``StrEnum``: ``str(Dialect.NGSPICE)`` and ``f"{Dialect.NGSPICE}"`` give ``"ngspice"``.
    """

    NGSPICE = "ngspice"
    LTSPICE = "ltspice"

    @property
    def display_name(self) -> str:
        """Return the conventional display name for this dialect."""
        return _DISPLAY_NAMES[self]

    @classmethod
    def from_name(cls, name: str) -> "Dialect":
        """Parse a dialect value or enum name, without regard to case."""
        normalized = name.strip().casefold()
        for dialect in cls:
            if normalized in {dialect.value.casefold(), dialect.name.casefold()}:
                return dialect
        valid_names = ", ".join(dialect.value for dialect in cls)
        raise ValueError(f"Unknown dialect {name!r}; valid names are: {valid_names}")


def _hidden_member(value: str, name: str) -> Dialect:
    """A ``Dialect`` instance that is not a member: iteration, ``__members__``, ``Dialect(value)``,
    ``Dialect[name]`` and ``from_name`` do not know it, and ``isinstance`` accepts it.

    The xyce dialect stays hidden this way until its milestones are done (decision 0026). It
    sets the attributes ``Enum`` gives a member, which are undocumented internals, so
    ``tests/architecture/test_hidden_dialects.py`` checks it on every supported Python. It cannot
    be pickled, since unpickling looks the value up.
    """
    member = str.__new__(Dialect, value)
    # `_sort_order_` is the members' count, one past the last member's order. A public member
    # added before X-M8 must keep the two distinct: define it in the class body, not later.
    member.__dict__.update(_name_=name, _value_=value, _sort_order_=len(Dialect.__members__))
    return member


_XYCE: Final[Dialect] = _hidden_member("xyce", "XYCE")
"""The xyce dialect while it is hidden (decision 0026). Never bound in a public ``__all__``."""

_DISPLAY_NAMES: Final[dict[Dialect, str]] = {
    Dialect.NGSPICE: "ngspice",
    Dialect.LTSPICE: "LTspice",
    _XYCE: "Xyce",
}


def _ascii_fold(name: str) -> str:
    return name.translate(_ASCII_LOWER)


def _unicode_fold(name: str) -> str:
    return normalize("NFC", name).casefold()


# ASCII lower case on ngspice, Unicode case folding after NFC normalisation on LTspice (decision
# 0009). Xyce ignores case ([xyce-ug] §4.1.3 p41); ASCII lower case is provisional until its
# names.md is written in X-M1.
_FOLDS: Final[dict[Dialect, Callable[[str], str]]] = {
    Dialect.NGSPICE: _ascii_fold,
    Dialect.LTSPICE: _unicode_fold,
    _XYCE: _ascii_fold,
}
# The folded names of the ground net: `0` and `gnd` on ngspice and LTspice; only `0` on Xyce,
# where `GND` is a ground only after `.PREPROCESS REPLACEGROUND` ([xyce-ref] §2.1.28 p125).
_GROUNDS: Final[dict[Dialect, frozenset[str]]] = {
    Dialect.NGSPICE: GROUND_NAMES,
    Dialect.LTSPICE: GROUND_NAMES,
    _XYCE: frozenset({"0"}),
}


def fold_name(name: str, dialect: Dialect) -> str:
    """``name`` in the form the dialect compares names in: ASCII lower case on ngspice, Unicode
    case folding after NFC normalisation on LTspice (decision 0009)."""
    return _FOLDS[dialect](name)


def is_ground_name(name: str, dialect: Dialect) -> bool:
    """Whether a node name is the ground net: ``0`` or ``gnd`` in any case on ngspice and
    LTspice, never ``00``."""
    return fold_name(name, dialect) in _GROUNDS[dialect]
