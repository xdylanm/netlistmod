# M9 task list — Phase 1 review package

> **Status:** COMPLETE (2026-11-03) — approved by the maintainer. T1–T11 are done; H1–H4 and the review's fixes are in `88a8754`, and T10 ran from a clean clone of that commit ([results](./phase-1-review.md#2-results)).
> **Part of:** [phase-1-plan.md](./phase-1-plan.md) (milestone M9, review gate in section 6). Governed by [architecture.md](../../../architecture.md) (§2, §7, §10, §11, §12 are normative; §13, §14, §15, §19, §21).

## 1. Scope

M9 reviews phase 1 as a whole and assembles what the maintainer needs for the hands-on review:

- **Overall review:** check the finished library against the plan's exit criteria, the architecture and the gate.
- **Package (plan M9):** README quick start, executed usage examples, a load → edit → save → run solver demo, an error reference, `CHANGELOG.md`, a coverage report (target 90%), a spec-coverage report, the broader Hypothesis oracle carried from M2, and the gate checklist.
- **Exit:** ready for hands-on review.

**Source changes are not made in M9.** Any change needed under `src/` is written up in a separate handoff document, [phase-2-code-changes.md](../../phase-2-code-changes.md) (created by R7), for a developer. The maintainer decides which entries must land before M9 is accepted. Documents, tests and the demo are M9's own work (decision 3).

Not in M9: phase 2 letters and stimulus functions, a release or version tag, and the maintainer's own use of the library (a gate item that follows this package).

## 2. Decisions (maintainer, 2026-11-02)

The maintainer accepted each recommendation below, except decision 4, which is replaced as written there. "Alternative" marks an option considered and not chosen. Decision record 0010 (T2) records the outcome.

1. **The four active design notes** (`m3-elements`, `m4-statements`, `m5-document`, `m6-edits`).
   Findings (2026-11-02):
   - None changed after M6 and none mentions LTspice, although M8 changed the shapes. The notes omit `StepDirective`, `ValueList`, `GlobalDirective`, `Flag.value`, `Diode.area`, `ModelStatement.ako`, `TranDirective.modifiers`, `AcDirective.frequencies`, `TempDirective.others` and `NODE_INTO_INSTANCE`.
   - They are not history: architecture §5.2, §5.3, §7.2, §7.7 and §16, decisions 0004–0007 and the usage guides cite them as the current specification. They hold content found nowhere else, such as the signature encoding, the sub-span definitions and the operation tables.
   - Phase 2 must extend them, and `design/README.md` forbids editing an archived file.

   *Recommendation:* keep them as living references under topic names, and do not archive them. `git mv` to `docs/design/elements.md`, `statements.md`, `document-layer.md` and `edit-layer.md` (§14 already describes `design/` as topic notes). Bring each up to date with M8 and LTspice, fix the links (archived files may have links fixed), add a small architecture test that every public node, field and export is named in a note so they cannot drift silently again, and add a "living reference" rule to `design/README.md`. Their milestone-time state stays in Git history, and the task lists remain the records.

   *Alternatives:* (a) archive as they are. Not recommended: the architecture would cite a stale, uneditable specification. (b) Archive them and write one new API reference. Not recommended: more writing for the same result, and it loses `git mv` history. (c) Keep the names and only update the content. Workable, with the least churn, but leaves "M3 design note" as the title of a document phase 2 keeps extending.
2. **CI** (plan open point 1; M7 deferred it to here; §13, §14 and §10.4 assume it). There is no `.github/`, although the repository has a GitHub remote.
   *Recommendation:* not in M9, which the plan does not ask to add it. Record the deferral to the start of phase 2 in decision 0010, and close the open point. *Alternative:* add a solver-free workflow (lint, types, tests) now.
3. **Boundary of "code".**
   *Recommendation:* the handoff covers `src/` only. M9 writes tests, docs, the demo and report scripts itself. If the wider oracle finds a library bug, the handoff gets an entry with the reproducer, and the test stays in the suite as a strict `xfail` naming that entry, to be removed by the fix. No invariant or test is weakened (§15).
4. **No stress or performance testing in phase 1.** M2's review carried a 20,000-line performance test to M9, but the plan's M9 list omits it and the CHANGELOG records its removal. The maintainer dropped it from the requirements: phase 1 has no need to stress-test or performance-profile anything. There is no size test either. Decision 0010 records this, which closes the M2 carry-over.
5. **Oracle scope.** The plan's list is written for ngspice, and the existing oracle is under `tests/grammar/ngspice/`. No LTspice oracle exists.
   *Recommendation:* extend the ngspice oracle as listed, and add an LTspice variant using the forms LTspice has (`+`, `;`, its `$` rule; no `\\`, `//` or blocks). The oracle's module note also names edits as M9 work: add a generator of allowed edits, comparing against an independently computed expected text.
