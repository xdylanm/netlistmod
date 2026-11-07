# M15 task list — Behavioural forms (B, and nonlinear E, F, G, H, C and L)

> **Status:** ACTIVE — review round 2 (section 7) requires change R6 before M15 can close. R1 to R5 of round 1 are made (section 6.5); section 2 records the maintainer's decisions (2026-11-06).
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

[x] **T1 — Decision record 0016.** Status `proposed` until M15 closes. It records section 2, with the amendments of decision 10.

[x] **T2 — Commit the corpus first.** Both families' new files and manifests (the M15b files skipped with their reason), the rejects with line, column and error, and the solver sweeps. Each later task makes some files pass.

[x] **T3 — Expressions in the grammar (decision 2).** The bare-expression terminal per dialect and element, with its trailing parameters. Tests first:
- an expression with blanks and continuations, and with a trailing parameter;
- a quoted or braced expression;
- the refusals of decision 9.

[x] **T4 — B on both dialects (decision 3).** `BehavioralSource`, with the quantity, the expression and the parameter lists of each dialect.
- **Negative tests:** two quantities, none, ngspice `r=`.
- **Solver tests:** each B probe of section 3.1, and a test that the output moves with the expression.
- **Spec entries:** `NG-BEH-001` and `LT-BEH-001`. The device matrices show B as `supported`.

[x] **T5 — The expression forms of E, F, G and H, and behavioural C and L (decisions 3 and 4).** ngspice `vol=`, `cur=` and `value`; LTspice `value=`. Then ngspice C `q=`, and LTspice C `Q=`, L `Flux=` and the hysteretic L. The `UnsupportedConstruct` refusals of these forms go, and the M15b forms keep theirs. Spec entries `NG-NLS-001` and `LT-NLS-001`, and updates to the C and L entries.

[x] **T6 — The formula scan (decision 5).** The expression context, with braces, `~`, and the context words. Tests show:
- `V(1) < {Vlow} ? {Vlow} : V(1)` gives `Vlow`;
- LTspice's `time` in B is not a reference, while `{time}` in a `.param` still is;
- `x` in `Q=` is not a reference.

[x] **T7 — The query and diagnostics (decision 6).** `expression_reads`, `UNRESOLVED_NODE`, and `UNRESOLVED_ELEMENT` for `I()`, with document-layer tests and the LTspice `X1:Vq` info.

[x] **T8 — Edits (decision 7).**
- `set_expression` on every expression slot, and `set_param` on the trailing parameters.
- Golden diffs for each form on both dialects, and property tests that no expression edit changes the signature.
- Solver tests that an edited expression moves the result.

[x] **T9 — Corpus and snapshots.** Every M15 accept file loads, round-trips and runs in its sweep. The tree snapshot gains the new files, and the signature snapshot does not change.

[x] **T10 — Documentation.**
- `docs/design/elements.md`, `docs/usage/elements.md` and `editing.md` (a B example), `edit-layer.md`, `document-layer.md`, `errors.md`;
- both `discrepancies.md`, the README, CHANGELOG and the architecture amendments.

[x] **T11 — Final evidence and handover.** Open the pull request. Run the full local check set with `--require-solver ngspice --require-solver ltspice`, record it and the green CI run in section 5, and set the status to `READY FOR REVIEW`.

### After the maintainer's approval

[ ] **T12 — Close M15.** Archive this list, accept decision 0016, and update the plan and index. Then write the M15b task list from decisions 1, 7, 8 and 9 and the M15b files of section 3.3.

## 5. Results

