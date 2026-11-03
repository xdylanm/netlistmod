# Phase 2 development plan

> **Status:** ACTIVE — approved by the maintainer on 2026-11-03, with section 8 decided; M10 is ready for review
> **Governed by:** [architecture.md](../architecture.md). This plan sequences the work; it does not change the architecture.
> **Follows:** [the phase 1 plan](./archive/phase-1/phase-1-plan.md), whose gate passed on 2026-11-03.

## 1. Objective

Reach v1 as architecture §6.7 defines it: every element type in the ngspice and LTspice device matrices is **supported**, and the full range of value specifications is covered (§6.4). Source stimulus specs become editable properties (G2, §7.1).

This covers Q, J, M, Z, E, F, G, H, B, S, W, T, O, U and A in both dialects, ngspice N, P and Y, LTspice `@` and `&`, and the forms of phase 1 letters that are still rejected, such as stimulus functions and LTspice's `tbl=`, `Q=` and `Flux=`.

**v1 is a beta.** It is feature complete and tagged `0.9.0`, and it is not published to PyPI. The maintainer then uses it in practice; a 1.0 release is outside this plan.

**Not in v1:** the non-goals of §1.4 still hold. qspice and xyce stay planned (§9.2), differential testing against spicelib (T9) stays optional, and LTspice `.machine` stays unsupported (section 8, point 4).

## 2. Assumptions

- The phase 1 layers, edit lifecycle and verification carry over unchanged. New elements are new grammar rules, nodes, spec entries and tests, not new mechanisms.
- **Each milestone covers both dialects.** Phase 1 built ngspice first to prove the design. With the shared core proven, a construct is designed once and validated on both solvers in the same milestone. Dialects remain separate grammars (P7).
- **Platforms are Windows and Linux.** macOS is not required, tested or claimed; it may well work, but nothing is validated there.
- Solver-backed tests stay local (§10.3): LTspice is only available on Windows, so the final evidence comes from the maintainer's Windows machine. CI runs only the solver-free tests and installs no solver.
- The maintainer's order from the [phase 1 limits decision](./archive/phase-1/phase-1-review.md#6-limits-for-your-decision) is fixed: CI, then the `.lib` block and `directives.add` limits, then stimulus specs and Q and M devices, then the rest. The order after that (M14 onward) is this plan's proposal.

## 3. What makes phase 2 different

Most phase 2 lines are simple to parse. These five points are where the guarantees are at risk, so each gets a decision record before its grammar is written.

1. **Where the nodes end and the model starts.** Q takes 3–5 nodes in ngspice (`nc nb ne <ns> <tj> mname`) and 3–4 in LTspice. M takes 4 in the ngspice general form, and 3 or 4 in LTspice (VDMOS has 3). Node and model names look alike. `X` already solves this by treating the last name as the subcircuit, but Q, J, Z, S and W can have bare `off` or `on`, or a positional area, after the model. A wrong boundary would put a model name in the topology signature with no error. M13 must define the rule, pin it with solver tests, and check whether any ngspice MOSFET model takes more than four nodes.
2. **Controlling references are topology.** The control nodes of E and G, and POLY's control pairs, are connections, so they belong in `nodes`, `nets()` and the signature. The source named by F, H and W (`Vnam`) is a reference, like K's inductors, and must be covered the same way. Without this, an edit could rewire a control path and still pass verification.
3. **Expressions hide connectivity.** `V(n1)*2` in B, E or G depends on nets outside the node list. §7.8 already accepts this limit, but phase 2 makes it much more common, and editing an expression can change that dependency. Expression edits stay allowed, and references stay out of the signature; a read-only query reports them (section 8, point 1).
4. **Nodes with their own syntax.** ngspice `A` has `%v`-style port types, `[ ]` vectors, `~` inversion and `null`. Adding these must not widen the node class that every other element uses (§6.3 rule 9).
5. **One letter, two devices.** ngspice `U` is a URC line, or a digital primitive when the PS compatibility flag is set and the line is inside a subcircuit (manual §10.1.3). The grammar tells them apart by shape, with no parser option (section 8, point 2).

**Compatibility rule for every milestone:** a netlist that parses today keeps the same topology signature and digest, so saved digests stay valid. A test pins this over the phase 1 corpus.

