# M18 task list — Completeness audit

> **Status:** ACTIVE — stage 1 and gate G1 are done (2026-11-10). Stage 2 has started with D1, D3 and D6. The maintainer decided 5, 10, 12 and 13 on 2026-11-10, and 11 on 2026-11-11
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
5. **Carried LTspice forms that load and that LTspice stops on** (M16 6.3, M17 6.3). **Decided (maintainer, 2026-11-10): as recommended.** The library's rule so far: a form that the library reads correctly and the solver stops on may load when it cannot misread a line (M17 decisions 4 and 7). The four carried items differ:

   | Form | Library today | LTspice 26.1.1 | Proposed |
   |---|---|---|---|
   | a `+` line that holds only a comment | loads | stops | **refuse** (`ParseError`): it is a line shape the grammar can see, and P5 asks for it |
   | `.model x BUF(…)` (a special-function type) | loads | stops ("Expected model definition" when used) | **refuse** the type in the LTspice `.model` rule if A1 or D2's probe shows LTspice stops on the `.model` line itself; otherwise a warning when an A line uses it |
   | `@ … zm` with an `&` probe for it | loads | stops ("FRA Probe not supported … impedance measurement mode") | **diagnostic** (warning) on the probe: it spans two lines, so it is not a grammar check |
   | `@` under `.fra` with neither `fstart=`/`fend=` nor `flist=` | loads | stops ("Missing parameter") | **diagnostic** (warning) on the `@` line, only when the netlist has a `.fra` command |

   New diagnostic codes change §17, so decision 7 records them. *Considered:* leaving all four as `discrepancies.md` rows.
6. **The planned-letter path in the loader.** *Proposed (lead).* Keep it, with its mocked-matrix tests (M17 decision 10): §6.7 still defines the `planned` status, and a later dialect (qspice, xyce; §9.2) will use it. A2 lists it as a justified path. *Considered:* removing it as dead code in v1.
7. **A decision record for M18.** **Decided:** G1 found normative changes, and the maintainer's decisions 5, 10 and 12 make them (decision 15). One record, `0021-completeness-audit.md`, written at gate G1 and `proposed` until M18 closes. It records decision 5's outcome and any new diagnostic codes (§17), the lookaround review (decision 8), and any other normative change G1 accepts. If G1 accepts no normative change, M18 needs no record, and the lookaround review is recorded in the grammar READMEs only.
8. **The lookaround terminals (limit 3).** *Proposed (lead).* A2 reviews each of the 21 terminals of `UNCHECKED_TERMINALS` (`tests/architecture/test_contracts.py`) by hand: what it matches, which terminals can be candidates in the same parser states, and why they cannot collide. The table goes in each dialect's grammar README beside the list, and the test's comment points to it. A terminal is rewritten only if the review finds a real collision or a simpler form with no lookaround (with a test). Limit 3 then closes as "reviewed in M18; the test keeps the list from growing silently".
9. **Real circuits per device group.** *Superseded by decision 13 at G1.* A3 lists each device group of plan section 5 with its accept files by origin (the maintainer's schematics or KiCad exports, or written here). A group with no file of the maintainer's is a `gap`; for each, the maintainer either supplies a circuit (a checklist as in M17 section 3.2) or accepts the files written here, as for M17's ngspice netlists.

10. **LTspice `.subckt` parameter commas** (A1-11). **Decided (maintainer, 2026-11-10): as recommended.** LTspice 26.1.1 runs `.subckt s p n r=1k, q=2` and `… params: r=1k, q=2`; the library refuses the comma, though it accepts `X1 … p=1, q=2` (an `observed` form). **Recommended: accept the comma between `.subckt` parameters, as on X,** with the probe as a test and `LT-SUB-001` noting the observed form, so both sides of a call read alike. *Alternative:* keep the refusal and add a `discrepancies.md` row.
11. **NG-COM-001's status** (A4-9). **Decided (maintainer, 2026-11-11): as recommended** (D8). The manual documents both accepted forms (`*` in column 1, §2.4.3; leading blanks ignored, §2.1.1), so the entry is not `observed`. **Recommended: make it `validated`,** add the §2.1.1 citation, and add a grammar test and an ngspice probe of an indented `*` (D6). *Alternative:* keep `observed` and rewrite the note.
12. **A lone CR right before a CRLF** (A2-20). **Decided (maintainer, 2026-11-10): as recommended.** Rule 13 writes free text as `\r(?!\r?\n)`, so `* abc\r\r\n` is a `ParseError` on both dialects (reproduced), while decision 0001 says a lone CR is ordinary text and `SourceText` counts that line as holding one. **Recommended: `\r(?!\n)`,** which accepts it; the terminals stay on the lookaround list, and decision 0021 amends rule 13's wording. *Alternative:* keep it and document it as a limit.
13. **Corpus origin** (A3-3 to A3-6; refines decision 9). **Decided (maintainer, 2026-11-10): as recommended.** Groups with no circuit of the maintainer's:
    - ngspice: Z; B `i=`; the expression forms of E and G; C `q=`; every M15b form; T, U, Y and P; A and N;
    - LTspice: Z; B; the `value=` forms; C `Q=`; L `Flux=` and the hysteretic L; every M15b form.

    Most of these have variants of the maintainer's exports, or files written here, and all run in the sweeps. **Recommended: accept the files written here for these groups** (as M17 did for A and N), with D4 adding variants for the three forms no file holds (LTspice H `value=`, ngspice `nand`/`nor` and G's gates), and accept the stimulus forms at group level (A3-5). Per-file origin stays in the manifest notes (A3-3, a documented limit). *Alternative:* the maintainer supplies circuits for some groups (a checklist as in M17 section 3.2); Z and the M15b forms would be the most useful.
