# M12 task list — Stimulus specs

> **Status:** READY FOR REVIEW — T1–T10 are done, with the results in section 5; T11 follows the maintainer's approval
> **Part of:** [phase-2-plan.md](./phase-2-plan.md) (milestone M12). Governed by [architecture.md](../architecture.md) (§2, §5.3, §7.1, §7.2, §10).

## 1. Scope

M12 replaces the rejected `stimulus` rule with a typed `SourceSpec`, so that source functions load and can be edited on both dialects.

- **In:**
  - **ngspice** (`[ngspice-manual] §4.1`): PULSE, SIN, EXP, PWL, SFFM, AM, TRNOISE, TRRANDOM, EXTERNAL, DISTOF1 and DISTOF2, and the RF port parameters (decision 6).
  - **LTspice:** PULSE, SINE, EXP, SFFM, PWL with its file, repeat and scale forms, `wavefile=`, the trigger parameters, and for I `tbl=`, `step(...)`.
  - **Edit API:** set a whole stimulus, set one argument, remove a stimulus.
  - Solver tests, spec entries, golden diffs and docs for each function.
- **Not in M12:**
  - Other device letters, including behavioural B (M15).
  - Reading a PWL or wave file; a path is text, as an `.include` path is (§7.8).
  - Checking a function's argument count or values (decision 5).
  - Reporting the nets a `Trigger=` expression reads. It is kept as text, and M15's read-only query covers it (plan section 8, point 1).

**Exit:** `half_rectifier.net` loads and edits, its solver test passes on LTspice, and each function has a spec entry, golden diff and solver test.

## 2. Decisions (maintainer, 2026-11-04)

Based on the probes in section 3. "Alternative" marks an option considered and not chosen.

1. **Field order: accept a function before or after DC and AC, at most one of each.** The manual's examples put the function last, but `SIN(0 1 1k) AC 1` and `SIN(0 1 1k) DC 1` run on both solvers and read the same. **Refuse two things that read differently:**
   - A bare value after a function (`SIN(0 1 1k) 1`): ngspice runs it and the output becomes 0, and LTspice stops.
   - Two functions: ngspice uses the last, and LTspice stops.

   *Alternative:* the manual's order only, which would refuse the `SINE(...) AC 1` style.
2. **Forms beyond the manual: follow the manual, with `SINE` as the one exception.**
   - **Parentheses are required,** although both solvers run `PULSE 0 1 1u`. Decision 0002 stands: solver behaviour does not widen the manual. The forms that have no parentheses in the references stay: EXTERNAL, DISTOF1 and DISTOF2, and LTspice's documented `PWL FILE=`, `PWL REPEAT …` and scale-factor forms. `PWL(file=x)`, which LTspice runs and its reference does not show, is refused.
   - **A blank before the parenthesis is accepted,** on both dialects. The manual's own example is `trrandom (2 10m 0 1)`, and a blank is a separator, not another form.
   - **`SINE` is accepted on ngspice, as a named exception to decision 0002.** ngspice runs it and reads it as `SIN`, and its manual does not list it. It goes in `discrepancies.md`.
   - **A bare parameter name as an argument is refused,** `PULSE(0 x)` for `PULSE(0 {x})`. ngspice runs it and LTspice stops. It is not in the manual, and without braces the library would not see the reference to `x`. It goes in `discrepancies.md`.
3. **`set_stimulus` leaves DC and AC alone, and the usage guide says how to edit them.** It changes only the function's text, and with no function it adds one after the DC and AC parts. `docs/usage/editing.md` shows `set_dc` and `set_ac` beside a function. An AC part is still needed for `.ac`, and removing a DC value would be a second edit the caller did not ask for. A solver test records what each solver does with a DC value beside a function. *Alternative:* replacing them, which changes more text than the edit names.
4. **The edit API has three operations, addressed by position or written name.**
   - `set_stimulus(designator, text)` replaces or adds the whole function, for example `"PULSE(0 1 1u)"`. Changing function is therefore a single edit.
   - `set_stimulus_arg(designator, key, value)` takes a 0-based position, or a name that the line writes as `name=value`, such as `td`, `Trigger` or `chan`. A position one past the end appends. A position further on is an `EditError`, because filling the gap would mean inventing defaults such as TSTEP.
   - `remove_stimulus(designator)`, which the plan did not list. Without it, the only way back to a DC source is a `set_stimulus` that cannot express "none".
   - There is no table of argument names such as `td` for PULSE's third position. The manual and the LTspice reference name them differently, and each would be one more list to maintain. *Alternative:* add such a table, later, if use shows the need.