6. **Demo solvers.**
   *Recommendation:* one script, `docs/usage/examples/edit_and_simulate.py`, with a `--dialect` argument for both solvers. It launches the solver itself, outside `src/` (P9), and prints its results at run time only. A test runs it under the `solver` marker. No LTspice output is committed (decision 0009).

## 3. Starting point (read-only baseline, 2026-11-02, `2127bb3`)

- Full suite with both solvers: 3853 passed, 2 skipped (POSIX only), 426 deselected; coverage 98.84%. `ruff check`, `ruff format --check`, `mypy` and the import-linter contract are clean.
- Relative links in the root and `docs/` Markdown files: none broken.
- Spec entries: ngspice 36 `validated`, 3 `observed`; LTspice 40 `validated`.

Gaps already seen, to be confirmed and fixed in the tasks below:

| Item | Gap |
|---|---|
| README | No quick start |
| Demo | Only the read-only M5 demo; no load → edit → save → run solver |
| Error reference | Does not exist (§14 expects one in `docs/usage/`) |
| `docs/usage/README.md` | Omits the LTspice export guide; "added as the API is implemented" wording |
| `structural-parse.md` | Has no executed examples and is not in `tests/test_usage_docs.py` |
| Usage guides | `elements.md`, `statements.md`, `document.md` and `editing.md` never mention LTspice |
| Decision records | 0002 and 0003 still say `proposed` |
| `docs/testing.md` | T9 is "documentation examples and spec coverage"; architecture §10.2 says T9 is differential testing |
| Architecture | Still `DRAFT v0.1`; the §4 layout omits `edit/operations.py`, `document/models.py` and the JSON data files, and shows `.github/workflows/` |
| Plan | M1's heading does not say complete; section 8's open points are stale |

## 4. Tasks

Every task that changes a file ends with the full check set green, run as `uv run --env-file .env python -m <tool>`: `ruff check`, `ruff format --check`, `mypy`, `mypy --strict` on the test-support command from M8, `lint-imports` and `pytest`. Findings outside this list go to the handoff (`src/`) or to section 5 (accepted limits for the gate). Nothing is silently resolved (§15, §21).

### Review (read-only, apart from recording findings)

[x] **R1 — Re-establish the baseline,** adding the `pre-commit run --all-files` result and the named `mypy --strict` test command.

[x] **R2 — Exit criteria.** For each of M0–M8, trace the plan's exit criterion to the tests or documents that show it, and note any gap.

[x] **R3 — Scope and traceability.**
- Plan section 1's construct list against spec entries, grammar markers and tests, for both dialects.
- Goals G1–G8.
- Each allowed operation in §7.2 to a golden test; each forbidden operation in §7.3 to a negative test.
- Each `.lark` rule, device matrix row and diagnostic code to its tests.

[x] **R4 — Code review of `src/` against the principles.**
- P1–P4: spans, round trip, the verification steps of §7.6, and whether any public path bypasses them.
- P5 and P13: silent acceptance; syntax decided outside the grammar.
- P7, P9, P11; layering.
- Public API: consistency across the two dialects, docstrings (§14), and what `__all__` exports.
- Error and diagnostic messages, read as a user would.

[x] **R5 — Carried items.** Decide each one for the handoff, section 5 or no action:

| Source | Item | Checked 2026-11-02 |
|---|---|---|
| M4 §10.3 | A missing argument (`.tran 1ns`, `.model dm`) lists only separators as expected tokens; "revisit with the M9 error reference" | Still so |
| M6 review | `directives.add(".model …")` suggests `params.set`; adding a `.model` has no API | Still so |
| M6 review | `Placement.after(line)` with a body line says "look the line up again" | Not yet |
| M6 review | Two `params.set` of one new name in a batch add two lines | Runs with no error; lines not yet inspected |
| M8 §9.4, §16 | `.backanno` on every LTspice export gives `UNKNOWN_DIRECTIVE_PRESERVED`; `.tf`, `.noise` and `.four` are called "unknown" though listed | `.backanno` still so |
| M8 §16 | `NODE_INTO_INSTANCE` occurs only in tests, not in an LTspice corpus file | Fixture to add in T8 |
| M8 §13.3 | With `.param time=3k`, behavioural expressions will need their own rule | Phase 2 note |
| M8 §4 | Optional `.end` for LTspice; "revisit after the phase 1 review" | Gate item |
| Decision 0003 | Terminals with lookarounds: rewriting them is an open design question | Gate item |
| Plan §7 | About 300 nested `.if` levels raise `RecursionError` | Gate item |

