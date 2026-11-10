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

## Behavioural observations (ngspice 47, 2026-11-06; M15)

Decision 0016 items 2 and 9. Each row is a case of `tests/solver/test_ngspice_behavioral_probes.py::test_behavioral_probes`.

| Solver behavior | Library behavior | Evidence |
|---|---|---|
| Stops on B `R=1k` and `P=4m` ("unknown parameter"); they are LTspice forms. | `ParseError` at the keyword, which says so. | `b-r`, `b-p`; `elements_rejects/b_r.cir` |
| Stops on `E1 out 0 vol=2*v(vx)`, a bare expression after `vol=`; the manual writes quotes or braces. | `ParseError` at the expression (decision 0002). | `e-vol-bare`; `elements_rejects/e_vol_bare.cir` |
| Stops on `E1 out 0 LAPLACE {v(vx)} {2}`; the manual says ngspice does not offer it (§5.2.5). | `ParseError`. | `e-laplace`; `elements_rejects/e_laplace.cir` |
| Runs `E1 out 0 value={2*` / `+ v(vx)}`, `vol='2*` / `+ v(vx)'` and `B1 out 0 V='2*` / `+ v(vx)'`, joining the lines. | `ParseError` at the brace or quote: a braced or quoted expression must close on its line, as every formula must (review R4). | `e-value-continued`, `e-vol-continued`, `b-quoted-continued` |
| Stops on `B1 out 0 V=2*v(vx)$c`: the `$c` is part of the expression (it runs `R7 out 0 1k$c`). | Loads, with the expression `2*v(vx)` and a trailing comment `$c`, as for every line. | `b-dollar` |
| Stops on `E1 out 0 value 0 2` and `G1 0 out value 0 1m`: `value` is the keyword there ("mal formed E source instance"). It reads `value` as the keyword in every node position of E and G, so it also stops on `E1 value 0 vx 0 2`, `E1 out value vx 0 2` and `E1 out 0 vx value 2`, in any case. It runs `E1 value 0 vol='2*v(vx)'` and `E1 value 0 value={2*v(vx)}`, but with `E1` not connected to `value`: `v(value)` is what the rest of the circuit gives, without a message. It runs F and H with a source or net named `value`. | `ParseError` at `value` in any node position of E and G (reviews R2 and R6; decision 0016 item 9). | `e-value-node`, `g-value-node`, `e-value-out`, `e-value-out-minus`, `e-value-control-minus`, `f-value-source`, `h-value-out`; `elements_rejects/e_value_node.cir` |
| Reports a singular matrix for `v(nonode)` in a B expression. | Loads, with `UNRESOLVED_NODE` (decision 0016 item 6). | `document_basic/node_read.cir` |

## Nonlinear form observations (ngspice 47, 2026-11-08; M15b)

Decision 0017 items 3 to 5. Each evidence entry is a case of `tests/solver/test_ngspice_nonlinear_probes.py::test_nonlinear_probes`, and the results quoted are those of `test_what_ngspice_computes`.

