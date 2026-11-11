# M18 task list — Completeness audit

> **Status:** ACTIVE — stage 1 (audits A1 to A4) started on 2026-11-10; stage 2 waits on the audit review (gate G1) and on the decisions marked *for the maintainer* in section 2
> **Part of:** [phase-2-plan.md](./phase-2-plan.md) (milestone M18). Governed by [architecture.md](../architecture.md) (§2, §6.3, §6.4, §6.7, §7.8, §10, §11, §17). Follows [M17](./archive/phase-2/m17-tasks.md) and carries the items noted for M18 in [M15b](./archive/phase-2/m15b-tasks.md) 6.3, [M16](./archive/phase-2/m16-tasks.md) 6.3 and [M17](./archive/phase-2/m17-tasks.md) 6.3.

## 1. Scope

M18 adds no device letter. It checks the library against the phase 2 plan and architecture before the v1 review package (M19), and fixes what the check finds. Unlike M10 to M17, most of the work is reading: the plan's M18 entry lists what to check, and the fixes are not known until the audits report. So the task list runs in **stages with review gates** (section 4), and each audit or fix is an **independent subtask** that a separate reviewer or developer carries out and reports back to the milestone lead. The lead reviews each report, decides whether the next stage may start, keeps this document current, and records each completed subtask with a commit.

- **In (plan M18):**
  - **Value specifications (§6.4):** the manual's full range against the grammar in both dialects, including the comma-separated lists of LTspice's `discrepancies.md`.
  - **Architecture tests:** no matrix entry is `planned`; every remaining `UnsupportedConstruct` path is justified; the lookaround terminal list is reviewed (phase 1 limit 3).
  - **Corpus:** real circuits for each device group, with manifests and provenance; the independent Hypothesis oracle and the edit properties extended to the phase 2 elements.
  - **Messages carried from M15b and M16,** and **diagnostics and messages carried from M17** (section 3.3).
  - **Spec coverage:** every construct with tests, and each `documented` entry saying why the solver cannot decide.
- **Also in:** stale text the audits find in docstrings, grammar comments and docs (a fix of wording, not of behaviour).
- **Not in M18:**
  - new device letters, and the v1 exclusions (ngspice digital U, LTspice `.machine`), which stay `UnsupportedConstruct`;
  - the usage guides, README and CHANGELOG pass, the version `0.9.0`, the clean-clone evidence and the v1 review package, which are M19. M18 updates these only where its own changes need it (plan section 4);
  - a release. M18 ends at its own merged pull request (decision 0018).

**Exit (plan):** the spec-coverage report shows every construct with tests, and each `documented` entry says why the solver cannot decide. Also:
- every audit finding is either fixed with a test, recorded as a documented limit, or marked out of v1 with the maintainer's agreement;
- no matrix entry is `planned`, and every remaining `UnsupportedConstruct` path is listed with its reason;
- the signature snapshot is unchanged and the compatibility test passes;
- the full local check set passes with both solvers, and CI is green.

## 2. Decisions

Decisions 1 to 4 set how the milestone runs and are the lead's, following the user's instruction of 2026-11-10 to run M18 as an audit with independent subtasks. Decisions 5 to 9 are **proposed**, each with a recommendation; those marked *for the maintainer* change behaviour or the plan and wait on the maintainer before their stage-2 subtask starts. More decisions will be added at gate G1 from the audit findings.

1. **Roles.** Three roles, each subtask taking one:
   - **Lead** (the session that owns this document): writes the subtask briefs, reviews every report and diff, runs or reads the checks, updates this document, commits, and decides each gate. Only the lead commits.
   - **Reviewer** (stage 1): reads and runs read-only checks, including scratch probes on the solvers outside the repository. It changes no file in the repository; it reports findings in the format of decision 3.
   - **Developer** (stage 2): changes only the files its brief names, adds the tests first or with each change, runs the named checks, and reports. It does not commit.
