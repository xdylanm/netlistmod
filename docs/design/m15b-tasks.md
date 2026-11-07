# M15b task list — Tables, polynomials and transfer functions (E, F, G, H and B)

> **Status:** DRAFT — awaiting the maintainer's decisions in section 2
> **Part of:** [phase-2-plan.md](./phase-2-plan.md) (milestone M15b). Governed by [architecture.md](../architecture.md) (§2, §5.3, §7.2, §7.8, §10). Follows [M15](./archive/phase-2/m15-tasks.md) and [decision 0016](../decisions/0016-behavioral-expressions.md).

## 1. Scope

M15b adds the nonlinear forms that M15 left `UnsupportedConstruct` (decision 0016 item 1). The rules are already set by decision 0016: item 7 names the M15b edits, item 8 the counting of POLY's control fields, and item 9 puts FREQ and the gates in M15b.

- **TABLE:**
  - ngspice E and G `TABLE {expr} = (x, y) …`, with or without `=`;
  - ngspice E's four-node `TABLE = (x, y, …)`;
  - LTspice E and G `table=(x, y, …)`.
- **POLY** on E, F, G and H on both dialects (on LTspice E and G, also with `(vx,0)` pairs). The control nodes and the controlling sources are topology, counted from the dimension (decision 0016 item 8).
- **Transfer functions:** LTspice E and G `Laplace=` with `window=`, `nfft=` and `mtol=`, and B's `laplace=` with the same parameters. ngspice's `LAPLACE` stays a `ParseError` (decision 0016 item 9).
- **ngspice's XSPICE forms of E** (manual §5.2.6, §5.2.7): FREQ, and AND, OR, NAND and NOR.
- **Edit API:** `set_table` and `set_poly_coefficients` (decision 0016 item 7). The expression of a TABLE or FREQ uses M15's `set_expression`.
- **Query:** the expressions of TABLE and FREQ, and `Laplace=`, join `expression_reads`.
- **Not in M15b:**
  - checking that a table's points are monotonic, or that a polynomial has the right number of coefficients for its dimension;
  - evaluating anything (non-goal 6);
  - editing POLY's dimension or a gate's input count, which changes the topology.

**Exit (plan):** as M15. Every form has golden diffs and solver tests showing that results move as expected.

## 2. Recommendations (for the maintainer's decision)

*(Your input)* marks the points that need a choice. "Alternative" marks an option considered and not recommended.

