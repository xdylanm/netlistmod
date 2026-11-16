# Xyce grammar

The Xyce grammar ([decision 0026](../../decisions/0026-the-xyce-dialect.md), the
[xyce plan](../../design/xyce-plan.md)) and its conformance records:

- [Device-letter matrix](./devices.md) and its packaged
  [machine-readable source](../../../src/netlistmod/grammar/xyce-devices.json).
- [Numbers and values](./numbers.md).
- [Spec entries](./specs/) cite the manuals and link to tests.
- [Names](./names.md) and [scoping](./scoping.md) rules of the document layer.
- [Discrepancies](./discrepancies.md) records where Xyce, its manuals and the library differ.

The manuals for this dialect are the Xyce Reference Guide and Users' Guide, Version 7.10, cited as
`[xyce-ref] §<section> p<page> "<title>"` and `[xyce-ug] §<section> p<page> "<title>"`
([references.md](../../references.md)). They are paraphrased, never copied. Xyce is GPLv3: its
source code, and the headers installed with it, are never read (P10, architecture §12). The
solver evidence is generated at test time and never committed (xm0-tasks decision 2).
`core_rules` in an entry names the shared rules of `core.lark` it relies on; `grammar` names the
rules of `xyce.lark`.

## A hidden dialect

Until the X-M8 review the dialect is not a member of `Dialect`: it is the internal
`netlistmod.dialects._XYCE`, a `Dialect` instance that iteration, `Dialect("xyce")`,
`Dialect["XYCE"]` and `Dialect.from_name` do not find, and that no public `__all__` binds
(`tests/architecture/test_hidden_dialects.py`). It is passed wherever a dialect is, for example
`Netlist.from_text(text, dialect=_XYCE)`. It cannot be pickled. X-M8 makes it the member
`Dialect.XYCE`.
The node classes only xyce has (`IndentedLine`, `PreprocessDirective`) live in
`netlistmod.model.nodes` and are not exported from `netlistmod` until then.

## What the dialect reads

X-M0 read the structure of a netlist (decision 0026). X-M1 (decision 0027) adds, task by task:

- **B2, structure, names and numbers:**
  - the title, line 1, whatever it holds, even when it is blank (`XY-TTL-001`);
  - comments: `*` lines, lines that begin with `;`, and `;` at the end of any line, the `.END`
    line included (`XY-COM-001`, `XY-END-001`);
  - indented lines, which Xyce reads as comments: a node of their own kind, `IndentedLine`, which
    the document layer reports with `INDENTED_LINE_IGNORED` (`XY-IND-001`; decision X-D1);
  - `+` continuation lines, across blank, comment and indented lines, which then belong to the
    statement (`XY-CNT-001`);
  - the final `.END`, required, with only blank lines after it (`XY-END-001`);
  - the name class and the node-field terminal (`XY-NAM-001`), `.GLOBAL` (`XY-GLB-001`) and
    `.PREPROCESS REPLACEGROUND` (`XY-PRE-001`); ground, `$G` globals and case are rules of
    [names.md](./names.md);
  - the two number readers, for device fields and for expressions (`XY-NUM-001`, `XY-NUM-002`;
    [numbers.md](./numbers.md)).

Every other line is refused (`XY-UNS-001`): an element line is `UnsupportedConstruct`, naming the
milestone of its letter ([devices.md](./devices.md)); A and N, not Xyce letters, are a
`ParseError`; a dot-command the dialect does not read yet, and a `.PREPROCESS` form other than
REPLACEGROUND, are `UnsupportedConstruct`. A `+` line with only the title, comments and blank
lines before it joins nothing and is a `ParseError`, as on Xyce. `$` and `//` are not comments, so
at the start of a line they are a `ParseError`. `rkm=True` is a `ValueError`.

Where Xyce is more lenient than the manual, the difference is a row of
[discrepancies.md](./discrepancies.md): Xyce runs without `.END`, ignores text after it and on its
line, warns on an unknown dot-command and ignores it, takes commas in `.GLOBAL`, `"` and non-ASCII
in names, and a few number forms that no list holds.

The rest is planned by task and milestone in [xm1-tasks.md](../../design/xm1-tasks.md) and the
xyce plan, section 8: parameters and expressions (B3), statements (B4) and the first elements (B5)
in X-M1, directives in X-M2, then the remaining devices.

## Validation status

Status words have the meanings of
[decision 0008](../../decisions/0008-validation-status-and-solver-harnesses.md);
`tests/architecture/test_spec_coverage.py` checks each against its evidence and this table against
the entries. The probes (`tests/solver/test_xyce_*.py`) ran on XyceNF Release 7.10.0, which each
entry records under `validated_on`. An entry they confirm is validated, and one whose reading rests
only on the binary is observed; `XY-UNS-001` is a refusal of the library's own, which solver
evidence cannot decide. "Tests" counts an entry's test references: those outside `tests/solver/`,
then the solver probes, which run only where the solver is installed. The table and its totals line
are the output of `python -m tests.support.spec_coverage xyce`.