| Solver behavior | Library behavior | Evidence |
|---|---|---|
| Runs `TABLE v(vx) = (0,0) (2,4)`, a bare expression, and reads something else: 4.0 where the table gives 2.67. | `ParseError` at `TABLE` (decision 0002): write the expression in braces or quotes. | `e-table-bare`; `elements_rejects/e_table_bare.cir` |
| TABLE points are numbers (§5.2.3). It runs `(2,k)` and `(2,{4})` in pairs and `(0,0,2,{4})` in the four-node form correctly, stops on `(0,0,2,{2*k})` in a flat list and on `(0,0,2,k)` in the four-node form, and runs the four-node `(0,0,2,{2*k})` wrongly (1.333 where the table gives 2.67). | `ParseError` at the formula or name: the points are numbers, with units allowed (`-5mV`). `set_table` refuses the same. | `e-table-name`, `e-table-formula`, `e-table-flat-formula`, `e-table-nodes-formula`, `e-table-nodes-braced`, `e-table-nodes-name`; `elements_rejects/e_table_param.cir` |
| Runs three-value points `(0,0,0) (2,4,0)` in a TABLE and reads them wrongly (1.333); stops on an odd count. | `ParseError` at the point. | `e-table-triples`, `e-table-odd`, `e-table-odd-flat` |
| Stops on a four-node TABLE on G, and on `m=` after E's TABLE. | `ParseError`. | `g-table-nodes`, `e-table-m`; `elements_rejects/g_table_nodes.cir` |
| Stops on a net named `table` in any node position of E and G, in any case, as it does for `value`; `poly`, `freq`, `and` and `or` run. | `ParseError` at the node, with the message that names the keyword (decision 0017 item 5). A line that loads in M15 and ngspice stops on. | `e-net-table-out`, `e-net-table-out-minus`, `e-net-table-control`, `e-net-table-control-minus`, `g-net-table-out`, `g-net-table-control`, `e-net-poly`, `e-net-freq`, `e-net-and`, `e-net-or`; `elements_rejects/e_table_node.cir` |
| Runs `POLY(1) (vx,0) 0 2` with the control pair in parentheses; the manual does not show it. | `ParseError` at the parenthesis (decision 0017 item 3). | `e-poly-parens`; `elements_rejects/e_poly_parens.cir` |
| Runs `POLY({1}) vx 0 0 2`, a braced dimension. | `ParseError` at the dimension: it decides how many control nodes follow, so it must be an integer literal of at least 1. | `e-poly-braced-dimension`; `elements_rejects/e_poly_dimension.cir` |
| Runs a bare name for a coefficient, `POLY(1) vx 0 0 k`. | `ParseError` at the name: coefficients follow the gain slot, a number or a `{...}` expression. | `e-poly-name` |
| Runs `m=2` after an E's POLY. The manual gives `m` to F and G. | `ParseError` at `m` (the grammar offers `m=` after F's and G's list only). | `e-poly-m` |
| Stops with a single coefficient, `POLY(1) vx 0 3` and F's `POLY(1) Vsense 2`, and with a missing controlling source. | `ParseError` at the line's end: at least two coefficients. A missing source loads with `UNRESOLVED_ELEMENT`, as F's linear one does. | `e-poly-one-coefficient`, `f-poly-one-coefficient`, `f-poly-missing-source`; `elements_rejects/e_poly_one_coefficient.cir`, `elements_rejects/e_poly_too_few.cir` |
| Stops on FREQ without a format word, on two-value points and on `m=2` after G's FREQ. | `ParseError` at the first point, at the point, and at `m`. | `e-freq-no-format`, `e-freq-two-values`, `g-freq-m`; `elements_rejects/e_freq_no_format.cir` |
| Stops on a FREQ table whose first frequency, braced or not, has more than one character as written and follows its `(` directly: `({1e7}, …)`, `({f0}, …)`, `(10, …)`, `(1.5, …)`, `(1e7, …)`, and the manual's own example `+(1.000000e+07Hz, …`. A blank after the `(` runs, with or without a `Hz` suffix, and a `Hz` suffix runs on any frequency. A first frequency of one character (`0`, `1`, `3`) runs. | `ParseError` at the first frequency, with the fix (`( 1e7, …)`). A unit suffix loads. `set_table` keeps the blank after the `(`, and an edit that would write the stop is refused through verification. | `e-freq-first-*`, `e-freq-hz-*`, `e-freq-manual*`; `elements_rejects/e_freq_first_point.cir`; accept `controlled_sources/test_esource_freq_manual.cir` |
| Runs contradicting FREQ format words and keeps the last: `DB MAG (1, 6.02, 0) …` reads the points as MAG (`v(out)` 8.03, where `DB` alone gives 2.67). `DB DB` runs and reads the same. | `ParseError` at the second word for `DB` with `MAG`, `DEG` with `RAD`, and `R_I` with any other word; a repeated word loads. | `e-freq-db-mag`, `e-freq-mag-db`, `e-freq-deg-rad`, `e-freq-r-i-db`, `e-freq-db-db`; `test_what_ngspice_computes` |
| Reads every name before a gate's first point as an input pair and ignores `N`: `and(1)` and `and(3)` with two pairs run as two inputs, and `and(2)` with three pairs runs as three. It stops on one pair ("Too few ports") and on an odd count. | `ParseError` at `(N)` when the inputs are not `2N`, and at the first point when they are fewer than two pairs or odd (decision 0017 item 3), so that a line means what the manual says. | `e-and-n1`, `e-and-n3`, `e-and-three-pairs`, `e-and-one-pair`, `e-and-one-pair-n1`, `e-and-odd`; `elements_rejects/e_and_count.cir` |
| Stops on a third gate point, `and (2)` with a blank, points without commas, `(0.5,0)(0.9,2)` written tight, nodes in parentheses, and a gate on G. | `ParseError`. | `e-and-three-points`, `e-and-blank`, `e-and-no-commas`, `e-and-tight`, `e-and-parens`, `g-and`; `elements_rejects/g_and.cir` |