5. **Argument counts are not checked, except that an empty list is refused.** Both solvers refuse `PULSE()`, and it has no slot to edit. `PULSE(1)` and an odd-length `PWL` parse and fail at the solver, because the library does not validate solver inputs. Extra arguments run on both solvers and are kept.
6. **Add the RF port parameters, which the plan's list leaves out.** `portnum` and `z0` are in the manual (§4.1.11), and today they are recognised only to be rejected. v1 must not leave a manual form unsupported (§6.7). They are written `portnum 1 z0 100` or with `=`, so they are named parameters, not a function. *Alternative:* a named exclusion, like `.machine`.
7. **One decision record, 0013,** amending §5.3, §7.1 and §7.2, and removing the source functions from `NG-UNS-001` and `LT-UNS-001`.

## 3. Starting point (2026-11-04, `a9efb31`)

Probes on ngspice 47 and LTspice 26.1.1: about 150 runs in a `.tran`, from a scratch script. "Runs" means exit code 0 with the expected waveform range.

| Line | ngspice 47 | LTspice 26.1.1 |
|---|---|---|
| `PULSE(...)`, any case, commas, `PULSE (...)`, `PULSE( ... )` | Runs | Runs |
| `PULSE 0 1 1u …`, no parentheses | Runs, refused by decision 2 | Runs, refused by decision 2 |
| `+` continuation before, after or inside the function | Runs | Runs |
| Comment on a continued line inside the parentheses | Runs | Runs |
| `{x}` and `'x*2'` arguments | Runs | Runs |
| Bare `x*2` argument | Stops | Stops |
| Bare `x` argument | Runs | Stops |
| `PULSE()` | Stops | Stops |
| `PULSE(1)` | Stops | Stops |
| Too many arguments | Runs | Runs |
| `AC 1 SIN(...)`, `DC 1 SIN(...)`, `1 SIN(...)`, `DC 1 AC 1 SIN(...)` | Runs | Runs |
| `SIN(...) AC 1`, `SIN(...) DC 1`, `SIN(...) DC 1 AC 1` | Runs | Runs |
| `SIN(...) 1` | Runs, output 0 | Stops |
| `SIN(...) PULSE(...)` | Runs, the last wins | Stops |
| `SIN` | Runs | Runs |
| `SINE` | Runs (not in the manual; accepted by decision 2) | Runs |
| `PWL(0 0 5u)`, odd count | Runs, output 0 | Stops |
| `PWL(...) r=0 td=1u` | Runs | Stops |
| `PWL file=x.txt`, `PWL(file=x.txt)`, `PWL file="x.txt"` | Stops | Runs |

**ngspice only:**
- AM, TRNOISE, TRRANDOM (also with a blank before the parenthesis) and the phase argument of §4.1.10 run.
- `portnum 1 z0 100` and `portnum=1 z0=100` run, also after a function.
- `DISTOF1 0.1 -90` and `DISTOF2 0.01` run, also after a function.
- **Manual forms that stop:** bare `DISTOF1`, and `AC 1 DISTOF1 DISTOF2 0.001`, which is a manual example. `EXTERNAL` stops with "unknown parameter" in this console build, because it needs the shared library (§4.1.9). The grammar follows the manual, and these go in `discrepancies.md`.

**LTspice only:**
- `Rser=` and `Cpar=` run before or after a function on V, and stop on I. `AC 1`, `AC=1` and `Rser` mix with a function in any order.
- `Trigger=V(a)>0.5` with `tripdv=` and `tripdt=` runs.
- `PWL TIME_SCALE_FACTOR=2 VALUE_SCALE_FACTOR=3 (…)` runs. The factors stop if written after the list, and after `FILE=`.
- `PWL REPEAT FOR 2 (…) ENDREPEAT` and `FOREVER` run with a closed sequence, and stop if the last value differs from the first. A nested repeat stops. Two repeats in a row, scale factors before a repeat, and `Rser=` after one run; the reference shows none, so the library refuses the first two and accepts the third as it does after any function.
- `wavefile=x.wav chan=0` was read and stopped on the missing file; T5 runs it with a real file, made in the test's folder.
- `tbl=(0 0, 1 1)`, with or without commas, runs. `1 step(1,2,3)`, `step(1,2,3)` and `1 step(1 2 3) load` run. `PULSE(...) load` runs. `wavefile=` on an I line stops here on the missing file.
- `PULSE(...) m=2` runs, although the reference does not list `m` on V. It stays refused and goes in `discrepancies.md`.

