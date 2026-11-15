# X-M0 task list — xyce set-up and solver spike

> **Status:** READY FOR REVIEW — the maintainer reviews the pull request
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

- [x] **A1 — References.** Record `[xyce-ref]` and `[xyce-ug]` 7.10 in `references.md`: URL, edition (SAND number, date), access date, and the licence or release terms printed in the manuals. Confirm the printed page numbers the plan cites resolve.
- [x] **A2 — The dialect audit.** List every place in `src/` that tests a dialect (`Dialect.LTSPICE`, `Dialect.NGSPICE`, and dicts keyed by dialect). For each: what a third dialect would get today (often the ngspice branch, by `else`), and whether that is right, wrong or unknown for xyce. Propose how the hidden dialect is reached (decision 1), with the effect on `Dialect`, `load`, type annotations and `__all__`, and the architecture tests that guard it.
- [x] **A3 — The solver.** Check that `XYCE_EXE` (`xyce.exe`, XyceNF 7.10) runs under Smart App Control in batch mode; the version line for `validated_on`; `-syntax`, `-norun`, `-r` with `-a`, and `-namesfile`; exit codes and where errors are written. Whether `tests/support/raw.py` reads Xyce's ASCII raw file.
- [x] **A4 — Probes** (section 6), each a minimal netlist authored here, run with `-syntax` or `-norun` and, where it matters, a real run:
  1. an unknown dot-command;
  2. a line that begins with whitespace (an element line, and a `.param`);
  3. a `+` continuation after a comment line;
  4. a node written in brackets (`[node]`), as the manual's syntax uses brackets for optional fields;
  5. `//` and `;` after a statement;
  6. the first line as the title, and a file without `.END`.

### Stage 2

- [x] **B1 — Decision X-D0** (`docs/decisions/0026-…`): items 1, 2 and 4 of section 2; the hiding mechanism and the reading of X-M0's xyce as decided at G1; the closed dot-command list as a goal for X-M2. Architecture §9.2 and §12 updated.
- [x] **B2 — The hidden dialect:** the internal name, the loader registry, `xyce.lark` on `core.lark` and `xyce-devices.json`, as decided at G1. Tests: a load with the hidden dialect; `Dialect` has no public xyce member; the audit's wrong branches raise or refuse instead of reading as ngspice.
- [x] **B3 — The solver harness:** `solvers.py` discovery of `XYCE_EXE`; `tests/support/xyce.py` (run, a `Run` with exit code, log and raw file); `--require-solver xyce`; `.env.example`; `docs/testing.md`.
- [x] **B4 — The probes as solver tests** (`tests/solver/test_xyce_*_probes.py`), skipping with a reason when Xyce is absent, with spec entries or `discrepancies.md` rows for what they show.
- [x] **B5 — `docs/grammars/xyce/`:** README, `devices.md`, `names.md`, `numbers.md`, `scoping.md`, `discrepancies.md` and `specs/`, as §9.3 requires, with what X-M0 knows and the rest marked for its milestone.

## 5. Findings and log

### 5.1 G1 decisions

From the stage 1 reports (A2, the dialect audit; A1, A3 and A4, the references, the solver and the probes).

1. **How the dialect is hidden (A2).** No `Enum` member can be both real and hidden: a single-underscore name is a member and is iterated, and an enum with members cannot be subclassed. The options:
   - **A, a pseudo-member:** `_XYCE: Final[Dialect]`, an instance of `Dialect` built in `dialects.py` and not registered. It is absent from `list(Dialect)`, `__members__`, `Dialect("xyce")` and `from_name`, and passes `isinstance`. No annotation or public signature changes, and X-M8 makes it public in one line. It relies on undocumented `Enum` internals, so an architecture test checks it on every CI Python. It cannot be pickled.
   - **B, a second internal enum** with a wider internal type: 52 annotations widen, and `Netlist.dialect`'s covered return type would change.
   - **C, a private string key:** reaches only the parser, not the document and edit layers. Rejected.

   *Recommendation:* A, with guard tests that the value is not public (not in `Dialect`, not bound in any `__all__`) and that it loads.
   **Decided (maintainer, 2026-11-15): A, the pseudo-member.**