[x] **R6 — Documentation and provenance audit.**
- Architecture, plan, `AGENTS.md`, `CONTRIBUTING.md` and `testing.md` against the code, including section 3's gaps.
- §21 and each decision record's status. The maintainer accepts or corrects 0002 and 0003, which M2 left `proposed`.
- Every corpus family has a manifest and a row in `provenance.md`.
- Runtime dependency licenses.
- No LTspice raw file, log or timing number is in the repository.
- Build the wheel and sdist, and import from a clean install.

[x] **R7 — Write the handoff.** Create `docs/design/m9-code-changes.md`, even if it says no change is required. For each entry: ID, severity (`required for the gate`, `recommended`, `phase 2`), location, reproducer, expected behaviour, tests to add, and any decision or architecture change it needs.

**Checkpoint A:** report the findings and the handoff to the maintainer, who triages the entries. Any entries marked required are made by a developer and are reviewed like other milestone rework.

### Documents

[x] **T1 — Design notes, per decision 1,** and the related `design/README.md` change. `tests/architecture/test_design_notes.py` checks each public name, dataclass field and diagnostic code; it found 10 gaps beyond those section 2 lists.

[x] **T2 — Decision record 0010: phase 1 close-out.** The outcomes of decisions 1, 2 and 4, plus the architecture corrections R6 confirms (§4 layout, T9, §13 on CI, the status line). Status `proposed` until the maintainer accepts it.

[x] **T3 — README quick start.** Install, then load → edit → save for one netlist, with the dialect explicit; supported constructs and limits; replace the status paragraph with a short phase 1 summary and links. Executed by `tests/test_usage_docs.py`.

[x] **T4 — Usage guides.**
- `docs/usage/README.md` as an index of what exists, including the LTspice guide.
- Executed examples in `structural-parse.md`.
- Each guide says which dialect it covers. Add executed LTspice examples to `elements.md`, `statements.md`, `document.md` and `editing.md`, at least where LTspice differs.
- Fix `testing.md` T9 once decision 0010 settles it.
- State the reference limits in `document.md`: `references_to_param` does not see `.meas` bodies, unknown dot-commands (`.func`) or opaque items, and a name defined only in an `.if` block is reported as unresolved (H8).
- Add a test that relative Markdown links resolve (§13 lists a link check, and CI is deferred).

[x] **T5 — Demo script,** per decision 6, linked from the README and usage index.

[x] **T6 — Error reference, `docs/usage/errors.md`.** Each exception of §17 and each `DiagnosticCode`: when it occurs, severity, an executed example, and what to do. A test fails if a code or exception has no entry. Poor messages found here go to the handoff.

[x] **T7 — CHANGELOG.** A phase 1 summary at the top of `Unreleased` (dialects, constructs, guarantees, known limits). Keep the entries already there. No version change.

### Tests

[x] **T8 — Broader oracle,** per decisions 3 and 5. Independent generators (expected values do not come from the parser) for: CRLF and mixed endings; `+` and `\\` continuations; trailing `;`, `$` and `//` comments; indentation; whitespace-only lines; block variants; generated edits; the LTspice variant. Also an LTspice fixture for `NODE_INTO_INSTANCE`, and LTspice golden cases for the operations that have only ngspice goldens (`set_formula`, `set_model_param`, `set_dc`, `set_ac`, `set_coupling`, `directives.add`, `replace`, `remove`, `add_include`). Bugs follow decision 3. Result: `tests/grammar/test_broad_oracle.py` found no library bug. The list's `set_formula`, `set_model_param` and other operations now have LTspice goldens whose expected bytes were written independently of the library.

### Package and exit

[x] **T9 — Review package, `docs/design/phase-1-review.md`** (archived with the plan once the gate passes). T10 recorded its final results.
- Coverage report: totals and per module, with an explanation of each uncovered line or a note that it is accepted.
- Spec-coverage report: per dialect, construct → spec entry → status → tests, generated by a small script under `tests/support/` so it can be repeated.
- The gate checklist: plan section 6, each item with its evidence, and which ones only the maintainer can complete.
- Section 5's limits for the maintainer's decision.
- A suggested hands-on script, including running on the maintainer's own netlist.

[x] **T10 — Final evidence and handover.** After any required handoff entries have landed: full check set with `--require-solver ngspice --require-solver ltspice` from a fresh clone of a commit, and record the results in T9's package. Update the plan's M9 heading, status line and section 8, and `design/README.md`. Set this list to `READY FOR REVIEW`. **Do not archive.**

