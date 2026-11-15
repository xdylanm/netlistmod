# M20 task list — the 1.0 API review

> **Status:** READY FOR REVIEW — implemented; the maintainer reviews the pull request
> **Follows:** the v1 gate ([v1-review.md](./archive/phase-2/v1-review.md), section 5.1 point 2 and section 6) and the `0.9.0` beta ([decision 0023](../decisions/0023-v1-beta-release.md)). Governed by [architecture.md](../architecture.md) (§2, §14, §16, §17, §18, §21).

## 1. Scope

Decisions 0018 and 0023 leave one question open before 1.0: what 1.0 commits to in the public API (§18), reviewed after the maintainer's practical use of the beta. The maintainer reported on 2026-11-14 that the beta works as expected in practical use. M20 makes that review. It runs in stages with review gates, as M18 and M19 did (section 4).

- **In:**
  - **The 1.0 contract:** what is public, what SemVer covers (names, fields, diagnostic codes and severities, exceptions, messages, what parses), the deprecation policy and the supported Python versions. It is recorded in a decision record and in §18.
  - **The eleven API notes** of [v1-review.md](./archive/phase-2/v1-review.md) section 6, each kept, changed or documented.
  - **The two questioned loads** (v1-review 5.1 point 4): ngspice `R1 a 0 1k |` and `D1 a 0 2` on both dialects.
  - **Library files** (§21): confirmed as a candidate after 1.0, or not.
  - **Stale API text found in the 1.0 reading:** §16's sketch and docstrings such as `Lines.insert_after`'s.
  - Anything else the stage 1 audits find that would be a breaking change after 1.0.
- **Not in M20:**
  - new constructs, and the limits of v1-review 5.2;
  - the version, the classifier and the release, which follow on a `release-1.0.0` branch after M20 is merged (decision 5).

## 2. Decisions

Decisions 1 to 4 set how the milestone runs and are the lead's, as in M19. Decisions 5 to 8 were proposed for the maintainer, each with a recommendation, and decided on 2026-11-14.

1. **Roles.** As M19 decision 1. The **lead** (the session that owns this document) writes the briefs, reviews every report and diff, runs the checks, updates this document and commits; only the lead commits. A **reviewer** (stage 1) reads and runs read-only checks, changes no file and reports. A **developer** (stage 2) changes only the files its brief names, runs the named checks and reports.
2. **Gates.**
   - **G1 (after stage 1):** the lead checks each finding and writes section 5.1, one entry per item with options and a recommendation. **Every API item is the maintainer's decision**; no stage 2 work starts on an item before it is decided.
   - **G2 (after each stage 2 subtask):** the lead reads the diff, runs the subtask's tests and the fast checks, and accepts it (commit, tick) or sends it back with numbered changes.
   - **G3 (after stage 2):** the full run with both solvers, the pull request and CI, then `READY FOR REVIEW`.
3. **Report format.** As M19 decision 3: a one-line verdict, then a table with ID, location, finding, kind (`ok`, `gap`, `stale`, `defect`, `question`, `api`) and proposed action. An `api` finding gives the options, what each breaks for a caller, and a recommendation.
4. **Parallel work.** Stage 1's reviewers run in parallel and read only. Stage 2's developers run in parallel only when their files do not overlap.
5. **The release.** **Decided (maintainer, 2026-11-14): as recommended.** *Recommendation:* as for `0.9.0`, M20's pull request does not change the version. After it is merged, a `release-1.0.0` branch sets `1.0.0`, the classifier `Development Status :: 5 - Production/Stable`, `uv.lock`, the CHANGELOG heading and the README's release line, and the maintainer tags `v1.0.0` and publishes the GitHub Release (decision 0018). *Alternative:* a `0.9.1` or `1.0.0rc1` first, when M20 changes the API enough to want a second beta.
6. **Breaking changes in M20.** **Decided (maintainer, 2026-11-14): as recommended.** *Recommendation:* §18 allows them before 1.0, and this is the last cheap point to make them. A decided change is made directly, with no deprecation shim, and the CHANGELOG lists it with the replacement (as M15b did for `control`). *Alternative:* keep 0.9.0's API and ship each change as a deprecation that 2.0 removes.
7. **The record.** **Decided (maintainer, 2026-11-14): as recommended.** *Recommendation:* one decision record (0024, "The 1.0 public API") holds the contract and every API item's outcome; §18 and the living references follow it in the same change.
8. **Where this list lives.** **Decided (maintainer, 2026-11-14): as recommended.** *Recommendation:* once approved, it moves to a new `archive/v1.0/` with this list's status `COMPLETE`, since phase 2 is closed. *Alternative:* `archive/phase-2/`.