## Transmission line observations (ngspice 47, 2026-11-09; M16)

Decision 0019. Each evidence entry is a case of `tests/solver/test_ngspice_line_probes.py::test_line_probes`, and the results quoted are those of `test_what_ngspice_computes_in_ac` and `test_what_ngspice_computes_in_op` (50 Ω in, a matched line, 50 Ω out).

| Solver behavior | Library behavior | Evidence |
|---|---|---|
| Runs a T without a length (a default delay: −9° at 100 MHz) and `NL=` without `F=` (−3.6°). The manual says one of `TD=` and `F=` must be given. | `ParseError` at the line's end, or at `NL=`: exactly one length form (decision 0019 item 2). | `t-no-length`, `t-nl-only`; `elements_rejects/t_no_length.cir`, `elements_rejects/t_nl_without_f.cir` |
| Runs `TD=` together with `F=` and `NL=`, in either order: `TD=` wins silently (−36°). | `ParseError` at the later of the two. | `t-td-and-f`, `t-f-and-td`; `elements_rejects/t_td_and_f.cir` |
| Runs `rel=` and `abs=` on T; the manual does not list them. | `ParseError` at the name, with its own message. | `t-rel-abs`; `elements_rejects/t_rel.cir` |
| Runs `IC=` with one, two or three values, and four values separated by blanks; stops on five. The manual writes four, comma-separated. | `ParseError`: `IC=` holds exactly four comma-separated values (V1, I1, V2, I2). | `t-ic-one`, `t-ic-two`, `t-ic-blanks`, `t-ic-five`; `elements_rejects/t_ic_count.cir` |
| Runs `Z0=` twice, and `Z0=` with `Zo=`: the last wins. | `ParseError` at the second: `Z0=` and `Zo=` are one parameter (decision 0019 item 3), so an ambiguous impedance never loads. | `t-z0-twice`, `t-z0-zo`; `elements_rejects/t_z0_and_zo.cir` |
| Runs `Zo=` (the letter O), the LTspice reference's spelling, as `Z0=`. | Accepted on both dialects, as the same parameter (decision 0019 item 3, an exception to decision 0002). | `t-zo`; `transmission_lines/test_tline_t_zo.cir` |
| Runs a U line without `l=`, with only `n=`, or with a positional length, all with a near-zero length (0.4995 V where `l=5` gives 0.3333 V). | `ParseError` at the line's end, or at the positional value: `l=` must be given (decision 0019 item 4). | `u-no-l`, `u-n-only`, `u-positional`; `elements_rejects/u_no_length.cir`, `elements_rejects/u_positional.cir` |
| Ignores the reference nodes of Y and P: a reference held at 0.2 V gives the grounded result (0.4545 V) on either port, in `.op` and `.tran`. T uses its reference nodes (0.4 V). | `ParseError` at a Y or P reference node that is not ground (`0` or `gnd`), inside a subcircuit too (decision 0019 item 5). | `y-reference`, `p-reference`; `test_what_ngspice_computes_in_op`; `elements_rejects/y_reference_node.cir`, `elements_rejects/p_reference_node.cir` |
| Runs `m=2` and a positional length on Y, and ignores both (the result of `len=1`). | `ParseError` at the field. | `y-m`, `y-positional`; `elements_rejects/y_param.cir` |
| Stops on `m=2` on P (the planning probe had it run, ignored), on an odd node count and on a positional length. | `ParseError` (decision 0019 item 4 and 6). | `p-m`, `p-odd`, `p-positional`; `elements_rejects/p_param.cir`, `elements_rejects/p_odd_nodes.cir` |
| Runs P with eight coupled lines and crashes (exit code 0xC0000409) on nine, with a valid, diagonally dominant matrix. | A P line takes one to eight lines, as the manual says (decision 0019 item 6). | `test_p_holds_up_to_eight_lines` |
| Ignores any unknown bare word in a `.model` (`foobar` runs on LTRA and on D), so a run does not show that an LTRA flag is read. `lininterp` and `mixedinterp` change a `.tran` waveform; `nosteplimit`, `steplimit`, `nocontrol`, `truncnr` and `truncdontcut` give the same one in that probe. | The seven flags load on an LTRA model, and are a `ParseError` on any other type (decision 0019 item 8). | `test_which_ltra_flags_change_a_run`; `statements_rejects/ltra_flag_on_diode.cir` |
| Runs a second value after a parameter outside a CPL matrix (`.model dm d is=1e-14 1e-15`) and ignores it. | `ParseError` at the second value: only the R, L, G and C matrices of a CPL model take a list (decision 0019 item 9). | `statements_rejects/cpl_list_on_diode.cir` |
| Stops on a CPL model without one of its matrices ("lossy line parallel conductance not given"), or without `length=` even when the instance writes `len=`, and on a TXL model without `g=`. | Loads: model contents are not checked (decision 0019, section 1). `remove_model_param` may remove a matrix. | `edits_golden/lines_cpl_remove.expected.cir` (its manifest's `solver.skip`) |

## Code model and OSDI observations (ngspice 47, 2026-11-10; M17)

Decision 0020. Each evidence entry is a case of `tests/solver/test_ngspice_special_probes.py::test_code_model_probes` or `test_osdi_probes`; every circuit has `V1 in 0 1`, `Rin in 0 1k` and `Rl out 0 1k`, and `gain=5` gives 5 V.

| Solver behavior | Library behavior | Evidence |
|---|---|---|
| Runs a comma inside a vector port (`[in, in]`) and inside a connection's parentheses (`%vd(in, 0)`); the manual writes blanks. | `ParseError` at the comma (decision 0020 item 4). | `vector-comma`, `vd-comma`; `elements_rejects/a_vector_comma.cir`, `elements_rejects/a_paren_comma.cir` |
| Runs `~ d` (a blank after the tilde) on a digital node; the manual writes `~d`. | `ParseError` at the `~`. | `tilde-blank`; `elements_rejects/a_tilde_blank.cir` |
| Runs a comma between a code model's vector values (`in_gain=[2.0, 1.0]`); the manual writes blanks. | `ParseError` at the comma (decision 0020 item 5). | `model-vector-comma`; `statements_rejects/model_vector_comma.cir` |
| Runs `TRUE` and a quoted string on a built-in model type (`.model dm d(foo=TRUE)`), with only "Model issue" in the log, and ignores them. | `ParseError`: a vector, a boolean or a string is a code model's value, refused on a built-in type (decision 0020 item 5). | `model-true-on-d`; `statements_rejects/model_vector_on_builtin.cir` |
| Stops on `%vnam` inside a vector ("unknown controlling source", naming the node after it). | `ParseError` at the `%vnam`. | `vnam-in-vector`; `elements_rejects/a_vnam_in_vector.cir` |
| Stops on an A line without a model, on an A or N model of a built-in type ("Invalid model type for A type device"), on too many or the wrong ports, `null` where a port needs a node, and `~` on an analog port. | Loads, with `UNRESOLVED_MODEL` or `MODEL_TYPE_MISMATCH` for the model; ports are not checked, because a code model's interface is not visible to the library (decision 0020 item 4). | `no-model`, `builtin-model`, `tilde-analog`, `osdi-diode-model` |
| Stops on three nodes on a two-terminal `r2_cmc`, an unknown instance parameter (`foo=1`), and an N line without `pre_osdi`. | Loads: the node count and the parameter names belong to the Verilog-A module (decision 0020 item 6). | `osdi-three-nodes`, `osdi-unknown`; `test_osdi_needs_pre_osdi` |
| Runs one node on a two-terminal `r2_cmc` (`N1 out rmod`), leaving its second terminal open (0 V). | Loads, as one node. | `osdi-one-node` |
| Ignores an `r2_cmc` model's `rsh=`: 0.3333 V with `rsh=100`, `200` or none; the instance's `l=` and `w=` move the result. | Loads; model contents are not checked. | `test_an_osdi_edit_moves_the_result` (its comment) |
