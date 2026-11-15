# Xyce manual, solver and library discrepancies

The library follows the manuals (architecture §11.3 rule 2;
[decision 0026](../../decisions/0026-the-xyce-dialect.md)). This file records what XyceNF Release
7.10.0 (Windows) does where it differs from the manuals, or where the library differs from either.
The rows come from the X-M0 probes (task A4, 2026-11-15; xm0-tasks 5.1 point 4). The probes become
solver tests in task B4, which adds them to the Evidence column; until then each row names the
library test that pins the library's side.

## Forms Xyce runs and the manual or the library rejects

| Xyce 7.10 | Manual | Library behaviour | Evidence |
|---|---|---|---|
| Runs a netlist without `.END`. | The last line must be `.END` (`[xyce-ug] §4.1.1 p40`, `§4.1.3.1 p42`). | `ParseError`: `.END` is required (`XY-END-001`), as on ngspice and LTspice. Whether X-M1 keeps this is decided there. | `tests/grammar/xyce/test_xyce_structure.py::test_end_is_required` |
| Ignores text after `.END`, element lines included. | `.END` marks the end of the netlist (`[xyce-ref] §2.1.6 p33`). | `ParseError`: only blank lines may follow `.END`. | `tests/grammar/xyce/test_xyce_structure.py::test_end_is_last_with_only_blank_lines_after_it` |
| Warns on an unknown dot-command and ignores the line; the body of an unknown block is read as ordinary lines. | Describes each command in `[xyce-ref]` §2.1 (p24–163) and says nothing of an unknown one. | `UnsupportedConstruct` for every dot-command but `.END` in X-M0 (`XY-UNS-001`). The closed list of dot-commands is X-M2's. | `tests/grammar/xyce/test_xyce_structure.py::test_every_other_dot_command_is_unsupported` |
| Reads an indented line as a silent comment, even an indented `.param` or `.END`. | Says the same (`[xyce-ug] §4.1.3.1 p43`, `[xyce-ref] §2.1.39.1 p163`). | An indented `*` line is a comment; any other indented line is `UnsupportedConstruct` until decision X-D1 (X-M1). An indented `.END` is not `.END`, so such a netlist has none. | `tests/grammar/xyce/test_xyce_structure.py::test_an_indented_line_is_unsupported` |
| Joins a `+` line to the last non-comment line, across comments and blank lines, but never to the title. | Says the same, without the title (`[xyce-ug] §4.1.3.2 p43`). | X-M0 reads no continuation: a `+` line after the title, a comment or a blank line is a `ParseError`, and one after a refused dot-command is part of its refusal. Continuation is X-M1's. | `tests/grammar/xyce/test_xyce_structure.py::test_other_line_starts_are_rejected`; `test_a_continued_dot_command_is_unsupported_whole` |

## Forms in the manuals that Xyce stops on

| Xyce 7.10 | Manual | Library behaviour | Evidence |
|---|---|---|---|
| Stops on `//` after a statement: it is not a comment. | The examples of `[xyce-ref] §2.2.3 p173` end `.print` lines with a `//` comment. | X-M0 refuses every line that could hold one; a `//` line is a `ParseError`. X-M1 follows the solver and the in-line comment rule of `[xyce-ug] §4.1.3.1 p43`, which names only `;`. | `tests/grammar/xyce/test_xyce_structure.py::test_other_line_starts_are_rejected` |
| Stops on `$` after a statement: it is not a comment, unlike on ngspice. | Names only `;` as an in-line comment (`[xyce-ug] §4.1.3.1 p43`, `[xyce-ref] §2.1.39.2 p163`). | As for `//`. | `tests/grammar/xyce/test_xyce_structure.py::test_other_line_starts_are_rejected` |
| Reads a bracketed node such as `[s]` as a node literally named `[s]`. | Writes a named BJT substrate in square brackets, `[substrate node]` (`[xyce-ref] §2.3.17 p241`), where the brackets elsewhere in the manual mark an optional field. | Not read in X-M0 (a Q line is `UnsupportedConstruct`); decided in X-M4. | `tests/grammar/xyce/test_xyce_structure.py::test_every_element_line_is_unsupported` |

## Where the manual is silent

| Xyce 7.10 | Library behaviour | Evidence |
|---|---|---|
| Reads a blank first line as the title, so the netlist starts on line 2. | The same: an empty title (`XY-TTL-001`). | `tests/grammar/xyce/test_xyce_structure.py::test_the_first_line_is_always_the_title` |
