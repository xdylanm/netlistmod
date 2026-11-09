# M15b task list — Tables, polynomials and transfer functions (E, F, G, H and B)

> **Status:** READY FOR REVIEW — implemented on branch `m15b-tables`; approved by the maintainer on 2026-11-08, with section 2 decided
> **Part of:** [phase-2-plan.md](./phase-2-plan.md) (milestone M15b). Governed by [architecture.md](../architecture.md) (§2, §5.3, §7.2, §7.3, §7.8, §10). Follows [M15](./archive/phase-2/m15-tasks.md) and [decision 0016](../decisions/0016-behavioral-expressions.md).

## 1. Scope

M15b adds the nonlinear forms that M15 left `UnsupportedConstruct` (decision 0016 item 1). Decision 0016 already sets three rules: item 7 names the M15b edits, item 8 the counting of POLY's control fields, and item 9 puts FREQ and the gates in M15b. Section 3.1 has the probes behind everything else.

- **In:**
  - **TABLE (ngspice):**
    - E and G `TABLE {expr} = (x, y) …`, with or without `=` (manual §5.2.3, §5.3.3), and G's `m=`;
    - E's four-node `TABLE = (x, y, …)` (§5.2.3).
  - **`table=` (LTspice):** E and G `table=(x, y, …)` ([ltspice-ref] CIRCUIT-ELEMENTS-REFERENCE.md "E — Voltage-Dependent Voltage Source").
  - **POLY** on E, F, G and H, on both dialects (§5.5; the reference's "Polynomial (legacy)"):
    - on LTspice E and G, also with `(n+,n-)` pairs;
    - ngspice's `m=` on F and G.

    The control nodes and the controlling sources are topology, counted from the dimension (decision 0016 item 8).
  - **`Laplace=` (LTspice):** E and G, with `window=`, `nfft=` and `mtol=`, and B's `laplace=` with the same parameters. ngspice's `LAPLACE` stays a `ParseError` (decision 0016 item 9).
  - **ngspice's XSPICE forms:**
    - FREQ on E and G (§5.2.6, §5.3.6);
    - AND, OR, NAND and NOR on E (§5.2.7).
  - **Edit API:** `set_table` and `set_poly_coefficients` (decision 0016 item 7). The expression of TABLE and FREQ, and the `Laplace=` formula, use M15's `set_expression`.
  - **Query:** the expressions of TABLE and FREQ join `expression_reads`.
- **Not in M15b:**
  - checking that a table's points are monotonic, or that a polynomial has the right number of coefficients for its dimension (beyond the minimums of recommendation 4);
  - evaluating anything (non-goal 6);
  - editing POLY's dimension, a gate's inputs, a form or FREQ's format words. The first two change the topology (§7.3), and the others change what the element is.
  - a release. M15b ends at its own merged pull request. Releases are decided separately from the milestones (maintainer, 2026-11-08; decision 0018).

**Exit (plan):** as M15. Every form has golden diffs and solver tests showing that results move as expected.
- The signature snapshot is unchanged, and the compatibility test still passes.
- A negative test shows that changing any POLY control node, gate input or POLY controlling source is a `TopologyViolation`.
- Every M15b accept file of both `controlled_sources` families loads, round-trips byte-exact and runs in its solver sweep.

## 2. Decisions (maintainer, 2026-11-08)

The maintainer decided the open points one at a time on 2026-11-08: the node fields (1), `control` as a tuple (2), the counting (3), the POLY minimums, numbers-only ngspice TABLE points and where `laplace=` may appear (4), the `table` net name (5) and FREQ's edit (6). The maintainer approved the other points as recommended with the whole list. "Considered" marks an option weighed and not chosen. Every refusal below that a solver runs gets a row in that dialect's `discrepancies.md`, with its probe.

1. **Node fields for the new forms.** **Decided:** as below, with `TablePoint.values`, `Laplace=` in `expression`, B's `laplace=` as a parameter, and the field names as written.
   - The forms keep the M14 classes (`Vcvs`, `Vccs`, `Cccs`, `Ccvs`), as M15's did. `value` is `None`, and `form` is `"table"`, `"poly"`, `"laplace"`, `"freq"`, `"and"`, `"or"`, `"nand"` or `"nor"`.
   - `ControlledSource` gains three fields, each `None` or empty unless the form uses it:
     - `table: Table | None` for TABLE, `table=`, FREQ and the gates' two points;
     - `dimension: int | None`, POLY's or a gate's `N` as written;
     - `coefficients: tuple[Value, ...]`, POLY's coefficients.
   - **`Table`** has:
     - `points: tuple[TablePoint, ...]`;
     - `layout`: `"pairs"` (each point in its own parentheses) or `"flat"` (one parenthesised list);
     - `format: tuple[str, ...]`, FREQ's words as written (`DB`, `MAG`, `DEG`, `RAD`, `R_I`), empty for the other forms;
     - `span`.

     **`TablePoint`** has `values: tuple[Value, ...]` (two, or three for FREQ) and `span`.
   - `expression` keeps one meaning: the formula the line writes. That is the input of ngspice's `TABLE {expr}` and `FREQ {expr}`, and the transfer function of `Laplace=`. The four-node TABLE, `table=`, POLY and the gates read their control nodes, so `expression` is `None` there.
   - `window=`, `nfft=` and `mtol=` on E and G, and `m=` on ngspice G and on F and G POLY, are in `params`.
   - On B, `laplace=` stays a trailing parameter whose value is a bare-expression `Formula`, with `window=`, `nfft=` and `mtol=` beside it.
   - *Considered:* `TablePoint(x, y)` with a separate `FrequencyTable` for FREQ's triples. That reads better for the two-value forms, but gives `set_table` two shapes.
   - *Considered:* a separate `laplace: Formula` field on E and G. That is more explicit, but adds a second formula slot that `set_expression` would have to choose between.
2. **POLY's controlling sources on F and H.**
   - Decision 0016 item 8 says `controls: tuple[ElementReference, …]`. Today `Cccs.control` and `Ccvs.control` are one `ElementReference | None`.
   - **Decided: `control` becomes the tuple,** `control: tuple[ElementReference, ...]`, on F and H for every form. It holds the one source of the linear form, the N sources of POLY in line order, and `()` for LTspice's `value=`. There is no second field, because `control` beside `controls` would be confusing. This is a breaking change to the public API, made now because no caller depends on it yet. The CHANGELOG says so.
   - `CurrentSwitch.control` (W) becomes the same tuple, always of one source, so that every reader of a controlling source handles one shape.
   - The signature, `UNRESOLVED_ELEMENT`, `CONTROL_SOURCE_MISMATCH` and the reference index loop over `control`. The signature has one `("control", scope, designator, source)` entry for each source, in line order. A linear line gives the same entry as today, so no digest changes, and swapping two POLY sources changes the order of the entries, which is a `TopologyViolation`.
   - *Considered:* a separate `controls` field beside `control`, kept as it is (not chosen), and one signature entry per line holding a tuple (not chosen: it would change every saved digest of a netlist with F, H or W).
3. **Counting (decision 0016 item 8).** **Decided:** as below.
   - **`N` is an integer literal of at least 1**, with or without a blank before `(` (both solvers run `POLY (1)`). Any other text there is a `ParseError` at it, including `POLY({1})`, which both solvers run: the dimension decides the topology, so it must be readable without evaluation.
   - **POLY on E and G:** the transformer takes the first 2N names after `POLY(N)` as control nodes, after the output pair in `nodes`, and the rest as coefficients. On F and H it takes the first N as controlling sources. With fewer, it raises a `ParseError` at the line's end. `elements_rejects/e_poly_too_few.cir` moves from `UnsupportedConstruct` to that error.
   - **LTspice `(n+,n-)` pairs** are grouped by the grammar, and count as one pair. LTspice runs them with a comma or a blank inside, written tight (`(vx,0)(vx,0)`), and mixed with flat pairs, so all four load. A controlling source in parentheses stops LTspice and is refused.
   - **ngspice pairs in parentheses** (`POLY(1) (vx,0) 0 2`) run, but the manual does not show them: refused, with a discrepancies row. *Considered:* accept them as on LTspice.
   - **Gates (`and(N)` …):** ngspice ignores `N`. It reads every name before the first point as an input pair: `and(1)` and `and(3)` with two pairs both run as two inputs. So the inputs are counted from the line, never from `N`:
     - the names before the first point must be an even number, at least four (ngspice stops on one pair: "Too few ports");
     - a `ParseError` when that count is not 2N, so that a line means what the manual says it means, with a discrepancies row. *Considered:* accept any `N`, as ngspice does.
4. **Fields and minimums.**
   - **ngspice TABLE (both forms):**
     - The expression must be in braces or quotes. `TABLE v(vx) = …` runs, but reads something else (4.0 where the table gives 2.67), so it is refused.
     - `=` is optional in both forms.
     - The points are pairs, with commas or blanks, or one flat list. Both forms run either layout.
     - At least one point; each pair has two values, and a flat list an even number. ngspice misreads a three-value point and stops on an odd list.
     - **The values are numbers.** The manual says "parameters are not allowed". ngspice runs some parameter forms and misreads others (`{2*k}` gives 1.33 in the four-node form instead of 2.67), so a formula or a name there is refused, with one discrepancies row listing the forms that run. Numbers with units (`-5mV`) load. `set_table` applies the same rule. **Decided.** *Considered:* accept the forms that run correctly (not chosen).
     - E's four-node TABLE is E only: G's stops ngspice, so it becomes a `ParseError` instead of `UnsupportedConstruct`.
     - `m=` after G's points runs and is accepted; on E it stops ngspice and is refused.
   - **LTspice `table=`:** one parenthesised list, with commas or blanks, over `+` lines if need be. At least two pairs, and an even count; LTspice stops otherwise ("Pairs of numbers expected"). Pairs in their own parentheses stop LTspice and are refused. The values follow LTspice's value slot (`{k}` runs, bare `k` stops). `table=` takes no `m=`.
   - **POLY coefficients:** the values follow each dialect's gain slot (ngspice runs a bare `k`, LTspice stops on it). **Minimums:** ngspice stops with fewer than two ("no such parameter"); LTspice runs one (the constant) and none (a gain of 1, which its reference does not show). **Decided:** at least two on ngspice and one on LTspice, as a `ParseError` at the line's end, with a discrepancies row for LTspice's zero. `set_poly_coefficients` enforces the same minimums.
   - **FREQ:** the expression in braces or quotes, `=` optional, then at least one format word, then the points.
     - ngspice stops with no format word, and with a two-value point.
     - The points are triples, with or without commas, in pairs layout or one flat list.
     - ngspice stops on the manual's own example, which writes `1.0e+07Hz`: a frequency with a unit suffix is refused, with a discrepancies row.
     - FREQ runs on G (manual §5.3.6), without `m=` (it stops).
   - **Gates:** E only (G stops ngspice). Exactly two points, each `(x, y)` with a comma, separated by blanks. ngspice stops on three points, on `and (2)`, on points without commas and on nodes in parentheses, so each is refused.
   - **LTspice `Laplace=`:**
     - The formula is bare or braced, and a bare one may hold blanks; it ends at the first ` name=`, as a bare expression does (decision 0016 item 2).
     - `window=`, `nfft=` and `mtol=` follow it, and may be on `+` lines. Any other name stops LTspice and is refused, and so is one of these before `Laplace=`, which LTspice runs but its reference does not show.
     - A `V()` or `I()` in the formula stops LTspice ("Voltage reference not allowed here"), so it is refused at the read.
     - `Laplace=` and `table=` need the four-node form: with two nodes LTspice stops.
   - **LTspice B `laplace=`:** after `V=` or `I=`, with `window=`, `nfft=` and `mtol=` after it. On `R=` and `P=` LTspice runs it, but the reference shows it only on `V=` and `I=`, so it is refused there. `window=`, `nfft=` and `mtol=` without `laplace=` before them (on B, E or G) run too, and are refused for the same reason, each with a discrepancies row. **Decided.** *Considered:* accept both, as observed parameters, as M15 accepted `vprx=` on `V=` (not chosen: these change what the element computes).
5. **Words that become keywords.** On ngspice, `table` in any node position of E stops ngspice, as `value` did in M15's review R6. **Decided:** refuse a net named `table` (any case) on ngspice E and G in any node position, at that node, with R6's kind of message, as a check in the transformer. T1 probes G first; if ngspice runs it there, the refusal is for E only. `poly`, `freq` and `and` as net names run on ngspice, and every one of these runs on LTspice, so nothing else changes. This refuses some lines that load today, but ngspice stops on every one of them.
6. **Edits.**
   - `set_table(designator, points)` replaces the points of TABLE, `table=`, FREQ or a gate. `points` is a sequence of points, each a sequence of value texts, as `set_stimulus_arg` takes text. It writes them in the layout already on the line, with the separator written between its first two values (`, ` or a blank). The number of points may change.
   - Write-time refusals (`EditError`, before verification): the wrong number of values per point (two, or three for FREQ), and the minimums of recommendation 4 (two points for a gate or `table=`, one for ngspice TABLE). On ngspice TABLE a value that is not a number is refused too.
   - `set_poly_coefficients(designator, values)` replaces the coefficients, from the first to the last, with the separator already there. The count may change, down to recommendation 4's minimum. `m=` stays as it is.
   - The dimension, the control nodes, the controlling sources, a gate's inputs, the form and FREQ's format words are not editable.
   - The expression of TABLE and FREQ, and `Laplace=`, use `set_expression`. `window=`, `nfft=`, `mtol=`, `m=` and B's `laplace=` use `set_param`. `set_value` on these forms is an `EditError` that names the right operation, as M15's is.
   - **FREQ's points: `set_table`** with three-value points, refused at write time when a point has the wrong number of values or a frequency has a unit suffix. **Decided.** *Considered:* a separate `set_freq_points` (not chosen).
   - Golden diffs for each, and property tests that no edit here changes the signature.
7. **The formula scan and the query.**
   - The expression of TABLE and FREQ is scanned as M15's are, and joins `expression_reads` with no change to the query.
   - `s` in `Laplace=` and `laplace=` is not a parameter reference (decision 0016 item 5). `Laplace=` can hold no `V()` or `I()` (recommendation 4), so it adds no reads.
   - The four-node TABLE, `table=`, POLY and the gates read only their control nodes, which are already in `nodes` and the signature.
8. **Unchanged refusals.** ngspice `LAPLACE` stays a `ParseError` (`elements_rejects/e_laplace.cir`). On LTspice, ngspice's `TABLE {…} =` stays refused (`elements_rejects/e_table_braces.cir`), with its discrepancies row.
9. **One decision record, 0017, and where the code goes.**
   - 0017 records this section. It amends §5.3 (the new fields and types), §7.2 (the two operations), decision 0015 (`control` becomes a tuple on F, H and W, with one signature entry per source), decision 0016 item 3 (`Cccs.control` and `Ccvs.control` are `()` rather than `None` on `value=`) and item 8 (`control` rather than `controls`, the minimums and the gate count).
   - **Recommended:** the rules go in a new family module, `model/_rules_nonlinear.py`, and the edits in `edit/_ops_nonlinear.py` (P12). `_rules_controlled.py` and `_rules_behavioral.py` keep their forms. *Considered:* add to `_rules_controlled.py` (185 lines today).

## 3. Starting point (2026-11-08, `4ba84af`, branch `m15b-tables`)

### 3.1 Probes

Probes on ngspice 47 and LTspice 26.1.1, from a scratch script outside the repository. Each circuit drives `vx` to 4/3 V (2 V over 1k and 2k), has a 1 mA sense source `Vsense` and a 1k load on `out`, and `.param k=2`, with `.op`. A table that doubles `v(vx)` gives `v(out)` = 2.667.

**ngspice 47:**

| Line (after `E1 out 0` or `G1 0 out`) | Result |
|---|---|
| `TABLE {v(vx)} = (0,0) (2,4)`; without commas, without `=`, in quotes, tight `=(0,0)(2,4)`, over `+` lines | Run, 2.667 |
| `TABLE {v(vx)} = (0,0,2,4)` (one flat list); one point `(0,3)` | Run, 2.667 / 3 |
| `TABLE v(vx) = …` (bare expression) | Runs, wrongly: 4.0 |
| `TABLE … (2,k)`, `(2,{4})` (pairs) | Run, right |
| `TABLE … (0,0,2,{2*k})` (flat) | Stops |
| `TABLE … (0,0) (2)` (odd); `(0,0,0) (2,4,0)` (triples) | Stops / runs, wrongly: 1.333 |
| `TABLE … m=2` on G; on E | Runs (5.333) / stops |
| `vx 0 TABLE = (0,0,2,4)`; pairs; without commas; without `=` | Run, 2.667 |
| `vx 0 TABLE = (0,0,2,{2*k})` / `(0,0,2,{4})` / `(0,0,2,k)` | Runs, wrongly: 1.333 / runs, right / stops |
| `vx 0 TABLE = (0,0,2)` (odd); G `vx 0 TABLE = …` | Stop |
| `POLY(1) vx 0 0 2`; `POLY (1)`; `POLY({1})`; `0 {k}`; `0 k`; over a `+` line | Run, 2.667 |
| `POLY(1) (vx,0) 0 2`; `POLY(1) vx,0 0,2` | Run, 2.667 |
| `POLY(0) 0 2`; `POLY(k) …`; `POLY(2) vx 0 0 1` (too few); `POLY(1) vx 0` (no coefficient); `POLY(1) vx 0 3` (one) | Stop |
| F `POLY(2) Vsense Vsense 0 1 1`; with `m=2`; H `POLY(1) Vsense 0 2k`; G POLY `m=2` | Run (2, 4, 2, 5.333) |
| F `POLY(1) Vnone 0 2`; F `POLY(1) Vsense 2` (one coefficient) | Stop |
| `FREQ {v(vx)}= DB (1, 6.02, 0) (1e9, 6.02, 0)`; without commas, without `=`, in quotes, over `+` lines, flat, one point | Run, 2.666 |
| `FREQ … = MAG DEG`, `= DB RAD`, `= R_I`, `= MAG (1, {k}, 0) …`; on G | Run |
| `FREQ {v(vx)} = (1, 2, 0) …` (no format word); two-value points; `(1Hz, …)`; G with `m=2` | Stop |
| `and(2) vx 0 vx 0 (0.5, 0) (0.9, 2)`; `AND(2)`; `or`, `nand`, `nor`; `(0.9, {k})` | Run |
| `and(1)` and `and(3)` with two input pairs; `and(2)` with three | Run, as two (or three) inputs |
| `and(2)` with one pair; `and(1)` with one pair; an odd name count | Stop ("Too few ports", "Expected node identifier") |
| Three points; `and (2)`; points without commas; `(0.5,0)(0.9,2)`; nodes in parentheses; G `and(2)` | Stop |
| `E1 out 0 table 0 2`, `E1 out 0 vx table 2`, `E1 table 0 vx 0 2` (a net named `table`) | Stop |
| The same with a net named `poly`, `freq` or `and` | Run |

**LTspice 26.1.1:**

| Line | Result |
|---|---|
| `E1 out 0 vx 0 table=(0,0,2,4)`; `TABLE=`; without commas; `table = (0, 0, 2, 4)`; `table(…)` without `=`; over a `+` line; `{2*k}`; G | Run, 2.667 |
| `table=(0,0) (2,4)`; `table=((0,0),(2,4))`; `(0,0,2)`; `(0,3)`; `(…,k)`; `m=2`; two nodes | Stop |
| `Laplace=2/(1+s/1k)`; with blanks; braced; `k/…`; with `window= nfft= mtol=`; `window=` on a `+` line; `window=` before `Laplace=`; G | Run, 2.667 (the DC gain) |
| `Laplace=… foo=1`; `Laplace=V(vx)/(1+s/1k)`; two nodes | Stop |
| B `V=… laplace=… window= nfft= mtol=`; braced; `I=… laplace=…`; `R=1k laplace=…`; `P=1m laplace=…`; `V=… window=1m` alone | Run |
| `POLY(1) vx 0 0 2`; `(vx,0)`; `(vx 0)`; mixed `POLY(2) (vx,0) vx 0 …`; tight `(vx,0)(vx,0)`; `POLY (1)`; `POLY({1})`; `vx,0 0,2`; `0 {k}`; G | Run, 2.667 |
| `POLY(1) vx 0` (no coefficient); `POLY(1) vx 0 3` (one) | Run (1.333, a gain of 1 / 3) |
| `POLY(1) vx 0 0 k`; `POLY(2) vx 0 0 1` ("No such node") | Stop |
| F `POLY(2) Vsense Vsense 0 1 1`; F `POLY(1) Vsense 2`; H `POLY(1) Vsense 0 2k` | Run |
| F `POLY(1) (Vsense) 0 2` | Stops |
| `table`, `poly` or `laplace` as a net name, in any position | Run |

T1 confirmed the points left open (2026-11-08, ngspice 47 and LTspice 26.1.1), and the probe tests hold every row of both tables, with the library's reading of each line:

| Line | Result |
|---|---|
| ngspice, G with a net named `table`, in any of its four node positions (with a load on the net) | Stops, as E does. So the refusal of decision 5 is for E and G. |
| ngspice, `POLY(1) vx,0 0,2`; `vx , 0 0 , 2`; `vx 0 0, 2` | Run, 2.667. The existing comma separator is enough. |
| ngspice, `FREQ … (1, 6.02, 0) (1e9Hz, 6.02, 0)` and `(1.0e+07Hz, …)` as a later frequency | **Runs.** A `Hz` suffix on the first frequency stops (`(1Hz, …)`, which is the row of 3.1); the library refuses a suffix on any frequency, as decision 4 says, so this is one more discrepancies row. |
| ngspice, FREQ whose first frequency is `1.0`, `10` or `1k` | Stops ("Undefined parameter [v]" from the expression pass), while `1` and `2` run. This is ngspice's own reading of the line and the library does not model it: such a line loads. |
| ngspice, `POLY(1) vx 0 0 2 m=2` on **E** | **Runs.** The manual gives `m` to F and G, and the library refuses it on E and H (one more discrepancies row). |
| LTspice, `E1 out 0 vx 0 2 window=1m` and B `V=… window=1m` | Run (the "without `laplace=`" rows of 3.1 hold for E as well as B). |
| LTspice, B `V=2*V(vx) laplace=1/(1+s/1k)` | Runs, and the operating point is the expression's, whatever the transfer function: `laplace=` shapes the response over time, so only an edit that lands and runs is tested for B. |

The ngspice probes that run a form and read it wrongly are quantified in `test_what_ngspice_computes` (4.0 for the bare `TABLE`, 1.333 for the four-node `{2*k}` and for triples, where the table gives 2.667).

### 3.2 Corpus

The accept files were written for M15 and credited to xdylanm under MIT (M15 section 3.3):

| | ngspice (`controlled_sources`) | LTspice (`controlled_sources`) |
|---|---|---|
| **Accept** | `test_esource_table`, `_table_nodes`, `_poly`, `_poly2`, `_freq`, `_and`; `test_gsource_table`, `_poly`; `test_fsource_poly`, `test_hsource_poly` | `lt_test_bsource_laplace`; `lt_test_esource_table`, `_laplace`, `_poly`, `_poly_paren`; `lt_test_hsource_poly` |
| **Rejects** (`elements_rejects`) | `e_laplace` (stays a `ParseError`), `e_poly_too_few` (becomes one) | `e_table_braces` (stays refused) |

Each accept file is marked `pending: M15b` in its manifest, so the loaders and solver sweeps skip it.

**New files (T2),** each one change from an existing file, credited the same way; your review confirms their provenance:
- **ngspice accept:** `test_gsource_freq` (G FREQ), `test_fsource_poly2` (two controlling sources, `m=`), `test_esource_or`.
- **ngspice rejects:** `e_table_bare` (bare expression), `e_table_param` (a parameter in a point), `g_table_nodes` (G four-node TABLE), `e_poly_parens`, `e_poly_dimension` (`POLY({1})`), `e_poly_one_coefficient`, `e_freq_no_format`, `e_freq_hz`, `e_and_count` (inputs differ from `N`), `g_and`, `e_table_node` (a net named `table`).
- **LTspice accept:** `lt_test_gsource_laplace` (with `window=`, `nfft=` and `mtol=`), `lt_test_gsource_poly`, `lt_test_fsource_poly2`.
- **LTspice rejects:** `e_table_pairs`, `e_table_odd`, `e_laplace_read` (`V()` in `Laplace=`), `e_laplace_unknown_param`, `e_poly_dimension`, `f_poly_paren`, `b_laplace_resistor`; the ones LTspice runs are listed in `LTSPICE_RUNS`.

### 3.3 In the repository

- **Grammar:** each M15b keyword is recognised only to raise `UnsupportedConstruct`: `nonlinear_form`, `cc_form` and `table_form` (`VC_FORM_KW`, `CC_FORM_KW`, `TABLE4_KW`) in `ngspice.lark`, and `nonlinear_form`, `ctl_form` and `b_laplace` (`OUT_FORM_KW`, `CTL_FORM_KW`, `B_LAPLACE_KW`) in `ltspice.lark`. ngspice's `table_form` also takes G's four-node line today.
- **Nodes:** `ControlledSource` has `value`, `expression` and `form`; `Cccs` and `Ccvs` have `control`. `Vcvs.control_nodes` is `nodes[2:]`, so it covers POLY's pairs as they are.
- **`control` readers:** `document/topology.py` (the signature), `document/index.py` (the reference index) and `document/diagnostics.py` (`_into_instance`, `CONTROL_SOURCE_MISMATCH`).
- **Tests that pin the M15b forms as unsupported:** `test_the_m15b_forms_stay_unsupported` (`tests/grammar/ngspice/test_behavioral.py`) and its LTspice twin, NG-NLS-001's list, and the LTspice validation test that M15 moved onto POLY, `Laplace=` and B `laplace=` (M15 section 5, point 8).
- **A precedent for flat points:** LTspice I's `tbl=` is a `SourceSpec` with flat `args`, edited by position with `set_stimulus_arg`. Tables here get points instead, because they come in two layouts and `set_table` replaces them whole.

## 4. Tasks

[x] **T1 — Probes and decision record 0017.**
- Run the open probes of section 3.1 and add them to the tables.
- Write the probe tests first, in `tests/solver/test_ngspice_nonlinear_probes.py` and `test_ltspice_nonlinear_probes.py`, with M15's shape: line, whether the solver runs it, and the library's reading. They fail until the forms are in.
- Write 0017 from section 2 as decided, status `proposed` until M15b closes, and add it to the decisions index.

[x] **T2 — Corpus first.** Add the new files of section 3.2 with manifests (rejects with line, column and error, and `LTSPICE_RUNS` where LTspice runs them). Keep the `pending` marks for now; T9 removes them.

[x] **T3 — Nodes and `control` as a tuple (recommendations 1 and 2).**
- `Table`, `TablePoint` and the three new `ControlledSource` fields in `model/nodes.py`, exported from the package, with docstrings.
- `control: tuple[ElementReference, ...]` on `Cccs`, `Ccvs` and `CurrentSwitch`, set for the linear and `value=` forms. Update every reader in `src/` (`document/topology.py`, `index.py`, `diagnostics.py`, the edit verification) and every test that reads `.control`.
- **Tests:** the signature snapshot and the compatibility test are unchanged, and `control` is a one-source tuple on every M14 corpus F, H and W line.
- The breaking change goes in the CHANGELOG, `elements.md`, `docs/usage/elements.md` and architecture §5.3.

[x] **T4 — POLY (recommendations 3 and 4).** On all four letters and both dialects, in `model/_rules_nonlinear.py`:
- the grammar's flat field list after `POLY(N)`, LTspice's pairs, and ngspice's `m=` on F and G;
- the transformer's count, the minimum coefficients, and the dimension as an integer literal.
- **Negative tests:** too few fields (at the line's end), a dimension of 0 or a formula, ngspice parentheses, LTspice sources in parentheses, too few coefficients.
- **Topology tests:** the control nodes are in `nodes`, `nets()` and the signature; F's and H's sources are `control` entries, resolved and diagnosed as M14's, including `UNRESOLVED_ELEMENT` for a missing one. A test that changing any control node or source is a `TopologyViolation`.
- **Spec entries:** `NG-PLY-001` and `LT-PLY-001`.

[x] **T5 — TABLE and `table=` (recommendations 1 and 4).**
- ngspice: both forms on E, the expression form on G with `m=`; the layouts, the minimums and numbers-only values. G's four-node line becomes a `ParseError`.
- LTspice: `table=` on E and G, flat, with its minimums.
- The ngspice refusal of a net named `table` (recommendation 5), with its probes.
- **Spec entries:** `NG-TBL-001` and `LT-TBL-001`. NG-NLS-001 loses `table_form` and `TABLE4_KW`.

[x] **T6 — `Laplace=` (LTspice).** E and G `Laplace=` with its parameters, and B's `laplace=` on `V=` and `I=`.
- `s` is not a reference; `V()` or `I()` in the formula is refused at the read.
- **Negative tests:** an unknown parameter, a parameter before `Laplace=`, two nodes, B `R=` or `P=` with `laplace=`, `window=` without `laplace=`.
- **Spec entry:** `LT-LAP-001`. LT-UNS-001 loses B's `laplace=`.

[x] **T7 — FREQ and the gates (ngspice).**
- FREQ on E and G: the expression, the format words and the points, with the refusals of recommendation 4.
- AND, OR, NAND and NOR on E: the inputs counted from the line and refused when they are not 2N, or fewer than two pairs (decision 3), and the two points. G is refused.
- **Topology test:** changing any gate input is a `TopologyViolation`.
- **Solver tests:** FREQ in `.ac` (the manual supports only AC), the gates in `.op`.
- **Spec entry:** `NG-XSP-001`. NG-UNS-001 loses these forms.

[x] **T8 — The query and edits (recommendations 6 and 7).**
- `expression_reads` on TABLE and FREQ, with document-layer tests, and none on `Laplace=`.
- `set_table` and `set_poly_coefficients` in `edit/_ops_nonlinear.py` and `edit/api.py`; `set_expression` and `set_param` on the new slots; `set_value`'s message on these forms.
- **Golden diffs** for each form on both dialects, in each layout, and with a change in the number of points or coefficients.
- **Property tests** that no edit here changes the signature.
- **Solver tests** that an edited table, coefficient, FREQ point and `Laplace=` formula move the result.

[x] **T9 — Corpus and snapshots.**
- The `pending` marks go, and every M15b accept file loads, round-trips and runs in its sweep.
- `e_poly_too_few.cir`'s manifest entry becomes a `ParseError` at the line's end. The tree snapshot gains the new files and changes that entry, with its docstring saying so.
- No existing signature snapshot entry changes. If the new terminals change the expected-terminal lists of the 17 rejected files again, the snapshot docstring says so, as in M13 to M15.
- The tests of section 3.3 that pinned the forms as unsupported change: the LTspice validation test moves to `.machine`, the last named exclusion.

[x] **T10 — Documentation.**
- Spec entries: NG-VCV, NG-VCC, NG-CCC, NG-CCV and their LTspice twins point to the new entries; NG-UNS-001 and LT-UNS-001 lose the forms.
- `docs/design/elements.md`, `edit-layer.md` and `document-layer.md`; `docs/usage/elements.md`, `editing.md` (a POLY and a table example) and `errors.md`.
- Both `discrepancies.md`, with a row for each refusal a solver runs, and the README rows.
- README, CHANGELOG (an "Unreleased" section) and the architecture amendments.

[x] **T11 — Final evidence and handover.** Open the pull request. Run the full local check set with `--require-solver ngspice --require-solver ltspice`, record it and the CI run in section 5, list the design points worth reviewing, and set the status to `READY FOR REVIEW`.

### After the maintainer's approval

[ ] **T12 — Close M15b.** Archive this list, accept decision 0017, and update the plan and index.

## 5. Results

### 5.1 Evidence

- **Full local check set** (2026-11-08): `pytest --require-solver ngspice --require-solver ltspice` on ngspice 47 and LTspice 26.1.1: **8,049 passed, 2 skipped**, 968 deselected (the other dialect's `ngspice_only` and `ltspice_only` runs), coverage **98.46%** (floor 90%), in 20 min 14 s. The two skips are the ones every run has.
- `ruff check`, `ruff format --check`, `mypy`, `mypy --strict` on the named tests, `lint-imports` and `pre-commit run --all-files` pass.
- **Exit criteria:** every form has golden diffs (`nonlinear_*` cases of both `edits_golden` families) and solver tests that an edited table, coefficient, FREQ point and `Laplace=` formula move the result. The signature snapshot is unchanged and its compatibility test passes. A negative test shows that changing any POLY control node, gate input or POLY controlling source is a `TopologyViolation` (`tests/document/test_nonlinear_topology.py`). Every M15b accept file of both `controlled_sources` families loads, round-trips byte-exact and runs in its solver sweep (809 tests of the three sweeps pass).
- The tree snapshot changed as 0017's task list says: ten files that M15 wrote as rejects now parse, `e_poly_too_few.cir` is a `ParseError` at the line's end, and 18 files are new. No rejected file's expected terminals changed, because M15b adds no element letter (the snapshot's docstring says so).
- **CI:** see the pull request.

### 5.2 Design points worth reviewing

1. **Two findings that add discrepancies rows the task list did not have** (T1, above): ngspice runs `m=` after an E's POLY, and runs a `Hz` suffix on a later FREQ frequency. Both follow decision 3 and 4 (refuse what the manual does not show), so the library refuses them; say if you would rather accept either.
2. **ngspice's FREQ with a first frequency other than 1 or 2 stopped** in the probes, from ngspice's expression pass and not from the form. The library loads such lines. The row is in the probe notes only; I did not chase the cause.
3. **`set_table` and `set_poly_coefficients` replace values one for one when the shape is unchanged**, and rewrite the points or the run only when the number changes. Decision 6 says "writes them in the layout already on the line"; the minimal edit keeps tight forms such as `(0,0)(2,4)` byte-exact, and a rewrite uses the separator between the first two values. A comment among the coefficients blocks a change of count.
4. **`Table.layout` of a single group.** One parenthesised group with exactly two values (three for FREQ) is `"pairs"`, one point; a longer single group is `"flat"`. A flat list of two values and a pair cannot be told apart in the text, and writing them the same loses nothing.
5. **`LT-UNS-001` has no grammar rule left.** It keeps the phase-2 letters and lists `body_line` under `core_rules`, which the coverage check requires of an entry with no rule of its own. If you would rather retire the entry, say so.
6. **The bare-`TABLE` refusal** (`TABLE v(vx) = …`) is recognised by a lookahead that finds `(` in the next word (a node name cannot hold one), so a net named `table` is not mistaken for it. It is the only place a keyword's recognition looks past the next field.
7. **POLY's coefficients on ngspice** refuse a bare name (`0 k`) although ngspice runs it, as decision 4 says (the gain slot), and so does the discrepancies row.
8. `Laplace=`'s `V()`/`I()` refusal is for E and G only: B's `laplace=` formula was not probed for it.
9. The model layer may not import `re` (a contract test), so the FREQ suffix check and the `V(`/`I(` scan are small hand-written scanners in `_rules_nonlinear.py`.
10. The new decision record is `proposed`; T12 accepts it.