14. **Conventions recorded, no status change** (A4-3, A4-4, A4-12; A1-7). *Proposed (lead).* Decision 0021 states: a refusal entry (`NG-UNS-001`, `LT-UNS-001`, `LT-MCH-001`) is `validated` by probes of the forms it refuses; an LTspice entry may hold observed parts in its notes (decision 0009), while ngspice splits them into their own entry; the checker does not prove that a solver test runs (they skip in CI); and the library does not read `.options`, so LTspice's `reject_number_tails` is a `discrepancies.md` row and a `numbers.md` note, not a diagnostic.
15. **Decision 7 confirmed by G1.** G1 accepts normative changes (decisions 5, 10 and 12, and the fixes of section 5.1), so the recommendation of decision 7 stands: decision record 0021, `proposed` until M18 closes.

## 3. Starting point (2026-11-10, `6843d4c`, `m17-special-devices`)

M17's pull request [#17](https://github.com/xdylanm/netlistmod/pull/17) is approved and still open; `main` is at `13ebefb`. M18 works on the branch `m18-completeness-audit`, cut from `6843d4c`, so its pull request is based on M17's branch until #17 is merged, and is rebased onto `main` then.

### 3.1 Inventory

- **Device matrices:** no letter is `planned` in either matrix, and `test_no_device_letter_is_planned` checks it (M17 T3).
- **Spec entries:** 148 in all (corrected in A4). ngspice: 72 `validated`, 3 `observed` (`NG-COM-001`, `NG-NUM-004`, `NG-TXT-001`). LTspice: 73 `validated`. No entry is `documented`, so the second half of the plan's exit holds today; A4 confirms it, and that no entry should be `documented` instead.
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

Full local run on `m18-completeness-audit` at `8f8c098` (the tree of `6843d4c` plus this list) with `--require-solver ngspice --require-solver ltspice`: 9,458 passed, 2 failed, 2 skipped, 1,203 deselected, coverage 98.61%, in 26 min 17 s. The two failures were LTspice corpus runs (`test_accept_fixture_runs_in_ltspice[special_functions/test_ltspice_fra_named.cir]` and `test_unedited_round_trip_gives_identical_results[ltspice_transistors/edges.net]`), while the stage 1 reviewers ran LTspice probes at the same time; both pass when rerun on their own (2 passed, 18 s). They are treated as host noise from the parallel solver runs, and T1's final run is made with no other solver work going on.

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

[x] **T0 — Task list and baseline.**
- Write this list, cut the branch, run the baseline (3.2).
- Commit the list.

### Stage 1 — Audits (independent reviewers, in parallel; read-only)

