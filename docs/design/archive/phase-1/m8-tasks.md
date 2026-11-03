# M8 task list — LTspice overlay

> **Status:** COMPLETE (2026-11-02) — checkpoint A approved in section 12, checkpoint B in section 16; section 2 records the decisions, sections 10, 13 and 15 the implementation.
> **Part of:** [phase-1-plan.md](./phase-1-plan.md) (milestone M8). Governed by [architecture.md](../../../architecture.md) (§2 P5, P7, P8, P10, P13; §4; §5.1; §6.1–§6.7; §9; §10; §11 (normative); §12; §21). Builds on the grammar of M2–M4 (`core.lark`, `ngspice.lark`), the document layer of M5 ([document-layer.md](../../document-layer.md)), the edit layer of M6 ([edit-layer.md](../../edit-layer.md)), the validation layer of M7 ([decision 0008](../../../decisions/0008-validation-status-and-solver-harnesses.md)), the LTspice spikes of M0/M1 ([ltspice-export.md](../../../usage/ltspice-export.md)) and [decision 0001](../../../decisions/0001-source-text-policy.md) (encoding).

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

[x] **D1 — Decision record 0009: the LTspice dialect.**
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

[x] **T1 — Baseline and reference survey.**
- Snapshot the ngspice node classes and spans per corpus file. This is the T2 regression gate, a test that stays.
- Write `docs/grammars/ltspice/README.md` and the `references.md` entry (commit and date).
- Make a construct-by-construct table (phase 1 letters and directives × the reference's forms × the ngspice form). It goes in the T2 report and drives T3–T5.

[x] **T2 — Move ngspice-only syntax out of core** (decision 3).
The ngspice tests, corpus results and the T1 snapshot are unchanged. Re-check the strict-mode lookaround list in the architecture test.

[x] **T3 — `ltspice.lark`, structure and comments** (decisions 4, 5, 9).
Title line, `.end`, `*`/`;`/`$`, `+` continuation, the closed dot-command list, `.include`/`.inc`/`.lib`, `.subckt`/`.ends` (with and without a name), and rejection of `.control`/`.if`/`\\`. Add the loader registration and an LTspice entry in `_BLOCKS`.

[x] **T4 — Directives** (decisions 11, 12).
Typed `.step`. LTspice forms of `.tran`, `.ac`, `.dc`, `.op`, `.temp`, `.param`, `.options`, `.ic`, `.nodeset`, `.save`, `.meas`, `.global` and `.title`. Spec entries and tests (T1–T6 tiers) for each.

[x] **T5 — Elements and numbers** (decisions 6, 7, 13).
- The R, C, L, V, I, D, X and K lines with the reference's instance parameters.
- Embedded-decimal values per slot.
- `ltspice-devices.json` and `devices.md`; phase 2 letters raise `UnsupportedConstruct`.
- Settle K with three inductors, and which value slots take the embedded decimal.

[x] **T6 — Names, scopes and the document layer** (decision 8).
- The dialect-aware fold and ground aliases.
- `names.md` and `scoping.md` for LTspice.
- Document-layer tests parametrised over both dialects.
- Diagnostics wording that names the dialect where it matters.

[x] **T7 — Edit layer for LTspice** (decisions 11, 17).
- Edit tests parametrised over both dialects.
- `.step` upsert.
- Golden edits on `contributed_examples` inputs: set a value, set `Rser`, change `.step`, add a `.param`.
- Verification (signature, outside text, opaque cuts) holds unchanged.

[x] **T8 — Fixtures, encoding and export workflow** (decisions 10, 14).
- The `contributed_examples` family, once the maintainer has drawn the schematics, and the hand-written LTspice families with manifests.
- The UTF-16LE-BOM fixture.
- The local re-export test.
- `docs/usage/ltspice-export.md`: verified commands, the path-comment normalisation, `-ascii`, the encoding results and the version caveat.
- Export settings: "Default Devices" and "Default Libraries" (`DefaultDeviceModels` and `DefaultDeviceLibraries` in `%APPDATA%\LTspice.ini`) must be off. With them on, every diode adds `.model D D` and a `.lib` line naming the bundled `lib\cmp\standard.dio` by absolute path. A running LTspice writes the setting to the file only when it exits, so a command-line export started while the GUI is open still uses the old value. Document this in `ltspice-export.md`. The re-export test fails with that explanation if an export has a `.lib` line into LTspice's `lib\cmp\` folder.
- `docs/provenance.md`.

**Checkpoint A:** set the status to `READY FOR REVIEW (checkpoint A)` and report. Do not start T9 before the review.

### Solver validation (checkpoint B)

[x] **T9 — Shared raw reader and the LTspice harness** (decision 15).
Move the reader to `tests/support/raw.py` (the ngspice tests keep their names). Add `tests/support/ltspice.py` with `run`, `op`, `ac`, `tran_rows`, `ensure_runs` and `with_stubs`. The LTspice reader tests use synthetic files written here (decision 2). The pytest header already lists LTspice.

[x] **T10 — Corpus sweep, (a) and (c).**
Manifest `solver` fields for the LTspice families, and `test_ltspice_corpus.py`.

[x] **T11 — Edit results, (b).**
The M7 closed-form table for the phase 1 letters, plus `Rser` on C, and `.step` giving one result per step value.

[x] **T12 — Entry and rule validation, (d).**
Probe tests for every `LT-*` entry and every rule row, with assertions on both LTspice and the library. Statuses and `validated_on` (ltspice 26.1.1). The status checker is extended to the LTspice documents. LTspice discrepancies go in `discrepancies.md`.

[x] **T13 — Docs and exit.**
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

The probes made while implementing (T1–T8, R1–R3) are recorded in [discrepancies.md](../../../grammars/ltspice/discrepancies.md), `names.md`, `scoping.md` and section 10. Runs used `LTspice.exe -b [-ascii] file.net` in a scratch folder. `v(out)` is from the raw file, on a 3 V divider unless noted. Nothing from these runs is committed.

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

## 9. Checkpoint A review, round 1 (2026-11-01)

### 9.1 Outcome

The grammar split, overlay, documents, layers and fixtures meet T1–T8, apart from the changes in 9.2. Checks re-run for the review:

- `ruff check`, `ruff format --check`, `mypy` (configured `src/` scope) and `lint-imports` are clean.
- The full suite with `--require-solver ngspice` gives 2864 passed, 2 skipped, 343 deselected (the other dialect's run of `ngspice_only` and `ltspice_only` tests), and 98.78% coverage.
- `test_ltspice_export.py` and `test_ltspice_spike.py` pass with `--require-solver ltspice`.
- **ngspice regression gate, checked independently:** the committed tests (`7d3a9cb`), unedited, were run against the new `src/`, with ngspice required: 1662 passed, 2 skipped, 42 failed. Those 42 are the expected API changes and registration: the new required `dialect` argument of `parse_formula`, `reserved_words`, `device_matrix` and `fold` (38), the new public exports, LTspice now being registered, and two architecture tests that the working tree updates. None is a change in ngspice parsing, and the golden, corpus and solver tests all pass unedited.
- No LTspice raw file, log or machine path is in `tests/corpus/ltspice/`.

### 9.2 Required changes

[x] **R1 — Element parameters LTspice's own parts carry** (decision 7, widened by the maintainer on 2026-11-01: the lists stay closed, and a name is added only once it is verified). The per-letter lists stay closed, so `Rsr=1` still fails, but they are too narrow: parts from LTspice's component database do not parse. LTspice 26.1.1 runs each of these, and the library rejects them:

```
C1 b 0 10µ V=6.3 Irms=1.2 Rser=0.002 Lser=0 mfg="TDK" pn="C3216" type="X5R"
L1 b 0 10µ Ipk=5 Rser=0.01 Rpar=1000 Cpar=1p mfg="Coilcraft" pn="MSS1038"
R1 b 0 1k tol=1 pwr=0.25
```

A read-only scan of `SYMATTR SpiceLine` in the 4365 schematics LTspice installs (nothing copied; used only to choose what to probe) found, by count: C `V` 292, `Irms` 285, `mfg`, `pn` and `type` 274 each; L `Ipk` 28, `mfg` and `pn` 25 each; R `tol` 16, `pwr` 13. Add:

- C: `V`, `Irms`, `mfg`, `pn`, `type`;
- L: `Ipk`, `mfg`, `pn`, and the `noiseless` flag;
- R: `tol`, `pwr`, `tc1`, and the `noiseless` flag;
- D: `area=`.

`mfg`, `pn` and `type` take a quoted string (settle by probe whether a bare word is also accepted on an element line). Probe each name on each letter, and probe `tc2` on R and the rest of the discrepancy row in the same pass. Each is a spec-entry note marked as observed (§11.3 rule 3), with tests, and the discrepancy row shrinks to what stays rejected. `set_param` edits the numeric ones.

Add the maintainer's new schematic `LC_filter_mfg_components.asc` (2026-11-01) to `contributed_examples` with its normalised export, its manifest entry and a golden edit (a numeric parameter of C1 or L1). LTspice 26.1.1 exports and runs it. It holds real database lines, so it also pins that a quoted value may contain blanks and a comma (`type="Al electrolytic"`, `mfg="Bourns, Inc."`). The `.net` in the folder is the maintainer's GUI export, with a machine path on its first line: regenerate it.

[x] **R2 — String parameters in `.model`** (LTspice overlay only). `.model DX D(Is=1e-14 Iave=1 Vpk=75 mfg=OnSemi type=silicon)` runs in LTspice and is a `ParseError`, as is the quoted `mfg="OnSemi"`. The bare form is what LTspice's own `lib/cmp/standard.dio` uses (924 of its 926 `.model` lines, by a read-only count), and users paste such lines into a schematic. Accept a bare word or a quoted string as a `.model` parameter value. Keep the value text verbatim; do not read a bare word as a formula or a reference.

[x] **R3 — `.ic I(L1)=…`** Accept inductor currents in `.ic`, and keep `.ic I(R1)=1` out if the grammar or a diagnostic can tell. The discrepancy row says the reference shows only `V(node)`, but `[ltspice-ref] TROUBLESHOOTING-GUIDE.md` says `.ic` sets node voltages and inductor currents, so this is a documented form. The current names an element: index it like `.save I(...)`, so a name no element has gets `UNRESOLVED_ELEMENT`. `.nodeset I(...)` and `.ic V(a,b)` stay rejected, with their rows.

[x] **R4 — Limit single `&` and `|` to LTspice.** Decision 3's gate is that ngspice is unchanged. ngspice 47 **fails** on `{a&b}` and `{a|b}` ("Error in netlist line"), so the shared formula grammar now reports references for a form ngspice rejects. Add a test that ngspice's `parse_formula("a&b")` gives no tokens, as it did before.

[x] **R5 — mypy on the tests.** `mypy --strict tests/support tests/solver tests/conftest.py tests/test_ngspice_raw_reader.py tests/test_corpus_manifests.py` has 3 errors (`test_ngspice_solver_structure.py:232`, `test_ngspice_solver_statements.py:157`, `:194`). `Param.value` is now `Value | ValueList`, and `ValueList` has no `text`, which also breaks public callers on ngspice netlists. Give `ValueList` a `text` property (the source slice of its span), so the union stays uniform, rather than narrowing at each call.

[x] **R6 — Edit messages that assume a resistor model.** In LTspice, `set_model("R1", …)` says "`R1` takes a model of type `R`", and `remove_value("R1")` says "add a model with set_model first". LTspice has no R, C or L model (confirmed: `.model rm R` with `R1 a 0 rm` exits 1). Say so, with an `EditError` before the type check. Test both.

[x] **R7 — Implementation report.** Add a section 10 to this list, as in earlier milestones: what changed, each "settle" with its basis, the deviations from section 2 (below), and where to find the T1 table. Add the probes that later documents cite, or point section 7 at `discrepancies.md`.

The maintainer confirmed R1–R7 (2026-11-01).

### 9.3 Developer's calls: accepted by the maintainer (2026-11-01)

- **Bare values rejected with a hint** (`R47`, `R1 a b x`). This corrects decision 6, which called `R47` a model name. LTspice stops at every such line, so no working netlist is lost and the hint is better than its message. Decision 0009 item 7 already records it.
- **`.options` names not checked.** Unlike element parameters, the option set cannot be enumerated from the reference or by probing letter by letter, and an option is not topology. A false rejection would cost more than a typo, which LTspice stops at anyway. The discrepancy row stays.
- **`.dc … list` only as the last sweep.** Rare, loud and recorded; not worth weakening the LALR grammar.
- **Edits to existing ngspice tests.** The `dialect` argument and the registration test are required. Moving the property tests to `m` and `temp`, and two tests to `.save v(...)`, loses no ngspice coverage: `.save all` and `tc1` are still tested in `test_edit_directives.py` and `test_edit_elements.py`.
- **Additions.** `.model … ako:` is in the reference (`SIMULATION-COMMANDS-REFERENCE.md`, `.MODEL`) and has entry `LT-MOD-001`. The `DUPLICATE_DEFINITION` warning on a repeated `.step` matches LTspice, which stops there, and is rule S12.
- **The T1 table in the LTspice README.** Fine; R7 points to it.

### 9.4 Observations (not required)

- Every LTspice export now gets one `UNKNOWN_DIRECTIVE_PRESERVED` (info) for `.backanno`, and `.tf`, `.noise` and `.four` are reported as "unknown" although they are on the closed list. Consider a quieter path for listed commands in phase 2.
- `BARE_FORMULA` in `ltspice.lark` is a long regular expression with a lookahead. It passes the probes (`.param x=2*pi*100 y=3`, `.param x 1k y 2k`, `.param x=1k, y=2k`) and is on the pinned lookaround list. Keep its tests close to it.
- Decision 0009 is `proposed` and the work is uncommitted in the working tree.

## 10. Implementation report (checkpoint A)

All probes ran locally on LTspice 26.1.1 (Windows, 2026-11-01). Only syntax facts are recorded (decision 2).

### 10.1 What changed

- **D1:** [decision 0009](../../../decisions/0009-ltspice-dialect.md), status `proposed`; architecture amended.
- **T1:** `tests/grammar/ngspice/test_tree_snapshot.py` with `tree_snapshot.json`, generated before the split. References entry `[ltspice-ref]`. The construct table is in [the LTspice README](../../../grammars/ltspice/README.md), section "Construct survey".
- **T2:** `core.lark` holds the shared subset; `ngspice.lark` holds `\\`, commas, RKM, the keyword and model forms of R, C and L, and the forms recognised only to be rejected. The snapshot is unchanged.
- **T3–T5:** `ltspice.lark`, `ltspice-devices.json`, `StepDirective`, `ValueList`, and new optional node fields; 40 `LT-*` entries, all `documented` until T12.
- **T6:** dialect-aware names, `$G_*`, per-dialect diagnostics wording and reserved words. `tests/document` runs on both dialects.
- **T7:** `.step` upsert, `set_param` on V, I and the D area. `tests/edits` runs on both dialects. Golden cases in `ltspice/edits_golden`.
- **T8:** `contributed_examples` exports and manifest, hand-written families, `utf16le_bom.cir`, `tests/test_ltspice_export.py`, `docs/usage/ltspice-export.md`, `docs/provenance.md`.

**Review round 1:**

- **R1:** the names below, the `noiseless` flag (`flags` on R, C and L nodes), and `LC_filter_mfg_components` with its normalised export and the golden case `set_part_parameters`. Parameter terminals now hold a lookahead for `=`, so `m` never matches the start of `mfg`.
- **R2:** `MODEL_WORD` and `STRING_VALUE` as `.model` values; a bare word is an `Identifier`.
- **R3:** `current_condition` in `.ic`, with `NodeCondition.current`, indexed as an element reference.
- **R4:** `formula_ltspice.lark`, an overlay, with `formula.lark` back to its committed operators. ngspice's `parse_formula("a&b")` is `None`.
- **R5:** `ValueList.text` is a field holding the source slice of its span (a property could not reach the source), and `Identifier.text` a property. The named mypy command is clean.
- **R6:** `set_model` and `remove_value` raise "LTspice has no R, C or L model", before the type check.

**Review round 2:**

- **R8:** `MODEL_TEXT_KW` gives `mfg` and `type` their text values. `MODEL_BARE` (renamed from `MODEL_WORD`) is now recognised only to be rejected, with a hint to write `{x}`. The bare word `mfg=3M` is now an `Identifier`, like any other text value. Rows corrected in `discrepancies.md`.
- **R9:** `Flag.value`, with `Flag.span` running to the value; `noiseless`, `load` and `off` take a number or a formula. A formula in a flag value is indexed as a reference. `set_param` edits a flag's value in place (`off` becomes `off=1`), an addition the review did not ask for: without it, the call would fail.
- **R10:** `mfg` and `pn` on R, `noiseless` on C, `Rpar=` on D. `ic=` on D stays rejected, with its row.

### 10.2 Each "settle", with its basis

| Item | Choice | Basis |
|---|---|---|
| `$` (decision 9) | A comment only as space, `$`, space | `1k $ c` runs; `1k$ c`, `1k $c`, `1k $`, and a tab on either side stop LTspice; `$G_x`, `a$b` and `a$` are names |
| `//` (decision 9) | Not a comment | `1k // c` stops LTspice; `.include sub//h.inc` reads a path |
| Value slots (decision 6) | Every slot | `1k5`-style values read correctly in R, C, L, V, I, K, the D area, parameters, `X`, `.subckt`, `.model`, `.param`, `.tran`, `.ac`, `.dc`, `.ic` and `.step` |
| K with three inductors (decision 7) | Valid | Three and four run when each has its own load. An inductor loop reproduces L13's symptom; L13's circuit is not recorded, so that cause is an inference |
| Name characters (decision 8) | Excluded: `= ( ) , { } ' " \|`, `;` and blanks | Each excluded character stops LTspice; about 20 others run |
| Fourth `.step` (decision 11) | Not refused | Four run; the reference states no limit |
| `.options` names (decision 12) | Not checked | Accepted by the maintainer (9.3) |
| `mfg`, `pn`, `type` (R1) | Double-quoted string or bare word | Both run on an element line, also with `;` or ` $ ` inside the quotes; `V="6.3"` stops LTspice |
| `type` on R and L (R1) | Not added | LTspice stops at it |
| `tc2` on R (R1) | **Added** with `tc1` | The probe the task asked for: it runs |
| `.model` bare words (R2, corrected by R8) | Only `mfg` and `type` take one; any other bare value is a `ParseError` suggesting `{x}` | LTspice reads it as a parameter reference (`Is=x`) and stops at an undefined one (`Is=abc`). A whole number under another name stays a number |
| Flag values (R9) | A number or a formula | `noiseless=0`, `load=1`, `off=1` and `{1}` run; `noiseless="1"` and `noiseless=x` stop LTspice |
| `.ic I(R1)` (R3) | Rejected by the grammar (`L_REF`) | LTspice runs it and ignores it. `.ic I(L1)=1` with `uic` gives -1 V across a 1 Ω load |
| `.ic I(x1:L1)` (R3) | Rejected, with a row | LTspice sets the current, but the form is undocumented and names no element of the scope |

### 10.3 Deviations from section 2

- **Decision 6:** `R47` and other bare values are rejected with a hint, not read as model names, because LTspice has no R, C or L model (accepted, 9.3).
- **Decision 7:** the lists are closed per letter, widened by R1 (accepted). Forms that stay rejected are rows in `discrepancies.md`.
- **Decision 12:** `.dc ... list` only as the last sweep (accepted, 9.3).
- **Decision 16:** besides the `ngspice_only` and `ltspice_only` markers, a module may name single cases in `NGSPICE_ONLY_CASES`, since parameter tables hold lambdas and ids. The LTspice forms of what they exclude are in `test_ltspice_*.py`.
- **R1 wording:** `ValueList.text` is a field, not a property (R5, above).

### 10.4 Candidates for later

- `[ltspice-ref]` citations name the installed copy; check them against the recorded commit if it moves.

## 11. Checkpoint A review, round 2 (2026-11-01)

### 11.1 Outcome

R1–R7 are done as section 10 reports, and the LC filter fixture parses and has a golden edit. Checks re-run for the review:

- `ruff check`, `ruff format --check`, `mypy` (configured `src/` scope), the named `mypy --strict` test command and `lint-imports` are clean.
- The full suite with `--require-solver ngspice --require-solver ltspice` gives 2949 passed, 2 skipped, 364 deselected, and 98.80% coverage.
- The ngspice gate holds: the committed tests against the new `src/` give the same 1662 passed and 42 failed as in round 1, in the same expected classes (9.1).

### 11.2 Required changes

[x] **R8 — `.model` bare words only for `mfg` and `type`** (corrects R2; confirmed by the maintainer, 2026-11-01). R2 asked for "a bare word as a `.model` parameter value", and that was too wide. LTspice 26.1.1 **reads a bare word in a numeric parameter as a parameter reference**:

| Line, with `.param x=2` or `x=1n` | LTspice | Library now |
|---|---|---|
| `.model DX D(Is=x*1n)` | same result as `Is=2n` | accepted, no reference to `x` |
| `.model DX D(Is=x)` | same result as `Is=1n` | accepted as an `Identifier`, no reference to `x` |
| `.model DX D(Is={x*1n})` | same result as `Is=2n` | accepted, one reference to `x` |
| `.model DX D(Is=abc)` | stops: "No such parameter defined" | accepted |

The first two are a form the library accepts and the solver reads differently, with no diagnostic: decision 0008's definition of `disputed`. They also make `references_to_param` silently incomplete. `test_a_bare_word_is_not_a_reference` pins the wrong behaviour.

A read-only scan of LTspice's `lib/cmp` (2638 `.model` lines) finds bare words only as `mfg` (2871) and `type` (1157), with no quoted values. So:

- accept a bare word or a quoted string only for `mfg` and `type`, in the LTspice overlay;
- every other `.model` parameter takes a number or a delimited formula, as before R2, so `Is=x`, `Is=1n*2` and `Is=abc` are `ParseError`s. The hint suggests `{x}`;
- correct the `discrepancies.md` row: the library rejects these forms, and restore "bare expressions only in `.param`";
- replace `test_a_bare_word_is_not_a_reference` with tests of the above, and one that `mfg=x` gives no reference to a parameter `x`.

`pn` stays out: `pn=1N4148A` stops LTspice, and no library line uses it.

[x] **R9 — A flag may take a value** (10.4; confirmed by the maintainer, 2026-11-01). `[ltspice-ref] CIRCUIT-ELEMENTS-REFERENCE.md` "Element Overview" says a flag is active if present, or may be assigned a value (0.5 or more is on). LTspice runs `noiseless=1`, `noiseless=0`, `load=1` and `off=1`. Rejecting a documented form breaks §11.3 rule 2, and this is grammar, so do it in this checkpoint rather than at T12. Accept `name` and `name=value` for `noiseless`, `load` and `off`. The library keeps the text and does not interpret the threshold.

[x] **R10 — Add the other verified names** (R1's rule; confirmed by the maintainer, 2026-11-01). The rule is that a closed list grows when a name is verified. These run, and are added as observed with tests:

- `mfg` and `pn` on R, as on C and L;
- `noiseless` on C, as on R and L;
- `Rpar=` on D: it takes effect (with `Rpar=1`, a 3 V source through 1k gives 2.997 mV across the diode, against 0.677 V without it).

`ic=` on D stays rejected, with its row: it runs, but a `.tran … uic` probe showed no effect on the result, so it is not verified as doing anything.

The maintainer confirmed R8–R10 (2026-11-01).

### 11.3 Developer's calls: accepted

- **`ValueList.text` as a field.** Correct: the node cannot reach the source. It holds the slice (`tc=1, 2` gives `1, 2`), and that is what R5 needed. This section supersedes R5's wording.
- **`.ic I(x1:L1)=1` stays rejected.** LTspice does set that current, but the form is undocumented and reaches into an instance, which S9 keeps out of scope. It fails loudly and has a row. The addition can wait until a real netlist needs it.

## 12. Checkpoint A review, round 3 (2026-11-01) — approved

R8–R10 are done, and checkpoint A is approved. T9 may start. Checks re-run for the review:

- `ruff check`, `ruff format --check`, `mypy` (configured `src/` scope), the named `mypy --strict` test command and `lint-imports` are clean.
- The full suite with `--require-solver ngspice --require-solver ltspice` gives 2995 passed, 2 skipped, 376 deselected, and 98.81% coverage.
- The ngspice gate holds: the committed tests against the new `src/` give the same 1662 passed and 42 failed as in rounds 1 and 2.

Probes (LTspice 26.1.1):

- `Is=x` and `Is=1n*2` on a `.model` are `ParseError`s whose message suggests `{x}`; `Is={x}` gives a reference to `x`; `mfg=x` gives none.
- Flags take values on R, C, L, I and D. `Rpar=` on D and `mfg`/`pn` on R parse; `ic=` on D stays rejected.

**Developer's calls: accepted.**

- **`mfg=3M` as an `Identifier`, not a number.** Under `mfg` and `type`, an unquoted value is text. Reading it as 3 milli would be wrong. `.text` is `3M` for both `mfg=3M` and `mfg="3M"`, so callers see the same text.
- **`set_param` editing a flag's value in place** (`off` to `off=1`, `noiseless=1` to `noiseless=0`). It follows from R9, is tested, and leaves the topology signature unchanged. On ngspice, `off=1` stays an `EditError`, because the edit does not parse.
- **`mfg={x}` stays rejected.** LTspice runs it but does not evaluate it: `mfg={nope}` (an undefined name) and `mfg={1+}` (not an expression) also run. Accepting it as a formula would report a reference to `x` that LTspice never reads. The form has a row in `discrepancies.md`, which may add that LTspice does not evaluate the value.

**For T12:** `pn` on a `.model` is not a metadata name there. LTspice warns "Ignoring unknown model parameter" for `pn=OnSemi`, and `pn=1N4148A` is a syntax error. The library treats `pn` on a `.model` as an open numeric name (`pn=3M` is a number), and rejects `pn="3M"` and `pn=OnSemi`. That is acceptable, since nothing in LTspice's libraries uses it, but T12's `.model` probe should pin it.

## 13. Implementation report (checkpoint B)

Probes ran on LTspice 26.1.1 and ngspice 47 (Windows, 2026-11-01, the machine's date). Only syntax facts are recorded; no raw file, log or timing from LTspice is committed (decision 2). Nothing is committed yet: the work is in the working tree, on top of `0b464ae`.

### 13.1 What changed

- **T9:** `tests/support/raw.py` holds the reader, and `tests/support/ngspice.py` re-exports its names, so the ngspice tests are unedited. `tests/support/ltspice.py` has `run`, `op`, `op_steps`, `ac`, `tran_rows`, `ensure_runs` and `with_stubs`. `run_ltspice` gains `ascii_raw`. Synthetic reader tests are in `tests/test_ltspice_raw_reader.py`, and solver tests of the harness in `tests/solver/test_ltspice_harness.py`.
- **T10:** `tests/solver/test_ltspice_solver_corpus.py` runs every accept fixture, (a) and (c). A checker test covers the `solver` fields.
- **T11:** `tests/solver/test_ltspice_edit_results.py` has the M7 table, the three rows of section 6, and `set_param` on V `Rser` and the D area. `test_ltspice_edit_properties.py` is the Hypothesis test of decision 0008 item 5 on LTspice, an addition.
- **T12:** `test_ltspice_validation.py` (entries), `test_ltspice_discrepancies.py` (rows, and every `*_rejects` fixture) and `test_ltspice_solver_document.py` (rule tables). 40 entries are `validated`. Rules: 13 `validated`, 9 `observed`, none `disputed`. The checker now also requires `validated_on` to name the dialect's solver.
- **T13:** `docs/testing.md`, the README's new supported-dialects table, CHANGELOG, the phase plan, `docs/design/README.md`, decision 0009 and architecture §10.3.

### 13.2 Results

From a fresh clone of `0b464ae` with the working-tree changes copied on top, with a new environment, since the work is uncommitted (so not a clone of a commit):

- `ruff check`, `ruff format --check`, `mypy` (configured scope), `mypy --strict` on the named test command plus `tests/test_ltspice_raw_reader.py`, and `lint-imports` are clean.
- `pytest --require-solver ngspice --require-solver ltspice`: 3778 passed, 2 skipped (POSIX only), 396 deselected, 98.81% coverage.
- After that run only this section and the runtime sentence in `docs/testing.md` changed; `tests/architecture` and `tests/test_usage_docs.py` were re-run on them.
- ngspice gate: the ngspice test files and `tree_snapshot.json` are unedited, and they pass. The `src/` changes of this checkpoint are listed in 13.3 and 13.5; each applies to LTspice only.

### 13.3 Rule S11: a candidate `disputed`, resolved (maintainer, 2026-11-01)

T12 found that `.param pi=3k` overrides the constant in LTspice while the library kept `pi` reserved, so `references_to_param("pi")` was empty with nothing flagging it. The maintainer chose to fix it, after asking for the probes below. On every word of the former list (`tests/solver/test_ltspice_solver_document.py`):

| Group | Words | Bare, no definition | With a definition | Library now |
|---|---|---|---|---|
| Built-in values | `pi`, `BOLTZ`, `ECHARGE`, `PLANCK`, `KELVIN`, `GMIN` | the value | masked, in that scope only | no reference, or a reference to the definition |
| | `temp` | the temperature | a top-level `.param` stops LTspice; a default or body `.param` masks it | the same, with a discrepancy row |
| Everything else | the function names, `time`, `freq` | stops | a parameter | an ordinary name: `UNRESOLVED_PARAM`, or a reference |

- The constant behaves as if it were in a scope outside the top level: one `.param pi` masks it, and a second is a repeat that stops LTspice (S6).
- `sqrt(9)` and bare `sqrt` are separate: `{sqrt+sqrt(9)}` with `.param sqrt=3k` is 3003. The grammar already tells a call apart.
- `time` and `freq` were to stay silent in the proposal to the maintainer, since bare `{time}` in a `.tran` was unprobed. The probe stops, in `.tran` and `.ac`, in a value, a parameter, a capacitor and a `.param`, so they are ordinary names too.
- **Scope limit for phase 2:** with `.param time=3k`, `R={time}` in a `.tran` reads the simulation time, not the parameter. The library rejects that form today, but behavioural expressions will need their own rule.
- ngspice is unchanged; the change is the LTspice list and one LTspice branch in `document/index.py`.
- **A gap from checkpoint A, fixed with this:** `{x}` with only a `.step param x` resolved to the step, but `references_to_param("x")` returned nothing, because it compared with `.param` lines only. It now includes them at the top level.

The full check set was re-run after this change (13.2). No other accepted form was found to be read differently from the library's model.

### 13.4 Each "settle", with its basis

| Item | Choice | Basis |
|---|---|---|
| Raw files of one run | A `Run` holds `<name>.raw` and `<name>.op.raw`, and (c) compares both | An AC analysis writes its bias point to the second file |
| A warning written as an error line | Manifest field `{"warning": "<text>"}`, used by `elements_basic/sources_diodes.cir` only | `V7 h 0` runs with exit 0 and `file(line): Missing value, assuming 0V`. Decision 15's rule would fail it, and it is a form the library accepts and LTspice reads as 0 V |
| Other `solver` fields | None needed | Every other accept fixture runs as it is, so there is no LTspice stub family |
| `.op` for a `.noise` or `.tf` file | `ensure_runs` treats those untyped commands as analyses | LTspice runs them as analyses |
| `validated` or `observed` for an entry with a mix | `validated`, with the undocumented part marked observed in `notes` | One status per entry; follows R1's "a spec-entry note marked as observed" (`LT-COM-002` `$`, `LT-TTL-001` `.title`) |
| `.model` `pn` (section 12's pin) | Pinned as stated | `pn=3M` runs and parses; `pn=OnSemi` warns in LTspice; `pn=1N4148A` stops it; the library rejects both words |
| `.tran ... steady` | Accepted, with a row | LTspice reads it, then stops on a circuit whose steady state it cannot detect; that is not syntax |

### 13.5 Corrections to what checkpoint A recorded

- **S7 was too broad.** A repeated `.model` or `.subckt` does not always stop LTspice: an unused one runs, and a used `.model` repeated with the same text runs. Rule, discrepancy row and comment corrected. The `DUPLICATE_DEFINITION` message in `document/diagnostics.py` is corrected too, message text only, LTspice only; severity is unchanged.
- **`1e3k2`** reads as 1.0002 Meg, not 1 Meg.
- **`noiseless=x`** runs when `x` is a parameter (LTspice reads it as a reference). It stops only when `x` is undefined. Added to the bare-expression row; the library still rejects it.
- **L13:** three coupled inductors in a loop with an ideal source reproduce exit 1 with no `file(line):` line, with an "over-defined circuit matrix" message. This is a better match than the two-inductor circuit recorded before, which runs when the source has `Rser`. L13's own circuit is still unknown, so the cause remains an inference.
- **N, P and Y:** all stop both, but LTspice's message for P and Y is "Expected nodes", so it may read them as undocumented letters. Recorded; nothing changed.
- `docs/usage/ltspice-export.md` said a run with no analysis has no message; the log has "No analysis specified."

### 13.6 Deviations and additions

- **File name:** T10 names `test_ltspice_corpus.py`. In `tests/solver/` that collides with `tests/grammar/ltspice/test_ltspice_corpus.py` under pytest's import mode, and collection fails, so it is `test_ltspice_solver_corpus.py`, like `test_ngspice_solver_*`.
- **`--require-solver` is now repeatable.** Before, the last value silently won, so `--require-solver ngspice --require-solver ltspice` required only LTspice, including in the checks reported in sections 9, 11 and 12. Those runs did find both solvers. M2 deferred this item.
- **Runtime in `docs/testing.md`:** T13 asks for the LTspice runtime, and decision 2 forbids committing timing numbers. I recorded one coarse sentence on the test run's duration, stated not to be a measure of LTspice. Remove it if you read decision 2 more strictly.
- **Dates:** `validated_on` uses 2026-11-01, the date on the machine that ran the probes.

### 13.7 Not verified, and one unexplained event

- **`.fra` and `.loadstate`** are on the closed list but not probed; each needs a setup of its own. `LT-DIR-001` says so and is `validated` for the rest.
- **One unexplained failure burst.** The first corpus sweep had 7 failures in a row: `sources_diodes.cir` twice, which is the warning above, and 5 others, of which the last visible was a 30 s `LTspice.exe` timeout; the output of the other 4 was not kept. It did not recur in three more sweeps, 300 repeated runs, or the full runs, so I treated it as host noise and changed nothing. A local timeout could reappear.
- **Linux and macOS** LTspice remain unverified (section 8).
- **Decision 0009** is still `proposed`, for acceptance at this review.

## 14. Checkpoint B review, round 1 (2026-11-02)

### 14.1 Outcome

T9–T13 meet the scope of section 1 and the decisions of section 2, apart from the changes in 14.2. Checks re-run for the review:

- `ruff check`, `ruff format --check`, `mypy` (configured `src/` scope), `mypy --strict` on the named test command and `lint-imports` are clean.
- The full suite with `--require-solver ngspice --require-solver ltspice` gives 3778 passed, 2 skipped, 396 deselected, and 98.81% coverage, as section 13.2 reports. `-m solver` collects 1087 tests.
- No ngspice test file or `tree_snapshot.json` changed since `0b464ae`. The `src/` changes were read: each takes effect for LTspice only.
- No LTspice raw file or log is in the working tree. All 40 `LT-*` entries are `validated`, and the rule tables have the 13 `validated` and 9 `observed` rows reported.

The edit tests assert the unedited result as well as the edited one. Probes confirmed S11 (`.param pi=3k` masks in its own scope only; `{sqrt+sqrt(9)}` with `.param sqrt=3k`; `{time+1}` stops and gives `UNRESOLVED_PARAM`; bare `{temp}`), and N1 and N2 (NFC and NFD, `straße` and `STRASSE`, `Gnd`). `$G_*` and `.global` also agree.

### 14.2 Required changes

[x] **R11 — A node name that reaches into an instance** (a candidate `disputed`; the maintainer chose the warning diagnostic, 2026-11-02). LTspice 26.1.1 connects a node named `<instance>:<node>` to that node inside the instance. The library reports a separate net, with no diagnostic. With `X1 a c s`, where `s` holds `R5 p n 1k` and `R6 n q 1k`:

```
V1 a 0 3
R1 a b 1k
R2 c 0 1k
R9 x1:n b 1k
```

| Probe | LTspice | Library |
|---|---|---|
| `R9 x1:n b 1k`, also written `X1:N` | `V(b)` = 2.625, so `R9` is joined to `n` inside `X1` | separate net `x1:n` |
| `R9 x1:q b 1k` (a port) | `V(b)` = 2.25, joined to the port's net | separate net `x1:q` |
| `a:b` with no instance, or `x7:n` with no `x7` | an ordinary node | an ordinary net (correct) |
| `x1.n` | an ordinary node | an ordinary net (correct) |

Decision 1 calls this `disputed`: an accepted form the solver reads differently, unflagged. It is also a wrong answer from the topology view, so section 13.3's "no other accepted form was found" no longer holds. The join is undocumented, and no export writes it.

Modelling the join is out of proportion for phase 1, and `a:b` must stay legal, so:

- add a warning diagnostic when the part before the first `:` of a node name folds to an instance of the same scope. The net keeps its text; the message says LTspice connects it into the instance and the library does not model that;
- add a rule row to `names.md` (`observed`), a row to `discrepancies.md`, and a known limit to architecture §7.8, through decision 0009;
- settle by probe, with solver tests: a name inside a definition (`x2:n` in a body), two levels (`x1:x2:n`), a name no instance holds (`x1:zz`), and `X§U1`, the form LTspice writes, which may be `U1:n` or `xu1:n`.

With the flag, the form no longer meets the definition of `disputed`, so `LT-NOD-001` can stay `validated`.

[x] **R12 — Remove the LTspice runtime from `docs/testing.md`.** The report asked about this (13.6). The sentence giving the suite's duration contradicts the bold line above it, "Never commit an LTspice raw file, log, or timing number", and it sits near the ngspice figure, which together reads as the comparison decision 2 keeps out. T13's request for a runtime was my error. Keep the test count, and say only that the LTspice suite runs for much longer than a normal test run and is worth starting on its own.

[x] **R13 — Probe `.loadstate` and `.fra`** (13.7). They need no setup worth skipping. `.loadstate` with no file runs in LTspice 26.1.1 and writes "no default loadstate file found", in the `file(line):` form. `.fra` takes keywords, and the reference says it requires an FRA device (`@`, phase 2), so probe it on its own and record what LTspice does; `.fra dec 10 1 1k`, which is not its form, is a syntax error there but is accepted as text here, like any argument of an untyped command. Then drop the "were not probed" note from `LT-DIR-001`, or say why one remains.

### 14.3 Developer's calls: accepted

- **`{"warning": …}` manifest field**, for the one form LTspice writes as an error line and runs.
- **S7's correction, `--require-solver` being repeatable, and the file name** `test_ltspice_solver_corpus.py`. The earlier reports' "both solvers required" should be read as "both found", as 13.6 says.
- **One status per entry, with the undocumented part marked in `notes`**, following R1.
- **The unexplained failure burst**, treated as host noise under `AGENTS.md`: it did not recur, and the full run in this review was clean. Consider one line in `docs/testing.md`: if a local LTspice timeout appears, close the GUI and rerun once.

### 14.4 Remaining before approval

- A true fresh-clone run needs a commit: section 13.2's run copied the working tree over a clone of `0b464ae`. Run it once from the commit that closes M8.
- Decision 0009 is accepted, and the list archived, at approval.

## 15. Implementation report (checkpoint B, round 1)

R11–R13 are done. Probes ran on LTspice 26.1.1 and record only syntax facts (decision 2). Section 14.4 is the reviewers', and nothing is committed.

From a clone of `0b464ae` with the working-tree changes copied on top, with both solvers required: `ruff check`, `ruff format --check`, `mypy`, `mypy --strict` on the named test command and `lint-imports` are clean, and `pytest` gives 3853 passed, 2 skipped (POSIX only), 426 deselected, 98.84% coverage. After that run only this section, the status lines and the test count in `docs/testing.md` changed; `tests/architecture` and `tests/test_usage_docs.py` were re-run on them.

### 15.1 R11: a node name that reaches into an instance

New diagnostic `NODE_INTO_INSTANCE`, LTspice only; the net keeps its text, and the signature is unchanged. Rule `N11` in `names.md` (`observed`), a new "flagged" table in `discrepancies.md`, a limit in architecture §7.8 and an entry in §17, and decision 0009 item 19. `LT-NOD-001` stays `validated`.

| Settle | Choice | Basis (`V(b)`: 3 ordinary, 2.625 joined to `n`, 2.25 joined to port `q`) |
|---|---|---|
| A name inside a definition | Looks in the instances of the same scope | `x2:n` in the body of `o` joins an `X2` of that body. `x1:n` in a body does not reach a top-level `X1` |
| Two levels | Each part follows an instance | `x1:x2:n` and `x1:x2:q` join; `x1:x2:zz` and `x1:x9:n` do not |
| `X§U1` | `u1`, removing only `X§` | `U1:n` joins; `xu1:n` and `x§u1:n` do not. `Xq1` is `xq1` (`q1:n` does not join), and `XY§U1` is `xy§u1` (`U1:n` does not join). The same holds at a second level (`x1:u2:n`) |
| A name no instance holds | **No warning** | `x1:zz` stays an ordinary node in LTspice and in the library, so a warning would be false |

**Two places this goes beyond R11's wording, for your review:**

- R11 says to warn when the part before the first `:` folds to an instance. That would also warn on `x1:zz`, which both read the same way, so the check follows the path into the definition and warns only if the node exists there.
- **Severity is not always a warning.** When the definition is in an `.include`, the library cannot see the node, so the finding is `info`, as for `UNRESOLVED_*` (section 17 of the architecture). LTspice does join in that case. If the subcircuit is simply undefined, there is only `UNRESOLVED_SUBCKT`.

**Found while settling, also flagged or recorded:**

- `x1:0`, `x1:gnd`, `x1:$G_x` and `x1:vcc` with `vcc` global stop LTspice ("Ill-formed node name"). The library accepts them, with the same code (a warning) and a message saying LTspice stops. An empty rest, `x1:`, is treated the same way.
- A `:` in a `.global` node or a `.subckt` port stops LTspice, and the library accepts it: a new row.
- `.save V(x1:n)` reads the inner node, and `.ic V(x1:n)` is accepted by both. They make no net in the library, so they get no finding. I did not measure the effect of `.ic V(x1:n)`: my probe could not tell.

**An ngspice-run test changed:** `test_every_diagnostic_code_occurs_in_the_corpus` in `tests/document/test_document_corpus.py` requires every code in the ngspice corpus, so it now leaves out this LTspice-only code. Nothing under `tests/grammar/ngspice/` and no `test_ngspice_*` file changed.

Section 13.3's "no other accepted form was found" is superseded by R11. I did not search further for other reach-in forms beyond those above.

### 15.2 R12

The runtime is gone from `docs/testing.md`. The test count stays, with the wording you asked for, and I added the optional line from 14.3 on a local timeout. No LTspice duration remains in the repository's docs; the ngspice figure next to it is unchanged.

### 15.3 R13

| Form | LTspice 26.1.1 | Library |
|---|---|---|
| `.loadstate`, `.loadstate reset` | runs, with `file(line): no default loadstate file found` | `UnknownDirective` |
| `.loadstate "s.st"` after `.savestate "s.st" time=1u` | runs | `UnknownDirective` |
| `.loadstate "nosuch.st"`, `.loadstate nosuch.st` | stops ("does not exist"; "syntax error") | accepted as text, a new row |
| `.fra`, `.fra Tstart=0 dTmax=1u Tstep=1u Tstop=1m`, no device | past the syntax, then stops: "requires at least one enabled fra device" | accepted, a new row |
| `@1 a b fstart=1k ...` with `.fra` | runs | `UnsupportedConstruct` for `@` (phase 2) |
| `.fra dec 10 1 1k`, `.fra foo=1` | "syntax error" | accepted as text, a new row |
| `.fra` or `.loadstate` in a body | stops | `ParseError` |

The "were not probed" note is gone from `LT-DIR-001`; nothing on the closed list remains unprobed.

## 16. Checkpoint B review, round 2 (2026-11-02) — approved

R11–R13 are done as section 15 reports, and M8 is approved. Checks re-run for the review:

- `ruff check`, `ruff format --check`, `mypy` (configured `src/` scope), `mypy --strict` on the named test command plus `tests/test_ltspice_raw_reader.py`, and `lint-imports` are clean.
- The full suite with `--require-solver ngspice --require-solver ltspice` gives 3853 passed, 2 skipped, 426 deselected, and 98.84% coverage.
- Nothing under `tests/grammar/ngspice/` changed since `0b464ae`, and the one ngspice-run test changed, `test_every_diagnostic_code_occurs_in_the_corpus`, only leaves out the LTspice-only code.

`NODE_INTO_INSTANCE`, probed against LTspice 26.1.1, flags each form LTspice joins and none it does not:

| Form | LTspice | Library |
|---|---|---|
| `x1:n`, `X1:N`, `x1:q` (a port), `x3:n` (a second instance) | joined | warning |
| `x1:x2:n`; `U1:n` for `X§U1` | joined | warning |
| A definition after its use; the name as an `X` node or on a source | joined | warning |
| The definition in an `.include` | joined | info |
| `a:b`, `x1:zz`, `xu1:n` for `X§U1` | ordinary node | no finding |
| `x1:gnd` | stops | warning that says it stops |

An edit keeps the finding, and the signature does not change.

**Accepted, beyond R11's wording:**

- following the path into the definition, so that `x1:zz` gets no false warning;
- `info` when the definition is in an include, as for `UNRESOLVED_*`.

**Probe the developer could not settle:** `.ic V(x1:n)=1` showed no difference in `V(b)` at the end of a short `uic` run, which does not show its effect on the inner node. It makes no net in the library, so nothing depends on it.

**Observations (not required):**

- `NODE_INTO_INSTANCE` occurs only in tests, not in an LTspice corpus file. A small fixture would extend the "every code occurs in a corpus" idea to LTspice.
- The diagnostic quiets nothing else: `.backanno` still gives `UNKNOWN_DIRECTIVE_PRESERVED` on every export (9.4), which phase 2 may revisit.

**Fresh-clone run (section 14.4), done 2026-11-02:** a clean clone of `93da644`, the commit that closes M8, with a new environment and both solvers required. `ruff check`, `ruff format --check`, `mypy`, `mypy --strict` on the named test command plus `tests/test_ltspice_raw_reader.py`, and `lint-imports` are clean, and `pytest` gives 3853 passed, 2 skipped, 426 deselected, and 98.84% coverage.

Decision 0009 is accepted with this review.
