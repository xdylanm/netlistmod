# LTspice reference, solver and library discrepancies

The library follows the reference, with the exceptions of
[decision 0009](../../decisions/0009-ltspice-dialect.md). This file records what LTspice 26.1.1
(Windows) does where the library differs from it, or where the library differs from the reference.
Only syntax facts are recorded (decision 0009 item 2). The evidence column names the solver test that
pairs LTspice's side with the library's, in `tests/solver/test_ltspice_discrepancies.py` unless noted,
and then the library test that pins the library's side.

## Forms LTspice reads differently, flagged

| LTspice 26.1.1 | Library behaviour | Evidence |
|---|---|---|
| A node named `<instance>:<node>` is connected to that node inside the instance (`names.md` N11). Undocumented, and no export writes it. | A separate net, so the topology view is wrong for it. `NODE_INTO_INSTANCE` says so. A known limit (architecture §7.8). | `tests/solver/test_ltspice_solver_document.py::test_a_node_into_an_instance_is_joined_and_flagged`; `test_other_names_with_a_colon_are_ordinary_nodes` |
| Runs an F, H or W controlled by an E, an H or an L; the reference names a voltage source. | Loads, with `CONTROL_SOURCE_MISMATCH` (decision 0015 item 5). | `tests/solver/test_ltspice_controlled_probes.py::test_controlled_source_probes` (`f-ctrl-e`, `f-ctrl-h`, `f-ctrl-l`) |
| Runs `F1 0 out X1:Vq 2`, controlled by a source inside instance `X1`. | Keeps the name as text and reports `UNRESOLVED_ELEMENT` as info; the controlling source is not resolved (a known limit, architecture §7.8; decision 0015 item 4). | `tests/solver/test_ltspice_controlled_probes.py::test_controlled_source_probes` (`f-into-instance`); `controlled_sources/lt_test_hsource_ctrl_into_instance.cir` |

## Exceptions to the reference

| LTspice and the reference | Library behaviour | Evidence |
|---|---|---|
| `.end` may be omitted, and text after it is ignored (L10, L19). | `ParseError`: `.end` is required, with only blank lines after it. A deliberate exception (decision 0009 item 4), to revisit after the phase 1 review. | `test_end_may_be_omitted_and_text_after_it_is_ignored`; `test_end_is_required_with_only_blank_lines_after_it` |
| An expression may stand for a node (`I1 {CONNECT} 0 2m`) or a subcircuit name (`X1 a b {name}`). | `ParseError`: the node list would not be known text, against the topology guarantee (P4). | `test_an_expression_for_a_node_runs_but_the_library_rejects_it`; `test_malformed_subcircuit_calls`; `names_rejects/name_with_brace.cir` |
| `.step ... list`, `.dc ... list` and `.ac list` take comma-separated values. | Values are separated by blanks; a comma is a `ParseError`. | `test_comma_lists_in_step_run_but_the_library_rejects_them`; `test_comma_lists_in_dc_and_ac_run_but_the_library_rejects_them`; `test_malformed_ac`; `test_malformed_step` |
| `C` has `Q=`; `L` has `Flux=` and the hysteretic form; `.machine`. | `UnsupportedConstruct` in phase 1. | `tests/solver/test_ltspice_validation.py::test_other_forms_run_and_are_unsupported`; `test_a_state_machine_runs_and_is_unsupported`; `test_nonlinear_forms_are_unsupported`; `test_machine_block_is_unsupported` |

## Forms in the reference that LTspice stops on

The library follows the reference, so these load.

| LTspice 26.1.1 | Library behaviour | Evidence |
|---|---|---|
| `I1 a 0 PULSE(…) Trigger=V(a)>0.5` and `tripdv=1m` stop with "Unknown parameter", while the same text runs on V. The reference says all time-dependent sources support a trigger. | Accepted. | `test_a_trigger_on_an_i_line_stops_ltspice` |

## Forms LTspice runs and the library rejects

None of these is in the reference. `test_every_reject_fixture_is_classified` also sweeps every fixture
of the `*_rejects` families.

