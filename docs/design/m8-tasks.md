# M8 task list — LTspice overlay

> **Status:** READY (2026-11-01) — section 2 decisions accepted by the maintainer (2026-10-31); the maintainer's schematics for decision 14 are in `tests/corpus/ltspice/contributed_examples/` (2026-11-01).
> **Part of:** [phase-1-plan.md](./phase-1-plan.md) (milestone M8). Governed by [architecture.md](../architecture.md) (§2 P5, P7, P8, P10, P13; §4; §5.1; §6.1–§6.7; §9; §10; §11 (normative); §12; §21). Builds on the grammar of M2–M4 (`core.lark`, `ngspice.lark`), the document layer of M5 ([m5-document.md](./m5-document.md)), the edit layer of M6 ([m6-edits.md](./m6-edits.md)), the validation layer of M7 ([decision 0008](../decisions/0008-validation-status-and-solver-harnesses.md)), the LTspice spikes of M0/M1 ([ltspice-export.md](../usage/ltspice-export.md)) and [decision 0001](../decisions/0001-source-text-policy.md) (encoding).

## 1. Scope

M8 makes `Dialect.LTSPICE` a working dialect for the phase 1 constructs, with the same guarantees as ngspice:

- **Grammar:** `ltspice.lark` is an overlay on `core.lark`. Constructs that only ngspice has move out of `core.lark` into `ngspice.lark`, and ngspice behaviour stays byte-for-byte the same. Both grammars compile under `strict=True`.
- **Documents per §9.3:** `docs/grammars/ltspice/` gets `devices.md` (with `ltspice-devices.json`), `names.md`, `scoping.md`, `numbers.md`, `discrepancies.md`, a README status table, and one `LT-*` spec entry per construct, each with tests.
- **Layers:** the document layer (names, scopes, diagnostics) and the edit layer work for LTspice netlists. Name rules are dialect-aware.
- **Fixtures:** LTspice exports of schematics authored in this repository, plus hand-written LTspice families, each with a manifest (§10.5). The export workflow is verified and documented (§9.1, §21 "LTspice CLI export").
- **Encoding policy** (§5.1, decision 0001) is validated on exported fixtures.
- **Solver tests (T8):** a local LTspice harness. Every LTspice accept fixture runs, edits are checked against closed forms, an unedited round trip gives identical results, and each `LT-*` entry gets a status backed by evidence (decision 0008 rules).
- **Exit (phase plan):** the M3–M6 test suites run for LTspice where the construct exists in both dialects; LTspice-only constructs have spec entries and tests.

Not in M8: phase 2 device letters, stimulus functions (`PULSE`, `SIN`, …), schematic (`.asc`) parsing (non-goal 4), and CI (M9 and later).

## 2. Decisions (maintainer, 2026-10-31)

The maintainer accepted every recommendation below as written (2026-10-31). On decision 2 the maintainer confirmed that only syntax facts are committed. On decision 14 the maintainer is drawing the schematics before implementation starts. "Recommendation" marks the accepted choice; an "Alternative" was considered and not chosen. Probe evidence (LTspice 26.1.1, 2026-10-31) is in section 7. Decision record 0009 (D1) records the outcome.

