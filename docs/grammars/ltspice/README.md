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
the entries. Every entry is `documented` until T12 (checkpoint B) adds its solver test.

| Entry | Construct | Status | Validated on |
|---|---|---|---|
| [LT-ACA-001](./specs/LT-ACA-001.yaml) | .ac | documented |  |
| [LT-CAP-001](./specs/LT-CAP-001.yaml) | capacitor (C) lines | documented |  |
| [LT-CNT-001](./specs/LT-CNT-001.yaml) | + continuation lines | documented |  |
| [LT-COM-001](./specs/LT-COM-001.yaml) | comment lines (* and ;) | documented |  |
| [LT-COM-002](./specs/LT-COM-002.yaml) | end-of-line comments (; and space-$-space) | documented |  |
| [LT-DCA-001](./specs/LT-DCA-001.yaml) | .dc | documented |  |
| [LT-DIO-001](./specs/LT-DIO-001.yaml) | diode (D) lines | documented |  |
| [LT-DIR-001](./specs/LT-DIR-001.yaml) | closed list of dot-commands | documented |  |
| [LT-END-001](./specs/LT-END-001.yaml) | required final .end | documented |  |
| [LT-FLD-001](./specs/LT-FLD-001.yaml) | field separators | documented |  |
| [LT-FML-001](./specs/LT-FML-001.yaml) | formula expression syntax (reference scan only) | documented |  |
| [LT-GLB-001](./specs/LT-GLB-001.yaml) | .global | documented |  |
| [LT-ICN-001](./specs/LT-ICN-001.yaml) | .ic and .nodeset | documented |  |
| [LT-IND-001](./specs/LT-IND-001.yaml) | inductor (L) lines | documented |  |
| [LT-MCH-001](./specs/LT-MCH-001.yaml) | .machine blocks | documented |  |
| [LT-MEA-001](./specs/LT-MEA-001.yaml) | .meas and .measure | documented |  |
| [LT-MOD-001](./specs/LT-MOD-001.yaml) | .model statements | documented |  |
| [LT-MUT-001](./specs/LT-MUT-001.yaml) | mutual inductance (K) lines | documented |  |
| [LT-NOD-001](./specs/LT-NOD-001.yaml) | node, element and subcircuit names | documented |  |
| [LT-NUM-001](./specs/LT-NUM-001.yaml) | numbers | documented |  |
| [LT-NUM-002](./specs/LT-NUM-002.yaml) | letters following a number | documented |  |
| [LT-NUM-003](./specs/LT-NUM-003.yaml) | embedded decimal | documented |  |
| [LT-NUM-004](./specs/LT-NUM-004.yaml) | micro signs | documented |  |
| [LT-OPA-001](./specs/LT-OPA-001.yaml) | opaque .include, .inc and .lib | documented |  |
| [LT-OPP-001](./specs/LT-OPP-001.yaml) | .op | documented |  |
| [LT-OPT-001](./specs/LT-OPT-001.yaml) | .options, .option and .opt | documented |  |
| [LT-PRM-001](./specs/LT-PRM-001.yaml) | .param assignments | documented |  |
| [LT-RES-001](./specs/LT-RES-001.yaml) | resistor (R) lines | documented |  |
| [LT-SAV-001](./specs/LT-SAV-001.yaml) | .save | documented |  |
| [LT-SBD-001](./specs/LT-SBD-001.yaml) | .subckt ... .ends definitions | documented |  |
| [LT-SRC-001](./specs/LT-SRC-001.yaml) | independent sources (V, I) | documented |  |
| [LT-STP-001](./specs/LT-STP-001.yaml) | .step | documented |  |
| [LT-STR-001](./specs/LT-STR-001.yaml) | top-level source structure | documented |  |
| [LT-SUB-001](./specs/LT-SUB-001.yaml) | subcircuit calls (X) | documented |  |
| [LT-TMP-001](./specs/LT-TMP-001.yaml) | .temp | documented |  |
| [LT-TRN-001](./specs/LT-TRN-001.yaml) | .tran | documented |  |
| [LT-TTL-001](./specs/LT-TTL-001.yaml) | implicit first-line title and .title | documented |  |
| [LT-TXT-001](./specs/LT-TXT-001.yaml) | statement text | documented |  |
| [LT-UNS-001](./specs/LT-UNS-001.yaml) | recognised but unsupported forms | documented |  |
| [LT-VAL-001](./specs/LT-VAL-001.yaml) | brace and quoted expressions | documented |  |
