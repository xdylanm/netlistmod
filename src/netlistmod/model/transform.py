"""Convert the strict grammar's parse into typed nodes with source spans.

Syntax is defined by the Lark grammar (architecture P13). The transformer only maps each grammar
rule to a node: one method per rule, no regular expressions and no re-scanning of source lines.
Raw statement text is a slice of the source by span. The rules live in mixins by family
(``_rules_*.py``), and their shared parts in ``_tree.py``; this module assembles and runs them.

The builder transforms the positioned tree after the whole source has parsed, so a syntax error
anywhere is reported before a form this module rejects. An item's end is the end of its last
token; every top-level rule ends with one.

Element fields are rules that start with their separator (a "gap"). A field method returns a
:class:`_Field` holding the field's node and the end-of-line comments of its gap; each element
method collects its slots by node type (architecture §6.3 rule 11). Forms the grammar
recognises only to reject them (RKM without the option, stimulus functions, ``q=``,
``params:``, bare ``.param`` expressions, reserved parameter names, a port named ``0``, the
statements not allowed in a subcircuit and, in LTspice, a bare name for a value, the nonlinear
inductor forms and ``.machine``) raise here, at the position of their token (P13 (c)).

Typed dot-commands (decision 0005) use the same field rules, with the keyword in the place of
the designator. A subcircuit definition is an item whose body items tile the text between its
header and its ``.ends`` line.
"""

from __future__ import annotations

from typing import Any, NoReturn

from lark import Token, Transformer
from lark.exceptions import VisitError

from netlistmod.dialects import Dialect
from netlistmod.errors import ParseError, UnsupportedConstruct
from netlistmod.grammar.loader import parse_tree
from netlistmod.model._rules_controlled import ControlledRules
from netlistmod.model._rules_sources import SourcesRules
from netlistmod.model._rules_statements import StatementsRules
from netlistmod.model._rules_structure import StructureRules
from netlistmod.model.nodes import (
    ParseResult,
)
from netlistmod.source import SourceText


class _NodeBuilder(
    StructureRules, SourcesRules, ControlledRules, StatementsRules, Transformer[Token, ParseResult]
):
    """Build nodes for one parse; every grammar rule has exactly one method."""

    def __init__(self, source: SourceText, dialect: Dialect, *, rkm: bool = False) -> None:
        super().__init__()
        self._source = source
        self._dialect = dialect
        self._rkm = rkm

    def __default__(self, data: Any, children: Any, meta: Any) -> NoReturn:
        raise TypeError(f"Unhandled grammar rule {data!r}")


def parse(source: SourceText, dialect: Dialect, *, rkm: bool = False) -> ParseResult:
    """Parse ``source`` with the strict grammar of ``dialect``.

    The dialect is required: there is no default and no auto-detection. An empty source, a
    missing ``.end`` or any syntax the grammar does not accept raises ``ParseError``. An element
    letter that is not supported yet, a source stimulus function, ``DISTOF`` and the charge form
    ``q=`` of a capacitor raise ``UnsupportedConstruct``.

    ``rkm=True`` accepts RKM values (``2k7``, ``4R7``, ``4p7``) for ngspice resistors and
    capacitors, read per IEC 60062; without it they raise ``ParseError``. The option does not
    change the grammar, and standard notation parses the same either way (decision 0004). LTspice
    reads its embedded decimal natively, so ``rkm=True`` with ``Dialect.LTSPICE`` is a
    ``ValueError`` (decision 0009).

    The whole source is parsed first, so a syntax error anywhere is reported before an RKM
    value, an unsupported form or ``params:`` that the transformer rejects.
    """
    if not isinstance(source, SourceText):
        raise TypeError(f"parse takes a SourceText, not {type(source).__name__}")
    if rkm and dialect is Dialect.LTSPICE:
        raise ValueError(
            "rkm=True applies only to ngspice: LTspice reads its embedded decimal natively"
        )
    tree = parse_tree(source, dialect)
    try:
        return _NodeBuilder(source, dialect, rkm=rkm).transform(tree)
    except VisitError as error:
        if isinstance(error.orig_exc, ParseError | UnsupportedConstruct):
            raise error.orig_exc from None
        raise
