# M15 task list — Behavioural forms (B, and nonlinear E, F, G, H, C and L)

> **Status:** ACTIVE — the maintainer accepted the decisions in section 2 (2026-11-06)
> **Part of:** [phase-2-plan.md](./phase-2-plan.md) (milestone M15). Governed by [architecture.md](../architecture.md) (§2, §5.3, §7.2, §7.8, §8, §10).

## 1. Scope

M15 adds the behavioural sources and the nonlinear forms that M14 left `UnsupportedConstruct`. An expression may read nets and sources outside the element's node list. The plan's decision stands (section 8, point 1): expression edits are allowed, the reads stay out of the signature, and a read-only query reports them.

- **B on both dialects:**
  - ngspice `V=` and `I=` (manual §5.1), with `tc1=`, `tc2=`, `temp=` and `dtemp=`;
  - LTspice `V=`, `I=`, `R=` and `P=`, with `ic=`, `tripdv=`, `tripdt=`, `Rpar=`, `vprx=`, and `laplace=` with `window=`, `nfft=` and `mtol=`.
- **Nonlinear E, F, G and H:**
  - ngspice: E `vol=` and `value`, G `cur=` and `value` (with `m=`), both TABLE forms, and POLY on all four (§5.2, §5.3, §5.5);
  - LTspice: E and G `value=`, `table=`, `Laplace=` and POLY; F and H `value=` and POLY.
- **ngspice's XSPICE forms of E** (§5.2.6, §5.2.7): FREQ and AND, OR, NAND and NOR. Both run on ngspice 47.
- **Behavioural C and L:** ngspice C `q=` (§3.3.9), and LTspice C `Q=`, L `Flux=` and L's hysteretic core.
- **Formula scan:** reads `{…}` inside a bare expression, LTspice's `~` operator, and the words an expression gives a meaning to: LTspice `time`, `x` in `Q=` and `Flux=`, and `s` in Laplace. This closes the `time` note carried from M8 (m8-tasks 13.2).
- **Edit API and query:** set an expression, a table and polynomial coefficients; report the nets and sources an expression reads.
- **Not in M15:** evaluating an expression (non-goal 6), checking a table's monotony or a polynomial's coefficient count against its dimension beyond the node count, and the behavioural A devices (M17).

**Exit (plan):** every form has golden diffs and solver tests showing that results move as expected.

## 2. Decisions (maintainer, 2026-11-06)

The maintainer accepted all ten recommendations on 2026-11-06, including the five that needed input: the split (1), the node classes (3), the query (6), POLY's counting (8) and the XSPICE forms in M15b (9). "Alternative" marks an option considered and not chosen. The probes behind them are in section 3.

1. **Split M15 in two, both before M16.** *(Your input.)*
   - **M15, behavioural expressions:**
     - B on both dialects;
     - the expression forms of E, F, G and H (ngspice `vol=`, `cur=`, `value`; LTspice `value=`);
     - ngspice C `q=`, and LTspice C `Q=`, L `Flux=` and the hysteretic L;
     - the formula scan, the expression edit and the read-only query.
   - **M15b, tables, polynomials and transfer functions:** TABLE and `table=`, POLY, `Laplace=` (E, G and B), and ngspice's FREQ and AND, OR, NAND and NOR.
   - **Why:**
     - POLY puts control nodes and sources in the topology (decision 8), and tables and polynomials need their own edits.
     - Together that is about twice M14's grammar, nodes and edits, in one review.
     - Each half has its own exit and corpus files (section 3.3). The plan gains a row, and M16 keeps its number.
   - *Alternative:* one milestone, as the plan has it now.
2. **Where a bare expression ends.**
   - An expression that is not in quotes or braces runs to the line end, or to the first trailing parameter its element takes: ngspice B `tc1= tc2= temp= dtemp=`; LTspice B `ic= tripdv= tripdt= Rpar= vprx= laplace= window= nfft= mtol=`.
   - It may hold blanks and `+` continuations. Both solvers read `B1 out 0 V = 2 * v(vx) tc1=0` that way.
   - It is one grammar terminal, a lookahead over those names (P13); the text is kept as written.
   - `vol=` needs quotes or braces, as the manual writes, and ngspice stops on it bare.
3. **Node classes.** *(Your input: the names, and whether `value` becomes optional.)*
   - `BehavioralSource` (B), with `quantity: "v" | "i" | "r" | "p"`, `expression: Formula` and `params`.
   - The expression forms of E, F, G and H keep their M14 classes, `Vcvs` and the rest. They gain `expression: Formula | None` and `form` (the keyword: `vol`, `cur` or `value`), and `ControlledSource.value` becomes `Value | None`: one of the two is set.
     - The class still follows the letter, as for every other element.
     - A caller who checks `isinstance(item, Vcvs)` keeps finding every E line.
   - *Alternative:* new classes for the expression forms (`ExpressionVcvs`, …). That keeps `value` mandatory, but the letter no longer names one class.
   - `Formula` keeps its current shape: a bare expression has `delimiter=""`, as LTspice's bare `.param` expressions already do.