## 4. Milestones

Each milestone is one pull request, merged after the maintainer's review (section 8, point 5). It ends with its tests passing, spec entries and docs written (§14), and the full check set clean, including both solvers locally and CI. New diagnostics, exceptions and public names go into the error reference and usage guides in the same change.

**Closing procedure.** As in phase 1: a task list is written before the milestone starts, implementation ends at `READY FOR REVIEW`, and after the maintainer approves it becomes `COMPLETE (date)` and moves to `archive/phase-2/`. Decisions go in `docs/decisions/`, and any new risks go in the architecture or this plan.

### M10 — CI and project infrastructure (ready for review; [task list](./m10-tasks.md))

- GitHub Actions: lint and types; solver-free tests on Linux and Windows with Python 3.13 and 3.14; strict grammar build and spec coverage; docs links; coverage. Add Dependabot.
- No solver is installed in CI, and there is no ngspice job (section 8, point 5). The solver tests skip, as §10.3 provides.
- **First run on Linux.** The solver-free suite has only run on Windows (3370 passed and 2 skipped on 2026-11-03, about a minute). Fix what this exposes, including the two POSIX-only tests in `tests/test_source.py`, which have never run. If a test turns out to need a solver, mark it.
- This closes the Python 3.13 limit.
- Decision record amending §13 (no macOS, no ngspice job, no PyPI release workflow), §10.3 and §19 decision 14.
- Replace "milestone sequence TBD" in both device matrices and their JSON files with the milestones in section 5.
- **Exit:** all checks are green on a pull request. Branch protection is on if the repository's GitHub plan allows it; otherwise the rule is to merge only on green.

### M11 — Carried limits and messages

- **`.lib name` … `.endl` blocks** (limit 6): recognise the block in the grammar, and stop counting its body as top-level topology. Decision record, amending decision 0002.
- **`directives.add` over a singleton** (limit 9): refuse a second `.tran`, including in a batch, and point to `directives.set`. Decision record, amending decision 0007. Check first whether any dialect has a real use for two lines of one kind.
- **H5–H8** from [phase-2-code-changes.md](./phase-2-code-changes.md): argument type errors, wording for listed LTspice commands, internal references in messages, and models defined in `.if` blocks. H6 and H8 change §17, so they need a decision. Doing H7 now means later messages start clean.
- **LTspice `.end`** (limit 2): record that it stays required, closing the question decision 0009 left open (section 8, point 3).
- **Exit:** both limits are closed with negative and golden tests, and `phase-2-code-changes.md` is archived.

### M12 — Stimulus specs

- A typed `SourceSpec` (§5.3) replaces the rejected `stimulus` rule. Each function has named or positional arguments with spans.
- **ngspice** (manual §4.1): PULSE, SIN, EXP, PWL, SFFM, AM, TRNOISE, TRRANDOM, EXTERNAL and DISTOF1/2.
- **LTspice:** PULSE, SINE, EXP, SFFM, PWL with its file and repeat forms, the WAV file form and the trigger parameter; for I, also `tbl=`, `step(...)`, `load` and `R=`.
- **Edit API:** set a whole stimulus, and set one argument. Decide what setting a stimulus does to an existing DC or AC value, and what happens when a source has none.
- Remove `test_review_package_holds_the_generated_spec_coverage` with the first new spec entry, as its comment says.
- **Exit:** `half_rectifier.net` loads and edits, its solver test passes on LTspice, and each function has a spec entry, golden diff and solver test.

### M13 — Transistors (Q, M, J, Z)

- The node and model boundary rule of section 3, point 1, as a decision record before the grammar.
- Typed nodes, instance parameters, flags (`off`), positional area and `ic=`. Extend `model-types.json` (Q → NPN, PNP; M → NMOS, PMOS, and LTspice's VDMOS form; J → NJF, PJF; Z → NMF, PMF, and LTspice's IGBT form).
- `set_model`, `set_param` and `.model` edits on these elements, with `MODEL_TYPE_MISMATCH`.
- **Exit:** the milestone's spec entries are validated on both solvers, property tests cover the new elements, and the signature's compatibility test passes.
- **Maintainer checkpoint:** hands-on use with your own transistor netlists. Most real circuits should now load, so this is the best time to change the order of what follows.