## 3. Starting point (2026-11-14, `70787fe`, `main`)

### 3.1 Inventory

- **Version:** `0.9.0`, classifier `4 - Beta`, published to PyPI on 2026-11-12 (release run green). The repository is public; `main` and `release-*` have rulesets.
- **Decisions:** 0001 to 0023, all accepted.
- **Public names:** `netlistmod.__all__` has 113 entries (with `__version__`, `apply_edits` and `parse`), not sorted. §18 says only "SemVer. Before 1.0 the public API may change".
- **Open items for 1.0:** v1-review 5.1 points 1, 2 and 4 (accepted as limits *for the beta*, recorded for the 1.0 review) and the eleven notes of its section 6.

### 3.2 Baseline run

2026-11-14, at `70787fe`, in a clean worktree of `main`, Windows, Python 3.14, ngspice 47 and LTspice 26.1.1, with `--require-solver ngspice --require-solver ltspice`: **10,207 passed, 2 skipped** (POSIX only), 1,424 deselected; coverage **99.22%**.

## 4. Tasks

Every task that changes a file ends with the checks green, run as `uv run --env-file .env python -m <tool>`: `ruff check`, `ruff format --check`, `mypy --strict`, `lint-imports`, `pre-commit run --all-files` and the tests the task names. Findings outside this list go to section 5.1. Nothing is resolved silently (§15, §21).

### Stage 0 — Set-up (lead)

[x] **T0 — Branch, baseline and briefs.** Branch `m20-api-review`; the baseline run of section 3.2; this list; the stage 1 briefs.

### Stage 1 — Reviews (independent reviewers, in parallel; read-only)

[x] **A1 — The public surface.** Every name in `netlistmod.__all__` and in each subpackage's `__all__`: what it is, whether a caller needs it, whether it is documented in a living reference or a guide, and whether its name, signature, field types and return types are consistent with its neighbours. Underscore-free names reachable from submodules that are not in `netlistmod.__all__`. The eleven notes of v1-review section 6, each with options, what each option breaks, and a recommendation.

[x] **A2 — The contract.** A draft of what §18 should say for 1.0: what is public; whether diagnostic codes, severities, exception classes, dataclass fields, `repr`s and message text are covered; how a grammar change is versioned (a form newly accepted, a form newly refused); the deprecation policy; the supported Python versions and solver versions; the typing promise (`py.typed`, mypy `--strict`). Each point with options and a recommendation, checked against decisions 0001 to 0023 and the living references.

[x] **A3 — Behaviour items and stale text.** The two questioned loads (reproduce; what the manuals say; what making each a `ParseError` would change in the grammar, the tests and the spec entries); library files (§21: what opening one would need, and whether it can be added in a minor release); §16's sketch against the real API; stale or wrong docstrings on public names (for example `Lines.insert_after`, "M6 decides the text inserted there").

### Gate G1 (lead, then the maintainer)

[x] **G1 — Classification and decisions.** Section 5.1 written; the maintainer decides each item.

### Stage 2 — Changes (developers; briefs written after G1)

D1 and D3 run in parallel (their files do not overlap); D2 follows D1, and D4 follows D2 and D3. A developer that needs a file outside its list reports it instead.

