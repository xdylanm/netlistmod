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
| C, L | [ELEMENTS] C, L | value, formula | closed lists; `Q=`, `Flux=`, `Hc=` unsupported |
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
reference does not mention is marked observed in the entry's notes (§11.3 rule 3).

| Entry | Construct | Status | Validated on |
|---|---|---|---|
| [LT-ACA-001](./specs/LT-ACA-001.yaml) | .ac | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-CAP-001](./specs/LT-CAP-001.yaml) | capacitor (C) lines | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-CNT-001](./specs/LT-CNT-001.yaml) | + continuation lines | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-COM-001](./specs/LT-COM-001.yaml) | comment lines (* and ;) | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-COM-002](./specs/LT-COM-002.yaml) | end-of-line comments (; and space-$-space) | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-DCA-001](./specs/LT-DCA-001.yaml) | .dc | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-DIO-001](./specs/LT-DIO-001.yaml) | diode (D) lines | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-DIR-001](./specs/LT-DIR-001.yaml) | closed list of dot-commands | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-END-001](./specs/LT-END-001.yaml) | required final .end | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-FLD-001](./specs/LT-FLD-001.yaml) | field separators | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-FML-001](./specs/LT-FML-001.yaml) | formula expression syntax (reference scan only) | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-GLB-001](./specs/LT-GLB-001.yaml) | .global | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-ICN-001](./specs/LT-ICN-001.yaml) | .ic and .nodeset | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-IND-001](./specs/LT-IND-001.yaml) | inductor (L) lines | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-MCH-001](./specs/LT-MCH-001.yaml) | .machine blocks | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-MEA-001](./specs/LT-MEA-001.yaml) | .meas and .measure | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-MOD-001](./specs/LT-MOD-001.yaml) | .model statements | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-MUT-001](./specs/LT-MUT-001.yaml) | mutual inductance (K) lines | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-NOD-001](./specs/LT-NOD-001.yaml) | node, element and subcircuit names | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-NUM-001](./specs/LT-NUM-001.yaml) | numbers | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-NUM-002](./specs/LT-NUM-002.yaml) | letters following a number | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-NUM-003](./specs/LT-NUM-003.yaml) | embedded decimal | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-NUM-004](./specs/LT-NUM-004.yaml) | micro signs | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-OPA-001](./specs/LT-OPA-001.yaml) | opaque .include, .inc and .lib, and .lib blocks | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-OPP-001](./specs/LT-OPP-001.yaml) | .op | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-OPT-001](./specs/LT-OPT-001.yaml) | .options, .option and .opt | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-PRM-001](./specs/LT-PRM-001.yaml) | .param assignments | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-RES-001](./specs/LT-RES-001.yaml) | resistor (R) lines | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-SAV-001](./specs/LT-SAV-001.yaml) | .save | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-SBD-001](./specs/LT-SBD-001.yaml) | .subckt ... .ends definitions | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-SRC-001](./specs/LT-SRC-001.yaml) | independent sources (V, I) | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-FUN-001](./specs/LT-FUN-001.yaml) | source functions, shared syntax | validated | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-002](./specs/LT-FUN-002.yaml) | PULSE | validated | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-003](./specs/LT-FUN-003.yaml) | SINE and SIN | validated | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-004](./specs/LT-FUN-004.yaml) | EXP | validated | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-005](./specs/LT-FUN-005.yaml) | SFFM | validated | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-006](./specs/LT-FUN-006.yaml) | PWL with its scale factors and file | validated | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-007](./specs/LT-FUN-007.yaml) | PWL REPEAT | validated | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-008](./specs/LT-FUN-008.yaml) | wave file | validated | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-009](./specs/LT-FUN-009.yaml) | I table | validated | ltspice 26.1.1 (2026-11-04) |
| [LT-FUN-010](./specs/LT-FUN-010.yaml) | I step load | validated | ltspice 26.1.1 (2026-11-04) |
| [LT-STP-001](./specs/LT-STP-001.yaml) | .step | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-STR-001](./specs/LT-STR-001.yaml) | top-level source structure | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-SUB-001](./specs/LT-SUB-001.yaml) | subcircuit calls (X) | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-TMP-001](./specs/LT-TMP-001.yaml) | .temp | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-TRN-001](./specs/LT-TRN-001.yaml) | .tran | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-TTL-001](./specs/LT-TTL-001.yaml) | implicit first-line title and .title | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-TXT-001](./specs/LT-TXT-001.yaml) | statement text | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-UNS-001](./specs/LT-UNS-001.yaml) | recognised but unsupported forms | validated | ltspice 26.1.1 (2026-11-01) |
| [LT-VAL-001](./specs/LT-VAL-001.yaml) | brace and quoted expressions | validated | ltspice 26.1.1 (2026-11-01) |