[x] **A1 — Value specifications (§6.4).** *Reviewer.* Reported 2026-11-10; reviewed at G1 (section 5.1).
- **ngspice:** the manual's numeric forms and scale-factor table (§2.1.3, and every other section that defines a value form: units after numbers, `meg`/`mil`, exponents, signs, leading `.`, `µ`, braces and quotes, RKM under the option) against `core.lark`/`ngspice.lark`, `NG-NUM-*`, `NG-VAL-001` and `numbers.md`. For each form: accepted, refused with a `discrepancies.md` row, or missing.
- **LTspice:** the same against the reference's number and value text, `LT-NUM-*`, `LT-VAL-001` and `numbers.md`.
- **Value slots:** check that each element's value slot of phase 2 (Q to `&`, the `.model` values of M16 and M17) reads the same number forms as R, or says where and why it differs.
- **Comma lists:** every row of LTspice's `discrepancies.md` with a comma, and its closing comma note: is each form the reference documents accepted, each form it does not refused with a row, and the note still true after M14 to M17?
- **Report:** decision 3's table, with a probe (scratch, outside the repository) for any form whose reading is not already pinned by a test.

[x] **A2 — Architecture and rejection paths.** *Reviewer.* Reported 2026-11-10; reviewed at G1 (section 5.1).
- Confirm that no matrix entry or JSON file is `planned`, and that `test_no_device_letter_is_planned` would fail if one were.
- List every place in `src/` that raises, or documents raising, `UnsupportedConstruct`, with its reason; mark each `justified` (a v1 exclusion or decision 6) or `stale`.
- **Lookaround review (decision 8):** for each terminal of `UNCHECKED_TERMINALS`, its pattern, the parser states where it is a candidate, the terminals it competes with there, and why they cannot match the same text; flag any that could. Draft the README table.
- Read the grammar comments, the `parse()` and loader docstrings and `docs/usage/errors.md` for text that M12 to M17 made stale.
- **Report:** decision 3's table and the draft lookaround table.

