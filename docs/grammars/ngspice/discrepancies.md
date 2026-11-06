# ngspice manual and solver discrepancies

The parser follows the strict ngspice manual policy in
[decision 0002](../../decisions/0002-grammar-structure-policy.md). The
observations below describe ngspice 47 only; they are not accepted as syntax
rules. Each lenient behavior is paired with a test demonstrating that the
strict parser rejects the same input.

## ngspice 47 observations (2026-10-21)

| Solver behavior | Strict parser behavior | Evidence |
|---|---|---|
| Accepts a complete netlist without `.end`. | Rejects missing `.end`. | `test_missing_end_is_solver_leniency_rejected_by_parser` |
| Silently ignores an element after `.end`. | Rejects content after `.end`. | `test_element_after_end_is_ignored_by_solver_rejected_by_parser` |
| Runs a `.control` block placed after `.end`. | Rejects a block after `.end`. | `test_control_block_after_end_runs_but_parser_rejects` |
| Joins a `+` continuation across intervening `*` comments and blank lines. | Requires the `+` line to immediately follow its statement. | `test_continuation_across_comment_and_blank_is_solver_leniency` |
| Ignores a `+` line after `.end`. | Rejects a continuation after `.end`. | `test_plus_after_end_is_ignored_by_solver_rejected_by_parser` |
| Accepts a standalone `//` line. | Rejects it: `//` is an end-of-line comment after a command (§2.4.4), not a comment line. | `test_double_slash_comment_probe` |
| Rejects an unknown dot-command after `.end`. | Rejects it as well. | `test_unknown_dot_command_after_end_fails_in_both` |
| Accepts `.end ; c`, `.end $ c` and `.end // c` (2026-10-30). | Rejects a trailing comment on `.end` (§2.4.2 reading). | `test_trailing_comment_on_end_is_solver_leniency_rejected_by_parser` |
| Continues a line ending in `\\` followed by spaces (2026-10-30). | `\\` must end the line; with trailing spaces it is text, so the next line is a separate statement. | `test_backslash_after_trailing_space_or_in_comment_is_solver_leniency` |
| Continues a line whose end-of-line comment ends in `\\` (2026-10-30). | The comment runs to the end of the line; its `\\` is comment text. | `test_backslash_after_trailing_space_or_in_comment_is_solver_leniency` |

The `.if (1)` … `.endif` form is accepted and is covered by
`test_valid_if_form_is_accepted_by_solver_and_parser`. The earlier `.if 1`
probe was invalid and is not evidence against conditional support.

The remaining manual-quiet cases are probed separately:

- Quoted and braced `.include` paths with `;` and `$` are probed by
  `test_quoted_and_braced_include_paths_probe`. The tested quoted path works;
  the braced path is truncated at `;`. The grammar honors matched quotes and
  treats braces as ordinary free text. These are observations about solver
  text handling, not a general claim that the manual specifies quoting or
  braces for arbitrary directive text.
- `//` end-of-line comments (2026-10-30) agree with the grammar:
  `test_double_slash_comment_needs_no_preceding_space` shows that ngspice 47
  treats `2//3`, `2// 3` and `2 // 3` alike, and
  `test_include_path_is_cut_at_double_slash_unless_quoted` shows that
  `.include sub//v.inc` is cut at `//` while `"sub//v.inc"` is included.
- `.include` and `.lib` continuation (2026-10-30) agrees with the grammar:
  `test_include_and_lib_continuation_fails_in_both` shows that ngspice 47
  does not join a `+` line to either statement and reports an error.
- Backslash continuation (2026-10-30) otherwise agrees with the grammar:
  `test_backslash_continuation_agrees_with_solver` (with or without a space
  before `\\`, indented next line, CRLF, mixed with `+`) and
  `test_backslash_before_a_line_that_cannot_continue_fails_in_both` (blank,
  comment or `+` line after `\\`, a line holding only `\\`).
  `test_backslash_after_include_path_fails_in_both`: ngspice 47 reads a
  trailing `\\` as part of an `.include` path; the parser rejects it.
