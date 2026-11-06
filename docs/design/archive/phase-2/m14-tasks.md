# M14 task list — Linear dependent sources and switches (E, F, G, H, S, W)

> **Status:** COMPLETE (2026-11-06) — approved by the maintainer; the results are in section 5, and the reviews in sections 6 and 7
> **Part of:** [phase-2-plan.md](../../phase-2-plan.md) (milestone M14). Governed by [architecture.md](../../../architecture.md) (§2, §5.3, §7.1, §7.2, §7.3, §7.7, §10).

## 1. Scope

M14 adds the linear dependent sources and the switches on both dialects. Their controls are topology (plan section 3, point 2), so the signature must catch any edit that rewires a control path.

- **In:**
  - **E** (VCVS) and **G** (VCCS): four nodes, the output pair then the control pair, and a gain.
  - **F** (CCCS) and **H** (CCVS): two nodes, a controlling source, and a gain.
  - **S** (voltage switch): four nodes, a model, and an optional `on` or `off`.
  - **W** (current switch): two nodes, a controlling source, a model, and an optional `on` or `off`.
  - Switch model types SW (S) and CSW (W), with `MODEL_TYPE_MISMATCH`.
  - Controlling sources resolved in their scope and covered by the signature, with diagnostics when they do not resolve or are not voltage sources.
  - Edits of the gain, `m=`, the switch model and the switch's initial state.
  - The `controlled_sources` corpus families (section 3.3).
- **Not in M14:**
  - The nonlinear and behavioural forms: `value=`, `VALUE`, `TABLE`, `table=`, `POLY`, `vol=`, `cur=` and `Laplace=`, and B (M15). They stay `UnsupportedConstruct`, as now.
  - Reading the current of a source inside an instance (`X1:Vq` on LTspice).
  - Editing any node or controlling source (§7.3).

**Exit:**
- Each letter has spec entries validated on both solvers, golden diffs and property tests.
- A negative test shows that a change to any control node or controlling source is a `TopologyViolation`.
- The signature snapshot is unchanged.
- Every accept file of both families loads, round-trips and runs on its solver.

## 2. Decisions (maintainer, 2026-11-06)

The maintainer accepted all fourteen recommendations on 2026-11-06, confirming the class names (decision 1), the refusal of `gain=` (decision 6) and `set_switch_state` (decision 10), and fixing the schematic of decision 12. "Alternative" marks an option considered and not chosen. The probes behind them are in section 3.

1. **Node classes.**
   - `Vcvs` (E), `Vccs` (G), `Cccs` (F), `Ccvs` (H), `VoltageSwitch` (S) and `CurrentSwitch` (W).
   - The bases are `ControlledSource` (E, F, G, H) and `Switch` (S, W), public for `isinstance`, as `Transistor` is.
   - The names follow the manual's VCVS, VCCS, CCCS and CCVS, written as words, as `Mosfet` is.
   - *Alternative:* long names such as `VoltageControlledVoltageSource`.
2. **Control nodes are nodes.**
   - E, G and S have four `nodes`, the output pair then the control pair, with a `control_nodes` property for the last two.
   - So the signature, `nets()`, `elements_on_net` and `connections` all include them with no new code, as plan section 3, point 2 asks.
   - *Alternative:* a separate `control_nodes` field, which every topology query would then have to read.
3. **Controlling sources are element references.**
   - F, H and W have two `nodes` and `control: ElementReference`, as K's inductors are references.
   - The signature gains a `("control", scope, designator, name)` entry for each, as K has `("coupling", …)`. No existing entry changes, so the signature snapshot does not change.
4. **A controlling source resolves in its own scope only.**
   - Both solvers look only in the element's own definition: a source at the top level is not found from inside a subcircuit (ngspice: "unknown controlling source v.x1.vs"; LTspice: "No such instance"). The name is case-insensitive, and the source may be defined later in the file.
   - Not found: `UNRESOLVED_ELEMENT`, a warning, or info where the scope has an `.include`, `.lib` or opaque block, as for K.
   - LTspice's `X1:Vq` reaches into an instance, and LTspice runs it. The library keeps it as text and reports `UNRESOLVED_ELEMENT` as info naming the form. This is a known limit (§7.8), recorded beside `names.md` N11.
