# M7 task list — local solver validation (ngspice)

> **Status:** READY FOR REVIEW (2026-10-31) — approved by the maintainer (2026-10-31); section 2 records the decisions, section 9 the implementation.
> **Part of:** [phase-1-plan.md](./phase-1-plan.md) (milestone M7). Governed by [architecture.md](../architecture.md) (§2 P5, P8, P9, P10; §10.1–§10.3 (T8); §11 (normative); §20). Builds on the solver tests of M0–M6 (`tests/solver/`, `tests/support/solvers.py`), the rule documents [names.md](../grammars/ngspice/names.md) and [scoping.md](../grammars/ngspice/scoping.md), [discrepancies.md](../grammars/ngspice/discrepancies.md), and the edit API of [m6-edits.md](./m6-edits.md). Citations use the manual edition in [references.md](../references.md).

## 1. Scope

M7 turns the solver checks that M2–M6 added one milestone at a time into a complete, checked validation layer (architecture §10.3 (a)–(d), §11):

- **Status is checked, not just written.** Every spec entry and every rule in `names.md` and `scoping.md` ends M7 with a status the solver evidence supports, and a test enforces the link between the status, the `validated_on` record and a solver test.
- **(a) The solver accepts the netlist:** every accept fixture of every corpus family, and every golden edit output, runs in ngspice. Missing include files are replaced with stubs authored here.
- **(b) Edited results move as expected:** every edit operation of M6 has a solver test against a closed form.
- **(c) An unedited round trip gives identical results:** for every runnable fixture.
- **(d) Documented behaviours are validated:** the five `documented` spec entries, `NG-STR-001` (marked `validated` without a record) and rule S9 get solver evidence. New discrepancies go into `discrepancies.md`.
- **Test support:** one shared ngspice helper module replaces the five per-file `_run`/`_voltage` copies.

No library code changes are expected. If a probe shows the library is wrong *against the manual*, that is a finding for the maintainer, not a silent fix (AGENTS.md; §11.3).

**Exit (from the plan):** the solver-backed suite passes locally with `--require-solver ngspice`; spec entries updated.

## 2. Decisions (maintainer, 2026-10-31)

The maintainer accepted every recommendation below as written (2026-10-31). "Recommendation" marks the accepted choice; an "Alternative" was considered and not chosen. Decision record 0008 (D1) records the outcome. Probe evidence is in section 7.

1. **What each status means** (§11.2 lists the words, not their meaning).
   *Recommendation:*
   - `validated`: the manual describes the construct, and ngspice reads every form the library **accepts** the way the library models it. Forms the library rejects but ngspice tolerates do not change the status; they are rows in `discrepancies.md`.
   - `observed`: the manual is silent, and the library's behaviour rests on what ngspice does (§11.3 rule 3).
   - `disputed`: ngspice reads a form the library accepts differently from the library's model, and the library does not flag it. None is expected: the RKM `1M0` case is flagged (`solver_mismatch`), so `NG-NUM-003` stays `validated`.
   - `documented`: no solver evidence. Allowed after M7 only with a `validation_note:` saying why the solver cannot decide (none is expected).
   *Alternative:* `disputed` for any entry with a discrepancy row. Not recommended: almost every entry has a rejected form that ngspice tolerates (`.end`, continuations, `.tran` in a body), so the word would lose its signal.
2. **Checking the status.**
   *Recommendation:* extend `tests/architecture/test_spec_coverage.py`:
   - `validated` and `observed` need a non-empty `validated_on` (each item has `solver`, `version` and `date`) and at least one `tests/solver/` test in `tests`;
   - `disputed` needs a `discrepancies.md` row that names the id;
   - `documented` needs `validation_note`.
   Apply the same rules to the rule tables of `names.md` and `scoping.md`, parsed as Markdown tables. The status column takes the four words only, so S5's "validated (discrepancy)" becomes `validated` with its discrepancy row. Each document gets one "Validated on: ngspice 47 (date)" line instead of per-row versions.
   *Alternative:* check spec entries only. Not recommended: the scoping rules are what M5/M6 rely on most.