4. **Behavioural C and L.**
   - `Capacitor` gains `charge: Formula | None` (ngspice `q=`, LTspice `Q=`), and `Inductor` gains `flux: Formula | None` (LTspice `Flux=`). `value` is then `None`.
   - The hysteretic L is an `Inductor` with no value, and `Hc= Bs= Br= A= Lm= Lg= N=` as parameters, a closed list from the reference.
   - ngspice's `R=`, `C=` and `L=` expressions already load as formula values (M3) and stay that way.
5. **The formula scan.**
   - In an expression, the scan reads `{…}` inside a bare expression and LTspice's `~`, so that `V = V(1) < {Vlow} ? …` gives its parameter references. ngspice's own examples write that form.
   - The words an expression gives a meaning to are not parameters there:
     - LTspice's `time` in B and `value=`;
     - `x` in `Q=` and `Flux=`;
     - `s` in `Laplace=` and `laplace=`.
   - ngspice's `time`, `temper` and `hertz` are reserved already.
   - In a `.param` and in R, C and L values, LTspice's `time` stays an ordinary name, as M8 found. With `.param time=3k`, `{time}` is still the parameter outside an expression.
   - This is a scan of names, never an evaluator.
6. **The read-only query and its diagnostics.** *(Your input: the name and shape.)*
   - `Netlist.expression_reads(designator, scope=())` returns a tuple of `ExpressionRead(kind, name, span, target)`. `kind` is `"node"` (each name in `V(a)` or `V(a,b)`) or `"source"` (`I(Vx)`), and `target` is the `Net` or the element, or `None`.
   - **Diagnostics:**
     - A `V()` of a net no element connects to gets a new warning, `UNRESOLVED_NODE`: ngspice reports a singular matrix, and LTspice says "No such node".
     - An `I()` of a missing element gets `UNRESOLVED_ELEMENT`, as F's controlling source does. LTspice's `I(X1:Vq)` is info, a known limit.
     - ngspice's `i()` may name any device ("the current through the first node", §5.1), so there is no mismatch check.
   - The reads stay out of the signature (plan section 8, point 1).
   - *Alternative:* a netlist-wide `expression_reads()` that lists every expression's reads at once, or a reverse query from a net to the expressions that read it. Either can be added later on top of this one.
7. **Edits.**
   - `set_expression(designator, text)` replaces an expression's text inside its delimiters, which stay as written: braces, quotes or none.
   - It covers B, the expression forms of E, F, G and H, C's charge and L's flux, and an R, C or L formula value (where `set_formula` also works).
   - The quantity (`V=` → `I=`) and the form (`vol=` → `value`) are not editable: changing them changes what the element is.
   - The other parameters (`tc1=`, `ic=`, `Rpar=`, `m=`) use `set_param`.
   - In M15b: `set_table(designator, points)` and `set_poly_coefficients(designator, values)`.
8. **POLY's control nodes are topology, counted from the dimension.** *(M15b; your input.)*
   - After `POLY(N)`, the grammar reads a flat list of fields. The transformer takes the first 2N names as control nodes (E, G), or the first N as controlling sources (F, H), and the rest as coefficients.
   - Fewer fields than that is a `ParseError` at the line's end, as ngspice stops with "Number of connections differs from poly dimension".
   - The control nodes join `nodes`, after the output pair, and the controlling sources are `controls: tuple[ElementReference, …]` with `control` entries in the signature, as M14's.
   - This is counting, which an LALR grammar cannot do, so it is the second refusal by position in the transformer after M13's model check (P13).
   - LTspice's `(vx,0)` pairs are grouped by the grammar.
9. **Forms the references do not show, and ngspice's XSPICE forms.** *(Your input on FREQ and AND/OR.)*
   - **Refused (decision 0002):**
     - ngspice B `r=`, which stops ngspice;
     - ngspice `vol=` without delimiters, which stops ngspice;
     - on LTspice, ngspice's `vol=` (stops) and `TABLE {…} =`, which LTspice runs but its reference does not show. The last goes in `discrepancies.md`.
   - **ngspice `LAPLACE` stays a `ParseError`:** the manual says ngspice does not offer it, and ngspice stops.
   - **FREQ and AND, OR, NAND and NOR are in M15b:** they are in the manual and run on ngspice 47, and v1 leaves no manual form unsupported (decision 0013 item 7, §6.7).
   - *Alternative:* a named exclusion in v1, as `.machine` is, since they need XSPICE.
