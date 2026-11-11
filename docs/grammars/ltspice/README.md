# LTspice grammar

The LTspice grammar (M8, [decision 0009](../../decisions/0009-ltspice-dialect.md)) and its
conformance records:

- [Device-letter matrix](./devices.md) and its packaged
  [machine-readable source](../../../src/netlistmod/grammar/ltspice-devices.json).
- [Numbers and values](./numbers.md): numbers, the embedded decimal and formulas.
- [Spec entries](./specs/) cite the reference and link to tests.
- [Names](./names.md) and [scoping](./scoping.md) rules of the document layer.
- [Discrepancies](./discrepancies.md) records where LTspice and the library differ.
- [The LTspice export workflow](../../usage/ltspice-export.md).

The manual for this dialect is `analogdevicesinc/ltspice-reference`, cited as
`[ltspice-ref] <FILE>.md "<heading>"` ([references.md](../../references.md)). The repository records
only syntax facts about LTspice: never its raw files, logs, or timing or performance numbers
(decision 0009 item 2). `core_rules` in an entry names the shared rules of `core.lark` and
`formula.lark` it relies on; `grammar` names the rules of `ltspice.lark`.

## Construct survey (M8 T1)

| Construct | Reference | ngspice form shared? | LTspice overlay |
|---|---|---|---|
| Title, `.end` | [SYNTAX] Netlist Structure | yes | `.end` takes a comment |
| Comments | [SYNTAX] Comments and Line Continuation | `*` and `;` only | `;` lines, ` $ `; no `//` |
| Continuation | same | `+` only | no `\\` |
| Separators | element syntax | blanks only | commas in few places |
| Names | [SYNTAX] Node Naming | no | own character set, Unicode fold, `$G_*` |
| Numbers | [SYNTAX] Engineering Multipliers | standard form | embedded decimal in every slot, any trailing letters |
| R | [ELEMENTS] R | value, formula | `tc` list, closed list; no model or keyword form |
| C, L | [ELEMENTS] C, L | value, formula; C `Q=`, L `Flux=` and the hysteretic core (M15) | closed lists; no parameters on `Flux=` or the hysteretic core |
| V, I | [ELEMENTS] V, I | DC, AC | `AC=`, `Rser`, `Cpar`, `load`, `R=` |
| D | [ELEMENTS] D | model | positional area, closed list |
| X, `.subckt` | [ELEMENTS] X, [COMMANDS] .SUBCKT | yes | `params:` accepted |
| K | [ELEMENTS] K | yes | |
| `.param` | [COMMANDS] .PARAM | `=` with a number or formula | no `=`, bare expressions, other names |
| `.model` | [COMMANDS] .MODEL | yes | `ako:` |
| `.tran` | [COMMANDS] .TRAN | yes | one argument, modifiers |
| `.ac` | [COMMANDS] .AC | yes | `list`, `file=` |
| `.dc` | [COMMANDS] .DC | yes | three sweeps, variation, `list`, `file=` |
| `.op` | [COMMANDS] .OP | yes | |
| `.temp` | [COMMANDS] .TEMP | one value | a list |
| `.options` | [COMMANDS] .OPTIONS | yes | `.opt` |
| `.ic`, `.nodeset` | [TROUBLE] | `v(n)=` | no `all=` |
| `.save` | [COMMANDS] .SAVE | `v()`, `i()` | device currents, wildcards; no plain names |
| `.meas` | [COMMANDS] .MEASURE | yes | optional analysis, `noise`, `op`; no `sp` |
| `.global` | [COMMANDS] .GLOBAL | yes | |
| `.step` | [COMMANDS] .STEP | no | new typed node |
| Other dot-commands | [COMMANDS] | no | closed list |

## Validation status

