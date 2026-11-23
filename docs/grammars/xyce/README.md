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
The node classes only xyce has (`IndentedLine`, `PreprocessDirective`, `GlobalParamStatement`,
`FuncStatement`, `LibCall`, `PrintDirective`, and the value `FunctionDefinition`) live in `netlistmod.model` and are
not exported from `netlistmod` until then.

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

- **B3, parameters and expressions:**
  - `.PARAM` assignments and function assignments, with blanks or commas (`XY-PRM-001`),
    `.GLOBAL_PARAM` (`XY-PRM-002`) and `.FUNC` (`XY-FUN-001`);
  - values in braces, in single quotes, or bare without blanks (`XY-VAL-001`; decision X-D5);
  - the formula grammar `formula_xyce.lark` and its reserved words (`XY-FML-001`), and the
    scoping rules of [scoping.md](./scoping.md).

- **B4, statements:**
  - `.SUBCKT`/`.ENDS`, with at least one port other than `0`, optional `PARAMS:` defaults
    without commas, and nesting (`XY-SBD-001`); `.GLOBAL`, `.GLOBAL_PARAM` and `.END` are refused
    in a body;
  - `.MODEL`, its parameters with or without one pair of parentheses and no comma, a repeated
    parameter refused, and xyce's own model types (`XY-MOD-001`);
  - `.INC`, `.INCL` and `.INCLUDE`, opaque, with one path (`XY-INC-001`);
  - `.LIB`: a call with a file and entries, opaque, or a definition block closed by `.ENDL` and
    its name (`XY-LIB-001`).

- **B5, elements** (R, C, L, K, D, V, I and X; [devices.md](./devices.md)):
  - the fields they share: node fields that may hold a `:` path into an instance, instance
    parameters with bare values without blanks, and no comma (`XY-ELM-001`);
  - R, C and L with the model right after the nodes, then the value, positional or `R=`, `C=`,
    `L=`; C's charge `Q=`; R's and C's geometry forms; the ngspice order refused with a hint
    (`XY-RCL-001`);
  - K with an optional CORE model after the coupling (`XY-MUT-001`), D with its model, an
    optional positional area, flags and parameters (`XY-DIO-001`);
  - V and I with their DC and AC parts (`XY-SRC-001`; the transient functions from X-M3, `XY-SRC-002` to `XY-SRC-004`);
  - X with optional `PARAMS:` and `M=` (`XY-SUB-001`).

- **B7, the instance-parameter lists:** R, C, L and D take only the names of their
  instance-parameter tables, for every level of the device, in any case, and refuse any other
  name at the name, as Xyce stops on it (`XY-IPN-001`; xm1-tasks 5.1 point 29). X's parameters
  are the subcircuit's and stay open; K, V and I take none.

- **B7, the corpus:** `tests/corpus/xyce/` holds authored netlists with manifests: accept families
  (`structure_basic`, `statements_basic`, `elements_basic`, with CRLF twins) that cover every
  construct above, round-trip byte for byte and run in Xyce with an `.op` added, and rejection
  families (`*_rejects`) whose manifests give each refusal's position and kind and Xyce's own
  outcome (`tests/grammar/xyce/test_xyce_corpus.py`, `tests/solver/test_xyce_solver_corpus.py`).

X-M2 ([decision 0028](../../decisions/0028-xyce-directives.md)) adds:

- **B2, analyses and sweeps**, top level only (Xyce ignores them in a body, so there they are a
  `ParseError`):
  - `.TRAN tstep tstop [tstart [tmax]] [NOOP] [UIC] [{schedule(...)}]`, the manual's form, a
    repeated flag refused (`XY-TRN-001`);
  - `.AC LIN|OCT|DEC points fstart fstop` (`XY-ACA-001`), `.DC` with any number of sweeps, each
    with its own `LIN`, `DEC`, `OCT` or `LIST` of at least two values (`XY-DCA-001`), and
    `DATA=table` on `.AC`, `.DC` and `.STEP` (`XY-DCA-002`);
  - `.OP`, with no fields (`XY-OPP-001`);
  - `.STEP`, one sweep per line, plain numbers only, no `param` keyword (`XY-STP-001`), and the
    sweep targets of `.DC` and `.STEP`, which may hold `:` (`XY-STP-002`).

- **B3, options, initial conditions, measurements and the `.DATA` block:**
  - `.OPTIONS` and `.OPTION` with a package of the manual's 21, in any case; any other word, a
    missing package or a package with no item is a `ParseError` with a hint, except
    `.OPTION SCALE=v` (`XY-OPT-001`); `name=value` items whose value is a number, a word or a comma
    list, braces and quotes only in SAMPLES and EMBEDDEDSAMPLES, and OUTPUT's and RESTART's
    `INITIAL_INTERVAL` pairs (`XY-OPT-002`); top level only;
  - `.IC` and `.DCVOLT` (`XY-ICN-001`) and `.NODESET` (`XY-NOD-001`): `V(node)=value` or `node value`
    pairs, one form per statement, nodes with `:` paths and `$G` names; allowed in a subcircuit
    body, where Xyce applies them in every instance;
  - `.MEASURE` and `.MEAS`, typed shallowly, with a required mode of the closed list
    (`XY-MEA-001`); top level only;
  - the `.DATA name columns... values... .ENDDATA` table, an opaque block with plain numbers in a
    non-zero multiple of the columns and a bare `.ENDDATA` (`XY-DAT-001`); top level only.

