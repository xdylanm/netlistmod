# M19 task list — v1 review package and beta tag

> **Status:** ACTIVE — decisions 5 to 10 decided by the maintainer on 2026-11-11; stage 0 is under way
> **Part of:** [phase-2-plan.md](./phase-2-plan.md) (milestone M19, v1 gate in section 6). Governed by [architecture.md](../architecture.md) (§2, §6.7, §10, §11, §13, §14, §17, §18). Follows [M18](./archive/phase-2/m18-tasks.md), and carries its section 5.3 point 9 and [M13](./archive/phase-2/m13-tasks.md) T14.

## 1. Scope

M19 adds no construct. It brings the user-facing documents up to v1, gathers the evidence for the v1 gate, and assembles the review package the maintainer uses to decide the gate. As in [M9](./archive/phase-1/m9-tasks.md), phase 1's review package, most of the work is reading and writing. As in M18, it runs in **stages with review gates** (section 4): independent reviewers audit first, independent developers then fix what the audits find, and the lead reviews each report before the next stage starts.

- **In (plan M19):**
  - **Documents:** the usage guides, the error reference, the README and the CHANGELOG. The README says the library is feature complete for v1.
  - **Evidence:** the full check set from a clean clone with both solvers, as phase 1's T10.
  - **The v1 review package:** `docs/design/v1-review.md`, with the coverage report, the spec coverage, the gate checklist with its evidence, the remaining limits for the maintainer's decision, and a hands-on script.
- **Carried:**
  - README lines 56 and 64 ("the phase 1 elements", "phase 2 is under way"; M18 5.3 point 9).
  - M13 T14, the maintainer's hands-on checkpoint with real transistor netlists. It becomes the gate item "You have used the library on your own netlists, including transistor and behavioural circuits".
- **Not in M19:**
  - new constructs, and resolving the limits the package lists;
  - what 1.0 commits to in the public API (§18), which the plan reviews after the maintainer's practical use. Reviewers note API findings for that review, and M19 does not act on them;
  - the version and the release, which follow the gate on their own branch (decision 5).

## 2. Decisions

Decisions 1 to 4 set how the milestone runs and are the lead's, as in M18. Decisions 5 to 10 were proposed for the maintainer, each with a recommendation, and decided on 2026-11-11.

1. **Roles.** As M18 decision 1:
   - **Lead** (the session that owns this document): writes the briefs, reviews every report and diff, runs the checks, updates this document and commits. Only the lead commits.
   - **Reviewer** (stage 1): reads and runs read-only checks. It changes no file in the repository and reports findings.
   - **Developer** (stage 2): changes only the files its brief names, runs the named checks and reports. It does not commit.
2. **Gates.**
   - **G1 (after stage 1):** the lead checks each finding (each `gap` by reproduction or by reading) and classifies it in section 5.1. A finding that changes behaviour, the plan or a decision goes to the maintainer.
   - **G2 (after each stage 2 subtask):** the lead reads the diff, runs the subtask's tests and the fast checks, and accepts it (commit, tick) or sends it back with numbered changes.
   - **G3 (after stage 2):** the clean-clone run with both solvers (T1), the review package (T2), the pull request and CI, then `READY FOR REVIEW`.
3. **Report format.** As M18 decision 3: a one-line verdict (`complete`, `complete with findings` or `blocked`), then a table with ID, location, finding, kind (`ok`, `gap`, `stale`, `defect`, `question`) and proposed action.
4. **Parallel work.** Stage 1's reviewers run in parallel and read only. Stage 2's developers run in parallel only when their files do not overlap.
5. **The version and the tag.** **Decided (maintainer, 2026-11-11): as recommended.** The plan's M19 sets the version to `0.9.0` and tags `v0.9.0` after the gate. Since 2026-11-08 the maintainer decides each release apart from the milestones, and a milestone ends at its own merged pull request.
   *Recommendation:* the M19 pull request does not change the version. After the gate passes, a `release-0.9.0` branch does what `release-0.5.0` did ([decision 0018](../decisions/0018-pypi-publication.md)): the version `0.9.0`, the classifier `Development Status :: 4 - Beta`, the CHANGELOG heading `0.9.0 — date`, and the README's release line. The maintainer then tags `v0.9.0` and publishes the GitHub Release, which publishes to PyPI. The plan's M19 entry is amended to say so.
   *Alternative:* as the plan says, M19's pull request sets `0.9.0`, and the tag follows the gate.
