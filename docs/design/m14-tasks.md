# M14 task list — Linear dependent sources and switches (E, F, G, H, S, W)

> **Status:** READY FOR REVIEW — the maintainer accepted the decisions in section 2 (2026-11-06); T1 to T11 done, results in section 5
> **Part of:** [phase-2-plan.md](./phase-2-plan.md) (milestone M14). Governed by [architecture.md](../architecture.md) (§2, §5.3, §7.1, §7.2, §7.3, §7.7, §10).

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
14. **Element rules and operations go in new family modules,** `model/_rules_controlled.py` and `edit/_ops_controlled.py` (P12), with the import contract updated.

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

[ ] **T12 — Close M14.** Archive this list, accept decision 0015, and update the plan and index.

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