| LTspice 26.1.1 | Library behaviour | Evidence |
|---|---|---|
| `PULSE 0 1 1u`, with no parentheses, runs. | `ParseError`: the reference writes them (decision 0013). | `test_forms_that_run_and_the_library_refuses` |
| `PWL(file=x.txt)` runs. | `ParseError`: the reference writes `PWL FILE=`. | `test_forms_that_run_and_the_library_refuses` |
| `PULSE(…) m=2` runs. | `ParseError`: the reference gives V no `m`. | `test_forms_that_run_and_the_library_refuses` |
| Two `REPEAT` blocks in a row run. | `ParseError`: the reference shows one. | `test_forms_that_the_reference_does_not_show_are_refused` |
| `I1 a 0 load PULSE(…)`, `I1 a 0 1 load PULSE(…)` and `I1 a 0 load DC 1 PULSE(…)` run. | `ParseError`: the reference writes `load` after the value, and M12 allows it after a function. | `test_forms_outside_the_reference_that_run_and_the_library_refuses` |
| `I1 a 0 1 tbl=(0 0, 1 1)`, `I1 a 0 AC 1 tbl=(…)`, `I1 a 0 tbl=(…) DC 1`, `I1 a 0 tbl=(…) AC 1` and `I1 a 0 tbl=(…) load` run. | `ParseError`: the reference writes `tbl=` alone. | `test_forms_outside_the_reference_that_run_and_the_library_refuses` |
| `Trigger=V(a) > 0.5`, with blanks, runs. | `ParseError`: a blank ends the field, so the library cannot tell where the expression stops. Write it without blanks. | `test_forms_outside_the_reference_that_run_and_the_library_refuses` |
| Joins a `+` line across comment and blank lines. | The `+` line must follow immediately (`LT-CNT-001`). | `test_a_continuation_across_other_lines_runs_but_the_library_rejects_it`; `test_continuation_must_follow_immediately` |
| Runs `.print`, `.plot` and `.width`. | `ParseError`: not on the closed list (`LT-DIR-001`). | `test_undocumented_commands_run_but_the_library_rejects_them`; `test_other_dot_commands_are_errors` |
| Accepts `.opti` (a prefix of `.options`). | `ParseError`. | `test_undocumented_commands_run_but_the_library_rejects_them`; `test_malformed_options` |
| Runs an empty `.options`, `.ic`, `.nodeset`, `.save` and `.global`, and `.meas op`, `.meas op y` and `.meas tran`. | `ParseError`: each form has at least one item (`LT-OPT-001`, `LT-ICN-001`, `LT-SAV-001`, `LT-GLB-001`, `LT-MEA-001`). | `test_undocumented_commands_run_but_the_library_rejects_them`; `test_malformed_options`; `test_malformed_initial_conditions`; `test_malformed_save`; `test_global_and_title`; `test_malformed_meas` |
| Runs `.ic I(R1)=1` and `.ic I(L9)=1` and ignores them; sets a current through `.ic I(x1:L1)=1`; accepts `.nodeset I(L1)=1` and `.ic V(a,b)=1`. | `.ic I(L...)` is accepted (the reference documents inductor currents, `LT-ICN-001`). `I(R1)`, a hierarchical name, `.nodeset I(...)` and `V(a,b)` are a `ParseError`. A name no element has, `I(L9)`, gets `UNRESOLVED_ELEMENT`. | `test_other_initial_conditions_run_but_the_library_rejects_them`; `test_an_ic_current_on_a_resistor_is_ignored`; `test_an_ic_current_of_no_element_runs_and_is_diagnosed`; `test_an_ic_current_inside_an_instance_is_set_but_the_library_rejects_it`; `test_malformed_initial_conditions`; `test_inductor_currents_in_ic`; `test_an_ic_current_is_indexed_like_a_saved_current` |
| Accepts `.ic` and `.nodeset` in a subcircuit body. | `ParseError`: top level only. | `test_conditions_in_a_body_run_but_the_library_rejects_them`; `test_top_level_statements_are_rejected_in_a_body` |
| Accepts `.save dialogbox`. | `ParseError`. | `test_undocumented_commands_run_but_the_library_rejects_them`; `test_malformed_save` |
| Reads `1k$c` as 1k, `2.2k2` as 2.4k, `1.5k5` as 2k, `1e3k2` as 1.0002 Meg, and `1x5`, `1a5`, `1l5`, `1kohm5`, `1V5` without the digits. | `ParseError` (`LT-NUM-002`). | `test_other_digits_after_letters_read_oddly_and_the_library_rejects_them`; `test_digits_after_other_letters_are_rejected` |
| Accepts names outside the closed lists: `tc` on C, `m` on V, and `ic=` on D, which runs but shows no effect on a `.tran ... uic` result. | `ParseError`. The lists hold the reference's names and the names verified by probe (`LT-RES-001`, `LT-CAP-001`, `LT-IND-001`, `LT-DIO-001`; reviews R1, R10). | `test_names_outside_the_closed_lists_run_but_the_library_rejects_them`; `test_the_lists_stay_closed`; `test_malformed_resistor_lines`; `test_other_parameters_are_rejected`; `test_malformed_voltage_sources`; `test_malformed_diodes`; `test_malformed_current_sources` |
| Runs `.model 2 NPN` with `Q1 c b e 2`, a model named with a plain number. | `ParseError`: a number in the model's place is refused, and is read as an area where one may stand (decision 0014 item 4). | `tests/solver/test_ltspice_transistor_probes.py::test_transistor_probes` (`q-number-model`) |
| Runs `area=` on Q, and `area=`, `m=` and `ic=` on J, outside the reference's lists. | `ParseError`: Q takes `temp`, J `temp`, Z `m` and `temp`, M `L W AD AS PD PS NRD NRS m temp IC`, and `off` on all (decision 0014 item 6). | `test_malformed_transistor_lines_are_rejected`; `tests/solver/test_ltspice_transistor_probes.py::test_transistor_probes` (`j-area-param`) |
| Accepts `mfg='abc'` and `mfg={abc}` on an element or a `.model`, and does not evaluate the braces (`mfg={1+}` runs). | `ParseError`: `mfg`, `pn` and `type` take a double-quoted string or a bare word. | `test_names_outside_the_closed_lists_run_but_the_library_rejects_them`; `test_mfg_in_braces_is_not_evaluated`; `test_the_lists_stay_closed`; `test_text_values_and_numeric_values_do_not_mix` |
| Accepts keyword values: `R=1k`, `inductance=1m` (not `resistance=`, `C=`, `capacitance=` or `L=`). | `ParseError`: no keyword form. | `test_keyword_values_run_but_the_library_rejects_them`; `test_other_keyword_values_stop_both`; `test_keyword_values_are_not_ltspice_forms` |
| Reads a bare word or expression as a parameter reference in `R=x*2`, `m=x`, `noiseless=x`, `X1 a b s r=2*1k`, `.subckt s a r=2*1k`, and `.model ... Is=x` or `Is=1n*2`. | `ParseError`: bare expressions only in `.param`. On a `.model` the message suggests `{x}`; only `mfg` and `type` take a bare word (review R8). | `test_bare_expressions_are_read_as_references_but_the_library_rejects_them`; `test_a_bare_word_for_a_flag_is_a_parameter_reference`; `test_bare_expressions_on_subcircuits_run_but_the_library_rejects_them`; `test_a_bare_word_in_a_model_is_a_parameter_reference_in_ltspice`; `test_malformed_subcircuit_calls`; `test_other_model_parameters_reject_a_bare_word` |
| Accepts `V1 a 0 DC=3`, `AC 1 DC 3`, `Rser=1 AC 1` and `I1 a 0 1 load AC 1`. | `ParseError`: the reference's order. | `test_other_source_orders_run_but_the_library_rejects_them`; `test_malformed_voltage_sources`; `test_malformed_current_sources` |
| Accepts `tc=1m 1u` (no comma). | `ParseError`. | `test_other_resistor_lists_run_but_the_library_rejects_them`; `test_malformed_resistor_lines` |
| Accepts commas in `m=2, temp=3`, `AC 1, 2`, `.subckt s a,b` and `.ac list 1,2`. | `ParseError`. | `test_other_resistor_lists_run_but_the_library_rejects_them`; `test_other_commas_run_but_the_library_rejects_them`; `test_malformed_ac` |
| Accepts `.dc V1 list 1 2 V2 1 2 1` (a list before another sweep). | `ParseError`: a list is the last sweep, since its values are not delimited for the LALR parser. | `test_other_dc_forms_run_but_the_library_rejects_them`; `test_malformed_dc` |
| Accepts `.dc V1 0 1` and `.step param x 1 2` (no increment). | `ParseError`: the reference has four fields. | `test_other_dc_forms_run_but_the_library_rejects_them`; `test_a_step_without_an_increment_runs_but_the_library_rejects_it`; `test_malformed_dc`; `test_malformed_step` |
| Accepts `{{x}}` and `.param a$b=1`. | `ParseError`. | `test_nested_braces_and_a_dollar_in_a_param_run_but_the_library_rejects_them`; `numbers.md` |
| Accepts a port named `0`. | `ParseError`, as for ngspice. | `test_a_port_named_0_runs_but_the_library_rejects_it`; `test_a_port_cannot_be_zero` |
| Reads BOM-less UTF-16LE and Latin-1 by itself (reference, Text Encoding). | BOM-less UTF-16LE is not detected, because it needs a heuristic (P5): the caller decodes it and names the encoding. Bytes that are not UTF-8 are tried as `cp1252` before Latin-1; the two differ on 0x80–0x9F (decision 0001). | `test_encodings_ltspice_reads_by_itself`; `test_encodings_round_trip` |
| Runs `E1 out 0 vx 0 gain=2`; the reference writes the gain positionally. | `ParseError` at `gain` (decision 0015 item 6). | `tests/solver/test_ltspice_controlled_probes.py::test_controlled_source_probes` (`e-gain-keyword`) |
| Runs `S1 … sm on off`; the last keyword sets the state. | `ParseError` at the second keyword (decision 0015 item 8). | `tests/solver/test_ltspice_controlled_probes.py::test_controlled_source_probes` (`s-on-off`); `elements_rejects/s_on_off.cir` |
| Runs `E1 out,0 vx 0 2`, a comma between E's output nodes, but stops on `F1 0,out Vs 2`. | `ParseError` for both: a comma is not a node separator on any LTspice letter (decision 0009). | `tests/solver/test_ltspice_controlled_probes.py::test_controlled_source_probes` (`e-comma`, `f-comma`) |

