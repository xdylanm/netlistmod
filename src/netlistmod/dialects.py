"""SPICE dialect names supported by netlistmod."""

from enum import Enum


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