[x] **D1 — The public boundary and the signatures (5.1 points 2, 3 and 4.1–4.5, 4.7).** `src/netlistmod/__init__.py` and the subpackage `__init__.py`s, `edit/api.py`, `edit/plan.py`, `document/document.py`, `document/lines.py`, `dialects.py`, the tests that use what changes, `tests/test_package.py`, `document-layer.md`, `edit-layer.md`, `statements.md` and the usage guides.

[x] **D3 — A number as a model name; `|` validated (5.1 points 6 and 7).** The transformer checks (`model/_rules_*.py`), `tests/grammar/`, `tests/solver/` (probe cases), the spec entries and `discrepancies.md` of both dialects, `names.md`, and `elements.md`.

[x] **D2 — Defects and the remaining types (5.1 points 5 and 4.6).** `document/index.py` (`Scope`), `edit/placement.py`, `edit/_ops_common.py`, `edit/_ops_elements.py`, `model/nodes.py` (`form`, `quantity`), their tests, `errors.md` and the living references.

[x] **D4 — Stale text, docs and CI (5.1 point 10).** Docstrings, architecture §13 and §16, README, CONTRIBUTING, `errors.md`, `document-layer.md`, `.github/workflows/release.yml` (`py.typed`), `.github/workflows/ci.yml` (`mypy` on the examples), and the pytest `filterwarnings` setting (point 1, deprecation policy).

[x] **T2 — The record (lead).** Decision 0024 (the contract and every outcome of 5.1, amending decisions 0004 item 5, 0007 item 10 and 0021 item 1), architecture §18, §19 decision 21 and §21, the CHANGELOG (each change with its replacement), and this list.

### Gate G3 (lead)

[x] **T1 — Full run and pull request.** The full check set with both solvers; the pull request; CI green; `READY FOR REVIEW`.

## 5. Findings and log

### 5.1 Items for the maintainer

The three audits (A1: 31 findings; A2: 18; A3: 18) all ended `complete with findings`. The lead reproduced every `defect` and `api` claim used below. For the two questioned loads the lead also probed both solvers on 2026-11-14 (P8; scratch files only, nothing committed):
- **ngspice 47:** `|` in a node name and in a model name runs. `D1 a 0 2` with `.model 2 D(…)` stops with "could not find a valid modelname", and `S1 a 0 c 0 2` with `.model 2 SW(…)` stops too. `R1 a 0 1k 2` with `.model 2 R(…)` runs as a 2 Ω resistor: ngspice reads the `2` as the value, while the library reads it as the model.
- **LTspice 26.1.1:** `D1 a 0 2` and `S1 a 0 c 0 2` run, as `Q1 c b e 2` does, which the library already refuses (decision 0021 item 1).

The items are grouped into ten points, each with a recommendation. Each `api` item that changes code is made directly (decision 6) and listed in the CHANGELOG with its replacement.

