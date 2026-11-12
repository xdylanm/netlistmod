# M19 task list — v1 review package and beta tag

> **Status:** READY FOR REVIEW — stages 1 and 2 are done; T1's evidence and the review package are in [v1-review.md](./v1-review.md)
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

2026-11-11, at `3000e95`, in a clean worktree of `main`, Windows, Python 3.14.3, ngspice 47 and LTspice 26.1.1, with `--require-solver ngspice --require-solver ltspice`: **10,173 passed, 2 skipped** (POSIX only), 1,420 deselected; coverage **98.73%** (44 lines and 35 branches uncovered, in 19 modules). This is the same tree as M18's final run.

## 4. Tasks

Every task that changes a file ends with the checks green, run as `uv run --env-file .env python -m <tool>`: `ruff check`, `ruff format --check`, `mypy --strict` (the package and the named tests of `docs/testing.md`), `lint-imports`, `pre-commit run --all-files` and the tests the task names. Findings outside this list go to section 5.1. Nothing is resolved silently (§15, §21).

### Stage 0 — Set-up (lead)

[x] **T0 — Branch, baseline and briefs.** Branch `m19-v1-review`; the baseline run of section 3.2; this list; the stage 1 briefs.

### Stage 1 — Reviews (independent reviewers, in parallel; read-only)

[x] **A1 — User documents, read as a new user.**
- The README, `docs/usage/README.md`, each usage guide, the error reference, `ltspice-export.md` and the examples' `--help`.
- Is each device letter, editable property, exception and diagnostic code of v1 described, with the dialect it covers? Are LTspice's differences shown where they matter?
- Stale wording about phases, milestones or what is "not yet" supported; links that would be dead on the PyPI page (decision 0018 item 6).
- Each public name of `netlistmod.__all__` against the guides: named, or deliberately left to the living references.
- API findings for the 1.0 review (section 1) are listed apart.

[x] **A2 — Records and the gate.**
- Plan section 6: for each gate item, the evidence that shows it, or the gap.
- The limits that remain: every limit named in the phase 1 review, decisions 0010 to 0021, the task lists' section 6.3 notes and the `discrepancies.md` files, each with its state (closed, accepted, open). This list becomes the package's limits section.
- The architecture, `testing.md`, `provenance.md`, `AGENTS.md`, `CONTRIBUTING.md`, the four living references and the decision index, against the code, for wording written before phase 2.
- Every corpus family has a manifest and a `provenance.md` row, and no LTspice raw file, log or timing number is in the repository.

[x] **A3 — Package and coverage.**
- The coverage report of the baseline run: each uncovered line or branch, what it is, and whether it is reachable.
- Build the wheel and the sdist; install the wheel in a new environment, then import, parse and edit on both dialects; check the sdist's contents and the wheel's data files (`*.lark`, `*.json`).
- The package metadata: classifiers, URLs, `requires-python`, the runtime dependencies and their licences.
- The release workflow against decision 0018, for a `0.9.0` release.

**G1** (lead): section 5.1, then the maintainer's decisions on any finding that needs one.

### Stage 2 — Development (independent developers; after G1)

The briefs are written at G1 from the findings. Expected:

The developers' files do not overlap: D1 the README and `docs/usage/` apart from `errors.md`; D2 `errors.md` and the CHANGELOG; D3a the architecture, decision 0022, `AGENTS.md`, `CONTRIBUTING.md` and the run times; D3b the living references, `testing.md`, `provenance.md` and the grammar documents; D4 and D5 `src/` docstrings, tests and `pyproject.toml`.

[x] **D1 — README and usage guides.** The README's v1 status and "What it does" list; the usage index; each guide's fixes from A1; executed examples where a v1 form has none.

[x] **D2 — Error reference and CHANGELOG.** The error reference's fixes from A1, and the CHANGELOG per decision 9.

[x] **D3a — Architecture and rules.** Decision record 0022 for the normative fixes (5.1.1 point 3), the architecture's other stale text, `AGENTS.md` (point 4), `CONTRIBUTING.md`, and the run times (point 5).

[x] **D3b — Living references and records.** The four living references, `testing.md`, `provenance.md`, and the grammar READMEs, device matrices and `discrepancies.md` prose.

[x] **D4 — Source docstrings** (5.1.1 point 1): text only.

[x] **D5 — Coverage tests.** A test for each reachable path of section 5.1 (A3-1), and the coverage floor of 98 (5.1.1 point 8).

### Stage 3 — Evidence and handover (lead)

[x] **T1 — Final evidence.** The full check set with `--require-solver ngspice --require-solver ltspice` from a clean clone of the commit under review, with the wheel build and install of A3, and one solver-free run on `lark` 1.2.2 (5.1.1 point 7). No run times (point 5).