2. **Gates.** A stage starts only when the lead has reviewed the reports of the stage before it:
   - **G1 (after stage 1):** each finding is checked by the lead (every `gap` by reproduction, a sample of the `ok` rows by spot check) and classified in section 5.1. Findings that change behaviour or the plan become decisions in this section for the maintainer.
   - **G2 (after each stage 2 subtask):** the lead reads the diff, runs the subtask's tests and the fast checks (`ruff`, `mypy --strict`, the architecture tests), and either accepts it (commit, tick) or sends it back with numbered changes, as a review round does.
   - **G3 (after stage 2):** the full local check set with both solvers, then the pull request and CI, then `READY FOR REVIEW`.
3. **Report format.** Every reviewer and developer report starts with a one-line verdict (`complete`, `complete with findings` or `blocked`), then a table:

   | # | Item | Evidence (file:line, test, probe) | Verdict | Proposed action |
   |---|---|---|---|---|

   Verdicts are `ok`, `gap` (missing or wrong), `stale` (text no longer true) and `question` (needs a decision). Proposed actions are `fix in M18` (naming the subtask), `document as a limit`, or `out of v1`. A developer report adds the files changed, the tests added and the commands run with their results.
4. **Parallel work.** Stage 1 runs its four audits in parallel, since none writes to the repository. In stage 2, two developers run at the same time only when their briefs name disjoint files; grammar and rule changes (D1, D2, D5) run one after another.
5. **Carried LTspice forms that load and that LTspice stops on** (M16 6.3, M17 6.3). *Proposed, for the maintainer.* The library's rule so far: a form that the library reads correctly and the solver stops on may load when it cannot misread a line (M17 decisions 4 and 7). The four carried items differ:

   | Form | Library today | LTspice 26.1.1 | Proposed |
   |---|---|---|---|
   | a `+` line that holds only a comment | loads | stops | **refuse** (`ParseError`): it is a line shape the grammar can see, and P5 asks for it |
   | `.model x BUF(…)` (a special-function type) | loads | stops ("Expected model definition" when used) | **refuse** the type in the LTspice `.model` rule if A1 or D2's probe shows LTspice stops on the `.model` line itself; otherwise a warning when an A line uses it |
   | `@ … zm` with an `&` probe for it | loads | stops ("FRA Probe not supported … impedance measurement mode") | **diagnostic** (warning) on the probe: it spans two lines, so it is not a grammar check |
   | `@` under `.fra` with neither `fstart=`/`fend=` nor `flist=` | loads | stops ("Missing parameter") | **diagnostic** (warning) on the `@` line, only when the netlist has a `.fra` command |

   New diagnostic codes change §17, so decision 7 records them. *Considered:* leaving all four as `discrepancies.md` rows.