[x] **A3 — Corpus, oracle and edit properties.** *Reviewer.* Reported 2026-11-10; reviewed at G1 (section 5.1).
- **Corpus:** for each device group of plan section 5 and each dialect, the accept files that hold it, by origin, and whether each has a manifest entry with author, licence, origin and hash, and runs in its solver sweep. Mark groups with no file of the maintainer's (decision 9).
- **Oracle:** which phase 2 letters and forms `test_element_oracle.py` and `test_broad_oracle.py` generate (today: none), and a proposed design for extending them to every phase 2 letter on both dialects, keeping the oracle independent of the parser (expected values from the generator's record only).
- **Edit properties:** for each edit operation added in M12 to M17, whether a Hypothesis property shows that it preserves the signature, is idempotent, and changes no text outside its span; list the gaps.
- **Report:** decision 3's table and the oracle design, sized for D3.

[x] **A4 — Spec coverage and statuses.** *Reviewer.* Reported 2026-11-10; reviewed at G1 (section 5.1).
- Run `tests/architecture/test_spec_coverage.py` and read what it checks against §10.4 and §11.2: every `supported` construct has an accept test; each status has its evidence.
- Check that every grammar rule added in M12 to M17 is traced to a spec entry, and that each spec entry's tests exist and test the construct (sample at least one entry per milestone by reading its tests).
- The three `observed` ngspice entries: is the manual still silent on each? Is any `validated` entry really `observed` or `documented`?
- Is there a **spec-coverage report** a reader can see (plan exit), or only a test? Propose the smallest form that meets the exit (for example a generated table in each dialect's grammar README, checked by a test).
- **Report:** decision 3's table.

[x] **G1 — Audit review (lead).** Done 2026-11-10: section 5.1, decisions 10 to 15, and stage 2 as below. Check every `gap` by reproduction and a sample of `ok` rows; classify each finding in section 5.1; add decisions to section 2; size D3 to D6; brief the maintainer on the decisions marked *for the maintainer*. Commit section 5.1 and the decisions.

### Stage 2 — Development (independent developers; after G1)

Revised at G1. **Order:** D1, D3 and D6 start at once, with disjoint files. D5 follows D1 and D6, since it touches the grammar after D1 and the spec entries and `discrepancies.md` after D6. D2 follows D5 and decision 5. D4 follows decision 13. The finding ids (A1-4 and so on) are section 5.1's.

[x] **D1 — Messages and stale source text (C1 to C6; A3-16; A2-3, A2-7 to A2-11).** *Developer.* Accepted 2026-11-10 (`15be89e`). No change in what loads: every form of C1 to C6 stays refused, with its own message instead of the generic list.
- **Files:** `src/netlistmod/grammar/loader.py`, the `model/_rules_*.py` that refuse each form, `edit/_ops_sources.py` (the A3-16 typo), the comments of `core.lark`, `ngspice.lark` and `ltspice.lark` (comments only), the docstrings of `model/transform.py` and `errors.py`; the grammar and edit tests of each; `docs/usage/errors.md` where it quotes a message.
- **Tests:** each form's message and column, in both dialects where it applies; the tree snapshot unchanged (or each changed entry listed).

[x] **D2 — LTspice forms that load and that LTspice stops on (C7 to C10; decision 5).** *Developer; after D5 and the maintainer's decision 5.* Accepted 2026-11-11 after one round (`afece61`).
- Probe each form on LTspice 26.1.1 first (the `.model x BUF(…)` line on its own, and used by an A line), as solver probe tests.
- **Also (G2 of D5, decision 5's rule):** `.subckt s p n params:, r=1k` loads and LTspice stops on it ("Expected end of line here"); it is a line shape, so it is refused like the `+` comment-only line, and its `discrepancies.md` row changes to say so.
- Make each change as decided; new diagnostic codes go in `document/diagnostics.py`, §17 and `docs/usage/errors.md`, with decision 0021.
- **Tests:** a probe test per form (the line, whether LTspice runs it, the library's reading), grammar or diagnostic tests, and an `elements_rejects` or `statements_rejects` file for each refusal.

[x] **D3 — Oracle and edit properties for phase 2 elements (A3-7 to A3-15, A4-8).** *Developer; tests only.* Accepted 2026-11-11 (`aba1d5e`); its finding D3-1 is D7. From A3's design:
- a new `tests/grammar/test_device_oracle.py`: every phase 2 letter and form on both dialects; expected spans, structure and signature entries from the generator's record only; and the mutation check (changing any topology token changes the signature);
- a new `tests/edits/test_device_edit_properties.py`: (a) the signature is kept, (b) idempotence (for a removal: the second call raises `EditError` and writes nothing), (c) the change lies inside the target item or its `.model`, over every operation of A3's matrix;
- the two properties that `continue` on `EditError` assert that a step applied (A3-14); `test_ngspice_accepts` checks the stimulus kind (A4-8);
- `docs/design/edit-layer.md`: one sentence on what idempotence means for a removal (A3-15).
- **Files:** those above only. A failure that shows a library defect is reported with a reproduction, not worked around.

[x] **D4 — Corpus gaps (A3-6; decision 13).** *Developer; after decision 13.* Accepted 2026-11-11 (`414f016`). Variants holding LTspice H `value=`, ngspice `nand`/`nor` and G's gates, with manifest entries and hashes, each in its sweep; and any circuits the maintainer supplies.

[x] **D5 — Value and grammar fixes (A1-2, A1-4, A1-6 to A1-8, A1-11 to A1-14, A2-19, A2-20).** *Developer; after D1 and D6.* Accepted 2026-11-11 (`50deb0f`).
- **A1-4, first (a topology misread):** a number with a non-ASCII letter (`1μ`, `2Ω`) after a transistor's model must never be read as the model. LTspice: `FIELD_NUMBER` takes the letters its `NUMBER` takes, so Q/J/Z areas and POLY coefficients with `μ` and `Ω` load as LTspice reads them. ngspice: probe how ngspice 47 reads `Q1 c b 0 qm 1μ` first, then read it the same way or refuse it at the token. Accept and reject tests, and solver probes on both dialects.
- **A2-19:** a nested `.if` block in its own rule, so that the line after an inner `.endif` parses (ngspice runs it); a corpus line; and an architecture test that no lexer state offers both a block-only terminal and a statement-start terminal.
- **A2-20:** the lone CR, as decision 12 decides. **A1-11:** `.subckt` parameter commas, as decision 10 decides.
- **Rows and wording:** the ngspice `discrepancies.md` rows of A1-2 (`1d3`, `1meg5`, `1μ`, `1kΩ`, `1_000`, `(1k)` and the others, pinned by solver probes); LTspice rows for A1-6 (`a`), A1-7 (`reject_number_tails`) and A1-8 (`1d3`, `1_000`); the closing comma note and `LT-FLD-001` (A1-12); LTspice `numbers.md` (A1-13); `NG-FLD-001` (A1-14).

[x] **D6 — Architecture, coverage report and stale docs (A2-12 to A2-18; A4-2, A4-5, A4-6, A4-9, A4-14, A4-15).** *Developer.* Accepted 2026-11-10 (`33a2b59`), except NG-COM-001 (decision 11, open) and the optional Spec column of `devices.md` (not cheap: it needs a new matrix check; left out).
- **Lookaround (decision 8):** A2's two tables in the grammar READMEs, noting that the merged states after a nested `.endif` are fixed by D5 (A2-19); the comment of `UNCHECKED_TERMINALS` points to them.
- **Spec checker (A4-2):** match `def <name>(` rather than a substring, and require a non-solver accept test for each entry except the refusal entries.
- **Coverage report (A4-14):** a Tests column (non-solver and solver counts) and a totals line in each README's "Validation status" table, checked by `check_status_summary`; `tests/support/spec_coverage.py` becomes the generator of those rows or is removed.
- **Statuses (A4-5, A4-6):** append `validated_on` to the five stale entries, citing their tests; an LTspice solver test of `~`, cited by `LT-FML-001`. NG-COM-001 as decision 11 decides (after it).
- **Stale docs:** `docs/usage/elements.md`, `docs/usage/structural-parse.md` and README line 60 (A2-13 to A2-15); NG-UNS-001's name (A2-17); an optional Spec column in `devices.md` (A4-15).
- **Files:** `docs/grammars/*/README.md`, `docs/grammars/*/devices.md`, the spec entries named, `docs/usage/` except `errors.md`, `README.md`, `tests/architecture/`, `tests/support/spec_coverage.py`, and one new LTspice solver test file.

[x] **D7 — A new parameter on an LTspice B line with `laplace=` (D3-1).** *Developer; after D5.* Accepted 2026-11-11 (`24f9788`). `set_param("B1", "ic", "1")` on `B1 o 0 V=2*V(vs) laplace=1/(1+s/1k)` writes `ic=1` after `laplace=…`, which the library refuses (it follows the reference's order, M15b), so the edit fails verification and writes nothing. A new parameter that is not `window=`, `nfft=` or `mtol=` goes before `laplace=`, as on E and G if they have the same gap. Probe whether LTspice runs `laplace=… ic=1` for the record. Golden diff, and D3's exclusion (`test_device_edit_properties.py`) removed.

[x] **D8 — NG-COM-001 `validated` (decision 11).** *Developer.* Accepted 2026-11-11. An indented `*` line as a grammar test and an ngspice 47 probe; the entry cites §2.4.3 and §2.1.1; the README table is regenerated.

### Stage 3 — Evidence and handover (lead)

[~] **T1 — Final evidence and handover.**
- Accept decision 0021 as written (`proposed`) if G1 created it, and update the architecture where it amends it.
- Run the full local check set with `--require-solver ngspice --require-solver ltspice`, `ruff check`, `ruff format --check`, `mypy --strict`, `lint-imports` and `pre-commit run --all-files`.
- Open the pull request, read CI once, record both in section 5.2, list the design points worth reviewing, and set the status to `READY FOR REVIEW`.

### After the maintainer's approval

[ ] **T2 — Close M18.** Archive this list, accept decision 0021 if there is one, and update the plan (status and M18 heading) and the index.

## 5. Results

### 5.1 Audit findings (G1)

Reviewed 2026-11-10. Every `gap` that changes behaviour was reproduced by the lead:
- A1-4 on both dialects: `Q1 c b 0 qm 1μ` and `… 2Ω` load with nodes `c b 0 qm` and model `1μ`; `M1 d g s mm 1μ` the same; `J1 … 2μ` fails with an empty message;
- A2-19: `.if (1)` / `.if (2)` / `.endif` / `R1 a b 1` / `.endif` is a `ParseError` at line 5 on ngspice; the same with `.else` loads;
- A2-20: `* abc\r\r\n` is a `ParseError` on both dialects;
- A3-14 and A3-16 by reading the code.

The two baseline failures (3.2) are host noise. The reviewers' scripts are in the session's scratch folder, outside the repository.

**Summary:** no device letter is `planned`; every remaining `UnsupportedConstruct` path is justified; no spec entry is `documented`, and none should be; all 402 grammar rules of M12 to M17 trace to spec entries, and every cited test exists; 20 of the 21 lookaround terminals are reviewed clean, and the review of the 21st found A2-19. Two defects in the library: A1-4 (a topology misread) and A2-19 (a valid netlist refused). The rest are test gaps, records and wording.

**A1 — Value specifications**

| # | Finding | Class | Subtask |
|---|---|---|---|
| A1-1, 3, 5, 9, 10, 15 | ngspice and LTspice number forms, every phase 2 value slot, every documented comma form and the comma rows: as the manual and the reference say, or refused with a row | ok | — |
| A1-2 | ngspice runs forms the library refuses, with no row: `1d3` (read as 1000), `1d-3` (−3), `1meg5`, `2.2k7`, `1μ` (read as 1, not micro), `1kΩ`, `1_000`, `0x10`, `1.5.3`, `1e+`, `(1k)`. Refusing is right (some would be misreads) | gap (records) | D5 |
| **A1-4** | **LTspice positional numbers (`FIELD_NUMBER`) lack the non-ASCII letters of `NUMBER`: `Q1 c b 0 qm 1μ` loads with `qm` as a node and model `1μ`, where LTspice reads an area of 1e-6. Also M; J and Z fail with an empty message; POLY coefficients with `μ` are refused. ngspice Q and M lines load the same way** | **gap (defect, P4)** | **D5, first** |
| A1-6 | The LTspice reference contradicts itself on `a` (atto); LTspice reads `1a` as 1 | gap (record) | D5 |
| A1-7 | `.options reject_number_tails` is not read | question → limit (decision 14) | D5 |
| A1-8 | LTspice `1d3`, `1_000` are not in the trailing-letters row | gap (record) | D5 |
| A1-11 | LTspice runs `.subckt` parameter commas; the library refuses them, with no row | question | decision 10, D5 |
| A1-12 to 14 | The closing comma note and `LT-FLD-001` omit the M12 to M17 forms; LTspice `numbers.md` on bare expressions; `NG-FLD-001`'s "phase 2" remark | stale | D5 |
| A1-16 | ngspice Greek `μ` gets the generic message | question → limit (A1-2's row) | D5 |

**A2 — Architecture and rejection paths**

| # | Finding | Class | Subtask |
|---|---|---|---|
| A2-1, 2 | No matrix entry is `planned`; the test fails on a patched matrix | ok | — |
| A2-3 to 6 | `UnsupportedConstruct` paths: the planned-letter path (decision 6), the digital U and `.machine` (v1 exclusions); the other places only catch it | ok (justified) | D1 (an optional docstring note) |
| A2-7 to 11 | `parse()` docstring, `core.lark` and `ngspice.lark` comments, `ltspice.lark`'s bare "decision 5", `errors.py` docstring | stale | D1 |
| A2-12 | §17 and §6.7 do not name the v1 exclusions | question | 0021 amends them (T1) |
| A2-13 to 15 | `docs/usage/elements.md`, `structural-parse.md`, README line 60 | stale | D6 (README line 64 is M19's) |
| A2-17 | NG-UNS-001's name | stale | D6 |
| A2-18, 21 | Lookaround review: 20 of 21 terminals clean; none can lose its lookaround simply | ok | D6 (the tables) |
| **A2-19** | **ngspice nested `.if`: after an inner `.endif`, LALR-merged states let `DOT_NAME`, names and `COMMENT_LINE` beat `BLOCK_TEXT`, so any line but `.else` is a `ParseError`; ngspice 47 runs it. A separate nested rule fixes it and builds in strict mode** | **gap (defect)** | **D5** |
| A2-20 | A lone CR before a CRLF is refused, against decision 0001 | question | decision 12, D5 |

**A3 — Corpus, oracle and edit properties**

| # | Finding | Class | Subtask |
|---|---|---|---|
| A3-1, 2, 9, 17 | Manifests and sweeps complete (the run needs `OPENJELLYBEAN_LIB`); about 70 phase 2 operations keep the signature, are idempotent and stay inside their element | ok | — |
| A3-3 to 6 | Per-file origin only in notes; groups with no file of the maintainer's; stimulus forms; three forms in no accept file | question / gap | decision 13, D4 |
| A3-7, 8 | Neither oracle generates a phase 2 letter | gap | D3 |
| A3-10 | The "any topology token changes the signature" property covers only R, C, L and V | gap | D3 (in the oracle file) |
| A3-11 to 13 | Idempotence and "no text outside the span" are missing for most phase 2 operations; letters and forms are missing from the properties (A3's matrix, carried into D3's brief) | gap | D3 |
| A3-14 | Two properties `continue` on `EditError` and can pass with no step applied | gap | D3 |
| A3-15 | What idempotence means for a removal is not stated | question → D3 states it | D3 |
| A3-16 | Message typo: "has no a source function" | stale | D1 |

**A4 — Spec coverage and statuses**

| # | Finding | Class | Subtask |
|---|---|---|---|
| A4-1, 7, 8, 10, 11, 13 | The checker runs in CI; rules traced; 14 sampled entries test their construct; NG-NUM-004 and NG-TXT-001 stay `observed`; no `documented` entry | ok | — |
| A4-2 | The checker matches a test name as a substring and does not require an accept test | gap (checker) | D6 |
| A4-3, 4, 12 | Refusal entries graded `validated`; what the checker cannot prove; LTspice entries with observed parts | question → conventions (decision 14) | 0021 |
| A4-5 | Five entries' `validated_on` predate rules added to them (LT-SRC, NG-SRC, NG-FML, LT-FML, LT-UNS) | stale | D6 |
| A4-6 | LTspice `~` has no solver test (a probe agrees with the library) | gap | D6 |
| A4-9 | NG-COM-001 is not really `observed` | question | decision 11, D6 |
| A4-14 | No coverage report a reader can see shows each construct's tests | gap | D6 |
| A4-15 | No test ties a device letter to its spec entry | ok (optional) | D6 |
| A4-16 | This list's count of spec entries | stale | fixed (148) |

### 5.2 Evidence

*Filled in T1.*

### 5.3 Subtask log

| Subtask | Role | Reported | Lead's review | Commit |
|---|---|---|---|---|
| T0 | lead | — | baseline recorded in 3.2 | `8f8c098`, this commit |
| A1 | reviewer | 2026-11-10 after a resume, complete with findings (16 rows) | reviewed at G1; A1-4 reproduced on both dialects | — |
| A2 | reviewer | 2026-11-10 after a resume, complete with findings (21 rows and the lookaround tables) | reviewed at G1; A2-19 and A2-20 reproduced | — |
| A3 | reviewer | 2026-11-10, complete with findings (17 rows) | reviewed at G1 | — |
| A4 | reviewer | 2026-11-10, complete with findings (16 rows) | reviewed at G1 | — |
| G1 | lead | — | section 5.1, decisions 10 to 15, stage 2 revised | this commit |
| D6 | developer | 2026-11-10, complete with findings | accepted: diff read; architecture, docs and usage-doc tests pass in a clean worktree of the commit (923 passed); CRLF working-copy endings normalised. Its findings F1 and F2 (a removed test cited by NG-CPL-001; `re` imported in the model layer) are D1's, sent back to it. Choices accepted: an accept test is a non-solver test whose name does not say it refuses; the refusal entries are constants in the checker; `26.1.1` as the version string | `33a2b59` |
| D1 | developer | 2026-11-10, complete with findings | accepted: diff read. C1, C5 and C6 are named by the loader after the parser stops (`_named_refusal`, beside the loader's existing own messages, reading its value stack), so no `.lark` rule or terminal changed; C2 and C3 stay in the rules. Five reject entries of the tree snapshot lose only their expected terminals. In a clean worktree of the commit: grammar, architecture, round-trip, document, edit and doc tests 6,789 passed; `ruff check`, `ruff format --check` and `mypy --strict src` clean. Noted: `window=` with no `Laplace=` gets the new message too; F/H POLY with a parenthesised source, POLY parentheses among the coefficients, and a value after a full `IC=` list keep the expected-token list | `15be89e` |
| D3 | developer | 2026-11-10, complete with findings | accepted: diff read; in a clean worktree of the commit, `tests/grammar`, `tests/edits`, `tests/architecture` and the doc tests with the CI profile: 5,339 passed; `ruff check tests` clean. 44 ngspice and 29 LTspice forms; every operation of A3's matrix now has (a), (b) and (c). Shapes the library refuses are not generated, nor `μ`/`Ω` after a model (A1-4) or nested `.if` (A2-19): D5 may add them. Finding D3-1 became D7 | `aba1d5e` |
| D4 | developer | 2026-11-11 after a resume, complete | accepted: three variants (`lt_test_hsource_value.cir`, `test_esource_nand.cir`, `test_esource_nor.cir`), each one change from a maintainer export, with hashes; their six solver cases pass (nand and nor 0 V where and and or give 2 V; H `value=` equals its base). G's gates are refused, and `g_and.cir` holds one. The lead regenerated the ngspice tree snapshot in a clean worktree: two entries added, none changed; snapshot, manifest, round-trip and LTspice grammar tests 1,943 passed | `414f016` |
| D5 | developer | 2026-11-11 after a resume, complete with findings | accepted: diff read. In a clean worktree of the commit, every solver-free test with the CI profile: 7,260 passed, 2 skipped; `ruff check`, `ruff format --check`, `mypy --strict src` and `lint-imports` clean. Its solver probes (53 new) and the swept families passed, one LTspice FRA case only on rerun (host noise). Parses changed only for lines that were misread or wrongly refused (A1-4 on both dialects, nested `.if`, a lone CR); no corpus file changed its parse, and the signature snapshot is unchanged. Decision 10 needed no grammar change: the comma already loaded through `x_param`. Its one new finding, `params:,`, goes to D2 under decision 5's rule. Its 0021 wording is taken into T1 | `50deb0f` |
| D7 | developer | 2026-11-11, complete | accepted: diff read (a new parameter goes after the last field before `laplace=`; E and G take only `window=`, `nfft=` and `mtol=`, so they have no gap). LTspice 26.1.1 runs both orders. In a clean worktree of the commit, the edit, architecture, round-trip, manifest and doc tests with the CI profile: 3,050 passed. Its new golden case runs in the LTspice sweep | `24f9788` |
| D2 | developer | 2026-11-11, complete with findings | **sent back (round 1):** C8, C9, C10 and `params:,` accepted as reported; R1, refuse C7 without the lookaheads it added to LTspice `CONT` and `SEP` (two core terminals out of strict checking, against decision 8); R2, a row and probe for `.subckt … , params:` (LTspice runs it). Its finding F1 (`remove_stimulus` can leave a comment-only `+` line) is D7b; F2 (unknown LTspice `.model` types load, LTspice stops) is a row and a design point for the maintainer | — |
| D2 R1 | developer | 2026-11-11 after a resume, complete | accepted: C7 is checked in the loader after the parse, from the physical lines; `UNCHECKED_TERMINALS` and the lookaround tables are as before; R2's row and probe added. At `afece61`, in a clean worktree, every solver-free test with the CI profile: 7,407 passed, 2 skipped; `ruff`, `ruff format` and `mypy --strict src` clean; its 95 probes and the LTspice reject sweep (184) passed | `afece61` |
| D7b | developer | 2026-11-11 after a resume, complete | accepted: four removal paths share `_removal_edit` (LTspice only; ngspice output unchanged), with tests for each and CRLF. At `7936120` alone the edit and architecture tests pass (2,415) | `7936120` |
| D8 | developer | 2026-11-11, complete | accepted: diff read; an indented and a tab-indented `*` line load as `CommentLine`, and ngspice 47 ignores both (a commented-out R3 leaves v(mid) at 1.0 V, 2/3 V when live). NG-COM-001 is `validated` (§2.4.3, §2.1.1); ngspice totals 73 validated, 2 observed. Architecture and doc tests pass in a clean worktree of the commit | this commit |