### M14 — Linear dependent sources and switches (E, F, G, H, S, W)

- Linear forms, with controlling references per section 3, point 2: E and G control nodes in the signature and net queries; F, H and W source names resolved, and covered by the signature, with a diagnostic when unresolved.
- S and W models (SW, CSW) with `on` and `off`.
- **Exit:** a negative test shows that any change to a control node or controlling source is a `TopologyViolation`.

### M15 — Behavioural forms (B, and nonlinear E, F, G, H)

- **B:** ngspice forms (manual §5.1); LTspice `V=`, `I=`, `R=` and `P=` with their parameters.
- **E and G:** ngspice `vol=`, `cur=`, `VALUE`, `TABLE` and POLY (§5.2–§5.5); LTspice `table=`, `Laplace=`, `value=` and POLY. POLY control nodes are topology.
- **Also:** LTspice `C` with `Q=`, and `L` with `Flux=` and the hysteretic form.
- **Formula grammar:** add `V()`, `I()` and the special variables (`time`, `temper`, `hertz`) per dialect, so that parameter scans do not report them. This closes the `time` note carried from M8. It stays a scan, not an evaluator (non-goal 6).
- **Edit API:** set an expression, table or polynomial coefficients. Add a read-only query for the nets and sources an expression reads (section 8, point 1).
- **Exit:** every form has golden diffs and solver tests showing results move as expected.

### M16 — Transmission lines (T, O, U as URC, Y, P)

- T with `Z0=` and `TD=`, or `F=` and `NL=`; O with LTRA; U as URC, in both dialects.
- ngspice Y (TXL) and P (CPL). P has a variable node list up to the line count, so it follows the rule from M13.
- **Exit:** each letter is `supported`, with spec entries validated wherever the solver can run the form.

### M17 — Special and mixed-signal devices (A, N, U digital, `@`, `&`)

- **ngspice A:** the port syntax of manual §8 and §22.2, in its own rules (section 3, point 4). Decide how vector ports appear in `nodes` and the signature.
- **ngspice N:** OSDI devices (manual §9). A solver test needs a compiled model, so these entries may stay `documented`.
- **ngspice U digital:** told apart from URC by shape, and accepted only in a subcircuit body, with `DIALECT_GATED_SYNTAX` (info) because it needs the PS flag (section 8, point 2). Check the shapes against every basic type in manual §10.1 first; raise it with the maintainer if any form is ambiguous.
- **LTspice:** A (eight fixed nodes and a model), `@` and `&`. `.machine` stays an `UnsupportedConstruct`; record it as a named v1 exclusion (section 8, point 4).
- **Exit:** no letter in either matrix is `planned`.

### M18 — Completeness audit

- **Value specifications (§6.4):** check the manual's full range against the grammar, including the comma-separated lists recorded in LTspice's `discrepancies.md`.
- **Architecture tests:** no matrix entry is `planned`, every `UnsupportedConstruct` path that remains is justified, and the lookaround terminal list is reviewed (limit 3).
- **Corpus:** real circuits for each device group, with manifests and provenance. Extend the independent Hypothesis oracle and the edit properties to the new elements.
- **Exit:** the spec-coverage report shows every construct with tests, and each `documented` entry says why the solver cannot decide.

### M19 — v1 review package and beta tag

- Update the usage guides, error reference, README and CHANGELOG, and set the version to `0.9.0`. The README says this is a feature-complete beta.
- Final evidence from a clean clone with both solvers, as in phase 1's T10, and a v1 review package.
- After the gate: tag `v0.9.0`. Nothing is published to PyPI. What 1.0 commits to in the public API (§18) is reviewed after the maintainer's practical use.
- **Exit:** the v1 gate (section 6) passes.

## 5. Device letters by milestone

| Milestone | ngspice | LTspice |
|---|---|---|
| M12 | V, I stimulus forms | V, I stimulus forms |
| M13 | Q, M, J, Z | Q, M, J, Z |
| M14 | E, F, G, H (linear), S, W | E, F, G, H (linear), S, W |
| M15 | B; E, F, G, H (nonlinear) | B; E, F, G, H (nonlinear); C and L forms |
| M16 | T, O, U (URC), Y, P | T, O, U |
| M17 | A, N, U (digital) | A, `@`, `&` |

