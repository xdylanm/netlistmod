# M13 task list — Transistors (Q, M, J, Z)

> **Status:** ACTIVE — approved by the maintainer's decisions in section 2 (2026-11-05)
> **Part of:** [phase-2-plan.md](./phase-2-plan.md) (milestone M13). Governed by [architecture.md](../architecture.md) (§2, §5.3, §6.3, §7.2, §7.7, §7.8, §10).

## 1. Scope

M13 adds the four transistor letters on both dialects, so that real transistor circuits load, query and edit. It ends with the maintainer's hands-on checkpoint (plan M13).

- **In:**
  - **Q** (BJT), **M** (MOSFET, including VDMOS), **J** (JFET) and **Z** (MESFET; IGBT on LTspice). Each has typed nodes, model, positional area, flags and instance parameters, with spec entries, solver tests and golden diffs.
  - The rule for where the nodes end and the model starts (plan section 3, point 1), decided before any grammar.
  - The model types each letter accepts, including those only one dialect has.
  - Two `.model` forms that real files use and the library refuses today: a bare `pchan` or `nchan` flag, and a dotted value like `version=3.3.0`.
  - `set_model`, `set_param` and `set_model_param` on the new elements, with `MODEL_TYPE_MISMATCH`.
  - The `kicad_transistors` and `ltspice_transistors` corpus families, and the `OPENJELLYBEAN_LIB` support, prepared on this branch.
- **Not in M13:**
  - Dependent sources and switches (M14), behavioural sources (M15), and the remaining letters.
  - Reading a model's parameters, or checking them against the model's level.
  - Reading `jellybean.lib`, or any other included file (§7.8).

**Exit:** each letter's spec entries are validated on both solvers, property tests cover the new elements, the signature snapshot is unchanged, and every file of both new corpus families loads, round-trips and runs on its solver.

## 2. Decisions (maintainer, 2026-11-05)

The maintainer accepted each recommendation, based on the probes in section 3. "Alternative" marks an option considered and not chosen.

1. **The boundary rule: the model is the last name before the first area value, flag, parameter or the end of the line.** The node count must be in the letter's range (decision 2).
   - **Why:** both solvers decide by looking up which names are defined models. Probes show this: ngspice says "can't find model 'off'", and LTspice reads `.model 2 NPN` as a model. The library cannot do that, because a model may come from an `.include` it never reads, and syntax belongs in the grammar (P13).
   - **The probes agree with the rule where it matters.** For `Q1 c b e qm s`, ngspice also takes `s` as the model and reports it missing, and LTspice stops.
   - **The grammar can do it.** It is right-recursive like the X line, so a name is classified once the parser sees what follows it.
   - *Alternative:* resolve the model through the symbol table. That puts syntax in Python, and it fails for included models.
