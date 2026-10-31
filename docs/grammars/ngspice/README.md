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

| Entry | Construct | Status | Validated on |
|---|---|---|---|
| [NG-ACA-001](./specs/NG-ACA-001.yaml) | .ac small-signal analysis | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-CAP-001](./specs/NG-CAP-001.yaml) | capacitor (C) lines | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-CNT-001](./specs/NG-CNT-001.yaml) | immediately adjacent continuation lines (+ and trailing \\) | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-COM-001](./specs/NG-COM-001.yaml) | full-line star comments | observed | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-DCA-001](./specs/NG-DCA-001.yaml) | .dc transfer function | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-DIO-001](./specs/NG-DIO-001.yaml) | junction diode (D) lines | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-DIR-001](./specs/NG-DIR-001.yaml) | unknown dot-commands and stray block terminators | validated | ngspice 47 (2026-10-31) |
| [NG-END-001](./specs/NG-END-001.yaml) | required final .end statement | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-FLD-001](./specs/NG-FLD-001.yaml) | element field separators: blanks, one comma, = with blanks, continuation | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-FML-001](./specs/NG-FML-001.yaml) | Formula expression syntax (reference scan only) | validated | ngspice 47 (2026-10-31) |
| [NG-GLB-001](./specs/NG-GLB-001.yaml) | .global node declarations | validated | ngspice 47 (2026-10-31) |
| [NG-ICN-001](./specs/NG-ICN-001.yaml) | .ic and .nodeset | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-IND-001](./specs/NG-IND-001.yaml) | inductor (L) lines | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-MEA-001](./specs/NG-MEA-001.yaml) | .meas / .measure (shallow) | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-MOD-001](./specs/NG-MOD-001.yaml) | .model statements | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-MUT-001](./specs/NG-MUT-001.yaml) | mutual coupling (K) lines | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-NOD-001](./specs/NG-NOD-001.yaml) | node, model, subcircuit and parameter names | validated | ngspice 47 (2026-10-31) |
| [NG-NUM-001](./specs/NG-NUM-001.yaml) | numbers: sign, mantissa, exponent and scale factor | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-NUM-002](./specs/NG-NUM-002.yaml) | letters following a number | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-NUM-003](./specs/NG-NUM-003.yaml) | RKM notation for R and C values (parser option rkm) | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-NUM-004](./specs/NG-NUM-004.yaml) | micro sign as a scale factor | observed | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-OPA-001](./specs/NG-OPA-001.yaml) | opaque .control and nested .if blocks | validated | ngspice 47 (2026-10-22, 2026-10-31) |
| [NG-OPA-002](./specs/NG-OPA-002.yaml) | opaque .include and .lib statements | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-OPP-001](./specs/NG-OPP-001.yaml) | .op operating point | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-OPT-001](./specs/NG-OPT-001.yaml) | .options / .option | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-PAR-001](./specs/NG-PAR-001.yaml) | instance parameters, model references and the off flag | validated | ngspice 47 (2026-10-31) |
| [NG-PRM-001](./specs/NG-PRM-001.yaml) | .param assignments | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-RES-001](./specs/NG-RES-001.yaml) | resistor (R) lines | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-SAV-001](./specs/NG-SAV-001.yaml) | .save output vectors | validated | ngspice 47 (2026-10-31) |
| [NG-SBD-001](./specs/NG-SBD-001.yaml) | .subckt ... .ends definitions and their bodies | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-SRC-001](./specs/NG-SRC-001.yaml) | independent sources (V, I): DC value and AC magnitude and phase | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-STR-001](./specs/NG-STR-001.yaml) | top-level source structure | validated | ngspice 47 (2026-10-31) |
| [NG-SUB-001](./specs/NG-SUB-001.yaml) | subcircuit calls (X) | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-TMP-001](./specs/NG-TMP-001.yaml) | .temp | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-TRN-001](./specs/NG-TRN-001.yaml) | .tran transient analysis | validated | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-TTL-001](./specs/NG-TTL-001.yaml) | implicit first-line title and explicit .title | validated | ngspice 47 (2026-10-22, 2026-10-31) |
| [NG-TXT-001](./specs/NG-TXT-001.yaml) | free text, quoted and braced segments, and trailing comments | observed | ngspice 47 (2026-10-30, 2026-10-31) |
| [NG-UNS-001](./specs/NG-UNS-001.yaml) | recognised but unsupported element forms | validated | ngspice 47 (2026-10-31) |
| [NG-VAL-001](./specs/NG-VAL-001.yaml) | brace and quoted expressions, and string parameter values | validated | ngspice 47 (2026-10-31) |
