# ngspice grammar

The ngspice grammar (M2 structure, M3 elements and values) and its conformance
records are tracked here:

- [Device-letter matrix](./devices.md) and its packaged
  [machine-readable source](../../../src/netlistmod/grammar/ngspice-devices.json).
- [Numbers and values](./numbers.md): number, RKM and formula rules.
- [Spec entries](./specs/) cite the ngspice manual and link to tests.
- [Names](./names.md) and [scoping](./scoping.md) rules of the document layer.
- [Discrepancies](./discrepancies.md) records probe results that differ from
  or extend the manual.

## Validation status

Status words have the meanings of
[decision 0008](../../decisions/0008-validation-status-and-solver-harnesses.md);
`tests/architecture/test_spec_coverage.py` checks each against its solver evidence and this
table against the entries. Re-validating appends a version to an entry (docs/testing.md).
"Tests" counts an entry's test references: those outside `tests/solver/`, then the solver probes,
which run only where the solver is installed. The table and its totals line are the output of
`python -m tests.support.spec_coverage ngspice`.

| Entry | Construct | Status | Tests | Validated on |
|---|---|---|---|---|
| [NG-ACA-001](./specs/NG-ACA-001.yaml) | .ac small-signal analysis | validated | 6 + 2 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-BEH-001](./specs/NG-BEH-001.yaml) | behavioral source (B) lines | validated | 6 + 2 solver | ngspice 47 (2026-11-06) |
| [NG-BJT-001](./specs/NG-BJT-001.yaml) | bipolar transistor (Q) lines | validated | 4 + 4 solver | ngspice 47 (2026-11-05) |
| [NG-CAP-001](./specs/NG-CAP-001.yaml) | capacitor (C) lines | validated | 5 + 3 solver | ngspice 47 (2026-10-30, 2026-10-31, 2026-11-06) |
| [NG-CCC-001](./specs/NG-CCC-001.yaml) | current-controlled current source (F) lines | validated | 2 + 3 solver | ngspice 47 (2026-11-06) |
| [NG-CCV-001](./specs/NG-CCV-001.yaml) | current-controlled voltage source (H) lines | validated | 2 + 3 solver | ngspice 47 (2026-11-06) |
| [NG-CNT-001](./specs/NG-CNT-001.yaml) | immediately adjacent continuation lines (+ and trailing \\) | validated | 7 + 5 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-COD-001](./specs/NG-COD-001.yaml) | code model (A) lines | validated | 11 + 4 solver | ngspice 47 (2026-11-10) |
| [NG-COM-001](./specs/NG-COM-001.yaml) | full-line star comments | validated | 3 + 2 solver | ngspice 47 (2026-10-30, 2026-10-31, 2026-11-11) |
| [NG-CPL-001](./specs/NG-CPL-001.yaml) | coupled transmission line (P) lines | validated | 5 + 4 solver | ngspice 47 (2026-11-09) |
| [NG-CTL-001](./specs/NG-CTL-001.yaml) | shared shape of the linear dependent sources and switches | validated | 4 + 1 solver | ngspice 47 (2026-11-06) |
| [NG-DCA-001](./specs/NG-DCA-001.yaml) | .dc transfer function | validated | 6 + 2 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-DIO-001](./specs/NG-DIO-001.yaml) | junction diode (D) lines | validated | 2 + 2 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-DIR-001](./specs/NG-DIR-001.yaml) | unknown dot-commands and stray block terminators | validated | 4 + 5 solver | ngspice 47 (2026-10-31) |
| [NG-END-001](./specs/NG-END-001.yaml) | required final .end statement | validated | 3 + 1 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-FLD-001](./specs/NG-FLD-001.yaml) | element field separators: blanks, one comma, = with blanks, continuation | validated | 6 + 1 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-FML-001](./specs/NG-FML-001.yaml) | Formula expression syntax (reference scan only) | validated | 10 + 2 solver | ngspice 47 (2026-10-31, 2026-11-10) |
| [NG-FUN-001](./specs/NG-FUN-001.yaml) | source functions, shared syntax | validated | 4 + 3 solver | ngspice 47 (2026-11-04) |
| [NG-FUN-002](./specs/NG-FUN-002.yaml) | PULSE | validated | 1 + 1 solver | ngspice 47 (2026-11-04) |
| [NG-FUN-003](./specs/NG-FUN-003.yaml) | SIN, and SINE | validated | 1 + 2 solver | ngspice 47 (2026-11-04) |
| [NG-FUN-004](./specs/NG-FUN-004.yaml) | EXP | validated | 1 + 1 solver | ngspice 47 (2026-11-04) |
| [NG-FUN-005](./specs/NG-FUN-005.yaml) | PWL with r= and td= | validated | 3 + 2 solver | ngspice 47 (2026-11-04) |
| [NG-FUN-006](./specs/NG-FUN-006.yaml) | SFFM | validated | 1 + 1 solver | ngspice 47 (2026-11-04) |
| [NG-FUN-007](./specs/NG-FUN-007.yaml) | AM | validated | 1 + 1 solver | ngspice 47 (2026-11-04) |
| [NG-FUN-008](./specs/NG-FUN-008.yaml) | TRNOISE | validated | 1 + 1 solver | ngspice 47 (2026-11-04) |
| [NG-FUN-009](./specs/NG-FUN-009.yaml) | TRRANDOM | validated | 1 + 1 solver | ngspice 47 (2026-11-04) |
| [NG-FUN-010](./specs/NG-FUN-010.yaml) | EXTERNAL | validated | 1 + 1 solver | ngspice 47 (2026-11-04) |
| [NG-FUN-011](./specs/NG-FUN-011.yaml) | DISTOF1 and DISTOF2 | validated | 1 + 2 solver | ngspice 47 (2026-11-04) |
| [NG-FUN-012](./specs/NG-FUN-012.yaml) | RF port parameters | validated | 2 + 1 solver | ngspice 47 (2026-11-04) |
| [NG-GLB-001](./specs/NG-GLB-001.yaml) | .global node declarations | validated | 4 + 1 solver | ngspice 47 (2026-10-31) |
| [NG-ICN-001](./specs/NG-ICN-001.yaml) | .ic and .nodeset | validated | 6 + 4 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-IND-001](./specs/NG-IND-001.yaml) | inductor (L) lines | validated | 3 + 1 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-JFT-001](./specs/NG-JFT-001.yaml) | junction FET (J) lines | validated | 2 + 2 solver | ngspice 47 (2026-11-05) |
| [NG-LTR-001](./specs/NG-LTR-001.yaml) | lossy transmission line (O) lines | validated | 4 + 3 solver | ngspice 47 (2026-11-09) |
| [NG-MEA-001](./specs/NG-MEA-001.yaml) | .meas / .measure (shallow) | validated | 6 + 2 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-MES-001](./specs/NG-MES-001.yaml) | MESFET (Z) lines | validated | 2 + 2 solver | ngspice 47 (2026-11-05) |
| [NG-MOD-001](./specs/NG-MOD-001.yaml) | .model statements | validated | 16 + 5 solver | ngspice 47 (2026-10-30, 2026-10-31, 2026-11-05, 2026-11-09, 2026-11-10) |
| [NG-MOS-001](./specs/NG-MOS-001.yaml) | MOSFET and VDMOS (M) lines | validated | 3 + 3 solver | ngspice 47 (2026-11-05) |
| [NG-MUT-001](./specs/NG-MUT-001.yaml) | mutual coupling (K) lines | validated | 2 + 1 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-NLS-001](./specs/NG-NLS-001.yaml) | expression forms of the dependent sources (E vol= and value, G cur= and value) | validated | 8 + 1 solver | ngspice 47 (2026-11-06) |
| [NG-NOD-001](./specs/NG-NOD-001.yaml) | node, model, subcircuit and parameter names | validated | 5 + 4 solver | ngspice 47 (2026-10-31) |
| [NG-NUM-001](./specs/NG-NUM-001.yaml) | numbers: sign, mantissa, exponent and scale factor | validated | 4 + 3 solver | ngspice 47 (2026-10-30, 2026-10-31, 2026-11-11) |
| [NG-NUM-002](./specs/NG-NUM-002.yaml) | letters following a number | validated | 1 + 1 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-NUM-003](./specs/NG-NUM-003.yaml) | RKM notation for R and C values (parser option rkm) | validated | 5 + 4 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-NUM-004](./specs/NG-NUM-004.yaml) | micro sign as a scale factor | observed | 2 + 1 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-OPA-001](./specs/NG-OPA-001.yaml) | opaque .control and nested .if blocks | validated | 4 + 3 solver | ngspice 47 (2026-10-22, 2026-10-31, 2026-11-11) |
| [NG-OPA-002](./specs/NG-OPA-002.yaml) | opaque .include and .lib statements, and .lib blocks | validated | 5 + 3 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-OPP-001](./specs/NG-OPP-001.yaml) | .op operating point | validated | 6 + 2 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-OPT-001](./specs/NG-OPT-001.yaml) | .options / .option | validated | 7 + 3 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-OSD-001](./specs/NG-OSD-001.yaml) | OSDI device (N) lines | validated | 5 + 4 solver | ngspice 47 (2026-11-10) |
| [NG-PAR-001](./specs/NG-PAR-001.yaml) | instance parameters, model references and the off flag | validated | 4 + 4 solver | ngspice 47 (2026-10-31) |
| [NG-PLY-001](./specs/NG-PLY-001.yaml) | POLY on E, F, G and H | validated | 10 + 3 solver | ngspice 47 (2026-11-08) |
| [NG-PRM-001](./specs/NG-PRM-001.yaml) | .param assignments | validated | 6 + 4 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-RES-001](./specs/NG-RES-001.yaml) | resistor (R) lines | validated | 4 + 2 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-SAV-001](./specs/NG-SAV-001.yaml) | .save output vectors | validated | 7 + 3 solver | ngspice 47 (2026-10-31) |
| [NG-SBD-001](./specs/NG-SBD-001.yaml) | .subckt ... .ends definitions and their bodies | validated | 13 + 5 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-SRC-001](./specs/NG-SRC-001.yaml) | independent sources (V, I): DC value and AC magnitude and phase | validated | 4 + 3 solver | ngspice 47 (2026-10-30, 2026-10-31, 2026-11-10) |
| [NG-STR-001](./specs/NG-STR-001.yaml) | top-level source structure | validated | 4 + 2 solver | ngspice 47 (2026-10-31) |
| [NG-SUB-001](./specs/NG-SUB-001.yaml) | subcircuit calls (X) | validated | 4 + 1 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-SWC-001](./specs/NG-SWC-001.yaml) | current-controlled switch (W) lines | validated | 2 + 2 solver | ngspice 47 (2026-11-06) |
| [NG-SWV-001](./specs/NG-SWV-001.yaml) | voltage-controlled switch (S) lines | validated | 3 + 3 solver | ngspice 47 (2026-11-06) |
| [NG-TBL-001](./specs/NG-TBL-001.yaml) | TABLE on E and G, and E's four-node TABLE | validated | 11 + 3 solver | ngspice 47 (2026-11-08) |
| [NG-TLL-001](./specs/NG-TLL-001.yaml) | lossless transmission line (T) lines | validated | 6 + 5 solver | ngspice 47 (2026-11-09) |
| [NG-TMP-001](./specs/NG-TMP-001.yaml) | .temp | validated | 6 + 2 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-TRN-001](./specs/NG-TRN-001.yaml) | .tran transient analysis | validated | 7 + 2 solver | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-TTL-001](./specs/NG-TTL-001.yaml) | implicit first-line title and explicit .title | validated | 1 + 1 solver | ngspice 47 (2026-10-22, 2026-10-31) |
| [NG-TXL-001](./specs/NG-TXL-001.yaml) | TXL transmission line (Y) lines | validated | 6 + 5 solver | ngspice 47 (2026-11-09) |
| [NG-TXT-001](./specs/NG-TXT-001.yaml) | free text, quoted and braced segments, and trailing comments | observed | 9 + 4 solver | ngspice 47 (2026-10-30, 2026-10-31, 2026-11-11) |
| [NG-UNS-001](./specs/NG-UNS-001.yaml) | refused element forms (params: on X, the digital U) | validated | 3 + 1 solver | ngspice 47 (2026-10-31) |
| [NG-URC-001](./specs/NG-URC-001.yaml) | uniform RC line (U) lines | validated | 3 + 4 solver | ngspice 47 (2026-11-09) |
| [NG-VAL-001](./specs/NG-VAL-001.yaml) | brace and quoted expressions, and string parameter values | validated | 6 + 4 solver | ngspice 47 (2026-10-31) |
| [NG-VCC-001](./specs/NG-VCC-001.yaml) | voltage-controlled current source (G) lines | validated | 2 + 3 solver | ngspice 47 (2026-11-06) |
| [NG-VCV-001](./specs/NG-VCV-001.yaml) | voltage-controlled voltage source (E) lines | validated | 2 + 3 solver | ngspice 47 (2026-11-06) |
| [NG-XSP-001](./specs/NG-XSP-001.yaml) | FREQ on E and G, and AND, OR, NAND and NOR on E | validated | 8 + 2 solver | ngspice 47 (2026-11-08) |
| [NG-XTR-001](./specs/NG-XTR-001.yaml) | shared transistor line shape (Q, M, J, Z) | validated | 6 + 3 solver | ngspice 47 (2026-11-05, 2026-11-11) |