## Forms the library accepts and LTspice rejects

Syntax the library cannot judge from the netlist's form, or chooses not to.

| LTspice 26.1.1 | Library behaviour | Evidence |
|---|---|---|
| Runs `Q1 c b e qm 1n5` with `qm` as the model and `1n5` as an area of 1.5n. | Loads a 4-node Q with model `1n5`, so `qm` is a net: the topology view and the signature show a connection that LTspice does not make. The grammar cannot tell `1n5` from a model name such as `2N3904`, which is also an embedded decimal (decision 0014 item 5). The only signal is `UNRESOLVED_MODEL` for `1n5`, which is info when the scope has an `.include`. Write the area as `1.5n`. | `tests/grammar/ltspice/test_ltspice_transistors.py::test_the_model_is_the_last_name`; `tests/solver/test_ltspice_transistor_probes.py::test_transistor_probes` (`q-embedded-area-after-model`) |
| `Q1 c b e qm s` stops: `s` is not a model. | Loads with `s` as the model and `qm` as a fourth node, the boundary rule (decision 0014 item 1), as ngspice reads it. | `tests/solver/test_ltspice_transistor_probes.py::test_transistor_probes` (`q-model-then-name`) |
| A 3-node M stops with an NMOS model; only VDMOS has 3 nodes. | Loads: node counts are per letter, not per model type (decision 0014 item 2). | `tests/solver/test_ltspice_transistor_probes.py::test_transistor_probes` (`m-3-nodes-nmos`) |
| `temp=` stops on a `level=8` MOSFET, although the reference lists it for M. | Loads: the grammar cannot know the level. | `tests/solver/test_ltspice_transistor_probes.py::test_temp_on_a_bsim_line_loads_and_stops_ltspice` |
| Stops at an unknown option name (`.options foo=1`). | Accepted: option names are not checked, because the reference's list is partial and an option is not topology (settled in T4, `LT-OPT-001`). | `test_an_unknown_option_stops_ltspice_only`; `test_options` |
| Stops at a UTF-16 big-endian file. | Accepted: the source layer is dialect-neutral (decision 0001). | `test_big_endian_utf16_stops_ltspice_only`; `tests/test_source.py` |
| Stops at `.step x 1 2 1` ("Can't sweep that") and at `.dc R1 ...` (only independent sources). | Accepted as syntax: the source is any name. A name no element has gets `UNRESOLVED_ELEMENT`. | `test_a_sweep_of_something_else_stops_ltspice_only`; `test_a_step_refers_to_its_source_and_model` |
| Stops at a repeated `.param` or designator, an undefined model or subcircuit and a port count mismatch; at a repeated `.subckt` that an instance uses; at a repeated `.model` that an element uses, when the definitions differ. | Diagnostics, not errors (`scoping.md`). | `tests/solver/test_ltspice_solver_document.py`; `tests/document/test_ltspice_document.py` |
| Fails on a shallow `.meas` body it cannot read (`.meas sp y param 1`). | The body is text; `sp` reads as the result name. | `test_a_measurement_ltspice_cannot_read_stops_ltspice_only`; `test_meas` |
| Reads `.tran ... steady`, then stops on a circuit whose steady state it cannot detect. | Accepted: whether a circuit has one is not syntax (`LT-TRN-001`). | `test_steady_without_a_steady_state_stops_ltspice_only` |
| Stops at a top-level `.param temp=1` ("reserved symbol"); runs `temp` as a subcircuit default or a body `.param`. | Accepted at both levels, with a reference to the definition: the rule is about one name in one scope, and it fails loudly in LTspice (rule S11). | `tests/solver/test_ltspice_solver_document.py::test_temp_may_be_defined_only_in_a_body` |
| Stops at `.func sqrt(x) ...` ("name of a built-in function") and at `.param pi=pi*2`. | Accepted: `.func` is untyped text, and a formula is not evaluated. | `tests/solver/test_ltspice_solver_document.py::test_a_func_may_not_redefine_a_built_in_function` |
| Stops at `x1:0`, `x1:gnd`, `x1:$G_x` or `x1:vcc` with `vcc` global ("Ill-formed node name"), when `x1` is an instance. | Accepted, with `NODE_INTO_INSTANCE` (`names.md` N11). | `tests/solver/test_ltspice_solver_document.py::test_a_global_node_in_an_instance_stops_ltspice_and_is_flagged` |
| Stops at a `:` in a `.global` node or a `.subckt` port. | Accepted: a `:` is a name character. | `tests/solver/test_ltspice_solver_document.py::test_a_colon_in_a_global_or_a_port_stops_ltspice_only` |
| Stops at `.fra` without an `@` device ("requires at least one enabled fra device"), and at arguments it cannot read (`.fra dec 10 1 1k`, `.loadstate nosuch.st`, a quoted file that does not exist). | Accepted as text, like any argument of an untyped command. `@` itself is `UnsupportedConstruct` until phase 2. | `tests/solver/test_ltspice_validation.py::test_fra_needs_its_device`; `test_untyped_arguments_ltspice_stops_at_are_kept_as_text` |
| Stops at a loop of inductors and a voltage source (over-defined matrix), with exit code 1 and no `file(line):` line. | Accepted: topology is not checked. | `test_an_inductor_loop_stops_ltspice_without_an_error_line` |

