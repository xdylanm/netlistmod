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
    Dialect.LTSPICE: ("core.lark", "ltspice.lark"),
}
_PENDING_DIALECTS: Final[frozenset[Dialect]] = frozenset()
_DEVICE_MATRICES: Final[dict[Dialect, str]] = {
    Dialect.NGSPICE: "ngspice-devices.json",
    Dialect.LTSPICE: "ltspice-devices.json",
}

# Opener terminal, or the rule whose first token is the opener -> (block name, closing keyword).
# Used only to explain an unterminated block.
_BLOCKS: Final[dict[Dialect, dict[str, tuple[str, str]]]] = {
    Dialect.NGSPICE: {
        "CONTROL_KW": (".control", ".endc"),
        "IF_KW": (".if", ".endif"),
        "SUBCKT_KW": (".subckt", ".ends"),
        "subckt_header": (".subckt", ".ends"),
    },
    Dialect.LTSPICE: {
        "MACHINE_KW": (".machine", ".endmachine"),
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
    "ENDL_KW": "`.endl`",
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
    "Q_NAME": "bipolar transistor (`Q`)",
    "M_NAME": "MOSFET (`M`)",
    "J_NAME": "JFET (`J`)",
    "Z_NAME": "MESFET (`Z`)",
    "FIELD_NUMBER": "number",
    "FIELD_EMBEDDED": "number",
    "IC_PARAM_KW": "`ic=`",
    "THERMAL_KW": "`thermal`",
    "E_NAME": "voltage-controlled voltage source (`E`)",
    "G_NAME": "voltage-controlled current source (`G`)",
    "F_NAME": "current-controlled current source (`F`)",
    "H_NAME": "current-controlled voltage source (`H`)",
    "S_NAME": "voltage-controlled switch (`S`)",
    "W_NAME": "current-controlled switch (`W`)",
    "ON_KW": "`on`",
    "CTL_M_KW": "`m=`",
    "E_FORM_KW": "`vol=` or `value`",
    "G_FORM_KW": "`cur=` or `value`",
    "VALUE_FORM_KW": "`value=`",
    "VALUE_WORD_KW": "`value`",
    "OPEN_FORMULA": "unclosed expression",
    "B_NAME": "behavioral source (`B`)",
    "B_QUANTITY_KW": "behavioral source quantity",
    "B_LT_QUANTITY_KW": "behavioral source quantity",
    "B_PARAM_KW": "behavioral source parameter",
    "TABLE_KW": "`TABLE`",
    "LAPLACE_KW": "`Laplace=`",
    "LAP_PARAM_KW": "`window=`, `nfft=` or `mtol=`",
    "TABLE4_KW": "`TABLE`",
    "TABLE_BARE_KW": "`TABLE`",
    "POLY_KW": "`POLY`",
    "POLY_DIM": "the dimension of `POLY`",
    "FREQ_KW": "`FREQ`",
    "FREQ_FMT_KW": "a FREQ format word (`DB`, `MAG`, `DEG`, `RAD`, `R_I`)",
    "GATE_KW": "`AND`, `OR`, `NAND` or `NOR`",
    "B_PIECE": "expression",
    "Q_PARAM_KW": "bipolar transistor parameter",
    "M_PARAM_KW": "MOSFET parameter",
    "J_PARAM_KW": "JFET parameter",
    "Z_PARAM_KW": "MESFET parameter",
    "PCHAN_KW": "`pchan`",
    "NCHAN_KW": "`nchan`",
    "DOTTED_VALUE": "dotted value",
    "T_NAME": "lossless transmission line (`T`)",
    "O_NAME": "lossy transmission line (`O`)",
    "U_NAME": "uniform RC line (`U`)",
    "Y_NAME": "TXL transmission line (`Y`)",
    "P_NAME": "coupled transmission line (`P`)",
    "T_PARAM_KW": "transmission line parameter",
    "T_UNLISTED_KW": "transmission line parameter",
    "U_WORD": "name",
    "U_PARAM_KW": "`l=` or `n=`",
    "U_BARE": "parameter name",
    "LEN_KW": "`len=`",
    "NOSTEPLIMIT_KW": "`nosteplimit`",
    "STEPLIMIT_KW": "`steplimit`",
    "NOCONTROL_KW": "`nocontrol`",
    "LININTERP_KW": "`lininterp`",
    "MIXEDINTERP_KW": "`mixedinterp`",
    "TRUNCNR_KW": "`truncnr`",
    "TRUNCDONTCUT_KW": "`truncdontcut`",
    "A_NAME": "code model (`A`)",
    "A_TYPE": "port type (`%v`, `%i`, `%g`, `%h` or `%d`)",
    "A_DTYPE": "differential port type (`%vd`, `%id`, `%gd` or `%hd`)",
    "A_VNAM": "`%vnam`",
    "A_NOT": "`~`",
    "A_NOT_BLANK": "`~`",
    "A_PCOMMA": "`,`",
    "A_PARAM_KW": "parameter name",
    "VEC_OPEN": "`[`",
    "VEC_CLOSE": "`]`",
    "BOOL_KW": "`TRUE` or `FALSE`",
    "N_NAME": "OSDI device (`N`)",
    "SF_FUNCTION_KW": "special function name (`BUF`, `AND`, `OR`, `XOR`, `SCHMITT`, `DFLOP`, "
    "`SRFLOP`, `VARISTOR`, `MODULATOR`, `OTA`, `PHASEDET`, `COUNTER` or `SAMPLEHOLD`)",
    "FRA_NAME": "frequency response analyzer (`@`)",
    "FRA_PARAM_KW": "frequency response analyzer parameter",
    "FRA_NET_KW": "`refnode=` or `intnode=`",
    "FRA_UNLISTED_KW": "parameter name",
    "ZM_KW": "`zm`",
    "PROBE_NAME": "frequency response probe (`&`)",
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
    "PULSE_KW": "`PULSE`",
    "SIN_KW": "`SIN`",
    "SINE_KW": "`SINE`",
    "EXP_KW": "`EXP`",
    "PWL_KW": "`PWL`",
    "SFFM_KW": "`SFFM`",
    "AM_KW": "`AM`",
    "TRNOISE_KW": "`TRNOISE`",
    "TRRANDOM_KW": "`TRRANDOM`",
    "EXTERNAL_KW": "`EXTERNAL`",
    "DISTOF1_KW": "`DISTOF1`",
    "DISTOF2_KW": "`DISTOF2`",
    "PORT_KW": "`portnum` or `z0`",
    "FN_PARAM_KW": "a function's named parameter",
    "TRIGGER_KW": "`Trigger=`",
    "TRIP_KW": "`tripdv=` or `tripdt=`",
    "TRIGGER_EXPR": "trigger expression",
    "PWL_FACTOR_KW": "scale factor",
    "PWL_FILE_KW": "`file=`",
    "FILE_PATH": "file path",
    "REPEAT_KW": "`REPEAT`",
    "FOR_KW": "`FOR`",
    "FOREVER_KW": "`FOREVER`",
    "ENDREPEAT_KW": "`ENDREPEAT`",
    "WAVEFILE_KW": "`wavefile=`",
    "TBL_KW": "`tbl=`",
    "I_STEP_KW": "`step`",
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
    "EMBEDDED": "embedded-decimal value",
    "BARE_FORMULA": "expression",
    "TC_KW": "`tc=`",
    "R_PARAM_KW": "resistor parameter",
    "C_PARAM_KW": "capacitor parameter",
    "L_PARAM_KW": "inductor parameter",
    "V_PARAM_KW": "`Rser=` or `Cpar=`",
    "D_PARAM_KW": "diode parameter",
    "FLUX_KW": "`Flux=`",
    "HYSTERETIC_KW": "hysteretic core parameter",
    "LOAD_KW": "`load`",
    "I_R_KW": "`R=`",
    "AKO_REF": "`ako:` base model",
    "MODEL_TEXT_KW": "`mfg=` or `type=`",
    "MODEL_BARE": "bare word",
    "R_TEXT_KW": "`mfg=` or `pn=`",
    "C_TEXT_KW": "`mfg=`, `pn=` or `type=`",
    "L_TEXT_KW": "`mfg=` or `pn=`",
    "NOISELESS_KW": "`noiseless`",
    "TOP_DOT_NAME": "dot-command",
    "INC_KW": "`.inc`",
    "MACHINE_KW": "`.machine`",
    "ENDMACHINE_KW": "`.endmachine`",
    "TRAN_MODIFIER_KW": "`.tran` modifier",
    "LIST_KW": "`list`",
    "FILE_KW": "`file=`",
    "FILE_NAME": "file name",
    "OPT_KW": "`.opt`",
    "DEVICE_CURRENT_OPEN": "device current (`Id(` and so on)",
    "SAVE_PATTERN": "name with a wildcard",
    "NOISE_KW": "`noise`",
    "OP_ANALYSIS_KW": "`op`",
    "STEP_KW": "`.step`",
    "STEP_PARAM_KW": "`param`",
    "STEP_TEMP_KW": "`temp`",
    "STEP_MODEL_REF": "model(parameter)",
}
# Where a dialect's terminal means something else than in the table above.
_DIALECT_TERMINAL_NAMES: Final[dict[Dialect, dict[str, str]]] = {
    Dialect.NGSPICE: {},
    Dialect.LTSPICE: {
        "TRAILING_COMMENT": "trailing comment (`;`, or `$` with a space on both sides)",
        "COMMENT_LINE": "comment line (`*` or `;`)",
        "VOLTAGE_OPEN": "`v(`",
    },
}
_MISSING_END = "the netlist must end with `.end`, which is missing"
_INCOMPLETE_LINE = "this line ends too early"
_AFTER_END = "the netlist ends at `.end`: only blank lines may follow it"
# May stand after any field, so they do not tell a reader what a line that ended early is missing.
_FIELD_PUNCTUATION: Final[frozenset[str]] = frozenset(
    {"SEP", "CSEP", "BS_CONT", "TRAILING_COMMENT"}
)


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


def _expected_names(terminals: Iterable[object], dialect: Dialect) -> tuple[str, ...]:
    table = {**_TERMINAL_NAMES, **_DIALECT_TERMINAL_NAMES[dialect]}
    # LIB_BLOCK_KW is a `.lib` whose lookahead found a block, not a thing to ask for by name.
    names = {
        table.get(str(terminal), str(terminal))
        for terminal in terminals
        if str(terminal) != "LIB_BLOCK_KW"
    }
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


def _missing_after_line_end(
    error: UnexpectedToken, expected_terminals: Iterable[object]
) -> frozenset[str] | None:
    """What a line that ended too early still needs, without punctuation; often nothing, since
    only the grammar knows the missing field. ``None`` if this error is not such a line."""
    if error.token.type not in _LINE_ENDS:
        return None
    terminals = {str(terminal) for terminal in expected_terminals}
    if error.token.type == _END_OF_INPUT:
        # At end of input the parser has not reduced yet, so its list holds lookaheads of other
        # rules, such as a line end it would refuse. Ask it what it really accepts.
        if error.interactive_parser is None:
            return None
        terminals = set(error.interactive_parser.accepts())  # type: ignore[no-untyped-call]
    if terminals & _LINE_ENDS or "END_KW" in terminals:
        return None
    return frozenset(terminals - _FIELD_PUNCTUATION)


def _after_end(error: UnexpectedToken | UnexpectedCharacters, expected: Iterable[object]) -> bool:
    """Whether the parser has read the top-level ``.end`` line, where only blank lines remain."""
    if not isinstance(error, UnexpectedToken) or {str(t) for t in expected} != {"LINE_END"}:
        return False
    return any(isinstance(v, Token) and v.type == "END_KW" for v in _value_stack(error))


def _incomplete_line(
    source: SourceText, dialect: Dialect, offset: int, missing: Iterable[object]
) -> ParseError:
    line, column = source.position(offset)
    return ParseError(
        line, column, source.excerpt(offset), _expected_names(missing, dialect), _INCOMPLETE_LINE
    )


def _map_error(
    source: SourceText,
    dialect: Dialect,
    offset: int,
    expected_terminals: Iterable[object],
    error: UnexpectedToken | UnexpectedCharacters,
) -> ParseError | UnsupportedConstruct:
    expected = _expected_names(expected_terminals, dialect)
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
        missing = _missing_after_line_end(error, expected_terminals)
        if missing is not None:
            return _incomplete_line(source, dialect, offset, missing)
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
        missing = _missing_after_line_end(error, expected_terminals)
        if missing is not None:
            return _incomplete_line(source, dialect, offset, missing)

    line, column = source.position(offset)
    line_start = source.line_span(line).start
    letter = source.text[offset : offset + 1].upper()
    if not source.text[line_start:offset].strip(" \t"):
        # No element may stand after .end, whatever its letter, so that comes first. Otherwise a
        # supported letter fails inside its line, a syntax error; only a planned letter is an
        # unsupported construct.
        if _after_end(error, expected_terminals):
            return ParseError(line, column, source.excerpt(offset), expected, _AFTER_END)
        if device_matrix(dialect).get(letter, {}).get("status") == "planned":
            return UnsupportedConstruct(
                f"{dialect.display_name} {letter} device", line, column, source.excerpt(offset)
            )
        if letter == "." and dialect is Dialect.LTSPICE:
            # The closed list of decision 0009: no terminal of this place matches the command.
            name = source.text[offset:].split(maxsplit=1)[0]
            reason = f"`{name}` is not an LTspice dot-command, or is not allowed here"
            return ParseError(line, column, source.excerpt(offset), expected, reason)
    return ParseError(line, column, source.excerpt(offset), expected)


@lru_cache(maxsize=None)
def device_matrix(dialect: Dialect) -> dict[str, dict[str, int | str]]:
    """Load a dialect's device status matrix, used for strict element errors."""
    resource = files("netlistmod.grammar") / _DEVICE_MATRICES[dialect]
    parsed = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"{dialect.value} device matrix must contain a JSON object")
    return parsed


def registered_dialects() -> frozenset[Dialect]:
    """Return dialects with implemented grammars."""
    return frozenset(GRAMMARS)


def pending_dialects() -> frozenset[Dialect]:
    """Return dialects intentionally awaiting their grammar milestone."""
    return _PENDING_DIALECTS