## 6. v1 gate

You confirm v1 can be tagged when:

- [ ] Every element in both device matrices is `supported`, and the full range of value specifications is covered.
- [ ] Every construct has a spec entry and tests, and the spec-coverage and strict-grammar checks pass.
- [ ] Round-trip is byte-exact across the corpus, and golden edit diffs show only intended changes.
- [ ] The topology guarantee covers the new elements, including controlling references, with negative and property tests.
- [ ] CI is green on Linux and Windows, on Python 3.13 and 3.14.
- [ ] ngspice and LTspice solver-backed tests pass on your machine.
- [ ] You have used the library on your own netlists, including transistor and behavioural circuits.
- [ ] Remaining limits are documented and acceptable.
- [ ] All task lists are archived, and this plan is archived as `COMPLETE`.

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| A wrong node and model boundary changes the meaning of a line with no error | Decision record before the grammar; solver tests for each form; an unresolved model is already a diagnostic. |
| LALR conflicts grow with flags, `%` port types and keyword-like node names | Strict build from the start of each milestone; `A` in its own rules; add forms one at a time. |
| Lookaround terminals grow beyond the pinned list (limit 3) | The architecture test fails on any addition, so each one is reviewed; revisit in M18. |
| A saved topology digest changes for an existing netlist | The compatibility rule in section 3, pinned by a test. |
| `transform.py` (about 1,300 lines) and `operations.py` become too large for P12 | Split by element family at the start of M13, with no change in behaviour. |
| A solver cannot run a form: OSDI needs a compiled model, and some code models may be missing from the Windows build | Spec status stays `documented` with a `validation_note`, as §11.2 allows. Check availability in each milestone's first task. |
| Model files and examples have mixed licences | Author fixtures here or export your own circuits (§12). Files from solver distributions need checking first. |
| The local suite, about 11 minutes with solvers, gets much longer | CI runs solver-free, about a minute today. Split the local run if it becomes a burden, without dropping any test from the final run. |
| Windows-only assumptions appear on the first Linux run | That is M10's job; fix them there, before the grammar grows. |
| A solver test is the only check of a behaviour on Linux | Solver evidence stays on Windows by design, so the local run with both solvers remains part of every milestone and the gate. |

## 8. Decisions for the maintainer

All decided on 2026-11-03.

1. **Expressions and hidden connectivity: decided.** An expression edit may change which nets it reads. §7.8's node-list guarantee stays, expression references stay out of the signature, and a read-only query reports them.
2. **ngspice digital `U`: decided.** A URC line and a digital primitive have different shapes: `U1 in out 0 um l=50u` against `U1 inv p n in out d0 dmio`. Probes on ngspice 47 showed:
   - Without a PS compatibility flag, the digital line is an error in the solver. With `ngbehavior=psa`, it runs inside a subcircuit and is an error at the top level.
   - A URC line whose first node is named `inv` stayed a URC line with `ngbehavior=psa`.

   There is no parser option. The grammar tells the forms apart by shape, accepts the digital form only in a subcircuit body as the manual says, and reports `DIALECT_GATED_SYNTAX` (info) because it needs the flag. This needs no exception to P5, and it matches the rule that the library does not validate solver inputs. M17 checks the shapes against every basic type before relying on this.
3. **LTspice `.end`: decided.** It stays required, and M11 records this as closing the question.
4. **LTspice `.machine`: decided.** It stays `UnsupportedConstruct` in v1, as a named exclusion, because its `.output` lines drive nodes.
5. **Workflow: decided.** One pull request per milestone, with Linux and Windows CI and no macOS. There is no ngspice job: the solver tests and spec entries are validated on ngspice 47, a distribution package may be a different version, and the required local run already covers ngspice.
6. **Stress testing: decided.** None is added, so limit 8's stress and performance part stays as it is.
7. **v1 release: decided.** v1 is a beta, tagged `0.9.0`, with no PyPI publication.

**Needed from you:** netlists with BJTs, MOSFETs and behavioural sources from your own KiCad and LTspice projects for the corpus, ideally before M13.