6. **Source changes.** **Decided (maintainer, 2026-11-11): as recommended.** As in M9 decision 3, M19 changes documents, tests and the examples, not `src/`.
   *Recommendation:* a reviewer's `defect` in `src/` becomes an entry in section 5.1 with a reproducer, for the maintainer to triage: fix in M19 (a developer subtask, reviewed at G2, with a decision record if it changes behaviour), or record it as a limit. A message or docstring fix found in reading is a `src/` change too, and is triaged the same way.
7. **Where the package lives.** **Decided (maintainer, 2026-11-11): as recommended.** `docs/design/v1-review.md`, moved to `archive/phase-2/` with this list and the plan once the gate passes, as phase 1's package was.
8. **Spec coverage in the package.** **Decided (maintainer, 2026-11-11): as recommended.** Since M18 each grammar README has a generated "Validation status" table ([decision 0021](../decisions/0021-completeness-audit.md) item 8).
   *Recommendation:* the package gives the totals per dialect and links to the two tables, with no third copy. *Alternative:* a generated section in the package, as phase 1's package had.
9. **The CHANGELOG.** **Decided (maintainer, 2026-11-11): as recommended.** The `Unreleased` section holds one entry per milestone from M15b to M18.
   *Recommendation:* add a short v1 summary at the top of `Unreleased` (the dialects, every device letter, the editable properties, the guarantees and the named exclusions), keep the milestone entries under it, and fix the duplicated M15b heading. Nothing above `0.5.0` is rewritten.
10. **The evidence.** **Decided (maintainer, 2026-11-11): as recommended.** The final run is on Windows with Python 3.14, ngspice 47 and LTspice 26.1.1, from a clean clone of the commit under review (T1). Linux and Python 3.13 are covered by CI, which installs no solver (decision 0011). There is no solver run on Linux.

## 3. Starting point (2026-11-11, `3000e95`, `main`)

### 3.1 Inventory

- **Version:** `0.5.0`, classifier `3 - Alpha`; the only tag is `v0.5.0`. The release workflow publishes on a GitHub Release (decision 0018).
- **Decisions:** 0001 to 0021, all accepted.
- **Spec entries:** ngspice 75 (73 `validated`, 2 `observed`), LTspice 73 (`validated`), none `documented`.
- **Device matrices:** every letter `supported`, apart from the two named exclusions of v1 (the ngspice digital U and LTspice `.machine`).
- **Task lists:** M10 to M18 archived. M13 T14 is open (section 1).
- **Documents seen as stale before the audits:**

| Item | Gap |
|---|---|
| README line 56 | "the phase 1 elements" |
| README line 64 | "phase 2 is under way" |
| `docs/usage/README.md` | `elements.md` "covers R, C, L, K, V, I, D and X" |
| `CHANGELOG.md` | The M15b heading is written twice; there is no v1 summary |

### 3.2 Baseline run

*Filled in from the run started on 2026-11-11 at `3000e95`, in a clean worktree, with both solvers required.*

## 4. Tasks

Every task that changes a file ends with the checks green, run as `uv run --env-file .env python -m <tool>`: `ruff check`, `ruff format --check`, `mypy --strict` (the package and the named tests of `docs/testing.md`), `lint-imports`, `pre-commit run --all-files` and the tests the task names. Findings outside this list go to section 5.1. Nothing is resolved silently (§15, §21).