- **B4, the closed list of dot-commands, and directives in a body:**
  - `.FOUR`, `.FFT`, `.RESULT`, `.SAVE`, `.SENS`, `.NOISE`, `.HB`, `.LIN`, `.SAMPLING`,
    `.EMBEDDEDSAMPLING` and `.PCE`, in any case, read as `UnknownDirective` with
    `UNTYPED_DIRECTIVE_PRESERVED` (info), continued by `+` lines, top level only (`XY-DIR-001`;
    `.PRINT` was one until X-M2.1); `.SAVE` is never ngspice's `SaveDirective` (`XY-SAV-001`);
  - any other dot-command is a `ParseError` "not an Xyce dot-command", at its first character, so
    the lines of a would-be block are never read, with hints for `.TEMP`, `.PROBE`, `.title` and
    `.opt` (`XY-DIR-002`);
  - `.PREPROCESS ADDRESISTORS ONETERMINAL|NODCPATH value`, an `UnknownDirective` allowed in a body,
    one of each kind per netlist; any other word after `.PREPROCESS` is a `ParseError`
    (`XY-PRE-002`);
  - in a subcircuit body the analyses, `.STEP`, `.OPTIONS`, `.MEAS`, `.DATA` and the untyped
    commands are a `ParseError` saying Xyce silently ignores them there; `.IC`, `.DCVOLT`,
    `.NODESET` and `.PREPROCESS` are allowed (`XY-DIR-003`).

- **B6, the evidence:** the solver tests `tests/solver/test_xyce_analysis_probes.py`,
  `test_xyce_directive_probes.py` and `test_xyce_closed_list_probes.py` run each X-M2 construct
  and each claim a diagnostic makes about Xyce; the corpus families `directives_basic` (with a
  CRLF twin, and `sampling.cir`, which runs without `-r`) and `directives_rejects`; the X-M2
  entries are `validated`, or `observed` where the reading rests on the binary (`.OPTION` as a
  synonym, the measure modes against the analysis that runs, `.NOISE` in the last-line rule;
  X-M2.1 adds `.HB` to the rule, `tests/solver/test_xyce_analysis_probes.py`).
  The refusals of `.IC`/`.DCVOLT`/`.NODESET` fields now say per keyword what Xyce does, and a
  package-less `TEMP=` or `TNOM=` gets the DEVICE hint.

X-M2.1 ([decision 0029](../../decisions/0029-xyce-discrepancy-categories.md) item 5) types
`.PRINT` shallowly, as `.MEAS` is: `PrintDirective` (internal) with a required print type of the
manual's closed list (AC, AC_IC, DC, ES, HB, HB_FD, HB_IC, HB_STARTUP, HB_TD, NOISE, PCE, TRAN,
HOMOTOPY, SENS and TRANADJOINT, in any case), then the rest as text, at least one field, continued
by `+` lines, top level only; `TR`, another word, no type or no field is a `ParseError`
(`XY-PRT-001`). `PRINT_TYPE_MISMATCH` (warning) reports a type that does not agree with the first
analysis line other than `.OP`, on which Xyce stops, and an analysis's type whose analysis does
not run, for which Xyce writes nothing (`tests/solver/test_xyce_print_probes.py`).

X-M3 ([decision 0030](../../decisions/0030-xyce-stimulus-and-port.md)) reads the transient
functions and the port:

- **The functions** of V and I, the line's last field, after the DC and AC parts, at most one:
  PULSE, SIN, EXP and SFFM (`XY-SRC-002`), PAT, whose DATA bit string is an `Identifier` in
  `SourceSpec.args` and whose repeat count is `R=` after the list (`XY-SRC-003`), and PWL, with
  time-value pairs or `FILE` and a double-quoted or bare path (held as the parameter `FILE`,
  never read, with no file reference), then `TD=` and `R=` (`XY-SRC-004`). The parentheses are
  optional and balanced; the arguments are blank-separated numbers or braced or quoted
  expressions; each function's count is checked. A comma, a `name=` argument, a positional PAT
  repeat count (hint `R=`) and an odd PWL count are a `ParseError` with their own messages.
- **The P port** (`XY-POR-001`): `PortSource` (internal), a sibling of V and I, with `port=` and
  `Z0=` in `params`, between the DC and AC parts in either order; `port=` is required and is an
  integer of 1 or more or a formula. P is allowed in a subcircuit body.
- **The edits:** the source edits work on P (`set_ac` and `set_stimulus` insert after `port=` and
  `Z0=`; `set_param` takes `port` and `z0`; `remove_param` refuses `port`); on xyce
  `set_stimulus_arg` adds only PWL's `TD=` and `R=` and PAT's `R=` by name.
