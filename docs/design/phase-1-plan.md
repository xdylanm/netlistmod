# Phase 1 development plan

> **Status:** ACTIVE — M0, M1 complete; M2 in rework after review
> **Governed by:** [architecture.md](../architecture.md). This plan sequences the work; it does not change the architecture.

## 1. Objective

Deliver a usable, tested library for the phase 1 device set and common directives (architecture §19, decision 6): **R, C, L, V, I, D, X, K**, plus `.title`, `.end`, `.param`, `.model`, `.subckt`/`.ends`, `.tran`, `.ac`, `.dc`, `.op`, `.options`, `.temp`, `.ic`, `.nodeset`, `.save`, `.meas`, with `.control`, conditional blocks, `.include`/`.lib` and unknown dot-commands handled as opaque or preserved statements.

Phase 1 ends at a **review gate**: the maintainer reviews the library hands-on and confirms before phase 2 (Q, J, M, E, F, G, H, B, S, W, T, the remaining ngspice letters A, N, O, P, U, Y, Z, all other LTspice devices, and full value specifications) begins. By the end of phase 2 all ngspice and LTspice elements are supported.

## 2. Assumptions

- **Testing is local only.** No solver in CI. Solver-backed tests (T8) run on the maintainer's machine and skip when a solver is absent (architecture §10.3).
- Both v1 dialects (ngspice, LTspice) are in phase 1 scope for the phase 1 device set. ngspice is built first as a complete vertical slice; LTspice is an overlay added afterwards (M8).
- The existing `ngspice.lark` / `ngspice.py` are exploratory. They seed M2/M3 but are not binding.
- Python 3.13+ (dev environment: `.venv`, 3.14), hatchling + uv, ruff, mypy `--strict`, pytest, pytest-cov, hypothesis (architecture §13, §19).

## 3. Local environment

M0 established and verified the local development and solver setup. The detailed
commands and findings are in [docs/testing.md](../testing.md). The current
Windows environment is:

| Need | Configuration |
|---|---|
| Python and `uv` | Python 3.14.3 and uv 0.13.4; `uv sync` manages the repository `.venv` from `uv.lock`. |
| ngspice | ngspice 47 is installed locally. Set `NGSPICE_EXE` or rely on discovery; the console sibling `ngspice_con.exe` is used for `-b -o <log> <netlist>`. |
| LTspice | LTspice 26.1.1 (file/product version 26.1.1.0) is installed locally. Headless export uses `-netlist <file.asc>` and batch simulation uses `-b <netlist>`. |
| Solver tests | Discovery order: environment variable, `PATH`, standard install locations. Missing solvers skip unless `--require-solver <name>` is supplied. |

Copy `.env.example` to `.env` and set executable paths if desired. On Windows,
quoted paths with forward slashes are supported by `uv --env-file`. Solver
switches and output behavior are recorded in
[docs/usage/ltspice-export.md](../usage/ltspice-export.md).

## 4. Milestones

Each milestone ends with its tests passing, its spec entries and docs written (architecture §14), and `ruff` and `mypy --strict` clean. Milestones are sequential unless noted.

**Milestone closing procedure (applies to M1–M9).** Each milestone has a task list in `docs/design/` (written before the milestone starts, with a `Status:` line). The milestone's final task is to hand it over for review; the archive step happens **only after the maintainer approves the review**:
1. When implementation is done, set the task list status to `READY FOR REVIEW`. Do not archive.
2. After the maintainer approves the review (any rework is a new section in the same task list), set the status to `COMPLETE (date)`.
3. `git mv` it to `docs/design/archive/` and fix its relative links.
4. Link the archived record from the milestone heading below and update the index in [README.md](./README.md).
5. Record any decisions made along the way in `docs/decisions/` (maintainer-accepted) and any new risks in the architecture or this plan.

The phase plan itself is archived at the end of the phase, after the review gate (section 6).

