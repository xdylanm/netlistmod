# LTspice reference, solver and library discrepancies

The library follows the reference, with the exceptions of
[decision 0009](../../decisions/0009-ltspice-dialect.md). This file records what LTspice 26.1.1
(Windows, probed by hand on 2026-10-31 and 2026-11-01) does where the library differs from it, or
where the library differs from the reference. Only syntax facts are recorded (decision 0009 item 2).
T12 (checkpoint B) ties each row to a solver test; until then the evidence column names the library
test that pins the library's side.

## Exceptions to the reference

| LTspice and the reference | Library behaviour | Evidence |
|---|---|---|
| `.end` may be omitted, and text after it is ignored (L10, L19). | `ParseError`: `.end` is required, with only blank lines after it. A deliberate exception (decision 0009 item 4), to revisit after the phase 1 review. | `test_end_is_required_with_only_blank_lines_after_it` |
| An expression may stand for a node (`I1 {CONNECT} 0 2m`) or a subcircuit name (`X1 a b {name}`). | `ParseError`: the node list would not be known text, against the topology guarantee (P4). | `test_malformed_subcircuit_calls`; `names_rejects/name_with_brace.cir` |
| `.step ... list`, `.dc ... list` and `.ac list` take comma-separated values. | Values are separated by blanks; a comma is a `ParseError`. | `test_malformed_ac`; `test_malformed_step` |
| `I` has `tbl=` and `step(...)`; `C` has `Q=`; `L` has `Flux=` and the hysteretic form; V and I have source functions; `.machine`. | `UnsupportedConstruct` in phase 1. | `test_source_functions_are_unsupported`; `test_nonlinear_forms_are_unsupported`; `test_machine_block_is_unsupported` |

## Forms LTspice runs and the library rejects

None of these is in the reference.

| LTspice 26.1.1 | Library behaviour | Evidence |
|---|---|---|
| Joins a `+` line across comment and blank lines. | The `+` line must follow immediately (`LT-CNT-001`). | `test_continuation_must_follow_immediately` |
| Runs `.print`, `.plot` and `.width`. | `ParseError`: not on the closed list (`LT-DIR-001`). | `test_other_dot_commands_are_errors` |
| Accepts `.opti` (a prefix of `.options`). | `ParseError`. | `test_malformed_options` |
| Runs an empty `.options`, `.ic`, `.nodeset`, `.save` and `.global`, and `.meas op`, `.meas op y` and `.meas tran`. | `ParseError`: each form has at least one item (`LT-OPT-001`, `LT-ICN-001`, `LT-SAV-001`, `LT-GLB-001`, `LT-MEA-001`). | `test_malformed_options`; `test_malformed_initial_conditions`; `test_malformed_save`; `test_global_and_title`; `test_malformed_meas` |
| Runs `.ic I(R1)=1` and `.ic I(L9)=1` and ignores them; sets a current through `.ic I(x1:L1)=1`; accepts `.nodeset I(L1)=1` and `.ic V(a,b)=1`. | `.ic I(L...)` is accepted (the reference documents inductor currents, `LT-ICN-001`). `I(R1)`, a hierarchical name, `.nodeset I(...)` and `V(a,b)` are a `ParseError`. A name no element has, `I(L9)`, gets `UNRESOLVED_ELEMENT`. | `test_malformed_initial_conditions`; `test_inductor_currents_in_ic`; `test_an_ic_current_is_indexed_like_a_saved_current` |
| Accepts `.ic` and `.nodeset` in a subcircuit body. | `ParseError`: top level only. | `test_top_level_statements_are_rejected_in_a_body` |
| Accepts `.save dialogbox`. | `ParseError`. | `test_malformed_save` |
| Reads `1k$c` as 1k, `2.2k2` as 2.4k, `1.5k5` as 2k, `1e3k2` as 1 Meg, and `1x5`, `1a5`, `1l5`, `1kohm5`, `1V5` without the digits. | `ParseError` (`LT-NUM-002`). | `test_digits_after_other_letters_are_rejected` |
| Accepts names outside the closed lists: `tc` on C, `m` on V, and `ic=` on D, which runs but shows no effect on a `.tran ... uic` result. | `ParseError`. The lists hold the reference's names and the names verified by probe (`LT-RES-001`, `LT-CAP-001`, `LT-IND-001`, `LT-DIO-001`; reviews R1, R10). | `test_the_lists_stay_closed`; `test_malformed_resistor_lines`; `test_other_parameters_are_rejected`; `test_malformed_voltage_sources`; `test_malformed_diodes`; `test_malformed_current_sources` |
| Accepts `mfg='abc'` and `mfg={abc}` on an element or a `.model`. | `ParseError`: `mfg`, `pn` and `type` take a double-quoted string or a bare word. | `test_the_lists_stay_closed`; `test_text_values_and_numeric_values_do_not_mix` |
| Accepts keyword values: `R=1k`, `inductance=1m` (not `resistance=`, `C=`, `capacitance=` or `L=`). | `ParseError`: no keyword form. | `test_keyword_values_are_not_ltspice_forms` |
| Reads a bare word or expression as a parameter reference in `R=x*2`, `m=x`, `X1 a b s r=2*1k`, `.subckt s a r=2*1k`, and `.model ... Is=x` or `Is=1n*2`. | `ParseError`: bare expressions only in `.param`. On a `.model` the message suggests `{x}`; only `mfg` and `type` take a bare word (review R8). | `test_malformed_subcircuit_calls`; `test_other_model_parameters_reject_a_bare_word` |
| Accepts `V1 a 0 DC=3`, `AC 1 DC 3`, `Rser=1 AC 1` and `I1 a 0 1 load AC 1`. | `ParseError`: the reference's order. | `test_malformed_voltage_sources`; `test_malformed_current_sources` |
| Accepts `tc=1m 1u` (no comma). | `ParseError`. | `test_malformed_resistor_lines` |
| Accepts commas in `m=2, temp=3`, `AC 1, 2`, `.subckt s a,b` and `.ac list 1,2`. | `ParseError`. | `test_malformed_ac` |
| Accepts `.dc V1 list 1 2 V2 1 2 1` (a list before another sweep). | `ParseError`: a list is the last sweep, since its values are not delimited for the LALR parser. | `test_malformed_dc` |
| Accepts `.dc V1 0 1` and `.step param x 1 2` (no increment). | `ParseError`: the reference has four fields. | `test_malformed_dc`; `test_malformed_step` |
| Accepts `{{x}}` and `.param a$b=1`. | `ParseError`. | `numbers.md` |
| Accepts a port named `0`. | `ParseError`, as for ngspice. | `test_a_port_cannot_be_zero` |
| Reads BOM-less UTF-16LE and Latin-1 by itself (reference, Text Encoding). | BOM-less UTF-16LE is not detected, because it needs a heuristic (P5): the caller decodes it and names the encoding. Bytes that are not UTF-8 are tried as `cp1252` before Latin-1; the two differ on 0x80–0x9F (decision 0001). | `test_encodings_round_trip` |

