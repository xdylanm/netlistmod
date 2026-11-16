# X-M2 task list — xyce directives

> **Status:** ACTIVE — stage 1 (research and probes)
> **Follows:** [X-M1](./archive/xyce/xm1-tasks.md) and decisions [0026](../decisions/0026-the-xyce-dialect.md) and [0027](../decisions/0027-xyce-structure-names-and-values.md). Plan: [xyce-plan.md](./xyce-plan.md) sections 4, 6 and 8. Governed by [architecture.md](../architecture.md) (§2, §6, §7, §9.3, §10, §11, §12).

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

- [ ] **A1 — Analyses and sweeps.** `.TRAN`, `.AC`, `.DC`, `.OP` and `.STEP`: each form in the manual against today's `TranDirective`, `AcDirective`, `DcDirective`, `OpDirective` and `StepDirective` and their ngspice and LTspice rules (reuse, reuse with differences, new); `NOOP`, `UIC`, `{schedule(…)}`; `DATA=`; `.DC` with three or more sweeps and `LIST`; `.STEP`'s targets and what `kind` gains; repeated analyses; probes for anything the manual leaves unclear. Options for each question, with a recommendation.
- [ ] **A2 — Options, initial conditions, measurements and `.DATA`.** `.OPTIONS` packages and items (closed list or open; values; what the edit layer's `set_option` means with a package); `.IC`, `.DCVOLT` and `.NODESET` (forms, `V(node)` paths with `:`, globals); `.MEAS` forms and how far the shallow typing serves; the `.DATA … .ENDDATA` block (header, rows, the name, how `DATA=` refers to it, case and scope). Probes; options with a recommendation.
- [ ] **A3 — The closed list and the edit layer.** Every dot-command in the manual's section 2.1 and its Table 6-1, sorted into: typed in X-M2, opaque statement, unknown directive with a diagnostic, or refused; what Xyce does with an unknown dot-command and an unknown block (X-M0's probe); `.SAVE`, `.PRINT` and the other outputs; the other `.PREPROCESS` forms; directives in a subcircuit body; the directive edits and the X-M2 site of the plan's section 8.1 (`model/_rules_statements.py`). Options with a recommendation.

### Stage 2

- [ ] **B1 — Decision record** for the G1 decisions, and the architecture sections they amend.
- [ ] **B2 — Analyses and sweeps** in `xyce.lark` and the statement rules: `.TRAN`, `.AC`, `.DC`, `.OP`, `.STEP`.
- [ ] **B3 — Options, initial conditions, measurements** and the `.DATA` block.
- [ ] **B4 — The closed list** of the other dot-commands, and directives in a body as decided at G1.
- [ ] **B5 — The document and edit layers:** the X-M2 line of the plan's section 8.1; references from `DATA=`, diagnostics, and the directive edits on xyce.
- [ ] **B6 — Evidence:** spec entries for every construct, `statements.md` for xyce, corpus files with manifests, solver tests (accept and reject probes, compared with Xyce), the discrepancy rows, the README status table, and the X-M8 release-notes checklist.

## 5. Findings and log

### 5.1 G1 decisions

(Written at G1.)

### 5.2 Log

- 2026-11-16: task list written; X-M1 archived (approved and merged as #27).