5. **A controlling source that is not a V gets a new warning, `CONTROL_SOURCE_MISMATCH`.**
   - The manual and the reference name a voltage source. The probes show:
     - both solvers also accept an E or an H, which have a branch current;
     - LTspice also accepts an L;
     - both stop on R, I and F.
   - The message says what each solver does.
   - *Alternative:* accept E and H silently, because both solvers run them. That widens the references (decision 0002).
6. **The gain is one positional value: a number or a formula.**
   - **Refused:**
     - a missing gain (both stop; ngspice 47 crashes on it);
     - a second value (`E1 a b c d 2 3`: ngspice runs it and the output matches neither value, while LTspice stops);
     - a word in the gain's place, such as the `E` that LTspice exports when a symbol's gain is never set (both stop);
     - `gain=2`: both solvers run it, but neither reference writes it. Manual chapter 27 lists `gain` among the device parameters read with `@e1[gain]`, not as an instance-line form (decision 0002).
   - *Alternative for `gain=`:* accept it as a value keyword, as `r=1k` is on R, recorded in `value_keyword`.
7. **Instance parameters.**
   - ngspice takes `m=` on F and G (manual §4.2.1, §4.2.3), and nothing on E and H.
   - LTspice takes none on E, F, G or H: `m=` stops it on all four.
   - S and W take none on either dialect: `m=` stops both.
   - *Alternative:* open names on ngspice, as R, C, L and D have. But ngspice stops on `m=` for E and H, and the manual lists `m` only for F and G.
8. **Switch state and model.**
   - The model is mandatory, and the state is optional: `on` or `off`, in any case, kept as a `Flag`.
   - Both together (`on off`) are refused, although both solvers run them and the last one wins: the line contradicts itself.
   - LTspice's `off=1` is accepted, as flags may take a value there (Element Overview, as for D).
   - The model is a fixed field, so a model named `off` is a model, as both solvers read it.
   - S takes an SW model and W a CSW model, on both dialects: `model-types.json`, and `MODEL_TYPE_MISMATCH`.
9. **The nonlinear forms stay `UnsupportedConstruct` until M15.**
   - The grammar recognises each keyword where it stands (`value=`, `VALUE`, `TABLE`, `table=`, `POLY(`, `vol=`, `cur=`, and on LTspice `Laplace=`) and raises `UnsupportedConstruct` there, as it does for C `Q=`.
   - ngspice stops on `Laplace=` ("unknown parameter"), so on ngspice it is a `ParseError`.
   - The device matrices show E, F, G and H as `supported`, and `NG-UNS-001` and `LT-UNS-001` list the forms that remain.
10. **Edits.**
    - `set_value` and `set_formula` on the gain of E, F, G and H. `set_param` takes `m=` on an ngspice F or G.
    - `set_model` on S and W, with the type check and `allow_external`.
    - A new `set_switch_state(designator, state)`, where `state` is `"on"`, `"off"` or `None`. It replaces the keyword, adds it after the model, or removes it.
    - Nodes and controlling sources have no operation (§7.3).
    - *Alternative:* no state edit in M14. A caller could then change a switch's initial state only by hand.
11. **Corpus.**
    - The accept files, including those written for M14 (section 3.3), stay in `controlled_sources` on each dialect, with manifests crediting xdylanm under MIT.
    - The `reject_*` files move to each dialect's `elements_rejects`, with the line, column and error.
    - The `diag_*` files load with a diagnostic and stop the solver, so their manifests mark them `solver.skip` with the reason.
12. **`lt_test_esource.asc` never sets E1's gain.**
    - LTspice exports `E1 OUT N002 VX 0 E` and stops with "Unknown parameter".
    - The maintainer set the symbol's value to 2.2, as in `test_esource.cir`, and the export is redone (2026-11-06). The earlier export is kept as an LTspice reject fixture, `elements_rejects/unset_gain.net`, for decision 6's word in the gain's place.
13. **One decision record, 0015.**
    - It records this section.
    - It amends §5.2 and §5.3 (the new nodes), §7.7 (the `control` entry), §7.8 (references into an instance), and decision 0006 (the new diagnostic).
14. **Element rules and operations go in new family modules,** `model/_rules_controlled.py` and `edit/_ops_controlled.py` (P12). The import contract is per layer, so it needed no change (reworded at T12, as 6.3 notes).

## 3. Starting point (2026-11-06, `8d23e14`, branch `m14-controlled-sources`)

### 3.1 Probes

