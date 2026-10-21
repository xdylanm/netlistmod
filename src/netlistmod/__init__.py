"""Source-preserving SPICE netlist editing."""

from importlib.metadata import version

from netlistmod.dialects import Dialect
from netlistmod.errors import (
    EditError,
    EncodingError,
    ParseError,
    SpiceNetlistError,
    TopologyError,
    TopologyViolation,
    UnsupportedConstruct,
)
from netlistmod.source import SourceText, Span

__version__ = version("netlistmod")

__all__ = [
    "Dialect",
    "EditError",
    "EncodingError",
    "ParseError",
    "SourceText",
    "Span",
    "SpiceNetlistError",
    "TopologyError",
    "TopologyViolation",
    "UnsupportedConstruct",
    "__version__",
]