- Titles are parsed as a single token, including `;` and `$`, under the narrow
  reading of `[ngspice-manual] §2.4.1 ".TITLE line"` (edition in
  [docs/references.md](../../references.md)).
  `test_title_is_first_line_and_later_title_replaces_it` records the ngspice
  47 behavior.

## Element and value observations (ngspice 47, 2026-10-30; M3)

Probes are in `tests/solver/test_ngspice_solver_elements.py`. Values are read from the device
tables ngspice prints after `.op`.

| Solver behavior | Parser behavior | Evidence |
|---|---|---|
| Without LT mode, drops the digits after a scale letter without a warning: R `2k7` is 2k, `4R7` and `4L7` are 4, `4G7` is 4G, `1M0` is 1m; C `4u7` is 4u, `4F7` is 4f. | An RKM value is a `ParseError` naming the `rkm` option. | `test_rkm_digits_are_dropped_without_lt_mode` |
| Without LT mode, R `R47` is an error. | `ParseError` (RKM without the option). | `test_leading_r_rkm_is_an_error_without_lt_mode` |
| With `set ngbehavior=lt`, reads `2k7`, `4R7`, `R47`, `4L7`, `4G7`, `4u7`, `4p7` per IEC 60062. | Accepted with `rkm=True`, `notation="rkm"`. | `test_lt_mode_reads_rkm_per_iec_60062` |
| In both modes, reads R `1M0`/`4M7` as milli and C `4F7` as femto; IEC 60062 reads mega and farad. | Accepted with `rkm=True` per IEC 60062 and marked `solver_mismatch=True` (`RKM_SOLVER_MISMATCH`, M5). | `test_rkm_mismatches_with_iec_60062_are_marked` |
| Reads `1µ` as `1u` (the manual's table has no `µ`). | Accepted (`observed`). | `test_standard_numbers_agree_with_solver` |

These agree with the parser: `4E7` is an exponent in both modes
(`test_exponent_is_not_an_rkm_code_in_either_mode`); trailing letters, `.5k`, `5.`, `+1k`,
`1e3k`, `mil` and `a` (`test_standard_numbers_agree_with_solver`); a comma between nodes,
`r=` and `r = ` and a `+` continuation (`test_separators_and_keyword_value_agree_with_solver`);
a model name starting with a digit (`test_digit_leading_model_name_agrees_with_solver`).
Every file of the `elements_basic` corpus loads and solves with model and subcircuit
definitions added (`test_accept_corpus_runs_in_ngspice`). The LTspice reading of `1M0` is
checked in M8.

## Statement and directive observations (ngspice 47, 2026-10-30; M4)

Probes are in `tests/solver/test_ngspice_solver_statements.py`. Unless noted, the circuit is a
divider (`V1 in 0 DC 3`, two 1k resistors) and the result is `v(out)` after `.op`.

| Solver behavior | Parser behavior | Evidence |
|---|---|---|
| Accepts `.tran` and `.op` inside a `.subckt` body (1.5 V). | `ParseError` at the directive: §2.6.1 forbids control lines in a definition (decision 0005). | `test_solver_runs_these_and_the_library_follows_the_manual` |
| Accepts a port named `0` (`.subckt div a 0`). | `ParseError` at the port (§2.6.1: ports "cannot be zero"). | same |
| Reads a blank-free bare `.param` expression (`.param c = a+1k`: 2.0 V; `.param c = a`: 1.5 V). | `ParseError` at the value suggesting braces (§2.11.1 recommends braces or quotes). | same; `test_param_values_reach_the_element` |
| Accepts `.param time=1` and `.param 1a=2`. | `ParseError`: §2.11.1 reserves `time`, `temper`, `hertz` and requires a letter first. | `test_solver_runs_these_and_the_library_follows_the_manual` |
| Accepts `.temp 27 30` with a warning and runs at the default temperature. | `ParseError`: `.temp` takes one value (§2.14). | same |
| Accepts an empty `.options`, an empty `.save`, `.op 1` and `.meas tran x` (with an "incomplete measurement" warning). | `ParseError`: each general form has at least one item, `.op` none, a measurement after the result name. | same |
| Accepts `.model x D bf` (a parameter without a value). | `ParseError`: §2.5 shows `pname=pval`. | same |
| Accepts `.nodeset v(out)=1 all=2`. | `ParseError`: §11.2.1 gives the `v()` list and `all=` as separate forms. | same |

These agree with the parser: a stray `.ends`, `.ic all=1`, a `.tran` field after `tmax`,
`.ac log`, `.dc` with a missing increment and `.param c = a + 1k` fail in both
(`test_solver_and_library_both_reject`); `.ends other` closing `.subckt div`, `D()`, duplicate
ports, a nested definition, a default overridden on the call (2.25 V), the three `.model`
parameter layouts, a `.model` local to a subcircuit (an error in ngspice when used outside it,
accepted as syntax here and scoped in M5), `.option` (typed) and `.opt` (unknown), and blanks
inside `.ic v( out )` (`test_initial_condition_with_blanks_inside_v`). Every file of the
`statements_basic` corpus runs in ngspice 47 without an error (`test_accept_corpus_runs_in_ngspice`).

### `.save` vector forms (ngspice 47, 2026-10-31; M4 review round 1)

`test_save_vector_forms_and_the_stored_variables` runs an AC analysis with one `.save` line
and reads the variables from the raw file. ngspice accepts every form, but stores only plain
voltages and currents: `.save v(in, out)` stores the two vectors `v(in)` and `v(out)`, not
their difference; `vm(out)` and `vdb(out)` store `v(out)` (the magnitude can be derived from
the raw data, §11.6.1); `v( out )` stores `v(out)` and `i(V1)` stores `i(v1)`. The parser
accepts the same forms and records each vector as written (`text`, `function`, nodes or
source); it does not model what ngspice stores.

## M7 validation observations (ngspice 47, 2026-10-31)

Probes are in `tests/solver/test_ngspice_validation.py` (decision 0008). Each lenient form is
rejected by the library under P5; none appears in the maintainer's exports.

| Solver behavior | Library behavior | Evidence |
|---|---|---|
| A stray `.endc` runs with "Warning: Missing .control statement!" (`NG-DIR-001`). | `ParseError` at `.endc`: a stray block terminator (§2.1.2.3). | `test_a_stray_endc_runs_with_a_warning_but_the_library_rejects_it` |
| Node names with `[ ]`, `%`, `<`, `~` or `(` run (`o[1]`, `a%b`, `a<b`, `a~b`, `a(b`: 1.5 V) (`NG-NOD-001`). | `ParseError` at the name: §2.1.3.4 lists these characters as not allowed in a name. | `test_excluded_name_characters_run_but_the_library_rejects_them` |
| `X1 in out div params: r=2k` runs (2.0 V) (`NG-UNS-001`). | `ParseError` at `params:`: not ngspice syntax per §2.11.3. | `test_params_keyword_on_an_x_line_runs_but_the_library_rejects_it` |
| `SINE(0 1 1k)` runs and reads as `SIN` (`NG-FUN-003`). | Accepted, although the manual does not list it: the one exception to decision 0002 (decision 0013). | `test_sine_reads_as_sin` |
| `PULSE 0 1 1u`, with no parentheses, runs (`NG-FUN-001`). | `ParseError`: the manual writes the parentheses. | `test_forms_that_run_and_the_library_refuses` |
| `PULSE(0 x 1u)`, a bare parameter name, runs (`NG-FUN-001`). | `ParseError`: not in the manual, and the reference would be hidden. | `test_forms_that_run_and_the_library_refuses` |
| `SIN(0 1 1k) 1` runs and the output is 0 (`NG-FUN-001`). | `ParseError`: a value after a function needs `DC`. | `test_forms_that_run_and_the_library_refuses` |
| `SIN(…) PULSE(…)` runs, and the last wins (`NG-FUN-001`). | `ParseError`: one function per line. | `test_forms_that_run_and_the_library_refuses` |

Three manual forms stop ngspice 47 here, and the library follows the manual: bare `DISTOF1`, the
manual's `AC 1 DISTOF1 DISTOF2 0.001` (`test_manual_distortion_forms_that_stop`), and `EXTERNAL`,
which needs ngspice as a shared library (`test_external_is_read_and_stops_this_build`).

These agree: unknown dot-commands `.print`, `.width` and `.func` run (`.func` takes effect in a
value) and stay `UnknownDirective`; a stray `.endif`, `.else` or `.elseif` fails in both; `a/b`,
`n+1`, `n-1`, `a#b`, `1n` and `N_OUT.2` are node names in both, and a `'` or `=` in a name fails
in both; `m=2`, `tc1` with `.temp` and `off` take effect; `q=` runs; `{…}` and `'…'` evaluate alike,
`{a;b}` fails in both and string defaults and overrides run; a top-level `K`, `.dc` or
`.save i()` cannot name an element inside an instance (S9, `UNRESOLVED_ELEMENT` in the library).

### An `.if` condition in braces (opaque text, `NG-OPA-001`)

| Solver behavior | Library behavior | Evidence |
|---|---|---|
| Stops at `.if {enabled}` ("Bad syntax"); reads `.if (enabled)` (`NG-OPA-001`). | Accepts both: an `.if` block is opaque and its condition is not checked. | `test_an_if_condition_in_braces_fails_in_ngspice_but_the_library_keeps_it` |

The condition is opaque text, which is not part of the library's model (decision 0008 item 1,
opaque-text rule), so this difference does not decide the status of `NG-OPA-001`: a netlist with
`.if {enabled}` is well-formed for the library and fails in ngspice, which is the netlist's error.
The grammar is unchanged. Evidence:
`test_an_if_condition_in_braces_fails_in_ngspice_but_the_library_keeps_it`.