### M0 — Scaffolding and environment (complete; [task record](./archive/m0-tasks.md))
- `pyproject.toml`, `src/` layout, `py.typed`, ruff/mypy/pytest config, pre-commit (with the corpus exclusions from §13), `.gitattributes` (`tests/corpus/** -text`).
- `AGENTS.md`, `CONTRIBUTING.md`, `docs/provenance.md`, `docs/testing.md` (environment setup, section 3 above), docs skeleton.
- T7 architecture tests: no `subprocess`/`os.system` in `src/`, layering (import-linter), no GPL runtime dependency, every `.lark` builds under `strict=True`.
- Solver discovery (`tests/support/solvers.py`) and the `solver` pytest marker.
- **Spikes:** (a) LTspice netlist export and batch switches; (b) confirm local ngspice batch run. Results recorded in docs.
- **Exit:** empty-but-green toolchain; local solvers discovered or cleanly skipped.

### M1 — Source layer ([task record](./archive/m1-tasks.md))
- `SourceText`, `Span`, `errors.py`, `dialects.py`. Decoding (BOM, UTF-8, fallback list), byte-oriented reads and writes.
- T1 unit tests and the T3 round-trip baseline (CRLF, mixed endings, BOM, missing final newline, tabs, trailing whitespace, `µ`).
- **Exit:** load/save of arbitrary text is byte-identical; encoding policy checked against LTspice-produced samples when available.

### M2 — Grammar core (ngspice; [task list](./m2-tasks.md), in rework: syntax must live in Lark, strict per the manual)
- **Spike first: continuation lines** (ignored-terminal approach, span correctness), the highest-risk item (architecture §20).
- Line structure, comments, title (including the implicit first-line title), `.end`, opaque blocks (`.control`/`.endc`, `.if`/`.endif`), unknown dot-commands, `.include`/`.lib` as opaque statements.
- `grammar/loader.py`; LALR + contextual lexer + `strict=True`; `core.lark` plus ngspice overlay (composition mechanism chosen here and recorded).
- ParseError with line/column/excerpt.
- **Exit:** T2 grammar tests and T3 round-trip over the corpus for this subset; strict build is green.

### M3 — Elements and values (ngspice)
- R, C, L, V, I, D, X, K with typed nodes (`Resistor`, … `MutualCoupling`), value slots (`NumericValue`, `Formula`, `ModelReference`), instance parameters. Standard scale factors; RKM per decision 8.
- Transformer (dispatch by node type, §6.3 rule 11), spans on every node.
- V/I sources: plain values and the `DC` and `AC` keywords are in phase 1 (maintainer decision). Stimulus functions (PULSE/SIN/…) as typed specs are phase 2 and fail with `UnsupportedConstruct` (P5) in phase 1.
- Spec entries (`docs/grammars/ngspice/`) with manual citations and tests; spec-coverage script.
- **Exit:** every phase 1 element parses, rejects malformed input with positions (T6), and has a spec entry and tests.

### M4 — Statements and directives
- `.param`, `.model`, `.subckt`/`.ends` (with instance and definition structure), typed analysis/control directives (`.tran`, `.ac`, `.dc`, `.op`, `.options`, `.temp`, `.ic`, `.nodeset`, `.save`, `.meas`).
- **Exit:** same criteria as M3 for these constructs.

### M5 — Document and semantic layer
- `Lines`, element/param/model/subckt indexes, symbol tables, topology view and signature.
- Read-only queries (`nets()`, `elements_on_net`, `connections`, subcircuit ports); diagnostics as data.
- `docs/grammars/ngspice/names.md` (case sensitivity, ground aliases, net identity) and `scoping.md` (simple model, flagged for solver validation).
- Design doc for the semantic API.
- **Exit:** queries tested on corpus circuits. **Optional checkpoint:** read-only use is demonstrable here if you want an early look before editing exists.