1. **Node fields for the new forms.** *(Your input: the names and shapes.)*
   - The forms keep the M14 classes (`Vcvs` and the rest) and set `form` to `"table"`, `"poly"`, `"laplace"`, `"freq"` or the gate's name. `value` is then `None`, as for M15's expression forms.
   - **TABLE:** `table: Table`, a tuple of `TablePoint(x, y, span)` with `Value` fields as written. ngspice's `TABLE {expr}` also sets `expression`. The four-node and LTspice `table=` forms read the control voltage, so `expression` is `None` there.
   - **POLY:** `poly: Poly`, with `dimension: int` and `coefficients: tuple[Value, …]`.
   - **Laplace:** `laplace: Formula` on E and G. On B, `laplace=` stays a trailing parameter whose value is a `Formula`, with `window=`, `nfft=` and `mtol=` beside it.
   - **FREQ:** `expression`, plus `freq: FrequencyTable`, holding the format words as written and a tuple of `(f, a, b)` points.
   - **Gates:** `points: Table` (the manual's two points), with the inputs in `nodes`.
   - *Alternative:* one generic `table: tuple[tuple[Value, …], …]` for every point list. That is simpler, but a caller would have to know the form to read it.
2. **POLY's controlling sources on F and H.** *(Your input.)*
   - Decision 0016 item 8 says `controls: tuple[ElementReference, …]`. Today `Cccs.control` and `Ccvs.control` are one `ElementReference | None`.
   - **Recommended:** add `controls` to F and H for every form, holding the single source of the linear form too, with `control` kept as it is (the linear form's source, `None` for POLY). A caller that wants every controlling source reads `controls`.
   - Each one has a `control` entry in the signature, resolves as M14's do, and gets `UNRESOLVED_ELEMENT` and `CONTROL_SOURCE_MISMATCH` the same way.
   - *Alternative:* make `control` a tuple. That is cleaner, but it breaks every M14 caller.
3. **Counting (decision 0016 item 8).**
   - After `POLY(N)` the transformer takes the first 2N names as control nodes (E, G), or the first N as controlling sources (F, H), and the rest as coefficients. With fewer, it raises a `ParseError` at the line's end. `elements_rejects/e_poly_too_few.cir` moves from `UnsupportedConstruct` to that error.
   - A gate `and(N)` takes 2N control nodes the same way, then its two points.
   - LTspice's `(vx,0)` pairs are grouped by the grammar, so they are counted as pairs.
   - `N` must be a positive integer written as one. Any other text there is a `ParseError` at it.
4. **Edits.** *(Your input on FREQ.)*
   - `set_table(designator, points)` replaces a TABLE's, `table=`'s or a gate's points, writing them in the layout already on the line (pairs in parentheses, or one flat list). The number of points may change.
   - `set_poly_coefficients(designator, values)` replaces the coefficients. The count may change, since checking it is out of scope. The dimension, the control nodes and the controlling sources are not editable: they are topology.
   - The expression of TABLE and FREQ, and `Laplace=`, use `set_expression`. B's `laplace=` uses `set_param`.
   - **FREQ's points:** recommended `set_table` with three-value points, refused at write time if the count of values per point is wrong. *Alternative:* a separate `set_freq_points`.
   - Golden diffs for each, and property tests that no edit here changes the signature.
5. **The formula scan.** `s` in `Laplace=` and `laplace=` is not a parameter reference there (decision 0016 item 5). The expression of TABLE and FREQ is scanned as M15's are.
6. **Refusals.**
   - Unchanged from decision 0016 item 9: ngspice `LAPLACE`, and on LTspice ngspice's `TABLE {…} =` (`elements_rejects/e_table_braces.cir`).
   - Forms the references do not show are refused, and any a solver runs go in that dialect's `discrepancies.md`. The probes of T1 decide which.
7. **One decision record, 0017.** It records this section, and amends §5.3 (the new fields), §7.2 (the two operations), the signature's `control` entries for POLY (decision 0015), and decision 0016 item 8 where this section settles it. The rules go in `model/_rules_behavioral.py` or `_rules_controlled.py`, and the edits in `edit/_ops_behavioral.py` (P12).

## 3. Starting point

- **Branch:** `m15b-tables`, from `main` once M15 (#12) merges.
- **Corpus (written for M15, credited to xdylanm under MIT; see M15 section 3.3):**

| | ngspice (`controlled_sources`) | LTspice (`controlled_sources`) |
|---|---|---|
| **Accept** | `test_esource_table`, `_table_nodes`, `_poly`, `_poly2`, `_freq`, `_and`; `test_gsource_table`, `_poly`; `test_fsource_poly`, `test_hsource_poly` | `lt_test_bsource_laplace`; `lt_test_esource_table`, `_laplace`, `_poly`, `_poly_paren`; `lt_test_hsource_poly` |
| **Rejects** (`elements_rejects`) | `e_laplace` (stays a `ParseError`), `e_poly_too_few` (becomes one) | `e_table_braces` (stays refused) |

  Each accept file is marked `pending: M15b` in its manifest, so the loaders and solver sweeps skip it. M15's probes (its section 3.1) show that each form runs on its solver.
- **In the repository:** the grammars recognise each M15b keyword only to raise `UnsupportedConstruct` (`nonlinear_form`, `table_form`, `cc_form`, `ctl_form`, and B's `laplace=` under LT-UNS-001).

## 4. Tasks

[ ] **T1 — Probes and decision record 0017.** Probe the points section 2 leaves open, on ngspice 47 and LTspice 26.1.1: the TABLE and FREQ layouts with and without commas, POLY with a parameter or formula coefficient, a gate with the wrong input count, and LTspice POLY with mixed pair and flat forms. Record the results in section 3. Write 0017, status `proposed` until M15b closes.

[ ] **T2 — POLY (recommendations 1 to 3).** The grammar's flat field list after `POLY(N)` on all four letters and both dialects, and the transformer's count.
- **Negative tests:** too few fields, a dimension that is not a positive integer.
- **Topology tests:** the control nodes are in `nodes` and the signature; F's and H's controlling sources are `control` entries, resolved and diagnosed as M14's.

[ ] **T3 — TABLE.** ngspice's two forms and LTspice's `table=`, with `Table` and `TablePoint`.

[ ] **T4 — Laplace (LTspice).** E and G `Laplace=` with its parameters, and B's `laplace=`. `s` is not a reference.

[ ] **T5 — FREQ and the gates (ngspice).** FREQ's expression, format words and points; AND, OR, NAND and NOR, counted as in recommendation 3.

[ ] **T6 — The query.** The expressions of TABLE, FREQ and `Laplace=` in `expression_reads`, with document-layer tests.

[ ] **T7 — Edits (recommendation 4).** `set_table` and `set_poly_coefficients`, with golden diffs on both dialects, property tests that the signature does not change, and solver tests that an edited table or coefficient moves the result.

[ ] **T8 — Corpus and snapshots.** The `pending` marks go, and every M15b accept file loads, round-trips and runs in its sweep. `e_poly_too_few.cir`'s manifest entry becomes a `ParseError` at the line's end. The tree snapshot gains the M15b files and changes that entry, with its docstring saying so. No existing signature snapshot entry changes.

[ ] **T9 — Spec entries and documentation.**
- The NG-VCV, NG-VCC, NG-CCC and NG-CCV entries and their LTspice equivalents gain the forms, and NG-UNS-001 and LT-UNS-001 lose them.
- `docs/design/elements.md`, `edit-layer.md`, `document-layer.md`, `docs/usage/elements.md` and `editing.md`, `errors.md`, both `discrepancies.md`, the README, CHANGELOG and the architecture amendments.

[ ] **T10 — Final evidence and handover.** Open the pull request. Run the full local check set with `--require-solver ngspice --require-solver ltspice`, record it and the CI run in section 5, and set the status to `READY FOR REVIEW`.

### After the maintainer's approval

[ ] **T11 — Close M15b.** Archive this list, accept decision 0017, and update the plan and index.

## 5. Results

To be written at T10.