### After the maintainer's approval (closing procedure, plan section 4)

[x] **T11 — Close M9.** Status `COMPLETE (date)`, `git mv` to `archive/`, fix links, update the plan and index, and accept decision 0010.

**The gate itself** (the maintainer's use on their own netlists, section 5's decisions, then archiving the plan) follows M9 and is not a task of this list.

## 5. Limits for the maintainer to weigh at the gate

Started from earlier reviews; R5 and R6 extend this. M9 records them and does not resolve them. The maintainer accepted all of them on 2026-11-03 and set phase 2's order ([decision](./phase-1-review.md#6-limits-for-your-decision)).

- Phase 1 limits named by the gate: opaque statements, no stimulus specs, unsupported element letters. Real netlists with Q or M devices or `PULSE`/`SIN` sources are rejected until phase 2.
- `.end` is required for LTspice too, although LTspice lets it be omitted (decision 0009; "revisit after the phase 1 review").
- Terminals with lookarounds are not collision-checked by strict mode: a test pins the list, and rewriting them is an open design question (decision 0003).
- About 300 nested `.if` levels raise `RecursionError` (plan section 7).
- An added `.if` block may contain element lines; opaque contents are not verified (§7.8).
- **Python 3.13 is untested.** The package declares `>=3.13`, but every run was on 3.14.3 (maintainer, 2026-11-02).
- A `.lib name` … `.endl` block is not recognised (decision 0002). Its first line is an opaque statement, its body is read as top-level lines, and `.endl` is an unknown directive, so the body's elements count as topology.
- `directives.add` is not an upsert: over an existing `.tran`, or followed by `directives.set` in a batch, it writes two `.tran` lines. ngspice runs both analyses and LTspice stops.
- Whether phase 2's order should change, based on hands-on use.

## 6. Out of scope for M9

- Any change under `src/` (the handoff).
- Phase 2 constructs, and resolving section 5's limits.
- Tagging or publishing a release.
- Differential testing against spicelib (T9 in §10.2, optional).
- Linux and macOS LTspice; qspice and xyce.

## 7. Review findings (checkpoint A, 2026-11-02, `2127bb3`)

### 7.1 Baseline (R1)

With both solvers found: 3853 passed, 2 skipped (POSIX only), 426 deselected, coverage 98.84% (24 lines and 17 branches uncovered). `ruff check`, `ruff format --check`, `mypy`, the named `mypy --strict` test command, import-linter and `pre-commit run --all-files` are clean. This run did not pass `--require-solver`, so T10 repeats it with both required.

### 7.2 Exit criteria and traceability (R2, R3)

| Milestone | Exit criterion | Evidence | Result |
|---|---|---|---|
| M0 | Green toolchain; solvers found or skipped | R1; `tests/test_solver_discovery.py`; `tests/architecture/test_contracts.py` | Met |
| M1 | Byte-identical load and save; encoding checked on LTspice samples | `tests/test_source.py`, `tests/roundtrip/`, `encoding_samples` | Met |
| M2 | T2 and T3 for the structural subset; strict build | `tests/grammar/ngspice/test_structure.py`, `structure_*` corpora | Met |
| M3, M4 | Each construct parses, rejects with positions, and has an entry and tests | 39 `NG-*` entries, `*_rejects` manifests, spec checker | Met |
| M5 | Queries tested on corpus circuits | `tests/document/`, `document_basic` manifest | Met |
| M6 | §7.2 operations work; each §7.3 operation has a negative test | At least one golden case per operation; `test_edit_negative.py` crafts each §7.3 case | Met, except H1 |
| M7 | Solver suite passes; entries updated | 36 `validated`, 3 `observed` | Met |
| M8 | M3–M6 suites run for LTspice; LTspice-only constructs covered | 40 `LT-*` entries, all `validated`; `tests/edits` and `tests/document` run on both | Met |

- **Plan section 1's constructs** each have an entry in both dialects where the dialect has the construct. `.control` and `.if` are ngspice-only, and LTspice rejects them by decision.
- **LTspice goldens are thinner than ngspice's.** The parametrised edit tests cover the other operations on both dialects, so this is not a gap in the guarantee; T8 adds cases.
- **Corpus:** all 21 families have a manifest and a `provenance.md` row. No LTspice raw file or log is in the corpus.

### 7.3 Code review (R4)