6. **The planned-letter path in the loader.** *Proposed (lead).* Keep it, with its mocked-matrix tests (M17 decision 10): §6.7 still defines the `planned` status, and a later dialect (qspice, xyce; §9.2) will use it. A2 lists it as a justified path. *Considered:* removing it as dead code in v1.
7. **A decision record for M18.** *Proposed, for the maintainer.* One record, `0021-completeness-audit.md`, written at gate G1 and `proposed` until M18 closes. It records decision 5's outcome and any new diagnostic codes (§17), the lookaround review (decision 8), and any other normative change G1 accepts. If G1 accepts no normative change, M18 needs no record, and the lookaround review is recorded in the grammar READMEs only.
8. **The lookaround terminals (limit 3).** *Proposed (lead).* A2 reviews each of the 21 terminals of `UNCHECKED_TERMINALS` (`tests/architecture/test_contracts.py`) by hand: what it matches, which terminals can be candidates in the same parser states, and why they cannot collide. The table goes in each dialect's grammar README beside the list, and the test's comment points to it. A terminal is rewritten only if the review finds a real collision or a simpler form with no lookaround (with a test). Limit 3 then closes as "reviewed in M18; the test keeps the list from growing silently".
9. **Real circuits per device group.** *Proposed, for the maintainer at G1.* A3 lists each device group of plan section 5 with its accept files by origin (the maintainer's schematics or KiCad exports, or written here). A group with no file of the maintainer's is a `gap`; for each, the maintainer either supplies a circuit (a checklist as in M17 section 3.2) or accepts the files written here, as for M17's ngspice netlists.

## 3. Starting point (2026-11-10, `6843d4c`, `m17-special-devices`)

M17's pull request [#17](https://github.com/xdylanm/netlistmod/pull/17) is approved and still open; `main` is at `13ebefb`. M18 works on the branch `m18-completeness-audit`, cut from `6843d4c`, so its pull request is based on M17's branch until #17 is merged, and is rebased onto `main` then.

### 3.1 Inventory

- **Device matrices:** no letter is `planned` in either matrix, and `test_no_device_letter_is_planned` checks it (M17 T3).
- **Spec entries:** 151 in all. ngspice: 72 `validated`, 3 `observed` (`NG-COM-001`, `NG-NUM-004`, `NG-TXT-001`). LTspice: 73 `validated`. No entry is `documented`, so the second half of the plan's exit holds today; A4 confirms it, and that no entry should be `documented` instead.
- **Value specifications:** `NG-NUM-001` to `004`, `LT-NUM-001` to `004`, `NG-VAL-001`/`LT-VAL-001`, and `docs/grammars/<dialect>/numbers.md`. LTspice's comma forms: `discrepancies.md` rows for `.step`/`.dc`/`.ac list`, `tc=`, `m=2, temp=3`, `AC 1, 2`, `.subckt s a,b`, E/F node commas, T and A/`@` parameters; the closing note lists the comma forms that run ("`tc` values (documented) and, observed, `.model` and `X` parameters, `.param` assignments, `.options` items and `.save` vectors").
- **`UnsupportedConstruct` paths in `src/`:**
  - `grammar/loader.py` (`planned` letters; reached only with a mocked matrix, decision 6);
  - `model/_rules_lines.py` (the ngspice digital U, a v1 exclusion);
  - `model/_rules_structure.py` (LTspice `.machine`, a v1 exclusion).
  - **Stale, for A2:** `parse()`'s docstring in `model/transform.py` still says that stimulus functions, `DISTOF` and `q=` raise it; `core.lark` and `ngspice.lark` have comments about forms "reported as unsupported".
- **Lookaround terminals:** 10 ngspice and 11 LTspice in `UNCHECKED_TERMINALS`, unchanged since M16 (M17 added none).
- **Oracles and properties:**
  - `tests/grammar/ngspice/test_element_oracle.py` generates only R, C, L, K, V, I, D and X, on ngspice only.
  - `tests/grammar/test_broad_oracle.py` covers formatting, comments, endings and blocks on both dialects, with phase 1 lines.
  - Edit properties: `test_edit_properties.py` (phase 1 circuits), `test_transistor_edit_properties.py` (M13), and per-milestone properties in the controlled, behavioural, nonlinear, line and special edit tests.
- **Corpus:** 16 ngspice and 15 LTspice families. The maintainer's circuits are in `kicad_basic`, `kicad_extended`, `kicad_transistors`, both `controlled_sources`, both `transmission_lines`, `contributed_examples`, `ltspice_transistors` and `special_functions`; `code_models` and `osdi_devices` are written here (provenance confirmed by the maintainer, M17).

### 3.2 Baseline run

Full local run on `m18-completeness-audit` at `6843d4c` with `--require-solver ngspice --require-solver ltspice`: *running; recorded here when it ends.*

### 3.3 Carried items

| # | From | Item | Subtask |
|---|---|---|---|
| C1 | M15b 6.3 | Own messages for refusals that give the generic list: ngspice POLY pairs in parentheses, G's four-node TABLE, G's gate, `and (2)` | D1 |
| C2 | M15b 6.3 | LTspice `window=1m Laplace=…`: the message says "`window` is not a gain"; name `Laplace=` instead | D1 |
| C3 | M15b 6.3 | A braced value refused in an ngspice TABLE point is quoted without its braces; quote `value.span`'s text | D1 |
| C4 | M15b 6.3 | The generic list shows the raw `GAIN_KW`; give it a readable name in `grammar/loader.py` | D1 |
| C5 | M16 6.3 | Own messages for `m=` on Y and P, and for ngspice T's `IC=0 0 0 0` | D1 |
| C6 | M17 6.3 | Own message for an odd count in a differential vector (`%vd [in 0 out]`) | D1 |
| C7 | M16 6.3 | LTspice `+` line that holds only a comment: loads, LTspice stops | D2 (decision 5) |
| C8 | M17 6.3 | `zm` with an `&` probe: loads, LTspice stops | D2 (decision 5) |
| C9 | M17 6.3 | `@` under `.fra` without `fstart=`/`fend=` or `flist=`: not checked | D2 (decision 5) |
| C10 | M17 6.3 | LTspice `.model x BUF(…)`: loads, LTspice stops | D2 (decision 5) |

## 4. Tasks

Each subtask names its role, the files it may change, and what it reports. `[x]` is done and committed, `[~]` is in progress, `[ ]` is not started.

### Stage 0 — Set-up (lead)

[~] **T0 — Task list and baseline.**
- Write this list, cut the branch, run the baseline (3.2).
- Commit the list.

### Stage 1 — Audits (independent reviewers, in parallel; read-only)

[ ] **A1 — Value specifications (§6.4).** *Reviewer.*
- **ngspice:** the manual's numeric forms and scale-factor table (§2.1.3, and every other section that defines a value form: units after numbers, `meg`/`mil`, exponents, signs, leading `.`, `µ`, braces and quotes, RKM under the option) against `core.lark`/`ngspice.lark`, `NG-NUM-*`, `NG-VAL-001` and `numbers.md`. For each form: accepted, refused with a `discrepancies.md` row, or missing.
- **LTspice:** the same against the reference's number and value text, `LT-NUM-*`, `LT-VAL-001` and `numbers.md`.
- **Value slots:** check that each element's value slot of phase 2 (Q to `&`, the `.model` values of M16 and M17) reads the same number forms as R, or says where and why it differs.
- **Comma lists:** every row of LTspice's `discrepancies.md` with a comma, and its closing comma note: is each form the reference documents accepted, each form it does not refused with a row, and the note still true after M14 to M17?
- **Report:** decision 3's table, with a probe (scratch, outside the repository) for any form whose reading is not already pinned by a test.

[ ] **A2 — Architecture and rejection paths.** *Reviewer.*
- Confirm that no matrix entry or JSON file is `planned`, and that `test_no_device_letter_is_planned` would fail if one were.
- List every place in `src/` that raises, or documents raising, `UnsupportedConstruct`, with its reason; mark each `justified` (a v1 exclusion or decision 6) or `stale`.
- **Lookaround review (decision 8):** for each terminal of `UNCHECKED_TERMINALS`, its pattern, the parser states where it is a candidate, the terminals it competes with there, and why they cannot match the same text; flag any that could. Draft the README table.
- Read the grammar comments, the `parse()` and loader docstrings and `docs/usage/errors.md` for text that M12 to M17 made stale.
- **Report:** decision 3's table and the draft lookaround table.

[ ] **A3 — Corpus, oracle and edit properties.** *Reviewer.*
- **Corpus:** for each device group of plan section 5 and each dialect, the accept files that hold it, by origin, and whether each has a manifest entry with author, licence, origin and hash, and runs in its solver sweep. Mark groups with no file of the maintainer's (decision 9).
- **Oracle:** which phase 2 letters and forms `test_element_oracle.py` and `test_broad_oracle.py` generate (today: none), and a proposed design for extending them to every phase 2 letter on both dialects, keeping the oracle independent of the parser (expected values from the generator's record only).
- **Edit properties:** for each edit operation added in M12 to M17, whether a Hypothesis property shows that it preserves the signature, is idempotent, and changes no text outside its span; list the gaps.
- **Report:** decision 3's table and the oracle design, sized for D3.

[ ] **A4 — Spec coverage and statuses.** *Reviewer.*
- Run `tests/architecture/test_spec_coverage.py` and read what it checks against §10.4 and §11.2: every `supported` construct has an accept test; each status has its evidence.
- Check that every grammar rule added in M12 to M17 is traced to a spec entry, and that each spec entry's tests exist and test the construct (sample at least one entry per milestone by reading its tests).
- The three `observed` ngspice entries: is the manual still silent on each? Is any `validated` entry really `observed` or `documented`?
- Is there a **spec-coverage report** a reader can see (plan exit), or only a test? Propose the smallest form that meets the exit (for example a generated table in each dialect's grammar README, checked by a test).
- **Report:** decision 3's table.

[ ] **G1 — Audit review (lead).** Check every `gap` by reproduction and a sample of `ok` rows; classify each finding in section 5.1; add decisions to section 2; size D3 to D6; brief the maintainer on the decisions marked *for the maintainer*. Commit section 5.1 and the decisions.

### Stage 2 — Development (independent developers; after G1)

[ ] **D1 — Carried messages (C1 to C6).** *Developer.* No change in what loads: every form here stays refused, with its own message instead of the generic list.
- **Files:** `grammar/loader.py`, the `model/_rules_*.py` that refuse each form, the grammar tests of each, `docs/usage/errors.md` if a message is quoted there.
- **Tests:** each form's message and column, in both dialects where it applies; the tree snapshot unchanged.

[ ] **D2 — LTspice forms that load and that LTspice stops on (C7 to C10; decision 5).** *Developer; after D1 and the maintainer's decision 5.*
- Probe each form on LTspice 26.1.1 first (the `.model x BUF(…)` line on its own, and used by an A line), as solver probe tests.
- Make each change as decided; new diagnostic codes go in `document/diagnostics.py`, §17 and `docs/usage/errors.md`, with decision 0021.
- **Tests:** a probe test per form (the line, whether LTspice runs it, the library's reading), grammar or diagnostic tests, and an `elements_rejects` or `statements_rejects` file for each refusal.

[ ] **D3 — Oracle and edit properties for phase 2 elements.** *Developer; may run alongside D1 or D2 (tests only).* From A3's design:
- extend the independent element oracle to every phase 2 letter, on both dialects;
- add the missing edit properties of A3's list.
- **Files:** `tests/grammar/` and `tests/edits/` only. A failure that shows a library defect is reported, not worked around.

[ ] **D4 — Corpus gaps.** *Developer, and the maintainer where decision 9 asks for a circuit.* Add the files A3 found missing, with manifest entries and hashes; each runs in its sweep. *If A3 finds no gap, this subtask is closed with that note.*

[ ] **D5 — Value-specification gaps.** *Developer; after D2.* The grammar changes A1 found and G1 accepted, each with a spec-entry update, accept and reject tests, and a `discrepancies.md` row where the solver differs. *If A1 finds no gap, closed with that note.*

[ ] **D6 — Architecture, coverage report and stale text.** *Developer; disjoint from D1/D2/D5 unless G1 says otherwise.*
- The lookaround tables in the grammar READMEs and the test comment (decision 8).
- The `UnsupportedConstruct` docstrings and comments A2 marked `stale`.
- The spec-coverage report of A4's proposal, with its test.
- The other `stale` rows of A2 and A4.

### Stage 3 — Evidence and handover (lead)

[ ] **T1 — Final evidence and handover.**
- Accept decision 0021 as written (`proposed`) if G1 created it, and update the architecture where it amends it.
- Run the full local check set with `--require-solver ngspice --require-solver ltspice`, `ruff check`, `ruff format --check`, `mypy --strict`, `lint-imports` and `pre-commit run --all-files`.
- Open the pull request, read CI once, record both in section 5.2, list the design points worth reviewing, and set the status to `READY FOR REVIEW`.

### After the maintainer's approval

[ ] **T2 — Close M18.** Archive this list, accept decision 0021 if there is one, and update the plan (status and M18 heading) and the index.

## 5. Results

### 5.1 Audit findings (G1)

*Filled at G1.*

### 5.2 Evidence

*Filled in T1.*

### 5.3 Subtask log

| Subtask | Role | Reported | Lead's review | Commit |
|---|---|---|---|---|
| T0 | lead | — | — | — |