ngspice 47 also cannot include one file both whole (`.include`) and as a library section
(`.lib file section`): a `.lib` section in a file included whole is an "unimplemented dot
command". `structure_basic.cir` does both with `models.lib`, so it is skipped by the corpus
sweep; the solver-free tests are unaffected.

## Names, scoping and formula observations (ngspice 47, 2026-10-31; M5)

Probes are in `tests/solver/test_ngspice_solver_document.py`; the rules they validate are in
[names.md](./names.md) and [scoping.md](./scoping.md).

| Solver behavior | Library behavior | Evidence |
|---|---|---|
| Resolves a parameter used before its `.param` line (2.25 V with `R2 out 0 {rx}` then `.param rx=3k`). | Resolves it and reports `PARAM_USED_BEFORE_DEFINITION` (warning): §2.11.1 says a parameter "must have been assigned a value" before its first use. | `test_parameter_case_order_and_redefinition` |
| Accepts `.global vcc` inside a `.subckt` body and makes `vcc` global (1.5 V). | `ParseError` at `.global`: top level only, like the other statements §2.6.1 keeps out of a definition (decision 0006). | `test_global_inside_a_body_runs_but_the_library_rejects_it` |
| A `.model` inside a definition is not found at the top level (§2.6.1), although §2.11.4 calls model and subcircuit names global. | Follows ngspice and §2.6.1: `UNRESOLVED_MODEL` (scoping.md, the §2.11.4 / §2.6.1 conflict). | `test_models_are_local_to_their_definition` |
| `.param a#b=3`, `a!b`, `a%b` are accepted as names (§2.11.1), but `{a#b}` fails ("Undefined parameter [b]"), as do `{a!b}` and `{a%b}`. | The formula grammar does not read `!`, `#` or `%` as name characters (§2.11.5 uses `!` and `%` as operators): `{a#b}` and `{a!b}` give no references, `{a%b}` gives `a` and `b` (unresolved). | `test_formula_name_characters_and_constants` |
| `{pi}` fails as an undefined parameter; §2.11.5 defines no constants (`vec(pi)` reads the const plot). | `pi` is an ordinary identifier: `UNRESOLVED_PARAM` unless a `.param pi` exists. | same |