- **The evidence:** `tests/solver/test_xyce_source_probes.py` and
  `tests/solver/test_xyce_port_probes.py`, and the corpus families `sources_basic` (with a CRLF
  twin, and `wave.csv` for PWL FILE) and `sources_rejects`. Under `.HB` a DC sweep uses a function
  source's time-0 value, and `.LIN` needs the ports numbered 1..N: rows, with no diagnostic.

X-M4 ([decision 0031](../../decisions/0031-xyce-transistors.md)) reads the transistors Q, M, J and Z
(B2 and B3):

- **The line shape** (`XY-XTR-001`): the fixed nodes, then names, the last of which is the model
  (decision 0014 item 1); a name field is a node field, so `[s]` and `X1:n` are nodes; a number is
  a node before the model and the area after it; `off` right after the fixed nodes is a node. A
  number, `off` or a `:` in the model's place is refused. The area is positional, right after the
  model and before any flag or parameter (where it is a `ParseError`), or `area=`, not both.
- **Q** (`XY-BJT-001`): 3 to 5 nodes, a 6th a `ParseError`; `OFF` or `OFF=`; `IC=` a comma list of
  at most two values; the closed list of the BJT levels' instance tables.
- **M** (`XY-MOS-001`): 3 to 7 nodes, an 8th a `ParseError`; no area (a number or expression after
  the model and `area=` are refused); `OFF` or `OFF=`; `IC=` a comma list of at most five values;
  `TNODEOUT=` a listed parameter, a bare `TNODEOUT` refused with the hint `TNODEOUT=1`; ngspice's
  `thermal` refused; the closed list of the MOSFET levels' instance tables (125 names and `IC`).
- **J and Z** (`XY-JFT-001`, `XY-MES-001`): exactly 3 nodes; `area=`, `dtemp=` and `temp=` only;
  no flag, no `M=`, no `IC=`. A parameter written twice is a `ParseError` on all four letters.

Every other line is refused (`XY-UNS-001`): an element line of another letter is
`UnsupportedConstruct`, naming the milestone of its letter ([devices.md](./devices.md)); A and N, not Xyce letters, are a
`ParseError`; `.PREPROCESS REMOVEUNUSED` is read since X-M4, as an `UnknownDirective` (`XY-PRE-003`). A `+` line with only the title, comments and blank
lines before it joins nothing and is a `ParseError`, as on Xyce. `$` and `//` are not comments, so
at the start of a line they are a `ParseError`. `rkm=True` is a `ValueError`.

Every difference between the manuals, Xyce and the library is a row of
[discrepancies.md](./discrepancies.md), with a category that says which side the library follows
([decision 0029](../../decisions/0029-xyce-discrepancy-categories.md)): `manual` (the manual is
precise, Xyce lenient or buggy), `imprecise` (Xyce fills a gap in the manual), `manual-error`
(the manual is wrong; the library follows Xyce) or `library-limit` (the library's model cannot
express or check the form). Its sections sort the rows by what the library does beside Xyce:

- **Xyce runs, the library refuses** (`manual`, `imprecise`): Xyce runs without `.END`, ignores
  text after it and on its line, warns on an unknown dot-command and ignores it, takes commas in
  `.GLOBAL`, `"` and non-ASCII in names, a few number forms that no list holds, blanks in a bare
  `.PARAM` value, a blank before a function's `(`, some reserved and built-in names, which it
  ignores, a second field on `.INC`, and, on element lines, the ngspice order of R, C and L, an R
  without a value, a value written twice, one inductor on K without a model, a number before D's
  model, a comma on a source line and `:` in a designator; on directives a repeated `.TRAN` flag,
  extra fields on `.OP`, a one-value `LIST`, two sweeps on one `.STEP` line, an unknown or a
  missing `.OPTIONS` package, a bare word after an option, the `TR` mode and print type, a
  `.PRINT` without an output variable, a table without its bare `.ENDDATA`, and directives in a
  body, which it silently ignores.
