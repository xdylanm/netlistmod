# Xyce manual, solver and library discrepancies

The library follows the manuals (architecture §11.3 rule 2;
[decision 0026](../../decisions/0026-the-xyce-dialect.md),
[decision 0027](../../decisions/0027-xyce-structure-names-and-values.md) item 12). This file
records what XyceNF Release 7.10.0 (Windows) does where it differs from the manuals, or where the
library differs from either. The rows come from the X-M0 probes (task A4, 2026-11-15) and the X-M1
stage 1 probes (xm1-tasks 5.1), re-run as the solver tests of `tests/solver/test_xyce_*.py`. Each
row's Evidence names the solver test that shows Xyce's side and the library test that pins the
library's side.

## Forms Xyce runs and the manual or the library rejects

| Xyce 7.10 | Manual | Library behaviour | Evidence |
|---|---|---|---|
| Runs a netlist without `.END`. | The last line must be `.END` (`[xyce-ug] §4.1.1 p40`, `§4.1.3.1 p42`). | `ParseError`: `.END` is required (`XY-END-001`; decision 0027 item 2). | `tests/solver/test_xyce_structure_probes.py::test_a_netlist_without_end_runs`; `tests/grammar/xyce/test_xyce_structure.py::test_end_is_required` |
| Ignores text after `.END`, element lines included. | `.END` marks the end of the netlist (`[xyce-ref] §2.1.6 p33`). | `ParseError`: only blank lines may follow `.END`. | `tests/solver/test_xyce_structure_probes.py::test_text_after_end_is_ignored`; `tests/grammar/xyce/test_xyce_structure.py::test_end_is_last_with_only_blank_lines_after_it` |
| Runs `.end junk`, ignoring the text after `.END` on its line. | `.END` stands alone; `;` may end any line (`[xyce-ug] §4.1.3.1 p43`). | `ParseError`: only a `;` comment may follow `.END` on its line (`XY-END-001`). | `tests/solver/test_xyce_names_probes.py::test_end_with_text_after_it_runs`; `tests/grammar/xyce/test_xyce_structure.py::test_end_is_last_with_only_blank_lines_after_it` |
| Warns on an unknown dot-command and ignores the line; the body of an unknown block is read as ordinary lines. | Describes each command in `[xyce-ref]` §2.1 (p24–163) and says nothing of an unknown one. | `UnsupportedConstruct` for every dot-command the dialect does not read yet (`XY-UNS-001`). The closed list of dot-commands is X-M2's. | `tests/solver/test_xyce_structure_probes.py::test_an_unknown_dot_command_warns_and_is_ignored`; `tests/grammar/xyce/test_xyce_structure.py::test_every_other_dot_command_is_unsupported` |
| Takes commas between the names of `.GLOBAL` (`.global vdd,vss`). | Writes the names separated by blanks (`[xyce-ref] §2.1.11 p44`). | `ParseError` (`XY-GLB-001`; xm1-tasks 5.1 point 8). | `tests/solver/test_xyce_names_probes.py::test_global_makes_nodes_global`; `tests/grammar/xyce/test_xyce_names_numbers.py::test_a_global_without_names_or_with_commas_is_rejected` |
| Takes `"` and non-ASCII letters in a node name. | Allows printable ASCII except blanks and `( ) { } , : ; " '` (`[xyce-ref] §2.3.2 p184`). | `ParseError` (`XY-NAM-001`; decision 0027 item 3). | `tests/solver/test_xyce_names_probes.py::test_names_outside_the_manual_class_run`; `tests/grammar/xyce/test_xyce_names_numbers.py::test_a_name_outside_the_class_is_rejected` |
| Runs the number forms `1keg`, `1kmeg`, `1kmhz` and `1e` in a device field, which no list holds. | Lists the scale factors only (`[xyce-ug] §4.1.3 p41–42`, Table 4-1). | `ParseError`: both readers take only the closed lists (`XY-NUM-001`, `XY-NUM-002`; decision 0027 item 8). | `tests/solver/test_xyce_names_probes.py::test_device_fields_take_lexer_artefacts`; `tests/grammar/xyce/test_xyce_names_numbers.py::test_the_device_field_reader_refuses_other_letters` |

## Forms in the manuals that Xyce stops on

| Xyce 7.10 | Manual | Library behaviour | Evidence |
|---|---|---|---|
| Stops on `//` after a statement: it is not a comment. | The examples of `[xyce-ref] §2.2.3 p173` end `.print` lines with a `//` comment. | `ParseError`; only `;` ends a line, as the in-line comment rule of `[xyce-ug] §4.1.3.1 p43` says. | `tests/solver/test_xyce_structure_probes.py::test_dollar_and_double_slash_do_not_end_a_line`; `tests/grammar/xyce/test_xyce_structure.py::test_other_line_starts_are_rejected` |
| Stops on `$` after a statement: it is not a comment, unlike on ngspice. | Names only `;` as an in-line comment (`[xyce-ug] §4.1.3.1 p43`, `[xyce-ref] §2.1.39.2 p163`). | As for `//`. | `tests/solver/test_xyce_structure_probes.py::test_dollar_and_double_slash_do_not_end_a_line`; `tests/grammar/xyce/test_xyce_structure.py::test_other_line_starts_are_rejected` |
| Reads a bracketed node such as `[s]` as a node literally named `[s]`. | Writes a named BJT substrate in square brackets, `[substrate node]` (`[xyce-ref] §2.3.17 p241`), where the brackets elsewhere in the manual mark an optional field. | `[` and `]` are name characters (`XY-NAM-001`); the Q line is X-M4's. | `tests/solver/test_xyce_structure_probes.py::test_a_bracketed_node_is_a_literal_node_name`; `tests/grammar/xyce/test_xyce_names_numbers.py::test_a_global_node_takes_the_name_class` |
| Refuses the micro sign `µ` as a scale factor, in a device field and in an expression. | Lists `µ` beside `u` (`[xyce-ug] §4.1.3 p42`, Table 4-1). | `ParseError`, as on Xyce (`XY-NUM-001`). | `tests/solver/test_xyce_names_probes.py::test_device_fields_refuse_other_letters`; `tests/grammar/xyce/test_xyce_names_numbers.py::test_the_device_field_reader_refuses_other_letters` |

## Where the manual is silent

| Xyce 7.10 | Library behaviour | Evidence |
|---|---|---|
| Reads a blank first line as the title, so the netlist starts on line 2. | The same: an empty title (`XY-TTL-001`). | `tests/solver/test_xyce_structure_probes.py::test_a_blank_line_one_is_the_title`; `tests/grammar/xyce/test_xyce_structure.py::test_the_first_line_is_always_the_title` |
| Folds case in ASCII only: `Äb` and `äb` are two nodes. | The same (names.md N5). | `tests/solver/test_xyce_names_probes.py::test_case_folds_in_ascii_only`; `tests/document/test_xyce_names.py::test_names_fold_by_ascii_case_only` |
| Reads a unit after a scale factor from one closed list in a device field and from a shorter one, with `j`, in an expression; a letter that begins a scale factor is read as one (`1farad` stops Xyce). | The same (`XY-NUM-001`, `XY-NUM-002`). | `tests/solver/test_xyce_names_probes.py::test_device_fields_take_scale_factors_and_units`; `tests/solver/test_xyce_names_probes.py::test_expressions_refuse_the_device_units`; `tests/grammar/xyce/test_xyce_names_numbers.py::test_the_expression_reader_refuses_the_device_units` |
