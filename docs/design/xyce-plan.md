# xyce dialect plan (draft)

> **Status:** ACTIVE (2026-11-15; the roadmap for the xyce milestones: [X-M0](./archive/xyce/xm0-tasks.md), [X-M1](./archive/xyce/xm1-tasks.md), [X-M2](./archive/xyce/xm2-tasks.md), [X-M2.1](./archive/xyce/xm2.1-tasks.md); [X-M3](./archive/xyce/xm3-tasks.md); [X-M4](./xm4-tasks.md) active). Written in [M21](./archive/v1.0/m21-tasks.md) (P1) from reviews X1 and X2; for the maintainer's review. It plans work after 1.0 and changes nothing in the library.
> **Governed by:** [architecture.md](../architecture.md) §2, §6, §9.3, §10, §11 and §12, and the 1.0 contract of [decision 0024](../decisions/0024-the-1-0-public-api.md).

## 1. Summary

An xyce dialect fits the existing design. About 70% of its constructs reuse ngspice nodes, as they are or with small differences. No covered name, signature or exception class has to change (M21 section 5.1). Two documentation sentences are made before 1.0: that minor releases may add `Dialect` members, node classes, union members and `Literal` values; and that a designator need not be one token.

Five things do not fit the current model, and each needs a decision record in its milestone:
1. **The two-token Y-type designator** (`YMEMRISTOR mr1 …`).
2. **Nets that reach into an instance** (`X1:node`) on device lines and in B expressions.
3. **`$G…` global nodes.**
4. **Leading whitespace makes a line a comment.**
5. **Bare expressions** in `.param`, `.global_param` and instance `name=value`.

The solver is free and runs on Windows, so solver-backed tests (§10 T8, P8) are possible on the maintainer's machine. CI stays solver-free (decision 0011).

## 2. Sources

- **[xyce-ref]:** *Xyce Parallel Electronic Simulator Reference Guide*, Version 7.10, SAND2025-05993, May 2025. https://xyce.sandia.gov/download/2068/, linked from https://xyce.sandia.gov/documentation-tutorials/ as the current release. The errata page lists no 7.10 entries.
- **[xyce-ug]:** *Xyce Users' Guide*, Version 7.10, SAND2025-05995, May 2025. https://xyce.sandia.gov/download/1756/.
- Accessed 2026-11-14. Page numbers below are the printed ones. Content is paraphrased (§11.3 rule 4).
- **Manuals only** (m21 decision 5). Xyce is GPLv3, so its source code is never read (P10). Running the binary for tests is allowed. Whether Xyce raw output may be committed is decided in X-M0 (section 7).

## 3. Devices

Kinds: **reuse** (an existing node as it is), **reuse with differences**, **new node**, **exclusion candidate**.