2. **Node counts by letter and dialect, without looking at the model's type.**

   | Letter | ngspice | LTspice |
   |---|---|---|
   | Q | 3 to 5 (substrate, then VBIC's junction temperature node) | 3 or 4 |
   | M | 3 to 5 (VDMOS 3, MOSFET 4, VDMOS with `thermal` 5) | 3 or 4 |
   | J | 3 | 3 |
   | Z | 3 | 3 |

   A count can be right for one model and wrong for another, such as a 3-node MOSFET with an NMOS model or a 5-node Q without VBIC. Those parse, and the solver stops, as it does for argument counts in M12. *Alternative:* tie counts to the model type, which needs the symbol table again.
3. **Topology is the nodes written.**
   - A 3-node Q connects its substrate to ground in ngspice ("When unspecified, ground is used"), but the signature records only the written nodes.
   - LTspice's export of a 3-pin VDMOS symbol writes the source twice (`MQ8 d g OUT OUT 2N7000_OJ`). That is two connections to one net, as written.
   - The implicit substrate goes in §7.8 as a known limit.
   - *Alternative:* add an implicit ground node, which would put a connection in the signature that the text does not show.
4. **Name forms that one solver allows and the manual does not.**
   - **Refused:** a model name that is a plain number, such as `.model 2 NPN`, which LTspice runs and ngspice cannot find. A number in that position is read as an area.
   - **Accepted as a node:** a node named `off` before the model, such as `Q1 c b e off qm`. LTspice reads it that way, and ngspice takes it as the model; `discrepancies.md` records the difference.
5. **Area: positional where the references write it, named where they write that.**
   - **Positional on both dialects:** J and Z.
   - **Positional on LTspice:** Q.
   - **Named on ngspice:** Q's `area=`, `areab=` and `areac=`.
   - **Refused, following the manual (decision 0002):** a positional area on an ngspice Q, which ngspice runs although its manual shows only `area=`.
   - *Alternative:* accept both forms on both dialects, which widens the manual (decision 0002).
6. **Instance parameters.**
   - **ngspice:** open names, as R, C, L and D have now. Two keyword flags: `off`, and VDMOS's `thermal`.
   - **LTspice:** closed lists per letter, each the reference's, as decision 0009 item 7 did for phase 1. That is: Q `temp`; monolithic M `m L W AD AS PD PS NRD NRS IC temp`; VDMOS `L W M m IC temp`; J `temp`; Z `m temp`; and `off` on all.
   - Forms LTspice runs beyond those lists, such as `area=` on Q and `IC=` or `m=` on J, are refused and recorded.
   - **Both dialects:** `ic=` takes a comma list, with or without a blank after the comma (`IC=0.6, 5.0` is the manual's own example).
7. **`.model` forms.**
   - `pchan` and `nchan` are accepted as bare flags in any `.model` parameter list. The manual writes `.model m VDMOS <Pchan> <parameters>`, and LTspice reads the same.
   - A dotted value such as `version=3.3.0` is kept as text, never as a number, because it is not one.
   - Both are needed for `jellybean.lib`'s `BS250_OJ` and for real BSIM files.
   - `set_model_param` edits these as values; adding or removing `pchan` is not offered.
8. **Model types per dialect.**
   - **Both:** Q takes NPN and PNP; M takes NMOS, PMOS and VDMOS (ngspice 47 has VDMOS); J takes NJF and PJF; Z takes NMF and PMF.
   - **LTspice only:** Z also takes NIGBT and PIGBT. ngspice reports "Unknown model type nigbt".
   - `model-types.json` gains a dialect split for this.
9. **Split `transform.py` and `operations.py` by element family first, with no change in behaviour.** They are 1,535 and 940 lines, and the plan's risk table names the start of M13 for this (P12).
10. **One decision record, 0014,** which also records the corpus manifests' `external` field as an addition to decision 0008.

## 3. Starting point (2026-11-05, `a23bd03`, branch `m13-transistors`)

Probes on ngspice 47 and LTspice 26.1.1, run from a scratch script. Each circuit is a small bias network with `.op`.

| Line | ngspice 47 | LTspice 26.1.1 |
|---|---|---|
| `Q1 c b e qm` | Runs | Runs |
| `Q1 c b e s qm` | Runs | Runs |
| `Q1 c b e s tj qm`, VBIC (`level=4`) | Runs | Stops: "Undefined model tj" |
| `Q1 c b e s tj qm`, Gummel-Poon | Stops | Stops |
| 6 nodes | Stops | Stops |
| `Q1 c b e 2 qm` (a node named 2) | Runs | Runs |
| `Q1 c b e qm 2`, `Q1 c b e s qm 2` (positional area) | Runs | Runs |
| `Q1 c b e qm off`, `Q1 c b e qm 2 off` | Runs | Runs |
| `Q1 c b e off qm` (a node named off) | Stops: "can't find model 'off'" | Runs |
| `.model 2N3904 NPN`, `Q1 c b e 2N3904`, also with area 2 | Runs | Runs |
| `.model 2 NPN`, `Q1 c b e 2` | Stops: "can't find model 'e'" | Runs |
| `Q1 c b e qm s` | Stops: "can't find model 's'" | Stops |
| `M1 d g s b nm`, NMOS | Runs | Runs |
| `M1 d g s nm`, NMOS | Stops | Stops |
| `M1 d g s vd`, `M1 d g s s vd`, VDMOS | Runs | Runs |
| `M1 d g s tj tc vd thermal`, VDMOS | Runs | Stops: "Too many nodes" |
| 5 nodes, NMOS | Stops | Stops |
| `.model vd VDMOS pchan VTO=-2 …` | Runs | Runs |
| `J1 d g s jm`; 4 nodes | Runs; stops | Runs; stops |
| `Z1 d g s zm 2 off`, NMF | Runs | Runs |
| `.model zi NIGBT`, `Z1 c g e zi` | Stops: "Unknown model type nigbt" | Runs |

From the M12 handover probes (2026-11-04): `ic=` and `IC=1, -1` run on Q, M and J on both. `area=`, `m=` and `temp=` run on J on both. `temp=` stops both on a `level=8` MOSFET, although the manual's general form lists it. M's `L W AD AS PD PS NRD NRS m off ic` run on both.

**From the corpus** (section 1's families, 29 ngspice and 28 LTspice files):
- LTspice's export writes a fourth node on every Q (substrate `0`) and every 3-pin VDMOS symbol (the source again).
- `10u` on a capacitor came out as `10µ`.
- The library refuses `version=3.3.0` and bare `pchan` today.
- All 51 netlists (29 ngspice, 22 LTspice) run on their solvers, the 15 and 14 that include `jellybean.lib` with `OPENJELLYBEAN_LIB` set.
- Every one stops the library at its first transistor line. On the branch, 146 solver-free and 102 solver tests fail for that reason; they are the tests M13 makes pass.

**In the repository:** `model-types.json` lists R, C, L and D. Q, M, J and Z are `planned` in both device matrices with milestone M13. The loader raises `UnsupportedConstruct` for a planned letter.

## 4. Tasks

[ ] **T1 — Decision record 0014.** Status `proposed` until M13 closes. It records section 2, and amends §5.3 (the new nodes), §6.3 (the boundary rule), §7.8 (the implicit substrate), decision 0002 for decision 4, and decision 0008 for the `external` field.

[x] **T2 — Commit the corpus first.** The two families, their manifests, `OPENJELLYBEAN_LIB` in `.env.example` and the solver sweeps' `external` support, as already prepared on this branch, with the failures listed in section 3. Each later task makes some of them pass.

[x] **T3 — Split by element family (decision 9).** Move the element rules of `transform.py` and the element operations of `operations.py` into modules by family. Every test passes before and after, the tree and signature snapshots are unchanged, and the import contract is updated.

[ ] **T4 — Q on both dialects.** Tests first:
- Grammar: decisions 1, 2, 4 and 5, in a right-recursive rule shared with the other letters where it can be. Negative tests: too many nodes, a number as the model, a positional area on ngspice, a name after the area.
- Node: `BipolarTransistor` with `nodes`, `model`, `area` (positional, LTspice), `flags` and `params`. `ic=` is a `ValueList`.
- Each probe of section 3 has a solver test that pins what each solver does, and the library's reading of it.
- Spec entries `NG-BJT-001` and `LT-BJT-001`, and the device matrices show Q as `supported`.

[ ] **T5 — M on both dialects.** As T4, with `Mosfet`: 3 to 5 nodes on ngspice and 3 or 4 on LTspice, the `thermal` flag on ngspice, and the closed LTspice lists for monolithic and VDMOS forms. A test that `temp=` on a `level=8` model loads, as the grammar cannot know the level, and stops both solvers.

[ ] **T6 — J and Z on both dialects.** `Jfet` and `Mesfet`, with exactly 3 nodes and a positional area. On LTspice, Z also covers an IGBT. Spec entries for each.

[ ] **T7 — `.model` forms (decision 7).** `pchan` and `nchan` as bare flags, and dotted values kept as text, on both dialects. Tests first. `cmos_xor_version.cir`, `cmos_xor_model_params.cir` and both `local_models` files must load. `NG-MDL-*` and `LT-MDL-*` are updated.

[ ] **T8 — Model types and diagnostics (decision 8).**
- `model-types.json` gains the letters and a dialect split, so that `MODEL_TYPE_MISMATCH` reports a PNP model on an NMOS line, and NIGBT only on ngspice.
- `UNRESOLVED_MODEL` works as for D, including info when the model may come from an `.include`, as in the 29 corpus files that include `jellybean.lib`.

[ ] **T9 — Edits.**
- `set_model` on each letter, with its type check and `allow_external=True`.
- `set_param` on instance parameters, flags and `ic=`, and on `area`: the positional slot where the dialect writes it, otherwise `area=`, as LTspice's diode does now.
- `set_model_param` on NPN, PNP, NMOS, PMOS, VDMOS, NJF, PJF and NMF models.
- Golden diffs for each letter on both dialects, from the corpus families. Property tests that no edit changes the signature, including on 4- and 5-node lines.
- Each family's edits are tested in a batch too.

[ ] **T10 — Corpus and snapshots.**
- Every file of both families loads, round-trips byte-exact, and runs in its solver sweep.
- The tree snapshot gains the new files, and the signature snapshot does not change.
- `kicad_basic`'s manifest note still describes its own three files.

[ ] **T11 — Documentation.**
- `elements.md` and `docs/usage/elements.md` describe the new nodes, `edit-layer.md` the new edits, and `docs/usage/errors.md` any new messages.
- Both `discrepancies.md` files take the rows of decisions 4 to 6.
- The device matrices, README and CHANGELOG are updated, and the usage guide has a short transistor example.

[ ] **T12 — Final evidence and handover.** Open the pull request. Run the full local check set with `--require-solver ngspice --require-solver ltspice` and `OPENJELLYBEAN_LIB` set, record it and the green CI run in section 5, and set the status to `READY FOR REVIEW`.

### After the maintainer's approval

[ ] **T13 — Close M13.** Merge on green, archive this list, accept decision 0014, and update the plan and index.

[ ] **T14 — Maintainer checkpoint (plan M13).** Hands-on use with real transistor netlists, and a decision on whether the order of M14 to M19 should change.

## 5. Results

To be filled in by T12.