### M6 — Edit layer
- **Decision records before coding:** resolve the architecture §21 unresolved questions (edit lifecycle; `set_model` vs. includes) in `docs/decisions/`.
- `Edit`/`EditPlan`/`apply_edits`, restricted edit API, directive placement, write-time verification (§7.6), `TopologyError`/`TopologyViolation`.
- T4 golden-diff tests, T5 property tests (round-trip, signature preserved, idempotence), T6 forbidden-operation tests.
- **Exit:** the operations in §7.2 work for phase 1 constructs; every forbidden operation in §7.3 has a negative test.

### M7 — Local solver validation (ngspice)
- T8 tests: solver accepts the netlist; edited results move as expected (e.g. divider ratio); unedited round-trip gives identical results.
- Validate the behaviors flagged in the spec entries and `scoping.md`; record discrepancies and mark entries `validated`/`observed`/`disputed` with solver version.
- **Exit:** solver-backed suite passes locally; spec entries updated.

### M8 — LTspice overlay
- `ltspice.lark` overlay on core; `devices.md`, `names.md`, `numbers.md` for LTspice; encoding policy validated on exported fixtures; document the export workflow.
- Fixtures: LTspice exports of circuits authored in this repository (manifest per §10.5). Local LTspice-backed T8 tests.
- **Exit:** the M3–M6 test suites run for LTspice where applicable; LTspice-only constructs have spec entries and tests.

### M9 — Phase 1 review package
- README quick start, executed usage examples, a short demo script covering load → edit → save → run solver, error reference, `CHANGELOG.md`.
- Coverage report (target 90%) and spec-coverage report.
- Review checklist for the gate (section 6).
- Archive the M9 task list per the closing procedure; the phase plan is archived once the gate passes.
- **Exit:** ready for hands-on review.

## 5. Corpus and provenance

Fixtures are authored here, exported from your own KiCad projects, or exported from LTspice from circuits authored here. Each family has a manifest (origin, license, author, date). Suggested starting set: resistive divider, RC filter, diode clamp, a subcircuit with an instance override, a coupled-inductor pair, a KiCad export (hierarchical net names), and a CRLF/BOM/no-final-newline stress file. **Needed from you:** any KiCad projects you are happy to contribute.

## 6. Phase 1 review gate

You confirm phase 2 can start when:

- [ ] All phase 1 constructs have spec entries and tests; spec-coverage and strict-grammar checks pass.
- [ ] Round-trip is byte-exact across the corpus; golden edit diffs show only intended changes.
- [ ] The topology guarantee is demonstrated by negative and property tests.
- [ ] ngspice and LTspice solver-backed tests pass on your machine.
- [ ] You have used the library on at least one of your own netlists.
- [ ] The §21 questions resolved in M6 are recorded as decision records, and any new findings are logged.
- [ ] The phase 1 limitations (opaque statements, no stimulus specs, unsupported element letters) are acceptable, or the plan for phase 2 is adjusted.
- [ ] All milestone task lists are archived, and this plan is archived with status `COMPLETE` once the gate passes.

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Continuation lines break span correctness | Spike at the start of M2, before the grammar grows around it. |
| Strict LALR conflicts as the grammar grows | Strict build in CI-equivalent local checks from M0; add constructs incrementally with tests. |
| Phase 1 rejects many real netlists (Q/M/stimulus specs) | Documented limitation; confirmed at the review gate; the phase 2 order can be adjusted. |
| LTspice export/encoding behavior differs from assumptions | M0 spike, then validated on real exports in M8. |
| Solver behavior differs from manuals | M7/M8 record discrepancies; the solver is authoritative (§11.3). |

## 8. Open points for this plan

1. **CI.** The plan assumes solver-free checks run locally in phase 1. Should a GitHub Actions workflow (lint, types, solver-free tests) be set up in M0, or deferred?
2. **LTspice timing.** LTspice (M8) is placed after ngspice is complete, so the shared design is proven on one dialect first. Say if you want it earlier.
3. **Optional checkpoint after M5** (read-only use) is proposed but not mandatory.
