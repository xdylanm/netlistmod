# Phase 1 review package

> **Status:** ACTIVE — written with M9 T9. Its results are interim until T10 repeats them from a fresh clone, once H1–H4 are committed. Archived with the plan once the gate passes.
> **Part of:** [m9-tasks.md](./m9-tasks.md). The gate is [phase-1-plan.md](./phase-1-plan.md) section 6.

## 1. Where things stand

| Item | State |
|---|---|
| Implementation (M0–M8) | Complete |
| Review findings | [m9-tasks.md](./m9-tasks.md) section 7 |
| Required code changes (H1–H4) | [m9-code-changes.md](./m9-code-changes.md): made and reviewed, with the review's fixes (section 5 there); not yet committed |
| Final evidence (T10) | **Not yet run:** waits for H1–H4 to be committed |
| The maintainer's own use | Not yet done: section 7 below is a suggested script |

## 2. Results so far

Run on Windows with Python 3.14.3, ngspice 47 and LTspice 26.1.1, on the working tree over `2127bb3`, before H1–H4. Both solvers were required (`--require-solver ngspice --require-solver ltspice`).

| Check | Result |
|---|---|
| `pytest` | 4405 passed, 2 skipped (POSIX only), 445 deselected (the other dialect's run of a one-dialect test) |
| Coverage | 98.84% (24 lines and 17 branches uncovered); the gate is 90% |
| `ruff check`, `ruff format --check` | Clean |
| `mypy` (configured `src/` scope) | Clean |
| `mypy --strict` on test support, the solver tests and the new doc tests | Clean |
| `lint-imports` | Contract kept |
| Python 3.13 | **Untested** (maintainer, 2026-11-02) |

## 3. Coverage

Per module, from that run. Modules not listed are at 100%.

| Module | Cover | Uncovered |
|---|---|---|
| `document/models.py` | 90% | 25 |
| `edit/api.py` | 99% | 46, 49 |
| `edit/operations.py` | 99% | 574, 576 |
| `edit/verify.py` | 99% | branch 163→165 |
| `grammar/formula.py` | 95% | 65, 82 |
| `grammar/loader.py` | 94% | 197–198, 222–223, 238, branch 291→304, 328 |
| `model/transform.py` | 99% | 286, 295, 364, 377, 1123, 1327 |
| `source.py` | 96% | 191, 211–212, 216, 228 |

Each uncovered line:

| Lines | What it is | Disposition |
|---|---|---|
| `models.py:25`, `formula.py:65`, `loader.py:328` | A packaged JSON data file has the wrong shape | Accepted: a packaging fault, and the tests that read the real files would fail first |
| `api.py:46, 49` | Abstract methods of the shared editing base | Accepted |
| `operations.py:574, 576` | Describing an opaque item in a message; `_directive_line` accepts those items, so they do not reach it | Accepted: dead for now, harmless |
| `verify.py` 163→165 | A dataclass in the walk with no `span` | Accepted: a defensive branch |
| `formula.py:82` | A formula whose tree is a single token | Accepted; reachability not established |
| `loader.py:197–198` | A dialect with no grammar | Accepted: every `Dialect` has one, and a test pins that |
| `loader.py:222–223, 238`, 291→304 | Lark's other error paths. A probe with a bad character did not reach 223 or 238 | Accepted; reachability not established |
| `transform.py:286, 295, 364, 1327` | Lark gave no positions, an unhandled rule, or a foreign exception | Accepted: internal faults that fail loudly |
| `transform.py:377, 1123` | Whitespace after `.end` with no newline; a comment before a `.step` item | **Now tested** (`tests/grammar/test_broad_oracle.py`): a probe showed both are reachable |
| `source.py:191` | Saving through a symlink | Covered by a test that runs only on POSIX |
| `source.py:211–212, 216, 228` | A temporary-file name collision, and cleanup after one | Accepted: hard to force, and the write stays atomic |

## 4. Gate checklist

Plan section 6. Only the maintainer can tick these.

| Gate item | Evidence | State |
|---|---|---|
| All phase 1 constructs have spec entries and tests; spec-coverage and strict-grammar checks pass | Section 5; `tests/architecture/test_spec_coverage.py`, `test_contracts.py` | Ready, pending T10 |
| Round-trip is byte-exact across the corpus; golden edit diffs show only intended changes | `tests/roundtrip/`, `test_edit_golden.py`, `test_ltspice_edits.py`, `tests/grammar/test_broad_oracle.py` | Ready, pending T10 |
| The topology guarantee is demonstrated by negative and property tests | `test_edit_negative.py`, `test_edit_properties.py`, the broad oracle's edits | Ready, pending T10 |
| ngspice and LTspice solver-backed tests pass on your machine | Section 2; T10 repeats it from a fresh clone | Ready, pending T10 |
| You have used the library on at least one of your own netlists | Section 7 | **Maintainer** |
| The §21 questions resolved in M6 are recorded as decision records, and new findings are logged | Decisions 0007–0010; [m9-tasks.md](./m9-tasks.md) section 7 | Ready; decision 0010 awaits acceptance |
| The phase 1 limitations are acceptable, or the phase 2 plan is adjusted | Section 6 | **Maintainer** |
| All milestone task lists are archived, and the plan is archived as `COMPLETE` once the gate passes | M0–M8 archived; M9 follows T11 | After the gate |

**Also to accept:** decision 0010 (T11). Decisions 0002 and 0003 were accepted on 2026-11-02.

## 5. Spec coverage

Generated by `python -m tests.support.spec_coverage`; a test fails if this section differs from its output. "Tests" counts the test references in each entry. `observed` means solver behaviour with no manual statement behind it, recorded as such (§11.3).

<!-- spec-coverage:begin -->
**ngspice:** 39 entries: 3 `observed`, 36 `validated`.

| Entry | Construct | Status | Tests |
|---|---|---|---|
| `NG-ACA-001` | .ac small-signal analysis | validated | 8 |
| `NG-CAP-001` | capacitor (C) lines | validated | 6 |
| `NG-CNT-001` | immediately adjacent continuation lines (+ and trailing \\) | validated | 12 |
| `NG-COM-001` | full-line star comments | observed | 3 |
| `NG-DCA-001` | .dc transfer function | validated | 8 |
| `NG-DIO-001` | junction diode (D) lines | validated | 4 |
| `NG-DIR-001` | unknown dot-commands and stray block terminators | validated | 9 |
| `NG-END-001` | required final .end statement | validated | 4 |
| `NG-FLD-001` | element field separators: blanks, one comma, = with blanks, continuation | validated | 7 |
| `NG-FML-001` | Formula expression syntax (reference scan only) | validated | 9 |
| `NG-GLB-001` | .global node declarations | validated | 5 |
| `NG-ICN-001` | .ic and .nodeset | validated | 10 |
| `NG-IND-001` | inductor (L) lines | validated | 4 |
| `NG-MEA-001` | .meas / .measure (shallow) | validated | 8 |
| `NG-MOD-001` | .model statements | validated | 10 |
| `NG-MUT-001` | mutual coupling (K) lines | validated | 3 |
| `NG-NOD-001` | node, model, subcircuit and parameter names | validated | 9 |
| `NG-NUM-001` | numbers: sign, mantissa, exponent and scale factor | validated | 6 |
| `NG-NUM-002` | letters following a number | validated | 2 |
| `NG-NUM-003` | RKM notation for R and C values (parser option rkm) | validated | 9 |
| `NG-NUM-004` | micro sign as a scale factor | observed | 3 |
| `NG-OPA-001` | opaque .control and nested .if blocks | validated | 4 |
| `NG-OPA-002` | opaque .include and .lib statements | validated | 4 |
| `NG-OPP-001` | .op operating point | validated | 8 |
| `NG-OPT-001` | .options / .option | validated | 10 |
| `NG-PAR-001` | instance parameters, model references and the off flag | validated | 8 |
| `NG-PRM-001` | .param assignments | validated | 10 |
| `NG-RES-001` | resistor (R) lines | validated | 6 |
| `NG-SAV-001` | .save output vectors | validated | 10 |
| `NG-SBD-001` | .subckt ... .ends definitions and their bodies | validated | 18 |
| `NG-SRC-001` | independent sources (V, I): DC value and AC magnitude and phase | validated | 5 |
| `NG-STR-001` | top-level source structure | validated | 6 |
| `NG-SUB-001` | subcircuit calls (X) | validated | 5 |
| `NG-TMP-001` | .temp | validated | 8 |
| `NG-TRN-001` | .tran transient analysis | validated | 9 |
| `NG-TTL-001` | implicit first-line title and explicit .title | validated | 2 |
| `NG-TXT-001` | free text, quoted and braced segments, and trailing comments | observed | 9 |
| `NG-UNS-001` | recognised but unsupported element forms | validated | 9 |
| `NG-VAL-001` | brace and quoted expressions, and string parameter values | validated | 10 |

**ltspice:** 40 entries: 40 `validated`.

| Entry | Construct | Status | Tests |
|---|---|---|---|
| `LT-ACA-001` | .ac | validated | 5 |
| `LT-CAP-001` | capacitor (C) lines | validated | 8 |
| `LT-CNT-001` | + continuation lines | validated | 5 |
| `LT-COM-001` | comment lines (* and ;) | validated | 4 |
| `LT-COM-002` | end-of-line comments (; and space-$-space) | validated | 5 |
| `LT-DCA-001` | .dc | validated | 6 |
| `LT-DIO-001` | diode (D) lines | validated | 7 |
| `LT-DIR-001` | closed list of dot-commands | validated | 12 |
| `LT-END-001` | required final .end | validated | 4 |
| `LT-FLD-001` | field separators | validated | 5 |
| `LT-FML-001` | formula expression syntax (reference scan only) | validated | 6 |
| `LT-GLB-001` | .global | validated | 5 |
| `LT-ICN-001` | .ic and .nodeset | validated | 9 |
| `LT-IND-001` | inductor (L) lines | validated | 6 |
| `LT-MCH-001` | .machine blocks | validated | 2 |
| `LT-MEA-001` | .meas and .measure | validated | 5 |
| `LT-MOD-001` | .model statements | validated | 9 |
| `LT-MUT-001` | mutual inductance (K) lines | validated | 6 |
| `LT-NOD-001` | node, element and subcircuit names | validated | 8 |
| `LT-NUM-001` | numbers | validated | 2 |
| `LT-NUM-002` | letters following a number | validated | 4 |
| `LT-NUM-003` | embedded decimal | validated | 5 |
| `LT-NUM-004` | micro signs | validated | 4 |
| `LT-OPA-001` | opaque .include, .inc and .lib | validated | 4 |
| `LT-OPP-001` | .op | validated | 2 |
| `LT-OPT-001` | .options, .option and .opt | validated | 4 |
| `LT-PRM-001` | .param assignments | validated | 8 |
| `LT-RES-001` | resistor (R) lines | validated | 9 |
| `LT-SAV-001` | .save | validated | 7 |
| `LT-SBD-001` | .subckt ... .ends definitions | validated | 7 |
| `LT-SRC-001` | independent sources (V, I) | validated | 11 |
| `LT-STP-001` | .step | validated | 11 |
| `LT-STR-001` | top-level source structure | validated | 6 |
| `LT-SUB-001` | subcircuit calls (X) | validated | 5 |
| `LT-TMP-001` | .temp | validated | 4 |
| `LT-TRN-001` | .tran | validated | 5 |
| `LT-TTL-001` | implicit first-line title and .title | validated | 3 |
| `LT-TXT-001` | statement text | validated | 3 |
| `LT-UNS-001` | recognised but unsupported forms | validated | 8 |
| `LT-VAL-001` | brace and quoted expressions | validated | 5 |
<!-- spec-coverage:end -->

## 6. Limits for your decision

From [m9-tasks.md](./m9-tasks.md) section 5. M9 records these and resolves none of them.

1. **Opaque statements, no stimulus specs, unsupported letters.** Netlists with Q or M devices, or `PULSE` or `SIN` sources, are rejected until phase 2. Note that this rejects `half_rectifier.net` from your own schematics.
2. **`.end` is required for LTspice,** although LTspice lets it be omitted (decision 0009: "revisit after the phase 1 review").
3. **Lookaround terminals** are not collision-checked by strict mode: a test pins the list, and rewriting them is an open question.
4. **About 300 nested `.if` levels** raise `RecursionError`.
5. **An added `.if` block may contain element lines:** opaque contents are not verified (§7.8).
6. **A `.lib name` … `.endl` block is not recognised:** its body is read as top-level lines, so its elements count as topology.
7. **Python 3.13 is untested.**
8. **No stress or performance testing, and no CI,** by decision 0010.
9. **`directives.add` is not an upsert.** `directives.add(".tran …")` over an existing `.tran`, or followed by `directives.set` in a batch, writes two `.tran` lines. ngspice runs both analyses and LTspice stops.
10. **Whether phase 2's order should change,** based on your hands-on use.

## 7. Suggested hands-on script

About half an hour. Use a copy of each netlist, under version control or beside the original.

1. **Load your own netlist,** with the dialect explicit. A failure here is the most useful finding: note whether the message told you what to do.
   ```python
   from netlistmod import Dialect, Netlist

   netlist = Netlist.load("my_circuit.net", dialect=Dialect.LTSPICE)
   print(len(netlist.lines), [d.code.value for d in netlist.diagnostics])
   ```
2. **Check an unedited save.** Save to a new path and compare the bytes with your file.
3. **Read it back.** Do `netlist.elements()`, `netlist.nets()` and `netlist.connections("R1")` match the schematic?
4. **Make your usual edits:** a value, a formula with a new `.param`, an analysis with `directives.set`, and a harness with `add_include`. After `save()`, read `git diff`: only the intended text should change.
5. **Try to break it.** Edit an element that does not exist, set a value to `1k 2k`, and call `directives.add("R9 a 0 1k")`. Each should refuse, and nothing should be written.
6. **Run it.** Run the edited file in your solver, or start from the demo:
   ```bash
   uv run --env-file .env python docs/usage/examples/edit_and_simulate.py --dialect ltspice
   ```
7. **Note anything awkward,** especially what is rejected. That feeds section 6's last item.
