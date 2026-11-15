# X-M0 task list — xyce set-up and solver spike

> **Status:** ACTIVE — stage 1 (research, audit and probes)
> **Follows:** [the xyce plan](./xyce-plan.md) section 8 and the 1.0 release ([decision 0024](../decisions/0024-the-1-0-public-api.md)). Governed by [architecture.md](../architecture.md) (§2, §3, §9.2, §9.3, §10, §11, §12, §18).

## 1. Scope

X-M0 is the first of the xyce milestones (X-M0 to X-M8). It sets up the dialect, the solver harness and the documentation skeleton, and probes the rules that later milestones rely on. It reads no xyce element yet.

- **In:**
  - **References:** `[xyce-ref]` and `[xyce-ug]` (Version 7.10) in `docs/references.md`, with their editions, access dates and licence terms.
  - **Decision X-D0** (a decision record): the references, the evidence policy, how the dialect stays hidden, the overlay on `core.lark`, and what X-M0's xyce reads.
  - **The dialect audit:** every place in `src/` that branches on a dialect, classified for a third dialect.
  - **A hidden xyce dialect:** the loader registry, an overlay and a device table, reachable only through an internal name (decision 1).
  - **The solver harness:** `XYCE_EXE` discovery, `tests/support/xyce.py`, `--require-solver xyce`, and `.env.example`.
  - **Probes** (local solver tests) of the rules section 6 lists.
  - **`docs/grammars/xyce/`:** the skeleton of §9.3.
- **Not in X-M0:**
  - any element, typed directive or value grammar (X-M1 onwards);
  - decisions X-D1 to X-D6, in their own milestones;
  - a public `Dialect.XYCE`, added at X-M8 (decision 1).

## 2. Decisions

1. **The dialect stays hidden until X-M8.** **Decided (maintainer, 2026-11-15).** The xyce milestones merge to `main`, but `Dialect.XYCE` joins the public enum only after the X-M8 review. Until then tests reach the dialect through an internal name, so a release in between ships nothing of xyce and the 1.0 contract does not bind a half-built grammar. The mechanism is chosen at G1 from the audit (task A2).
2. **Evidence as for ngspice.** **Decided (maintainer, 2026-11-15).** Tests run Xyce locally and generate raw files and logs at test time; nothing from Xyce is committed. Spec entries record the Xyce version in `validated_on`, and fixtures are authored here. Recorded in X-D0.
3. **Workflow as M18 to M21.** **Decided (maintainer, 2026-11-15).** Developer and reviewer subagents report to the lead; gates carry the maintainer's decisions; one commit per completed task; one pull request for the milestone.
4. **Provenance (P10).** Xyce is GPLv3. Its source code, including the headers installed with it (`include/`), is never read. Its manuals are paraphrased and cited by page (§11.3 rule 4). Running the binary is allowed.
5. **The plan is the roadmap.** The xyce plan moves from DRAFT to ACTIVE with this milestone; its decisions X-D1 to X-D6 are still open.

## 3. Stages and gates

1. **Stage 1 — research, audit and probes** (tasks A1 to A4). Reports to the lead; nothing in `src/` changes.
2. **G1 —** the lead writes section 5.1 from the reports; the maintainer decides the hiding mechanism, the reading of X-M0's xyce, and what the probes imply.
3. **Stage 2 — implementation** (tasks B1 to B5).
4. **R1 —** an independent review of the branch; findings are fixed or recorded.
5. **The pull request,** READY FOR REVIEW.

## 4. Tasks

### Stage 1

- [ ] **A1 — References.** Record `[xyce-ref]` and `[xyce-ug]` 7.10 in `references.md`: URL, edition (SAND number, date), access date, and the licence or release terms printed in the manuals. Confirm the printed page numbers the plan cites resolve.
- [ ] **A2 — The dialect audit.** List every place in `src/` that tests a dialect (`Dialect.LTSPICE`, `Dialect.NGSPICE`, and dicts keyed by dialect). For each: what a third dialect would get today (often the ngspice branch, by `else`), and whether that is right, wrong or unknown for xyce. Propose how the hidden dialect is reached (decision 1), with the effect on `Dialect`, `load`, type annotations and `__all__`, and the architecture tests that guard it.
- [ ] **A3 — The solver.** Check that `XYCE_EXE` (`xyce.exe`, XyceNF 7.10) runs under Smart App Control in batch mode; the version line for `validated_on`; `-syntax`, `-norun`, `-r` with `-a`, and `-namesfile`; exit codes and where errors are written. Whether `tests/support/raw.py` reads Xyce's ASCII raw file.
- [ ] **A4 — Probes** (section 6), each a minimal netlist authored here, run with `-syntax` or `-norun` and, where it matters, a real run:
  1. an unknown dot-command;
  2. a line that begins with whitespace (an element line, and a `.param`);
  3. a `+` continuation after a comment line;
  4. a node written in brackets (`[node]`), as the manual's syntax uses brackets for optional fields;
  5. `//` and `;` after a statement;
  6. the first line as the title, and a file without `.END`.

### Stage 2

- [ ] **B1 — Decision X-D0** (`docs/decisions/0026-…`): items 1, 2 and 4 of section 2; the hiding mechanism and the reading of X-M0's xyce as decided at G1; the closed dot-command list as a goal for X-M2. Architecture §9.2 and §12 updated.
- [ ] **B2 — The hidden dialect:** the internal name, the loader registry, `xyce.lark` on `core.lark` and `xyce-devices.json`, as decided at G1. Tests: a load with the hidden dialect; `Dialect` has no public xyce member; the audit's wrong branches raise or refuse instead of reading as ngspice.
- [ ] **B3 — The solver harness:** `solvers.py` discovery of `XYCE_EXE`; `tests/support/xyce.py` (run, a `Run` with exit code, log and raw file); `--require-solver xyce`; `.env.example`; `docs/testing.md`.
- [ ] **B4 — The probes as solver tests** (`tests/solver/test_xyce_*_probes.py`), skipping with a reason when Xyce is absent, with spec entries or `discrepancies.md` rows for what they show.
- [ ] **B5 — `docs/grammars/xyce/`:** README, `devices.md`, `names.md`, `numbers.md`, `scoping.md`, `discrepancies.md` and `specs/`, as §9.3 requires, with what X-M0 knows and the rest marked for its milestone.

## 5. Findings and log

### 5.1 G1 decisions

(Written at G1.)

### 5.2 Log

- 2026-11-15: task list written; decisions 1 to 3 taken by the maintainer.
