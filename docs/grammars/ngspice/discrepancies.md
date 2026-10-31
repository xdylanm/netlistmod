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
