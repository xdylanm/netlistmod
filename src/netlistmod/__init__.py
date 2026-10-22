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
from netlistmod.model.nodes import (
    BlankLine,
    CommentLine,
    End,
    OpaqueBlock,
    OpaqueStatement,
    ParseResult,
    Title,
    TitleDirective,
    UnknownDirective,
)
from netlistmod.model.transform import parse
from netlistmod.source import SourceText, Span

__version__ = version("netlistmod")

__all__ = [
    "Dialect",
    "BlankLine",
    "CommentLine",
    "End",
    "EditError",
    "EncodingError",
    "ParseError",
    "ParseResult",
    "OpaqueBlock",
    "OpaqueStatement",
    "SourceText",
    "Span",
    "SpiceNetlistError",
    "TopologyError",
    "TopologyViolation",
    "Title",
    "TitleDirective",
    "UnsupportedConstruct",
    "UnknownDirective",
    "__version__",
    "parse",
]
