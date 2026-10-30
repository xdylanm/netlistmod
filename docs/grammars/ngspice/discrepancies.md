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
| Accepts a `//` line in the tested netlist. | Rejects it as a non-comment line. | `test_double_slash_comment_probe` |
| Rejects an unknown dot-command after `.end`. | Rejects it as well. | `test_unknown_dot_command_after_end_fails_in_both` |

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
- Titles are parsed as a single token, including `;` and `$`, under the narrow
  reading of `[ngspice-manual] §2.4.1 ".TITLE line"` (edition in
  [docs/references.md](../../references.md)).
  `test_title_is_first_line_and_later_title_replaces_it` records the ngspice
  47 behavior.