3. **Running every fixture** ((a) and (c)).
   *Recommendation:* each corpus manifest gains an optional per-fixture `solver` field. Absent means "runs as is". Otherwise it is `{"skip": "<reason>"}` (for example `every_diagnostic.cir`, which is broken on purpose) or `{"stubs": {"<include path>": "<stub file>"}}`. A test checks that every accept fixture either runs or has a reason.
   - **Stubs** are authored here in `tests/corpus/ngspice/solver_stubs/` with a manifest (author `xdylanm`, MIT, confirmed by the maintainer on 2026-10-31; this also covers the raw files of T1). Examples: a `TL072` 8-pin dual op-amp built from ideal sources and a 3-pin `pot` with `R` and `wiper` parameters, both for `kicad_extended`; small `.model`/`.subckt` files for `structure_basic` and the `edits_golden` includes. The stubs are never parsed by the library (they are only included), so they may use phase 2 elements (`E`).
   - **How the stub is wired in:** the test copies the fixture to a temporary folder and points each include at its stub with `directives.replace`. This uses the M6 API, which may replace a whole `.include`. It needs no `HOME` trick for `~/spice-models/...`.
   - **(c):** each runnable fixture is run as is and after `load(...).save(...)`, and the raw-file data sections (after `Values:`) must be identical. The `Date:` line differs between runs; everything else is deterministic (section 7).
   *Alternative:* skip fixtures with external includes. Not recommended: `kicad_extended` is your real export, and it is the closest thing to a user file in the corpus.