Status words have the meanings of
[decision 0008](../../decisions/0008-validation-status-and-solver-harnesses.md);
`tests/architecture/test_spec_coverage.py` checks each against its evidence and this table against
the entries. The probes are in `tests/solver/test_ltspice_validation.py`; a part of an entry that the
reference does not mention is marked observed in the entry's notes (§11.3 rule 3). "Tests" counts
an entry's test references: those outside `tests/solver/`, then the solver probes, which run only
where LTspice is installed. The table and its totals line are the output of
`python -m tests.support.spec_coverage ltspice`.

| Entry | Construct | Status | Tests | Validated on |
|---|---|---|---|---|
| [LT-ACA-001](./specs/LT-ACA-001.yaml) | .ac | validated | 2 + 3 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-BEH-001](./specs/LT-BEH-001.yaml) | behavioral source (B) lines | validated | 5 + 2 solver | ltspice 26.1.1 (2026-11-06) |
| [LT-BJT-001](./specs/LT-BJT-001.yaml) | bipolar transistor (Q) lines | validated | 3 + 3 solver | ltspice 26.1.1 (2026-11-05) |
| [LT-CAP-001](./specs/LT-CAP-001.yaml) | capacitor (C) lines | validated | 5 + 4 solver | ltspice 26.1.1 (2026-11-01, 2026-11-06) |
| [LT-CCC-001](./specs/LT-CCC-001.yaml) | current-dependent current source (F) lines | validated | 2 + 2 solver | ltspice 26.1.1 (2026-11-06) |
| [LT-CCV-001](./specs/LT-CCV-001.yaml) | current-dependent voltage source (H) lines | validated | 1 + 3 solver | ltspice 26.1.1 (2026-11-06) |
| [LT-CNT-001](./specs/LT-CNT-001.yaml) | + continuation lines | validated | 2 + 3 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-COM-001](./specs/LT-COM-001.yaml) | comment lines (* and ;) | validated | 2 + 2 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-COM-002](./specs/LT-COM-002.yaml) | end-of-line comments (; and space-$-space) | validated | 3 + 2 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-CTL-001](./specs/LT-CTL-001.yaml) | shared shape of the linear dependent sources and switches | validated | 3 + 1 solver | ltspice 26.1.1 (2026-11-06) |
| [LT-DCA-001](./specs/LT-DCA-001.yaml) | .dc | validated | 3 + 3 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-DIO-001](./specs/LT-DIO-001.yaml) | diode (D) lines | validated | 3 + 4 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-DIR-001](./specs/LT-DIR-001.yaml) | closed list of dot-commands | validated | 3 + 9 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-END-001](./specs/LT-END-001.yaml) | required final .end | validated | 2 + 2 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-FLD-001](./specs/LT-FLD-001.yaml) | field separators | validated | 2 + 3 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-FML-001](./specs/LT-FML-001.yaml) | formula expression syntax (reference scan only) | validated | 3 + 6 solver | ltspice 26.1.1 (2026-11-01, 2026-11-10) |
| [LT-FRA-001](./specs/LT-FRA-001.yaml) | frequency response analyzer (@) lines | validated | 6 + 3 solver | ltspice 26.1.1 (2026-11-10) |
| [LT-FRP-001](./specs/LT-FRP-001.yaml) | frequency response probe (&) lines | validated | 3 + 2 solver | ltspice 26.1.1 (2026-11-10) |
| [LT-FUN-001](./specs/LT-FUN-001.yaml) | source functions, shared syntax | validated | 3 + 3 solver | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-002](./specs/LT-FUN-002.yaml) | PULSE | validated | 1 + 1 solver | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-003](./specs/LT-FUN-003.yaml) | SINE and SIN | validated | 1 + 1 solver | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-004](./specs/LT-FUN-004.yaml) | EXP | validated | 1 + 1 solver | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-005](./specs/LT-FUN-005.yaml) | SFFM | validated | 1 + 1 solver | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-006](./specs/LT-FUN-006.yaml) | PWL with its scale factors and file | validated | 3 + 5 solver | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-007](./specs/LT-FUN-007.yaml) | PWL REPEAT | validated | 2 + 4 solver | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-008](./specs/LT-FUN-008.yaml) | wave file | validated | 3 + 2 solver | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-009](./specs/LT-FUN-009.yaml) | I table | validated | 1 + 1 solver | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-010](./specs/LT-FUN-010.yaml) | I step load | validated | 1 + 2 solver | ltspice 26.1.1 (2026-11-04) |
| [LT-GLB-001](./specs/LT-GLB-001.yaml) | .global | validated | 3 + 2 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-ICN-001](./specs/LT-ICN-001.yaml) | .ic and .nodeset | validated | 4 + 5 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-IND-001](./specs/LT-IND-001.yaml) | inductor (L) lines | validated | 4 + 3 solver | ltspice 26.1.1 (2026-11-01, 2026-11-06) |
| [LT-JFT-001](./specs/LT-JFT-001.yaml) | junction FET (J) lines | validated | 2 + 2 solver | ltspice 26.1.1 (2026-11-05) |
| [LT-LAP-001](./specs/LT-LAP-001.yaml) | Laplace= on E and G, and laplace= on B | validated | 7 + 3 solver | ltspice 26.1.1 (2026-11-08) |
| [LT-LTR-001](./specs/LT-LTR-001.yaml) | lossy transmission line (O) lines | validated | 3 + 3 solver | ltspice 26.1.1 (2026-11-09) |
| [LT-MCH-001](./specs/LT-MCH-001.yaml) | .machine blocks | validated | 1 + 2 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-MEA-001](./specs/LT-MEA-001.yaml) | .meas and .measure | validated | 2 + 3 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-MES-001](./specs/LT-MES-001.yaml) | MESFET and IGBT (Z) lines | validated | 2 + 1 solver | ltspice 26.1.1 (2026-11-05) |
| [LT-MOD-001](./specs/LT-MOD-001.yaml) | .model statements | validated | 8 + 6 solver | ltspice 26.1.1 (2026-11-01, 2026-11-05, 2026-11-09) |
| [LT-MOS-001](./specs/LT-MOS-001.yaml) | MOSFET and VDMOS (M) lines | validated | 3 + 3 solver | ltspice 26.1.1 (2026-11-05) |
| [LT-MUT-001](./specs/LT-MUT-001.yaml) | mutual inductance (K) lines | validated | 2 + 4 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-NLS-001](./specs/LT-NLS-001.yaml) | expression forms of the dependent sources (value= on E, F, G and H) | validated | 6 + 1 solver | ltspice 26.1.1 (2026-11-06) |
| [LT-NOD-001](./specs/LT-NOD-001.yaml) | node, element and subcircuit names | validated | 3 + 5 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-NUM-001](./specs/LT-NUM-001.yaml) | numbers | validated | 1 + 1 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-NUM-002](./specs/LT-NUM-002.yaml) | letters following a number | validated | 2 + 3 solver | ltspice 26.1.1 (2026-11-01, 2026-11-11) |
| [LT-NUM-003](./specs/LT-NUM-003.yaml) | embedded decimal | validated | 2 + 3 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-NUM-004](./specs/LT-NUM-004.yaml) | micro signs | validated | 2 + 2 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-OPA-001](./specs/LT-OPA-001.yaml) | opaque .include, .inc and .lib, and .lib blocks | validated | 4 + 4 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-OPP-001](./specs/LT-OPP-001.yaml) | .op | validated | 1 + 1 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-OPT-001](./specs/LT-OPT-001.yaml) | .options, .option and .opt | validated | 2 + 2 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-PLY-001](./specs/LT-PLY-001.yaml) | POLY on E, F, G and H | validated | 6 + 4 solver | ltspice 26.1.1 (2026-11-08, 2026-11-11) |
| [LT-PRM-001](./specs/LT-PRM-001.yaml) | .param assignments | validated | 4 + 4 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-RES-001](./specs/LT-RES-001.yaml) | resistor (R) lines | validated | 6 + 3 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-SAV-001](./specs/LT-SAV-001.yaml) | .save | validated | 3 + 4 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-SBD-001](./specs/LT-SBD-001.yaml) | .subckt ... .ends definitions | validated | 3 + 6 solver | ltspice 26.1.1 (2026-11-01, 2026-11-11) |
| [LT-SPF-001](./specs/LT-SPF-001.yaml) | special function (A) lines | validated | 6 + 3 solver | ltspice 26.1.1 (2026-11-10) |
| [LT-SRC-001](./specs/LT-SRC-001.yaml) | independent sources (V, I) | validated | 9 + 12 solver | ltspice 26.1.1 (2026-11-01, 2026-11-10) |
| [LT-STP-001](./specs/LT-STP-001.yaml) | .step | validated | 4 + 7 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-STR-001](./specs/LT-STR-001.yaml) | top-level source structure | validated | 3 + 3 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-SUB-001](./specs/LT-SUB-001.yaml) | subcircuit calls (X) | validated | 3 + 2 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-SWC-001](./specs/LT-SWC-001.yaml) | current-controlled switch (W) lines | validated | 1 + 2 solver | ltspice 26.1.1 (2026-11-06) |
| [LT-SWV-001](./specs/LT-SWV-001.yaml) | voltage-controlled switch (S) lines | validated | 2 + 3 solver | ltspice 26.1.1 (2026-11-06) |
| [LT-TBL-001](./specs/LT-TBL-001.yaml) | table= on E and G | validated | 4 + 3 solver | ltspice 26.1.1 (2026-11-08) |
| [LT-TLL-001](./specs/LT-TLL-001.yaml) | lossless transmission line (T) lines | validated | 4 + 4 solver | ltspice 26.1.1 (2026-11-09) |
| [LT-TMP-001](./specs/LT-TMP-001.yaml) | .temp | validated | 2 + 2 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-TRN-001](./specs/LT-TRN-001.yaml) | .tran | validated | 2 + 3 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-TTL-001](./specs/LT-TTL-001.yaml) | implicit first-line title and .title | validated | 1 + 2 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-TXT-001](./specs/LT-TXT-001.yaml) | statement text | validated | 3 + 3 solver | ltspice 26.1.1 (2026-11-01, 2026-11-11) |
| [LT-UNS-001](./specs/LT-UNS-001.yaml) | recognised but unsupported forms | validated | 2 + 2 solver | ltspice 26.1.1 (2026-11-01, 2026-11-10) |
| [LT-URC-001](./specs/LT-URC-001.yaml) | uniform RC line (U) lines | validated | 3 + 4 solver | ltspice 26.1.1 (2026-11-09) |
| [LT-VAL-001](./specs/LT-VAL-001.yaml) | brace and quoted expressions | validated | 2 + 3 solver | ltspice 26.1.1 (2026-11-01) |
| [LT-VCC-001](./specs/LT-VCC-001.yaml) | voltage-dependent current source (G) lines | validated | 2 + 2 solver | ltspice 26.1.1 (2026-11-06) |
| [LT-VCV-001](./specs/LT-VCV-001.yaml) | voltage-dependent voltage source (E) lines | validated | 2 + 3 solver | ltspice 26.1.1 (2026-11-06) |
| [LT-XTR-001](./specs/LT-XTR-001.yaml) | shared transistor line shape (Q, M, J, Z) | validated | 4 + 3 solver | ltspice 26.1.1 (2026-11-05, 2026-11-11) |