Probes on ngspice 47 and LTspice 26.1.1, run from a scratch script. Each circuit is a 2 V divider with `.op`, a 0 V sense source `Vs`, and a 1k load on `out`.

| Line | ngspice 47 | LTspice 26.1.1 |
|---|---|---|
| `E1 out 0 vx 0 2`, `{k}`, `'2*1'` | Runs | Runs |
| `E1 out 0 vx 0 gain=2` | Runs, gain 2 | Runs, gain 2 |
| `E1 out 0 vx 0` | Stops: "not enough parameters"; exit code 0xC0000005 in the corpus run | Stops: "Missing gain value" |
| `E1 out 0 vx 0 2 3` | Runs, with an output that matches neither gain | Stops |
| `E1 out 0 vx 0 E` (LTspice's unset export) | Stops | Stops |
| `E1 out 0 vx 0 2 m=2`, `H1 … m=2` | Stops | Stops |
| `G1 … 2m m=2`, `F1 … 2 m=2` | Runs, output doubled | Stops |
| `E1 out 0 vx 2` (3 nodes) | Stops | Stops |
| `E1 out,0 vx 0 2` | Runs | Runs |
| `F1 0,out Vs 2` | Runs | Stops |
| `value=`, `VALUE`, `POLY(1)`, `table=` (M15) | Run | Run |
| `E1 … Laplace=2` (M15) | Stops: "unknown parameter" | Runs |
| F controlled by a V, in another case (`vs`), or by one defined later | Runs | Runs |
| F controlled by an E or an H | Runs | Runs |
| F controlled by an L | Stops | Runs |
| F controlled by an R, an I or an F, or a missing name | Stops: "unknown controlling source" | Stops: "Not a source" or "No such instance" |
| F, H or W in a subcircuit, controlled by a top-level V | Stops | Stops |
| F in a subcircuit, controlled by a V of its own body | Runs | Runs |
| F controlled by `X1.Vq` / `X1:Vq` | Stops / stops | Stops / runs |
| `S1 … sm off`, `ON`, none | Runs | Runs |
| `S1 … sm on off` / `off on`, inside the hysteresis loop | Runs; the last wins | Runs; the last wins |
| `S1 … sm off=1` | Stops | Runs |
| `S1 … sm m=2` | Stops | Stops |
| No model, or 3 nodes | Stops | Stops |
| S with a CSW model, W with an SW model | Stops: "model type mismatch" | Stops: "Undefined model" |
| `.model off SW`, `S1 … off` | Runs (`off` is the model) | Runs |
| W controlled by an R | Stops | Stops |

### 3.2 The examples as given

- **ngspice:** all six run, with the expected outputs, such as `v(/out)` = 2.0 for E and 2.2 for F and H, and both switches trip between 0.75 and 1.0 V.
- **LTspice:**
  - The six schematics export to `.net`. The header's local path is reduced to the file name, as in M13.
  - Five run, with the same outputs as ngspice.
  - `lt_test_esource` stopped (decision 12). After the maintainer's fix it exports `E1 OUT N002 VX 0 2.2` and runs, with the same output as ngspice.
- The KiCad files write the title as `.title`, a `.control` block, `GND` as a net name, and `.model` lines continued with `+`. All of these already load.

### 3.3 Files written for M14 (uncommitted, credited to xdylanm under MIT)

Each changes one thing from one of your files, named in a comment on its second line. All accept files run as expected:

| Dialect | Accept variants | Intentional failures |
|---|---|---|
| ngspice | `test_esource_formula`, `test_gsource_m`, `test_fsource_m`, `test_hsource_sense_later`, `test_fsource_subckt`, `test_vswitch_on`, `test_vswitch_no_state`, `test_iswitch_off`, and `test_cascade` (all six letters, with F, H and W sensing one source) | `elements_rejects/`: `e_two_values` (ngspice runs it), `e_no_value`, `e_m`, `s_on_off` (ngspice runs it), `s_no_model`. In the family, loading with a diagnostic: `diag_w_ctrl_resistor`, `diag_f_ctrl_missing` |
| LTspice | the six exports; `lt_test_fsource_ctrl_e`, `lt_test_hsource_ctrl_into_instance`, `lt_test_vswitch_on`, `lt_test_vswitch_off_value`, `lt_test_iswitch_off`, `lt_test_gsource_formula` | `elements_rejects/`: `f_m`, `s_on_off` (LTspice runs it), and `unset_gain.net`, the export before the fix (decision 12) |

**In the repository:**
- E, F, G, H, S and W are `planned` in both device matrices, so the loader raises `UnsupportedConstruct` for them.
- K is the model for references (`index.py`, `_element_reference`; `topology.py`, the `coupling` entry).
- Tests that use T as the planned example letter are not affected: T is M16.

## 4. Tasks

[x] **T1 — Decision record 0015.** Status `proposed` until M14 closes. It records section 2, with the amendments of decision 13.

[x] **T2 — Commit the corpus first.** The two families with their manifests, and the rejects in `elements_rejects`. Then the solver sweeps (`test_ngspice_corpus.py`, `test_ltspice_solver_corpus.py`) and the tree snapshot docstring name the new family. Every file fails at its first E, F, G, H, S or W line, and each later task makes some of them pass.

[x] **T3 — E and G on both dialects.** Tests first:
- **Grammar:** four nodes and one gain (decision 6). Negative tests: three nodes, no gain, two values, a word, and `gain=`. On ngspice, G takes `m=` and E does not.
- **Node:** `Vcvs` and `Vccs`, with `control_nodes`.
- **Solver tests:** each probe of section 3.1 for E and G, pinning what each solver does and the library's reading. A test that the gain takes effect.
- **Spec entries:** `NG-VCV-001`, `NG-VCC-001`, `LT-VCV-001` and `LT-VCC-001`, and the shared shape, `NG-CTL-001` and `LT-CTL-001`.

[x] **T4 — F and H on both dialects.** As T3, with `Cccs` and `Ccvs`, and `control: ElementReference`. On ngspice, F takes `m=` and H does not. Spec entries `NG-CCC-001`, `NG-CCV-001`, `LT-CCC-001` and `LT-CCV-001`.

[x] **T5 — S and W on both dialects.** `VoltageSwitch` and `CurrentSwitch`, with the model, the state flag and the refusals of decision 8. A test that the state takes effect inside the hysteresis loop. Spec entries `NG-SWV-001`, `NG-SWC-001`, `LT-SWV-001` and `LT-SWC-001`.

[x] **T6 — The nonlinear forms stay unsupported (decision 9).** Each keyword is a positioned `UnsupportedConstruct` on both dialects, and ngspice's `Laplace=` is a `ParseError`. `NG-UNS-001` and `LT-UNS-001` are updated, and so are the device matrices and `devices.md`.

[x] **T7 — Document layer (decisions 3 to 5, 8).**
- **References:** controlling sources join the index as element references, resolved in their scope, with `UNRESOLVED_ELEMENT` and `CONTROL_SOURCE_MISMATCH`.
- **Topology:** the signature's `control` entry. Tests show that E, G and S control nodes appear in `nets()`, `elements_on_net` and `connections`.
- **Model types:** `model-types.json` gains SW and CSW.
- **LTspice:** the `X1:Vq` info.

[x] **T8 — Edits (decision 10).**
- `set_value`, `set_formula` and `set_param` (`m=`) on the gain letters; `set_model` and `set_switch_state` on the switches.
- Golden diffs for each letter on both dialects, from `test_cascade.cir` and an LTspice counterpart.
- Property tests that no edit changes the signature.
- **The exit's negative test:** a raw `EditPlan` that changes any control node of E, G or S, or the controlling source of F, H or W, raises `TopologyViolation`.

[x] **T9 — Corpus and snapshots.** Every accept file of both families loads, round-trips byte-exact and runs in its solver sweep. The tree snapshot gains the new files, and the signature snapshot does not change.

[x] **T10 — Documentation.**
- `docs/design/elements.md`, `docs/usage/elements.md` and `editing.md`, `edit-layer.md` and `document-layer.md` (the new code).
- `docs/usage/errors.md`, both `discrepancies.md` (decisions 4 to 8), the README, CHANGELOG and the architecture amendments.

[x] **T11 — Final evidence and handover.** Open the pull request. Run the full local check set with `--require-solver ngspice --require-solver ltspice`, record it and the green CI run in section 5, and set the status to `READY FOR REVIEW`.

### After the maintainer's approval

[x] **T12 — Close M14.** Archive this list, accept decision 0015, and update the plan and index.

## 5. Results

**Pull request:** [xdylanm/netlistmod#11](https://github.com/xdylanm/netlistmod/pull/11), branch `m14-controlled-sources`.

**Full local run** at `037dd37` (2026-11-06; Windows, Python 3.14, ngspice 47 and LTspice 26.1.1 with `--require-solver ngspice --require-solver ltspice`):
- ruff, ruff format, mypy (src and the strict test set), the import contract and pre-commit are clean.
- pytest: 6,882 passed, 2 skipped, coverage 98.48%, in 16 min 30 s.
- Every accept file of both `controlled_sources` families loads, round-trips byte-exact and runs in its solver sweep. The two `diag_*` files are skipped there, with the manifest's reason.
- The signature snapshot is unchanged.

**The first full run** at `ae3c1f1` found four things, fixed in `037dd37`:
- `test_ltspice_discrepancies.py` did not list `elements_rejects/s_on_off.cir`, which LTspice runs.
- `test_ltspice_validation.py` still had a linear E as an unsupported form; that case now uses E's `value=`.
- `test_ngspice_solver_document.py` ran the deliberately broken `document_basic/control_source.cir`.
- pre-commit's end-of-file hook added the missing final newline to `docs/grammars/ngspice/discrepancies.md`.

**CI** on #11 at `037dd37` is green on all five jobs.

**Design points worth reviewing:**
1. **Nonlinear keywords.** Each is recognised only where its dialect writes it: after the output nodes, and on LTspice's E and G also after the control nodes. A lookahead on `=`, `(` or `{` keeps a node named `value` or `poly` a node. The constructs are named "nonlinear dependent source form (…)".
2. **`CONTROL_SOURCE_MISMATCH`** cites the one section that applies to the letter: manual §4.2.3 (F), §4.2.4 (H) or §3.3.15 (W), or the LTspice reference. It is the last code in `DiagnosticCode`, so the order of other diagnostics is unchanged.
3. **`document_basic/control_source.cir` is a new fixture,** rather than a line added to `every_diagnostic.cir`, because changing that file would change a digest in the signature snapshot.
4. **LTspice's `E1 out,0 vx 0 2` runs and is refused,** as a comma between nodes is on every LTspice letter (decision 0009); `discrepancies.md` records it.
5. **The `ON_KW` keyword is `on` alone.** It is offered only in the switch-state position, so a node named `on` elsewhere is unaffected.
6. **`set_switch_state(…, None)` on a line with no state** returns no edit, so removing is idempotent, as the property test checks.

## 6. Review round 1 (2026-11-06, `c74c941`)

### 6.1 Outcome

M14 is accepted once the changes below are made. The design holds up on review:
- **Checks:** pytest 6,882 passed, 2 skipped, coverage 98.48%, in 16 min 50 s, with ngspice 47 and LTspice 26.1.1 from `.env` (`--require-solver ngspice --require-solver ltspice`). ruff, ruff format and `mypy src` are clean. CI on #11 is green on all five jobs.
- **Grammar:** each letter spells out its own line on each overlay, and the nonlinear keywords are recognised only where the dialect writes them. The `=`, `(` and `{` lookaheads keep a node named `value`, `table` or `on` a node (`E1 out 0 value 0 2` loads with four nodes).
- **Topology:** control nodes are ordinary `nodes`, so the signature and the net queries needed no new code. The `control` entry is added beside the element's entry, and the signature snapshot is unchanged.
- **Edits:** the goldens cover each letter on both dialects, and the negative test covers every control node and controlling source.
- **Probes by hand** (ngspice and LTspice dialects):
  - `gain=2`, a missing gain, two values, LTspice's unset `E` and `m=` on E and H are refused at the right column; `m=` on an ngspice G and F loads.
  - `F1 … R1 2`, `F1 … E1 2` and `F1 … X1 2` give `CONTROL_SOURCE_MISMATCH`; `X1:Vq` is info only when `X1` is an instance of the scope; an F in a subcircuit does not see a top-level `Vs`, even with an `.include` at the top level.
  - S with a CSW model and W with an SW model give `MODEL_TYPE_MISMATCH`, and `set_model` refuses them.
  - `set_switch_state` replaces, adds and removes the state, keeps a trailing comment, and replaces LTspice's `off=1` whole. A raw edit of a control node, a controlling source or the case of its name (`Vs` → `VS`) is a `TopologyViolation`.

### 6.2 Required changes

[x] **R1 — One clear message for each refused gain form that a solver runs.** Decision 6 refuses them, and today each gets only the generic list of expected tokens:

| Line | Solvers | Message today |
|---|---|---|
| `E1 out 0 vx 0 gain=2` | both run it | "Expected: `'expression'`, `,` field separator, …" (column 15) |
| `E1 out 0 vx 0 2 3` | ngspice runs it | "Expected: `\` continuation …, end of line, …" (column 17) |
| `E1 out 0 vx 0 E` | both stop (LTspice's export of an unset gain) | "Expected: `'expression'`, `{expression}`, …" (column 15) |

- **Change:** `gain=` should say that the gain is written positionally (`E1 … 2`), citing decision 0015 item 6. A second value should say that a dependent source takes one gain. On LTspice, a word in the gain's place should say that the gain is not set, as LTspice writes it for a symbol whose value was never set. Keep the column at the offending token, on all four letters (E, F, G, H).
- **Tests:** assert the wording in `test_malformed_lines_are_rejected` (or a new test beside it) in both `test_controlled_sources.py` files. Show the `gain=` message in `docs/usage/errors.md`.
- The other refusals (`m=` on E or H, three nodes, no gain) keep their messages.

[x] **R2 — Make `CONTROL_SOURCE_MISMATCH` name the V and the outcome for this target.**
- Today: "`F1` is controlled by `E1`, a voltage-controlled voltage source, but the ngspice manual §4.2.3 names a voltage source; ngspice 47 also reads an E or H source here and stops on other elements".
- A VCVS *is* a voltage source in plain words, so the first half reads as a contradiction. The second half lists both outcomes and leaves the reader to work out which applies.
- **Change:** say "an independent voltage source (`V`)", and state the solver's outcome for this target only: for an E or H (and on LTspice an L) that the solver runs it; otherwise that the solver stops on it. Keep the code, the severity and the cited section.
- **Tests:** `test_a_mismatch_says_what_each_solver_does` covers one target that runs and one that stops, on both dialects. Update the example in `docs/usage/errors.md` and the row in `document-layer.md` if the wording there changes.

[x] **R3 — Pin the remaining rows of section 3.1 in the probe tests.**
- "S with a CSW model, W with an SW model" (both solvers stop) has no solver probe, although decision 8 and the `MODEL_TYPE_MISMATCH` behaviour rest on it.
- "F controlled by `X1.Vq`" on ngspice (stops) has no probe; LTspice's `X1:Vq` does (`f-into-instance`).
- **Change:** add `s-csw-model` and `w-sw-model` to both `test_*_controlled_probes.py` files, with the library's reading (loads, with `MODEL_TYPE_MISMATCH`), and `f-into-instance-dot` to the ngspice file (loads, with `UNRESOLVED_ELEMENT` as a warning). If the reading helper cannot show the diagnostic, assert it in the test.

[x] **R4 — Bring the public edit docstrings up to date.**
- In `edit/api.py`, `set_value` names only R, C, L, V and I; `set_param` names R, C, L and D and the LTspice V and I; `set_model` names R, C, L and D, and its type list stops at D. The `set_param` and `set_model` docstrings were already behind since M13 (Q, M, J, Z).
- In `edit/_ops_elements.py`, the `set_value`, `set_param` and `set_model` docstrings do not name the M14 letters.
- **Change:** make each docstring name the letters that `docs/design/edit-layer.md` lists for the operation (the gain of E, F, G and H; `m=` on an ngspice F or G; S → `SW`, W → `CSW`). No code change.

[x] **R5 — Cover `set_param` in the signature property test.**
- `_EDITS` in `tests/edits/test_controlled_edits.py` samples every operation of decision 10 except `set_param` with `m=`.
- **Change:** add `set_param("G1", "m", …)` and `set_param("F1", "m", …)`, sampled on ngspice only (LTspice refuses them, as `test_ltspice_takes_no_m_on_f_or_g` shows).

### 6.3 Noted, no change required

- In `document/index.py` `_collect`, the new `if isinstance(item, Cccs | Ccvs | CurrentSwitch)` splits the old `if`/`elif` chain in two. It is correct: a W needs both its model and its control reference, and K, `.dc`, `.save`, `.ic`, `.step` and `.model … ako` still reach their branches. A one-line comment saying the split is deliberate would help the next reader.
- In `model/__init__.py`, the eight new names sit after `"Transistor"` in `__all__`, out of order. Cosmetic, as for M13.
- Section 2 decision 14 says "with the import contract updated". The contract is per layer, so no change was needed; T12 can reword it when 0015 is accepted.
- A change in the case of a controlling source (`Vs` → `VS`) is a `TopologyViolation`. This follows §7.7's exact-text rule, as for nodes.

### 6.4 Exit for this round

Make R1 to R5. Run the full check set with `--require-solver ngspice --require-solver ltspice`, read CI once after the push, and append a short report as 6.5. Then set the status to `READY FOR REVIEW`. **Do not archive** (T12 follows approval).

### 6.5 Report (2026-11-06, `ce9573e`)

R1 to R5 are made in one commit, `ce9573e`.

- **R1:** both overlays now recognise the three forms after the gain's place on E, F, G and H, only to refuse them (`gain_keyword`, `second_value`, and on LTspice `unset_gain`, under `NG-CTL-001` and `LT-CTL-001`). Each gets its own message at the offending token:
  - `gain=`: "`gain=` is not a form of the ngspice manual §4.2" (or "of the LTspice reference"), "write the gain positionally, as the value after the nodes (`E1 out 0 in 0 2`) or after the controlling source (`F1 out 0 Vs 2`)". Column 15 for `E1 out 0 vx 0 gain=2`, as in the table.
  - A second value: "`3` is a second value: a dependent source takes one gain". Column 17.
  - On LTspice, a word: "`E` is not a gain: the gain is not set. LTspice writes the symbol's name in the gain's place when a symbol's value was never set; set it to a number or a `{...}` expression". Column 15.
  - The message cites the manual section rather than decision 0015 item 6: the contract test refuses internal citations in messages (`decision \d`, M11 H7). The comments in the grammar cite the decision.
  - `m=` on E or H, three nodes and a missing gain keep their messages, and so does ngspice's word in the gain's place.
  - Tests: `test_refused_gain_forms_name_the_form` beside `test_malformed_lines_are_rejected` in both files, covering all four letters. `docs/usage/errors.md` shows the `gain=` message.
  - The strict grammars build. The tree snapshot changes for two reject files only, with the same positions and error classes: `e_two_values.cir` has its own reason now, and `e_m.cir` lists the value terminals of a second gain among its expected tokens.
- **R2:** the message now reads, for example: "`F1` is controlled by `R1`, a resistor, but the ngspice manual §4.2.3 names an independent voltage source (`V`); ngspice 47 stops on it". For an E or H, and on LTspice an L, the ending is "… runs it, with the current through `E1`". The code, severity and cited section are unchanged.
  - `test_a_mismatch_says_what_the_solver_does_with_this_source` replaces the old test. It covers R and I (stop), E and H (run), and L (runs on LTspice only), on both dialects.
  - The `document-layer.md` row and the `errors.md` description say the same. The `errors.md` example prints only the code, so it is unchanged.
- **R3:** `s-csw-model` and `w-sw-model` are in both probe files, and `f-into-instance-dot` is in the ngspice file; ngspice and LTspice stop on each. A `_DIAGNOSED` table asserts the library's diagnostic for these and three earlier rows:
  - `MODEL_TYPE_MISMATCH` at the model;
  - `UNRESOLVED_ELEMENT` as a warning for `X1.Vq` on ngspice, and as info for `X1:Vq` on LTspice;
  - `CONTROL_SOURCE_MISMATCH` for `f-ctrl-r` (ngspice) and `f-ctrl-l` (LTspice);
  - `UNRESOLVED_ELEMENT` for `f-ctrl-missing`.
- **R4:** the `set_value`, `set_param` and `set_model` docstrings in `edit/api.py` and `edit/_ops_elements.py` name every letter `edit-layer.md` lists:
  - the gain of E, F, G and H;
  - `m=` on an ngspice F or G, and the positional `area`;
  - the full type list, with S → `SW` and W → `CSW`.

  There is no code change.
- **R5:** the signature property test draws from the shared edits plus, on ngspice only, `set_param("G1", "m", "2")` and `set_param("F1", "m", "3")`.
- **6.3:** `_collect` in `index.py` gains the one-line comment that the second chain is deliberate.

**Checks** at `ce9573e` (Windows, Python 3.14, ngspice 47 and LTspice 26.1.1 with `--require-solver ngspice --require-solver ltspice`):
- ruff, ruff format, mypy (src and the strict test set), the import contract and pre-commit are clean.
- pytest: 6,911 passed, 2 skipped, coverage 98.49%, in 16 min 24 s.
- The signature snapshot is unchanged.

**CI** on #11 at `ce9573e` is green on all five jobs.

Nothing is archived: T12 follows approval.

## 7. Review round 2 (2026-11-06, `39e9d6f`) — no further changes required

### 7.1 Outcome

R1 to R5 are made as 6.5 reports. Nothing else is required, and M14 is ready for the maintainer's approval (T12).
- **Checks:**
  - pytest with ngspice 47 and LTspice 26.1.1 from `.env` (`--require-solver ngspice --require-solver ltspice`): 6,910 passed, 2 skipped, 1 failed, coverage 98.49%, in 27 min 28 s. The failure is `test_every_corpus_family_has_a_manifest_and_matching_hashes`, because `ltspice/controlled_sources/lt_test_esource.net` was deleted from the working tree during the run, at about 12:46. No test writes to the corpus, since the solver tests copy fixtures into `tmp_path`. On a clean checkout of `39e9d6f` the manifest tests pass (3 passed), so this is not a code failure. The 6,910 passing tests include every M14 test.
  - ruff, ruff format and `mypy src` are clean.
  - CI on #11 is green on all five jobs.
- **R1:**
  - Each refused gain form gets its own message at the offending token, on all four letters and both dialects: `gain=` (column 15 on `E1 out 0 vx 0 gain=2`), a second value (column 17 on `E1 out 0 vx 0 2 3`), and LTspice's unset `E` (column 15).
  - The added alternatives exist only to reach the refusals, and the grammar comments say so. The strict grammars build.
  - `m=` on E or H, three nodes and a missing gain keep their messages.
  - By hand on LTspice 26.1.1, a bare parameter name in the gain's place (`E1 … k` with `.param k=2`) also stops ("Unknown parameter"), and `{k}` runs. So refusing a word there is right, and the message's advice (a number or a `{...}` expression) fits that case too.
- **R2:** the message names "an independent voltage source (`V`)" and gives the outcome for the target only. `_CONTROL_RUNS` matches section 3.1: E and H on both dialects, and L on LTspice. The new test covers R, I, E, H and L on both dialects.
- **R3:** `s-csw-model`, `w-sw-model` and ngspice's `f-into-instance-dot` are probed, and both solvers stop on each. `_DIAGNOSED` asserts the library's diagnostic for each of them and for three earlier rows.
- **R4:** the `set_value`, `set_param` and `set_model` docstrings in `api.py` and `_ops_elements.py` agree with `edit-layer.md`, including the Q, M, J and Z entries that were missing since M13.
- **R5:** the property test samples `set_param` with `m=` on an ngspice G and F.
- **6.3:** `_collect` has the comment.

### 7.2 The two points the report raises

1. **The `gain=` message cites the manual, not decision 0015.**
   - **Accepted.** R1 was wrong to ask for the citation: `test_no_message_cites_an_internal_document` in `tests/architecture/test_contracts.py` has refused internal citations in messages since M11 T7, because a wheel ships without the decision records.
   - Citing manual §4.2 (or the LTspice reference) in the message, and the decision in the grammar comments and `errors.md`, follows that rule and matches what `CONTROL_SOURCE_MISMATCH` and M13's area message already do.
2. **The tree snapshot changes for two reject files.**
   - **Accepted.** The positions and error classes are unchanged, and the snapshot docstring records both entries.
   - `e_two_values.cir` now has its own reason, which is the point of R1.
   - `e_m.cir` (`E1 /OUT a /VX GND 2.2 m=2`) now lists a number and the formula forms among its expected tokens. These are what the parser can shift there now, because of the `second_value` alternative. Read literally, they suggest writing a second gain, which would itself be refused. That is a small cost: the column is still at `m`, both solvers stop on the line, and no message names `m=` on E or H today. If the list ever misleads users, the fix is to give `m=` on E and H a message of its own ("ngspice takes `m=` on F and G only"), as R1 did for `gain=`. That is not needed for M14.

### 7.3 Noted, no change required

- The LTspice unset-gain message says that "the gain is not set" for any word in the gain's place, including a parameter name such as `k`. LTspice stops on both, and the advice to write `{k}` applies to both, so the wording is acceptable. A later change could add "if it names a parameter, write `{k}`".