75 entries: 73 validated, 2 observed, 0 disputed, 0 documented.

## Lookaround terminals

Lark's strict mode checks equal-priority collisions only for terminals interegular can model, so it
skips a terminal with a lookaround
([decision 0003](../../decisions/0003-grammar-composition-and-opaque-regions.md)).
`UNCHECKED_TERMINALS` in `tests/architecture/test_contracts.py` lists those terminals and fails
when the list changes. M18 reviewed each one by hand (A2, Lark 1.3.1): the parser states where it
is a candidate, the terminals that compete there, and why they cannot collide. `.N` is a
terminal's priority. None of them can drop its lookaround without changing what it matches.

**Fixed defect (A2-19, M18 D5):** after a nested `.endif`, 8 LALR-merged states offered
`BLOCK_TEXT` and `BLOCK_DOT_NAME` beside the statement-start terminals (`DOT_NAME`, the letter
names, `COMMENT_LINE`), which outrank them, so any line there but `.else` was a `ParseError`. A
nested `.if` is now its own rule (`nested_if_block`), so those states no longer merge, and
`test_no_lexer_state_offers_a_block_line_and_a_statement_start` checks that no state of either
dialect offers a block line's terminal beside a statement's first terminal. The counts below are
after the fix.

| Terminal | Matches | Candidate in | Competitors | Why no collision |
|---|---|---|---|---|
| `BLOCK_TEXT.2` | a non-blank, then text to the end of the line; a lone CR is text | 72 states: the lines of `.control`, `.if` and `.lib` blocks, and the text after a block opener or closer | `BLOCK_DOT_NAME`, `ENDC_KW`, `ENDIF_KW`, `ENDL_KW`, `IF_KW` (4); `NL`, `LINE_END`, `CONT`, `WS` | No competitor at its priority: it is the fallback, and every competitor outranks it. No state offers it beside a statement start (A2-19). |
| `BS_CONT.7` | `\` and a line end, when the next line starts with statement text | 1642 states: every field of a continuable statement | `CONT` (7); above: `SEP`, `CSEP`, `EQ`, `IC_COMMA`, `WS`; below: every field terminal | `CONT` starts with a line end and `BS_CONT` with `\`. `TEXT` stops before a `\` that ends the line. |
| `B_PIECE.4` | a piece of a bare B, E or G expression, stopping before `name=`, a comment, or a lone braced or quoted value | 28 states: after the output nodes of B, E and G | above: `OPEN_FORMULA.5`, `SEP`, `CSEP`, `EQ`, `NL`, `CONT`, `BS_CONT`; below: `BRACE_FORMULA`, `QUOTE_FORMULA`, `B_PARAM_KW`, `B_QUANTITY_KW`, `TRAILING_COMMENT` | No competitor at its priority. Its lookaheads refuse to start where a keyword, `name=` or a lone formula belongs, so the lower terminals keep those. |
| `COMMENT_LINE.3` | `*` to the end of the line | 568 states: line starts | the letter names, the dot keywords, `DOT_NAME`, `LIB_BLOCK_KW`, `TITLE_KW`, `LINE_END` | No competitor at its priority; no name or keyword starts with `*`. |
| `DOT_NAME.4` | `.name`, except `.endc`, `.endif`, `.else`, `.elseif` and `.ends` | 568 states: line starts | at 4: the dot keywords (string terminals) and the letter names; above: `LIB_BLOCK_KW`, `TITLE_KW` | Lark re-types an exact keyword match (rule 12). `ENDS_KW` and `ENDIF_KW` take what `DOT_NAME` refuses. Letter names start with a letter. `BLOCK_DOT_NAME` has the same language and is never a candidate in the same state (A2-19). |
| `LIB_BLOCK_KW.5` | `.lib`, when a one-field `.lib` line is followed by `.endl` before the next one-field `.lib` or `.end` | 568 states: line starts | `LIB_KW.4` (`.lib`), the other dot keywords | No competitor at its priority. It outranks `LIB_KW` only where its lookahead holds; elsewhere `LIB_KW` takes the text. |
| `TEXT.2` | statement text up to `;`, `$`, `//`, a quote, or a `\` that ends the line | 101 states: the text of untyped statements and `line_rest` | `QUOTED`, `TRAILING_COMMENT`, `BS_CONT`, `SEP`, `CSEP`, `NL`, `LINE_END`, `CONT` | No competitor at its priority. It cannot start on a blank, a quote or a comment marker, and a comma that starts a token is `CSEP`. |
| `TITLE_ARG.3` | a non-blank, then text to the end of the line | 2 states: after `.title` | `WS`, `LINE_END`, `CONT` | No text terminal competes. |
| `TITLE_TEXT.2` | any text to the end of the line | 1 state: the first line | `TITLE_KW.6`, `WS`, `LINE_END`, `CONT` | Only `.title` outranks it, on purpose. |
| `TRAILING_COMMENT.3` | `;`, `$` or `//` to the end of the line | 1649 states: after any field | 32 at its priority (`NUMBER`, `QUOTED`, `BRACE_FORMULA`, `QUOTE_FORMULA`, the `*_KW` lookahead keywords, `VOLTAGE_OPEN`, `CURRENT_OPEN`, `A_TYPE`, `A_NOT` …) | Disjoint by first character: none of the 32 starts with `;`, `$` or `/`. |

Method: patterns and per-state terminals from `build_parser(dialect).parser.lexer.lexers`; each
competitor at the same priority was checked with interegular against the pattern with its
lookarounds removed (a superset of what it matches).