73 entries: 73 validated, 0 observed, 0 disputed, 0 documented.

## Lookaround terminals

As for ngspice ([ngspice README](../ngspice/README.md#lookaround-terminals)): Lark's strict mode
skips these terminals in its collision check, `UNCHECKED_TERMINALS` in
`tests/architecture/test_contracts.py` lists them, and M18 reviewed each one by hand (A2, Lark
1.3.1). `.N` is a terminal's priority. The LTspice grammar has no merged block state:
`BLOCK_TEXT` competes only with block terminals.

| Terminal | Matches | Candidate in | Competitors | Why no collision |
|---|---|---|---|---|
| `BARE_FORMULA.5` | a bare `.param` expression; refuses a plain number that ends its field | 3 states: a `.param` value | below: `NUMBER`, `EMBEDDED`, `BRACE_FORMULA`, `QUOTE_FORMULA`, `STRING_VALUE` | No competitor at its priority. Its lookahead leaves numbers to `NUMBER` and `EMBEDDED`: `1k ; c`, `1k $ c`, `1k,` and `-1k` give `NUMBER`, `2k2` gives `EMBEDDED`, and `1k*2` and `1..2` give `BARE_FORMULA`. |
| `BLOCK_TEXT.2` | a non-blank, then text to the end of the line | 38 states: the lines of `.lib` and `.machine` blocks | `BLOCK_DOT_NAME`, `ENDL_KW`, `ENDMACHINE_KW`, `NL`, `LINE_END`, `CONT`, `WS` | No competitor at its priority, and only block terminals compete. |
| `BRACE_FORMULA.3` | `{…}`; a `$` inside only when no blank follows it | 106 states: value slots | 13 at its priority (`NUMBER`, `QUOTE_FORMULA`, `STRING_VALUE`, `TRAILING_COMMENT`, `GAIN_KW`, `LAPLACE_KW`, `TABLE_KW` …) | Disjoint: only it starts with `{`. |
| `B_PIECE.4` | a piece of a bare B expression, stopping before `name=` or a comment | 24 states: after the output nodes of B | above: `SEP`, `NL`, `CONT`, `WS`; below: `BRACE_FORMULA`, `QUOTE_FORMULA`, `B_PARAM_KW`, `LAPLACE_KW`, `TRAILING_COMMENT` … | No competitor at its priority; as in ngspice. |
| `COMMENT_LINE.3` | `*` or `;` to the end of the line | 595 states: line starts | the letter names, the dot keywords, `TOP_DOT_NAME`, `LIB_BLOCK_KW`, `TITLE_KW` | No competitor at its priority; nothing else starts with `*` or `;`. |
| `LIB_BLOCK_KW.5` | as in ngspice | 595 states: line starts | `LIB_KW.4`, `INC_KW` and the other dot keywords | As in ngspice. |
| `MODEL_BARE.5` | a bare word as a `.model` parameter value (refused with a hint); refuses a number or embedded decimal ended by a blank, `,`, `)` or the line end | 3 states: a `.model` parameter value | above: `DOTTED_VALUE.6`; below: `NUMBER`, `EMBEDDED`, `BRACE_FORMULA`, `QUOTE_FORMULA` | No competitor at its priority: `is=1e-14)`, `is=1meg)` and `is=1e-14 ; c` give `NUMBER`, `is=2k2` gives `EMBEDDED`, and `is=abc` gives `MODEL_BARE`. |
| `TEXT.2` | statement text up to `;` or a quote; a `$` is text unless it has a blank on both sides | 66 states: the text of untyped statements | `QUOTED`, `TRAILING_COMMENT`, `SEP`, `NL`, `LINE_END`, `CONT` | No competitor at its priority. A `$` with a blank on both sides ends `TEXT`, and `TRAILING_COMMENT` starts there. |
| `TITLE_ARG.3` | as in ngspice | 2 states | `WS`, `LINE_END`, `CONT` | As in ngspice. |
| `TITLE_TEXT.2` | as in ngspice | 1 state | `TITLE_KW.6`, `WS`, `LINE_END`, `CONT` | As in ngspice. |
| `TRAILING_COMMENT.3` | `;`, or `$` after a blank, to the end of the line | 1326 states: after any field | 30 at its priority (`NUMBER`, `QUOTED`, `BRACE_FORMULA`, `AKO_REF`, `SF_FUNCTION_KW`, the `*_PARAM_KW` lookahead keywords …) | Disjoint by first character (`;` or `$`). A tab beside the `$` makes it text ([discrepancies](./discrepancies.md)). |
