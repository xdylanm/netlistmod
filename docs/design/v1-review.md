# v1 review package

> **Status:** DRAFT — T1's results are filled in when the clean-clone run ends; then `READY FOR REVIEW`
> **Part of:** [m19-tasks.md](./m19-tasks.md) (T2). The gate is [phase-2-plan.md](./phase-2-plan.md) section 6. Phase 1's package is [phase-1-review.md](./archive/phase-1/phase-1-review.md).

## 1. Where things stand

| Item | State |
|---|---|
| Implementation (M10 to M17) | Complete: every device letter of both matrices is `supported`, apart from the two named exclusions |
| Completeness audit (M18) | Complete; [decision 0021](../decisions/0021-completeness-audit.md) |
| Reviews (M19 A1 to A3) | Done; findings in [m19-tasks.md](./m19-tasks.md) section 5.1 |
| Documents and tests (M19 D1 to D5) | Done and committed; [decision 0022](../decisions/0022-v1-record-corrections.md) is proposed |
| Final evidence (T1) | Section 2 |
| Your own use (gate item 7) | Done (maintainer, 2026-11-11): "all good" |
| Limits (gate item 8) | Section 5.1 decided (maintainer, 2026-11-11); 5.2 confirmed with the package's approval |
| The `0.9.0` release | After the gate, on a `release-0.9.0` branch (m19 decision 5); checklist in section 9 |

## 2. Results

*T1 is running: a clean clone of the commit under review, with a new environment, on Windows with Python 3.14.3, ngspice 47 and LTspice 26.1.1, both solvers required. Run times are not recorded (m19 5.1.1 point 5).*

| Check | Result |
|---|---|
| `pytest --require-solver ngspice --require-solver ltspice` | *pending* |
| Coverage | *pending* (the floor is now 98%) |
| `ruff check`, `ruff format --check` | *pending* |
| `mypy` (configured `src/` scope), and `mypy --strict` on the named tests | *pending* |
| `lint-imports` | *pending* |
| `pre-commit run --all-files` | *pending* |
| Wheel and sdist build; wheel installed in a new environment, then a parse and an edit on both dialects | *pending* |
| Solver-free suite on `lark` 1.2.2, the declared lower bound | *pending* |
| Linux, and Python 3.13 | CI on the M19 pull request (no solver; decision 0011) |

## 3. Coverage

From the baseline run (m19 section 3.2), with D5's tests added. Modules not listed are at 100%.

*The per-module table is filled in from T1's report.*

Each line left uncovered, from A3's review (each one read, and probed where it looked reachable):

| Lines | What it is | Disposition |
|---|---|---|
| `edit/_ops_common.py:262` | An LTspice removal's join meets a line that is not a `+` line; the grammar refuses a comment or blank line between `+` lines | Accepted: defensive, left to verification |
| `edit/_ops_directives.py:124, 126` | Describing an opaque item in a message; `_directive_line` does not pass them | Accepted: dead for now, harmless (phase 1) |
| `edit/_ops_elements.py` 185→187 | A T line with `Z0`/`Zo` written other than once; the grammar refuses both | Accepted: defensive |
| `edit/api.py:46, 49` | Abstract methods of the editing base | Accepted (phase 1) |
| `edit/verify.py` 181→183 | A dataclass with no `span` in the walk | Accepted: defensive (phase 1) |
| `grammar/formula.py:65`, `grammar/loader.py:675`, `model/model_types.py:29` | A packaged JSON file has the wrong shape | Accepted: a packaging fault, and the tests that read the real files would fail first (phase 1) |
| `grammar/formula.py:82` | A formula whose tree is a single token | Accepted; reachability not established (phase 1) |
| `grammar/loader.py:328-329` | A dialect with no grammar | Accepted: every `Dialect` has one (phase 1) |
| `grammar/loader.py:354-355`, 466→490 | Lark's `UnexpectedCharacters` path; a fuzz of 30,000 lines per dialect did not reach it, since the contextual lexer reports `UnexpectedToken` | Accepted; reachability not established (phase 1) |
| `grammar/loader.py:375, 416` | Lark gave no interactive parser | Accepted: defensive (phase 1) |
| `grammar/loader.py:521, 592, 596`, 631→636 | Branches of the loader's own messages that the parser's stacks do not produce | Accepted: defensive |
| `model/_rules_nonlinear.py:404` | A POLY pair running past the control nodes; the count and the grammar prevent it | Accepted: defensive |
| `model/_rules_sources.py` 99→87 | A stimulus field of another type; no grammar path gives one | Accepted: defensive |
| `model/_tree.py:289, 298`, `model/transform.py:67, 99` | Lark gave no positions, an unhandled rule, or a foreign exception | Accepted: internal faults that fail loudly (phase 1) |
| `source.py:191` | Saving through a symlink | Covered by a test that runs on Linux CI only |
| `source.py:211-212, 216, 228` | A temporary-file name collision, and cleanup after one | Accepted: hard to force, and the write stays atomic (phase 1) |