These agree: node, designator, model, subcircuit, parameter and inductor-reference case; `gnd`
as ground and `00` as a separate node; duplicate designators (case-insensitive) and an X line
with the wrong number of nodes are fatal in ngspice and diagnosed by the library; definition
order does not matter; local parameters mask global ones; a repeated `.param` uses the last
assignment and a repeated `.model`/`.subckt` the first; an unknown X parameter is ignored; a net
inside a definition is local (`x1.mid`) unless it is ground, a port or `.global`. For every
`statements_basic`, `elements_basic` and `document_basic` file, the library's top-level nets are
ngspice's node list (`test_library_nets_match_the_ngspice_node_list`).

## Transistor observations (ngspice 47, 2026-11-05; M13)

Decision 0014 items 1 to 6. Each row is a case of `tests/solver/test_ngspice_transistor_probes.py::test_transistor_probes` unless named.

| Solver behavior | Library behavior | Evidence |
|---|---|---|
| Runs `Q1 c b e qm 2`, a positional area on a BJT; the manual shows only `area=`. | `ParseError`: the area of an ngspice Q is named (decision 0014 item 5, decision 0002). | `test_a_positional_area_on_q_runs_and_is_refused` |
| `Q1 c b e off qm` stops: "can't find model 'off'". | `off` before the model is a node, as LTspice reads it (decision 0014 item 4). | `q-node-named-off` |
| `Q1 c b e qm s` stops: "can't find model 's'". | Agrees on the reading: `s` is the model and `qm` a fourth node (the boundary rule). | `q-model-then-name` |
| `.model 2 NPN` with `Q1 c b e 2` stops: "can't find model 'e'". | `ParseError`: a model named with a plain number is refused (decision 0014 item 4). | `q-number-model` |
| A 5-node Q runs only with a VBIC model, and a 3-node M only with VDMOS. | Node counts are checked per letter, not per model type: those lines load (decision 0014 item 2). | `q-5-nodes-gummel-poon`, `m-3-nodes-nmos` |
| `temp=` stops on a `level=8` MOSFET, although §7.6.1 lists it. | Loads: the grammar cannot know the level. | `test_temp_on_a_bsim_line_loads_and_stops_ngspice` |
| `.model zi NIGBT` stops: "Unknown model type nigbt". | Loads, and `MODEL_TYPE_MISMATCH` on a Z line that names it (decision 0014 item 8). | `test_an_igbt_model_is_not_an_ngspice_type` |

