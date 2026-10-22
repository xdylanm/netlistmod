"""Public exceptions raised by netlistmod."""


class SpiceNetlistError(Exception):
    """Base class for errors raised while working with SPICE netlists."""


class ParseError(SpiceNetlistError):
    """A syntax error with its 1-based source position and rendered excerpt."""

    def __init__(
        self,
        line: int,
        column: int,
        excerpt: str,
        expected: tuple[str, ...] = (),
        reason: str = "",
    ) -> None:
        """Create a parse error at ``line`` and ``column``.

        ``reason`` is an optional one-line explanation (for example an unterminated block).
        """
        self.line = line
        self.column = column
        self.excerpt = excerpt
        self.expected = expected
        self.reason = reason
        explanation = f" {reason}" if reason else ""
        expectation = f"\nExpected: {', '.join(expected)}" if expected else ""
        super().__init__(
            f"Parse error at line {line}, column {column}:{explanation}\n{excerpt}{expectation}"
        )


class UnsupportedConstruct(SpiceNetlistError):
    """A construct known to the dialect but not supported by netlistmod."""

    def __init__(
        self,
        construct: str,
        line: int,
        column: int,
        excerpt: str,
    ) -> None:
        """Create an error for a recognized construct not implemented yet."""
        self.construct = construct
        self.line = line
        self.column = column
        self.excerpt = excerpt
        super().__init__(
            f"Unsupported construct {construct!r} at line {line}, column {column}:\n{excerpt}"
        )


class EditError(SpiceNetlistError):
    """An edit cannot be applied without violating the document contract."""


class TopologyError(SpiceNetlistError):
    """An operation is not permitted because it could alter circuit topology."""


class TopologyViolation(SpiceNetlistError):
    """A write-time check found that an edit changed circuit topology."""


class EncodingError(SpiceNetlistError):
    """Source bytes could not be decoded or text could not be encoded."""