**In the repository:**
- The `stimulus` rule is `SEP STIMULUS_KW rest NL`, and its transformer raises `UnsupportedConstruct`. `_IndependentSource` has `dc`, `dc_keyword`, `ac` and `flags`.
- `half_rectifier.net` line 3 is `V1 N001 0 SINE(0 1 60k) Rser=1`, and its manifest entry expects the error at line 3, column 11.
- `elements_rejects/stimulus_function.cir` on ngspice, and tests in `test_elements.py`, `test_ltspice_elements.py`, `test_ngspice_validation.py` and `test_ltspice_validation.py`, pin the rejection. They become acceptance tests.
- The tree snapshot will change for `stimulus_function.cir`. The signature snapshot holds only files that parsed at the start of M11, so it should not change at all.

## 4. Tasks

[x] **T1 — Decision record 0013.** Status `proposed` until M12 closes. It records section 2, and amends §5.3 (`SourceSpec`), §7.1 and §7.2 (the operations and "phase 1: DC and AC only"), and records `SINE` on ngspice as the exception to decision 0002.

[x] **T2 — Shared syntax and node.** Tests first, on both dialects:
- A typed `SourceSpec` on `_IndependentSource`, with `None` when there is no function: the function's name and span; each argument with its span, as `NumericValue` or `Formula`; the named parameters; and the whole span.
- The grammar accepts the forms of decisions 1 and 2, with a blank allowed before the parenthesis, continuation lines, comments and commas anywhere fields already allow them. Arguments are matched by rules and terminals, not split in Python (P13). `rest` is no longer used here.
- Negative tests with positions: a bare value after a function, two functions, two DC parts, an empty list, an unclosed parenthesis, a function with no parentheses, and bare names and expressions.
- `Formula` arguments reach the document layer, so that `UNRESOLVED_PARAM` and references see them. Nothing in a function changes `nets()` or the signature, which a property test pins.
- Round-trip tests that every form is byte-exact, including CRLF.

[x] **T3 — ngspice functions.** PULSE, SIN and SINE, EXP, PWL with `r=` and `td=`, SFFM, AM, TRNOISE, TRRANDOM, EXTERNAL with `m=`, and DISTOF1 and DISTOF2 with optional magnitude and phase. `portnum` and `z0` (decision 6). Each with a spec entry and a solver test comparing the waveform against a plain expectation where one is deterministic. TRNOISE and TRRANDOM only assert that they run. EXTERNAL and bare DISTOF record that they stop.

[x] **T4 — LTspice functions.** PULSE, SINE, SIN, EXP, SFFM, PWL with pairs. Each with a spec entry and a solver test. `Rser`, `Cpar`, `AC` and the function mix in any order on V. `Trigger=`, `tripdv=` and `tripdt=`; the trigger expression is kept as text. `load` after a function on I.

[x] **T5 — LTspice file, repeat and table forms.** Each with a spec entry and a solver test:
- `PWL FILE=`, with or without quotes, and the path is never read by the library.
- `PWL REPEAT FOR n` and `FOREVER` … `ENDREPEAT`, with a closed sequence. Probe whether a repeat can nest before writing the rule.
- `TIME_SCALE_FACTOR=` and `VALUE_SCALE_FACTOR=` before the list.
- `wavefile=` and `chan=`, with a small wave file generated by the test.
- For I: `tbl=(...)`, `step(...)` alone or after a value, and with `load`.

[x] **T6 — Edit operations (decisions 3 and 4).** `set_stimulus`, `set_stimulus_arg` and `remove_stimulus` on the operations mixin, so batches get them:
- Slot checks: the text must re-parse as one `SourceSpec`, so `SIN(0 1) R2 a b 1k` or a new line in a value cannot add topology.
- A separator matches its neighbours, so a list with commas stays a list with commas.
- `set_stimulus` on a source with none goes after the DC and AC parts. On LTspice it goes before `Rser`, and the conventions are recorded in `edit-layer.md`.
- `set_value`, `set_dc`, `set_ac` and `set_param` keep working beside a function.
- Batch keys, as in decision 0010 item 5, for the upserts: one per designator for a whole stimulus, and one per designator and key for an argument.
- Negative tests: no such designator, not a source, a position past the end, no stimulus to edit, and `scope` without `in_definition`.
- Golden diffs on both dialects for each operation, and property tests that the signature is unchanged.

[x] **T7 — Solver-backed edit tests.** For each operation on each dialect, an edited netlist runs and its waveform changes as expected. A test records what each solver does with a DC value beside a function (decision 3).

