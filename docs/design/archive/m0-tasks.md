# M0 task list — scaffolding and environment

> **Status:** COMPLETE (2026-10-20)
> **Progress:** T1–T16 complete.
> **Part of:** [phase-1-plan.md](./phase-1-plan.md) (milestone M0). Governed by [architecture.md](../../architecture.md).

## 1. Current state

| Item | State |
|---|---|
| `.venv` | Python 3.14.3, with `pip` and `uv` 0.13.4 only. All packages go here. |
| `.env` | Created and git-ignored: `NGSPICE_EXE` → `…\ngspice-47_64\Spice64\bin\ngspice.exe`, `LTSPICE_EXE` → `…\ADI\LTspice\LTspice.exe`. Both executables exist. `ngspice_con.exe` is in the same folder. |
| `requirements.txt` | Contains `lark`; deleted in T2 when `pyproject.toml` exists. |
| `src/netlistmod/grammar/ngspice.{lark,py}` | Exploratory prototype; no `__init__.py`. Moved to `prototype/` in T3. |
| `tests/fixtures/` | Three KiCad-style ngspice circuits (divider ×2, RC low-pass). Moved in T11. |

## 2. Decisions (confirmed by the maintainer)

1. **Prototype files** move to `prototype/` (outside `src/`) so they are not packaged, type-checked, or covered by the "every `.lark` builds strict" test. They remain a starting point for M2.
2. **Fixtures** move to the architecture layout `tests/corpus/<dialect>/<family>/` with a manifest (T11): `tests/corpus/ngspice/kicad_basic/`.
3. **Phase 1 scope change:** V (and I) sources with the `DC` and `AC` keywords are in phase 1 scope (applied to [phase-1-plan.md](./phase-1-plan.md), M3). Stimulus functions (`SIN`, `PULSE`, …) remain phase 2. The `SIN(...)` stimulus has been removed from `ac_basic_rc_lpf.cir`, so all three fixtures are within phase 1 scope.
4. **Environment loading:** use `uv` only: tests are run with `uv run --env-file .env pytest`. No `python-dotenv` dependency. Solver discovery still falls back to `PATH` and default install locations when the variables are not set.

## 3. Tasks

Tasks are ordered by dependency. Every task ends with `ruff`, `mypy --strict` and `pytest` green (where applicable).

### Project definition

- [x] **T1 — Verify tool availability.**
Confirm `uv` can manage the existing `.venv` (`uv sync` / `uv pip` target `.venv`), and check `lark` license (MIT) and the version that supports `strict=True`.
*Done when:* findings recorded in `docs/testing.md` (T14) and the minimum Lark version is chosen.

- [x] **T2 — Create `pyproject.toml`; delete `requirements.txt`.**
- PEP 621 metadata, hatchling backend, `src/` layout, `requires-python = ">=3.13"`, MIT license, `.lark` files included as package data.
- Runtime dependency: `lark` (version floor from T1).
- Dev dependency group: `pytest`, `pytest-cov`, `hypothesis`, `ruff`, `mypy`, `pre-commit`, `import-linter`.
- Tool config: ruff (lint + format), `mypy --strict`, pytest (`testpaths`, `solver` marker, strict markers), coverage (90% target, informational for now).
- Delete `requirements.txt`.
- *Done when:* `uv sync` into `.venv` succeeds, `uv.lock` is created, and `python -c "import netlistmod"` works.

- [x] **T3 — Package skeleton.**
Create `src/netlistmod/__init__.py` and `py.typed`; add empty layer modules matching architecture §4 only as needed to host M0 tests (`errors.py`, `source.py`, `dialects.py` stubs are filled in M1). Move `src/netlistmod/grammar/ngspice.lark` and `ngspice.py` to `prototype/` with `git mv` (decision 1); remove the then-empty `grammar/` directory from `src/` unless later tasks need it. Exclude `prototype/` from ruff, mypy and pytest collection.
*Done when:* the package imports, `mypy --strict` passes, and nothing from the prototype is in `src/`.