2. **What X-M0's xyce reads.** A2 found 60 sites that branch on a dialect: 17 right for xyce, 20 wrong, 20 unknown and 3 that depend on the mechanism. Seven of the wrong ones crash any xyce load (the grammar, device-table, terminal-name and formula registries, the reserved words, the diagnostics' solver names), and `rkm=True` is refused on LTspice only.

   *Recommendation:* X-M0's xyce reads only a title, comment lines, blank lines and `.END`. Every element and dot-command line raises `UnsupportedConstruct` ("not yet supported on xyce"). B2 fixes the seven crashing sites and the cheap wrong ones (`display_name`, ground as `0` only, the `rkm` refusal, the solver name and citation). The rest sit in rules xyce cannot reach until its overlay defines them; each goes to the xyce plan as a checklist line for its milestone. Binary `is LTSPICE … else` tests that xyce can reach become per-dialect tables, so a missing entry fails loudly (P5).
   **Decided (maintainer, 2026-11-15): as recommended.**
3. **The wheel between milestones.** Hatch packages all of `src/netlistmod`, so a release before X-M8 ships `xyce.lark` and its tables as package data. It is reachable only through private names.

   *Recommendation:* accept it. Leaving the files out would make the hidden dialect fail in an installed copy, and it changes nothing public.
   **Decided (maintainer, 2026-11-15): accepted.**
4. **Probe findings (for the record; decided in later milestones).**
   - **Confirmed:** an indented line is a silent comment, even an indented `.param` or `.END` (X-D1). A `+` line joins the last non-comment line across comments and blank lines, never the title. Line 1 is always the title, even when blank. `0` is the only ground without `.PREPROCESS REPLACEGROUND`.
   - **The binary is more lenient than the manual:**
     - `.END` is not required (ug p40 says the last line must be `.END`);
     - text after `.END` is ignored;
     - an unknown dot-command is a warning and is ignored (an unknown block's body is read as lines);
     - a bracketed node such as `[s]` is a literal node name, against ref §2.3.17 p241 (X-M4).
   - **The manual's examples fail on the binary:** `//` is not a comment (ref p173). Only `;` ends a line; `$` and `//` are errors.
   - These become `discrepancies.md` rows. The grammar follows the manual (P5, §11.3), so the strictness of `.END` and the closed dot-command list are decided in X-M1 and X-M2.
5. **The solver (A3).** `Xyce.exe` runs under Smart App Control. `-v` prints `XyceNF Release 7.10.0`, the `validated_on` value. Exit codes: 0, or 1 on any error; warnings don't change them. Diagnostics go to stdout as `Netlist error in file … at or near line N`. A run writes `<netlist>.prn` beside the netlist. `-namesfile` lists the circuit's nodes in lower case without a run, a node-list check. `tests/support/raw.py` reads Xyce's ASCII raw file only after three changes: blank lines between points, complex values written `re, im`, and `Title:` given once for several plots. B3 makes them.
6. **References (A1).** Both manuals carry the NTESS copyright (2002–2025) and the US Government report notice, with no licence for the text. They are paraphrased and cited by page, as the ngspice manual is. Plan citations to correct:
   - Table 6-1 runs over p847–848, and `.control`, `.if` and `.title` are not in it;
   - §8 is p857–858;
   - GND belongs to §2.1.28 p125;
   - Table 2-35 is p177–178.
7. **Tests that a third dialect touches.**
   - `test_contracts.py:262` compares the registry with `frozenset(Dialect)`.
   - `UNCHECKED_TERMINALS` needs an xyce entry.
   - `test_spec_coverage.py` hard-codes each dialect; an empty `specs/` raises, and its citation pattern takes no page numbers.
   - `test_packaged_grammar.py` lists the grammar files.

   B2, B4 and B5 cover them. Tests that iterate `Dialect` skip xyce while it is hidden, and pick it up at X-M8.

### 5.2 Log

- 2026-11-15: task list written; decisions 1 to 3 taken by the maintainer.
- 2026-11-15: stage 1 reports in (A1 to A4); G1 points 1 to 3 decided as recommended.
- 2026-11-15: stage 2 done (B1 to B5). Lead's additions: indented non-comment lines are refused until X-D1 (decision 0026 item 6); XY-STR, XY-TTL and XY-COM validated by the B4 probes; the plan's section 8.1 lists the branches for later milestones.
- 2026-11-15: R1 (independent review): no blockers; 4 should-fix and 6 nits, all fixed. Manual-valid `;` lines and `+` lines after comments are refused as unsupported (decision 0026 item 6); the raw reader's Xyce relaxations are behind `xyce=True`; the hidden-name guard scans every module and `Dialect` itself.
- 2026-11-15: full run with ngspice, LTspice and Xyce: 10797 passed, 2 skipped; coverage 99.21%. READY FOR REVIEW.
