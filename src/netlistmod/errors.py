"""Public exceptions raised by netlistmod."""


class SpiceNetlistError(Exception):
    """Base class for errors raised while working with SPICE netlists."""


class ParseError(SpiceNetlistError):
    """A syntax error with its 1-based source position and rendered excerpt."""

    def __init__(self, line: int, column: int, excerpt: str) -> None:
        """Create a parse error at ``line`` and ``column``."""
        self.line = line
        self.column = column
        self.excerpt = excerpt
        super().__init__(f"Parse error at line {line}, column {column}:\n{excerpt}")


class UnsupportedConstruct(SpiceNetlistError):
    """A construct known to the dialect but not supported by netlistmod."""


class EditError(SpiceNetlistError):
    """An edit cannot be applied without violating the document contract."""


class TopologyError(SpiceNetlistError):
    """An operation is not permitted because it could alter circuit topology."""


class TopologyViolation(SpiceNetlistError):
    """A write-time check found that an edit changed circuit topology."""


class EncodingError(SpiceNetlistError):
    """Source bytes could not be decoded or text could not be encoded."""