## Forms the library accepts and LTspice rejects

Syntax the library cannot judge from the netlist's form, or chooses not to.

| LTspice 26.1.1 | Library behaviour | Evidence |
|---|---|---|
| Stops at an unknown option name (`.options foo=1`). | Accepted: option names are not checked, because the reference's list is partial and an option is not topology (settled in T4, `LT-OPT-001`). | `test_options` |
| Stops at a UTF-16 big-endian file. | Accepted: the source layer is dialect-neutral (decision 0001). | `tests/test_source.py` |
| Stops at `.step x 1 2 1` ("Can't sweep that") and at `.dc R1 ...` (only independent sources). | Accepted as syntax: the source is any name. A name no element has gets `UNRESOLVED_ELEMENT`. | `test_a_step_refers_to_its_source_and_model` |
| Stops at repeated definitions, a repeated designator, an undefined model or subcircuit and a port count mismatch. | Diagnostics, not errors (`scoping.md`). | `tests/document/test_ltspice_document.py` |
| Fails on a shallow `.meas` body it cannot read (`.meas sp y param 1`). | The body is text; `sp` reads as the result name. | `test_meas` |

## Settled while implementing

- **K with three inductors** is valid: three and four inductors run when each has its own load.
  Probe L13's circuit is not recorded. A circuit with two ideal inductors in parallel reproduces its
  symptom (exit 1 with no error line), which suggests an inductor loop, but that cause is an inference.
- **`$`** is a comment only as space, `$`, space; a tab on either side does not count. `$G_x`, `a$b`
  and `a$` are names, and a `$` line is an error.
- **`//`** is not a comment in LTspice: `1k // c` fails and `.include sub//h.inc` is a path.
- **Nested `.step`:** four run, and the reference states no limit, so a fourth is not refused. Sweeping
  the same quantity twice stops LTspice.
- **No R, C or L model:** `.model rm R` then `R1 a b rm` exits 1, and `R1 a b 1k rm` stops at "Unknown
  parameter"; the reference lists no such type.
- **Comma forms** are minimal: `tc` values (documented) and, observed, `.model` and `X` parameters,
  `.param` assignments, `.options` items and `.save` vectors.