Read in full: `edit/`, `document/` apart from `diagnostics.py`, `source.py`, `errors.py` and `dialects.py`. Read in part and searched for string scanning: `document/diagnostics.py`, `grammar/loader.py` and `model/transform.py`; for the rest of these, this review relies on the earlier milestone reviews, the grammar tests and the oracle. The `.lark` files were not read line by line. Probes ran on the public API (handoff section 4).

**One defect is proposed as required (H1)**, plus message and documentation entries (H2–H8). No violation of P1–P4, P7, P9 or P11 was found.

### 7.4 Carried items (R5) and audit (R6)

| Item | Outcome |
|---|---|
| Missing-argument messages (M4) | H2 |
| `.model` hint, `Placement.after` message (M6) | H3 |
| Two `params.set` in a batch (M6) | H1, which found it is wider |
| `.backanno` and "unknown" listed commands (M8) | H6, phase 2 |
| `NODE_INTO_INSTANCE` fixture (M8) | T8 |
| `time` in behavioural expressions (M8) | Phase 2 note; nothing to do now |
| `.end`, lookarounds, deep `.if` | Section 5, for the gate |
| `_include_path` splitting a quoted path with a space (M7) | Test helper; fails loudly; no action |

Documentation findings beyond section 3, for T2 and T4:

- The §4 layout also lists `tests/unit`, `property` and `negative`, which do not exist; those tests live elsewhere.
- Paths named in the live docs all exist.
- **Python 3.13 has never been run here.** `requires-python` is `>=3.13` and ruff and mypy target 3.13, but only 3.14.3 is installed. The maintainer chose to record it as untested (section 5).
- Runtime dependencies are Lark and interegular, both MIT per `docs/testing.md`.

### 7.5 For the maintainer at checkpoint A

1. ~~Triage [phase-2-code-changes.md](../../phase-2-code-changes.md).~~ Decided 2026-11-02: H1–H4 land before M9 is accepted.
2. ~~Accept or correct decisions 0002 and 0003.~~ Decided 2026-11-02: reviewed against the code and accepted, with wording amendments. No behaviour differed from them; what was stale was text (section 7.6).
3. ~~Whether the token slicing in the handoff's section 3 is acceptable under P13.~~ Decided 2026-11-02: it stays, and decision 0010 item 6 clarifies P13.
4. ~~Whether to install Python 3.13 for one run.~~ Decided 2026-11-02: no. It is recorded as untested (section 5).

T1–T9 can start without the triage, apart from H1's wording in decision 0010 and any message H2 changes in the error reference. T10 waits for the required entries.

### 7.6 Decisions 0002 and 0003 against the code (2026-11-02)

Each rule of decision 0002 was probed on the parser, and the terminals and priorities of decision 0003 were read in the grammar. The behaviour matches, apart from the wording corrected by amendment:

| Decision | Statement | Finding |
|---|---|---|
| 0002 | Titles do not split on `;` or `$` | True, and also not on `//` |
| 0002 | "The accepted conditional form is `.if (1)`" | The header is not checked, so `.if 1` and `.if` parse |
| 0002 | `*` comment lines | May be indented (`NG-COM-001`) |
| 0003 | 20,000-line performance bound | Withdrawn by decision 0004; the test is gone |
| 0003 | Priority list and file locations | `SEP.10` is new; decision 0009 moved `BS_CONT` and `TEXT` |
| 0003 | `%extend statement` for opaque blocks | `.control` now uses `%extend top_statement` |

### 7.7 Hands-on use (maintainer, 2026-11-03)

The maintainer ran `read_only_demo.py` and `edit_and_simulate.py` on `dc_basic_r_divider.cir` and `shiftscaleinvert.cir`, with further tweaks, and confirmed that the basic operations behave as expected. `edit_and_simulate.py` gained a netlist path, `--edit-value`, `--probe` and `--rkm` for this; `src/` did not change.

Findings, both decided by the maintainer on 2026-11-03 with no change:

- **`limit` differs between solvers.** `limit(0.5, 1m, 0.999)` returned 1.499 or -0.499 at random in ngspice 47, and 0.5 in LTspice. A subcircuit in the maintainer's model library used it as a clamp, so `.op` results changed from run to run on byte-identical files. The maintainer fixed that file. No diagnostic is required for `limit`.
- **RKM values can give wrong voltages with only an `info` diagnostic.** With `rkm=True`, the library reads `2k7` as 2.7k, while ngspice 47 without `ngbehavior=lt` read it as 2k: a test divider gave 1.0000 V rather than 0.8108 V. `DIALECT_GATED_SYNTAX` is `info`, and `RKM_SOLVER_MISMATCH` (a warning) did not fire for `2k7`, though it did for `1M0`. The warning stays as it is: validating solver inputs is out of scope for this library.
