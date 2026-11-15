# xyce dialect plan (draft)

> **Status:** ACTIVE (2026-11-15; the roadmap for the xyce milestones, starting with [X-M0](./xm0-tasks.md)). Written in [M21](./archive/v1.0/m21-tasks.md) (P1) from reviews X1 and X2; for the maintainer's review. It plans work after 1.0 and changes nothing in the library.
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
| Q | `Q c b e [sub] <model> [area]`, 3 to 5 nodes; a named substrate is written in square brackets; VBIC and HICUM add a thermal node | ref §2.3.17 p241–242 | Reuse with differences: the `[node]` form is new; the manual's VBIC example writes the thermal node unbracketed, which needs a probe |
| M | 4 nodes and a model; BSIM-SOI 4 to 7 nodes (a `TNODEOUT` flag changes the last node's meaning); MVS 3 or 5; `IC=` lists | ref §2.3.20 p292–294 | Reuse with differences: the node counts |
| S | (a) `S s+ s- c+ c- <model> [ON] [OFF]` (VSWITCH); (b) a generic `S s+ s- <model> [ON][OFF] CONTROL={expr}` (SWITCH model) | ref §2.3.22 p762, §2.3.23 p766 | (a) reuse; (b) a new form with two nodes, whose `CONTROL=` is edited with `set_expression` |
| T | `T a+ a- b+ b- Z0= [TD=] [F= [NL=]]`, `ZO` a synonym | ref §2.3.25 p769 | Reuse with differences |
| U | digital gates: `U <type>[(<n>)] <dpwr> <dgnd> <in>* <out>* <model>`, types INV, BUF, AND, NAND, OR, NOR, XOR, NXOR, DFF, JKFF, TFF, DLTCH, ADD; model DIG | ref §2.3.28 p775–777 | New node. Collides with ngspice's URC; xyce has no URC |
| X | `X [node]* <subckt> [PARAMS: n=v …]`; `M=` without `PARAMS:` | ref §2.3.33 p803 | Reuse with differences: `PARAMS:` on X (ngspice refuses it) |
| Y\<type\> | `Y<type> <name> [node]* <model>`; the name is unique only with the type | ref Table 2-35 p178, §2.3.29 p780 | **A new designator form** (section 6, decision X-D4). The letter collides with ngspice's TXL |
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
| `.TRAN` | `NOOP`, `UIC` (ignored with a warning), a `{schedule(…)}` argument | ref §2.1.38 p161 | Reuse with differences |
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

Not in xyce: `.TEMP`, `.TF`, `.PROBE`, `.PZ`, `.DISTO`, `.MC`, `.PLOT`, `.control`, `.if` and `.title` (ref Table 6-1 p847). The plan proposes a closed list of dot-commands, as decision 0009 did for LTspice. The manuals do not say what xyce does with an unknown one, so X-M0 probes it.

## 5. Names, numbers, scoping and structure

- **Case:** case-insensitive, except file names (ug §4.1.3 p41). ASCII folding, as on ngspice.
- **Characters:** printable ASCII, except whitespace, parentheses, braces, comma, colon, semicolon and quotes (ref §2.3.2 p184). Parameter names start with a letter or `_` (ug §4.3.1 p46).
- **Ground and globals:** only `0` is ground; `GND` and the rest only with `.PREPROCESS REPLACEGROUND` (ref §2.3.1.1 p182). Every node beginning `$G` is global (decision X-D3).
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
- **Raw format:** SPICE3-style, without the Commands and Options lines (ref §8 p857). `tests/support/raw.py` should mostly serve.
- **To check first (X-M0):** whether Smart App Control lets the installer and the binary run (AGENTS.md), and the install path for `XYCE_EXE`.

## 8. Milestones

One pull request each, in the style of the phase plans. Sizes are rough.

| Milestone | Content | Size |
|---|---|---|
| **X-M0 — Set-up and solver spike** | `[xyce-ref]` and `[xyce-ug]` in `references.md`; the install and Smart App Control; `tests/support/xyce.py` and `XYCE_EXE` discovery; `Dialect.XYCE` with an empty overlay; the `docs/grammars/xyce/` skeleton (§9.3); decision X-D0. Probes: an unknown dot-command, leading whitespace, `+` after a comment, `[node]`, `//` in the manual's examples | S |
| **X-M1 — Structure, names, numbers; R, C, L, V, I, D, X, K** | Title and `.END`; comments and continuation; names, `$G`, `:`; scale factors and the `rkm` refusal; expressions; `.param`, `.global_param`, `.func`, `.model`, `.subckt`, includes and `.lib`, `.global`, `.preprocess replaceground`; names.md and scoping.md; the elements, with R, C and L's model before the value; decisions X-D1, X-D2, X-D3, X-D5 | L |
| **X-M2 — Directives** | Typed `.tran`, `.ac`, `.dc`, `.op`, `.options`, `.ic`/`.dcvolt`/`.nodeset`, `.step`, `.meas`; the opaque `.data` block; the closed list of the rest | M |
| **X-M3 — Stimulus and the port** | PULSE, SIN, EXP, PAT, PWL (with FILE, `TD=`, `R=`), SFFM, with and without parentheses; the P port device | M |
| **X-M4 — Transistors** | Q (3 to 5 nodes, `[sub]`, VBIC and HICUM), M (3 to 7 nodes, `IC=` lists, `TNODEOUT`), J, Z | M |
| **X-M5 — Controlled and behavioural sources, switches** | E, F, G, H (gain, VALUE/VOL/CUR, unbraced TABLE, POLY); B (`tablefile`); S in both forms, W; the expression scan (`^`, `:` names, accessors) | L |
| **X-M6 — Lines and Y-types** | T, O; decision X-D4, then YTRANSLINE, YDELAY, YLIN, YACC, YMEMRISTOR | M–L |
| **X-M7 — Digital U and exclusions** | The U gates; decision X-D6 | M |
| **X-M8 — Completeness audit and review** | As M18 and M19: the value-spec audit, the corpus with manifests, property tests, a review package | M |

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