**Pull request:** [xdylanm/netlistmod#12](https://github.com/xdylanm/netlistmod/pull/12), branch `m15-behavioral`.

**Full local run** at `77df2c7` (2026-11-06; Windows, Python 3.14, ngspice 47 and LTspice 26.1.1 with `--require-solver ngspice --require-solver ltspice`):
- ruff, ruff format, mypy (src and the strict test set) and the import contract are clean.
- pytest: 7,360 passed, 2 skipped, coverage 98.55%, in 18 min 20 s.
- Every M15 accept file of both `controlled_sources` families loads, round-trips byte-exact and runs in its solver sweep; the M15b files are skipped there, marked `pending` in their manifests.
- The signature snapshot is unchanged.
- pre-commit's end-of-file hook removed an extra blank line at the end of `docs/grammars/ngspice/discrepancies.md`; that was the only finding, and CI's lint job failed on the same line. The fix is in the commit that sets this status.

**CI** on #12 at `77df2c7`: the four test jobs (Linux and Windows, Python 3.13 and 3.14) passed; "Lint and types" failed on that end-of-file line only.

**Design points worth reviewing:**
1. **`Rpar=` on a `V=` or `P=` B source is refused on LTspice,** with its own message. Found while probing: LTspice stops on it ("only allowed for behavioral current sources"), and the reference lists `Rpar=` for `I=` only. It runs on `R=`, which loads. Decision 0016 item 9 records it; section 2 did not.
2. **`vprx=` on a `V=` B source is accepted:** LTspice runs it, though the reference shows it for `P=` only (an observed parameter, as for other LTspice lists). The LTspice `discrepancies.md` records it.
3. **The stale-citation check is narrowed.** It rejected §5.1.1 and §5.2.1 to §5.2.4, numbers phase 1 had cited for chapter-2 sections. In the edition in `references.md` they are the B and E source sections that M15 cites, so `tests/architecture/test_spec_coverage.py` no longer rejects them; `§§` and `manual, §` are still rejected.
4. **A bare expression ends before any blank that is followed by a name and `=`** (not `==`), not only before the element's own parameters. An unknown parameter such as `tc1=` on an LTspice B is then refused instead of being read into the expression, and `set_expression` refuses new text that would end early.
5. **The expression forms of E and G sit under a new marker, NG-NLS-001 and LT-NLS-001,** and B's `laplace=` under LT-UNS-001, so each spec entry lists the rules it covers.
6. **The tree snapshot:** the same 17 rejected files list "behavioral source (`B`)" among their expected terminals. The M15 terminals got readable names in `grammar/loader.py`, so that the list does not show `B_NAME`.
7. **`document_basic/node_read.cir` is a new fixture** for `UNRESOLVED_NODE`, rather than a line in an existing file, so that no digest in the signature snapshot changes (the M14 lesson).
8. **Two M14 probe tests changed:** their `value=` rows now expect the line to load, and an LTspice validation test uses the M15b forms (POLY, `Laplace=`, B `laplace=`) instead of `Q=`, `Flux=` and `value=`.

## 6. Review round 1 (2026-11-06, `32c0b3e`)

### 6.1 Outcome

M15 goes back for changes R1 to R5. Most of the design holds up on review:
- **Checks:**
  - pytest with ngspice 47 and LTspice 26.1.1 from `.env` (`--require-solver ngspice --require-solver ltspice`): 7,360 passed, 2 skipped, coverage 98.55%, in 18 min 32 s. This matches section 5.
  - ruff, ruff format and `mypy src` are clean.
  - CI on #12 at `32c0b3e` is green on all five jobs.
- **Grammar:**
  - The bare expression ends where decision 2 says. By hand on ngspice: `>=`, `<=`, `!=` and `==` stay inside it, and `;` and `$ ` end it. `tc1=` after a brace, quoted or bare expression is a parameter, and a `+` continuation stays inside a bare expression with `tc1=` after it. `{k} * v(vx)` is a bare expression, and `{k}` alone is a braced one.
  - `m=` on an ngspice B and `tc1=` on an LTspice B are refused at the parameter. So are a bare `vol=` and `cur=`, and `Rpar=` on an LTspice `V=` B, each with its own message.
  - A node named `vol` or `cur` stays a node, and ngspice runs that line.
- **Nodes:** `Vcvs`, `Vccs`, `Cccs` and `Ccvs` keep their classes, and `form`, `expression` and `value` are set as decision 3 says. LTspice's F and H `value=` have `control=None`, as the decision record (item 3) states. The hysteretic L loads its seven parameters with no value.
- **Formula scan:** `v(vx) < {k} ? {k} : v(vx)` gives `k`, and `~` reads on LTspice. `time` in an LTspice B, and `x` and `time` in `Q=`, give no references. `{time}` in an R value with `.param time=3` stays a parameter.
- **Query and diagnostics (probed on both solvers):**
  - A subcircuit's B that reads a top-level net gets `UNRESOLVED_NODE`, and both solvers stop on it. A `.global` net resolves.
  - A read in a scope with an `.include` is info.
  - `i(R1)` on ngspice loads with no diagnostic, and ngspice runs it, as decision 6 says.
- **Edits:** `set_expression` keeps the delimiter for ordinary text. It refuses ` tc2=1` and `; x` inside a bare expression, an empty expression, and a quote inside a quoted one. `set_value` on an expression form names `set_expression`.
- **Section 5's design points 1 to 8:** accepted. Point 4 (any blank followed by `name=` ends a bare expression) is the right default: it turns a misspelt parameter into an error instead of a silent change to the expression.

### 6.2 Required changes

[x] **R1 — A read into a subcircuit instance is not an unresolved node.**

| Line (with `X1 vx sub`, and `sub` holding `R1 a n 1k`, `R2 n 0 1k`) | Solver | Library today |
|---|---|---|
| ngspice `B1 out 0 V=v(x1.n)` | runs, `v(out)` = 0.5 | `UNRESOLVED_NODE` warning |
| LTspice `B1 out 0 V=V(X1:n)` | runs, `v(out)` = 0.5 | `UNRESOLVED_NODE` warning |
| ngspice `B1 out 0 V=1k*i(v.x1.vq)` (with `Vq` in `sub`) | runs | `UNRESOLVED_ELEMENT` warning |
| ngspice `B1 out 0 V=1k*i(x1.vq)` | stops, "unknown controlling source v_x1.vq" | `UNRESOLVED_ELEMENT` warning (right) |

- Reading a node inside a subcircuit is a common way to probe it, so a warning here is a false positive. Decision 6 already makes LTspice's `I(X1:Vq)` info for this reason.
- **Change:** a node read whose first part names an instance of the scope (ngspice `x1.n`, LTspice `X1:n`) is info, as a known limit, in the same way `I(X1:Vq)` is. Its `ExpressionRead.target` stays `None`. Either make ngspice's `i(v.x1.vq)` info too, or record in the ngspice `discrepancies.md` why it stays a warning.
- **Tests:** document-layer tests for each row, and solver probes for the first three rows in `test_*_behavioral_probes.py`. Amend decision 0016 item 6 and the `UNRESOLVED_NODE` entry in `errors.md`.

[x] **R2 — `value` after the output nodes of E or G is the keyword on both solvers.**
- `E1 out 0 value 0 2` and `G1 0 out value 0 1m`, with a net `value` (`Rv value 0 1k`), stop both solvers:
  - ngspice: "mal formed E source instance: e1 out 0 vol= 0 2" (G: `cur=`);
  - LTspice: "Unknown parameter".
- The library loads each as a linear source with the control node `value`, and `test_a_node_named_value_is_a_node` (`tests/grammar/ngspice/test_behavioral.py`) asserts this. M14's review accepted it from the grammar alone (m14-tasks 6.1), and no solver probe backed it.
- `vol` and `cur` in that place are nodes on ngspice, and ngspice runs them; they need no change.
- **Change:** on both dialects, refuse a word `value` after the output nodes of E and G, with its own message at `value`: "`value` here is the keyword of the expression form, and ngspice/LTspice read it so". Probe F and H in the same place (`F1 out 0 value 2`, where `value` names a V) and treat them the same way if a solver stops.
- **Tests:** replace `test_a_node_named_value_is_a_node` with the refusal, on both dialects. Add the lines to both probe files and a reject file to each `elements_rejects` family, and record the change in decision 0016 item 9.

[x] **R3 — `set_expression` may change the delimiter.**
- `B2 out2 0 V={2*v(vx)}`:
  - `set_expression("B2", "3}")` writes `V={3}}`;
  - `"a{b}"` writes `V={a{b}}`;
  - `"1+{k}"` writes `V={1+{k}}`.
- Each loads as a bare expression with `delimiter=""`. The slot check finds a `Formula` over the whole replacement, so it passes, though the docstring and decision 7 promise to keep the delimiters.
- A bare slot given `{k}` becomes a braced formula (`delimiter="{"`). This is the same change in the other direction.
- **Change:** refuse the edit when the re-read formula's delimiter is not the original one. For example, give `SlotCheck` the expected delimiter, or check it in `set_expression`. Say in the message that the text closes the delimiter early. If a bare slot should accept a whole `{…}` instead, decide that and write it in decision 0016 item 7 and the docstring.
- **Tests:** add these three cases and the bare-slot case to `tests/edits/test_behavioral_edits.py`, on both dialects.

[x] **R4 — Give a delimited expression over a `+` continuation an honest refusal.**
- ngspice runs `E1 out 0 value={2*` / `+ v(vx)}` (2.0), `E1 out 0 vol='2*` / `+ v(vx)'` and `B1 out 0 V='2*` / `+ v(vx)'` (2.0). The library refuses all three.
- That matches the existing limit for every formula (`R7 out 0 {1k*` / `+ 2}` is refused too), so refusing is fine. But the `value` case gets the `bare_expression` message: "ngspice reads the expression of `vol=`, `cur=` and `value` only in quotes or braces; write `{...}` or `'...'`". The user already wrote braces. The other two cases get the generic list of expected tokens.
- **Change:** `bare_expression` must not take a field that opens with `{` or `'`. Give an unclosed brace or quote on its physical line one message: "a braced or quoted expression must close on its line; join the lines, or write the expression bare (B only)". Record in the ngspice `discrepancies.md` that ngspice runs these and the library refuses them.
- **Tests:** the three lines, with their message and column, in `tests/grammar/ngspice/test_behavioral.py`, and solver probes showing that ngspice runs them.

[x] **R5 — Bring the LTspice grammar docs up to date, and record what the probes found.**
- `docs/grammars/ltspice/discrepancies.md`, "Forms LTspice runs that the library rejects", still says "`C` has `Q=`; `L` has `Flux=` and the hysteretic form; `.machine`. `UnsupportedConstruct` in phase 1". It also cites `test_nonlinear_forms_are_unsupported`, which no longer exists. Keep `.machine` only, and check the evidence names.
- `docs/grammars/ltspice/README.md` (row C, L) still says "`Q=`, `Flux=`, `Hc=` unsupported".
- LTspice 26.1.1 runs `L1 out 0 Flux=1m*tanh(5*x) Rser=1` and the hysteretic L with `Rser=1`. The library refuses both, though `Q=` takes the capacitor's parameters.
  - If the reference lists parameters for these forms, accept them.
  - If it does not, add a row to "Forms LTspice runs that the library rejects", with a probe.
- ngspice stops on `B1 out 0 V=2*v(vx)$c`, and the library loads it as the expression `2*v(vx)` and a comment. ngspice runs `R7 out 0 1k$c`. Add a row to the ngspice `discrepancies.md` ("Forms the library accepts and ngspice rejects"), with a probe, or refuse it.

### 6.3 Noted, no change required

- Architecture §5.3 still writes `ControlledSource`'s `value: NumericValue | Formula`, before the sentence that makes it `None` for the expression forms. Write `| None` when T12 accepts decision 0016.
- `_control_into_instance` (`document/diagnostics.py`) now applies to every LTspice element reference, not only to controlling sources. So a `K` line's `X1:L2` or a `.save I(X1:R1)` is info too. That is consistent with §7.8, but say so in the function's docstring.
- `BehavioralSource` and `ExpressionRead` are out of order in the two `__all__` lists. This is cosmetic, as in M13 and M14.
- The `formula.lark` change (`%ignore CONT`, `{…}` as an atom) applies to every formula, not only to expressions. No formula outside an expression can hold a continuation or a nested brace today, so nothing changes. A comment there would help the next reader.

### 6.4 Exit for this round

Make R1 to R5. Run the full check set with `--require-solver ngspice --require-solver ltspice`, read CI once after the push, and add a short report as 6.5. Then set the status to `READY FOR REVIEW`. **Do not archive** (T12 follows approval).

### 6.5 Report (round 1, `7084360`)

R1 to R5 are made in `7084360`.

**Checks:**
- Full local run at `7084360` (Windows, Python 3.14, ngspice 47 and LTspice 26.1.1, `--require-solver ngspice --require-solver ltspice`): ruff, ruff format, mypy (src and the strict test set), the import contract and pre-commit are clean. pytest: 7,410 passed, 2 skipped, coverage 98.54%, in 18 min 41 s.
- CI on #12 at `7084360` is green on all five jobs.
- The signature snapshot is unchanged. The tree snapshot adds `elements_rejects/e_value_node.cir` only.

**Changes:**
- **R1:** a node or source read whose first part names an instance of the scope is info, with `target` `None`: ngspice `v(x1.n)` and `i(v.x1.vq)` (the letter, the instance, the name), LTspice `V(X1:n)`, as `I(X1:Vq)` already was. `i(x1.vq)`, which ngspice stops on, stays a warning, and so does a name whose first part is not an instance. The function is `_into_instance` in `document/diagnostics.py`, and its docstring now lists every reference it applies to (6.3). Tests: `test_an_ngspice_read_into_an_instance_is_info` (four rows) and `test_an_ltspice_read_into_an_instance_is_info`; probes `b-into-node`, `b-into-source` and `b-into-source-short` (ngspice) and `b-into-node` (LTspice). Decision 0016 item 6, `errors.md` and `document-layer.md` say so.
- **R2:** `value` and a blank after the output nodes is refused at `value` with "`value` here is the keyword of the expression form, and ngspice/LTspice reads it so; …". Probing F and H with a source named `value` found:
  - ngspice runs `F1 0 out value 2` and `H1 out 0 value 1k` as linear sources, so ngspice F and H are unchanged;
  - LTspice runs them as the expression form: `F1 0 out value 3` gives 3 kV on a 1k load, a constant 3 A. The library would have read a controlling source, so LTspice F and H are refused too.
  - `vol`, `values` and a `value` in the control-node place stay names (`test_other_words_there_are_names`). New rejects: ngspice and LTspice `e_value_node.cir` and LTspice `f_value_source.cir` (which LTspice runs, so it is in `LTSPICE_RUNS`). Decision 0016 item 9 and both `discrepancies.md` record it.
- **R3:** `SlotCheck` gains an optional `delimiter`, and the write-time slot check refuses a re-read formula with another one. The message says that the new text closes the delimiter early, or that a whole `{...}` or `'...'` would make a bare expression a delimited one. The four cases are in `test_set_expression_keeps_the_delimiter` on both dialects, with a quote case on ngspice. Decision 0016 item 7 and the docstring say so.
- **R4:** a new terminal, `OPEN_FORMULA`, is an opening brace or quote with no closing one on its physical line, and runs over the `+` lines after it. After ngspice's `vol=`, `cur=`, `value` and B's quantity it gives "a braced or quoted expression must close on its line; join the lines, or write the expression bare (B only)" at the brace or quote. `bare_expression` no longer takes such a field. This also refuses `B1 out 0 V={2*` / `+ v(vx)}`, which loaded before as a bare expression holding braces. Tests: `test_a_delimited_expression_over_a_continuation_is_refused` (four lines with columns); probes `e-value-continued`, `e-vol-continued` and `b-quoted-continued` show that ngspice runs them. The ngspice `discrepancies.md` records it.
- **R5:**
  - The LTspice "Exceptions to the reference" row keeps `.machine` with its two tests. A new row lists the M15b forms with the current test names. README row C, L is current.
  - The reference shows no parameters on `Flux=` or the hysteretic core. So `Rser=` on them stays refused, with probes `l-flux-rser` and `l-hysteretic-rser` and a row in "Forms LTspice runs and the library rejects".
  - ngspice's stop on `B1 out 0 V=2*v(vx)$c` is a row in the ngspice `discrepancies.md` (probe `b-dollar`). The library still reads `$c` as a comment, as on every line.
- **6.3:** the `formula.lark` comment is added. The `__all__` order is left as it is: those lists are grouped by hand, not sorted. Architecture §5.3's `| None` waits for T12, as noted.

## 7. Review round 2 (2026-11-06, `cf8051b`)

### 7.1 Outcome

R1, R3, R4 and R5 are made as 6.5 reports. R2 is right for the third field of every letter on both dialects. On ngspice, though, `value` is the keyword in every node position of E and G, not only in the third. That is R6 below, the only change left.
- **Checks:**
  - pytest with ngspice 47 and LTspice 26.1.1 from `.env` (`--require-solver ngspice --require-solver ltspice`): 7,410 passed, 2 skipped, coverage 98.54%, in 18 min 30 s. This matches 6.5.
  - ruff, ruff format and `mypy src` are clean.
  - CI on #12 at `cf8051b` is green on all five jobs.
- **R1 (probed on both solvers):**
  - ngspice `v(x1.n)` and LTspice `V(X1:n)` are info, and both solvers run them (`v(out)` = 0.5).
  - ngspice `i(v.x1.vq)` is info, and ngspice runs it.
  - `i(x1.vq)` stays a warning, and ngspice stops on it.
  - `v(x9.n)`, where `x9` is not an instance, stays a warning, and ngspice stops on it.
  - `_into_instance` names every case in its docstring, which also covers 6.3's point.
- **R2:** `E1 out 0 value 0 2` (ngspice) and `G1 0 out value 0 1m` (LTspice) are refused at `value` with the new message, and both solvers stop on them. ngspice runs `F1 0 out value 2` as a linear F, so leaving ngspice F and H unchanged is right. LTspice reads F and H as the value form, so refusing them there is right too, and a good catch.
- **R3:** the `SlotCheck.delimiter` check is in `verify.py`, so the write-time check makes the refusal for every caller of `set_expression`. The message names both directions.
- **R4:** `OPEN_FORMULA` gives the new message at the brace or quote for `value={…`, `vol='…`, `cur='…` (with `m=` after it) and B's `V={…` and `V='…`. ngspice runs each of them. A quoted expression followed by `; it's` still loads, so the terminal does not reach into a trailing comment. A bare expression over a `+` line still loads. The ngspice `discrepancies.md` has the row.
- **R5:** the LTspice discrepancies and README rows are current. The `Flux=` and hysteretic `Rser=` row cites the probes, and the reference shows no parameters there, so refusing them follows P5. The `$c` row is in the ngspice `discrepancies.md`.

### 7.2 Required change

[ ] **R6 — On ngspice, `value` is the keyword in every node position of E and G.**

| Line, with a net `value` (`Rv value 0 1k`) | ngspice 47 | Library at `cf8051b` |
|---|---|---|
| `E1 value 0 vx 0 2` | stops: "mal formed E source instance: e1  vol= 0 vx 0 2" | loads |
| `E1 out value vx 0 2` | stops (`vol=` in the second field) | loads |
| `E1 out 0 vx value 2` | stops (`vol=` in the fourth field) | loads |
| `E1 out 0 vx VALUE 2` | stops (any case) | loads |
| `G1 0 value vx 0 1m`, `G1 0 out vx value 1m` | stop: "mal formed G source instance … `cur=` …" | load |
| `H1 value 0 Vs 1k`, `R5 out value 1k` | run | load (right) |

- ngspice replaces the word `value` with `vol=` (E) or `cur=` (G) wherever it stands on the line. So R2's refusal covers only one of the four node positions.
- 6.5 says that "a `value` in the control-node place" stays a name. That holds for LTspice: `E1 out 0 vx value 2` and `G1 0 out vx value 1m` run there, and `E1 out value vx 0 2` runs too. On ngspice it does not hold, and `test_other_words_there_are_names` does not test it.
- **Change:** on ngspice only, refuse a node written `value` (any case) on an E or G line, in any of the four positions, at that node. Use R2's message or one like it ("ngspice reads `value` on an E or G line as the keyword of the expression form; give the net another name"). This can be a check in the transformer's `_voltage_controlled`, since it is one word in a closed set of positions. Leave LTspice, F, H and the other letters as they are.
- **Tests:** a parametrized refusal over the five ngspice lines above, with columns, in `tests/grammar/ngspice/test_behavioral.py`. A test that the same lines load on LTspice. Solver probes in `test_ngspice_behavioral_probes.py` for the first three rows, showing that ngspice stops. Extend the decision 0016 item 9 sentence and the ngspice `discrepancies.md` row, if R2 added one.

### 7.3 Noted, no change required

- `_is_expression_read` finds the formula by the reference's offset into `expression`, `charge`, `flux` or `value`. That is enough for ngspice's `v.x1.vq` form, which only an `i()` read can write.
- The `__all__` order and architecture §5.3's `| None` stay as 6.5 says; T12 picks up the second.

### 7.4 Exit for this round

Make R6. Run the full check set with `--require-solver ngspice --require-solver ltspice`, read CI once after the push, and add a short report as 7.5. Then set the status to `READY FOR REVIEW`. **Do not archive** (T12 follows approval).
