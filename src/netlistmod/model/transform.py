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

from netlistmod.dialects import _XYCE, Dialect
from netlistmod.errors import ParseError, UnsupportedConstruct
from netlistmod.grammar.loader import parse_tree
from netlistmod.model._rules_behavioral import BehavioralRules
from netlistmod.model._rules_lines import LinesRules
from netlistmod.model._rules_nonlinear import NonlinearRules
from netlistmod.model._rules_params import ParamRules
from netlistmod.model._rules_sources import SourcesRules
from netlistmod.model._rules_special import SpecialRules
from netlistmod.model._rules_statements import StatementsRules
from netlistmod.model._rules_structure import StructureRules
from netlistmod.model._rules_xyce import XyceRules
from netlistmod.model._tree import _span
from netlistmod.model.nodes import (
    ParseResult,
    _IndentedParseResult,
)
from netlistmod.source import SourceText

# Why ``rkm=True`` is refused on a dialect, or ``None`` where it is accepted.
_RKM_REFUSAL: dict[Dialect, str | None] = {
    Dialect.NGSPICE: None,
    Dialect.LTSPICE: "LTspice reads its embedded decimal natively",
    _XYCE: "the Xyce manuals define no RKM notation",
}
# Whether the grammar reads an indented line inside a continued statement as its own token,
# INDENTED_TRAILING (xyce, decision X-D1), which the parse records for the document layer.
_INDENTED_TRAILING: dict[Dialect, bool] = {
    Dialect.NGSPICE: False,
    Dialect.LTSPICE: False,
    _XYCE: True,
}


class _NodeBuilder(
    StructureRules,
    SourcesRules,
    NonlinearRules,
    BehavioralRules,
    SpecialRules,
    LinesRules,
    ParamRules,
    XyceRules,
    StatementsRules,
    Transformer[Token, ParseResult],
):
    """Build nodes for one parse; every grammar rule has exactly one method."""

    def __init__(self, source: SourceText, dialect: Dialect, *, rkm: bool = False) -> None:
        super().__init__()
        self._source = source
        self._dialect = dialect
        self._rkm = rkm
        self._addresistors = set()

    def __default__(self, data: Any, children: Any, meta: Any) -> NoReturn:
        raise TypeError(f"Unhandled grammar rule {data!r}")


def parse(source: SourceText, dialect: Dialect, *, rkm: bool = False) -> ParseResult:
    """Parse ``source`` with the strict grammar of ``dialect``.

    The dialect is required: there is no default and no auto-detection. An empty source, a
    missing ``.end`` or any syntax the grammar does not accept raises ``ParseError``. The two
    constructs out of scope for v1, the ngspice digital U (a U line that is not a URC line) and an
    LTspice ``.machine`` block, raise ``UnsupportedConstruct``.

    ``rkm=True`` accepts RKM values (``2k7``, ``4R7``, ``4p7``) for ngspice resistors and
    capacitors, read per IEC 60062; without it they raise ``ParseError``. The option does not
    change the grammar, and standard notation parses the same either way (decision 0004). LTspice
    reads its embedded decimal natively, so ``rkm=True`` with ``Dialect.LTSPICE`` is a
    ``ValueError`` (decision 0009), as it is on any dialect but ngspice.

    The whole source is parsed first, so a syntax error anywhere is reported before an RKM
    value, an unsupported form or ``params:`` that the transformer rejects.
    """
    if not isinstance(source, SourceText):
        raise TypeError(f"parse takes a SourceText, not {type(source).__name__}")
    refusal = _RKM_REFUSAL[dialect]
    if rkm and refusal is not None:
        raise ValueError(f"rkm=True applies only to ngspice: {refusal}")
    tree = parse_tree(source, dialect)
    try:
        result = _NodeBuilder(source, dialect, rkm=rkm).transform(tree)
    except VisitError as error:
        if isinstance(error.orig_exc, ParseError | UnsupportedConstruct):
            raise error.orig_exc from None
        raise
    if not _INDENTED_TRAILING[dialect]:
        return result
    # An xyce indented line inside a continued statement is one of its trailing comments, and its
    # own token (INDENTED_TRAILING, decision X-D1), which the document layer reports.
    indented = sorted(
        (
            _span(token)
            for token in tree.scan_values(
                lambda value: isinstance(value, Token) and value.type == "INDENTED_TRAILING"
            )
        ),
        key=lambda span: span.start,
    )
    if indented:
        return _IndentedParseResult(result.items, result.dialect, tuple(indented))
    return result