[x] **T2 — The review package, `v1-review.md`:** where things stand; T1's results; the coverage report with each uncovered line's disposition; the spec coverage per decision 8; the gate checklist with its evidence, marking the items only the maintainer can complete; the limits for the maintainer's decision; and a hands-on script for transistor and behavioural circuits.

[x] **T3 — Hand over.** The pull request and CI; the plan's status line and M19 heading; `design/README.md`; this list `READY FOR REVIEW`. **Do not archive.**

### After the maintainer's approval

[ ] **T4 — The gate and the close.** The maintainer's hands-on use and decisions on the limits are recorded in the package. Then this list, the package and the plan become `COMPLETE (date)` and move to `archive/phase-2/`, with the links fixed. The release follows decision 5.

## 5. Results

### 5.1 Review findings (G1)

The three reports were checked by the lead on 2026-11-11: every `defect` reproduced or read in the file, and a sample of the rest. Each report's full table stays with the lead's notes; this section classifies them.

**The gate (A2).** G1 to G5 are met by tests and CI at `3000e95` (G2, G3 and G5 are repeated by T1 and the M19 pull request). G6 waits on T1. G7 (hands-on use, carried from M13 T14), G8 (the limits) and G9 (archiving) are the maintainer's.

**Limits (A2).** 38 collected, deduplicated (L1 to L38). Open: library files (after the beta), the 1.0 API review, the hands-on checkpoint, and three cosmetic notes. The rest are closed or accepted by a decision. They become the package's limits section (T2).

