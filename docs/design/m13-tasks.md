# M13 task list — Transistors (Q, M, J, Z)

> **Status:** READY FOR REVIEW — review round 1 changes R1 to R8 are made (report in 6.4). T1 to T12 done (results in section 5); section 2 records the maintainer's decisions (2026-11-05).
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
   - **Where `ic=` is accepted:** on every ngspice transistor, and on LTspice's M only, since the closed lists for Q, J and Z leave it out. It takes a comma list, with or without a blank after the comma (`IC=0.6, 5.0` is the manual's own example; review R6).
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

[x] **T1 — Decision record 0014.** Status `proposed` until M13 closes. It records section 2, and amends §5.3 (the new nodes), §6.3 (the boundary rule), §7.8 (the implicit substrate), decision 0002 for decision 4, and decision 0008 for the `external` field.

[x] **T2 — Commit the corpus first.** The two families, their manifests, `OPENJELLYBEAN_LIB` in `.env.example` and the solver sweeps' `external` support, as already prepared on this branch, with the failures listed in section 3. Each later task makes some of them pass.

[x] **T3 — Split by element family (decision 9).** Move the element rules of `transform.py` and the element operations of `operations.py` into modules by family. Every test passes before and after, the tree and signature snapshots are unchanged, and the import contract is updated.

[x] **T4 — Q on both dialects.** Tests first:
- Grammar: decisions 1, 2, 4 and 5, in a right-recursive rule shared with the other letters where it can be. Negative tests: too many nodes, a number as the model, a positional area on ngspice, a name after the area.
- Node: `BipolarTransistor` with `nodes`, `model`, `area` (positional, LTspice), `flags` and `params`. `ic=` is a `ValueList`.
- Each probe of section 3 has a solver test that pins what each solver does, and the library's reading of it.
- Spec entries `NG-BJT-001` and `LT-BJT-001`, and the device matrices show Q as `supported`.

[x] **T5 — M on both dialects.** As T4, with `Mosfet`: 3 to 5 nodes on ngspice and 3 or 4 on LTspice, the `thermal` flag on ngspice, and the closed LTspice lists for monolithic and VDMOS forms. A test that `temp=` on a `level=8` model loads, as the grammar cannot know the level, and stops both solvers.

[x] **T6 — J and Z on both dialects.** `Jfet` and `Mesfet`, with exactly 3 nodes and a positional area. On LTspice, Z also covers an IGBT. Spec entries for each.

[x] **T7 — `.model` forms (decision 7).** `pchan` and `nchan` as bare flags, and dotted values kept as text, on both dialects. Tests first. `cmos_xor_version.cir`, `cmos_xor_model_params.cir` and both `local_models` files must load. `NG-MDL-*` and `LT-MDL-*` are updated.

[x] **T8 — Model types and diagnostics (decision 8).**
- `model-types.json` gains the letters and a dialect split, so that `MODEL_TYPE_MISMATCH` reports a PNP model on an NMOS line, and NIGBT only on ngspice.
- `UNRESOLVED_MODEL` works as for D, including info when the model may come from an `.include`, as in the 29 corpus files that include `jellybean.lib`.

[x] **T9 — Edits.**
- `set_model` on each letter, with its type check and `allow_external=True`.
- `set_param` on instance parameters, flags and `ic=`, and on `area`: the positional slot where the dialect writes it, otherwise `area=`, as LTspice's diode does now.
- `set_model_param` on NPN, PNP, NMOS, PMOS, VDMOS, NJF, PJF and NMF models.
- Golden diffs for each letter on both dialects, from the corpus families. Property tests that no edit changes the signature, including on 4- and 5-node lines.
- Each family's edits are tested in a batch too.

[x] **T10 — Corpus and snapshots.**
- Every file of both families loads, round-trips byte-exact, and runs in its solver sweep.
- The tree snapshot gains the new files, and the signature snapshot does not change.
- `kicad_basic`'s manifest note still describes its own three files.

[x] **T11 — Documentation.**
- `elements.md` and `docs/usage/elements.md` describe the new nodes, `edit-layer.md` the new edits, and `docs/usage/errors.md` any new messages.
- Both `discrepancies.md` files take the rows of decisions 4 to 6.
- The device matrices, README and CHANGELOG are updated, and the usage guide has a short transistor example.