| Letter or type | xyce form (paraphrased) | Source | Kind and notes |
|---|---|---|---|
| R | `R n+ n- [model] [value] [params]`; the value is optional when a model or `R=` gives it | ref §2.3.7 p201 | Reuse with differences: the model comes **before** the value (ngspice puts it after, §6.3 rule 14) |
| C | `C n+ n- [model] [value] [params]`; also `C={expr}` or a `Q={expr}` charge form | ref §2.3.4 p186 | Reuse with differences: model before value; `Q=` as on LTspice |
| L | `L n+ n- [model] <value> [params]` | ref §2.3.5 p191 | Reuse with differences: model before value |
| K | `K L1 [L2 …] <coupling> [model]`; with a CORE model one inductor is allowed and the L values count turns | ref §2.3.6 p194 | Reuse with differences: `MutualCoupling` gains a model reference (a field, best-effort) |
| D, J, Z, W, O | as on ngspice | ref §2.3.8 p207, §2.3.18 p286, §2.3.19 p290, §2.3.22 p762, §2.3.21 p760 | Reuse |
| V, I | `[[DC] v] [AC mag [ph]] [tran]`. Functions PULSE, SIN, EXP, **PAT**, PWL (also `PWL FILE "f"` with `TD=` and `R=`), SFFM; parentheses optional | ref §2.3.9 p221–225, §2.3.10 p226 | Reuse with differences: `PAT` is new; PWL repeats by `R=`/`TD=` |
| P | a port for `.LIN`: `P n+ n- [[DC] v] port=<n> [Z0=v] [AC …] [tran]` | ref §2.3.11 p231 | New node (source-like). The letter collides with ngspice's coupled line |
| E, G | gain; `VALUE={}` (`VOL` and `CUR` synonyms); `TABLE {expr} = …`, with the expression allowed unbraced; `POLY(n)` | ref §2.3.12 p232–233, §2.3.14 p235 | Reuse with differences: the unbraced TABLE expression |
| F, H | gain, which may be a brace expression; `POLY(n)` | ref §2.3.13 p234, §2.3.15 p237 | Reuse with differences |
| B | `V=expr` or `I=expr`; also `tablefile("f")` with a quoted string | ref §2.3.16 p238–240 | Reuse with differences |
| Q | `Q c b e [sub] <model> [area]`, 3 to 5 nodes; a named substrate is written in square brackets; VBIC and HICUM add a thermal node | ref §2.3.17 p241–242 | Reuse with differences: the manual brackets a named substrate, but Xyce 7.10 reads `[s]` as a node literally named `[s]` (X-M0 probe; a discrepancy for X-M4); the manual's VBIC example writes the thermal node unbracketed, which needs a probe |
| M | 4 nodes and a model; BSIM-SOI 4 to 7 nodes (a `TNODEOUT` flag changes the last node's meaning); MVS 3 or 5; `IC=` lists | ref §2.3.20 p292–294 | Reuse with differences: the node counts |
| S | (a) `S s+ s- c+ c- <model> [ON] [OFF]` (VSWITCH); (b) a generic `S s+ s- <model> [ON][OFF] CONTROL={expr}` (SWITCH model) | ref §2.3.22 p762, §2.3.23 p766 | (a) reuse; (b) a new form with two nodes, whose `CONTROL=` is edited with `set_expression` |
| T | `T a+ a- b+ b- Z0= [TD=] [F= [NL=]]`, `ZO` a synonym | ref §2.3.25 p769 | Reuse with differences |
| U | digital gates: `U <type>[(<n>)] <dpwr> <dgnd> <in>* <out>* <model>`, types INV, BUF, AND, NAND, OR, NOR, XOR, NXOR, DFF, JKFF, TFF, DLTCH, ADD; model DIG | ref §2.3.28 p775–777 | New node. Collides with ngspice's URC; xyce has no URC |
| X | `X [node]* <subckt> [PARAMS: n=v …]`; `M=` without `PARAMS:` | ref §2.3.33 p803 | Reuse with differences: `PARAMS:` on X (ngspice refuses it) |
| Y\<type\> | `Y<type> <name> [node]* <model>`; the name is unique only with the type | ref Table 2-35 p177–178, §2.3.29 p780 | **A new designator form** (section 6, decision X-D4). The letter collides with ngspice's TXL |
| YTRANSLINE, YDELAY, YLIN, YACC, YMEMRISTOR | lumped line; delay (four nodes, no model); linear N-port from a Touchstone file; accelerometer (three nodes, no model); memristor | ref §2.3.26 p771, §2.3.27 p773, §2.3.24 p767, §2.3.30 p785, §2.3.32 p797 | New nodes |
| YPGBR, YPGBS, YPGTR, YPGGB | power-grid devices, four or five nodes, no model | ref §2.3.31 p786–796 | Exclusion candidate (niche); decide in X-M7 |
| Y digital (YAND, YNOT, …), deprecated | which nodes appear depends on the model card | ref §2.3.29 p780–782 | Exclusion candidate: the library cannot see the model card |
| YPDE | TCAD device with its own brace-list sublanguage | ref §2.4 p805 | Exclusion candidate, as ngspice's digital U and LTspice's `.machine` are (decision 0020) |
| A, N | not xyce letters | ref Table 2-35 | `ParseError` |

Model types for `model-types.json`: R/RES, C/CAP, L/IND, CORE, D, NPN, PNP, NJF, PJF, NMF, PMF, NMOS, PMOS, LTRA, VSWITCH, ISWITCH, SWITCH, DIG, LIN, TRANSLINE, MEMRISTOR, ZOD. `.model` names may contain `.` for binning (`nch.1`), and an instance's `nch` selects among them (ref §2.1.21 p89–90).

## 4. Statements

| Command | Notes | Source | Kind |
|---|---|---|---|
| `.OP`, `.ENDS`, `.GLOBAL`, `.IC`, `.NODESET`, `.MEASURE` | as on ngspice (`.DCVOLT` is a synonym of `.IC`) | ref §2.1 | Reuse |
| `.TRAN` | `NOOP`, `UIC` (a synonym of `NOOP`, as §2.1.38 says; Table 6-1's "ignored with a warning" is stale, X-M2 point 8), a `{schedule(…)}` argument | ref §2.1.38 p161 | Reuse with differences |
| `.AC`, `.DC` | `DATA=<table>`; `.DC` takes any number of sweeps, `LIST` | ref §2.1.1 p24, §2.1.3 p27 | Reuse with differences |
| `.STEP` | one sweep per line, no `param` keyword; sweeps a device, `dev:param`, `model:param`, `TEMP` or a parameter; `LIST`, `DATA=` | ref §2.1.36 p155–158 | Reuse with differences (`StepDirective.kind` gains values) |
| `.PARAM` | values braced, quoted or **bare**; functions (`f(x)={…}`); commas optional; complex `1+2J` | ref §2.1.26 p120, §2.2.1 p172 | Reuse with differences (decision X-D5) |
| `.GLOBAL_PARAM` | top level only; a top-level `.param` is equivalent | ref §2.1.12 p45–46 | Reuse of `ParamStatement` with a new keyword |
| `.FUNC` | `.FUNC f(args) [=] {body}`, scoped like `.param` | ref §2.1.10 p42–43 | New node |
| `.MODEL` | parentheses only around all parameters; no commas; binning | ref §2.1.21 p89 | Reuse with differences |
| `.SUBCKT` | nested definitions; `PARAMS:` with commas; node 0 is not a port | ref §2.1.37 p159–160 | Reuse with differences |
| `.INC`, `.INCLUDE`, `.INCL` | quotes optional | ref §2.1.15 p49 | Opaque statement, a third spelling |
| `.LIB` | a call `file entry [entry …]`, or a block `.LIB entry … .ENDL entry` | ref §2.1.16 p50–51 | Opaque; telling the two apart is a grammar question |
| `.OPTIONS` | a package name is required (`DEVICE`, `TIMEINT`, …) | ref §2.1.25 p96 | Reuse with differences (a package field) |
| `.DATA … .ENDDATA` | a named table | ref §2.1.2 p26 | New opaque block |
| `.PREPROCESS REPLACEGROUND` | makes `GND`, `GND!` and `GROUND` aliases of 0 | ref §2.1.28 p125 | New node: it changes net identity |
| `.PREPROCESS REMOVEUNUSED`, `ADDRESISTORS` | change the simulated circuit or write a file | ref §2.1.29–2.1.30 | New node or unknown directive, with a diagnostic |
| `.SAVE` | saves the operating point, unlike ngspice's `.save` | ref §2.1.34 p152 | **Not** `SaveDirective`: a new node or an unknown directive |
| `.PRINT`, `.FOUR`, `.FFT`, `.NOISE`, `.HB`, `.LIN`, `.SENS`, `.RESULT`, the sampling analyses | outputs and further analyses | ref §2.1 | Unknown directive in a closed list, typed later where needed |
| `.END` | must be the last line | ug §4.1.1 p40 | Reuse |

Not in xyce: `.TEMP`, `.TF`, `.PROBE`, `.PZ`, `.DISTO`, `.MC` and `.PLOT` (ref Table 6-1 p847–848, which says `.TEMP` is ignored). `.control`, `.if` and `.title` are not in the manual at all. The plan proposes a closed list of dot-commands, as decision 0009 did for LTspice. X-M0 probed an unknown one: Xyce 7.10 warns and ignores the line, and reads an unknown block's body as ordinary lines (a discrepancy row; the list is decided in X-M2).

## 5. Names, numbers, scoping and structure

- **Case:** case-insensitive, except file names (ug §4.1.3 p41). ASCII folding, as on ngspice.
- **Characters:** printable ASCII, except whitespace, parentheses, braces, comma, colon, semicolon and quotes (ref §2.3.2 p184). Parameter names start with a letter or `_` (ug §4.3.1 p46).
- **Ground and globals:** only `0` is ground (ref §2.3.1.1 p182); `GND` and the rest only with `.PREPROCESS REPLACEGROUND` (ref §2.1.28 p125). Every node beginning `$G` is global (decision X-D3).
- **Hierarchy:** `:` separates instance paths (`Xmain:Xnot1:A`), or `.` with the `-hspice-ext separator` flag. `X1:node` may stand on a device line (ref §2.3.1.2 p182–183; decision X-D2).
- **Numbers:** the scale factors T, G, Meg, **X** (1e6), K, mil, m, u, n, p, f (ug Table 4-1 p42). There is **no `a`**: it means amperes unless `-hspice-ext units` is given (ref §3.1 p835). There is no RKM, so `rkm=True` on xyce is a `ValueError` (m21 5.1 item 3).
- **Scoping:** as on ngspice: a body `.param` is local and masks outer names. A repeated `.param` takes the last definition by default; `-redefined_params` changes that (ref §2.1.26 p120, §3.2 p835).
- **Structure:** the first line is the title and `.END` is the last line (ug §4.1.1 p40). So `AFTER_TITLE` and `BEFORE_END` fit, with no exception.
- **Comments and continuation** (ug §4.1.3.1–4.1.3.2 p43):
  - `*` starts a comment line and `;` an end-of-line comment.
  - **A line that begins with whitespace is a comment** unless its first non-blank character is `+` (decision X-D1).
  - A `+` line joins the last non-comment line, even across comment lines. That is the xyce manual's rule, so the xyce overlay follows it; ngspice's rule (§19 decision 22) is unchanged.
- **Expressions** (ref §2.2 p164–171):
  - `{}` is preferred, and `'…'` is allowed. They may be bare in `.param`, `.global_param` and instance `name=` values (decision X-D5).
  - `**` is the power operator and `^` is boolean XOR.
  - `R1:R` reads a device parameter and `X1:A` a node.
  - `log` is base 10.
- **Command-line flags that change reading:** `-hspice-ext` and `-redefined_params` (ref §3 p834–835). Nothing before 1.0 (m21 5.1 item 3). If the library models them, they become keyword arguments with defaults.

## 6. Decisions the work needs

Each is a decision record in the milestone named, before its implementation.

- **X-D0 (X-M0) — The dialect.**
  - **Contents:** the references and the evidence policy (whether Xyce raw files and logs may be committed; the version recorded in `validated_on`); the closed dot-command list; the overlay on `core.lark`.
- **X-D1 (X-M1) — Leading whitespace.** An indented line is a `CommentLine`, as xyce reads it. An indented element line would otherwise read as an element that xyce ignores, and the topology would differ from the solver's.
- **X-D2 (X-M1) — `X1:node` on device lines.** Either refuse it (P5 allows a library to be stricter only by a recorded exception), or model it in the nets layer, as LTspice's reach into an instance is (`NODE_INTO_INSTANCE`).
- **X-D3 (X-M1) — `$G` globals,** in the names layer and `Net.global_`.
- **X-D4 (X-M6) — The Y-type designator convention.** Either the two tokens as written (`"YMEMRISTOR mr1"`), or xyce's internal `Y<type>!<name>`. The choice covers the designator span, the signature entries and the uniqueness check (type plus name).
- **X-D5 (X-M1) — Bare expressions,** an exception to §6.3 rule 10 for `.param`, `.global_param` and instance `name=`, as LTspice's `.param` has one.
- **X-D6 (X-M7) — Exclusions:** Y digital, YPDE and possibly the YPG devices, each as `UnsupportedConstruct` (decision 0020 style).

## 7. Solver evidence

- **Availability:** the 7.10 executables are a free download with no registration. Windows: an installer, serial build. Linux: an RHEL 8 RPM only. macOS: a package. The binaries include proprietary models (the "XyceNF" build). Xyce is GPLv3.
- **Batch command line:** `Xyce [options] <netlist>` (ref §3 p833):
  - `-syntax` checks syntax and `-norun` syntax and topology, which suits accept and reject probes;
  - `-r <file>` writes a raw file (`-a` for ASCII);
  - `-namesfile` lists the qualified node names, a node-list check like ngspice's;
  - `-v` gives the version for `validated_on`.
- **Raw format:** SPICE3-style, without the Commands and Options lines (ref §8 p857–858). `tests/support/raw.py` reads it after three changes made in X-M0: blank lines between points, complex values written `re, im`, and one `Title:` for several plots.
- **To check first (X-M0):** whether Smart App Control lets the installer and the binary run (AGENTS.md), and the install path for `XYCE_EXE`.

## 8. Milestones

One pull request each, in the style of the phase plans. Sizes are rough.

| Milestone | Content | Size |
|---|---|---|
| **X-M0 — Set-up and solver spike** | `[xyce-ref]` and `[xyce-ug]` in `references.md`; the install and Smart App Control; `tests/support/xyce.py` and `XYCE_EXE` discovery; a hidden xyce dialect with a structure-only overlay ([decision 0026](../decisions/0026-the-xyce-dialect.md)); the `docs/grammars/xyce/` skeleton (§9.3); decision X-D0. Probes: an unknown dot-command, leading whitespace, `+` after a comment, `[node]`, `//` in the manual's examples | S |
| **X-M1 — Structure, names, numbers; R, C, L, V, I, D, X, K** | Title and `.END`; comments and continuation; names, `$G`, `:`; scale factors and the `rkm` refusal; expressions; `.param`, `.global_param`, `.func`, `.model`, `.subckt`, includes and `.lib`, `.global`, `.preprocess replaceground`; names.md and scoping.md; the elements, with R, C and L's model before the value; decisions X-D1, X-D2, X-D3, X-D5 | L |
| **X-M2 — Directives** | Typed `.tran`, `.ac`, `.dc`, `.op`, `.options`, `.ic`/`.dcvolt`/`.nodeset`, `.step`, `.meas`; the opaque `.data` block; the closed list of the rest | M |
| **X-M3 — Stimulus and the port** | PULSE, SIN, EXP, PAT, PWL (with FILE, `TD=`, `R=`), SFFM, with and without parentheses; the P port device | M |
| **X-M4 — Transistors** | Q (3 to 5 nodes, `[sub]`, VBIC and HICUM), M (3 to 7 nodes, `IC=` lists, `TNODEOUT`), J, Z | M |
| **X-M5 — Controlled and behavioural sources, switches** | E, F, G, H (gain, VALUE/VOL/CUR, unbraced TABLE, POLY); B (`tablefile`); S in both forms, W; the expression scan (`^`, `:` names, accessors) | L |
| **X-M6 — Lines and Y-types** | T, O; decision X-D4, then YTRANSLINE, YDELAY, YLIN, YACC, YMEMRISTOR | M–L |
| **X-M7 — Digital U and exclusions** | The U gates; decision X-D6 | M |
| **X-M8 — Completeness audit and review** | As M18 and M19: the value-spec audit, the corpus with manifests, property tests, a review package | M |

### 8.1 Dialect branches for later milestones

X-M0 keyed every dialect branch that an xyce load reaches ([decision 0026](../decisions/0026-the-xyce-dialect.md) item 6). These sites are not reachable until the milestone named; each gets its xyce entry or branch there, from the manuals (X-M0 audit A2, line numbers at `xm0-xyce-setup`).

- **X-M1** (each line done in X-M1, B2 to B6, unless it says otherwise):
  - names and nets: `document/names.py:45` (`$G`, X-D3; done in X-M1 B2); `document/diagnostics.py:94` `_INSTANCE_NODES` and `:351` `_into_instance` (`X1:node`, X-D2; done in X-M1 B6, an `_InstanceNodeRule` per dialect and `_EXPRESSION_PATHS`); `dialects.py` `_FOLDS` (the ASCII fold, observed; done in X-M1 B2);
  - diagnostics: `document/diagnostics.py:97` `_ENDS_NAME_RULE`, `:101` `_VALUE_CHECKS`, `:103` `_REPEAT_STOPS` (done in X-M1 B2 to B4), and the citations at `:185` and `:198` (done in X-M1 B6: xyce reports no `PARAM_USED_BEFORE_DEFINITION`, and its `MODEL_TYPE_MISMATCH` carries no citation, as on LTspice);
  - the index: `document/index.py:557`, `:565` (use before definition) and `:604` (`_context_words`) (done in X-M1 B3);
  - formulas: `grammar/formula.py:24` `_GRAMMARS` and `formula-reserved.json` (done in X-M1 B3);
  - models: `model/model_types.py:38`, which gives xyce no model types of its own without an entry (done in X-M1 B4);
  - elements: `model/_rules_elements.py:321` (the transistor rule: not reached in X-M1, so it stays for X-M4);
  - edits: `edit/_ops_common.py:254`; `edit/_ops_elements.py:147`, `:359` and `:412`, and the model placed after the value (`:397`; xyce writes R, C and L's model first); `edit/_ops_remove.py:75` (done in X-M1 B6: the tables `_JOIN_TRAILING_COMMENTS`, `_LTSPICE_FORMS`, `_RCL_FORMS`, `_POSITIONAL_AREAS` and `_PORT_PARAMS` in `edit/_ops_common.py`).
- **X-M1 and X-M2 (statements):** `model/_rules_statements.py:180` and `:279` (done in X-M2 B4: the tables `_REFUSED_MODEL_TYPES` and `_LTRA_FLAG_REFUSALS`).
- **X-M3 (sources):** `model/_rules_sources.py:244`; `edit/_ops_sources.py:171` (done in X-M3 B4: the tables `_PARAM_SOURCES` and `_NEEDS_VALUE`, with `_NAMED_ARGS`).
- **X-M4 (transistors):** the positional area of Q (`edit/_ops_elements.py:234`).
- **X-M5 (controlled and behavioural sources):** `model/_rules_controlled.py:70`, `:171` and `:185`; `model/_rules_nonlinear.py:46` and `:206`; `edit/_ops_nonlinear.py:23`, `:98`, `:105` and `:185`; `document/diagnostics.py:325` `_CONTROL_RUNS`.
- **X-M6 (lines):** `model/_rules_lines.py:85`, `:135` and `:174`.

### 8.2 Held until X-M8

While the dialect is hidden, the user documentation does not describe it, and no new public name
is given to it (xm1-tasks 5.1 point 31). X-M8 restores what is held here and decides the names.

**The X-M8 release notes.** The best-effort additions that X-M0 to X-M7 make to the public API
(decision 0024 item 11), each harmless on ngspice and LTspice, which X-M8 lists in the release
notes:

- [ ] `ParamStatement.functions` (empty on ngspice and LTspice), with `FunctionDefinition` in
  `netlistmod.model.values` (X-M1 B3);
- [ ] `MutualCoupling.model` (`None` on ngspice and LTspice; X-M1 B5);
- [ ] `Resistor`, `Capacitor` and `Inductor` `.value_keyword_span` (`None` on ngspice and
  LTspice; X-M1 R1);
- [ ] the `ReferenceKind` `"function"` (X-M1 B6);
- [ ] the `DiagnosticCode` members `INDENTED_LINE_IGNORED` (X-M1 B2), `LIB_EXTRA_ENTRIES` and
  `NUMERIC_MODEL_NAME` (X-M1 R1), which `docs/usage/errors.md` lists only as reserved;
- [ ] the growth of the `BodyItem` and `TopLevelItem` unions by `IndentedLine`,
  `PreprocessDirective`, `FuncStatement` and `GlobalParamStatement` (X-M1 B2 and B3), and
  `LibCall`, an `OpaqueStatement` subclass (X-M1 B4): nodes that only an xyce parse produces;
- [ ] the internal names X-M8 makes public, or keeps internal: `Scope._functions` and
  `Scope._replace_ground` (X-M1 B3 and B2; point 31), with their read-only accessors
  `document.index.scope_functions` and `scope_replaces_ground` (X-M2.1 C4), and the parse's
  record of indented lines inside continued statements (`model.nodes.indented_comments`, X-M1
  R1).
- [ ] the X-M2 fields (decision 0028 item 10; xm2-tasks 5.1 point 28), each `None` or empty on
  ngspice and LTspice: `TranDirective.noop` and `.schedule`, `AcDirective.data`,
  `DcDirective.data`, `StepDirective.parameter` and `.data` (X-M2 B2), `OptionsDirective.package`,
  `OptionItem.values` and `.pairs`, `NodeCondition.form` (X-M2 B3);
- [ ] the X-M2 `Literal` values: the `StepDirective.kind` values `"name"`, `"qualified"` and
  `"data"` (X-M2 B2), the `OpaqueBlock.kind` `"data"` with its subclass `DataTable` for the
  `.DATA … .ENDDATA` table (X-M2 B3), the `NodeCondition.form` values `"v"` and `"pair"` (X-M2
  B3), and the `ReferenceKind` `"data"` (X-M2 B5);
- [ ] the growth of the `BodyItem` union by `IcDirective` and `NodesetDirective`, which stand in
  a body on xyce only (X-M2 B3);
- [ ] the X-M2 `DiagnosticCode` members `UNRESOLVED_DATA`, `ANALYSIS_IGNORED`,
  `STEPPED_ANALYSIS_FIELD`, `STEP_IGNORED`, `STEPS_WITH_OP`, `IC_WITH_NODESET`,
  `MEASURE_MODE_MISMATCH` and `CONDITION_IGNORED` (X-M2 B5), which `docs/usage/errors.md` lists
  only as reserved;
- [ ] the X-M2.1 additions (decision 0029 item 5): the node `PrintDirective` (xyce's `.PRINT`,
  in `netlistmod.model.nodes`) and the growth of the `TopLevelItem` union by it, and the
  `DiagnosticCode` member `PRINT_TYPE_MISMATCH`, which `docs/usage/errors.md` lists only as
  reserved;
- [ ] the X-M2 internal names X-M8 makes public, or keeps internal: `Scope._data` (the `.DATA`
  tables, with its accessor `document.index.scope_data`, X-M2.1 C4), `Index.sweep_targets` with
  `SweepTarget`, `Index.condition_nodes` (the nodes that initial conditions set; X-M2 R1), and
  `document.index.step_quantity` (the folded `.STEP` quantity that `directives.set` also keys
  by; X-M2 B5).
- [ ] the X-M3 additions (decision 0030 item 9): the node `PortSource` (xyce's P port, in
  `netlistmod.model.nodes`, a sibling of `VoltageSource` and `CurrentSource`) and the growth of
  the `BodyItem` and `TopLevelItem` unions by it, with its `ELEMENT_NAMES` entry `"port"` (X-M3
  B3); and `SourceSpec.args` widened to `Value | Identifier`, for PAT's DATA bit string (X-M3 B2;
  only an xyce parse holds an `Identifier` there).
- [ ] the X-M4 additions (decision 0031 item 11), each harmless on ngspice and LTspice: the
  `DiagnosticCode` member `NODE_COUNT_MISMATCH` (X-M4 B4), which `docs/usage/errors.md` lists only
  as reserved; the data file `model/xyce-levels.json` with its loader `model.xyce_levels`
  (`level_nodes`, `default_level`, `LevelNodes`); and the internal names X-M8 makes public, or
  keeps internal: `Index.model_bins` (an M line's model reference that resolves to a set of bins,
  mapped to every bin; X-M4 B4), with `document.index.model_set` (the bins a name refers to) and
  `document.index.model_binning` (whether `.OPTIONS PARSER MODEL_BINNING` leaves binning on).

**`docs/usage/errors.md`.** X-M8 puts back these paragraphs, held at X-M1 R1, in the entries
named:

- `UNRESOLVED_MODEL`, after "which may define it.": "On the hidden xyce dialect, when an R, C or
  L's model name is a visible parameter, the message adds that Xyce reads the word as the value."
- `UNRESOLVED_PARAM`, after "Severity as for `UNRESOLVED_MODEL`.": "On the hidden xyce dialect, a
  call to a function that no visible `.FUNC` (or `.PARAM` function) defines is reported the same
  way, with a message that names a function."
- `NODE_INTO_INSTANCE`, in place of "LTspice only.": "LTspice, and the hidden xyce dialect." and,
  after "a net of its own.": "On xyce only an internal node of the definition is joined (not a
  port or a global), and `X1:X2:m` reaches through both instances."
- `INDENTED_LINE_IGNORED`, in place of its reserved entry: "Xyce only. A line that begins with
  blanks and is not a `*`, `;` or `+` line: Xyce reads it as a comment and ignores it, even an
  element line or a dot-command, so the library reads it as a comment too; also such a line
  between a statement and its `+` line, which the library keeps among the statement's comments. A
  warning, on the line." Then: "**What to do:** remove the indentation if the line is meant as a
  statement; to keep it as a comment, begin it with `*`."
- `LIB_EXTRA_ENTRIES`, in place of its reserved entry: "Xyce only. A `.LIB` call that names more
  than one entry, of which Xyce loads only the first, ignoring the rest with a warning. Info, on
  the entries after the first." Then: "**What to do:** write one `.LIB` call per entry."
- `NUMERIC_MODEL_NAME`, in place of its reserved entry: "Xyce only. A `.model` whose name reads
  as a number (`.model 2k R`): the library reads `2k` on an element line as a value, while Xyce
  takes it as that model. A warning, on the model name." Then: "**What to do:** rename the model
  so it begins with a letter."
- `UNRESOLVED_PARAM`, `UNRESOLVED_ELEMENT` and `UNRESOLVED_NODE`, after the X-M1 paragraphs: "On
  the hidden xyce dialect, a `.DC` or `.STEP` target that names nothing is reported as a
  parameter (a plain name, 'parameter or element') or an element (`head:param`, 'element or
  model'), and a node of an `.IC`, `.DCVOLT` or `.NODESET` condition that nothing connects is an
  `UNRESOLVED_NODE`; a path such as `V(X1:m)` to an internal node is a `NODE_INTO_INSTANCE`."
  (X-M2 B5)
- `DUPLICATE_DEFINITION`, after its rule: "On the hidden xyce dialect it also reports a repeated
  `.OPTIONS` item (Xyce uses the first value; not the OUTPUT package, whose lines all apply), a
  repeated node in `.IC` and `.DCVOLT` or in `.NODESET`, a repeated `.MEAS` result and a repeated
  `.DATA` name (Xyce uses the last), and two `.STEP` lines of one quantity (`R2` and `R2:R`), which
  Xyce nests." (X-M2 B5)
- each X-M2 code, in place of its reserved entry (X-M2 B5), with its **What to do:**
  - `UNRESOLVED_DATA`: "Xyce only. A `DATA=` field on `.AC`, `.DC` or `.STEP` that names no
    top-level `.DATA` table; Xyce stops. A warning, info if an `.include` or `.lib` may define it,
    on the name." "**What to do:** define the table, or correct the name."
  - `ANALYSIS_IGNORED`: "Xyce only. An analysis Xyce does not run: of `.TRAN`, `.AC`, `.DC`,
    `.NOISE` and `.HB` only the last line's analysis runs, and `.OP` gives way to any of them;
    every `.DC` line after the first joins it into one nested sweep (its own message). A
    warning, on the keyword." "**What to do:** keep one analysis line, or one `.DC` line with
    all its sweeps."
  - `STEPPED_ANALYSIS_FIELD`: "Xyce only. A field of `.TRAN`, `.AC` or `.DC` reads a parameter
    that a `.STEP` sweeps; Xyce reads a `.TRAN` field once, so the sweep does not change it, and
    stops on an `.AC` or `.DC` field. A warning, on the parameter." "**What to do:** write the
    field as a number."
  - `STEP_IGNORED`: "Xyce only. A `.STEP` line beside a `.STEP DATA=` line, which makes Xyce drop
    every other `.STEP` line. A warning, on the keyword." "**What to do:** put the swept quantity
    in the table's columns."
  - `STEPS_WITH_OP`: "Xyce only. Two or more `.STEP` lines when `.OP` is the analysis that runs;
    Xyce 7.10 aborts. A warning, on `.OP`." "**What to do:** keep one `.STEP` line, or use `.DC`."
  - `IC_WITH_NODESET`: "Xyce only. `.IC` or `.DCVOLT` and `.NODESET` in one netlist, which Xyce
    aborts on. A warning, on each `.NODESET`." "**What to do:** keep one of the two."
  - `MEASURE_MODE_MISMATCH`: "Xyce only. A `.MEAS` mode whose analysis Xyce does not run (TRAN
    needs `.TRAN` to be the analysis that runs, AC `.AC`, DC `.DC`, NOISE `.NOISE`, with their
    `_CONT` forms, and FFT `.TRAN` as well as a `.FFT` line; no mode is `.HB`'s), or FFT without
    a `.FFT` line when `.TRAN` runs; Xyce stops, except that DC under `.OP` reports the
    measurement as FAILED. A warning, on the mode." "**What to do:** match the mode to the
    analysis, and give FFT a `.FFT` line."
  - `CONDITION_IGNORED`: "Xyce only. An `.IC`, `.DCVOLT` or `.NODESET` condition in a subcircuit
    body on a global node (`$G…` or a `.GLOBAL` node), which Xyce ignores with a warning. A
    warning, on the node." "**What to do:** move the condition to the top level."
  - `PRINT_TYPE_MISMATCH` (X-M2.1 C3): "Xyce only. A `.PRINT` type that does not agree with the
    first analysis line other than `.OP` (`.OP` when it is the only one), against which Xyce
    checks every type and stops; or an analysis's type whose analysis is not the one that runs
    (the last line's, `.HB` taking part), for which Xyce writes nothing. A warning, on the print
    type." "**What to do:** use the print type of the analysis that runs, and keep one analysis
    line."
- X-M4 B4 (decision 0031 items 5 to 8):
  - `NODE_COUNT_MISMATCH`, in place of its reserved entry: "Xyce only. A Q, M, J or Z line whose
    model resolves to a visible `.model` with a known LEVEL (its last `level=`, a plain integer;
    level 1 if it writes none) and whose node count that level does not take (with `TNODEOUT=`
    on the line, the count the level takes then); for a set of binned models, each bin with a
    known level, named. The message says what Xyce does: it stops on too few nodes, and on too
    many it stops, drops the extra nodes silently, or joins them to internal nodes of the device,
    by level. Also a node after the third that names a visible model whose level takes the count
    of the nodes before it: Xyce takes that node as the model and stops. Silent when the model is
    unresolved or its level unknown; the topology stays the nodes written. A warning, on the
    model name, the extra nodes, or the node." Then: "**What to do:** write the node count the
    model's level takes, or a model whose level takes the nodes written; rename a node that is
    also a model's name."
  - `MODEL_TYPE_MISMATCH`, after its rule: "On the hidden xyce dialect the transistor types are
    Xyce's (Q `NPN`/`PNP`, M `NMOS`/`PMOS`, J `NJF`/`PJF`, Z `NMF`/`PMF`), the message adds that
    Xyce 7.10 stops, and on an M that a VDMOS is an `NMOS` or `PMOS` model with `LEVEL=18`; for an
    M that names a set of binned models, each bin of another type is reported."
  - `UNRESOLVED_MODEL`, after the X-M1 paragraph: "On the hidden xyce dialect an M line whose
    model name no model matches exactly, while models `<name>.<suffix>` are visible (binned
    models, `nch.1`, `nch.2`), resolves to that set and is not reported, unless `.OPTIONS PARSER
    MODEL_BINNING=false` (or `0`) turns binning off."

## 9. Risks

1. **Leading whitespace.** An indented element line is a comment to xyce. The manual's own TCAD examples are indented, so X-M0 probes the rule before anything relies on it.
2. **Bare expressions** widen what a value slot can hold (decision X-D5).
3. **Nets into an instance** (`X1:node`) break the local-net model unless they are refused or modelled (decision X-D2).
4. **Letters that mean other things:** U, P and Y, and the keyword `.save`. Each gets its own node per dialect; none changes an existing dialect.
5. **Reading that depends on outside switches:** `.PREPROCESS REPLACEGROUND`, `-hspice-ext`, `-redefined_params`, and model binning (which could give false `UNRESOLVED_MODEL` warnings).
6. **Solver logistics:**
   - Smart App Control;
   - no Ubuntu binary, so CI stays solver-free in any case;
   - the serial-only Windows build;
   - manual examples that contradict the manual's rules (VBIC's thermal node, YLIN's node count). These need probes and `discrepancies.md` rows.