## Dependent source and switch observations (ngspice 47, 2026-11-06; M14)

Decision 0015 items 4 to 8. Each row is a case of `tests/solver/test_ngspice_controlled_probes.py::test_controlled_source_probes`.

| Solver behavior | Library behavior | Evidence |
|---|---|---|
| Runs `E1 out 0 vx 0 gain=2`; manual chapter 27 lists `gain` as a device parameter, and §4.2 writes the gain positionally. | `ParseError` at `gain` (decision 0015 item 6, decision 0002). | `e-gain-keyword` |
| Runs `E1 out 0 vx 0 2 3`, with an output that matches neither value. | `ParseError` at the second value. | `e-two-values`; `elements_rejects/e_two_values.cir` |
| Runs `S1 … sm on off` and `off on`; the last keyword sets the state. | `ParseError` at the second keyword (decision 0015 item 8). | `s-on-off`; `elements_rejects/s_on_off.cir` |
| Runs an F, H or W controlled by an E or an H (they have a branch current); §4.2.3 and §4.2.4 name a voltage source. | Loads, with `CONTROL_SOURCE_MISMATCH` (decision 0015 item 5). | `f-ctrl-e`, `f-ctrl-h` |
| Crashes (exit code 0xC0000005) on `E1 … GND` with no gain in a KiCad netlist, after "not enough parameters". | `ParseError` at the line's end. | `elements_rejects/e_no_value.cir` |
