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

[x] **X1 — xyce against the API.** The covered surface (decision 0024 items 1 and 2), the five candidate points, and anything else, checked against the Xyce Reference Guide.

[x] **Q1 — qspice against the API.** The same, against qspice's documentation.

[x] **X2 — xyce inventory for the plan.** Device letters and their forms, statements, names, numbers, scoping, structure, expressions, the solver's availability and its command line.

[x] **Q2 — qspice inventory for the plan.** The same for qspice.

### Gate G1 (lead, then the maintainer)

[ ] **G1 — Classification and decisions.** Section 5.1 written; the maintainer decides each API finding.

### Stage 2 — Plans (lead)

[ ] **P1 — The xyce plan draft** and **P2 — the qspice plan draft**, from X2 and Q2 and the G1 decisions.

[ ] **T1 — Pull request.** Docs checks, the pull request, CI green, `READY FOR REVIEW`.

## 5. Findings and log

### 5.1 Items for the maintainer

**xyce.** The two xyce reviews found nothing that would change a covered name, signature or exception class. Every point of decision 0024's covered surface `fits` or is `additive`. These are the points the reviews raise for 1.0:

1. **Growth (X1-18 to X1-20; Q1-5; X2).** A new dialect adds a `Dialect` member, node classes in `TopLevelItem`/`BodyItem`, `DiagnosticCode` members and values in `Literal` vocabularies (`StepDirective.kind` among them). Decision 0024 makes annotations, fields and diagnostics best-effort, but it says nothing about `Dialect` members or new node classes. A caller that matches exhaustively on `Dialect`, or on today's node classes, would break.
   *Recommendation:* one sentence in decision 0024 and §18, made in the fix milestone: minor releases may add `Dialect` members, node classes, union members and `Literal` values. Documentation only.
   **Decided (maintainer, 2026-11-15): as recommended.**
2. **What a designator is (X1-1; X2).** xyce's Y-type devices write the type and the name as two tokens (`YMEMRISTOR mr1 n1 n2 m`; Reference Guide Table 2-35), and the name is unique only together with the type (§2.3.29). A `str` still identifies such a device, so the signatures fit. But "designator" is nowhere defined as possibly more than one token.
   *Recommendation:* in the fix milestone, state in decision 0024 and `elements.md` that a designator is the string naming an element in its dialect and need not be a single token. The xyce milestone picks the convention: the two tokens as written, or xyce's own `Y<type>!<name>`. Documentation only.
   **Decided (maintainer, 2026-11-15): as recommended.**
3. **Load options (X1-9; X2).** xyce's command-line flags `-hspice-ext` and `-redefined_params` change how a netlist is read: what `a` means, the hierarchy separator, and which repeated `.param` wins.
   *Recommendation:* nothing before 1.0. If the library needs to model them, they become keyword arguments with defaults, which is additive. `rkm=True` on xyce is a `ValueError`, as on LTspice.
   **Decided (maintainer, 2026-11-15): as recommended.**
4. **Nets that reach into an instance, and `$G` globals (X1-2; X2).** xyce allows `X1:node` on device lines and treats every `$G…` node as global.
   *Recommendation:* nothing before 1.0. Net identity sits behind `nets()` and `Net`, whose fields are best-effort; the xyce milestone decides whether to refuse these forms or to model them.
   **Decided (maintainer, 2026-11-15): as recommended.**

The two reports are also the inventory for the xyce plan (P1): about 70% of the constructs reuse ngspice nodes. The five that do not fit the current model, each a plan risk rather than an API change:
- the two-token designator;
- `X1:node` on device lines;
- `$G` globals;
- a line that starts with whitespace is a comment;
- bare expressions in `.param` and instance parameters.

**qspice.** Both qspice reviews are `gap`. Qorvo publishes no reference online. The help ships inside the installer, which needs a registration with an email address. Architecture §12 says a proprietary built-in help is not cited, as was decided for LTspice's. On the API side, nothing is disruptive by construction. Two points depend on facts the help would settle:
- whether an instance name is always one token (designator, as item 2);
- whether a netlist's first line is always a title (`AFTER_TITLE`).

5. **qspice's sources.** *Options:*
   - **A.** The maintainer installs QSPICE; the lead checks the help's terms. If they allow paraphrase with citation, a decision record extends §12 to it and Q1 and Q2 run again.
   - **B.** Evidence only: the grammar comes from solver probes, each behaviour an `observed` entry. §12 allows this, but it departs from the manual-driven policy (P5, §11).
   - **C.** Defer qspice: 1.0 is audited against xyce only. For both open qspice points the reviewers found fall-backs that are additive (a designator defined per dialect, as item 2; a title exception as in decision 0009), so the risk is small.

   *Recommendation:* A if the maintainer is willing to register, otherwise C.
   **Open (maintainer, 2026-11-15): investigating.** The maintainer can install QSPICE (and Xyce), and found a further source, the `KSKelvin-Github/Qspice` repository. The lead checked it on 2026-11-15:
   - GitHub gives its licence as GPL-3.0.
   - It describes itself as "Qspice Unofficial Guidelines".
   - Its reference PDFs (Command, Device and General Reference Guides) are a third party's, not Qorvo's.

   Using it would need a decision record. Decision 5 names qspice's own documentation, §11 makes the manual the authority, and §12 and P10 keep GPL material out of the project. It is not proposed as a reference.

### 5.2 Subtask log

- [x] T0: branch, this list and the stage 1 briefs.
- [x] X1: `complete with findings`. Sources: the Xyce Reference Guide and Users' Guide, version 7.10 (SAND2025-05993 and SAND2025-05995, May 2025; xyce.sandia.gov, accessed 2026-11-14). No finding is `disruptive`; two documentation-only questions (5.1). The lead checked the Y-type form (Reference Guide Table 2-35) and the title and `.END` rule (Users' Guide §4.1.1).
- [x] Q1: `gap`. Qorvo publishes no qspice reference online; the help ships inside the installer, behind a registration form. On the API side nothing is disruptive by construction; two points depend on unverified qspice facts (5.1).
- [x] X2: `complete with findings`. The inventory for the xyce plan (devices, statements, names, numbers, scoping, solver evidence, milestones). The lead checked the leading-whitespace comment rule (Users' Guide §4.1.3.1) and R's model-before-value form.
- [x] Q2: `gap`, for the same reason as Q1. The official pages establish that QSPICE is free, Windows-only, and can export and run a netlist without the GUI; architecture §12 does not allow citing a proprietary built-in help (as for LTspice), so qspice's sources need a maintainer decision (5.1).
- [ ] G1
- [ ] P1, P2
- [ ] T1
