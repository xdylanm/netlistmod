"""Build strict dialect parsers and parse source-preserving netlists."""

from __future__ import annotations

import json
from collections.abc import Iterable
from functools import lru_cache
from importlib.resources import files
from typing import Final

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedCharacters, UnexpectedToken

from netlistmod.dialects import Dialect
from netlistmod.errors import ParseError, UnsupportedConstruct
from netlistmod.source import SourceText

GRAMMARS: Final[dict[Dialect, tuple[str, ...]]] = {
    Dialect.NGSPICE: ("core.lark", "ngspice.lark"),
}
_PENDING_DIALECTS: Final[frozenset[Dialect]] = frozenset({Dialect.LTSPICE})
_DEVICE_MATRIX = "ngspice-devices.json"

# Opener terminal, or the rule whose first token is the opener -> (block name, closing keyword).
# Used only to explain an unterminated block.
_BLOCKS: Final[dict[Dialect, dict[str, tuple[str, str]]]] = {
    Dialect.NGSPICE: {
        "CONTROL_KW": (".control", ".endc"),
        "IF_KW": (".if", ".endif"),
        "SUBCKT_KW": (".subckt", ".ends"),
        "subckt_header": (".subckt", ".ends"),
    },
}
# Opening parenthesis terminals; an unclosed one is reported at the opener when the line ends.
_OPEN_PARENS: Final[frozenset[str]] = frozenset(
    {"LPAR", "V_OPEN", "VOLTAGE_OPEN", "CURRENT_OPEN", "CURRENT_VARIANT_OPEN"}
)
_LINE_ENDS: Final[frozenset[str]] = frozenset({"$END", "NL", "LINE_END"})
_END_OF_INPUT = "$END"
_TERMINAL_NAMES: Final[dict[str, str]] = {
    "$END": "end of input",
    "LINE_END": "end of line",
    "NL": "end of line",
    "BS_CONT": "`\\\\` continuation onto a line of statement text",
    "END_KW": "`.end`",
    "ENDC_KW": "`.endc`",
    "ENDIF_KW": "`.endif`",
    "CONTROL_KW": "`.control`",
    "IF_KW": "`.if`",
    "INCLUDE_KW": "`.include`",
    "LIB_KW": "`.lib`",
    "TITLE_KW": "`.title`",
    "TITLE_TEXT": "title text",
    "TITLE_ARG": "title text",
    "COMMENT_LINE": "comment line (`*`)",
    "DOT_NAME": "dot-command",
    "BLOCK_DOT_NAME": "dot-command",
    "BLOCK_TEXT": "text",
    "TEXT": "text",
    "QUOTED": "quoted text",
    "TRAILING_COMMENT": "trailing comment (`;`, `$` or `//`)",
    "SEP": "field separator",
    "CSEP": "`,` field separator",
    "EQ": "`=`",
    "WORD": "name",
    "NUMBER": "number",
    "RKM_R": "RKM value",
    "RKM_R_MEGA": "RKM value",
    "RKM_R_MILLI": "RKM value",
    "RKM_C": "RKM value",
    "RKM_C_FARAD": "RKM value",
    "BRACE_FORMULA": "`{expression}`",
    "QUOTE_FORMULA": "`'expression'`",
    "STRING_VALUE": '`"string"`',
    "OFF_KW": "`off`",
    "R_NAME": "resistor (`R`)",
    "C_NAME": "capacitor (`C`)",
    "L_NAME": "inductor (`L`)",
    "K_NAME": "coupling (`K`)",
    "V_NAME": "voltage source (`V`)",
    "I_NAME": "current source (`I`)",
    "D_NAME": "diode (`D`)",
    "X_NAME": "subcircuit call (`X`)",
    "L_REF": "inductor name (`L...`)",
    "R_KW": "`r=`",
    "RESISTANCE_KW": "`resistance=`",
    "C_KW": "`c=`",
    "CAPACITANCE_KW": "`capacitance=`",
    "L_KW": "`l=`",
    "INDUCTANCE_KW": "`inductance=`",
    "Q_KW": "`q=`",
    "DC_KW": "`DC`",
    "AC_KW": "`AC`",
    "STIMULUS_KW": "source function",
    "PARAMS_KW": "`params:`",
    "PARAM_KW": "`.param`",
    "PARAM_NAME": "parameter name",
    "TIME_KW": "`time`",
    "TEMPER_KW": "`temper`",
    "HERTZ_KW": "`hertz`",
    "BARE_EXPR": "bare expression",
    "MODEL_KW": "`.model`",
    "LPAR": "`(`",
    "RPAR": "`)`",
    "SUBCKT_KW": "`.subckt`",
    "ENDS_KW": "`.ends`",
    "ZERO_PORT": "`0`",
    "TRAN_KW": "`.tran`",
    "UIC_KW": "`uic`",
    "DOT_AC_KW": "`.ac`",
    "DEC_KW": "`dec`",
    "OCT_KW": "`oct`",
    "LIN_KW": "`lin`",
    "DOT_DC_KW": "`.dc`",
    "OP_KW": "`.op`",
    "OPTIONS_KW": "`.options`",
    "OPTION_KW": "`.option`",
    "TEMP_KW": "`.temp`",
    "IC_KW": "`.ic`",
    "NODESET_KW": "`.nodeset`",
    "V_OPEN": "`v(`",
    "ALL_KW": "`all`",
    "SAVE_KW": "`.save`",
    "OUTPUT_VECTOR": "output vector",
    "VOLTAGE_OPEN": "`v(` (or `vr(`, `vi(`, `vm(`, `vp(`, `vdb(`)",
    "CURRENT_OPEN": "`i(`",
    "CURRENT_VARIANT_OPEN": "`ir(`, `ii(`, `im(`, `ip(` or `idb(`",
    "MEAS_KW": "`.meas`",
    "MEASURE_KW": "`.measure`",
    "TRAN_ANALYSIS_KW": "`tran`",
    "SP_KW": "`sp`",
    "GLOBAL_KW": "`.global`",
}
_MISSING_END = "the netlist must end with `.end`, which is missing"


