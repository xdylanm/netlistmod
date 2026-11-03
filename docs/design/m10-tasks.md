# M10 task list — CI and project infrastructure

> **Status:** READY FOR REVIEW — T1–T10 are done, with the results in section 5; T11 follows the maintainer's approval
> **Part of:** [phase-2-plan.md](./phase-2-plan.md) (milestone M10). Governed by [architecture.md](../architecture.md) (§10, §13, §14, §19).

## 1. Scope

M10 adds the checks that every later milestone's pull request must pass, and runs the solver-free suite on Linux for the first time.

- **In:** GitHub Actions on Linux and Windows with Python 3.13 and 3.14; Dependabot; fixes for anything the new platforms and Python version expose; the device matrices' milestones; a decision record for the architecture's infrastructure sections; the documented pull request workflow.
- **Not in M10:** new grammar, spec entries or edit operations. macOS, any solver in CI, and a release workflow or PyPI publication (plan section 8). `src/` changes only if a new platform exposes a real defect, each with a test and a CHANGELOG line.

**Exit:** all checks are green on a pull request, from a clean environment with no solver.

## 2. Decisions (maintainer, 2026-11-03)

The maintainer accepted each recommendation. "Alternative" marks an option considered and not chosen.

1. **How CI treats solver tests.** Run the whole suite with no `-m` filter and no `--require-solver`, so solver tests skip through the fixture. This also proves that they skip cleanly, and any unmarked test that needs a solver fails instead of staying hidden. *Alternative:* `-m "not solver"`, which is simpler but proves neither.
2. **Merge method for milestone pull requests.** "Rebase and merge", which keeps `main` linear and keeps each commit's message, as in phase 1. *Alternatives:* squash, which loses the milestones' separate commits; a merge commit, which ends the linear history.
3. **Repository visibility and branch protection.** Stay private for M10, and merge only on green by convention, since the free plan does not enforce branch protection on a private repository. Going public is decided at the 0.9 tag, after weighing the LTspice licence point in [provenance.md](../provenance.md). The maintainer changes visibility; no task here does. If the repository goes public sooner, T9 turns on protection.
4. **Coverage gate in CI.** Keep the 90% gate on every test job. The solver-free run on Windows gives 98.92% with no solver tests, the same as the full run, so nothing depends on a solver to reach it.
5. **Hypothesis in CI.** A CI profile with `derandomize=True` for the required jobs, so a pull request cannot fail on an example unrelated to its change. Local runs stay random and keep finding new examples. The tests already set `deadline=None`.

## 3. Starting point (2026-11-03, `52204f0`)

- There is no `.github/` folder. All checks have only been run locally on Windows with Python 3.14.3.
- Solver-free run on Windows (`-m "not solver"`): 3370 passed, 2 skipped, 1606 deselected, about a minute, coverage 98.92%.
- **Never run:** the two POSIX-only tests in `tests/test_source.py`, anything on Linux, and anything on Python 3.13.
- `tests/test_docs.py` and `tests/architecture/` already cover links, spec coverage and strict grammar builds inside `pytest`.
- `uv run --env-file .env` fails without a `.env`, so CI commands leave out `--env-file`.
- The repository is private and on the free plan; WSL is not installed on the Windows machine.
- `tests/architecture/test_spec_coverage.py` only allows the milestones `M3` and `M8` in the device matrices and maps all others to `post-review`, so T7 must change it.

## 4. Tasks

[x] **T1 — Decision record 0011: CI and release scope.** Status `proposed` until M10 closes. It records:
- Platforms are Linux and Windows; macOS is neither required nor claimed.
- CI installs no solver, and the optional ngspice job is dropped, because the local run covers solvers and a distribution package may differ from the validated ngspice 47.
- There is no release-on-tag or PyPI workflow in v1, which is tagged `0.9.0`.
- One pull request per milestone.
- Amendments: §10.3 ("Environment"), §13 ("GitHub Actions", "Branch protection", the "Phase 1" line), §19 decision 14, and the §4 layout, which regains `.github/`. Decision 0010 item 2 is fulfilled.

[x] **T2 — Lint and type job, `.github/workflows/ci.yml`.** Runs on pull requests and pushes to `main`, on Ubuntu with Python 3.13, using `uv sync --locked`:
- `ruff check` and `ruff format --check`
- `mypy` for the configured `src/` scope, and `mypy --strict` on the test files M9's T10 named (test support, solver tests, doc tests). Record that list in `docs/testing.md`, so that the command has one home.
- The import-linter contract
- `pre-commit run --all-files`

Set `permissions: contents: read`, and cancel a superseded run on the same branch. Pin actions to full commit hashes, so Dependabot can raise updates.

[x] **T3 — Test job.** A matrix of `ubuntu-latest` and `windows-latest` with Python 3.13 and 3.14, `fail-fast: false`, per decisions 1, 4 and 5. Use `uv python install` for the interpreter, and `python -m pytest` as elsewhere. The log's session header shows no solver found. Add the Hypothesis profile of decision 5, selected with `--hypothesis-profile=ci`.

[x] **T4 — First Linux and Python 3.13 run.** Open the pull request and fix what fails:
- Expected kinds of failure: default text encoding, path separators and case, file permissions, line endings, the two POSIX-only tests, and packaging in `test_packaged_grammar.py`.
- A test that turns out to need a solver gets the marker.
- A real library defect gets its own test and CHANGELOG line. Never weaken an invariant, and never skip a test to get a pass (§15); a platform skip needs a stated reason that is a real platform difference.
- `requires-python` stays `>=3.13` if 3.13 passes. If it does not, stop and raise it.
- Record any Linux finding in `docs/testing.md`.

