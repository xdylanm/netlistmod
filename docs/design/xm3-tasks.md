# X-M3 task list — xyce stimulus and the P port

> **Status:** ACTIVE (2026-11-22)
> **Follows:** [X-M2.1](./archive/xyce/xm2.1-tasks.md) (merged as #31) and decisions [0026](../decisions/0026-the-xyce-dialect.md) to [0029](../decisions/0029-xyce-discrepancy-categories.md). Plan: [xyce-plan.md](./xyce-plan.md) sections 4 and 8. Governed by [architecture.md](../architecture.md) (§2, §6, §7, §9.3, §10, §11, §12).

## 1. Scope

X-M3 makes the hidden xyce dialect read the transient functions of the V and I sources, which X-M1 refuses whole (`src_function` in `xyce.lark`), and the P port device. The dialect stays hidden (decision 0026 item 4).

- **In:**
  - **The functions** PULSE, SIN, EXP, PAT, PWL (with `FILE "name"`, `TD=` and `R=`) and SFFM, with and without parentheses ([xyce-ref] §2.3.9, §2.3.10); reusing `SourceSpec` where the reading is the same as on ngspice or LTspice. PAT is new.
  - **The P port** ([xyce-ref] §2.3.11): `P n+ n- [[DC] v] port=<n> [Z0=v] [AC …] [tran]`, a new source-like node. The letter is ngspice's coupled line, so P is xyce-only.
  - **The document and edit layers:** the X-M3 line of the plan's section 8.1 (`model/_rules_sources.py`, `edit/_ops_sources.py`); the source edits (`set_stimulus`, `remove_stimulus` and the others that exist) on xyce and the P port; references a PWL `FILE` makes, if any.
  - **The open `.HB` and SIN question** from X-M2: a `.DC` sweep of a SIN source reports 0 when the netlist has `.HB`.
  - **Spec entries, corpus files with manifests, solver tests and discrepancy rows** with categories (decision 0029) for every construct read (§10).
- **Not in X-M3:** the controlled and behavioural sources (X-M5); `.LIN` beyond the P port's fields (an `UnknownDirective`, decision 0028 item 1); a public `Dialect.XYCE` (X-M8).

## 2. Decisions

1. **Workflow as X-M2** (decision 0026; X-M0 decision 3): developer and reviewer subagents report to the lead; gates carry the maintainer's decisions; one commit per completed task; one pull request.
2. **Provenance** as decision 0026 items 2 and 3: Xyce source and headers are never read; the manuals are paraphrased and cited by section and page; nothing produced by Xyce is committed, and no timing numbers.
3. **The manual is the reference and the solver is observed** (decision 0029): every difference is a `discrepancies.md` row with a category and its Library/Xyce pair.
4. **Reuse first** (§9.3 item 4). New fields, nodes, `Literal` values and `DiagnosticCode` members are best-effort additions (decision 0024 item 11) and go on the X-M8 checklist (plan section 8.2). ngspice and LTspice do not change (decision 0024).

## 3. Stages and gates

1. **Stage 1 — research and probes** (A1, A2). Reports to the lead; nothing in `src/` changes.
2. **G1 —** the lead writes section 5.1; the maintainer decides the questions the reports raise.
3. **Stage 2 — implementation** (B1 to B5).
4. **R1 —** an independent review; findings are fixed or recorded.
5. **The pull request,** READY FOR REVIEW.

## 4. Tasks

### Stage 1

- [ ] **A1 — The transient functions.** Each of PULSE, SIN, EXP, PAT, PWL and SFFM in the manual against today's `SourceSpec` and its ngspice and LTspice rules (reuse, reuse with differences, new): the argument counts and defaults, parentheses or none, commas, braces and expressions in arguments, keyword arguments (`TD=`, `R=`, PWL `FILE`), PAT's bit string, a function after `AC` or before `DC`, a second function; the `.HB` and SIN question. Probes for what the manual leaves unclear. Options for each question, with a recommendation.
- [ ] **A2 — The P port and the edit layer.** The P line's forms and fields against the V source and ngspice's coupled line; the node it needs; where P may stand and what `.LIN` needs from it; the source edits on xyce (the plan's section 8.1 sites) and on P. Probes; options with a recommendation.

### Stage 2

- [ ] **B1 — Decision record** for the G1 decisions.
- [ ] **B2 — The functions** in `xyce.lark` and the source rules.
- [ ] **B3 — The P port.**
- [ ] **B4 — The document and edit layers.**
- [ ] **B5 — Evidence:** spec entries, corpus files with manifests, solver tests, discrepancy rows, the README status table, the X-M8 checklist.

## 5. Findings and log

### 5.1 G1 decisions

(After stage 1.)

### 5.2 Log

- 2026-11-22: task list written; X-M2.1 merged as #31.