The eight reachable paths that had no test (A3-1) are tested by D5.

## 4. Spec coverage

Each grammar README holds the generated "Validation status" table, with every entry's status, test counts and validation dates (decision 0021 item 8; m19 decision 8):

- **ngspice:** 75 entries: 73 `validated`, 2 `observed` ([table](../grammars/ngspice/README.md#validation-status)).
- **LTspice:** 73 entries: 73 `validated` ([table](../grammars/ltspice/README.md#validation-status)).

No entry is `documented` or `disputed`. `observed` means the solver's behaviour with no manual statement behind it (§11.3).

## 5. Limits for your decision

Collected by A2 from the phase 1 review, decisions 0010 to 0022, the task lists, the plan's risks, architecture §7.8 and §21 and both `discrepancies.md` files; deduplicated. "Decided" means a decision record or the maintainer already accepted it; the gate asks whether the whole list is acceptable for v1.

### 5.1 Open

1. **Library files** (decision 0012 item 6; §21): opening a library file, and editing a model inside a `.lib` section. To decide after using the beta. **Accepted (maintainer, 2026-11-11).**
2. **What 1.0 commits to in the public API** (§18): reviewed after your practical use. Section 6 lists the notes for it. **Accepted (maintainer, 2026-11-11).**
3. **Your hands-on checkpoint** (M13 T14; gate item 7), and whether anything you find changes what comes after v1. **Done (maintainer, 2026-11-11):** all good.
4. **Two loads that a reviewer questioned** (A3-14, A3-15; m19 5.1.1 point 2): on ngspice `R1 a 0 1k |` reads `|` as the R's model, and on both dialects `D1 a 0 2` reads `2` as the diode's model. Each gives `UNRESOLVED_MODEL` (a warning), so neither is silent. Recorded for the 1.0 review. **Accepted (maintainer, 2026-11-11).**
5. **Cosmetic:** `__all__` is not sorted; LTspice's message for an unset gain; a formula after a Q model gets the generic message. **Accepted (maintainer, 2026-11-11).**
6. **Decision wording:** decision 0016 item 1 speaks of "the expression forms of E, F, G and H" on ngspice, but ngspice F and H have no such form (`F1 a 0 value={…}` is a `ParseError`, as the manual has it). The behaviour is right; the record's wording is loose (found in D3a). **Fixed (maintainer, 2026-11-11):** decision 0016 item 1 now names the forms per letter, through decision 0022 item 6.

### 5.2 Decided, carried into v1

| Limit | Source |
|---|---|
| The ngspice digital U and LTspice `.machine` raise `UnsupportedConstruct` | Decisions 0020 items 1 and 11, 0021 item 11 |
| LTspice requires `.end`, although LTspice lets it be omitted | Decisions 0009 item 4, 0012 item 3 |
| 21 lookaround terminals are not collision-checked by strict mode; reviewed by hand and pinned | Decision 0021 item 7 |
| Deep `.if` nesting raises `RecursionError` at about 240 levels | Phase 1 review; `errors.md` |
| Opaque contents are not verified: an added `.if`, `.include` or `.lib` item may bring element lines | §7.8, §7.9 |
| A `.lib` block is opaque, and its body is not topology | Decision 0012 item 1 |
| No stress or performance testing | Decision 0010 item 3; plan section 8 point 6 |
| `directives.add` is not an upsert; `directives.set` is | Decision 0012 item 2 |
| Combinations of analyses are not refused (LTspice stops on `.tran` with `.ac`) | M11 |
| No macOS; CI installs no solver; all solver evidence is Windows, ngspice 47 and LTspice 26.1.1 | Decision 0011; m19 decision 10 |
| Expression reads are not topology, and an expression edit may change them; `expression_reads` and `UNRESOLVED_NODE` report them | §7.8; decisions 0016 item 6, 0017 item 7 |
| Reaches into an instance (`X1:n`, `X1:Vq`, `v(x1.n)`) are not resolved; they are info | Decisions 0009, 0015 item 4, 0016 item 6 |
| `.include` and `.lib` contents are not read; their names are unresolved (info), and `set_model` needs `allow_external=True` | Decisions 0006, 0007, 0012 item 5 |
| A 3-node ngspice Q grounds its substrate; the signature records only the nodes written | Decision 0014 item 3 |
| Node counts are checked per letter, not per model; A port counts and types, N node counts and P/CPL value counts are not checked | Decisions 0014 item 2, 0019 item 9, 0020 items 4 and 6 |
| Solver inputs are not validated: stimulus argument counts, model contents, `.options` (`reject_number_tails`), `.fra` values | Decisions 0013 item 6, 0019, 0020, 0021 items 5 and 9 |
| Replacement text is checked only by its slot | §7.8; decision 0007 |
| Forms that load and that a solver stops on or reads differently: about 21 LTspice rows (among them a comment-only last `+` line and an unknown `.model` type) and about 10 ngspice rows | Both `discrepancies.md`; decision 0021 item 5 |
| Forms a solver runs that the library refuses (P5): about 78 ngspice rows and 49 LTspice rows | Both `discrepancies.md` |
| The recorded exceptions to decision 0002 (RKM, `SINE`, `Z0`/`Zo`, the 13 LTspice A names, LTspice's `.end`) | Decision 0022 item 1 |
| The places where the loader reads tokens outside the grammar (P13): the splits of `AKO_REF`, `STEP_MODEL_REF` and `v(`, and messages read from the parser's stack | Decisions 0010 item 6, 0021 item 10 |
| Edit restrictions: no `pchan`/`nchan` edit; LTRA flags, the LTspice A function and `zm` are not editable; a table or POLY count cannot change across a comment; `set_stimulus` drops a comment inside its span | Decisions 0013, 0014 item 7, 0017 item 6, 0019 item 11, 0020 item 9 |
| A `.model` line cannot be added or removed, and a `.param` line cannot be removed | Decision 0007; `editing.md` |
| Y and P reference nodes must be ground; P takes at most 8 lines | Decision 0019 items 5 and 6 |
| `@`'s `refnode=`/`intnode=` and `&`'s analyzer are references, not topology | Decision 0020 items 7 and 8 |
| `NG-OSD-001` needs the `r2_cmc.osdi` that ngspice 47 ships, and some corpus runs need `OPENJELLYBEAN_LIB`; they skip without them | Decisions 0020 item 6, 0014 item 10 |
| The spec checker recognises an accept test by its name, and does not prove that a solver test runs | Decision 0021 item 8 |
| T9 (differential testing) and the optional observation files are not done | §10.2, §10.3 |
| qspice and xyce are planned, not in v1 | §9.2 |
| README links are relative, so they are dead on PyPI; a release can only be yanked | Decision 0018 items 4 and 6; m19 5.1.1 point 6 |
| The local suite keeps growing and is not split | Plan risk 8 |

Closed since phase 1: Q, M and stimulus specs (M12 to M17), Python 3.13 (CI since M10), the `.lib` block's topology (M11) and the lookaround review (M18).

## 6. Notes for the 1.0 API review

From A1's reading of the guides as a new user (section 1 of m19 keeps these out of M19):

1. An LTspice B line's `laplace=` is a parameter, while E and G's `Laplace=` is an expression edited with `set_expression`.
2. `set_value` means three things: a value, the DC value of V and I (overlapping `set_dc`), and a refusal on K that points to `set_coupling`.
3. `apply_edits(text, plan)` is public and splices with no verification, beside `Netlist.apply`, which verifies: a public path around P4.
4. `Diagnostic.code` is an enum, but `severity` is a plain string.
5. A read of a missing name raises `KeyError`, an edit of it `EditError`.
6. `Netlist.text` and `Netlist.source.text` are the same.
7. Names: `Vcvs`, `Vccs`, `Cccs`, `Ccvs` beside `VoltageSource`; `BehavioralSource` in US spelling; `net.global_`; `lines.insert_after()` returns a `Span` and inserts nothing.
8. A `.param` can be set but not removed, and a `.model` edited but neither added nor removed.
9. A double-quoted LTspice string (`PWL file="w.txt"`) is a `Formula` with `delimiter='"'`.
10. Scopes are tuples in edits (`scope=("amp",)`) and `Scope` objects in `netlist.scopes`.
11. `in_definition=True` on every edit method, where a scoped editor might read better.

## 7. Gate checklist

Plan section 6.

| Gate item | Evidence | State |
|---|---|---|
| Every element in both matrices is `supported`, and the full range of value specifications is covered | Both device matrices and their JSON files; `test_contracts.py::test_no_device_letter_is_planned`; decision 0021 items 1, 3 and 9 and the value probes | Met |
| Every construct has a spec entry and tests; spec coverage and strict grammar checks pass | Section 4; `tests/architecture/test_spec_coverage.py`, `test_contracts.py` | Met; T1 repeats them |
| Round trip is byte-exact across the corpus; golden edit diffs show only intended changes | `tests/roundtrip/`, `tests/test_corpus_manifests.py`, `test_edit_golden.py`, `test_ltspice_edits.py` | Met; T1 repeats them |
| The topology guarantee covers the new elements, with controlling references, by negative and property tests | `test_controlled_edits.py`, `test_edit_negative.py`, `test_nonlinear_edits.py`, `test_device_edit_properties.py`, `test_device_oracle.py`, `test_signature_snapshot.py` | Met |
| CI is green on Linux and Windows, on Python 3.13 and 3.14 | `.github/workflows/ci.yml`; green on `main` after M18 | The M19 pull request's run |
| ngspice and LTspice solver tests pass on your machine | Section 2 | T1 |
| You have used the library on your own netlists, including transistor and behavioural circuits | Section 8; the maintainer, 2026-11-11 | Met |
| Remaining limits are documented and acceptable | Section 5 | 5.1 decided by the maintainer on 2026-11-11; 5.2's limits were each decided earlier, and are confirmed with the package's approval |
| All task lists are archived, and the plan is archived as `COMPLETE` | M10 to M18 are archived; this package, m19 and the plan move at m19 T4 | After your approval |

## 8. Suggested hands-on script

About an hour. Use copies of your netlists, under version control. Prefer the transistor and behavioural circuits from your own KiCad and LTspice projects; the corpus copies are in `tests/corpus/ngspice/kicad_transistors`, `tests/corpus/ltspice/ltspice_transistors` and both `controlled_sources` families.

1. **Load each netlist,** with the dialect explicit, and look at what it holds:
   ```bash
   uv run --env-file .env python docs/usage/examples/read_only_demo.py my_amp.cir --dialect ngspice
   ```
   A refusal is the most useful finding: note whether the message says what to do.
2. **Check an unedited save** gives the same bytes, and that `netlist.elements()`, `netlist.nets()` and `netlist.connections("Q1")` match the schematic.
3. **Edit a transistor:** `set_model`, `set_param` (an area), `set_model_param` (a `BF`), then `save()` and read the `git diff`.
4. **Edit a behavioural circuit:** `set_expression` on a B or an E `value=`, `set_table` or `set_poly_coefficients` where you use them, and `netlist.expression_reads("B1")` before and after.
5. **Try to break it:** change a controlling source with `set_formula`, give `set_model` a model that does not exist, `directives.add("Q9 a b c qn")`. Each should refuse and write nothing.
6. **Run it** with the demo, which edits one value, runs `.op` and prints a net's voltage (from PowerShell if a net name starts with `/`):
   ```bash
   uv run --env-file .env python docs/usage/examples/edit_and_simulate.py my_amp.net --dialect ltspice --edit-value="R1,3k" --probe="out"
   ```
7. **Note anything awkward,** for section 5.1 points 2 and 3.

## 9. Release checklist for `0.9.0`

After the gate, on a `release-0.9.0` branch (m19 decision 5; decision 0018):

1. `pyproject.toml`: `version = "0.9.0"`, and the classifier `Development Status :: 4 - Beta`.
2. `uv.lock`: the project's own version (CI runs `uv sync --locked`; run `uv lock`).
3. `CHANGELOG.md`: `## Unreleased` becomes `## 0.9.0 — date`.
4. `README.md`: the release line ("The current release is the `0.5.0` alpha").
5. Optional (A3-4, A3-10): anchor the sdist's `README.md` and `LICENSE` patterns in `[tool.hatch.build.targets.sdist]`, which now also take the `README.md` files under `docs/`; extend the release workflow's smoke test to a phase 2 element on each dialect.
6. Merge on green, tag `v0.9.0` on `main`, and publish the GitHub Release, which publishes to PyPI.