Optionally, the maintainer can run the suite earlier on their Linux machine or in WSL.

[x] **T5 — Dependabot, `.github/dependabot.yml`.** GitHub Actions and the uv lockfile, weekly, with minor and patch updates grouped to limit noise. Confirm that the `uv` ecosystem is supported for `uv.lock` on the first run; if it is not, leave dependencies out and record that. An update goes through the same checks, and a Lark update needs extra care because it can change what parses.

[x] **T6 — Keep the checks honest.** A deliberately broken commit on a throwaway branch shows each kind of check fails: a lint error, a type error, a failing test, and a broken link. Delete the branch afterwards. Record the result in section 5 of this list.

[x] **T7 — Device matrices.** Replace the `post-review` milestone and "milestone sequence TBD" in `ngspice-devices.json`, `ltspice-devices.json` and both `devices.md` files with the assignments of plan section 5. U in ngspice is `M16` and `M17`; say so in the note under the table. Change `test_spec_coverage.py` so it compares milestones exactly rather than mapping them. Check that nothing else reads this field; no behaviour changes.

[x] **T8 — Documentation.**
- `docs/testing.md`: a CI section saying what runs where, what CI does not cover, and how to read a failure. Make clear that the local run with both solvers stays required for every milestone.
- `CONTRIBUTING.md`: the pull request workflow, merge rule and merge method.
- `README.md`: supported platforms (Linux and Windows).
- `AGENTS.md` and `docs/testing.md`: the "Linux and macOS" interpreter wording becomes Linux.
- `CHANGELOG.md`: CI added, macOS not claimed.

[x] **T9 — Merge rule.** Merge only on green. If the repository is public by then (decision 3), turn on branch protection for `main`, requiring the lint and test checks; that setting is the maintainer's, with instructions here. Otherwise record in `CONTRIBUTING.md` that the rule is by convention. The repository is still private, so the convention stands.

[x] **T10 — Final evidence and handover.** Run the full local check set with `--require-solver ngspice --require-solver ltspice` on Windows, to show that the fixes broke nothing. Record that run and the green CI run with its commit in section 5, set the status to `READY FOR REVIEW`, and update the plan's status and M10 heading and the index.

### After the maintainer's approval

[ ] **T11 — Close M10.** Merge the pull request by the chosen method. Status `COMPLETE (date)`, `git mv` to `docs/design/archive/phase-2/`, fix links, update the plan and index, and accept decision 0011. Then confirm that Dependabot reads its configuration, which it only does from the default branch (T5); if it rejects the `uv` ecosystem, leave dependencies out and record that.

## 5. Results

**CI on `861dbbc` (T4, [PR 1](https://github.com/xdylanm/netlistmod/pull/1), run 41582121058): all five jobs green.** This was the first run on Linux and on Python 3.13, and it needed no fixes, so `src/` has no platform change and `requires-python` stays `>=3.13`. There is no Linux finding to record in `docs/testing.md`.

| Job | Python | Passed | Skipped | Deselected | Coverage |
|---|---|---:|---:|---:|---:|
| Ubuntu | 3.13.18 | 3379 | 1155 | 446 | 98.92% |
| Ubuntu | 3.14.10 | 3379 | 1155 | 446 | 98.92% |
| Windows | 3.13.17 | 3378 | 1156 | 446 | 98.92% |
| Windows | 3.14.10 | 3378 | 1156 | 446 | 98.92% |

- Each session header says both solvers are `not found`, and the solver tests skip through their fixture.
- The difference of one between platforms is `tests/test_source.py`: Windows skips the two POSIX tests and Linux skips the one Windows read-only test. The POSIX tests ran for the first time here, and passed.
- The 446 deselected are the dialect pairs of M8 decision 16, the same as locally.
- The lint and types job passed every step, including the import contract (1 kept, 0 broken).

**The checks fail when they should (T6, `861dbbc` plus one break each).** Each break had its own draft pull request, because the lint job stops at its first failing step. All four were closed and their branches deleted.

| Break | Pull request | Failed | Reported as | Other jobs |
|---|---|---|---|---|
| Unused import in `src/` | [2](https://github.com/xdylanm/netlistmod/pull/2) | `ruff check` in lint and types | `F401` | Test jobs green |
| Wrong type in `src/` | [3](https://github.com/xdylanm/netlistmod/pull/3) | `mypy` in lint and types | `Incompatible types in assignment` | Test jobs green |
| Failing test | [4](https://github.com/xdylanm/netlistmod/pull/4) | All four test jobs | `tests/test_m10_t6.py::test_m10_t6_fails` | Lint and types green |
| Broken link in `docs/testing.md` | [5](https://github.com/xdylanm/netlistmod/pull/5) | All four test jobs | `test_relative_links_resolve[docs/testing.md]` | Lint and types green |

**Full local run on `861dbbc` (T10, Windows, Python 3.14.3, ngspice 47, LTspice 26.1.1.0):** 4532 passed, 2 skipped, 446 deselected, 11 minutes 14 seconds, coverage 98.92%, with `--require-solver ngspice --require-solver ltspice`. `ruff check`, `ruff format --check`, `mypy` (26 files), the named `mypy --strict` (29 files), the import contract and `pre-commit run --all-files` are all clean.

**Not confirmed:**
- **Dependabot (T5).** It only reads `.github/dependabot.yml` from the default branch, so the `uv` ecosystem cannot be confirmed until this pull request merges. T11 checks it.
- **A Linux desktop or WSL run.** It was optional and has not been done. CI's Ubuntu 24.04 jobs are the only Linux evidence, and they run no solver, so no solver has been run on Linux.