1. **Reference and citations** (§11.1, §12 "needs verification").
   *Recommendation:* use [`analogdevicesinc/ltspice-reference`](https://github.com/analogdevicesinc/ltspice-reference) as the LTspice "manual" for §11. Its license is **Apache-2.0** (verified 2026-10-31; `LICENSE.md`; the README says the documentation is Apache-2.0 and the software is proprietary).
   - Cite it as `[ltspice-ref] <FILE>.md "<heading>"`, and record the commit and access date in `docs/references.md`.
   - Paraphrase only, as for ngspice (§11.3 rule 4).
   - LTspice 26.1 installs a copy under `%LOCALAPPDATA%\LTspice\reference\` (marked version "24+"). Note which copy was cited.
   - The built-in LTspice Help (`LTspiceHelp\*.htm`) is proprietary. Do not cite or copy it. Use it only to choose what to probe.

   *Alternative:* cite the built-in Help. Not recommended: its terms are restrictive, and the Apache reference covers the phase 1 constructs.
2. **LTspice license and committed evidence** (§12). The LTspice EULA (`License.txt` §5) says the licensee may not publish "the results of any benchmark or comparison tests" without ADI's consent, and §7 treats the documentation as confidential.
   *Recommendation:*
   - Record only syntax facts in the repository, as for ngspice: what LTspice accepts or rejects, and how it reads a value (for example, `1M0` is milli). Use them in spec entries, `discrepancies.md` and test assertions. Probes run locally.
   - Never commit LTspice raw files, logs, or timing or performance numbers. This differs from the ngspice `raw/` samples; the LTspice reader tests use synthetic files written here.
   - Exports of schematics authored here stay allowed, as in M0/M1.
   - Add a line to `docs/provenance.md`.

   **This is your call. It is not legal advice**, and §12 already suggests a legal review of the provenance policy. *Alternative:* commit LTspice raw samples as for ngspice. Not recommended until you have checked the EULA.
3. **Grammar composition** (§6.1).
   *Recommendation:* move constructs that LTspice lacks or reads differently out of `core.lark` into `ngspice.lark`. Candidates found so far:
   - the `\\` continuation (LTspice rejects it, probe L24);
   - the IEC RKM terminals and the `rkm` gate (LTspice's form differs, decision 6);
   - the comment starters ngspice accepts and LTspice may not (settle `$` and `//`, decision 9).

   `ltspice.lark` adds the LTspice-only constructs. The regression gate:
   - every ngspice test and corpus result is unchanged;
   - the ngspice tree has the same shape (snapshot the node classes per corpus file before T2);
   - both grammars compile strict.

   *Alternative:* `ltspice.lark` overrides ngspice-flavoured core rules (`%override`). Not recommended: core would keep ngspice syntax, against §6.1.
4. **Structure: `.end` and text after it** (§6.3 rule 2, decision 0002).
   The reference says `.end` may be omitted and anything after it is ignored. LTspice 26.1.1 agrees (L10, L19). Every LTspice export writes `.end`.
   *Recommendation:* in phase 1, keep `.end` required and allow only blank lines after it, for LTspice too. Record it in `discrepancies.md` (the library rejects a form LTspice accepts). Decision 0009 records this as a deliberate exception to §11.3 rule 2 ("the grammar follows the manual"), to revisit after the phase 1 review. Reason: edit placement (`Placement.BEFORE_END`, `ensure_runs`) and the round-trip tests depend on `.end`.
   *Alternative:* follow the reference. `.end` becomes optional, and text after it becomes an opaque trailer. Edits without `.end` insert at the end of the file. This would be a grammar and edit-layer change in M8.
5. **Dot-commands** (§6.5). ngspice runs unknown dot-commands; LTspice 26.1.1 **stops** at one ("Expected device instantiation or directive here", L18). It also stops at `.control` and `.if` (L22, L23).
   *Recommendation:* the LTspice overlay has a closed list.
   - The typed directives (shared with ngspice where the forms agree, plus `.step`, decision 11).
   - The reference's other LTspice commands, kept as `UnknownDirective`: `.backanno`, `.func`, `.four`, `.noise`, `.tf`, `.fra`, `.wave`, `.net`, `.savebias`, `.savestate`, `.loadstate`.
   - Any other dot-command is a `ParseError` ("not an LTspice dot-command"). That includes `.control` and `.if`, which stay ngspice-only.
   - `.machine` … `.endmachine` is an `UnsupportedConstruct` in phase 1.
   - `.include`/`.inc`/`.lib` are opaque, as for ngspice. LTspice reads `.lib file` without a section as an include (L21).

   *Alternative:* preserve every dot-command as for ngspice, and treat an LTspice failure as the netlist's error. Not recommended: unlike opaque text, a misspelt directive (`.tarn`) would then pass silently, and LTspice has a documented closed set (P5).
6. **Numbers** (§6.4, decision 0004). LTspice's embedded decimal is native, works for every multiplier and uses LTspice's multipliers:
   - `2k2` = 2.2k, `1meg5` = 1.5Meg and `2R2` = 2.2 (L25–L28);
   - `M` is always milli, so `1M0` = 1 mΩ (L1, L3), unlike IEC 60062 mega;
   - `R47` is a model name, not 0.47 (L2);
   - `µ` is micro (L5);
   - letters after a number are ignored (reference).

   *Recommendation:*
   - The LTspice grammar accepts embedded-decimal values in the value slots of the phase 1 elements, without `rkm=True`. Passing `rkm=True` with `Dialect.LTSPICE` is a `ValueError`.
   - The node records `notation="rkm"` and the LTspice reading. `RKM_SOLVER_MISMATCH` is not used for LTspice.
   - `docs/grammars/ltspice/numbers.md` lists the forms.
   - Which value slots take the form (R, C, L values only, or also V/I `DC` and parameters) is settled with a probe per slot in T5.

   *Alternative:* reuse the ngspice `rkm` option and IEC meanings. Not recommended: it would mislabel LTspice's own reading of `1M0`.
7. **Element instance parameters** for the phase 1 letters. Exports carry LTspice-only parameters (`C … Rser=1`, `L … Rpar=1k`, `V … Rser=1`, `R … tc=a,b`).
   *Recommendation:* accept the parameters the reference documents for R, C, L, V, I, D, X and K. They are `name=value` pairs with value slots, so `set_param` can edit them. The `tc=a,b` list form gets a dedicated rule. Each letter's entry lists its parameters, and probes check each one. K with three or more inductors exited 1 with no error message in L13; settle it in T5.
8. **Names** (§8, decision 0006). Probes and the reference agree:
   - node names are any string without blanks, and `[ ]` (buses) is accepted (L20);
   - comparison uses Unicode case folding (L14);
   - `GND` is a synonym for `0`;
   - `00` is not `0` (L15).

   *Recommendation:*
   - `docs/grammars/ltspice/names.md` gets its own rule table.
   - `document/names.py` gains a dialect-aware fold: `str.casefold()` after NFC normalisation for LTspice, the current ASCII fold for ngspice.
   - Ground aliases are `0` and `GND` for LTspice.
   - The parse result carries the dialect, so the document layer needs no new argument.
   - The excluded name characters are settled by probe in T5. The reference's "avoid spaces" is the only stated limit.
9. **Comments.** The reference documents `*` at the start of a line and `;` anywhere. LTspice 26.1.1 also treats `$ …` as a comment (L4, L29: `1k $ 5k` ran as 1k, while `1k 5k` failed). Export comments of the form `;§pnba` are ordinary comments.
   *Recommendation:* `;` and `*` are documented forms. `$` becomes an `observed` entry with its exact rule (preceded by a blank? inside braces?) settled by probe. `//` is accepted only if LTspice accepts it. All trailing comments are preserved as they are today.
10. **Encoding** (§5.1, decision 0001). The reference lists UTF-8 (the netlister's only output), UTF-16LE with or without BOM, and Latin-1 when the bytes are not valid UTF-8. The source layer detects a BOM, then UTF-8, then `cp1252`, then `latin-1`.
    *Recommendation:* keep the source layer dialect-neutral and unchanged. Validate the policy on exports (UTF-8, no BOM; the M1 samples plus the new family). Record two differences in `discrepancies.md`:
    - BOM-less UTF-16LE is not detected (the caller passes `encoding="utf-16-le"`);
    - `cp1252` is tried before Latin-1 (the two differ on 0x80–0x9F).

    Add an authored UTF-16LE-with-BOM fixture that LTspice runs and the library round-trips.
    *Alternative:* add BOM-less UTF-16 detection. Not recommended: it needs a heuristic, against P5.
11. **`.step`** (§6.5 lists it as typed for LTspice).
    *Recommendation:*
    - Add a typed node for the reference's forms: `param`, a source, `temp`, or a model parameter; `lin`, `dec` or `oct`, or `list`. Several `.step` lines nest.
    - The swept quantity and each number are value slots.
    - Edit semantics (decision 0007 upsert): `directives.set(".step param x …")` replaces the `.step` that sweeps the same quantity and adds one otherwise. A fourth nested `.step` is refused (`EditError`) only if the reference states the limit of three; otherwise settle it by probe.

    *Alternative:* treat `.step` as repeatable, so `directives.add` only and `set` refuses.
12. **Other typed directives.** Reuse the core nodes where the LTspice form is the same as the ngspice form. Add overlay rules only where LTspice differs. Known so far:
    - `.tran` with one argument, and the keywords `startup`, `steady`, `nodiscard` and `uic`;
    - nested `.dc`;
    - `.temp` with a list;
    - `.param x 3k` without `=` (L11);
    - the wider `.meas` forms;
    - the LTspice option names.

    T4 lists each directive's forms against the reference before writing rules. `.save`, `.ic`, `.nodeset`, `.global`, `.options`/`.option`/`.opt` and `.title` run in LTspice (L30–L37).
13. **Device matrix** (§6.7).
    *Recommendation:* `ltspice-devices.json` and `devices.md` cover the reference's letters:
    - R, C, L, V, I, D, X and K are supported (phase 1);
    - A, B, E, F, G, H, J, M, O, Q, S, T, U, W and Z, plus `@` and `&` (frequency response analysis), are planned for phase 2.

    The architecture names `Ö` as an LTspice-only letter, but it is not in the reference. Decision 0009 corrects §6.7 to `@` and `&`.
14. **Fixtures and the export workflow** (§9.1, §10.5, phase plan section 5).
    *Recommendation:*
    - Add a family `tests/corpus/ltspice/contributed_examples/` (the maintainer's folder; the first file is `r_divider.asc`, 2026-10-31) of `.asc` schematics authored here, with their `-netlist` exports. The machine-specific path comment is normalised, as in M0.
    - Circuits: a divider; an RC filter with a `µ` value and `Rser`; a diode clamp with a `.model`; a coupled-inductor pair with `K`; a bus-named net; a `.step` sweep; a subcircuit instance with a parameter, via a `.lib` stub, as the M7 `solver_stubs` do.
    - **You draw the schematics in the LTspice GUI** (realistic exports, clean provenance). The developer may author further `.asc` files by hand where the GUI adds nothing.
    - A local test re-exports each `.asc` and compares the result with the committed `.net` after path normalisation. This verifies the export switch on every run and shows LTspice version drift.
    - Hand-written families: `ltspice/elements_basic`, `statements_basic`, `names_basic`, and matching `*_rejects` families.
15. **Solver harness** (decision 0008 item 6, by analogy).
    *Recommendation:*
    - `tests/support/ltspice.py` runs `LTspice.exe -b -ascii`. The ASCII raw file has full precision; the binary default stores floats for non-first variables (L0).
    - Move the M7 raw reader to `tests/support/raw.py`, shared by both harnesses. It reads LTspice ASCII files unchanged (L0).
    - A run fails on a non-zero exit code or a `file(line): message` line in the log.
    - The (c) comparison drops `Title:` (absolute path) and `Date:`.
    - `run_ltspice` in `solvers.py` stays the low-level runner (P9 holds: `src/` launches nothing).
16. **Running the M3–M6 suites for LTspice** (phase plan exit).
    *Recommendation:*
    - A shared case table of constructs whose text is valid in both dialects runs the grammar, round-trip, span, document and edit tests parametrised over `Dialect`. A `dialects=` marker per case excludes the ones that differ.
    - LTspice-only grammar tests go in `tests/grammar/ltspice/`.
    - The golden edit tests run on the `contributed_examples` fixtures.
    - Solver tests `tests/solver/test_ltspice_*.py` cover:
      - (a) every accept fixture runs;
      - (b) the M7 closed-form table for R, C, L, V, I, D, K and `.step`;
      - (c) an unedited round trip gives identical results;
      - (d) every `LT-*` entry and rule row.
    - The status checker of M7 is extended to `docs/grammars/ltspice/`, with `validated_on: {solver: ltspice, version: "26.1.1", …}`.
17. **Edit-layer conventions** (decision 0007).
    *Recommendation:* use the same text conventions for LTspice: lower-case keywords, `.param x=1k`, the line terminator of the insertion point, and `.include` for `add_include` (LTspice accepts it). Values the caller passes are written as given. An LTspice-only directive (`.step`) follows decision 11.
18. **Size and reviews.** M8 is larger than M7.
    *Recommendation:* one task list with **two review checkpoints**.
    - Checkpoint A, after T1–T8, covers the grammar, documents, fixtures and layers, all offline.
    - Checkpoint B, after T9–T13, covers the LTspice solver validation and exit.

    *Alternative:* split it into milestones M8a and M8b.

## 3. Design notes

- **Overlay file:** `src/netlistmod/grammar/ltspice.lark` imports from `.core` like `ngspice.lark`. `loader.py` registers `Dialect.LTSPICE` and drops it from `_PENDING_DIALECTS`. The device matrix is per dialect (`_DEVICE_MATRIX`). The block-name table for unterminated-block messages gets an LTspice entry (`.subckt` only).
- **Spec IDs:** `LT-<AREA>-<NNN>`, using the same area codes as ngspice where the construct is the same (`LT-RES-001` …). Each entry cites `[ltspice-ref]`. A construct shared by the two dialects has one entry per dialect: the evidence is per solver.
- **Rule documents:** `names.md` and `scoping.md` for LTspice follow the ngspice layout, including the "Validated on:" line. `scoping.md` re-probes S1–S11 in LTspice. Any rule that differs gets its own row, and the document layer branches on the dialect only where a row says so.
- **Raw files:** LTspice ASCII raw files are 8-bit text with CRLF line endings and the same `Values:` layout as ngspice. The header has extra keys (`Offset:`, `Command:`) and `Title:` holds the absolute netlist path.
- **Discrepancies:** `docs/grammars/ltspice/discrepancies.md` uses the M7 table layout (solver behaviour | library behaviour | evidence).

## 4. Tasks

Every task ends with `ruff check`, `ruff format --check`, `mypy --strict`, `lint-imports` and `pytest` (coverage gate) green, run as `uv run --env-file .env python -m <tool>`. Test-support files also pass `mypy --strict`, as in M7. Solver tasks also run with `--require-solver ltspice` (and `ngspice` wherever ngspice files changed). Where a task says "settle", state the choice and its basis in the report.

### Decisions

[ ] **D1 — Decision record 0009: the LTspice dialect.**
Record section 2 and amend the architecture:
- §6.1 (core content);
- §6.3–§6.5 (the `.end` exception, the dot-command list, `.step`);
- §6.4 (LTspice numbers);
- §6.7 (`@`/`&`, not `Ö`);
- §8 (dialect-aware names);
- §9.1;
- §10.3 (the LTspice harness);
- §11.1 (the citation form);
- §12 (the reference license; the EULA policy of decision 2);
- §21 (the CLI export is verified).

Status `proposed` until the maintainer accepts it.

### Grammar and documents (checkpoint A)

[ ] **T1 — Baseline and reference survey.**
- Snapshot the ngspice node classes and spans per corpus file. This is the T2 regression gate, a test that stays.
- Write `docs/grammars/ltspice/README.md` and the `references.md` entry (commit and date).
- Make a construct-by-construct table (phase 1 letters and directives × the reference's forms × the ngspice form). It goes in the T2 report and drives T3–T5.

[ ] **T2 — Move ngspice-only syntax out of core** (decision 3).
The ngspice tests, corpus results and the T1 snapshot are unchanged. Re-check the strict-mode lookaround list in the architecture test.

[ ] **T3 — `ltspice.lark`, structure and comments** (decisions 4, 5, 9).
Title line, `.end`, `*`/`;`/`$`, `+` continuation, the closed dot-command list, `.include`/`.inc`/`.lib`, `.subckt`/`.ends` (with and without a name), and rejection of `.control`/`.if`/`\\`. Add the loader registration and an LTspice entry in `_BLOCKS`.

[ ] **T4 — Directives** (decisions 11, 12).
Typed `.step`. LTspice forms of `.tran`, `.ac`, `.dc`, `.op`, `.temp`, `.param`, `.options`, `.ic`, `.nodeset`, `.save`, `.meas`, `.global` and `.title`. Spec entries and tests (T1–T6 tiers) for each.

[ ] **T5 — Elements and numbers** (decisions 6, 7, 13).
- The R, C, L, V, I, D, X and K lines with the reference's instance parameters.
- Embedded-decimal values per slot.
- `ltspice-devices.json` and `devices.md`; phase 2 letters raise `UnsupportedConstruct`.
- Settle K with three inductors, and which value slots take the embedded decimal.

[ ] **T6 — Names, scopes and the document layer** (decision 8).
- The dialect-aware fold and ground aliases.
- `names.md` and `scoping.md` for LTspice.
- Document-layer tests parametrised over both dialects.
- Diagnostics wording that names the dialect where it matters.

[ ] **T7 — Edit layer for LTspice** (decisions 11, 17).
- Edit tests parametrised over both dialects.
- `.step` upsert.
- Golden edits on `contributed_examples` inputs: set a value, set `Rser`, change `.step`, add a `.param`.
- Verification (signature, outside text, opaque cuts) holds unchanged.

[ ] **T8 — Fixtures, encoding and export workflow** (decisions 10, 14).
- The `contributed_examples` family, once the maintainer has drawn the schematics, and the hand-written LTspice families with manifests.
- The UTF-16LE-BOM fixture.
- The local re-export test.
- `docs/usage/ltspice-export.md`: verified commands, the path-comment normalisation, `-ascii`, the encoding results and the version caveat.
- Export settings: "Default Devices" and "Default Libraries" (`DefaultDeviceModels` and `DefaultDeviceLibraries` in `%APPDATA%\LTspice.ini`) must be off. With them on, every diode adds `.model D D` and a `.lib` line naming the bundled `lib\cmp\standard.dio` by absolute path. A running LTspice writes the setting to the file only when it exits, so a command-line export started while the GUI is open still uses the old value. Document this in `ltspice-export.md`. The re-export test fails with that explanation if an export has a `.lib` line into LTspice's `lib\cmp\` folder.
- `docs/provenance.md`.

**Checkpoint A:** set the status to `READY FOR REVIEW (checkpoint A)` and report. Do not start T9 before the review.

### Solver validation (checkpoint B)

[ ] **T9 — Shared raw reader and the LTspice harness** (decision 15).
Move the reader to `tests/support/raw.py` (the ngspice tests keep their names). Add `tests/support/ltspice.py` with `run`, `op`, `ac`, `tran_rows`, `ensure_runs` and `with_stubs`. The LTspice reader tests use synthetic files written here (decision 2). The pytest header already lists LTspice.

[ ] **T10 — Corpus sweep, (a) and (c).**
Manifest `solver` fields for the LTspice families, and `test_ltspice_corpus.py`.

[ ] **T11 — Edit results, (b).**
The M7 closed-form table for the phase 1 letters, plus `Rser` on C, and `.step` giving one result per step value.

[ ] **T12 — Entry and rule validation, (d).**
Probe tests for every `LT-*` entry and every rule row, with assertions on both LTspice and the library. Statuses and `validated_on` (ltspice 26.1.1). The status checker is extended to the LTspice documents. LTspice discrepancies go in `discrepancies.md`.

[ ] **T13 — Docs and exit.**
- `docs/testing.md` (LTspice procedure and runtime);
- README supported-dialects table;
- CHANGELOG;
- the phase plan's M8 heading.

Run the full check set with `--require-solver ngspice --require-solver ltspice` from a fresh clone. Report every "settle", every deviation, and every candidate `disputed`. Set the status to `READY FOR REVIEW`. **Do not archive.**

## 5. Construct coverage (minimum; T1 extends it)

| Area | LTspice forms to cover | Ngspice form shared? |
|---|---|---|
| Structure | title line; `.end` (required, decision 4); `+` continuation; `*`, `;`, `$` comments | partly (no `\\`, no `.control`/`.if`) |
| R | value, embedded decimal, `tc=a,b`, `temp=`, `m=` | value form |
| C, L | value, `Rser`, `Lser`, `Rpar`, `Cpar`, `RLshunt`, `m`, `ic`, `temp` | value form |
| V, I | DC value, `AC mag phase`, `Rser`, `Cpar` (V) | DC/AC forms |
| D | model, `area`, `off`, `m`, `n`, `temp` | yes |
| X | nodes, name, `name=value`, `params:` | settle by probe (`params:` ran, L40) |
| K | two or more inductors, coupling | settle three |
| Directives | `.step`, `.tran`, `.ac`, `.dc`, `.op`, `.temp`, `.param`, `.options`, `.ic`, `.nodeset`, `.save`, `.meas`, `.global`, `.title`, untyped list | per directive |
| Names | `[ ]`, Unicode fold, `GND`, `00` | no (dialect-aware) |
| Encoding | UTF-8 export, UTF-16LE BOM, cp1252 `µ` | source layer shared |

## 6. Edit results (minimum; extend in T11)

The M7 rows for R, C, L, V, I, D and K (`set_value`, `set_formula` with `params.set`, `set_param`, `set_model`, `set_model_param`, `set_dc`, `set_ac`, `set_coupling`, `directives.set` for `.tran` and `.temp`, `add_include`, a batch of three), plus:

| Operation | Circuit | Before → after (closed form) |
|---|---|---|
| `set_value` with an embedded decimal | 3 V divider, R2 = `1k` | `2k2`: 1.5 → 2.0625 V |
| `set_param` `Rser` on a C | RC low-pass, `Rser=0` | `Rser=1k`: \|H\| at f→∞ goes from 0 to 1k/(1k+1k) = 0.5 |
| `directives.set` `.step` | divider, R2 = `{x}` | `.step param x 1k 3k 2k`: v(out) = 1.5 and 2.25 V, one row per step |

## 7. Probe facts gathered while planning (LTspice 26.1.1, Windows, 2026-10-31)

Runs used `LTspice.exe -b [-ascii] file.net` in a scratch folder. `v(out)` is from the raw file, on a 3 V divider unless noted. Nothing from these runs is committed.

| # | Probe | LTspice |
|---|---|---|
| L0 | `-b` / `-b -ascii` | exit 0. The default raw file is binary with a UTF-16LE header, with the first variable as a double and the rest as float32. `-ascii` writes 8-bit text with CRLF; the M7 reader reads it unchanged. The log is ASCII. |
| L1, L3 | R2 `1M0`, `1M` | milli (v(out) = 3e-6) |
| L2 | R `R47` | "Undefined model r47" |
| L4, L29 | `1k ; c`, `1k $ c`, `1k $ 5k` | all run as 1k |
| L5 | C `1µ` | runs |
| L6 | C `… 1u Rser=1` | runs |
| L9 | first line `V1 …` (no title) | the line is the title |
| L10 | no `.end` | runs |
| L11 | `.param x 3k` and `.param x=3k` | both 2.25 V |
| L12 | bare formula `x*3` | fails |
| L13 | `K1 L1 L2 L3 0.5` (AC) | exit 1, no error line (settle in T5) |
| L16 | `.step param x 1k 3k 2k` | two points: 1.5 and 2.25 V |
| L17 | `.backanno` | runs |
| L18 | `.foo bar` | "Expected device instantiation or directive here" |
| L19 | text after `.end` | ignored |
| L20 | node `o[1]` | runs (1.2 V, correct) |
| L21 | `.lib h.inc` (no section), `.inc h.inc` | both include the file |
| L22, L23 | `.control … .endc`, `.if (1) … .endif` | fail at the first line |
| L24 | `\\` continuation | fails |
| L25–L28 | `2R2`, `100R`, `2k2`, `1meg5` | 2.2, 100, 2200, 1.5e6 Ω |
| L40 | `X1 in out div params: r=3k`, `X1 in out div r=3k` | both 2.25 V |
| L14, L15 | `ÄIN`/`äin` the same node; `00` distinct from `0` | yes; yes |
| L30–L37 | `.ic`, `.nodeset`, `.opt`, `.option`, `.meas op`, `.global`, `.save`, `.title`, `.func` | all run |
| L38 | `R2 out 0 1k 5k` | "Unknown parameter" |
| L39 | a directive inside `.subckt` | fails |
| L41 | C `1μ` (U+03BC GREEK SMALL LETTER MU, `rc_lowpass` export) | read as micro (\|H\| at 100 Hz = 0.5861, as for 1u) |
| L42 | X instance `X1` placed from a block symbol | exported as `X§X1 … ;§pnba r1)r2` (LTspice inserts `§` after the prefix) |
| L43 | `-netlist` on a schematic with a hierarchical block (`r_divider_subckt.asc`) | the block's sheet is **not** netlisted (no `.subckt`), so the export does not run ("This sub-circuit name is not defined") |
| L44 | R value `x` (bare parameter name, `r_divider_sweep`) | "Undefined model "x"": a bare name is a model name |
| L45 | instance `SYMATTR Value ""` on a block | the subcircuit name is dropped from the X line |
| L46 | the seven `contributed_examples` schematics (2026-11-01), with Default Devices and Default Libraries off | each exports with `-netlist` and runs with `-b` with no warning or error. `half_rectifier` runs because LTspice supports `SINE`; the library will reject that line (phase 2). |

## 8. Out of scope for M8

- Phase 2 letters and stimulus functions.
- `.asc` parsing.
- `.machine` (unsupported, decision 5).
- An optional `.end` (decision 4; revisit after the phase 1 review).
- BOM-less UTF-16 detection.
- Linux/macOS LTspice (wine) and CI.
- qspice and xyce.