| Group | Findings | Classification | Goes to |
|---|---|---|---|
| README | A1-2 to 7, A3-12 | stale or gap: "the phase 1 elements", "phase 2 is under way", milestone tags in the element table, the edit list stops at phase 1, LTspice `.control`/`.if`, the plan link that moves at T4 | D1 |
| Usage guides and examples | A1-9 to 20, 22 to 25, 28 to 30 | stale wording and milestone tags; gaps (LTspice values, stimulus and `.param` differences; `set_coupling`, `directives.replace`, `BEFORE_END`, `allow_external`; what cannot be added or removed; four public names); doc defects (`elements.md:306` says LTspice E and G take no parameter; `read_only_demo.py --help` crashes; an unused import and an undefined `rt` in `editing.md`) | D1 |
| Error reference and CHANGELOG | A1-26, A1-27, A2-27 | "Since M17"; `DiagnosticCode` not named; the `.if` depth is 247 levels, not about 300 | D2 |
| Architecture, normative | A2-1, 2, 3, 7, 11 | stale or gap: RKM as "the only exception" to decision 0002; §7.7 omits A's `ports` and `%vnam` entries and POLY's several `control` entries; §17 omits `CONTROL_SOURCE_MISMATCH`; rule 10 on bare formulas; the info rule's opaque scopes | D3, through decision record 0022 |
| Other records | A2-4 to 6, 8 to 10, 12 to 16, 18 to 26, 29 to 34, 36, 37, 42 to 44; A1-31, A1-32 | stale wording, the living references' phase 2 gaps, `testing.md`, nine corpus families missing from `provenance.md`, the grammar READMEs and device matrices | D3 |
| Coverage | A3-1, coverage table | 8 reachable paths with no test (about 13 lines and 2 branches), each probed and behaving as intended; the rest accepted as in phase 1 (defensive, packaging or internal faults, POSIX only) | D5 (tests are M19's own work) |
| Package | A3-2 to 5, 7, 9 | ok: the wheel and sdist build, the wheel holds the grammars and data files, a clean install loads and edits both dialects, `twine check` passes, the release workflow fits a `0.9.0` | — |
| Release checklist | A3-4, A3-8, A3-10 | for the `release-0.9.0` branch: `uv.lock`'s own version (CI runs `uv sync --locked`), the classifier, the CHANGELOG heading, the README's release line; optional: anchor the sdist's `README.md` and `LICENSE` patterns, and a phase 2 smoke step | T2's release checklist |
| For the maintainer | A1-8/A3-11, A1-21/A2-28, A2-35, A2-41, A3-6, A3-13, A3-14, A3-15 | section 5.1.1 | — |
| 1.0 notes | A1 N-1 to N-11 | recorded for the 1.0 review, not acted on (section 1) | T2 |

#### 5.1.1 For the maintainer

**Decided (maintainer, 2026-11-11):** points 1 to 4, 6, 7 and 8 as recommended; point 5 as amended there.

1. **Two `src/` docstrings** (A1-21, A2-28): "(review R3)" in `edit/api.py` (two places), and `ModelStatement`'s description of `flags`, which also holds LTRA's. *Recommendation:* fix in M19 as D4, text only.
2. **Two loads that a reviewer questioned** (A3-14, A3-15), reproduced: on ngspice `R1 a 0 1k |` reads `|` as the model, and on both dialects `D1 a 0 2` reads `2` as the model. Each gives `UNRESOLVED_MODEL` (a warning), so neither is silent, and neither misreads a field that has another meaning. *Recommendation:* no change in M19; record both as limits for the 1.0 review.
3. **Normative architecture fixes** (A2-1, 2, 3, 7, 11). *Recommendation:* one decision record, 0022, in D3: it corrects the text to what decisions 0013 to 0021 already decided, and changes no behaviour.
4. **`AGENTS.md`** (A2-35): its constitution omits P8, P11, P12 and P13. *Recommendation:* add them, one line each, as the others.
5. **Run times** (A2-41): archived task lists record whole-suite times that include LTspice runs; decision 0009 item 2 keeps LTspice timing numbers out of the repository. *Recommendation:* new records (T1 and the package) give no times; archived records stay as history, since an archived file is edited only to fix links. **Decided otherwise:** new records give no times, and the whole-suite and LTspice suite times are also removed from the archived task lists, the plan and `testing.md`, an exception to the archive rule made by the maintainer. A time for an ngspice-only run may stay.
6. **README links on PyPI** (A1-8, A3-11): relative links are dead on PyPI, even once the repository is public. *Recommendation:* keep them for `0.9.0` (decision 0018 item 6), and make them absolute when the repository is made public.
7. **The `lark` lower bound** (A3-6): `lark>=1.2.2`, with every run on 1.3.1; a smoke test passes on 1.2.2. *Recommendation:* one solver-free full run on 1.2.2 in T1.
8. **The coverage floor** (A3-13): `fail_under = 90` while the suite is at 98.7%. *Recommendation:* raise it to 98 after D5.

### 5.2 Subtask log

| Subtask | Role | Reported | Lead's review | Commit |
|---|---|---|---|---|
| T0 | Lead | 2026-11-11 | Baseline recorded (section 3.2); decisions 5 to 10 decided | this commit |
| A1 | Reviewer | 2026-11-11: complete with findings (32, and 11 notes for 1.0) | Spot-checked; classified at G1 | — |
| A2 | Reviewer | 2026-11-11: complete with findings (47; gate table; 38 limits) | Spot-checked; classified at G1 | — |
| A3 | Reviewer | 2026-11-11: complete with findings (15; coverage table) | Two loads reproduced; classified at G1 | — |
| G1 | Lead | 2026-11-11 | Section 5.1; eight points for the maintainer (5.1.1), decided the same day | `6ef5023`, this commit |
| D2 | Developer | 2026-11-11: complete with findings (the `.if` depth is 247, measured) | Diff read; operations in the v1 summary checked against `edit/api.py`; accepted | this commit |
| D3a | Developer | 2026-11-11: complete (decision 0022 proposed; 40 run times removed) | Diff read; 0022 checked against its source decisions; the lead added the `.lib` block to §11.2's opaque list, which the developer reported; the 30 s LTspice timeout in `m8-tasks.md` is a setting, not a measured time, and stays; accepted | this commit |
| D3b | Developer | 2026-11-11: complete | Diff read; the lead completed the `ltspice_transistors` provenance row, which lacked its author and licence cells; the plan links in the device matrices are fixed at T4, and `testing.md`'s coverage floor with D5; accepted | this commit |
| D1 | Developer | 2026-11-11: complete with findings (the brief's check ran the six solver-marked demo tests; they passed and wrote only to `tmp_path`) | Diff read; the README's edit list checked against `edit/api.py`; the lead noted in the CHANGELOG that a path given to `read_only_demo.py` is now read without RKM unless `--rkm` is given; accepted | this commit |
| D4, D5 | Developer | 2026-11-11: complete (11 paths tested; solver-free run 10,205 passed, coverage 99.22%, floor 98) | Diff read; the touched tests and the fast checks rerun; the lead updated `testing.md`'s floor and the oracle's module note, which named review IDs. "(review R3)" in the private `edit/_ops_*` modules stays: point 1 covered the public docstrings; accepted | this commit |
| T1 | Lead | 2026-11-11 | Clean clone of `745991e`: 10,205 passed, 2 skipped, coverage 99.22%; all checks clean; wheel smoke on both dialects; `lark` 1.2.2 solver-free 10,135 passed | this commit |
| T2 | Lead | 2026-11-11 | `v1-review.md`; the maintainer's hands-on use and section 5.1 recorded; decision 0016 item 1's wording corrected through decision 0022 item 6 | `db3e75d`, `d5edd30`, `2903dc9`, this commit |
| T3 | Lead | 2026-11-11 | Plan, index and this list set; pull request opened | this commit |