### Repository hygiene

- [x] **T4 — `.gitattributes` and `.editorconfig`.**
`tests/corpus/** -text` (plus golden-output paths); default `* text=auto` for source. `.editorconfig` for source files only.
*Done when:* `git check-attr text` reports `unset` for corpus files.

- [x] **T5 — Pre-commit.**
Hooks: ruff, ruff-format, mypy, YAML/TOML checks, merge-conflict check. Whitespace/EOL hooks (`trailing-whitespace`, `end-of-file-fixer`, `mixed-line-ending`) exclude `tests/corpus/` and golden files (architecture §13).
*Done when:* `pre-commit run --all-files` is green and leaves the corpus files byte-identical (verified by `git diff --exit-code`).

- [x] **T6 — `AGENTS.md` (project constitution and patterns).**
A short file (about one page) at the repository root. It MUST point to [docs/architecture.md](../../architecture.md) as the authority and MUST NOT duplicate it. Content:
- *Constitution* (one line each, referencing the architecture sections): source text is the single source of truth (P1); typed view with edits as span replacements (P2); exact round-trip and minimal diff (P3); topology is read-only (P4); strict grammar, fail loudly (P5); grammar constructs have spec entries and tests (P6); dialects are separate grammars over a shared core and the caller selects the dialect (P7); no simulator launching in `src/` (P9); clean-room provenance, no GPL-derived code or tests, including spicelib (P10, §12).
- *Working rules:* the agent working agreement in architecture §15; do not resolve items in architecture §21 silently; do not weaken an invariant to pass a test; architecture changes go through a decision record in `docs/decisions/`; detailed requirements live in `docs/design/`.
- *Patterns:* layering (architecture §3) and package layout (§4); tests first for each construct (tiers T1–T9, §10); golden-diff tests for edits; corpus fixtures with manifests and byte-exact preservation (`-text`); prototype code in `prototype/` is exploratory and not to be imported.
- *Commands:* run everything through `uv run --env-file .env …` (tests, `ruff check`, `ruff format`, `mypy`, `pre-commit`); solver tests are local-only and skip when a solver is absent.
*Done when:* `AGENTS.md` exists, fits in about one page, links to the architecture, and states the GPL rule and the `uv run` convention.

- [x] **T6b — Other contributor documents.**
`CONTRIBUTING.md` (clean-room rules, how to declare fixture origin, how to run checks), `docs/provenance.md` (policy), `CHANGELOG.md` (empty "Unreleased"), `README.md` (purpose, status, link to docs).
*Done when:* the files exist; `CONTRIBUTING.md` states the GPL rule.

- [x] **T7 — Docs skeleton.**
Create `docs/decisions/` (with a short template), `docs/usage/`, `docs/grammars/ngspice/`, `docs/grammars/ltspice/` placeholders. Only what is needed; no empty boilerplate beyond directory README stubs.
*Done when:* the layout matches architecture §14 and links resolve.

### Solver environment

- [x] **T8 — Environment template.**
Add `.env.example` (tracked, placeholder paths for `NGSPICE_EXE` and `LTSPICE_EXE`). No loader code: `uv run --env-file .env …` supplies the variables (decision 4). Document this convention in `docs/testing.md` (T14).
*Done when:* a fresh clone can copy `.env.example` to `.env`, edit it, and `uv run --env-file .env pytest` sees the paths in the test environment.

- [x] **T9 — Solver discovery: `tests/support/solvers.py`.**
Discovery order: environment variable → `PATH` → default install locations (e.g. `…\Programs\ngspice\…`, `…\Programs\ADI\LTspice`). Return the path and version string, or `None`. Handle both `ngspice.exe` and `ngspice_con.exe`. Tests-only: no `subprocess` in `src/`.
*Done when:* unit tests for discovery logic (using fake paths/monkeypatched env) pass without the solvers installed.