10. **One decision record, 0016, for M15** (and 0017 for M15b).
    - It amends §5.3 (`BehavioralSource`, the new fields), §7.2 (the operations) and §7.8 (expression reads, with the query), and decision 0006 (`UNRESOLVED_NODE`).
    - The rules go in a new family module, `model/_rules_behavioral.py`, with `edit/_ops_behavioral.py` (P12).

## 3. Starting point (2026-11-06, `d9a25de`, branch `m15-behavioral`)

### 3.1 Probes

Probes on ngspice 47 and LTspice 26.1.1, run from a scratch script. Each circuit drives `vx` to 1 V (`.op`), with a 1 V source through a 1k resistor and a 0 V sense source, a 1k load on `out`, and `.param k=2`.

| Line | ngspice 47 | LTspice 26.1.1 |
|---|---|---|
| `B1 out 0 V=2*v(vx)`, `V = 2 * v(vx)`, `v={…}`, `v='…'` | Run | Run (no quotes form probed) |
| `V = 2 * v(vx) tc1=0`; a `+` continuation inside | Run | Run (continuation) |
| `V={k}*v(vx)`, `V=k*v(vx)` | Run | Run |
| `I=2*i(Vsense)` | Runs | Runs (`I(V1)`) |
| `V=… I=…`; no expression | Stop | Stop |
| `R=1k` on B | Stops: "unknown parameter (r)" | Runs; also `P=`, `vprx=`, `Rpar=`, `ic=`, `tripdv=`, `tripdt=` |
| `laplace=1/(1+s/1k)` on B | — | Runs |
| `time` in B | Runs | Runs |
| `V(nonode)` | Stops: singular matrix | Stops: "No such node" |
| `I(Vnone)` | Stops: "unknown controlling source" | Stops: "No such instance" |
| `I(X1:Vq)` | — | Runs |
| E `vol='…'`, `vol={…}` / `vol=…` bare | Run / stops | Stops ("Expected 2 node names") |
| E `value={…}`, `value {…}`, `value='…'`; LTspice `value=…` bare | Run | Run |
| E `TABLE {v(vx)} = (0,0) (1,2)`, with or without `=` | Runs | Runs (not in the reference) |
| E 4 nodes `TABLE = (…)`; `table=(…)` | Run | Runs (`table=`) |
| E `POLY(1) vx 0 0 2`, `POLY(2)` | Run | Run, also with `(vx,0)` pairs |
| E `POLY(2)` with one pair | Stops: "Number of connections differs" | — |
| E `Laplace=` (4 nodes), `LAPLACE {…} {…}` | Stops | Runs (`Laplace=`, `window=`, `nfft=`) |
| E `FREQ {…}= DB (…)`, `and(2) …` | Run (XSPICE) | — |
| G `cur='…' m=2`, `value`, TABLE, POLY | Run | Run (`value=`, `table=`) |
| F, H `POLY(1) Vsense 0 2`; `value={…I(…)}` | Run (POLY) | Run |
| R `R='…'`, R `'…'`, C `c='…'`, C `q='…'`, L `L='…'` | Run | — |
| C `Q=1u*x`, with `ic=` and `m=`, `Q={…}`; L `Flux=1m*tanh(5*x)`; L `Hc=… N=1000` | — | Run |

### 3.2 The example as given

`test_bsource.cir`, `B1 /OUT GND v={2*v(/VX)}`, runs on ngspice 47 with `v(/out)` = 2.0. Today the library stops at it with `UnsupportedConstruct` (the planned letter B).

### 3.3 Files written for M15 (uncommitted, credited to xdylanm under MIT)

Each changes one thing from one of your files, named in a comment on its second line. Every accept file runs with the output of the file it came from (2.0 for the E and B files, 1.0143 for G, 2.2 for F and H). Every reject stops its solver, except `e_table_braces.cir`, which LTspice runs on purpose.