4. **Edit results against closed forms** ((b)).
   *Recommendation:* one solver test per M6 operation family, on small circuits whose answer is a formula (section 6). Tolerances, relative to the expected value:
   - linear DC and AC magnitude: `1e-6`, read from the raw file (15 digits), not the log (7 digits);
   - diode and other nonlinear results: `1e-3` (ngspice's default `reltol`).
   Each test asserts the unedited result as well, so a test cannot pass because the edit was ignored.
5. **Solver-backed property test.**
   *Recommendation:* one Hypothesis test that generates sequences of `set_value`/`params.set` edits on a three-resistor ladder with a parameterised leg, applies them (also through `batch()`), and compares ngspice's `v(out)` with the value computed in the test. Settings: `max_examples=20`, `deadline=None`, `derandomize=True`, so the run is reproducible and costs about 20 solver runs.
   *Alternative:* none; leave properties solver-free. Not recommended: this is the one place where "allowed edits keep their meaning" is checked against the solver rather than against the signature.
6. **Shared test support.**
   *Recommendation:* a new `tests/support/ngspice.py` providing:
   - `run(netlist | text | path, *, harness=None, stubs=None) -> Run`, where `Run` holds the return code, log and parsed raw file;
   - a clean-room ASCII raw-file reader (written from the files ngspice produces, section 7);
   - `op(...) -> dict[str, float]`, `ac(...)` and `tran_rows(...)`;
   - an `ensure_runs` harness that adds `.control` / `op` / `.endc` before `.end` with `directives.add` when a file has no analysis. In batch mode ngspice runs nothing without `-r`, `.print` or a control block (section 7).
   The existing five solver files move to it. Test names stay, because spec entries and rule tables cite them. `solvers.py` keeps discovery and `run_ngspice` (P9: `src/` is untouched).
7. **Version recording** (§10.3 hygiene).
   *Recommendation:*
   - a `pytest_report_header` prints each discovered solver's path and version;
   - `validated_on` items are **appended** when M7 re-validates an entry (version `47`, date of the run), never replaced;
   - `docs/testing.md` gets a short re-validation procedure for a new ngspice version.
   No committed observation files (§10.3 "optional"): defer.
8. **New discrepancies** (from today's probes, section 7). Record them, and make no grammar change:
   - a stray `.endc`: ngspice warns and runs, the library rejects it;
   - a node name with brackets (`o[1]`): ngspice accepts it, the library rejects it per §2.1.3.4;
   - `params:` on an X line: ngspice accepts it (1.0 V), the library gives a `ParseError` per §2.11.3.
   *Alternative:* accept any of them. Not recommended: P5, and none appears in your exports.
9. **CI** (plan open point 1).
   *Recommendation:* still deferred. M7 stays local-only (§10.3). Revisit in M9 with the review package.

## 3. Design

### 3.1 Layout

| Path | Contents |
|---|---|
| `tests/support/ngspice.py` | `run`, `Run`, raw reader, `op`/`ac`/`tran_rows`, `ensure_runs`, stub wiring (decision 6) |
| `tests/support/solvers.py` | unchanged except the report header hook's data |
| `tests/solver/test_ngspice_corpus.py` | (a) and (c) over every manifest (decision 3) |
| `tests/solver/test_ngspice_edit_results.py` | (b), section 6 |
| `tests/solver/test_ngspice_edit_properties.py` | decision 5 |
| `tests/solver/test_ngspice_validation.py` | probes for the entries and rules of section 5 |
| `tests/corpus/ngspice/solver_stubs/` | stub include files and their manifest |
| `tests/architecture/test_spec_coverage.py` | the status checks of decision 2 |

### 3.2 Raw file

ngspice 47 on Windows writes ASCII raw files by default with `-r` (section 7). The reader takes the `Title`, `Plotname`, `Flags`, `No. Variables`, `No. Points`, `Variables` and `Values` sections. `Flags: complex` values are `re,im` pairs. Several plots in one file (two analyses) give several plots. The reader may use `str` methods and regular expressions: it is test code reading solver output, not netlist syntax (P13 governs `src/`). The task is to settle whether to force ASCII with the environment variable `SPICE_ASCIIRAWFILE=1` (checked in the manual and on the binary).

## 4. Tasks

Every task ends with `ruff check`, `ruff format --check`, `mypy --strict`, `lint-imports`, and `pytest` (coverage gate) green, run as `uv run --env-file .env python -m <tool>`. Solver tasks also run with `--require-solver ngspice`. On Smart App Control failures, follow `docs/testing.md`. Where a task says "settle", state the choice with its basis in the report.

### Decisions

[x] **D1 — Decision record 0008: validation status and solver harnesses.**
Record section 2. Amend the architecture:
- §11.2: the meaning of each status, `validation_note`;
- §10.3: manifest `solver` field, stubs, the raw-file comparison for (c), the report header;
- §10.5: the stub family.
Status `proposed` until the maintainer accepts it.

### Test support

[x] **T1 — `tests/support/ngspice.py`** (decision 6, 3.2).
Raw reader with unit tests on raw files produced by ngspice 47 and committed under `tests/corpus/ngspice/solver_stubs/raw/` (op, ac with complex values, tran, two plots in one file). `ensure_runs` uses the edit API. Settle the ASCII question.

[x] **T2 — Move the existing solver tests to the helper.**
Mechanical. Same test names and parametrisation ids. The per-file `_run`/`_voltage` helpers are deleted. Values read from the log become raw-file reads where the tolerance tightens.

[x] **T3 — Report header and version records** (decision 7).

### Validation

[x] **T4 — Status checker** (decision 2).
Extend `test_spec_coverage.py` for spec entries and the two rule tables, with negative tests on crafted entries (as the existing checker tests do). Fix what it finds: `NG-STR-001` (no `validated_on`), S5's status word, S9.

[x] **T5 — Corpus sweep** (decision 3).
Manifest `solver` fields, stub family and manifest, `test_ngspice_corpus.py` for (a) and (c). Covers `structure_basic`, `kicad_basic`, `kicad_extended`, `elements_basic`, `statements_basic`, `document_basic`, the `edits_golden` inputs and expected files. The `*_rejects` families are already probed by the discrepancy tests.

[x] **T6 — Edit results** (decision 4, section 6).

[x] **T7 — Solver property test** (decision 5).

[x] **T8 — Entry and rule validation** (section 5).
Probe tests for each row, with assertions both on ngspice and on the library, as the M5 tests do. Update each entry's `status`, `validated_on`, `tests` and `notes`, and each rule row. New discrepancies (decision 8) go into `discrepancies.md` with their evidence tests.

### Docs and exit

[x] **T9 — Docs.**
- `docs/testing.md`: the helper, manifests with `solver` fields, how to add a stub, the re-validation procedure, the expected solver-suite runtime;
- `docs/grammars/ngspice/README.md`: a status summary table (entry → status → versions);
- CHANGELOG (test-only and doc changes; say so);
- the phase plan's M7 heading.

[x] **T10 — Exit.**
Full check set, a fresh-clone run with `--require-solver ngspice`, and the runtime of the solver suite. Report what changed, every "settle" with its basis, deviations, and any finding where ngspice and the library disagree on an *accepted* form (decision 1: a candidate `disputed`). Set this document's status to `READY FOR REVIEW`. **Do not archive.**

## 5. Validation work per entry and rule

| Item | Now | M7 action | Evidence today (section 7) |
|---|---|---|---|
| `NG-DIR-001` unknown dot-commands, stray terminators | documented | probe `.print`, `.func` (used in a value), `.width`, stray `.endc`/`.ends`/`.endif` → `validated` | `.func` takes effect; stray `.endc` runs with a warning (discrepancy); stray `.ends` fails in both |
| `NG-NOD-001` names | documented | probe names with `/`, `+`, `-`, `#`, digits first, and the excluded characters → `validated` | `a/b`, `n+1` agree; `o[1]` is accepted by ngspice only (discrepancy) |
| `NG-PAR-001` instance parameters, `off` | documented | `m=2` and `tc1` with `.temp` move the result; `off` is accepted → `validated` | `m=2`: 2.0 V; `tc1=0.01` at 127 °C: 1.0 V; `off` runs |
| `NG-UNS-001` unsupported forms | documented | ngspice accepts each source function, `DISTOF`, `q=`; `params:` → `validated` (the forms are real syntax, so "unsupported", not "invalid", is right) | `PULSE` runs; `params:` runs (discrepancy) |
| `NG-VAL-001` formulas, strings | documented | `{…}` and `'…'` evaluate the same; `{a;b}` fails in both; string default and override run → `validated` | all three agree |
| `NG-STR-001` structure | validated, no record | run `structure_basic` with stubs; add `validated_on` | missing `models.lib` today |
| `NG-COM-001`, `NG-NUM-004`, `NG-TXT-001` | observed | keep `observed`; check the record and solver test | — |
| S9 (`K`, `.dc`, `.save i()` in one scope) | documented | probe cross-scope references → `validated` | `K1` cannot reach `L1` in `X1`; `.dc V9` cannot reach `X1`'s source; the library warns `UNRESOLVED_ELEMENT` for both |
| S5 | "validated (discrepancy)" | status word `validated` | — |
| every other entry and rule | validated / observed | re-run under the shared helper; append `validated_on` | — |

## 6. Edit results (minimum; extend in T6)

| Operation | Circuit | Before → after (closed form) |
|---|---|---|
| `set_value` R | 3 V divider, R1 = R2 = 1k | `set_value("R2", "3k")`: 1.5 → 2.25 V |
| `set_value` C | RC low-pass 1k, 1u, at f = 1/(2π·1k·1u) | `C1` → 2u: \|H\| 1/√2 → 1/√5 |
| `set_value` L | RL low-pass (L series, R to ground), 1k, 1m, at f = 1k/(2π·1m) | `L1` → 2m: \|H\| 1/√2 → 1/√5 |
| `set_formula` + `params.set` (add) | divider | `R2` → `{rx}`, `rx=3k`: 2.25 V |
| `params.set` (replace, top level) | `.param rx=1k` used twice | 1.5 → 2.25 V |
| `params.set` in a definition (`in_definition`) | two instances of a divider subcircuit | both outputs move |
| `set_instance_param` X | the same | only that instance moves |
| `set_param` R | divider | `m=2` on R1: 1.5 → 2.0 V; `tc1=0.01` with `.temp 127`: 1.5 → 1.0 V |
| `set_model` D | 1 mA into a diode, models with `is=1e-14` and `is=1e-12` | ΔV = n·Vt·ln 100 ≈ 0.1191 V at 27 °C (1e-3) |
| `set_model_param` D | the same | `is` 1e-14 → 1e-12: the same ΔV |
| `set_model` + `remove_value` R | semiconductor resistor | geometry value (existing M6 test, moved) |
| `set_dc` V and I | divider; I into R | linear |
| `set_ac` | divider with `AC 1` | magnitude 2: \|v(out)\| doubles; phase 90: `vp(out)` = π/2 |
| `set_coupling` K | L1 = L2 = 1m, secondary open (1 GΩ to ground), V AC 1 on L1 | \|v2\| = k: 0.5 → 0.9 (1e-3) |
| `directives.set` `.tran` | RC charge from `DC 1` with `.ic v(out)=0` and `uic` (no `PULSE`: unsupported) | end time changes; v(tstop) = 1 − e^(−tstop/τ) (1e-3) |
| `directives.set` `.temp` | divider with `tc1` | as `set_param` row |
| `directives.add` `.dc` | divider | sweep endpoints are linear |
| `add_include` | harness that adds `.op`/`.save` | runs (existing test, moved) |
| batch of three | divider + `.param` + `.tran` | the combined result |

## 7. Probe facts gathered while planning (ngspice 47, 2026-10-31)

- **Batch mode runs nothing** without `-r <raw>`, a `.print`/`.plot`/`.four` line or a `.control` block: "no simulations run" and exit code 1. With `-r` it runs, also for files without any analysis line, which then produce no data. Hence `ensure_runs` (decision 6).
- **Raw files:** with `-r` on Windows the file is ASCII (`Values:` section, 15 significant digits). Two runs of one file differ only in the `Date:` line.
- **Corpus status today:**
  - every `edits_golden` file without an include runs;
  - the files with `old_models.lib`, `new_models.lib`, `harness.cir` or `h.cir` stop at the missing include, as do `structure_basic` (`models.lib`) and `kicad_extended` (`~/spice-models/...`);
  - `kicad_basic` and the inputs without an analysis run with `-r`.
- **Documented entries** (each case was also loaded in the library):
  - `.func dbl(x) {2*x}` used in `{dbl(1k)}` takes effect. `.width out=80` is ignored with a warning. Both stay unknown directives in the library.
  - A stray `.endc` warns and runs; the library rejects it (new discrepancy). A stray `.ends` fails in both.
  - `a/b` and `n+1` are node names in both. `o[1]` runs in ngspice; the library rejects it (new discrepancy).
  - `R1 in out 1k m=2` gives 2.0 V. `tc1=0.01` with `.temp 127` gives 1.0 V. `D1 a 0 dm off` runs (0.629 V).
  - `PULSE(…)` runs with `.tran`. `X1 … params: r=2k` gives 1.0 V (new discrepancy: the library rejects `params:`).
  - `'a*2'` and `{a}` evaluate. `{a;b}` fails in both. String defaults and overrides (`f="x"`, `f="y"`) run.
- **S9:** a top-level `K1 L1 L2` cannot couple to `L1` inside `X1` ("coupling to non-existent inductor"). `.dc V9` cannot sweep a source inside `X1` ("not in the circuit"). The library reports `UNRESOLVED_ELEMENT` (warning) for both.

## 8. Out of scope for M7

- Library behaviour changes. A disagreement on an accepted form is reported (T10), not fixed.
- LTspice (M8) and the phase 1 review package (M9).
- CI, and committed solver observation files (decisions 7, 9).
- Validating what included third-party files define. The stubs stand in for them.
- Performance bounds on the solver suite (record its runtime only).

## 9. Implementation report (2026-10-31)

**What changed.** Test and documentation changes only; `src/` is untouched. Decision record
[0008](../decisions/0008-validation-status-and-solver-harnesses.md) (status `proposed`) and the
architecture amendments of D1 (§10.3, §10.5, §11.2). The shared harness
`tests/support/ngspice.py` (T1) with its solver-free tests `tests/test_ngspice_raw_reader.py`
and raw samples in `tests/corpus/ngspice/solver_stubs/raw/`; `run_ngspice` gained an `env`
argument. The five solver files of M2–M6 use the harness (T2; same test names and ids, the
per-file helpers deleted; values from the raw file). A `pytest_report_header` (T3). The status
checker and a README status-table check in `tests/architecture/test_spec_coverage.py` with
negative tests (T4). The stub family `solver_stubs/`, `solver` fields in five corpus manifests,
`tests/solver/test_ngspice_corpus.py` and a manifest check in `tests/test_corpus_manifests.py`
(T5). `tests/solver/test_ngspice_edit_results.py`, 20 tests (T6; the M6 geometry-switch test
moved here). `tests/solver/test_ngspice_edit_properties.py` (T7).
`tests/solver/test_ngspice_validation.py`, 46 probes, and the spec, rule-table and
discrepancy updates (T8). Docs (T9): `testing.md`, the ngspice README status table, CHANGELOG,
the phase plan, `names.md`, `scoping.md`, `discrepancies.md`.

**Results.** Full suite with `--require-solver ngspice`: 1703 passed, 2 skipped (POSIX-only),
coverage 98.77%, 110 s. The solver suite: 334 tests (168 before M7) in about 75 s, of which the
corpus sweep is about 26 s. `ruff check`, `ruff format --check`, `mypy --strict` and
`lint-imports` are clean; the new test-support and test files also pass `mypy --strict`
(outside the configured `src/` scope). Every spec entry now has a 2026-10-31 ngspice 47 record
(appended; FML, GLB and SAV already had one). Statuses: 36 `validated`, 3 `observed`
(`NG-COM-001`, `NG-NUM-004`, `NG-TXT-001`), none `documented` or `disputed`.

**Settled:**

- *ASCII raw files (T1):* ngspice 47's `spinit` sets `filetype=ascii`, which wins over
  `SPICE_ASCIIRAWFILE` (probed with the variable at 0 and 1: ASCII both times; only a
  `.spiceinit` with `set filetype=binary` gives `Binary:`). The harness sets
  `SPICE_ASCIIRAWFILE=1` for other builds, and the reader raises on `Binary:`. Raw files are
  CRLF.
- *`ensure_runs` adds an `.op` line, not a control block (T1):* with `-r`, `.control` / `op` /
  `.endc` produced no raw file at all, while an `.op` line writes the operating point, also when
  the file has a control block (probes p1–p9).
- *Device values (T2):* with `-r`, ngspice prints no device tables to the log, so the M3 value
  probes save `@r1[resistance]` / `@c1[capacitance]` and read them from the raw file (ngspice
  names the resistor vector `v(@r1[resistance])`).
- *`.include` stubs (T5):* `directives.replace` refuses `.include` text by design (decision 0007
  amendment 1), so an `.include` line is removed and `add_include` adds the stub after the line
  before it, in one batch; a `.lib` line uses `directives.replace`. Include paths are matched as
  the whole path token.

**Deviations from this list:**

- **`harness` manifest form** (decision 3 lists `skip` and `stubs`): the `elements_basic`
  fixtures need the M3 definitions, now `solver_stubs/elements_harness.inc`, included before
  `.end`.
- **`structure_basic.cir` is skipped**, not run with stubs (section 5 expected it to run). It
  has `.if {enabled}`, which ngspice 47 stops at, and it includes one `models.lib` both whole
  and as the section `typical`, which no single file can serve (a `.lib` section in a file
  included whole is "unimplemented"). `NG-STR-001` is validated by
  `test_structure_sample_runs_with_a_valid_condition`, the same structure with `.if (enabled)`
  and two stubs.
- **More excluded name characters** (decision 8 named `o[1]`): ngspice 47 also accepts `%`,
  `<`, `~` and `(` in a node name; one discrepancy row covers them; the grammar is unchanged.
- The run of every fixture has the library prepare it (stubs, `.op`) for both runs of (c), so
  (c) compares the original against its unedited save under the same preparation.

**Finding for the maintainer (decision 1, candidate `disputed`):** the library accepts
`.if {expr}` (an opaque block; the condition is not checked), and ngspice 47 stops at it ("Bad
syntax") and reads `.if (expr)`. That is a form the library accepts and ngspice reads
differently, without a diagnostic. `NG-OPA-001` is left `validated` with a note, and
`discrepancies.md` has an "open finding" section; evidence:
`test_an_if_condition_in_braces_fails_in_ngspice_but_the_library_keeps_it`. Options: mark
`NG-OPA-001` `disputed`; or check the condition form (a grammar change, out of M7 scope).
No other accepted form disagreed.
