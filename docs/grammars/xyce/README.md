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

## What X-M0 reads

Only the structure of a netlist (decision 0026):

- the title, line 1, whatever it holds, even when it is blank (`XY-TTL-001`);
- `*` comment lines, also after blanks (`XY-COM-001`), and blank lines (`XY-STR-001`);
- the final `.END`, in any case, with only blank lines after it (`XY-END-001`).

Every other line is refused (`XY-UNS-001`): an element line is `UnsupportedConstruct`, naming the
milestone of its letter ([devices.md](./devices.md)); A and N, not Xyce letters, are a
`ParseError`; a dot-command other than `.END` and an indented line (a comment to Xyce, decision
X-D1) are `UnsupportedConstruct`. `;`, `$`, `//` and `+` at the start of a line are a `ParseError`.
`rkm=True` is a `ValueError`. The only ground is `0` ([names.md](./names.md) N1).

What the X-M0 probes found on XyceNF Release 7.10.0 (xm0-tasks 5.1 point 4) is in the spec
entries and [discrepancies.md](./discrepancies.md): line 1 is always the title; an indented line is
a silent comment; a `+` line joins the last non-comment line across comments and blank lines,
never the title; `0` is the only ground without `.PREPROCESS REPLACEGROUND`; Xyce runs without
`.END` and ignores text after it, warns on an unknown dot-command and ignores it, reads `[s]` as a
node literally named `[s]`, and stops on `$` and `//` after a statement.

The rest is planned by milestone in the xyce plan, section 8: names, numbers, continuation and the
first elements in X-M1, directives in X-M2, then the remaining devices.

## Validation status

Status words have the meanings of
[decision 0008](../../decisions/0008-validation-status-and-solver-harnesses.md);
`tests/architecture/test_spec_coverage.py` checks each against its evidence and this table against
the entries. The X-M0 probes ran on XyceNF Release 7.10.0, which each entry records under
`validated_on`; the entries stay documented until the probes are solver tests (task B4).
"Tests" counts an entry's test references: those outside `tests/solver/`, then the solver probes,
which run only where the solver is installed. The table and its totals line are the output of
`python -m tests.support.spec_coverage xyce`.

| Entry | Construct | Status | Tests | Validated on |
|---|---|---|---|---|
| [XY-COM-001](./specs/XY-COM-001.yaml) | full-line star comments | validated | 1 + 2 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-END-001](./specs/XY-END-001.yaml) | required final .END statement | documented | 3 + 0 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-STR-001](./specs/XY-STR-001.yaml) | netlist structure (title line, body lines, blank lines, final .END) | validated | 3 + 2 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-TTL-001](./specs/XY-TTL-001.yaml) | first-line title | validated | 1 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-UNS-001](./specs/XY-UNS-001.yaml) | lines X-M0 does not read (element lines, dot-commands other than .END, indented lines) | documented | 6 + 0 solver |  |

5 entries: 3 validated, 0 observed, 0 disputed, 2 documented.

## Lookaround terminals

As for ngspice ([ngspice README](../ngspice/README.md#lookaround-terminals)): Lark's strict mode
skips these terminals in its collision check, and `UNCHECKED_TERMINALS` in
`tests/architecture/test_contracts.py` lists them. Each was reviewed by hand in X-M0 (Lark 1.3.1).
`.N` is a terminal's priority. The grammar has no block, so no block state.

| Terminal | Matches | Candidate in | Competitors | Why no collision |
|---|---|---|---|---|
| `COMMENT_LINE.3` | `*` to the end of the line (core) | 13 states: line starts | above: `INDENTED_LINE.10`, `WS`, `LINE_END`; `END_KW.4`, `DOT_NAME.4` | No competitor at its priority; only it starts with `*`, and `INDENTED_LINE` excludes a `*` after the blanks, so an indented `*` line is a comment. |
| `INDENTED_LINE.10` | blanks, then a character other than a blank, `+` or `*`, then text to the end of the line | 13 states: line starts | `COMMENT_LINE`, `END_KW`, `DOT_NAME`, `LINE_END`; below: `WS.9` | No competitor at its priority; it outranks `WS`, so an indented line is one token, and a line of blanks, which it cannot match, is still `WS` and `LINE_END`. Nothing else starts with a blank. |
| `REST_TEXT.2` | a non-blank, then text to the end of the line | 4 states: after a refused dot-command | `NL`, `CONT`, `WS` | No competitor at its priority, and only line ends compete. |
| `TITLE_TEXT.2` | as in ngspice | 1 state: line 1 | `LINE_END`, `WS` | No competitor at its priority; Xyce has no `TITLE_KW`. |