- **The manual and Xyce accept, the library refuses** (`library-limit`): a bare `AC`.
- **The library reads, Xyce stops on or ignores** (`manual`, `library-limit`): a schedule after
  tstart, the full `.TRAN` form and a zero-argument `.FUNC`, which the library reads as the manual
  writes them; `.PCE`; a `.PRINT` type that does not agree with the first analysis, which the
  manual says is not processed (`PRINT_TYPE_MISMATCH` warns); and what the library does not
  check: R's and D's parameter lists (the union of their levels' tables), the `DEC` and `OCT`
  point counts, ngspice's `.save v(2)`, a `_CONT` measure type and a `.PRINT` line's output
  variables.
- **The library follows Xyce against the manual** (`manual-error`): `//` is no comment, `µ` no
  scale factor, a bracketed `[s]` is a node name, a `.SUBCKT` needs a port, `PARAMS:` takes no
  comma, a one-field `.LIB` opens a block, a `.DATA` table needs its name, a repeated `.PARAM`
  resolves to the first definition, and two `.OPTIONS OUTPUT` lines both apply.
- **The manual is silent or imprecise** (`imprecise`): the readings that rest on Xyce alone.

The rest is planned by milestone in the xyce plan, section 8: the remaining devices, from X-M5.
The records of X-M1, X-M2, X-M2.1 and X-M3 are
[archive/xyce/xm1-tasks.md](../../design/archive/xyce/xm1-tasks.md),
[archive/xyce/xm2-tasks.md](../../design/archive/xyce/xm2-tasks.md),
[archive/xyce/xm2.1-tasks.md](../../design/archive/xyce/xm2.1-tasks.md) and
[archive/xyce/xm3-tasks.md](../../design/archive/xyce/xm3-tasks.md).

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
| [XY-ACA-001](./specs/XY-ACA-001.yaml) | .AC small-signal analysis (a sweep, or DATA=) | validated | 5 + 5 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-BJT-001](./specs/XY-BJT-001.yaml) | Q bipolar transistor lines (3 to 5 nodes, area, OFF, IC= and the closed parameter list) | documented | 8 + 0 solver |  |
| [XY-CNT-001](./specs/XY-CNT-001.yaml) | `+` continuation lines, across blank, comment and indented lines | validated | 7 + 4 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-COM-001](./specs/XY-COM-001.yaml) | comments (`*` lines, `;` lines and `;` at the end of a line) | validated | 3 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-DAT-001](./specs/XY-DAT-001.yaml) | the .DATA ... .ENDDATA table (an opaque named block) | validated | 9 + 7 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-DCA-001](./specs/XY-DCA-001.yaml) | .DC sweeps (any number, each LIN, DEC, OCT or LIST) | validated | 6 + 5 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-DCA-002](./specs/XY-DCA-002.yaml) | DATA=table on .AC, .DC and .STEP | validated | 6 + 6 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-DIO-001](./specs/XY-DIO-001.yaml) | D diode lines (model, positional area, flags and parameters) | validated | 4 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-DIR-001](./specs/XY-DIR-001.yaml) | the closed list's untyped dot-commands (.FOUR, .FFT, .RESULT, .SAVE, .SENS, .NOISE, .HB, .LIN, .SAMPLING, .EMBEDDEDSAMPLING, .PCE) as UnknownDirective | observed | 11 + 11 solver | xyce XyceNF Release 7.10.0 (2026-11-16, 2026-11-22) |
| [XY-DIR-002](./specs/XY-DIR-002.yaml) | any other dot-command is refused (not an Xyce dot-command), with hints | validated | 8 + 8 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-DIR-003](./specs/XY-DIR-003.yaml) | directives in a subcircuit body (the analyses, .STEP, .OPTIONS, .MEAS, .DATA and the untyped commands refused; .IC, .DCVOLT, .NODESET and .PREPROCESS allowed) | validated | 9 + 7 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-ELM-001](./specs/XY-ELM-001.yaml) | element fields (node fields with `:` paths, instance parameters with bare values) | validated | 5 + 4 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-END-001](./specs/XY-END-001.yaml) | required final .END statement | validated | 4 + 4 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-FML-001](./specs/XY-FML-001.yaml) | formula expression syntax for reference scans (formula_xyce.lark) | validated | 6 + 1 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-FUN-001](./specs/XY-FUN-001.yaml) | .FUNC user-defined functions | validated | 8 + 5 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-GLB-001](./specs/XY-GLB-001.yaml) | .GLOBAL node names | validated | 5 + 1 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-ICN-001](./specs/XY-ICN-001.yaml) | .IC and .DCVOLT initial conditions (V(node)=value or node value pairs) | validated | 9 + 10 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-INC-001](./specs/XY-INC-001.yaml) | .INC, .INCL and .INCLUDE | validated | 2 + 2 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-IND-001](./specs/XY-IND-001.yaml) | indented lines (a comment to Xyce, decision X-D1) | validated | 6 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-IPN-001](./specs/XY-IPN-001.yaml) | closed instance-parameter lists of R, C, L and D | validated | 9 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-JFT-001](./specs/XY-JFT-001.yaml) | J JFET lines (3 nodes, area and the closed parameter list) | documented | 7 + 0 solver |  |
| [XY-LIB-001](./specs/XY-LIB-001.yaml) | .LIB calls and .LIB/.ENDL definitions | validated | 7 + 4 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-MEA-001](./specs/XY-MEA-001.yaml) | .MEASURE and .MEAS (a required mode of the closed list; the body kept as text) | observed | 5 + 11 solver | xyce XyceNF Release 7.10.0 (2026-11-16, 2026-11-22) |
| [XY-MES-001](./specs/XY-MES-001.yaml) | Z MESFET lines (3 nodes, area and the closed parameter list) | documented | 6 + 0 solver |  |
| [XY-MOD-001](./specs/XY-MOD-001.yaml) | .MODEL statements (parameters with or without parentheses; xyce model types) | validated | 8 + 2 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-MOS-001](./specs/XY-MOS-001.yaml) | M MOSFET lines (3 to 7 nodes, no area, OFF, IC=, TNODEOUT= and the closed parameter list) | documented | 16 + 0 solver |  |
| [XY-MUT-001](./specs/XY-MUT-001.yaml) | K mutual inductors (coupling and optional CORE model) | validated | 4 + 4 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-NAM-001](./specs/XY-NAM-001.yaml) | node and device names (legal characters) | validated | 4 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-NOD-001](./specs/XY-NOD-001.yaml) | .NODESET (the forms of .IC) | validated | 6 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-NUM-001](./specs/XY-NUM-001.yaml) | numbers in device fields (scale factors and units) | observed | 2 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-NUM-002](./specs/XY-NUM-002.yaml) | numbers in expressions and .PARAM values (units and the imaginary J) | observed | 2 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-OPP-001](./specs/XY-OPP-001.yaml) | .OP operating point | validated | 4 + 4 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-OPT-001](./specs/XY-OPT-001.yaml) | .OPTIONS and .OPTION packages (the manual's closed list; .OPTION SCALE) | observed | 8 + 9 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-OPT-002](./specs/XY-OPT-002.yaml) | .OPTIONS items (name=value, comma lists, expressions in SAMPLES, INITIAL_INTERVAL pairs) | validated | 7 + 6 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-POR-001](./specs/XY-POR-001.yaml) | P port (`port=` and `Z0=` between the DC and AC parts) | validated | 10 + 8 solver | xyce XyceNF Release 7.10.0 (2026-11-22) |
| [XY-PRE-001](./specs/XY-PRE-001.yaml) | .PREPROCESS REPLACEGROUND TRUE\|FALSE | validated | 7 + 5 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-PRE-002](./specs/XY-PRE-002.yaml) | .PREPROCESS ADDRESISTORS ONETERMINAL\|NODCPATH value (an UnknownDirective), and any other .PREPROCESS word refused | validated | 6 + 4 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-PRE-003](./specs/XY-PRE-003.yaml) | .PREPROCESS REMOVEUNUSED with a comma list of C, D, I, L, M, Q, R and V (an UnknownDirective) | documented | 5 + 1 solver |  |
| [XY-PRM-001](./specs/XY-PRM-001.yaml) | .PARAM assignments and function assignments | validated | 9 + 5 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-PRM-002](./specs/XY-PRM-002.yaml) | .GLOBAL_PARAM | validated | 5 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-PRT-001](./specs/XY-PRT-001.yaml) | .PRINT (a required print type of the closed list; the rest kept as text) | observed | 17 + 15 solver | xyce XyceNF Release 7.10.0 (2026-11-21, 2026-11-22) |
| [XY-RCL-001](./specs/XY-RCL-001.yaml) | R, C and L lines (the model before the value; R=, C=, L= and Q=; the geometry forms) | validated | 17 + 8 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-SAV-001](./specs/XY-SAV-001.yaml) | .SAVE (an UnknownDirective, never a SaveDirective) | validated | 3 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-SBD-001](./specs/XY-SBD-001.yaml) | .SUBCKT/.ENDS subcircuit definitions (ports, `PARAMS` defaults, nesting) | validated | 19 + 7 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-SRC-001](./specs/XY-SRC-001.yaml) | V and I independent sources, DC and AC parts, then a transient function | validated | 4 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-SRC-002](./specs/XY-SRC-002.yaml) | transient source functions PULSE, SIN, EXP and SFFM, and the argument list shared by every function | validated | 13 + 7 solver | xyce XyceNF Release 7.10.0 (2026-11-22) |
| [XY-SRC-003](./specs/XY-SRC-003.yaml) | PAT pattern source function (the DATA bit string and `R=`) | validated | 7 + 6 solver | xyce XyceNF Release 7.10.0 (2026-11-22) |
| [XY-SRC-004](./specs/XY-SRC-004.yaml) | PWL piecewise linear source function (pairs or FILE, `TD=` and `R=`) | validated | 9 + 9 solver | xyce XyceNF Release 7.10.0 (2026-11-22) |
| [XY-STP-001](./specs/XY-STP-001.yaml) | .STEP parametric sweep (one sweep per line) | validated | 11 + 9 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-STP-002](./specs/XY-STP-002.yaml) | sweep targets of .DC and .STEP (names, `dev:param`, `model:param`, paths, TEMP) | validated | 4 + 5 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-STR-001](./specs/XY-STR-001.yaml) | netlist structure (title line, body lines, blank lines, final .END) | validated | 8 + 6 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-SUB-001](./specs/XY-SUB-001.yaml) | X subcircuit calls (nodes, optional `PARAMS`, `M=`) | validated | 4 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-TRN-001](./specs/XY-TRN-001.yaml) | .TRAN transient analysis (NOOP, UIC and a schedule) | validated | 10 + 9 solver | xyce XyceNF Release 7.10.0 (2026-11-16) |
| [XY-TTL-001](./specs/XY-TTL-001.yaml) | first-line title | validated | 1 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-UNS-001](./specs/XY-UNS-001.yaml) | lines the dialect does not read yet (element lines of a planned letter, `+` lines after a refused line) | documented | 9 + 0 solver |  |
| [XY-VAL-001](./specs/XY-VAL-001.yaml) | expression values (braces, single quotes, bare expressions without blanks) | validated | 4 + 3 solver | xyce XyceNF Release 7.10.0 (2026-11-15) |
| [XY-XTR-001](./specs/XY-XTR-001.yaml) | shared transistor line shape (Q, M, J, Z), with the model types, binned M models, the node count against the model's LEVEL and the area edits | documented | 30 + 0 solver |  |

