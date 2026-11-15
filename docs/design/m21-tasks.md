# M21 task list — the xyce and qspice audit

> **Status:** ACTIVE
> **Follows:** [M20](./m20-tasks.md) and [decision 0024](../decisions/0024-the-1-0-public-api.md), whose contract takes effect at `1.0.0`. Governed by [architecture.md](../architecture.md) (§2, §9.2, §9.3, §11, §12, §18).

## 1. Scope

xyce and qspice are planned dialects (§9.2). The maintainer wants to know, before 1.0, whether adding either would change anything decision 0024 covers: public names, signatures, and the exception raised for a condition. If it would, 1.0 would otherwise need a 2.0. M21 answers that question from the manuals alone, and drafts a plan for each dialect. It runs in stages with gates, as M20 did (section 4).

- **In:**
  - **The API audit, per dialect:**
    - every covered part of the public API (decision 0024 items 1 and 2) checked against the dialect's reference;
    - each part classed as fits, additive (a minor release) or disruptive (a covered change);
    - a disruptive part gets options for changing the API before 1.0.
  - **The candidate pressure points** named on 2026-11-14:
    1. element identity as one designator string (xyce's Y-type devices; qspice's device prefixes);
    2. `Placement.AFTER_TITLE` and `BEFORE_END` where a title or `.end` is optional;
    3. the letter-specific edit methods;
    4. per-dialect load options (`rkm`);
    5. whether `Dialect`, `DiagnosticCode` and the item unions may gain members in a minor release.
  - **A draft plan per dialect**, as M8 did for LTspice:
    - the device letters and statements, with what each needs (reuse a node, a new node, out of scope);
    - names, numbers, scoping and structure;
    - what solver evidence is obtainable;
    - a proposed milestone breakdown.
- **Not in M21:**
  - changes to `src/` or to the API: fixes decided at G1 are a later milestone, before 1.0 (decision 6);
  - grammars, spec entries and corpus files for the new dialects.

## 2. Decisions

Decisions 1 to 4 set how the milestone runs and are the lead's, as in M20. Decisions 5 to 7 were the maintainer's, decided on 2026-11-14 before the task list was written.

1. **Roles.** As M20 decision 1: the lead writes the briefs, reviews every report, writes the documents and commits; a reviewer reads, runs read-only checks and reports, and changes no file.
2. **Gates.**
   - **G1 (after stage 1):** the lead checks the findings against the API and the cited sections, and writes section 5.1. The maintainer decides each API finding (fix before 1.0, accept as additive, or record).
   - **G2 (stage 2):** the lead writes the plan drafts from the reports; the maintainer reviews them in the pull request.
3. **Report format.** As M20 decision 3. The kinds are `fits`, `additive`, `disruptive`, `question` and `gap` (a manual silent or unavailable). Every claim cites the manual's section or page.
4. **Parallel work.** The four stage 1 reviewers run in parallel and read only.
5. **Sources.** **Decided (maintainer, 2026-11-14): manuals only.** These are the Xyce Reference Guide and Users' Guide (current release), and qspice's own help and documentation, with each edition and access date recorded. No source code: Xyce is GPL, and P10 also excludes spicelib. Nothing from a source is copied beyond a short citation.
6. **Where fixes go.** **Decided (maintainer, 2026-11-14): audit only.** M21 reports, and G1 decides each finding. The fixes are a separate milestone before 1.0.
7. **Depth.** **Decided (maintainer, 2026-11-14): also draft the dialect plans.** Besides the API points, each dialect gets a draft plan (section 1).

## 3. Starting point (2026-11-14, `8125421`, `m20-api-review`)

- M20 is ready for review as #21; its branch is this list's base. The version is `0.9.0`. The next release is `0.10.0`, after M20 is merged, and `1.0.0` waits for this audit (decision 0024, consequences).
- No xyce or qspice material exists in the repository beyond §9.2's one line. There is no solver for either on the maintainer's machine; solver evidence is a question for the plans.

## 4. Tasks

### Stage 0 — Set-up (lead)

[x] **T0 — Branch, list and briefs.** Branch `m21-dialect-audit` from `m20-api-review`; this list; the stage 1 briefs.

### Stage 1 — Reviews (independent reviewers, in parallel; read-only)

[ ] **X1 — xyce against the API.** The covered surface (decision 0024 items 1 and 2), the five candidate points, and anything else, checked against the Xyce Reference Guide.

[ ] **Q1 — qspice against the API.** The same, against qspice's documentation.

[ ] **X2 — xyce inventory for the plan.** Device letters and their forms, statements, names, numbers, scoping, structure, expressions, the solver's availability and its command line.

[ ] **Q2 — qspice inventory for the plan.** The same for qspice.

### Gate G1 (lead, then the maintainer)

[ ] **G1 — Classification and decisions.** Section 5.1 written; the maintainer decides each API finding.

### Stage 2 — Plans (lead)

[ ] **P1 — The xyce plan draft** and **P2 — the qspice plan draft**, from X2 and Q2 and the G1 decisions.

[ ] **T1 — Pull request.** Docs checks, the pull request, CI green, `READY FOR REVIEW`.

## 5. Findings and log

### 5.1 Items for the maintainer

To come (G1).

### 5.2 Subtask log

- [x] T0: branch, this list and the stage 1 briefs.
- [ ] X1
- [ ] Q1
- [ ] X2
- [ ] Q2
- [ ] G1
- [ ] P1, P2
- [ ] T1