@lru_cache(maxsize=None)
def build_parser(dialect: Dialect) -> Lark:
    """Build or retrieve the strict LALR parser for ``dialect``."""
    if not isinstance(dialect, Dialect):
        raise ValueError(f"Unknown dialect {dialect!r}")
    try:
        grammar_files = GRAMMARS[dialect]
    except KeyError as error:
        raise ValueError(f"No grammar registered for dialect {dialect.value}") from error
    return Lark.open_from_package(
        "netlistmod.grammar",
        grammar_files[-1],
        parser="lalr",
        lexer="contextual",
        propagate_positions=True,
        strict=True,
    )


def parse_tree(source: SourceText, dialect: Dialect) -> Tree[Token]:
    """Parse source into a positioned Lark tree using an explicit dialect.

    Raises ``ParseError`` (or ``UnsupportedConstruct`` for a known but unsupported element
    letter). Positions come only from ``SourceText``.
    """
    parser = build_parser(dialect)
    try:
        return parser.parse(source.text)
    except UnexpectedToken as error:
        at_end = error.token.type == _END_OF_INPUT
        offset = len(source.text) if at_end else int(error.token.start_pos or 0)
        raise _map_error(source, dialect, offset, error.expected, error) from error
    except UnexpectedCharacters as error:
        raise _map_error(
            source, dialect, int(error.pos_in_stream or 0), error.allowed or (), error
        ) from error


def _expected_names(terminals: Iterable[object]) -> tuple[str, ...]:
    names = {_TERMINAL_NAMES.get(str(terminal), str(terminal)) for terminal in terminals}
    return tuple(sorted(names))


def _value_stack(error: UnexpectedToken) -> list[object]:
    """The parser's value stack at the failure: tokens and trees of the still-open rules."""
    if error.interactive_parser is not None:
        return list(error.interactive_parser.parser_state.value_stack)
    return list(getattr(error.state, "value_stack", ()))


def _unterminated_block(
    dialect: Dialect, error: UnexpectedToken
) -> tuple[Token, tuple[str, str]] | None:
    blocks = _BLOCKS.get(dialect, {})
    for value in reversed(_value_stack(error)):
        if isinstance(value, Token) and value.type in blocks:
            return value, blocks[value.type]
        if isinstance(value, Tree) and value.data in blocks:
            opener = value.children[0]
            assert isinstance(opener, Token)
            return opener, blocks[str(value.data)]
    return None


def _unclosed_parenthesis(error: UnexpectedToken) -> Token | None:
    if error.token.type not in _LINE_ENDS:
        return None
    # A ")" still on the stack closes the parenthesis before it (v(1) waiting for "=value").
    for value in reversed(_value_stack(error)):
        if isinstance(value, Token) and value.type == "RPAR":
            return None
        if isinstance(value, Token) and value.type in _OPEN_PARENS:
            return value
    return None


def _map_error(
    source: SourceText,
    dialect: Dialect,
    offset: int,
    expected_terminals: Iterable[object],
    error: UnexpectedToken | UnexpectedCharacters,
) -> ParseError | UnsupportedConstruct:
    expected = _expected_names(expected_terminals)
    if isinstance(error, UnexpectedToken) and error.token.type == _END_OF_INPUT:
        block = _unterminated_block(dialect, error)
        if block is not None:
            opener, (name, closing) = block
            opener_offset = int(opener.start_pos or 0)
            line, column = source.position(opener_offset)
            return ParseError(
                line,
                column,
                source.excerpt(opener_offset),
                (f"`{closing}`",),
                f"unterminated `{name}` block: `{closing}` is missing before end of input",
            )
        reason = _MISSING_END if "END_KW" in {str(t) for t in expected_terminals} else ""
        line, column = source.position(offset)
        return ParseError(line, column, source.excerpt(offset), expected, reason)
    if isinstance(error, UnexpectedToken):
        parenthesis = _unclosed_parenthesis(error)
        if parenthesis is not None:
            opener_offset = int(parenthesis.start_pos or 0)
            line, column = source.position(opener_offset)
            return ParseError(
                line,
                column,
                source.excerpt(opener_offset),
                ("`)`",),
                "unbalanced `(`: `)` is missing before the end of the line",
            )

    line, column = source.position(offset)
    line_start = source.line_span(line).start
    letter = source.text[offset : offset + 1].upper()
    if letter.isalpha() and not source.text[line_start:offset].strip(" \t"):
        # A supported letter fails inside its line, or where no element may stand (after
        # .end): both are syntax errors. Only a planned letter is an unsupported construct.
        if device_matrix().get(letter, {}).get("status") == "planned":
            return UnsupportedConstruct(
                f"{dialect.value} {letter} device", line, column, source.excerpt(offset)
            )
    return ParseError(line, column, source.excerpt(offset), expected)


@lru_cache(maxsize=1)
def device_matrix() -> dict[str, dict[str, int | str]]:
    """Load the ngspice device status matrix used for strict element errors."""
    resource = files("netlistmod.grammar") / _DEVICE_MATRIX
    parsed = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("ngspice device matrix must contain a JSON object")
    return parsed


def registered_dialects() -> frozenset[Dialect]:
    """Return dialects with implemented grammars."""
    return frozenset(GRAMMARS)


def pending_dialects() -> frozenset[Dialect]:
    """Return dialects intentionally awaiting their grammar milestone."""
    return _PENDING_DIALECTS