57 entries: 44 validated, 6 observed, 0 disputed, 7 documented.

## Lookaround terminals

As for ngspice ([ngspice README](../ngspice/README.md#lookaround-terminals)): Lark's strict mode
skips these terminals in its collision check, and `UNCHECKED_TERMINALS` in
`tests/architecture/test_contracts.py` lists them. Each was reviewed by hand (Lark 1.3.1; X-M0, and
X-M1 B2 to B7 for the changed and new ones). `.N` is a terminal's priority; the state counts are
parse states. The blocks are a `.LIB` definition (B4) and a `.DATA` table (X-M2 B3).

| Terminal | Matches | Candidate in | Competitors | Why no collision |
|---|---|---|---|---|
| `COMMENT_LINE.3` | `*` or `;`, then text to the end of the line | 56 states: line starts | above: `INDENTED_LINE.10`, `WS`, `LINE_END`; `END_KW.4`, `DOT_NAME.4`, `PREPROCESS_KW.4`, `GLOBAL_KW.4`; at its priority: `PLUS_LINE.3` | Only it starts with `*` or `;`, and `INDENTED_LINE` excludes a `*` or `;` after the blanks, so an indented `*` or `;` line is a comment. |
| `INDENTED_LINE.10` | blanks, then a character other than a blank, `+`, `*` or `;`, then text to the end of the line | 56 states: line starts | `COMMENT_LINE`, `PLUS_LINE`, the keywords, `DOT_NAME`, `LINE_END`; below: `WS.9` | No competitor at its priority; it outranks `WS`, so an indented line is one token, and a line of blanks, which it cannot match, is still `WS` and `LINE_END`. Nothing else starts with a blank. |
| `PLUS_LINE.3` | `+` to the end of the line | 50 states: line starts after a statement | as `COMMENT_LINE` | Only it starts with `+`. It is reached only after a refused line (a statement refused in a body, and the other `REST_TEXT` refusals), whose `REST_TEXT` leaves the line end to `NL`: after a statement the dialect reads, `SEP` takes a `+` line, with or without comment lines before it. |
| `REST_TEXT.2` | a non-blank, then text to the end of the line | after a refused word of `.PREPROCESS REMOVEUNUSED` (X-M4 B4), another `.PREPROCESS` word or `ADDRESISTORS` kind (X-M2 B4), a statement refused in a subcircuit body, `.STEP`'s refused `param` and second sweep (X-M2 B2), and the refused `.IC` forms, `.MEASURE` mode and stray `.ENDDATA` (X-M2 B3) | `NL`, `CONT`, `WS` | No competitor at its priority, and only line ends compete. |
| `TITLE_TEXT.2` | as in ngspice | 1 state: line 1 | `LINE_END`, `WS` | No competitor at its priority; Xyce has no `TITLE_KW`. |
| `SEP.10` | blanks; a line end and a `+` line's `+`; or a line end whose lookahead finds blank, comment or indented lines and then a `+` line | 95 states: before a field and at the end of a statement | `NL.5`, `CONT.7` (ignored), `WS.9` (ignored); above: `TRAILING_COMMENT.12`; below: the field tokens | It outranks `NL` and `CONT`, so a line end that a `+` line joins is a separator; the third alternative matches only when a `+` line follows the skipped lines, so any other line end stays `NL` and ends the statement. Field tokens never start with a blank or a line end. |
| `TRAILING_COMMENT.12` | `;` to the end of the line; or, right after a line end (a lookbehind), a `*` line or an indented line other than a `+` line | 96 states: in a statement's gaps, and after `.END` | `SEP.10`, `NL`, `LINE_END`, the field tokens | Its `;` alternative: no field token holds `;`. Its other alternatives match only right after a line end, which in a gap only `SEP`'s third alternative leaves, so they are the skipped lines; it outranks `SEP`, so an indented skipped line is one comment rather than `SEP` and a field. A blank skipped line, which it cannot match, is part of a `SEP`. |
| `DOT_NAME.4` | one of the closed list's untyped commands (`.print`, `.four`, `.fft`, `.result`, `.sens`, `.noise`, `.hb`, `.lin`, `.sampling`, `.embeddedsampling`, `.pce`), in any case, when a blank, `;` or a line end follows (a lookahead; X-M2 B4) | line starts | the keywords (`END_KW.4`, `MODEL_KW.4`, `LIB_KW.4`, `PARAM_KW.4`, `PREPROCESS_KW.4`, …) and `XY_SAVE_KW.4` at its priority | Its words are none of the keywords' and no keyword is a prefix of one (`.lin` against `.lib`, `.pce` against `.param`), and the lookahead makes `.prints` or `.linx` no match, so such a word matches no terminal and is refused (XY-DIR-002). Lark now checks it for collisions; it was unchecked before B4, when it matched any dot-name but `.ends` and `.endl`. |
| `XY_SAVE_KW.4` | `.save` in any case, when a blank, `;` or a line end follows (a lookahead; X-M2 B4) | line starts | as `DOT_NAME` | As `DOT_NAME`, whose list it completes; core.lark's `SAVE_KW` is not imported, so `.save` is never ngspice's `save_stmt`. |
| `BLOCK_TEXT.2` | a non-blank, then text to the end of the line | the states of a `.LIB` definition's lines | `BLOCK_DOT_NAME.4`, `ENDL_KW.4`, `LINE_END`, `NL` | Reached only after the opening line's own NL (`lib_open_end`) and after a block line, states no statement shares, so no statement terminal competes; `BLOCK_DOT_NAME` outranks it at a line start, and `.endl` is re-typed to `ENDL_KW`. |
| `INST_KEY.3` | a letter or `_`, then name characters, when a `=` follows (a lookahead) | after an element's fixed fields | `WORD.2`, `NODE_WORD.2`; at its priority `NUMBER.3`, `PARAMS_KW.3`, `XFN_KW.3`, `PAT_KW.3`, `PWL_NAME_KW.3`; above: the parameter keywords below | It outranks the names, so a name before `=` is a parameter; it starts with a letter, so no number, and it holds no `:`, so no `PARAMS:`. On R, C, L and D it is the name outside the letter's list, which the keywords outrank. |
| `TC_KW.4`, `OFF_VALUE_KW.4` | `tc` or `off`, when a `=` follows | after R, C and L's fields; after D's model | `INST_KEY.3`; at their priority the parameter keywords below | They outrank `INST_KEY`, so `TC=` takes its list and `OFF=` is a flag; the lookahead keeps `tcx=` and `offset=` ordinary parameters. No list holds `tc` or `off`, so they meet no keyword. |
| `R_PARAM_KW.4`, `C_PARAM_KW.4`, `L_PARAM_KW.4`, `D_PARAM_KW.4` | one name of the letter's closed list, in any case, when a `=` follows (a lookahead) | after R, C and L's fields; after D's model | `INST_KEY.3`, `WORD.2`, `NODE_WORD.2`; at their priority `TC_KW.4` (R, C, L) or `OFF_VALUE_KW.4` (D) | Each is offered only after its own letter's fields, so they never meet each other. They outrank `INST_KEY`, so a listed name is a parameter and any other is `INST_KEY`, refused; the lookahead makes the name end at the `=`, so `l` never takes the start of `lg=` and `m` never the start of `mult=`. |
| `XFN_KW.3`, `PAT_KW.3`, `PWL_NAME_KW.3` | a function name (PULSE, SIN, EXP or SFFM; PAT; PWL), in any case, when a blank, `(`, `;` or a line end follows (a lookahead; X-M3 B2) | after a source's nodes, DC or AC part | `NUMBER.3`, `DC_KW.2`, `AC_KW.2` | A function name starts with a letter, so it never meets a number; the keywords are other words. The lookahead makes `SINE` and `PULSEX` no match, so they are refused. |
| `PAT_BITS.4` | `b` or `B` and a string of 0s and 1s, when a blank, `)`, `;` or a line end follows (a lookahead; X-M3 B2) | in PAT's list, and after a comma in any function's list (refused) | `NUMBER.3`, `BRACE_FORMULA.3`, `QUOTE_FORMULA.3`, `INST_KEY.3` | It starts with a letter, so it meets no number or expression; `INST_KEY` needs a `=`, which the lookahead refuses, so `b01=` is a name. |
| `PORT_KW.4`, `Z0_KW.4` | `port` or `z0`, in any case, when a `=` follows (a lookahead; X-M3 B3) | after a P line's nodes and DC part, and after `port=` or `Z0=` | `NUMBER.3`, `BRACE_FORMULA.3`, `QUOTE_FORMULA.3`, `DC_KW.2`, `AC_KW.2`, the function names | They start with a letter, so they meet no number or expression, and the keywords and function names are other words; the lookahead makes `port 1`, `Z0 100` and `zo=` no match, so each is refused. |
| `PWL_FILE_KW.4`, `TD_KW.4` | `file` when a blank, `;` or a line end follows; `td` when a `=` follows (lookaheads; X-M3 B2) | after PWL's name; after its list or path | `INST_KEY.3`, `NUMBER.3`; at their priority `R_VALUE_KW.4` | They outrank `INST_KEY`; the lookaheads leave `FILE=` to `INST_KEY`, refused with a hint, and make `td` end at its `=`. `R_VALUE_KW` is another word. |
| `RU_LETTER.3` | one of `c d i l m q r v`, in any case, when no name character follows (a lookahead; X-M4 B4) | 6 states: the letters of `.PREPROCESS REMOVEUNUSED`, after a blank, a `+` line or a comma | `WORD.2`, `BRACE_FORMULA.3`, `QUOTE_FORMULA.3` | It outranks `WORD`, and the lookahead makes it a whole field, so `RC` or `rx` is a `WORD` (refused), never a letter and a name; the expressions start with `{` or `'`. |
| `DATA_KW.4` | `data` in any case, when a `=` follows (a lookahead; X-M2 B2) | after `.AC`, after `.DC`, after `.STEP` | `NODE_WORD.2` (`.DC`, `.STEP`); `DEC_KW.2`, `OCT_KW.2`, `LIN_KW.2`; `STEP_PARAM_KW.3` (`.STEP`) | It outranks the target's `NODE_WORD`, and the lookahead leaves a target named `data` (`.DC data 0 1 1`) a name; `NODE_WORD` holds no `=`. The other keywords are other words. |
| `STEP_PARAM_KW.3` | `param` in any case, when blanks and a letter or `_` follow and that word is not `list` (a lookahead whose alternatives spell out every word but `list`, case-folded, with no nested lookaround, so Lark still checks it for collisions; X-M2 B2 and R1) | after `.STEP` | `NODE_WORD.2`, `DATA_KW.4`, `DEC_KW.2`, `OCT_KW.2`, `LIN_KW.2` | It outranks `NODE_WORD`, so `.STEP param x ...` is recognised, to be refused with a hint; the lookahead leaves a target named `param` a name before a number (`.STEP param 1 2 1`) and before `LIST` (`.STEP param LIST 1k 2k`, which Xyce runs as a sweep of a parameter `param`), while `.STEP param listx ...` is still refused. `DATA_KW` needs a `=`, which this lookahead cannot meet. |
| `SCHEDULE_FORMULA.4` | `{` or `'`, blanks, `schedule` in any case, blanks and `(`, then an expression to the closing delimiter (X-M2 B2) | after `.TRAN`'s keyword and tstep (to be refused), and after its tstop, tstart, tmax and flags | `BRACE_FORMULA.3`, `QUOTE_FORMULA.3`, `NUMBER.3`, `NOOP_KW.2`, `UIC_KW.2` | It outranks the expressions it is also one of, so a schedule there is the schedule field, not tstart or tmax; in tstep's and tstop's place it is offered only through `tran_early_schedule`, which refuses it (X-M2 R1; it was the transformer's before). It starts with a delimiter, so no number or keyword. |
| `OPT_PACKAGE_KW.4` | a package of the manual's 21, in any case, when a blank, `;` or a line end follows (a lookahead; X-M2 B3) | after `.OPTIONS` and `.OPTION` | `OPT_KEY.3`, `WORD.2` | It outranks `WORD`, so a listed package is read and any other word is `WORD`, refused with the closest package; its lookahead makes `nonlin_tran` and `device=1` other tokens, and leaves `nonlin` to `nonlin-tran`. |
| `OPT_KEY.3` | a letter or `_`, then name characters, when a `=` follows (a lookahead; X-M2 B3) | after `.OPTIONS`'s package and items | `WORD.2`, `NUMBER.3`, `BRACE_FORMULA.3`, `QUOTE_FORMULA.3`; above: `OPT_PACKAGE_KW.4` | It outranks `WORD`, so a name before `=` is an item and a bare word is `WORD`, refused; it starts with a letter or `_`, so it meets no number or expression. `OPT_PACKAGE_KW` cannot match before a `=`. |
| `ALL_KW.4` | `all` in any case, when a `=` follows (a lookahead; X-M2 B3) | at a condition of `.IC`, `.DCVOLT` and `.NODESET` | `NODE_WORD.2`; at its priority `V_OPEN.4`, `IC_CURRENT_OPEN.4` | It outranks `NODE_WORD`, so `all=` is recognised, to be refused; the lookahead leaves a node named `all` (`.IC all 1`) a name. `V(` and `I(` begin with other letters. |
| `MEAS_MODE_KW.4` | a mode of the closed list, in any case, when a blank, `;` or a line end follows (a lookahead; X-M2 B3) | after `.MEASURE` and `.MEAS` | `WORD.2` | It outranks `WORD`, so a listed mode is read and any other word (`TR`, `HB`, a result name) is `WORD`, refused; the lookahead makes `tran_x` a word, and the `_CONT` forms come first. |
| `BARE_FORMULA.5` | an expression without blanks: no `= , ; ( ) { } ' "` outside parentheses, `[<>!=]=`, parentheses three deep | 4 states: a `.PARAM` or `.GLOBAL_PARAM` value | `EXPR_NUMBER.3`, `BRACE_FORMULA.3`, `QUOTE_FORMULA.3` | Its lookahead refuses a word that begins like a number and runs to the end of the field, so a number is `EXPR_NUMBER`, and a refused number form is not an expression; braces and quotes cannot begin it. |
| `BLANK_TAIL.12` | blanks followed by something other than a blank, `,`, `;`, a line end or the next `name=` or `name(...)=`, then the rest of the line | 42 states: after a `.PARAM` or `.GLOBAL_PARAM` value | `SEP.10`, `CSEP.11`, `TRAILING_COMMENT.12`, `NL` | Its lookaheads leave every blank that `SEP` or `CSEP` may take before a field, a comment or a line end; `TRAILING_COMMENT` never starts with a blank there (its indented alternative needs a line end before it). |