### Stage 0 — Set-up (lead)

[ ] **T0 — Branch, baseline and briefs.** Branch `m19-v1-review`; the baseline run of section 3.2; this list; the stage 1 briefs.

### Stage 1 — Reviews (independent reviewers, in parallel; read-only)

[ ] **A1 — User documents, read as a new user.**
- The README, `docs/usage/README.md`, each usage guide, the error reference, `ltspice-export.md` and the examples' `--help`.
- Is each device letter, editable property, exception and diagnostic code of v1 described, with the dialect it covers? Are LTspice's differences shown where they matter?
- Stale wording about phases, milestones or what is "not yet" supported; links that would be dead on the PyPI page (decision 0018 item 6).
- Each public name of `netlistmod.__all__` against the guides: named, or deliberately left to the living references.
- API findings for the 1.0 review (section 1) are listed apart.

[ ] **A2 — Records and the gate.**
- Plan section 6: for each gate item, the evidence that shows it, or the gap.
- The limits that remain: every limit named in the phase 1 review, decisions 0010 to 0021, the task lists' section 6.3 notes and the `discrepancies.md` files, each with its state (closed, accepted, open). This list becomes the package's limits section.
- The architecture, `testing.md`, `provenance.md`, `AGENTS.md`, `CONTRIBUTING.md`, the four living references and the decision index, against the code, for wording written before phase 2.
- Every corpus family has a manifest and a `provenance.md` row, and no LTspice raw file, log or timing number is in the repository.

[ ] **A3 — Package and coverage.**
- The coverage report of the baseline run: each uncovered line or branch, what it is, and whether it is reachable.
- Build the wheel and the sdist; install the wheel in a new environment, then import, parse and edit on both dialects; check the sdist's contents and the wheel's data files (`*.lark`, `*.json`).
- The package metadata: classifiers, URLs, `requires-python`, the runtime dependencies and their licences.
- The release workflow against decision 0018, for a `0.9.0` release.

**G1** (lead): section 5.1, then the maintainer's decisions on any finding that needs one.

### Stage 2 — Development (independent developers; after G1)

The briefs are written at G1 from the findings. Expected:

[ ] **D1 — README and usage guides.** The README's v1 status and "What it does" list; the usage index; each guide's fixes from A1; executed examples where a v1 form has none.

[ ] **D2 — Error reference and CHANGELOG.** The error reference's fixes from A1, and the CHANGELOG per decision 9.

[ ] **D3 — Records.** The architecture, `testing.md` and other records from A2, through a decision record if a fix is normative.

[ ] **D4 — Source fixes,** only if the maintainer triages a `defect` into M19 (decision 6).

### Stage 3 — Evidence and handover (lead)

[ ] **T1 — Final evidence.** The full check set with `--require-solver ngspice --require-solver ltspice` from a clean clone of the commit under review, with the wheel build and install of A3.

[ ] **T2 — The review package, `v1-review.md`:** where things stand; T1's results; the coverage report with each uncovered line's disposition; the spec coverage per decision 8; the gate checklist with its evidence, marking the items only the maintainer can complete; the limits for the maintainer's decision; and a hands-on script for transistor and behavioural circuits.

[ ] **T3 — Hand over.** The pull request and CI; the plan's status line and M19 heading; `design/README.md`; this list `READY FOR REVIEW`. **Do not archive.**

### After the maintainer's approval

[ ] **T4 — The gate and the close.** The maintainer's hands-on use and decisions on the limits are recorded in the package. Then this list, the package and the plan become `COMPLETE (date)` and move to `archive/phase-2/`, with the links fixed. The release follows decision 5.

## 5. Results

### 5.1 Review findings (G1)

*Filled in at G1.*

### 5.2 Subtask log

| Subtask | Role | Reported | Lead's review | Commit |
|---|---|---|---|---|
