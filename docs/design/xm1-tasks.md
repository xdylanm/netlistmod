# X-M1 task list — xyce structure, names, numbers; R, C, L, V, I, D, X, K

> **Status:** ACTIVE — stage 1 (research and probes)
> **Follows:** [X-M0](./archive/xyce/xm0-tasks.md) and [decision 0026](../decisions/0026-the-xyce-dialect.md). Plan: [xyce-plan.md](./xyce-plan.md) sections 3 to 6 and 8. Governed by [architecture.md](../architecture.md) (§2, §6, §7, §9.3, §10, §11, §12).

## 1. Scope

X-M1 makes the hidden xyce dialect read real netlists: the structure, names and numbers, parameters and expressions, subcircuits and models, and the first element letters. The dialect stays hidden (decision 0026 item 4).

- **In:**
  - **Structure:** the title, comments and continuation (`*`, `;`, `+` across comments), indented lines (decision X-D1), and whether `.END` is required (decision 0026 item 5).
  - **Names:** case, legal characters, ground, `$G` globals (X-D3), `:` hierarchy and `X1:node` on device lines (X-D2), `.PREPROCESS REPLACEGROUND`, `.GLOBAL`. `names.md` and `scoping.md` written.
  - **Numbers:** the scale factors (with `X` = 1e6 and `mil`, and no `a`), `rkm` refused.
  - **Parameters and expressions:** `.PARAM`, `.GLOBAL_PARAM`, `.FUNC`; braces, quotes and bare expressions (X-D5); the xyce formula grammar and reserved words (`**`, `^` as XOR, `log` base 10, `R1:R` accessors) as far as the expression scan needs them.
  - **Statements:** `.MODEL` (xyce's model types; binned names such as `nch.1`), `.SUBCKT`/`.ENDS` (`PARAMS:`, nesting, node 0 not a port), `.INC`/`.INCL`/`.INCLUDE`, `.LIB` (call and block), `.GLOBAL`, `.PREPROCESS REPLACEGROUND`.
  - **Elements:** R, C, L (the model before the value), V and I (DC and AC parts only; the transient functions stay refused until X-M3), D, X (`PARAMS:`, `M=`), K (with an optional model).
  - **The document and edit layers** for these: the X-M1 entries of the plan's section 8.1 (names, diagnostics, the index, model types, edits), so that topology, diagnostics and the edit methods work on xyce for these letters.
  - **Spec entries, corpus files with manifests, and solver tests** for every construct read (§10).
- **Not in X-M1:**
  - typed directives other than those above (`.tran`, `.ac`, `.dc`, `.op`, `.options`, `.step`, `.meas`, `.data`): X-M2. Until then they raise `UnsupportedConstruct`;
  - the transient source functions (X-M3) and every other letter (X-M3 to X-M7);
  - a public `Dialect.XYCE` (X-M8).

## 2. Decisions

1. **Workflow as X-M0** (decision 0026; X-M0 decision 3): developer and reviewer subagents report to the lead; gates carry the maintainer's decisions; one commit per completed task; one pull request.
2. **Provenance** as decision 0026 items 2 and 3. Xyce source and headers are never read; the manuals are paraphrased and cited by section and page; nothing produced by Xyce is committed.
3. **The grammar follows the manual** (decision 0026 item 5). Where the binary is more lenient, the difference is a `discrepancies.md` row; where the manual is silent, the solver decides and the entry is `observed` (§11.3 rule 3).
4. **Reuse first.** An xyce construct reuses the ngspice node and rule where the reading is the same (§9.3 item 4), and gets a dialect-specific node only where its meaning differs.

## 3. Stages and gates

1. **Stage 1 — research and probes** (A1 to A3). Reports to the lead; nothing in `src/` changes.
2. **G1 —** the lead writes section 5.1; the maintainer decides X-D1, X-D2, X-D3, X-D5, the `.END` rule and any question the reports raise.
3. **Stage 2 — implementation** (B1 to B7), in the order below, since most tasks touch `xyce.lark`.
4. **R1 —** an independent review; findings are fixed or recorded.
5. **The pull request,** READY FOR REVIEW.

## 4. Tasks

### Stage 1

- [ ] **A1 — Structure and names.** From the manuals and probes: indented lines (X-D1) and what the library should do with them; `.END` strictness; `;` and `+` lines; name characters and case; ground and `.PREPROCESS REPLACEGROUND`; `$G` globals (X-D3); `:` hierarchy, `X1:node` on device lines and in expressions (X-D2), against today's nets layer and LTspice's `NODE_INTO_INSTANCE`; `.GLOBAL`. Options for each decision, with a recommendation.
- [ ] **A2 — Numbers, parameters and expressions.** Scale factors (`X`, `mil`, `a`, `Meg` case), suffixes after scale factors; `.PARAM` forms (braced, quoted, bare; commas; functions), `.GLOBAL_PARAM`, `.FUNC`; bare expressions in instance `name=` values (X-D5); scoping (body `.param` local, last definition wins, `.func` scope); the formula grammar: operators, functions, reserved words, accessors; how far the existing `formula.lark`/`formula_ltspice.lark` serve. Options for X-D5, with a recommendation.
- [ ] **A3 — Statements and elements.** `.MODEL`, `.SUBCKT`/`.ENDS`, includes, `.LIB` call and block, and R, C, L, V, I (DC/AC), D, X, K: each form in the manual against today's ngspice rules and nodes (reuse, reuse with differences, new); the R/C/L model-before-value order and what it means for the nodes and for edits (`set_value`, `set_model`, insertion order); xyce's model types; binned model names. Probes for anything the manual leaves unclear.

### Stage 2

- [ ] **B1 — Decision record(s)** for the G1 decisions (X-D1, X-D2, X-D3, X-D5, `.END`), and the architecture sections they amend.
- [ ] **B2 — Structure, names and numbers** in `xyce.lark`, the names layer and the value grammar; `names.md`, `numbers.md`.
- [ ] **B3 — Parameters and expressions:** `.PARAM`, `.GLOBAL_PARAM`, `.FUNC`, the xyce formula grammar and reserved words; `scoping.md`.
- [ ] **B4 — Statements:** `.MODEL` and model types, `.SUBCKT`/`.ENDS`, includes, `.LIB`, `.GLOBAL`, `.PREPROCESS REPLACEGROUND`.
- [ ] **B5 — Elements:** R, C, L, V, I (DC/AC), D, X, K; `devices.md`.
- [ ] **B6 — The document and edit layers:** the X-M1 lines of the plan's section 8.1; topology, diagnostics and edits on xyce for the letters read.
- [ ] **B7 — Evidence:** spec entries for every construct, corpus files with manifests, solver tests (accept and reject probes, values and nets compared with Xyce), the README status table.

## 5. Findings and log

### 5.1 G1 decisions

(Written at G1.)

### 5.2 Log

- 2026-11-15: task list written; X-M0 archived (approved and merged as #26).