1. **The 1.0 contract** (A2-1 to A2-14; A3-5's precaution). §18 is rewritten:
   - **Public:** only `netlistmod.__all__`, with the documented attributes and methods of those objects. Submodules are internal.
   - **Covered by SemVer:**
     - names, signatures and field names and types (a field with a default may be added in a minor release; construct by keyword);
     - enum members and values (enums and the item unions may grow in a minor release);
     - the exception class raised for a condition, and its documented attributes;
     - `DiagnosticCode` members and the §17 severity rules (a new code, or a code fired in a new place, is minor);
     - the topology signature and `digest()` (a minor release may add entries that close a P4 gap, labelled "Signature");
     - the text an edit inserts.
   - **Not covered:** message text, `repr`/`str` (apart from enum values) and `ParseError.expected`.
   - **Grammar:**
     - accepting a form is minor;
     - refusing a form the manual does not allow is minor, labelled "Refused";
     - refusing a form the manual allows, retyping a correct reading, or removing a §19 decision 21 exception is major;
     - fixing a misread is minor.
   - **Deprecation:** a `DeprecationWarning` for at least one minor release, with removal only in the next major; pytest `filterwarnings = error`.
   - **Python:** every CPython from 3.13 in support; a version is dropped only after its end of life, in a minor release.
   - **Solvers:** `validated_on` is evidence, not a support promise.
   - **Typing:** `py.typed` and the annotations are covered.

   *Recommendation:* as drafted by A2. *Alternative:* a narrower contract (names only; fields and diagnostics best-effort).
   **Decided (maintainer, 2026-11-14): the narrower contract.** Names and signatures are covered; dataclass fields and their types, diagnostics (codes, severities, when they fire), the topology digest and the inserted text are best-effort and not covered. §18 also states, as drafted: the grammar versioning rule, the deprecation policy, the Python and solver policy, and that the exception class raised for a condition (and the hierarchy) is covered.
2. **The public boundary** (A1-2 to A1-5, A2-2, A2-3).
   - Make `netlistmod.__all__` the only public list, sort it, and pin the sorted order in `tests/test_package.py`.
   - Export `ScopePath`, `Severity`, `TopLevelItem`, `BodyItem` and `ReferenceKind`, which public signatures use.
   - Drop `Netlist` from `netlistmod.document.__all__`. `from netlistmod.document import Netlist` silently gives the read-only base.
   - Remove the `netlistmod.version` leak.
   - Trim the subpackage `__all__`s to what the package itself imports.
   - Say in the README and the usage README to import from `netlistmod`.

   *Recommendation:* all of it. *Alternative:* the statement only, with no code change.
   **Decided (maintainer, 2026-11-14): as recommended.**
3. **`apply_edits`** (v1-review §6 note 3; A1-23; A3-15). It is public and splices with no verification, beside `Netlist.apply`, which verifies.
   *Recommendation:* make it internal and amend decision 0007 item 10. *Alternatives:* keep it public, with a docstring saying it does not verify; or deprecate it.
   **Decided (maintainer, 2026-11-14): as recommended.**
4. **Signature consistency** (A1-11, A1-12, A1-13; note 7). Each change breaks only the callers it names:
   1. `Dialect` becomes a `StrEnum`; `str()` gives `"ngspice"`.
   2. `placement` is keyword-only everywhere (`add_include`, `directives.add`).
   3. `scope` is keyword-only on the read methods, as on edits.
   4. `set_formula`'s second parameter is renamed `text`, as on its siblings.
   5. `set_switch_state(state: Literal["on", "off"] | None)`.
   6. `ControlledSource.form` and `BehavioralSource.quantity` are typed as `Literal`.
   7. `Lines.insert_after`/`insert_before`, which insert nothing, are renamed `point_after`/`point_before`.

   *Recommendation:* all seven. *Alternative:* pick per item.
   **Decided (maintainer, 2026-11-14): as recommended.**
5. **Defects in public objects** (A1-6, A1-10, A1-14, A1-15, A1-20):
   - `Scope`'s attributes can be assigned; they become read-only.
   - `Placement("bogus")` is accepted, and `Placement("before")` fails later with a bare `AssertionError`; both get a `ValueError` at construction.
   - `in_definition=True` on a top-level edit is silently ignored; it becomes an `EditError`.
   - Passing a `Scope` as `scope=` gives a raw `TypeError`; it gets a message naming `.path`.
   - On LTspice, `set_param("E1", "Laplace", …)` names no alternative; it now points to `set_expression`.

   *Recommendation:* fix all five.
   **Decided (maintainer, 2026-11-14): as recommended.**
6. **A number as a model name** (v1-review 5.1 point 4; A3-2, A3-4). Decision 0021 item 1 ("a field written as a number is never the model") is enforced on Q, M, J, Z, U, T, O, A and N, but not on:
   - D, S and W (both dialects);
   - ngspice R, C and L when a model follows a value.

   The probes support refusing them. ngspice stops on D and S. On R it reads the number as the value, so the library misreads it today. LTspice runs D and S, as it runs the Q form that the library already refuses.
   *Recommendation:* refuse them before 1.0, by the same transformer check as Q (no grammar change). This means:
   - flipping the three pinned cases in `tests/grammar/ngspice/test_elements.py:446-461`;
   - amending decision 0004 item 5 and decision 0021 item 1 through 0024;
   - spec notes and `discrepancies.md` rows.

   `1n4148`, `2N2222` and `1N4148_OJ` stay models. After 1.0 this change would be major.
   *Alternative:* keep the forms as recorded limits.
   **Decided (maintainer, 2026-11-14): uniform refusal,** after the probes of 5.1.1 (asked: "What if a model were named `4093` or similar?"). On both dialects a field the grammar reads as a number (digits, then letters only: `2`, `4093`, `1k`, `4093B`) is never a model name, on every letter, as decision 0021 item 1 already has it for Q and the rest. This adds D, S and W on both dialects and the model after a value on ngspice R, C and L, which also fixes the ngspice misread. On LTspice it is stricter than the manual ("any string without blanks") and the solver, so decision 0024 records it as an exception (§19 decision 21; decision 0022 item 1), with `discrepancies.md` rows on both dialects. A subcircuit name is not affected.
7. **`|` in ngspice names** (v1-review 5.1 point 4; A3-1). The manual's excluded list does not contain `|`, and ngspice 47 runs it in a node and a model name. The library's read is therefore correct.
   *Recommendation:* keep it, and record it as validated: a solver test and a note in NG-NOD-001. *Alternative:* refuse `|`, against the solver and the manual.
   **Decided (maintainer, 2026-11-14): as recommended.**
8. **Library files** (§21; decision 0012 item 6; A3-5). Opening one needs its own entry point and result type, so it can be added in a minor release without changing 1.0 behaviour.
   *Recommendation:* it stays a later candidate, and §21's wording drops "decided after using the beta".
   **Decided (maintainer, 2026-11-14): as recommended.**
9. **The remaining API notes, kept** (notes 1, 2, 4, 5, 6, 8, 9, 10 and 11; A1-13's `model_name`; note 7's `Vcvs`…, `BehavioralSource` and `global_`). Each is kept and documented where the guides don't already say it.
   - **Note 4:** an open set is an enum, a closed vocabulary a `Literal`.
   - **Note 1:** the B `laplace=` parameter versus the E/G form.

   These can be added later in a minor release: a `Netlist.net` delegate (A1-16), exception fields (A1-18), a scoped editor (note 11), `Scope` accepted as `scope=` (note 10), `params.remove`/`models.add` (note 8).
   *Recommendation:* as listed. *Alternative:* name any note to change.
   **Decided (maintainer, 2026-11-14): as recommended.**
10. **Stale text, docs and CI** (A1-7 to A1-9, A1-15, A1-17, A1-19; A2-14 to A2-16; A3-6 to A3-16). These change no behaviour.
    - Replace §16's sketch with a pointer to `edit-layer.md` and `editing.md`. Nine of its calls are wrong.
    - Fix the stale docstrings, among them `OutputVector`'s, which contradicts the behaviour.
    - Fix `errors.md`'s `SourceText.load`, `document-layer.md`'s `has_opaque_include`, `SlotCheck.delimiter`, and the `Dialect.display_name`/`from_name` docs.
    - Update the README's and §13's beta wording, and CONTRIBUTING's "not enforced by branch protection".
    - Check `py.typed` in the release smoke test, and run `mypy --strict` on `docs/usage/examples` in CI.

    *Recommendation:* all of it.
    **Decided (maintainer, 2026-11-14): as recommended.**

#### 5.1.1 Point 6: names like `4093` (lead probes, 2026-11-14)

| Model or subcircuit name | ngspice 47 (D, Q) | LTspice 26.1.1 (D, Q) | Library today |
|---|---|---|---|
| `2`, `4093`, `1k`, `1n`, `2u`, `2meg`, `1e3`, `2.5`, `1N`, `4093k` | stops: "could not find a valid modelname" | runs (`2`, `4093` probed) | D, S, W: a model (resolves). Q, M, J, Z, U, T, O, A, N: `ParseError` |
| `4093B`, `4093x`, `1ohm`, `1kohm` | runs, as a name | (not probed) | D: a model. Q and the rest: `ParseError` (the grammar's number reading: digits, then letters) |
| `CD4093`, `74HC00`, `4N25`, `2N2222`, `1n4148` | runs | runs | a model on every letter |
| a subcircuit `4093` (`X1 a 0 4093`) | runs | runs | loads (X is not checked) |
| ngspice `R1 a 0 1k 4093` with `.model 4093 R` | runs as a 4093 Ω resistor (the number is the value) | — | a model `4093` (a misread) |

ngspice's own test is stricter than the library's: only a field that is entirely a number with a scale factor is refused, and any further letters make it a name. LTspice runs a number as a model name.

### 5.2 Subtask log

- [x] T0: branch, baseline (3.2), this list and the briefs.
- [x] A1: `complete with findings`, 31 items (1 ok, 16 api, 7 gap, 4 stale, 2 defect, 1 question); defects and api claims reproduced by the lead.
- [x] A2: `complete with findings`, 18 items, with a draft §18; claims checked by the lead.
- [x] A3: `complete with findings`, 18 items; both loads reproduced; the lead probed both solvers (5.1, 5.1.1).
- [x] G1: ten points; all decided by the maintainer on 2026-11-14 (point 1 the narrower contract, point 6 uniform refusal, the rest as recommended).
- [x] D1: `complete with findings`. Points 2, 3, 4.1–4.5 and 4.7 made as decided. Lead decisions at G2: `Netlist.scope(path)` stays positional (its argument is the path asked about, not a filter; D1-n4); the slot-check examples that `1k 2k` no longer reaches (D3 refuses it first) use `1k rmod` (D1-n2); D1-n5 and D1-n6 (architecture §4, §5.4, decision 0007 items 10 and 11) go to T2.
- [x] D3: `complete with findings`. Point 6 by the transformer check of decision 0021 item 1 on D, S, W and ngspice R/C/L (no grammar change); point 7 validated; solver probes on both dialects; the lead added the `set_model` test (D3 suggestion) and moved LTspice's `q-number-model` row under "Exceptions to the reference" (D3-3). D3-2 (a `.model` named with a number still loads, though no element can now use it) and D3-4 (`.step` and `ako:` model references are not checked) are recorded in decision 0024; D3-5 is existing behaviour, no change.
- [x] D2: `complete`. Point 5 (a to e) and point 4.6 made as decided, with D1-n7's internal tidy; `_rules_behavioral.py` gained a `cast` for the `quantity` type (D2-n4, accepted). Lead decisions at G2: D2-n1 (`remove_param` on an LTspice `Laplace`) and D2-n2 (the `set_param` docstring) go to D4; D2-n3, `set_switch_state` accepting `"ON"` at run time, stays lenient (outside the typed contract, no change).
- [x] D4: `complete with findings`. Point 10 and the deprecation setting made as decided (§13 and §16 are committed with T2, in the same file as the lead's edits); `remove_param` on an LTspice `Laplace` names `set_expression` (D2-n1); `filterwarnings = ["error"]` needed no ignores, and the solver run with it raised no warning; the release smoke script with the `py.typed` check passed against a fresh wheel. The lead did D4-n1 (`testing.md`), D4-n2 (a B line's `set_value` names `set_expression`, with a test) and D4-n3 (messages say "an OSDI device"; `element_phrase` also no longer gives "an uniform RC line"); D4-n5 is accepted.
- [x] T2: decision 0024 (accepted, the maintainer's G1 decisions), indexed; architecture §4, §5.4, §6.3 rule 14, §18, §19 decision 21 and §21 (with D4's §13 and §16); the CHANGELOG's `Unreleased` entry for M20.
- [x] T1: 2026-11-14, at `cda1e4b`, in a clean worktree of the branch, Windows, Python 3.14, ngspice 47 and LTspice 26.1.1, with `--require-solver ngspice --require-solver ltspice`: **10,634 passed, 2 skipped** (POSIX only), 1,427 deselected; coverage **99.24%**. ruff, mypy (the package, the named tests and the examples), lint-imports and pre-commit are clean.