| | ngspice (`controlled_sources`) | LTspice (`controlled_sources`) |
|---|---|---|
| **M15** | `test_bsource_current`, `_bare`, `_continued`, `_quoted`, `_param`, `_ternary`, `_pwl`, `_sense`, `_special`; `test_esource_vol`, `_value`, `_value_no_equals`; `test_gsource_cur`, `_value`; `test_behavioral_rcl` | `lt_test_bsource`, `_braces`, `_spaces`, `_current`, `_resistor`, `_power`, `_trip`, `_time`, `_sense`; `lt_test_esource_value`, `lt_test_gsource_value`, `lt_test_fsource_value`; `lt_test_capacitor_charge`, `lt_test_inductor_flux`, `lt_test_inductor_hysteretic` |
| **M15b** | `test_esource_table`, `_table_nodes`, `_poly`, `_poly2`, `_freq`, `_and`; `test_gsource_table`, `_poly`; `test_fsource_poly`, `test_hsource_poly` | `lt_test_bsource_laplace`; `lt_test_esource_table`, `_laplace`, `_poly`, `_poly_paren`; `lt_test_hsource_poly` |
| **Rejects** (`elements_rejects`) | `b_v_and_i`, `b_no_expression`, `b_r`, `e_vol_bare`, `e_laplace`, `e_poly_too_few` | `b_v_and_i`, `b_no_expression`, `e_vol`, `e_table_braces` (LTspice runs it) |

The M15b files are written now, so that one review confirms their provenance. They wait in the family until M15b, and the solver sweep skips them with that reason.

**In the repository:**
- B is `planned` in both device matrices, so the loader raises `UnsupportedConstruct` for it.
- M14's grammar recognises each nonlinear keyword only to raise `UnsupportedConstruct` (decision 0015 item 9), so each form here starts from a positioned refusal.
- The formula scan (`grammar/formula.lark`) already reads `v(…)`, `i(…)` and ngspice's reserved words; it fails, and gives no references, on `{…}` inside an expression.

## 4. Tasks (M15)

[ ] **T1 — Decision record 0016.** Status `proposed` until M15 closes. It records section 2, with the amendments of decision 10.

[ ] **T2 — Commit the corpus first.** Both families' new files and manifests (the M15b files skipped with their reason), the rejects with line, column and error, and the solver sweeps. Each later task makes some files pass.

[ ] **T3 — Expressions in the grammar (decision 2).** The bare-expression terminal per dialect and element, with its trailing parameters. Tests first:
- an expression with blanks and continuations, and with a trailing parameter;
- a quoted or braced expression;
- the refusals of decision 9.

[ ] **T4 — B on both dialects (decision 3).** `BehavioralSource`, with the quantity, the expression and the parameter lists of each dialect.
- **Negative tests:** two quantities, none, ngspice `r=`.
- **Solver tests:** each B probe of section 3.1, and a test that the output moves with the expression.
- **Spec entries:** `NG-BEH-001` and `LT-BEH-001`. The device matrices show B as `supported`.

[ ] **T5 — The expression forms of E, F, G and H, and behavioural C and L (decisions 3 and 4).** ngspice `vol=`, `cur=` and `value`; LTspice `value=`. Then ngspice C `q=`, and LTspice C `Q=`, L `Flux=` and the hysteretic L. The `UnsupportedConstruct` refusals of these forms go, and the M15b forms keep theirs. Spec entries `NG-NLS-001` and `LT-NLS-001`, and updates to the C and L entries.

[ ] **T6 — The formula scan (decision 5).** The expression context, with braces, `~`, and the context words. Tests show:
- `V(1) < {Vlow} ? {Vlow} : V(1)` gives `Vlow`;
- LTspice's `time` in B is not a reference, while `{time}` in a `.param` still is;
- `x` in `Q=` is not a reference.

[ ] **T7 — The query and diagnostics (decision 6).** `expression_reads`, `UNRESOLVED_NODE`, and `UNRESOLVED_ELEMENT` for `I()`, with document-layer tests and the LTspice `X1:Vq` info.

[ ] **T8 — Edits (decision 7).**
- `set_expression` on every expression slot, and `set_param` on the trailing parameters.
- Golden diffs for each form on both dialects, and property tests that no expression edit changes the signature.
- Solver tests that an edited expression moves the result.

[ ] **T9 — Corpus and snapshots.** Every M15 accept file loads, round-trips and runs in its sweep. The tree snapshot gains the new files, and the signature snapshot does not change.

[ ] **T10 — Documentation.**
- `docs/design/elements.md`, `docs/usage/elements.md` and `editing.md` (a B example), `edit-layer.md`, `document-layer.md`, `errors.md`;
- both `discrepancies.md`, the README, CHANGELOG and the architecture amendments.

[ ] **T11 — Final evidence and handover.** Open the pull request. Run the full local check set with `--require-solver ngspice --require-solver ltspice`, record it and the green CI run in section 5, and set the status to `READY FOR REVIEW`.

### After the maintainer's approval

[ ] **T12 — Close M15.** Archive this list, accept decision 0016, and update the plan and index. Then write the M15b task list from decisions 1, 7, 8 and 9 and the M15b files of section 3.3.

## 5. Results

To be filled in by T11.
