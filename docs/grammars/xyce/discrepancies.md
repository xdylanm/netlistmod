# Xyce manual, solver and library discrepancies

The library follows the manuals (architecture §11.3 rule 2;
[decision 0026](../../decisions/0026-the-xyce-dialect.md)). This file records what XyceNF Release
7.10.0 (Windows) does where it differs from the manuals, or where the library differs from either.
The rows come from the X-M0 probes (task A4, 2026-11-15; xm0-tasks 5.1 point 4), which are the
solver tests of `tests/solver/test_xyce_structure_probes.py` (task B4). Each row's Evidence names
the solver test that shows Xyce's side and the library test that pins the library's side.

## Forms Xyce runs and the manual or the library rejects

| Xyce 7.10 | Manual | Library behaviour | Evidence |
|---|---|---|---|
| Runs a netlist without `.END`. | The last line must be `.END` (`[xyce-ug] §4.1.1 p40`, `§4.1.3.1 p42`). | `ParseError`: `.END` is required (`XY-END-001`), as on ngspice and LTspice. Whether X-M1 keeps this is decided there. | `tests/solver/test_xyce_structure_probes.py::test_a_netlist_without_end_runs`; `tests/grammar/xyce/test_xyce_structure.py::test_end_is_required` |
| Ignores text after `.END`, element lines included. | `.END` marks the end of the netlist (`[xyce-ref] §2.1.6 p33`). | `ParseError`: only blank lines may follow `.END`. | `tests/solver/test_xyce_structure_probes.py::test_text_after_end_is_ignored`; `tests/grammar/xyce/test_xyce_structure.py::test_end_is_last_with_only_blank_lines_after_it` |
| Warns on an unknown dot-command and ignores the line; the body of an unknown block is read as ordinary lines. | Describes each command in `[xyce-ref]` §2.1 (p24–163) and says nothing of an unknown one. | `UnsupportedConstruct` for every dot-command but `.END` in X-M0 (`XY-UNS-001`). The closed list of dot-commands is X-M2's. | `tests/solver/test_xyce_structure_probes.py::test_an_unknown_dot_command_warns_and_is_ignored`; `tests/grammar/xyce/test_xyce_structure.py::test_every_other_dot_command_is_unsupported` |
| Reads an indented line as a silent comment, even an indented `.param` or `.END`. | Says the same (`[xyce-ug] §4.1.3.1 p43`, `[xyce-ref] §2.1.39.1 p163`). | An indented `*` line is a comment; any other indented line is `UnsupportedConstruct` until decision X-D1 (X-M1). An indented `.END` is not `.END`, so such a netlist has none. | `tests/solver/test_xyce_structure_probes.py::test_an_indented_element_line_is_a_comment`; `test_an_indented_param_line_is_a_comment`; `test_an_indented_end_line_is_a_comment`; `tests/grammar/xyce/test_xyce_structure.py::test_an_indented_line_is_unsupported` |
| Joins a `+` line to the last non-comment line, across comments and blank lines, but never to the title. | Says the same, without the title (`[xyce-ug] §4.1.3.2 p43`). | X-M0 reads no continuation. A `+` line after comment or blank lines that follow a statement is accepted by the grammar and refused with that statement (`XY-UNS-001`); one right after a refused dot-command is part of its refusal. A `+` line with only the title, comments and blank lines before it joins nothing and is a `ParseError`, as on Xyce. Continuation is X-M1's. | `tests/solver/test_xyce_structure_probes.py::test_a_continuation_joins_across_comments_and_blank_lines`; `test_a_continuation_never_joins_the_title`; `test_a_semicolon_line_is_a_comment`; `tests/grammar/xyce/test_xyce_structure.py::test_a_continuation_after_comment_or_blank_lines_is_not_a_syntax_error`; `test_a_continuation_with_only_the_title_before_it_is_rejected`; `test_a_continued_dot_command_is_unsupported_whole` |
| Reads a line that begins with `;` as a comment; a `+` line joins across it. | An in-line comment, `;`, may occur on any line (`[xyce-ug] §4.1.3.1 p43`). | `UnsupportedConstruct` until X-M1 reads `;` comments (`XY-UNS-001`); not a difference from the manual, recorded because X-M0 refuses a valid line. | `tests/solver/test_xyce_structure_probes.py::test_a_semicolon_line_is_a_comment`; `tests/grammar/xyce/test_xyce_structure.py::test_a_line_that_begins_with_a_semicolon_is_unsupported` |

## Forms in the manuals that Xyce stops on

| Xyce 7.10 | Manual | Library behaviour | Evidence |
|---|---|---|---|
| Stops on `//` after a statement: it is not a comment. | The examples of `[xyce-ref] §2.2.3 p173` end `.print` lines with a `//` comment. | X-M0 refuses every line that could hold one; a `//` line is a `ParseError`. X-M1 follows the solver and the in-line comment rule of `[xyce-ug] §4.1.3.1 p43`, which names only `;`. | `tests/solver/test_xyce_structure_probes.py::test_dollar_and_double_slash_do_not_end_a_line`; `tests/grammar/xyce/test_xyce_structure.py::test_other_line_starts_are_rejected` |
| Stops on `$` after a statement: it is not a comment, unlike on ngspice. | Names only `;` as an in-line comment (`[xyce-ug] §4.1.3.1 p43`, `[xyce-ref] §2.1.39.2 p163`). | As for `//`. | `tests/solver/test_xyce_structure_probes.py::test_dollar_and_double_slash_do_not_end_a_line`; `tests/grammar/xyce/test_xyce_structure.py::test_other_line_starts_are_rejected` |
| Reads a bracketed node such as `[s]` as a node literally named `[s]`. | Writes a named BJT substrate in square brackets, `[substrate node]` (`[xyce-ref] §2.3.17 p241`), where the brackets elsewhere in the manual mark an optional field. | Not read in X-M0 (a Q line is `UnsupportedConstruct`); decided in X-M4. | `tests/solver/test_xyce_structure_probes.py::test_a_bracketed_node_is_a_literal_node_name`; `tests/grammar/xyce/test_xyce_structure.py::test_every_element_line_is_unsupported` |

## Where the manual is silent

| Xyce 7.10 | Library behaviour | Evidence |
|---|---|---|
| Reads a blank first line as the title, so the netlist starts on line 2. | The same: an empty title (`XY-TTL-001`). | `tests/solver/test_xyce_structure_probes.py::test_a_blank_line_one_is_the_title`; `tests/grammar/xyce/test_xyce_structure.py::test_the_first_line_is_always_the_title` |