## Settled while implementing

- **K with three inductors** is valid: three and four inductors run when each has its own load.
  Probe L13's circuit is not recorded. Three coupled inductors in a loop with an ideal source reproduce
  its symptom (exit 1 with no error line, an "over-defined circuit matrix" message), which suggests
  that cause, but it is an inference.
- **`$`** is a comment only as space, `$`, space; a tab on either side does not count. `$G_x`, `a$b`
  and `a$` are names, and a `$` line is an error.
- **`//`** is not a comment in LTspice: `1k // c` fails and `.include sub//h.inc` is a path.
- **Nested `.step`:** four run, and the reference states no limit, so a fourth is not refused. Sweeping
  the same quantity twice stops LTspice.
- **No R, C or L model:** `.model rm R` then `R1 a b rm` exits 1, and `R1 a b 1k rm` stops at "Unknown
  parameter"; the reference lists no such type.
- **Comma forms** are minimal: `tc` values (documented) and, observed, `.model` and `X` parameters,
  `.param` assignments, `.options` items and `.save` vectors.
- **N, P and Y** stop both. LTspice's message for `P` and `Y` is "Expected nodes", not the one for an
  unknown line, so it may read them as undocumented letters; the reference does not list them.
- **A warning in the form of an error:** `V1 a 0` (no value) runs and is read as 0 V, but LTspice writes
  "Missing value, assuming 0V" as a `file(line):` line. The fixture that holds it names the message in
  its manifest's `solver` field. `.loadstate` with no file does the same: it runs, with "no default
  loadstate file found".