[x] **T12 — Final evidence and handover.** Open the pull request. Run the full local check set with `--require-solver ngspice --require-solver ltspice` and `OPENJELLYBEAN_LIB` set, record it and the green CI run in section 5, and set the status to `READY FOR REVIEW`.

### After the maintainer's approval

[ ] **T13 — Close M13.** Merge on green, archive this list, accept decision 0014, and update the plan and index.

[ ] **T14 — Maintainer checkpoint (plan M13).** Hands-on use with real transistor netlists, and a decision on whether the order of M14 to M19 should change.

## 5. Results

**Pull request:** [xdylanm/netlistmod#10](https://github.com/xdylanm/netlistmod/pull/10), branch `m13-transistors`.

**Full local run** (2026-11-05, at `367b92c`, Windows, Python 3.14, ngspice 47 and LTspice 26.1.1 with `--require-solver ngspice --require-solver ltspice`, `OPENJELLYBEAN_LIB` set):

- ruff, ruff format, mypy (src and the strict test set), the import contract and pre-commit: all clean.
- pytest: 6,296 passed, 2 skipped, 1 failed, coverage 98.63%, in 15 min 18 s. The failure was a stale case in `test_ltspice_validation.py::test_other_forms_run_and_are_unsupported` that still expected a Q line to be unsupported. It is removed (Q is covered by `test_ltspice_transistor_probes.py`), and the test passes on LTspice 26.1.1.
- Every file of `kicad_transistors` (29) and `ltspice_transistors` (22) loads, round-trips byte-exact and runs in its solver sweep. The signature snapshot is unchanged.

**Design points worth reviewing:**

1. **The model-name refusal is in the transformer, not the grammar.** Where only a name may follow (`Q1 c b e s qm 2`, `Q1 c b e 2 off`), the lexer reads `2` or `off` as a name. A name terminal that excludes numbers was tried and dropped: it outranked the parameter-name terminal, so `temp=30` stopped lexing. The transformer raises a `ParseError` at the token instead (P13).
2. **LTspice embedded decimals rank below `WORD`.** So `Q1 c b e s 2N3904` reads `2N3904` as the model, the common case, and `Q1 c b e qm 1n5` reads `1n5` as the model with `qm` a fourth node. An embedded area is read only where no name may follow (`Q1 c b e s qm 1n5`, `J1 d g s jm 1n5`).
3. **Spec IDs.** `NG-TRN-001` and `LT-TRN-001` are `.tran`, so the shared transistor shape is `NG-XTR-001` and `LT-XTR-001`. The letters are `BJT`, `MOS`, `JFT` and `MES`.
4. **`.model 2 NPN` still loads.** Decision 4 refuses the plain-number model on the instance line; the `.model` line is unchanged, as for D.
5. **One closed list for LTspice's M.** The grammar cannot tell a monolithic MOSFET from a VDMOS without the model, so M takes the union of the two lists.
6. **`DOTTED_VALUE` outranks LTspice's `MODEL_BARE`.** Otherwise `version=3.3.0` was refused with the bare-word hint.
7. **Tests that used Q as a planned letter now use T** (M16), including the three reject fixtures, whose manifests have new hashes.
8. **`set_model_param` after a lone flag.** `VDMOS(pchan)` becomes `VDMOS(pchan KP=0.3)`; before the fix it would have written `(KP=0.3pchan)`.

**CI:** to be read once after the final push.

## 6. Review round 1 (2026-11-05, `48b497c`)

### 6.1 Outcome

M13 is accepted once the changes below are made. The design holds up on review:
- **Checks:** pytest 6,296 passed, 2 skipped, coverage 98.63%, in 15 min 33 s, with ngspice 47 and LTspice 26.1.1 from `.env`. ruff, ruff format and `mypy src` are clean. CI on #10 is green on all five jobs.
- **Grammar:** the grammar decides the boundary rule, as for X (P13). The number and keyword refusals in the transformer are limited to the positions where only a name may follow.
- **Split (T3):** the tree and signature snapshots are unchanged.
- **Edits:** the goldens and property tests cover each letter and every node count.
- **Probes by hand:**
  - nodes, model and area for 3- to 5-node lines;
  - `off` and `thermal` in the model's place;
  - `MODEL_TYPE_MISMATCH` for NIGBT on ngspice only;
  - `elements_on_net("OUT")` on `MQ8 d g OUT OUT nm`, which lists `MQ8` once.

### 6.2 Required changes

[x] **R1 — Record the LTspice reading of `Q1 c b e qm 1n5`.**
- The library loads it as a 4-node Q with model `1n5`, so `qm` is a net. LTspice reads `qm` as the model and `1n5` as an area of 1.5n.
- The only signal is `UNRESOLVED_MODEL`, and that is info when the scope has an `.include`.
- The grammar cannot decide this, because `2N3904` is also an embedded decimal (design point 2 in section 5). No code change is required.
- **Change:** add a row to the "cannot judge" table of `docs/grammars/ltspice/discrepancies.md`. Name the reading, the topology difference and the evidence. If no test pins the reading yet, add one beside the `Q1 c b e s qm 1n5` case in `tests/grammar/ltspice/test_ltspice_transistors.py`, and name it as the evidence.

[x] **R2 — One clear message for a positional area on an ngspice Q.** Decision 5 refuses the form, and ngspice 47 runs it, so users coming from ngspice will write it. Today one mistake gets three messages, and none of them names the cause:

| Line | Message today |
|---|---|
| `Q1 c b e qm 2` | "this line ends too early" (column 14) |
| `Q1 c b e s qm 2` | "`2` is in the model's place …" |
| `Q1 c b e qm 2 off` | "`off` is in the model's place …" |

- **Change:** each of these should say that an ngspice Q writes its area as `area=` (decision 0014 item 5). Keep the column at the offending token.
- **Tests:** assert the wording in `tests/grammar/ngspice/test_transistors.py` (`test_malformed_transistor_lines_are_rejected` and `test_a_model_name_cannot_be_a_number_or_a_keyword`). Update `docs/usage/errors.md` if the message is new.
- A plain number or keyword as the model on a 3-node line (`Q1 c b e 2`, `Q1 c b e off`) keeps its current message.

[x] **R3 — Readable element names in `MODEL_TYPE_MISMATCH`.**
- `diagnostics.py:170` writes `type(owner).__name__.lower()`. The result is "a bipolartransistor takes a model of type `NPN`, `PNP`", "a mosfet" and "a mesfet".
- **Change:** move `_ELEMENT_NAMES` from `edit/_ops_common.py` to the model layer (it serves both layers; the import contract must still hold), and use it in the edit errors and in the diagnostic.
- **Tests:** add a test that asserts the message for at least Q and Z.

[x] **R4 — No private import across layers.**
- `document/index.py` imports `_Transistor` from `model.nodes`.
- **Change:** either make the base class public (for example `Transistor`, exported, which is also useful to callers for `isinstance`), or use a tuple of the four classes. If it becomes public, update the architecture's element table and `docs/usage/elements.md`.

[x] **R5 — Fix architecture §7.8's implicit-substrate line.**
- It says "(and a MOSFET line without a bulk node)". Section 3 shows that a 3-node NMOS line stops ngspice. Only VDMOS writes 3 nodes, and it has no bulk.
- **Change:** limit the sentence to the 3-node Q. Check that decision 0014 item 3 and `docs/design/elements.md` say the same.

[x] **R6 — State where `ic=` is accepted.**
- Decision 0014 item 6, and decision 6 in section 2, say "on both dialects `ic=` takes a comma list". On LTspice only M takes `IC=`; the closed lists for Q, J and Z exclude it.
- **Change:** say so in both places, and check the LTspice spec entries and `docs/usage/elements.md` against it.

[x] **R7 — Restore `model-types.json`'s formatting.**
- The file was rewritten with `§` escapes and one item per line.
- **Change:** write `§` literally and keep each list on one line, as before, so that the diff shows only the new entries. No change in content.

[x] **R8 — Pin decision 3 in the document layer.**
- No document-layer test shows that transistor nodes reach the topology as written.
- **Change:** add tests to `tests/document/test_topology.py` (or beside it) for:
  - `MQ8 d g OUT OUT nm`: `elements_on_net("OUT")` lists `MQ8` once, and the line connects to `OUT` twice;
  - a 3-node Q: no ground connection is added;
  - a 5-node ngspice Q: all five nets are listed.

### 6.3 Exit for this round

Make R1 to R8. Run the full check set with `--require-solver ngspice --require-solver ltspice` and `OPENJELLYBEAN_LIB` set, read CI once after the push, and append a short report as 6.4. Then set the status to `READY FOR REVIEW`. **Do not archive** (T13 follows approval).

### 6.4 Report (2026-11-06, `1f09e40`)

R1 to R8 are made in one commit, `1f09e40`.

- **R1:** a row in the "cannot judge" table of `docs/grammars/ltspice/discrepancies.md` names both readings, the extra connection on `qm` and the `UNRESOLVED_MODEL` signal, and says to write the area as `1.5n`. Two tests pin it:
  - `test_the_model_is_the_last_name` (the `Q1 c b e qm 1n5` case) in `test_ltspice_transistors.py`, the library's reading;
  - the `q-embedded-area-after-model` probe in `test_ltspice_transistor_probes.py`, which shows LTspice runs it, so it resolves `qm` as the model.
- **R2:** ngspice's `bjt` rule gains three alternatives that read a number after the model. The transformer refuses them with one message, "`2` after the model is a positional area, and an ngspice Q writes its area as `area=2`". The column is that of the number, the offending token in all three forms (13, 15 and 13 in the table; before, 14, 15 and 15).
  - The 3-node forms keep their messages: `Q1 c b e 2` ("ends too early") and `Q1 c b e off` (the keyword).
  - The wording is asserted in a new `test_a_positional_area_on_q_says_to_write_area_equals`, beside the two tests named. Their Q area cases moved into it, and the keyword test now covers `Q1 c b e off` and `Q1 c b e 2 off`.
  - The solver test `test_a_positional_area_on_q_runs_and_is_refused` covers all three forms and the message. `docs/usage/errors.md` shows the message.
  - The strict grammar builds with no conflict, and the tree snapshot is unchanged.
- **R3:** `ELEMENT_NAMES`, `element_name()` and `element_phrase()` are in `model/nodes.py`, and the edit errors and `MODEL_TYPE_MISMATCH` use them. The diagnostic now says "a bipolar transistor", "a MOSFET", "a JFET" and "a MESFET"; `element_phrase` also gives "an inductor", where the old message said "a inductor".
  - The import contract holds.
  - Tests: `test_a_type_mismatch_names_the_element_kind` (Q, M, J, Z and D, both dialects) and `test_edit_errors_name_the_element_kind`.
- **R4:** the base class is public as `Transistor` and exported. `index.py` uses it, as do the probe and property tests. The architecture's element table and §5.3, `docs/design/elements.md` and `docs/usage/elements.md` name it.
- **R5:** §7.8 now names the 3-node Q only, and says why M is not affected. Decision 0014 item 3 already said so; the `Transistor` docstring now does too. `docs/design/elements.md` makes no claim about it.
- **R6:** decision 0014 item 6 and section 2 decision 6 say that `ic=` is on every ngspice transistor and on LTspice's M only. `LT-XTR-001`, `NG-XTR-001` and the LTspice grammar comment say the same. `LT-MOS-001` and `docs/usage/elements.md` already listed `IC` for M only.
- **R7:** `model-types.json` writes `§` literally with each list on one line. Against `main` the diff is the `source` sentence, which now names §7.3 to §7.7, plus the new entries.
- **R8:** `tests/document/test_transistor_topology.py`, on both dialects:
  - `MQ8 d g OUT OUT nm`: `elements_on_net("OUT")` lists `MQ8` once, and terminals 2 and 3 are on one net;
  - a 3-node Q: no ground connection, and the signature entry holds three nodes;
  - an ngspice 5-node Q: all five nets.

**Checks** at `1f09e40` (Windows, Python 3.14, ngspice 47 and LTspice 26.1.1 with `--require-solver ngspice --require-solver ltspice`, `OPENJELLYBEAN_LIB` set):
- ruff, ruff format, mypy (src and the strict test set), the import contract and pre-commit are clean.
- pytest: 6,334 passed, 2 skipped, coverage 98.58%, in 15 min 44 s.
- The signature and tree snapshots are unchanged.

**CI** on #10 at `1f09e40` is green on all five jobs.

Nothing is archived: T13 follows approval.