[x] **T8 — `half_rectifier.net` (the exit).**
- It loads, a manifest entry replaces the expected error, and the corpus sweep runs it.
- `set_stimulus_arg("V1", 1, "2")` gives a golden diff, and the result runs on LTspice with the output changing as expected.
- Replace `test_the_half_rectifier_export_runs_and_is_unsupported`.
- Move `elements_rejects/stimulus_function.cir` to an accept family, regenerate the tree snapshot, and state which entries changed and why.
- Check that the signature snapshot does not change.

[x] **T9 — Documentation.**
- Narrow `NG-UNS-001` and `LT-UNS-001` to what is still unsupported, and add the rows from section 3 to both `discrepancies.md` files.
- `elements.md`, `edit-layer.md` and the `docs/usage/` guides, including LTspice export. `docs/usage/editing.md` shows, with doctests, that `set_stimulus` leaves DC and AC alone, and that `set_dc` and `set_ac` edit them separately (decision 3). Remove `half_rectifier.net` from any list of limits.
- `docs/usage/errors.md`: the `UnsupportedConstruct` text no longer names `PULSE`.
- README and CHANGELOG known limits, with a line for each new public name.

[x] **T10 — Final evidence and handover.** Open the pull request. Run the full local check set with `--require-solver ngspice --require-solver ltspice` on Windows, and record it and the green CI run in section 5. Set the status to `READY FOR REVIEW`, and update the plan's M12 heading and the index.

### After the maintainer's approval

[ ] **T11 — Close M12.** Merge on green with "Rebase and merge". Status `COMPLETE (date)`, `git mv` to `docs/design/archive/phase-2/`, fix links, update the plan and index, and accept decision 0013.

## 5. Results

**Full local run on `5e77131` (T10, Windows, Python 3.14.3, ngspice 47, LTspice 26.1.1.0):** 5395 passed, 2 skipped, 493 deselected, 13 minutes 44 seconds, coverage 98.85%, with `--require-solver ngspice --require-solver ltspice`. `ruff check`, `ruff format --check`, `mypy` (26 files), the named `mypy --strict` (32 files), the import contract (1 kept, 0 broken) and `pre-commit run --all-files` are all clean.

**CI on `5e77131` ([PR 8](https://github.com/xdylanm/netlistmod/pull/8), run 41848889929): all five jobs green,** with no solver found.

| Job | Python | Passed | Skipped | Deselected | Coverage |
|---|---|---:|---:|---:|---:|
| Ubuntu | 3.13.18 | 4137 | 1260 | 493 | 98.85% |
| Ubuntu | 3.14.10 | 4137 | 1260 | 493 | 98.85% |
| Windows | 3.13.17 | 4136 | 1261 | 493 | 98.85% |
| Windows | 3.14.10 | 4136 | 1261 | 493 | 98.85% |

The commit that records these results adds a few tests and changes docs; its run is on the pull request.

**The exit.** `half_rectifier.net` loads. `set_stimulus_arg("V1", 1, "2")` gives a golden diff, and the edited netlist runs on LTspice with a higher output and the same signature (`test_the_half_rectifier_export_loads_and_edits`).

**Compatibility rule.** All 153 recorded corpus digests are unchanged. The tree snapshot lost `elements_rejects/stimulus_function.cir`, `distortion_input.cir` and `continued_stimulus.cir`, whose forms moved to `elements_basic/source_functions.cir`. It gained that file and the four golden files, and no other entry changed.

**Design points worth reviewing:**
- **A source line is right-linear in the grammar.** An optional AC phase or named parameter followed by another field is a shift/reduce conflict in LALR, so each source rule is one state of what the line has shown so far. These rules are Lark templates, and the spec checker's pattern does not see a template's declaration. Their comment in `core.lark` explains them.
- **The transformer checks three things the grammar does not:** that `r=`, `td=`, `m=` and `chan=` belong to the function before them, that `chan=` follows it directly, and that `portnum` and `z0` are on a V line. One rule for each keeps the state count down, and each gives a clearer message. They raise `ParseError` with the position.
- **`set_stimulus` tells a distortion input by the start of the caller's text** (`DISTOF1` or `DISTOF2`). The result is still re-parsed and slot-checked.

**Probes that settled T5:** a nested `REPEAT` stops LTspice, so refusing it costs nothing. Two `REPEAT` blocks in a row, and scale factors before `REPEAT`, run on LTspice but are not in the reference, so they are refused and recorded in `discrepancies.md`.

**Not done:** no solver has been run on Linux, as before. `Trigger=` with a blank in its expression is refused, because a blank ends the field; I did not probe whether LTspice accepts one.
