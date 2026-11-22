# X-M2 task list — xyce directives

> **Status:** COMPLETE (2026-11-17) — approved by the maintainer and merged as #30; the outcome is [decision 0028](../../../decisions/0028-xyce-directives.md)
> **Follows:** [X-M1](./xm1-tasks.md) and decisions [0026](../../../decisions/0026-the-xyce-dialect.md) and [0027](../../../decisions/0027-xyce-structure-names-and-values.md). Plan: [xyce-plan.md](../../xyce-plan.md) sections 4, 6 and 8. Governed by [architecture.md](../../../architecture.md) (§2, §6, §7, §9.3, §10, §11, §12).

## 1. Scope

X-M2 makes the hidden xyce dialect read its analysis, option, initial-condition, sweep and measurement directives, and decides what it does with every other dot-command. The dialect stays hidden (decision 0026 item 4).

- **In:**
  - **Analyses:** `.TRAN` (`NOOP`, `UIC`, a `{schedule(…)}` argument), `.AC` (and `DATA=`), `.DC` (any number of sweeps, `LIST`, `DATA=`), `.OP`.
  - **Options:** `.OPTIONS` with its package name (`DEVICE`, `TIMEINT`, …).
  - **Initial conditions:** `.IC`, `.DCVOLT` (a synonym of `.IC`) and `.NODESET`.
  - **Sweeps:** `.STEP` (one sweep per line, no `param` keyword; a device, `dev:param`, `model:param`, `TEMP` or a parameter; `LIST`, `DATA=`); what `StepDirective.kind` gains.
  - **Measurements:** `.MEAS`/`.MEASURE`, typed as shallowly as on ngspice and LTspice.
  - **The `.DATA … .ENDDATA` block:** a new opaque, named block, and the references to it from `DATA=`.
  - **The closed list of the other dot-commands** (as decision 0009 did for LTspice): which are read as opaque statements, which as unknown directives with a diagnostic, and which are refused. Among them `.SAVE` (not ngspice's `SaveDirective`), `.PRINT`, `.FOUR`, `.FFT`, `.NOISE`, `.HB`, `.LIN`, `.SENS`, `.RESULT`, the sampling analyses, and the other `.PREPROCESS` forms.
  - **Where directives may stand:** a directive in a subcircuit body, which Xyce runs (X-M1's discrepancy row, xm1-tasks 5.1 point 16).
  - **The document and edit layers** for these: the X-M2 lines of the plan's section 8.1 (`model/_rules_statements.py`), and the directive edits (`set_tran`, `set_option` and the others that exist) on xyce.
  - **Spec entries, corpus files with manifests, and solver tests** for every construct read (§10).
- **Not in X-M2:**
  - the transient source functions and the P port (X-M3) and every letter not read in X-M1 (X-M3 to X-M7);
  - the command-line flags that change reading (`-hspice-ext`, `-redefined_params`): nothing before X-M8 (plan section 5);
  - a public `Dialect.XYCE` and the user documentation (X-M8; plan section 8.2).

## 2. Decisions

1. **Workflow as X-M1** (decision 0026; X-M0 decision 3): developer and reviewer subagents report to the lead; gates carry the maintainer's decisions; one commit per completed task; one pull request.
2. **Provenance** as decision 0026 items 2 and 3. Xyce source and headers are never read; the manuals are paraphrased and cited by section and page; nothing produced by Xyce is committed, and no timing numbers.
3. **The grammar follows the manual** (decision 0026 item 5). Where the binary is more lenient, the difference is a `discrepancies.md` row; where the manual is silent, the solver decides and the entry is `observed` (§11.3 rule 3).
4. **Reuse first.** An xyce directive reuses the ngspice or LTspice node and rule where the reading is the same (§9.3 item 4), and gets new fields or a node of its own only where its meaning differs. New fields, nodes, `Literal` values and `DiagnosticCode` members are best-effort additions (decision 0024 item 11) and go on the X-M8 release-notes checklist (plan section 8.2).

## 3. Stages and gates

1. **Stage 1 — research and probes** (A1 to A3). Reports to the lead; nothing in `src/` changes.
2. **G1 —** the lead writes section 5.1; the maintainer decides the closed list, the place of directives in a body, the `.DATA` block and any question the reports raise.
3. **Stage 2 — implementation** (B1 to B6), in the order below, since most tasks touch `xyce.lark`.
4. **R1 —** an independent review; findings are fixed or recorded.
5. **The pull request,** READY FOR REVIEW.

## 4. Tasks

### Stage 1

- [x] **A1 — Analyses and sweeps.** `.TRAN`, `.AC`, `.DC`, `.OP` and `.STEP`: each form in the manual against today's `TranDirective`, `AcDirective`, `DcDirective`, `OpDirective` and `StepDirective` and their ngspice and LTspice rules (reuse, reuse with differences, new); `NOOP`, `UIC`, `{schedule(…)}`; `DATA=`; `.DC` with three or more sweeps and `LIST`; `.STEP`'s targets and what `kind` gains; repeated analyses; probes for anything the manual leaves unclear. Options for each question, with a recommendation.
- [x] **A2 — Options, initial conditions, measurements and `.DATA`.** `.OPTIONS` packages and items (closed list or open; values; what the edit layer's `set_option` means with a package); `.IC`, `.DCVOLT` and `.NODESET` (forms, `V(node)` paths with `:`, globals); `.MEAS` forms and how far the shallow typing serves; the `.DATA … .ENDDATA` block (header, rows, the name, how `DATA=` refers to it, case and scope). Probes; options with a recommendation.
- [x] **A3 — The closed list and the edit layer.** Every dot-command in the manual's section 2.1 and its Table 6-1, sorted into: typed in X-M2, opaque statement, unknown directive with a diagnostic, or refused; what Xyce does with an unknown dot-command and an unknown block (X-M0's probe); `.SAVE`, `.PRINT` and the other outputs; the other `.PREPROCESS` forms; directives in a subcircuit body; the directive edits and the X-M2 site of the plan's section 8.1 (`model/_rules_statements.py`). Options with a recommendation.

### Stage 2

- [x] **B1 — Decision record** for the G1 decisions, and the architecture sections they amend.
- [x] **B2 — Analyses and sweeps** in `xyce.lark` and the statement rules: `.TRAN`, `.AC`, `.DC`, `.OP`, `.STEP`.
- [x] **B3 — Options, initial conditions, measurements** and the `.DATA` block.
- [x] **B4 — The closed list** of the other dot-commands, and directives in a body as decided at G1.
- [x] **B5 — The document and edit layers:** the X-M2 line of the plan's section 8.1; references from `DATA=`, diagnostics, and the directive edits on xyce.
- [x] **B6 — Evidence:** spec entries for every construct, `statements.md` for xyce, corpus files with manifests, solver tests (accept and reject probes, compared with Xyce), the discrepancy rows, the README status table, and the X-M8 release-notes checklist.

## 5. Findings and log

### 5.1 G1 decisions

From the stage 1 reports: A1 (analyses and sweeps), A2 (options, initial conditions, measurements and `.DATA`) and A3 (the closed list and the edit layer). All probes are on XyceNF Release 7.10.0 and are kept outside the repository. Each point gives the evidence, then *Recommendation:*, then the decision. **Every point not marked otherwise was decided as recommended (maintainer, 2026-11-16).**

**Dot-commands and where they stand (A3)**

1. **Closed or open.** Xyce warns on any unknown dot-command ("Unrecognized dot line will be ignored") and runs without it: a misspelling (`.tarn`, `.optoins`, `.opt`; no prefix matching) too, so a misspelt `.tran` leaves "No analysis specified". An unknown "block" is no block: its end lines each warn, and the lines between are read as circuit lines (`.foo / R3 2 0 1k / .endfoo` loads R3; a `.control` block stops on device `RUN`). Options:
   - (a) a closed list: the manual's commands, everything else `ParseError` with hints (as decision 0009);
   - (b) open, as on ngspice, with a warning "Xyce ignores this line";
   - (c) the manual's untyped commands open, the rest refused.

   *Recommendation:* (a). One discrepancy row for Xyce's leniency replaces `XY-UNS-001`'s. The closed-list `UnknownDirective` lines are continuable with `+`, as Xyce joins them.
   **Decided (maintainer, 2026-11-16): as recommended, a closed list.**
2. **Commands that are not Xyce's.** `.TEMP`, `.TF`, `.PROBE`, `.PZ`, `.DISTO`, `.MC`, `.PLOT`, `.WCASE` and the rest of [xyce-ref] Table 6-1 (p847–848), `.title`, `.backanno`, `.control`/`.if`, `.ALIASES`: each is ignored with that warning, and the lines of a block are read. `.step param` stops Xyce. The binary also knows `.MOR`, `.INITCOND` (it hangs with no arguments), `.LOAD` and a lone `.ENDDATA`, none in the manual.

   *Recommendation:* `ParseError` "not an Xyce dot-command" for all of them, with hints for `.TEMP` (use `.STEP TEMP` or `.OPTIONS DEVICE TEMP=`), `.PROBE` (`.PRINT … FORMAT=PROBE`), `.title` (the first line is the title), `.opt` (`.OPTIONS`) and `.step param` (no `param` keyword). Discrepancy rows for each one Xyce runs.
3. **Outputs and further analyses.** `.PRINT`, `.FOUR`, `.FFT`, `.RESULT`, `.SAVE`, `.SENS`, `.NOISE`, `.HB`, `.LIN`, `.SAMPLING`, `.EMBEDDEDSAMPLING` and `.PCE` run (`.PCE` is ignored by this build: "unrecognized"). None changes the circuit; `.SAVE` writes an `.IC`/`.NODESET` file at the operating point and has no vectors, and ngspice's `.save v(2)` stops Xyce.

   *Recommendation:* `UnknownDirective` (with `UNTYPED_DIRECTIVE_PRESERVED`), top level only; typed later where needed. `.SAVE` never builds `SaveDirective`. A discrepancy row for `.PCE`.
4. **The other `.PREPROCESS` forms.** `REMOVEUNUSED` deletes devices whose terminals share one node, so it changes the circuit (P4); a second line stops Xyce. `ADDRESISTORS` writes `<netlist>_xyce.cir` and leaves the run unchanged; two of one kind stop Xyce.

   *Recommendation:* `REMOVEUNUSED` stays `UnsupportedConstruct` (revisited at X-M4, when M and Q exist). `ADDRESISTORS` is an `UnknownDirective`, allowed wherever `.PREPROCESS` is, and a second of the same kind is a `ParseError`.
5. **Directives in a subcircuit body.** X-M1 point 16 and its discrepancy row said Xyce runs them; it does not. In a body Xyce silently ignores the analyses, `.OPTIONS`, `.STEP`, `.MEAS`, `.DATA` (a body table is invisible to the top level) and the outputs. It applies `.IC`, `.DCVOLT` and `.NODESET` to every instance, and `.PREPROCESS` netlist-wide; it stops on `.GLOBAL`, `.GLOBAL_PARAM` and `.END`. The manual allows only devices, `.MODEL`, `.PARAM` and `.FUNC` in a body ([xyce-ref] §2.1.37 p160), but its `.IC` text (§2.1.14 p48) implies `.IC` may stand there.

   *Recommendation:* `ParseError` in a body ("Xyce ignores it there") for the analyses, `.OPTIONS`, `.STEP`, `.MEAS`, `.DATA` and every closed-list `UnknownDirective` except `ADDRESISTORS`. `.IC`, `.DCVOLT` and `.NODESET` are allowed in a body, read per definition (§7.8); a `$G` node in a body condition gets a warning, since Xyce ignores it. The X-M1 row and point 16 are corrected.
6. **The plan's section 8.1 sites** (`model/_rules_statements.py`, now `:192` and `:302`) are `.MODEL` checks keyed `is Dialect.LTSPICE`, false on xyce. *Recommendation:* per-dialect tables, so a missing entry fails loudly (decision 0026 item 6).

**Analyses and sweeps (A1)**

7. **`.TRAN` fields** ([xyce-ref] §2.1.38 p161). `tstep tstop [tstart [tmax]]`, tstep required; one value, five numbers, a comma or a word such as `startup` stop Xyce. *Recommendation:* the core field order, no LTspice modifiers, no comma (`XY-TRN-001`).
8. **`NOOP` and `UIC`.** The manual makes them synonyms (§2.1.38; [xyce-ug] §13.6 p205); Table 6-1 says UIC is ignored with a warning, but the binary treats it as `NOOP`, silently. Either order, case-insensitive; the binary caps the field count, so `tstep tstop tstart tmax NOOP UIC` stops it.

   *Recommendation:* a new field `TranDirective.noop` beside `uic`; each at most once, after the numbers, either order. The manual's full form is read, with a row (Xyce stops on it); a repeated flag or a flag before a number is refused, with rows. The plan's section 4 is corrected.
9. **`{schedule(…)}`.** The binary takes it only where tstart would be: with tstart or tmax, the manual's own form stops Xyce ("Maximum Time step is invalid"). Braced or quoted, any case, an even number of arguments, one per line. Options:
   - (a) the manual's form (tstart, tmax and the schedule together), with a row;
   - (b) only what both allow: `tstep tstop [NOOP] [UIC] {schedule(…)}`, without tstart and tmax, refused otherwise with a hint;
   - (c) keep the line opaque.

   *Recommendation:* (b), as a new field `TranDirective.schedule: Formula | None` with its own terminal (P13); a row for the manual's form.
   **Decided (maintainer, 2026-11-16): (a), the manual's form.** tstart and tmax may stand with the schedule (`tstep tstop [tstart [tmax]] [NOOP] [UIC] [{schedule(…)}]`): tstart is meaningful, and tmax is a fixed ceiling beside the schedule's. That Xyce 7.10 stops on a schedule after tstart is taken as a solver bug and is a discrepancy row; a generator can always write a line Xyce runs. The field `TranDirective.schedule: Formula | None` and its own terminal stay as recommended.
10. **Numbers and expressions in analysis fields.** Unbraced fields take the device-field reader (decision 0027 item 8: `1kohm`, `10meghz` and `10x` run; `1j`, `10z` and `µ` stop Xyce). Braces and quotes run on `.TRAN`, `.AC` and `.DC` (the manual's own examples use them, though §2.1.36 p157 says analyses take no expressions); `.STEP` stops on any. A stepped parameter in a `.TRAN` field is read once.

    *Recommendation:* that reading; `.STEP` takes plain numbers only. A warning when an analysis field names a parameter that a `.STEP` sweeps (Xyce reads it once).
11. **`.AC`** (§2.1.1 p24). `LIN|OCT|DEC points fstart fstop` or `DATA=table`; `list` stops Xyce, points must be an integer. *Recommendation:* a new field `AcDirective.data` (`variation` = `data` as written); no `list` or `file=` (`XY-ACA-001`).
12. **`.DC`** (§2.1.3 p27). Any number of sweeps, first innermost, each with its own `LIN|DEC|OCT` (`LIN` optional) or `LIST`, in any position; `DATA=table` stands alone. Targets: a source, a device (its primary parameter), `dev:param`, `model:param`, `TEMP`, a `.param` or `.global_param`. `LIST` with one value runs, though the manual requires two. Options for `LIST`: (a) at least two values, as the manual, with a row; (b) at least one, as the binary.

    *Recommendation:* (a); a sweep-target terminal that allows `:`; a new field `DcDirective.data` with empty `sweeps` (`XY-DCA-001`, `-002`).
    **Decided (maintainer, 2026-11-16): (a), at least two values, as the manual; the same for `.STEP` (point 14).**
13. **`.OP`.** Extra fields run with a warning. *Recommendation:* refused, with a row (`XY-OPP-001`).
14. **`.STEP` forms** (§2.1.36 p155–158). `[LIN|DEC|OCT] target start stop step`, `target LIST v…` or `DATA=table`; no `param` keyword; one sweep per line (two on one line run only the last, silently); `LIST` as point 12. Targets as `.DC`, plus `X1:R5:R` (not `X1:R5`). Xyce resolves a name as a parameter first, then a device; the form of a target does not tell a device from a parameter, nor `dev:param` from `model:param`.

    *Recommendation:* a second sweep on a line is a `ParseError`, with a row. `StepDirective.kind` gains `name`, `qualified` and `data` (a best-effort widening), with new fields `parameter` (after the last `:`) and `data`; the document layer resolves each target against the scope, parameter first (`XY-STP-001`, `-002`).
15. **Repeated analyses** (observed; the manual is silent). Among `.TRAN`, `.AC` and `.DC`, only the last line runs, silently; `.OP` gives way to any other; two `.TRAN` or two `.AC` lines: the last wins. **Two `.DC` lines join into one nested sweep.** Options: (a) no diagnostic; (b) a warning on each analysis Xyce will not run, and on a second `.DC` line; (c) `ParseError` on more than one analysis.

    *Recommendation:* (b), a new `DiagnosticCode` (for example `ANALYSIS_IGNORED`, warning), with per-dialect entries (none on ngspice and LTspice). The directive upsert (`SINGLETON_DIRECTIVES`) needs no change.
16. **Repeated and nested `.STEP`.** Several lines nest, first innermost (manual). The same quantity twice nests silently; a `DATA=` step makes Xyce drop every other `.STEP` line; two `.STEP` lines with `.OP` crash Xyce 7.10.

    *Recommendation:* key the quantity by the folded target, with the primary parameter of R, C, L (R, C, L) and V, I (`DCV0`) so that `R2` and `R2:R` are one; warnings for a repeated quantity, for `DATA=` with other steps, and for several steps with `.OP`. `DUPLICATE_DEFINITION`'s "stops with an error" text becomes per dialect. `directives.set` replaces by the same key.
17. **Case.** Every keyword folds case, and `DATA` takes blanks around `=`. *Recommendation:* `"…"i` terminals; `variation` as written.

**Options, initial conditions, measurements and `.DATA` (A2)**

18. **`.OPTIONS` packages** (§2.1.25 p96, 21 packages). Every listed package runs except `PCES` (unrecognized by this build); an unknown package warns and is ignored; the binary also knows `LINSOL-ES`, `NONLIN-TWOLEVEL` and `PRINT` (which crashes it); a line with no package is ignored ("SPICE-style option not supported") or, bare, stops Xyce. `.OPTION` is a full synonym. Options: (a) the manual's closed list; (b) open; (c) closed with a warning.

    *Recommendation:* (a), case-folded; any other package or a missing one is a `ParseError` with a hint; `PCES` is read, with a row; `.OPTION` is read as a spelling, `observed` (`XY-OPT-001`).
19. **Item names.** Hundreds, per package; an unknown one is ignored with a warning. *Recommendation:* open in X-M2 (a closed list would copy the manual's tables).
20. **Values.** Numbers (device fields), words, comma lists (`2n,4n,6n`, blanks after a comma allowed), blanks around `=`; braced lists in `SAMPLES` (`OUTPUTS={V(1)},{V(2)}`). Braces elsewhere, commas between items, a blank-separated list and a leading bare word stop Xyce; a bare word after an item is dropped silently. `OUTPUT` and `RESTART` take `INITIAL_INTERVAL=i [t i]*`.

    *Recommendation:* `name=value` items, values as listed; braces only in `SAMPLES` and `EMBEDDEDSAMPLES`; the interval pairs as a new field `OptionItem.pairs`, an odd count refused; a list as a new field `OptionItem.values`; everything else a `ParseError`, with rows for the silent drops (`XY-OPT-002`).
21. **Repeats and place.** A repeated item: Xyce uses the **first** value, with a warning; two `OUTPUT` lines both apply (the manual says once only). *Recommendation:* `DUPLICATE_DEFINITION` (warning, the first value is used); top level only (point 5).
22. **`.OPTION SCALE`** without a package (§2.1.25.21 p119) runs, singular or plural. *Recommendation:* read `.OPTION SCALE=v`, singular, one item, as `package=None`; the plural refused, with a row.
23. **Nodes and edits.** A new field `OptionsDirective.package` (`None` on ngspice and LTspice). There is no `set_option` edit: X-M2 adds none, and `directives.add`, `replace` and `remove` work as they are. Section 1's "`set_tran`, `set_option`" is corrected.
24. **`.IC`, `.DCVOLT` and `.NODESET` forms** (§2.1.14 p48, §2.1.4 p29, §2.1.22 p92). `V(node)=value` (blanks around `=`) or `node value` pairs, several per line; values as numbers, braces or quotes. Mixed forms, commas, `I(…)`, `V(a,b)` and `2=0.5` are ignored with a warning; `all=` and `.NODESET I(…)` stop Xyce; **an odd number of pair fields hangs Xyce**. A repeated node: the last wins. `.IC` and `.NODESET` in one netlist: Xyce aborts.

    *Recommendation:* reuse `IcDirective`, `NodesetDirective` and `NodeCondition`, with a new field `NodeCondition.form` (`"v"` or `"pair"`); one form per statement; everything else a `ParseError`, with rows (the hang is recorded, not probed). `.DCVOLT` builds `IcDirective`. A new warning code for `.IC` with `.NODESET` (for example `IC_WITH_NODESET`); `DUPLICATE_DEFINITION` for a repeated node (the last is used) (`XY-ICN-001`, `XY-NOD-001`).
25. **Nodes in conditions.** `v(x1:m)` reaches an internal node; `$G` globals work at the top level; a condition in a body applies in every instance. *Recommendation:* the node field takes `:` paths, resolved as decision 0027 item 4 (`NODE_INTO_INSTANCE`), and `UNRESOLVED_NODE` (warning) for a node that nothing in the scope connects. Topology is unchanged (P4).
26. **`.MEAS`** (§2.1.18–2.1.20 p54–84). Modes TRAN, DC, AC, NOISE, FFT and the four `_CONT` forms, required; `TR` runs, though not in the manual; `HB`, `OP`, `SP` and a missing mode stop Xyce, as does a mode with no matching analysis. A repeated result name: the last is used, with a warning.

    *Recommendation:* reuse `MeasureDirective`; a closed, required mode list, `TR` refused with a row; at least one body field; top level only. A new warning code for a mode with no matching analysis (for example `MEASURE_MODE_MISMATCH`), and `DUPLICATE_DEFINITION` for a repeated result (`XY-MEA-001`).
27. **`.DATA … .ENDDATA`** (§2.1.2 p26). The binary reads the first word as the name, so the manual's optional name cannot work; column names follow on the `.DATA` line or `+` lines; values are read as a stream, and a count that is not a multiple of the columns stops Xyce even when nothing uses the table; `.ENDDATA` is a no-op to the binary (missing, named or doubled runs); a repeated name: the last wins; order is free; `DATA=` on `.DC`, `.AC`, `.NOISE` and `.STEP`, not `.TRAN`; an unknown name stops Xyce.

    *Recommendation:* a new opaque block node (for example `DataTable`): the name required, at least one column, plain numbers only in a multiple of the columns, `.ENDDATA` required and bare, top level only, each strictness a row. A `data` namespace: `DATA=` fields are references of a new kind `data`, a new `UNRESOLVED_DATA` (warning), and `DUPLICATE_DEFINITION` for a repeated name (the last is used). Directive edits treat the block whole (`XY-DAT-001`, `-002`).

**Across the milestone**

28. **New best-effort names** (decision 0024 item 11), each on the X-M8 release-notes checklist: the fields `TranDirective.noop` and `.schedule`, `AcDirective.data`, `DcDirective.data`, `StepDirective.parameter` and `.data`, `OptionsDirective.package`, `OptionItem.values` and `.pairs`, `NodeCondition.form`; the `kind` values `name`, `qualified` and `data`; the `.DATA` node and the `data` reference kind; the `DiagnosticCode` members of points 15, 16, 24, 26 and 27.
29. **Corrections:** the plan's section 4 (UIC), X-M1's point 16 and its discrepancy row (archived record: only links are fixed there, so the correction goes in the discrepancy row and decision record), and this list's section 1.
30. **Evidence** as the reports propose: solver tests per directive (accept, reject, and the binary's leniencies), corpus files with manifests (`.IC` and `.NODESET` in separate files, since together they abort), and no probe that hangs Xyce (`.IC` with odd pairs, `.INITCOND` with no arguments).

**Decided during B5** (probes by the B5 developer, kept outside the repository; maintainer, 2026-11-16)

31. **`.NOISE` is an analysis** for points 15 and 26: `.TRAN` and `.NOISE` override each other as `.TRAN`, `.AC` and `.DC` do, so it takes part in `ANALYSIS_IGNORED` and `MEASURE_MODE_MISMATCH`. **Decided: accepted.**
32. **`MEASURE_MODE_MISMATCH` checks the analysis that runs,** not only that a matching line exists: `.TRAN` then `.AC` with `.MEAS TRAN` stops Xyce. A DC mode under `.OP` gets a milder message, since Xyce runs it and reports the measure as failed. **Decided: accepted.**
33. **`CONDITION_IGNORED` covers `.GLOBAL` nodes** in a body condition as well as `$G` names: Xyce reads such a node as a node of the instance (`X1:VDD`), finds none, and ignores the condition. **Decided: accepted.**

### 5.2 Log

- 2026-11-16: task list written; X-M1 archived (approved and merged as #27).
- 2026-11-16: A1, A2 and A3 done (reports to the lead; nothing in `src/` changed); section 5.1 written for G1.
- 2026-11-16: G1 in progress: points 1, 9 (the manual's form), 12 and 14 decided; the other points wait for the maintainer's review.
- 2026-11-16: G1 done: the maintainer accepted every other point as recommended.
- 2026-11-16: B1 done: [decision 0028](../../../decisions/0028-xyce-directives.md); architecture §6.5 and the plan's section 4 amended.
- 2026-11-16: B2 done: `.TRAN` (`NOOP`, `UIC`, a schedule), `.AC`, `.DC` (any number of sweeps, `LIST`), `DATA=`, `.OP` and `.STEP` read on xyce, top level only; new fields `TranDirective.noop` and `.schedule`, `AcDirective.data`, `DcDirective.data`, `StepDirective.parameter` and `.data`, and the `kind` values `name`, `qualified` and `data`; spec entries `XY-TRN-001`, `XY-ACA-001`, `XY-DCA-001`, `XY-DCA-002`, `XY-OPP-001`, `XY-STP-001` and `XY-STP-002`, `documented` until B6's solver tests.
- 2026-11-16: B3 done: `.OPTIONS`/`.OPTION` (a package of the manual's 21, `.OPTION SCALE=` without one; `name=value` items, comma lists, braces only in SAMPLES and EMBEDDEDSAMPLES, `INITIAL_INTERVAL` pairs), `.IC`, `.DCVOLT` and `.NODESET` (`V(node)=value` or `node value` pairs, one form per line, allowed in a body), `.MEASURE`/`.MEAS` (a required mode of the closed list) and the `.DATA … .ENDDATA` table read on xyce; new fields `OptionsDirective.package`, `OptionItem.values` and `.pairs`, `NodeCondition.form`, the `OpaqueBlock` kind `data` and the node `DataTable` (internal); `BodyItem` holds `IcDirective` and `NodesetDirective`; spec entries `XY-OPT-001`, `XY-OPT-002`, `XY-ICN-001`, `XY-NOD-001`, `XY-MEA-001` and `XY-DAT-001`, `documented` until B6's solver tests.
- 2026-11-16: B4 done: the closed list on xyce: `.PRINT`, `.FOUR`, `.FFT`, `.RESULT`, `.SAVE` (never `SaveDirective`), `.SENS`, `.NOISE`, `.HB`, `.LIN`, `.SAMPLING`, `.EMBEDDEDSAMPLING` and `.PCE` read as `UnknownDirective`, top level only, continued by `+` lines; any other dot-command a `ParseError` "not an Xyce dot-command" at its first character, with hints for `.TEMP`, `.PROBE`, `.title` and `.opt`; `.PREPROCESS ADDRESISTORS ONETERMINAL|NODCPATH` an `UnknownDirective`, allowed in a body, one of each kind; `REMOVEUNUSED` still `UnsupportedConstruct`, any other `.PREPROCESS` word a `ParseError`; every decided directive refused in a body with the "ignores it there" message, `.IC`, `.DCVOLT`, `.NODESET` and `.PREPROCESS` allowed; the plan's section 8.1 statement sites made per-dialect tables; spec entries `XY-DIR-001`, `XY-DIR-002`, `XY-DIR-003`, `XY-PRE-002` and `XY-SAV-001`, `documented` until B6's solver tests.
- 2026-11-16: B5 done: on xyce, `.DC` and `.STEP` targets resolve as Xyce does (a parameter first, then an element; `head:param` an element, a path `X1:R5` through the instances, or a model; `TEMP` none); `DATA=` on `.AC`, `.DC` and `.STEP` is a new `data` reference to the top-level `.DATA` tables; the nodes of `.IC`, `.DCVOLT` and `.NODESET` conditions are `node` references (`NODE_INTO_INSTANCE` for a path to an internal node, `UNRESOLVED_NODE` for an unconnected one); the `.TRAN` schedule word is no function reference; new warnings `UNRESOLVED_DATA`, `ANALYSIS_IGNORED` (`.NOISE` takes part in the last-line rule, as probed), `STEPPED_ANALYSIS_FIELD`, `STEP_IGNORED`, `STEPS_WITH_OP`, `IC_WITH_NODESET`, `MEASURE_MODE_MISMATCH` (against the analysis that runs, as probed) and `CONDITION_IGNORED` (a `$G` or `.GLOBAL` node in a body condition), listed as reserved in `docs/usage/errors.md`; `DUPLICATE_DEFINITION` for repeated options (the first; not OUTPUT), conditions, results and tables (the last) and `.STEP` quantities by the folded key, with per-dialect messages; `directives.set` keys an xyce `.STEP` by that key; golden edit tests for every xyce directive kind, the closed list and `.DATA`; `SINGLETON_DIRECTIVES` unchanged; the plan's section 8.2 checklist holds the X-M2 additions.
- 2026-11-16: points 31 to 33 (from B5's probes) accepted by the maintainer.
- 2026-11-16: B6 done: the solver tests `tests/solver/test_xyce_analysis_probes.py`, `test_xyce_directive_probes.py` and `test_xyce_closed_list_probes.py` (every X-M2 construct, the values Xyce writes compared with the library's fields, and each diagnostic's claim about Xyce); X-M1's `test_a_directive_runs_in_a_body` replaced by `test_an_option_in_a_body_is_ignored`; the corpus families `directives_basic` (with a CRLF twin, and `sampling.cir` run without `-r` through a manifest `solver` field `{"mode": "print"}`) and `directives_rejects`; the discrepancy rows of B2 to B5 and the probes, rows 21 and 31 rewritten; 15 X-M2 entries `validated`, `XY-OPT-001`, `XY-MEA-001` and `XY-DIR-001` `observed` (README: 40 validated, 5 observed, 1 documented); `scoping.md` rows S10 to S12. Two message corrections from the probes: the `.IC`/`.DCVOLT`/`.NODESET` field refusals (`all=`, `I(...)`, `V(a,b)`, mixed forms) now say per keyword that Xyce ignores the field on `.IC` and `.DCVOLT`, with a warning, and stops on `.NODESET` (the `all=` message said Xyce stops on every keyword); the package-less `.OPTIONS` refusal now says Xyce ignores such a line with a warning, and a line whose only item is `TEMP=` or `TNOM=`, which Xyce applies, gets the hint "write `.OPTIONS DEVICE TEMP=`". Full run with ngspice, LTspice and Xyce: 13272 passed, 2 skipped, coverage 99.26%.
- 2026-11-16: R1 findings fixed. Blockers: B1, a node that an expression in an `.ic` or `.nodeset` value reads no longer reaches the condition checks (ngspice and LTspice no longer crash; on xyce it is an ordinary expression node): `Index.condition_nodes` (internal) holds the nodes the conditions set and alone routes to them; B2, the body-line refusal of the directive operations keeps main's text on ngspice and LTspice, the xyce note in a per-dialect table. Should-fix: S1, `STEPPED_ANALYSIS_FIELD` is keyed per analysis: Xyce reads a `.TRAN` field once and stops on an `.AC` or `.DC` one ("contains unknowns"; probed; point 10's rationale corrected, the warning unchanged), with solver tests; S2, `STEP_PARAM_KW` leaves `.STEP param LIST …` a sweep of a parameter `param`, as Xyce runs it, its lookahead spelling out every word but `list` so Lark still checks it for collisions. Gaps: 1, a path to a device without its parameter (`.DC X1:R5`, `.STEP X1:R5`) is an unresolved element, "element parameter", a warning that says Xyce stops and to write `X1:R5:<param>`; `StepDirective.parameter` stays the part after the last `:`, as the form alone cannot tell `X1:R5` from `R2:R` (documented); 2, the package-less `.OPTION SCALE=` is keyed as PARSER's, so beside `.OPTIONS PARSER SCALE=` it is a repeat; both discrepancy rows dropped and their solver assertions flipped; 3 stays a row. Nits: N1, an xyce dot-command outside the closed list lists no expected tokens, whichever way the parser stops (LTspice unchanged); N2, the ADDRESISTORS info names `.PREPROCESS ADDRESISTORS`; N3, a schedule in tstep's or tstop's place is refused by the grammar (`tran_early_schedule`), not the transformer; N5, the `DcSweep` and `MeasureDirective` docstrings cover xyce; N7, `_MEASURE_ANALYSES` dropped; N8, `test_tran_takes_no_data` asserts Xyce's message; N9, `SWEEP_LOOKUP` is `_SWEEP_LOOKUP`; N6 left as is. Full run with ngspice, LTspice and Xyce: 13332 passed, 2 skipped, coverage 99.26%.
- 2026-11-16: pre-commit hooks pass (mypy 1.18.2 as CI pins it). READY FOR REVIEW.
- 2026-11-21: approved by the maintainer and merged as #30; archived in `archive/xyce/`. The loose ends go to [X-M2.1](../../xm2.1-tasks.md).