- [x] **T10 — `solver` marker and `--require-solver`.**
`conftest.py` registers `@pytest.mark.solver("ngspice"|"ltspice")`, skips with a clear reason when absent, and `--require-solver <name>` turns a missing solver into a failure. Run solvers in a temp directory, batch mode, with a timeout (architecture §10.3).
*Done when:* a smoke test runs ngspice in batch on a tiny netlist and passes locally; the same test skips with a reason when `NGSPICE_EXE` is unset.

### Corpus

- [x] **T11 — Corpus manifest and fixture migration.**
Per decision 2: create `tests/corpus/ngspice/kicad_basic/` with a manifest (origin: export from maintainer's own KiCad project, license, author, date, notes), `git mv` the three fixtures from `tests/fixtures/`, and preserve their bytes exactly (trailing whitespace, line endings). Note in the manifest that the fixtures use RKM values (`1k0`) and `DC`/`AC` source keywords. Remove the empty `tests/fixtures/`. Ask the maintainer for the origin/license/author/date if they cannot be inferred.
*Done when:* a test checks that every corpus family has a manifest and that fixture hashes match the manifest (guards against accidental reformatting).

### Spikes

- [x] **T12 — ngspice batch spike.**
Run the three fixtures through ngspice in batch mode (`-b -o`) via the T10 harness. Record: which executable to use for batch runs, the exact switches, exit code and output behavior, and whether a netlist with no analysis directive is accepted. Note: the fixtures have no analysis statements, so the spike will add a temporary copy with `.op`/`.ac` (not modifying the fixtures).
*Done when:* findings are in `docs/testing.md`; one solver-backed smoke test is committed.

- [x] **T13 — LTspice export/batch spike.**
Determine (and record in `docs/usage/ltspice-export.md`): the command-line switches for batch simulation and for netlist export from `.asc`, working-directory/output behavior, whether it is usable headlessly, and the encoding of the produced netlist (BOM, UTF-8 vs. UTF-16 vs. cp1252). Use a trivial circuit authored here and save any export as a corpus candidate (not committed until its manifest exists). If an `.asc` cannot be produced without the GUI, ask the maintainer for one.
*Done when:* findings recorded with the LTspice version; open points listed as risks.

### Architecture tests (T7 tier)

- [x] **T14 — `docs/testing.md`.**
Document: environment setup (uv, `.venv`, `.env`), how to run each tier, solver configuration and markers, `--require-solver`, writing golden tests, and the T1/T12/T13 findings.
*Done when:* a new contributor can follow it to a green local run.

- [x] **T15 — Architecture tests.**
In `tests/architecture/`: no `subprocess`/`os.system`/`os.popen` imports in `src/`; layering contract via `import-linter` (layers per architecture §3, initially trivially satisfied); every `.lark` under `src/` compiles with `strict=True` (vacuously true until M2, and must fail on a deliberately conflicting grammar in a self-test); no GPL packages in runtime dependencies.
*Done when:* the tests pass, and each rule is shown to fail on a deliberate violation (self-tests using temporary files).

### Wrap-up

- [x] **T16 — M0 exit check.**
Run `ruff check`, `ruff format --check`, `mypy --strict`, `pytest` (with coverage), `pre-commit run --all-files`, and the local solver smoke test. Update `phase-1-plan.md` section 3 with the final environment instructions and mark M0 done. Remove any temporary files.
*Done when:* all checks are green on this machine and the maintainer's exit criteria in the phase 1 plan (green toolchain; solvers discovered or cleanly skipped) hold.

## 4. Dependencies between tasks

```
T1 → T2 → T3 → T15
T2 → T5, T8 → T9 → T10 → T12
T4 → T5, T11
T3, T6, T6b, T7 (independent after T2; T6 should reference the final pyproject commands)
T1, T10, T12, T13 → T14 → T16
T11, T15 → T16
```

## 5. Out of scope for M0

Grammar work, `SourceText`/`Span` (M1), CI workflows (deferred, plan open point 1), and any change to the architecture document except through a decision record.