| Entry | Construct | Status | Tests | Validated on |
|---|---|---|---|---|
| [XY-CNT-001](./specs/XY-CNT-001.yaml) | `+` continuation lines, across blank, comment and indented lines | validated | 6 + 4 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-COM-001](./specs/XY-COM-001.yaml) | comments (`*` lines, `;` lines and `;` at the end of a line) | validated | 3 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-END-001](./specs/XY-END-001.yaml) | required final .END statement | validated | 4 + 4 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-GLB-001](./specs/XY-GLB-001.yaml) | .GLOBAL node names | validated | 4 + 1 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-IND-001](./specs/XY-IND-001.yaml) | indented lines (a comment to Xyce, decision X-D1) | validated | 3 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-NAM-001](./specs/XY-NAM-001.yaml) | node and device names (legal characters) | validated | 4 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-NUM-001](./specs/XY-NUM-001.yaml) | numbers in device fields (scale factors and units) | observed | 2 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-NUM-002](./specs/XY-NUM-002.yaml) | numbers in expressions and .PARAM values (units and the imaginary J) | observed | 2 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-PRE-001](./specs/XY-PRE-001.yaml) | .PREPROCESS REPLACEGROUND TRUE\|FALSE | validated | 7 + 5 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-STR-001](./specs/XY-STR-001.yaml) | netlist structure (title line, body lines, blank lines, final .END) | validated | 4 + 2 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-TTL-001](./specs/XY-TTL-001.yaml) | first-line title | validated | 1 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-UNS-001](./specs/XY-UNS-001.yaml) | lines the dialect does not read yet (element lines, the other dot-commands and .PREPROCESS forms, `+` lines after a refused dot-command) | documented | 9 + 0 solver |  |

12 entries: 9 validated, 2 observed, 0 disputed, 1 documented.

## Lookaround terminals

As for ngspice ([ngspice README](../ngspice/README.md#lookaround-terminals)): Lark's strict mode
skips these terminals in its collision check, and `UNCHECKED_TERMINALS` in
`tests/architecture/test_contracts.py` lists them. Each was reviewed by hand (Lark 1.3.1; X-M0, and
X-M1 B2 for the changed and new ones). `.N` is a terminal's priority; the state counts are parse
states. The grammar has no block, so no block state.

| Terminal | Matches | Candidate in | Competitors | Why no collision |
|---|---|---|---|---|
| `COMMENT_LINE.3` | `*` or `;`, then text to the end of the line | 38 states: line starts | above: `INDENTED_LINE.10`, `WS`, `LINE_END`; `END_KW.4`, `DOT_NAME.4`, `PREPROCESS_KW.4`, `GLOBAL_KW.4`; at its priority: `PLUS_LINE.3` | Only it starts with `*` or `;`, and `INDENTED_LINE` excludes a `*` or `;` after the blanks, so an indented `*` or `;` line is a comment. |
| `INDENTED_LINE.10` | blanks, then a character other than a blank, `+`, `*` or `;`, then text to the end of the line | 38 states: line starts | `COMMENT_LINE`, `PLUS_LINE`, the keywords, `DOT_NAME`, `LINE_END`; below: `WS.9` | No competitor at its priority; it outranks `WS`, so an indented line is one token, and a line of blanks, which it cannot match, is still `WS` and `LINE_END`. Nothing else starts with a blank. |
| `PLUS_LINE.3` | `+` to the end of the line | 32 states: line starts after a statement | as `COMMENT_LINE` | Only it starts with `+`. It is reached only after a refused dot-command, whose `REST_TEXT` leaves the line end to `NL`: after a statement the dialect reads, `SEP` takes a `+` line, with or without comment lines before it. |
| `REST_TEXT.2` | a non-blank, then text to the end of the line | 9 states: after a refused dot-command or `.PREPROCESS` form | `NL`, `CONT`, `WS` | No competitor at its priority, and only line ends compete. |
| `TITLE_TEXT.2` | as in ngspice | 1 state: line 1 | `LINE_END`, `WS` | No competitor at its priority; Xyce has no `TITLE_KW`. |
| `SEP.10` | blanks; a line end and a `+` line's `+`; or a line end whose lookahead finds blank, comment or indented lines and then a `+` line | 27 states: before a field and at the end of a statement | `NL.5`, `CONT.7` (ignored), `WS.9` (ignored); above: `TRAILING_COMMENT.12`; below: the field tokens | It outranks `NL` and `CONT`, so a line end that a `+` line joins is a separator; the third alternative matches only when a `+` line follows the skipped lines, so any other line end stays `NL` and ends the statement. Field tokens never start with a blank or a line end. |
| `TRAILING_COMMENT.12` | `;` to the end of the line; or, right after a line end (a lookbehind), a `*` line or an indented line other than a `+` line | 28 states: in a statement's gaps, and after `.END` | `SEP.10`, `NL`, `LINE_END`, the field tokens | Its `;` alternative: no field token holds `;`. Its other alternatives match only right after a line end, which in a gap only `SEP`'s third alternative leaves, so they are the skipped lines; it outranks `SEP`, so an indented skipped line is one comment rather than `SEP` and a field. A blank skipped line, which it cannot match, is part of a `SEP`. |
