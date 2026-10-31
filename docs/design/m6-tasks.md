# M6 task list — edit layer (ngspice)

> **Status:** READY FOR REVIEW — implemented 2026-10-31 (section 9); approved by the maintainer (2026-10-31); section 2 records the decisions.
> **Part of:** [phase-1-plan.md](./phase-1-plan.md) (milestone M6). Governed by [architecture.md](../architecture.md) (§2 P1–P4, P11; §3 layers [4]–[5]; §7 (normative); §10 T4–T6; §16; §17; §19 decision 18; §21). Builds on the design notes [m3-elements.md](./m3-elements.md) (element sub-spans), [m4-statements.md](./m4-statements.md) (statement and directive sub-spans), and [m5-document.md](./m5-document.md) (`Netlist`, `Lines`, scopes, references, signature). Citations use the manual edition in [references.md](../references.md).

## 1. Scope

The edit layer (`src/netlistmod/edit/`, architecture §3 layers [4] and [5], §4):

- **Edit plans** (§7.5): `Edit`, `EditPlan` and `apply_edits`, a pure splice over the original text.
- **The restricted edit API** (§7.2), for phase 1 constructs:
  - element values, formulas and instance parameters;
  - `set_model`;
  - source `DC`/`AC` values and the `K` coupling value;
  - X instance parameter overrides;
  - add or set a `.param`; edit `.model` parameters;
  - add, replace or remove directives with a placement strategy;
  - add an `.include` for a harness file (§7.9).
- **Write-time verification** (§7.6): splice, re-parse, compare the topology signature with the one taken at load, and check that text outside the edited spans is unchanged. `save()` writes atomically in the original encoding.
- **Forbidden operations** (§7.3) have no API. Where an API could be misused (replacing an element line, removing an `.include`, touching an opaque block, inserting an element as a "directive") it raises `TopologyError`. A splice that changes topology anyway raises `TopologyViolation`, and nothing is written.
- **Before coding**, decision record 0007 resolves architecture §21 **unresolved** question 1 (edit lifecycle) and the `set_model` half of question 2. It also settles these deferred items:
  - text conventions for inserted lines;
  - placement semantics;
  - directive and `.param` matching and upsert;
  - edit scope inside subcircuits (§7.4);
  - where an added instance parameter goes (the gap in `m3-elements.md`);
  - `MODEL_TYPE_MISMATCH`, deferred by M5.

**Exit (from the plan):** the operations in §7.2 work for phase 1 constructs; every forbidden operation in §7.3 has a negative test; T4 golden-diff, T5 property and T6 negative tests pass.

## 2. Decisions (maintainer, 2026-10-31)

The maintainer accepted every recommendation below as written (2026-10-31). "Recommendation" marks the accepted choice; an "Alternative" was considered and not chosen. Decision record 0007 (D1) records them. Probe evidence is in section 7.

1. **Edit lifecycle** (§21 unresolved question 1).
   *Recommendation:* **immutable and eager.** Each edit method returns a **new** `Netlist`; the old one is unchanged. The call builds an `EditPlan` against the current text, applies it, re-parses, and verifies (decision 8) before returning, so a failing edit raises and nothing changes. This answers the five sub-questions:
   - **Staged or eager:** eager, per call or per batch.
   - **Read-back:** yes. The returned netlist is fully indexed, so `references_to_param("Rx")` works right after `params.set("Rx", …)`.
   - **Handles after a re-parse:** nodes and `Line`s belong to the netlist they came from. Passing one from an older netlist to an edit raises `EditError`. Callers address by designator and scope, or look the item up again.
   - **Edit set:** `netlist.batch()` collects several operations and applies them as **one** plan with one re-parse and verification. It is atomic: all or nothing.
   - **Two edits to the same span** in one batch: `EditError`, never last-wins (§7.5 forbids overlap). Two insertions at the same point keep their submission order.
   - **Baseline:** every derived netlist carries the topology signature taken when the **original** file was loaded, so verification always compares against the load (§7.6), not the previous step.
   *Alternative:* a mutable netlist with staged edits and an explicit `commit()`. Not chosen: it needs invalidation rules for every handle and index, and the nodes are immutable by design (P2).
2. **Edits inside a subcircuit definition** (§7.4, P11).
   *Recommendation:* an edit is addressed by designator and definition scope (`scope=("amp",)`, as in M5). Any edit with a non-empty `scope` also requires `in_definition=True`, otherwise `EditError` with a message that it would change every instance of `amp`. The topology-safe per-instance alternative is `set_instance_param` on the X line (§7.4). No string path form in M6 either; the tuple stays the only addressing.
3. **`set_model`** (§7.2; §21 question 2, the `set_model` half; `MODEL_TYPE_MISMATCH` from M5).
   *Recommendation:*
   - **When the new model resolves** (in the element's scope chain, M5 rules), its type must be allowed for the element letter: R → `R`, C → `C`, L → `L`, D → `D` (§2.5 Table 2.3; case-insensitive). Otherwise `EditError`. Each letter has one type, so this equals §7.2's "same model type as the current one".
   - **When it does not resolve,** `EditError`, unless the caller passes `allow_external=True` **and** a searched scope has an opaque `.include`/`.lib`. With that flag the edit is made, and the new netlist carries the usual `UNRESOLVED_MODEL` info diagnostic; the type cannot be checked.
   - **Load-time diagnostic:** M6 also adds the warning `MODEL_TYPE_MISMATCH`, at the model name, for an element whose resolved model has a type not allowed for its letter (decision 0006 deferred it). Added to §17.
4. **Text conventions for inserted text** (§21 deferred).
   *Recommendation:*
   - **Line ending:** the inserted line uses the terminator of the line just before the insertion point, or of the first line when inserting at the start. A file's mixed endings are thus kept locally consistent and never normalised (P3).
   - **The end of the file:** placements never insert after `.end`, so a missing final newline is never touched.
   - **Keyword case:** lowercase (`.param`, `.include`); one blank between fields; `name=value` without blanks; one assignment per new `.param` line; no indentation, also inside a subcircuit body.
   - **Replacement text:** a value or formula replaces exactly the slot's sub-span (`m3-elements.md` §4: for `r=1k`, only `1k`). `set_formula("Rx*2")` writes `{Rx*2}`; `set_value` takes the text as given.
5. **Where added fields go** (the gap in `m3-elements.md`).
   *Recommendation:*
   - **A new instance parameter** goes after the element's last field: its last parameter, flag, model or value, on whichever physical line that is. It is written as one blank plus `name=value`, before any trailing comment or continuation that follows.
   - **A value where none exists** (`R1 a b rmod` → `R1 a b 1k rmod`) is inserted after the last node.
   - **A new `.model` parameter** goes after the last parameter, inside the parentheses when there are any.
   - **`set_ac` on a source without `AC`** appends `AC mag [phase]` after the DC part; when an AC part exists, it replaces its magnitude, and its phase if given.
   - **Removing** an instance parameter or a model parameter is **not** offered in M6. §7.2 lists only set and add.
6. **Placement** (§7.2, §21 deferred).
   *Recommendation:* `Placement.AFTER_TITLE`, `Placement.AFTER_LAST_PARAM` (falls back to after the title when there is none), `Placement.BEFORE_END`, `Placement.before(line)` and `Placement.after(line)`.
   - **Defaults:** `.param` → `AFTER_LAST_PARAM`; directives → `BEFORE_END`; `.include` → `AFTER_TITLE`.
   - **Scope:** directives and `.include` are top-level only (decision 0005 rejects them in a body). A `.param` added inside a definition (with `in_definition=True`) goes after the definition's last body `.param`, else at the start of the body.
   - **Anchors:** a line from a different netlist, or a placement inside an opaque block, is an `EditError`.
7. **Matching and upsert** (§21 deferred).
   *Recommendation:*
   - **`params.set(name, value, scope=…)`:** when the name is assigned in that scope (folded), replace the value of the **effective** assignment, the last one (M5 resolution); otherwise add a `.param` line by placement. Earlier repeats are left as they are, and keep their `DUPLICATE_DEFINITION` info.
   - **`directives.set(text)`** for the **singleton** kinds `.tran`, `.ac`, `.dc`, `.op` and `.temp`: replace the one existing line of that kind, or add one if there is none. With two or more, `EditError` (ambiguous; use `replace(line, …)`). ngspice 47 runs two `.tran` lines with the same settings and uses the last `.temp` (section 7).
   - **Repeatable kinds** (`.options`, which ngspice merges; `.ic`, `.nodeset`, `.save`, `.meas`, unknown dot-commands): `set` raises `EditError`. Use `add`, `replace` or `remove`.
   - **What `add`/`replace`/`set` accept:** text that must parse as exactly **one** line of the stated kind, a typed directive or an unknown dot-command. Anything else is `TopologyError` (an element, a `.subckt`, `.global`) or `EditError` (several lines, a different kind, a syntax error).
   - **`remove(line)`:** allowed for typed and unknown directives only. Removing a `.param`, `.model`, `.global`, element, definition, `.include`/`.lib` or opaque block is a `TopologyError` or `EditError`. `.param`/`.model` are properties that may be added and edited but not removed (§7.1), and removing one could leave references unresolved.
8. **Verification** (§7.6; amends architecture decision 18 "no validation of replacement text").
   *Recommendation:* every apply runs, in order:
   1. the splice (§7.5 rules);
   2. a re-parse with the same dialect and `rkm` (a failure is `EditError` carrying the `ParseError`);
   3. the signature compared with the load baseline (`TopologyViolation`);
   4. a check that every byte outside the edited spans is identical, **always on**, not debug-only;
   5. a **slot check**: each edited slot re-parses as a slot of the same kind whose text is exactly the replacement.
   Step 5 catches `set_value("1k 2k")`, which parses but would add a model `2k`. It verifies that the edit landed where intended; it does not validate the caller's value (still the caller's responsibility, decision 18). §7.6 and decision 18 are amended to say so.
   `save(path=None)` re-verifies, encodes in the original encoding (`EncodingError` if the new text cannot be encoded, before any write), and writes atomically (`SourceText.write`). An unedited netlist saves its original bytes (P3).
9. **`add_include(path)`** (§7.9).
   *Recommendation:* writes `.include "path"` (quoted, so `//` or blanks in a path are safe, decision 0002) at `AFTER_TITLE` by default.
   - The path is written as given; the library never reads it.
   - `names.md`/the usage docs note that ngspice resolves a relative path from the netlist file's folder, not the working directory (section 7).
   - The include's content is outside the parsed file, so the topology check does not cover what it adds; that is the harness tool's responsibility (§7.8, §7.9).
   - Adding the same path twice is an `EditError`.
10. **Low-level plans.**
    *Recommendation:* `Edit(span, text, reason)`, `EditPlan` and `apply_edits(text, plan) -> str` are public for tests and advanced use. A plan can only be applied to a `Netlist` through `netlist.apply(plan)`, which runs the same verification (decision 8), so the restricted API cannot be bypassed.

## 3. Design

### 3.1 Package layout (architecture §4)

- `edit/plan.py`: `Edit`, `EditPlan`, `apply_edits`.
- `edit/api.py`: the operations, as methods on `Netlist` and its `params`/`directives` helpers, implemented here.
- `edit/placement.py`: `Placement`.
- `edit/verify.py`: re-parse, signature, outside-text and slot checks.
- `edit/conventions.py`: line ending and keyword rules (decision 4).

`document/` must not import `edit/`. The edit methods are therefore attached in the layer that may see both: either `edit/` provides an `EditableNetlist` facade, or `Netlist` exposes them through a small protocol that `edit/` implements. D2 decides which, keeping the import-linter contract.

### 3.2 API sketch (proposed; D2 finalizes it)

```python
nl = Netlist.load("amp.cir", dialect=Dialect.NGSPICE)

nl2 = nl.set_value("R22", "2.2k")
nl2 = nl.set_formula("R1", "Rx")  # R1 a b {Rx}
nl2 = nl.set_param("R1", "tc1", "2m")  # instance parameter, set or add
nl2 = nl.set_model("D1", "dmod2")  # EditError if not type D
nl2 = nl.set_dc("V1", "5")
nl.set_ac("V1", "1", phase="90")
nl2 = nl.set_coupling("K1", "0.95")
nl2 = nl.set_instance_param("X1", "r2", "5k")  # per-instance override (§7.4)
nl2 = nl.params.set("Rx", "22k")  # upsert (decision 7)
nl2 = nl.set_model_param("dmod", "is", "1e-14")
nl2 = nl.directives.set(".tran 1u 10m")  # singleton upsert
nl2 = nl.directives.add(".save v(out)", Placement.BEFORE_END)
nl2 = nl.directives.remove(nl.lines.find(OpDirective))
nl2 = nl.add_include("harness.cir")
nl2 = nl.set_value("R1", "5k", scope=("amp",), in_definition=True)

with nl.batch() as b:  # one plan, one verification
    b.set_value("R1", "1k")
    b.params.set("Rx", "2k")
nl3 = b.result

nl3.save("amp.edited.cir")
```

## 4. Tasks

Every task ends with `ruff check`, `ruff format --check`, `mypy --strict`, `lint-imports`, and `pytest` (coverage gate) green, run as `uv run --env-file .env python -m <tool>` (AGENTS.md; on Smart App Control failures follow docs/testing.md). P13 applies: the edit layer composes text from the caller's strings and the conventions; it never scans source text to find syntax. Spans come from the nodes. Where a task says "settle", state the choice with its basis in the design note and the report.

### Decisions and design

[x] **D1 — Decision record 0007: edit lifecycle and edit semantics.**
Record the section 2 outcomes. Amend the architecture:
- §7.2: placement, upsert, set_model;
- §7.4: `in_definition`;
- §7.5: batches;
- §7.6: the outside-text check always on, and the slot check;
- §16: replace the illustrative sketch with the real API, or point to the design note;
- §17: `MODEL_TYPE_MISMATCH`;
- §19 decision 18: clarify;
- §21: mark question 1, the `set_model` half of question 2, and the deferred items "text conventions", "matching and upsert", "hierarchical addressing" (edit part) and placement resolved.
Status `proposed` until the maintainer accepts it.

[x] **D2 — Design note `docs/design/m6-edits.md`.**
- **API:** every operation with its signature, the slot it edits (by node field and sub-span), its insertion rule, and the errors it raises; the facade or protocol choice of 3.1.
- **Verification steps.**
- **Edit coverage:** a table "§7.2 allowed operation → method" and "§7.3 forbidden operation → no API / `TopologyError` test".
Reviewed by the maintainer **before T3** (M5's D2 was written after the fact; M6's API is the public surface, so review it first).

### Implementation

[x] **T1 — `Edit`, `EditPlan`, `apply_edits`** (§7.5).
Sorted by position; overlaps are `EditError`; zero-width insertions are allowed; equal positions keep submission order; offsets are against the original; the input is never mutated. T1-tier tests, plus a Hypothesis test that random non-overlapping plans reproduce a reference splice.

[x] **T2 — Verification** (decision 8).
Re-parse, signature, outside-text and slot checks; `EditError` wrapping `ParseError`; `TopologyViolation` with the first differing signature entry in its message. Tests that inject a faulty plan (one that edits a node span directly) and see `TopologyViolation`.

[x] **T3 — Element operations** (after D2 review).
`set_value`, `set_formula`, `set_param`, `set_model` (decision 3), `set_dc`, `set_ac`, `set_coupling`, `set_instance_param`; `scope`/`in_definition` (decision 2); insertion rules (decision 5). Settle:
- `set_value` on a source with `dc_keyword=False`: replace only; never add `DC`;
- `set_value` on a `K` line: no; that is `set_coupling`;
- `set_param` on a name that is a value keyword (`r=`): replace the keyword value;
- RKM text with `rkm=False`: the re-parse fails, so `EditError` naming the option.

[x] **T4 — `.param` and `.model` operations.**
`params.set` (decision 7, including `scope`/`in_definition`) and `set_model_param`. Settle: `params.set` with a value that is a bare expression (the re-parse rejects it, decision 0005: `EditError` suggesting braces); quoting of string values.

[x] **T5 — Directives, placement and include.**
`directives.add/replace/remove/set`, `Placement`, `add_include` (decisions 6, 7, 9); the forbidden variants (decision 7) raise `TopologyError`.

[x] **T6 — `batch()`, `apply(plan)`, `save()`.**
Per decisions 1, 8 and 10. Atomicity: a failing operation in a batch leaves the netlist unchanged. `save()` encoding failure: `EncodingError` before writing. A stale-handle check (a node from another netlist) raises `EditError`.

[x] **T7 — `MODEL_TYPE_MISMATCH`** (decision 3): a diagnostic at load, the table as data, a spec note in `names.md` or the design note, and tests.

### Validation, docs and tests

[x] **T8 — Golden-diff tests (T4 tier).**
`tests/edits/` with `input.cir` + operation → `expected.cir` pairs, compared byte for byte, plus a unified diff in the failure message. Cover every operation; LF, CRLF and mixed endings; a missing final newline; continued lines (`+` and `\\`); trailing comments; tabs; a body edit with `in_definition=True`; a batch. The golden files go under `tests/corpus/ngspice/edits_golden/`, with a manifest; `.gitattributes` keeps them byte-exact (author `xdylanm`, MIT, confirmed by the maintainer on 2026-10-31).

[x] **T9 — Property tests (T5 tier, Hypothesis).**
Over generated netlists (reuse the M3–M5 generators):
- any sequence of allowed edits preserves the signature;
- each operation is idempotent (applying it twice gives the same text as once);
- an empty plan returns identical bytes;
- text outside the edited spans is unchanged;
- `save` then `load` gives the same items.

[x] **T10 — Negative tests (T6 tier).**
One per §7.3 forbidden operation, plus the misuse cases:
- adding, removing or reordering an element, and changing a node, type or designator: no API, so check by `apply(plan)` with a crafted plan → `TopologyViolation`;
- renaming a net, or changing `.subckt` ports or definitions: the same way;
- replacing an element line, removing an `.include`, editing an opaque block, adding an element through `directives.add`, removing `.global`: `TopologyError`;
- a wrong value kind (`set_value` on a diode, `set_model` on a source), an unresolved model, a wrong model type, `scope` without `in_definition`, an ambiguous `directives.set`, a stale handle, overlapping edits: `EditError`.

[x] **T11 — Solver checks (light; M7 does the full set).**
- An edited divider (`set_value`) and an added `.param` reach ngspice and move `v(out)` as computed.
- A `directives.set(".tran …")` result runs.
- An unedited `save` gives identical results to the original.
Record the section 7 probes as tests.

[x] **T12 — Docs.**
- `docs/usage/editing.md` with executed recipes: the §1.2 examples (set R22, replace with a formula and add `.param`, set `.tran`, sweep a `.param` across runs, add a harness include).
- `CHANGELOG.md`, `README.md` status, `docs/testing.md` (golden tests: how to add one), and the phase plan's M6 heading.
- Update or archive `m3-elements.md`, `m4-statements.md` and `m5-document.md` per the plan: fold the parts M6 relies on into `m6-edits.md`, or keep them ACTIVE with a pointer, and say which.
- Docstrings on every public name.

[x] **T13 — Exit.**
Full check set, a fresh-clone test, and the solver tests. Report what changed, every "settle" decision with its basis, deviations from this list, and limitations. Set this document's status to `READY FOR REVIEW`. **Do not archive.**

## 5. Dependencies between tasks

```
Section 2 decisions → D1 → D2 (maintainer review) → T3
T1 → T2 → T3, T4, T5 (independent of each other once T2 is in)
T3 → T7
T3–T5 → T6 → T8, T9, T10
T6 → T11
T8–T11 → T12 → T13
```

## 6. Behaviour table (minimum; extend in T3–T6 and T8)

| Netlist (essentials) + operation | Expected |
|---|---|
| `R22 a b 1k` + `set_value("R22", "2.2k")` | `R22 a b 2.2k`; nothing else changes |
| `R1 a b r=10k` + `set_formula("R1", "Rx")` | `R1 a b r={Rx}` |
| `R1 a b rmod` + `set_value("R1", "1k")` | `R1 a b 1k rmod` |
| `R1 a b 1k` + `set_param("R1", "tc1", "2m")` | `R1 a b 1k tc1=2m` |
| `R1 a b 1k ; note` + `set_param(…)` | `R1 a b 1k tc1=2m ; note` |
| `R1 a b 1k` / `+ tc1=1m` + `set_param("R1", "tc1", "2m")` | `+ tc1=2m` (in place, on the continuation line) |
| `D1 a k dm` + `set_model("D1", "dm2")`, `.model dm2 d` exists | `D1 a k dm2` |
| same, `.model dm2 npn` | `EditError` (type) |
| same, no `dm2`, file has `.include m.lib` | `EditError`; with `allow_external=True`: done, `UNRESOLVED_MODEL` info |
| `V1 in 0 DC 3` + `set_dc("V1", "5")`; `set_ac("V1", "1")` | `V1 in 0 DC 5`; `V1 in 0 DC 3 AC 1` |
| `X1 in out div` + `set_instance_param("X1", "r2", "5k")` | `X1 in out div r2=5k` |
| `R1` inside `.subckt amp` + `set_value("R1", "5k", scope=("amp",))` | `EditError` (needs `in_definition=True`); with it: body line edited |
| `.param Rx=1k` + `params.set("Rx", "22k")` | `.param Rx=22k` |
| no `.param` + `params.set("Rx", "22k")` | `.param Rx=22k` after the title, with the file's line ending |
| `.model dm d(is=1e-14)` + `set_model_param("dm", "n", "1.5")` | `.model dm d(is=1e-14 n=1.5)` |
| one `.tran 1u 5u` + `directives.set(".tran 1u 10m")` | replaced in place |
| no `.tran` + `directives.set(".tran 1u 10m")` | added before `.end` |
| two `.tran` lines + `directives.set(…)` | `EditError` (ambiguous) |
| `directives.set(".options reltol=1e-4")` | `EditError` (repeatable: use `add`) |
| `directives.add("R9 a 0 1k")` | `TopologyError` |
| `directives.remove(<element line>)`; `remove(<.include>)`; `remove(<.global>)` | `TopologyError` |
| `add_include("harness.cir")` | `.include "harness.cir"` after the title |
| `set_value("R1", "1k 2k")` | `EditError` (slot check) |
| `set_value("R1", "2k7")` with `rkm=False` | `EditError` naming the `rkm` option |
| CRLF file + any insertion | the inserted line ends in CRLF |
| file without final newline + `directives.add(…)` | inserted before `.end`; the end of file is unchanged |
| a batch of three edits, the third invalid | `EditError`; the netlist is unchanged |
| a crafted plan that renames a node | `TopologyViolation`; nothing written |

## 7. Probe facts gathered while planning (ngspice 47, 2026-10-31)

Re-recorded as solver tests in T11.

| Input | ngspice 47 |
|---|---|
| two `.tran` lines (`1u 5u`, `1u 20u`) | two transient runs with the same point count (one setting applied to both) |
| two `.op` lines | two operating-point runs |
| `.op` and `.tran` | both run |
| `.temp 50` then `.temp 100` | analysis at 100 °C: the last `.temp` wins |
| `.options temp=40` and `.options tnom=30` | both apply (TEMP 40, TNOM 30): `.options` lines merge |
| `.include harness.inc` (relative), ngspice run from another folder | resolved from the netlist file's folder |

## 8. Out of scope for M6

- Argument-level directive edits (for example, changing only `tstop`); M6 replaces whole directive lines.
- Removing parameters, models or instance parameters.
- String path addressing.
- Editing stimulus specs (phase 2) and `.meas` bodies.
- Reading or validating included files.
- The LTspice dialect (M8).
- Solver-backed result validation beyond the light checks of T11 (M7).

## 9. Implementation report (2026-10-31)

**What changed.** Decision record 0007 (status `proposed`) and the architecture amendments of
D1 (§4, §7.2, §7.4, §7.5, §7.6, §16, §17, §19 decision 18, §21). Design note
[m6-edits.md](./m6-edits.md) (D2). The edit layer under `src/netlistmod/edit/`: `plan.py`,
`conventions.py`, `placement.py`, `verify.py`, `operations.py` and `api.py`. `netlistmod.Netlist`
is now the editable subclass of the read-only `netlistmod.document.Netlist`, whose constructors
return `Self`. New diagnostic `MODEL_TYPE_MISMATCH`, with its table as data
(`document/model-types.json`, `document/models.py`). Tests: `tests/edits/` (plan, verification,
element, statement and directive operations, lifecycle, golden, property and negative tests),
`tests/solver/test_ngspice_solver_edits.py`, the new corpus family `edits_golden` (4 inputs,
20 cases), and an architecture test that `edit/` does not import `re`. Docs:
`docs/usage/editing.md` (executed), CHANGELOG, README, `testing.md`, `provenance.md`, the phase
plan and the design-folder index.

**Settled** (each with its basis in [m6-edits.md](./m6-edits.md) §4):

- *T3:* `set_value` on a source replaces the DC value as written and never adds a value or `DC`
  (use `set_dc`); `set_value` on a `K` line is an `EditError` pointing to `set_coupling`;
  `set_param` with a value keyword (`r`, `resistance`, `c`, `capacitance`, `l`, `inductance`) sets
  the value when it is written `r=…`, else `EditError` (use `set_value`); RKM text with
  `rkm=False` is an `EditError` wrapping the `ParseError`, which names `rkm=True`. A repeated
  designator or instance parameter is an `EditError`. `set_model` replaces an existing model
  name only. The element keywords `DC`/`AC` are written uppercase (the manual's spelling and the
  behaviour table), dot-command keywords lowercase.
- *T4:* `params.set` with a bare expression is an `EditError` wrapping the `ParseError`, which
  says to use braces or single quotes; string values are written as given (the caller quotes).
  `set_model_param` edits the first `.model` of that name in the given scope; a repeated
  parameter or a model with empty parentheses (no span to anchor after `(`, P13) is an
  `EditError`.
- *T5:* directive text must be one physical line; it is classified in a probe netlist before
  the plan is applied, so a topology line is a `TopologyError` rather than a
  `TopologyViolation`. A single topology item spread over several lines (`.subckt … .ends`) is
  still a `TopologyError`. Duplicate `.include` detection compares the statement text.

**Deviations from this list:**

- **The D2 review gate was not held:** T3 was implemented right after D2, in one pass, at the
  maintainer's request to complete M6. D2 and decision 0007 are for review with the
  implementation.
- **An opaque-items check was added to verification** (step 3; decision 0007 item 8,
  architecture §7.6, m6-edits.md §3). While writing T10 it turned out that the signature does
  not cover opaque content, so a plan passed to `apply` could edit a `.control` block, drop an
  `.include` or add an `.if` block hiding an element without a `TopologyViolation`. Now the
  opaque items must be unchanged and in order, apart from added `.include` statements.
- `operations.py` was added to the layout of section 3.1, holding the plan builders that
  `api.py` exposes.
- `Edit` has an optional fourth field `slots` (the slot checks), and `SlotCheck` is public;
  `Netlist` gained `baseline`, `path` and `verify()`; `Batch` has `plan`.
- `tests/support/solvers.run_ngspice` takes an optional `cwd` (the include probe runs ngspice
  from another folder).
- `every_diagnostic.cir` (`document_basic`) gained two lines for `MODEL_TYPE_MISMATCH`, so that
  every code still occurs in the corpus; its manifest hash and expectations were updated.
- The API sketch in section 3.2 was reformatted by `ruff format` (ruff 0.17 formats Python
  blocks in Markdown; the committed file already failed `ruff format --check`). Whitespace and
  line breaks only.
- `m3-elements.md`, `m4-statements.md` and `m5-document.md` stay ACTIVE with a pointer to
  m6-edits.md, which holds what M6 adds (insertion rules, operations); nothing was folded or
  archived.
- Test files are named `test_edit_*.py`: test folders without `__init__.py` need unique
  basenames.

**Limitations:** see decision 0007 "Known limits": whole-line directive edits only; no removal
of parameters or models; no stimulus specs or `.meas` bodies; no string paths; a duplicate
`.include` spelled differently is not caught; what an included harness adds is not verified.
Two operations in one batch that each add the same new `.param` add it twice. Element keyword
case does not follow the file's own spelling (`AC` is written uppercase even after a
lowercase `dc`).

**Checks** (2026-10-31): `ruff check`, `ruff format --check`, `mypy --strict`, `lint-imports`
and `pytest` (1430 passed, 2 POSIX-only skips, coverage 98.7%) with `--require-solver ngspice`
(ngspice 47) on Windows. Fresh clone of the commit, `uv sync`, full suite with
`--require-solver ngspice`: 1430 passed, 2 skipped. Not archived (awaiting review).

## 10. Review round 1 (2026-10-31)

### 10.1 Outcome

The maintainer accepted the deviations of section 9 (other changes, formatting), the keyword
case, the treatment of ambiguous targets and duplicate includes, and asked for the changes
below, recorded as [decision 0007](../decisions/0007-edit-lifecycle-and-edit-semantics.md)
amendment 1. Principle: allow an operation that *may* leave topology unaffected, and keep
opaque contents a black box.

### 10.2 Required changes

[x] **R1 — Whole opaque items.** `directives.remove`/`replace` accept a top-level `.control`
or `.if` block or `.include`/`.lib` statement; `add`/`replace` accept a whole block or a
`.lib` statement (`.include` stays with `add_include`). The opaque check of verification now
rejects only an edit that cuts into an opaque item of the original text, and runs right after
the splice. Architecture §7.1–§7.3, §7.6, §7.8, §7.9 amended.

[x] **R2 — Model switch for R, C, L.** `set_model` adds a model name after the value when
there is none (not for `r=1k`, which takes no model); new `remove_value` removes the value of a
line that names a model (ngspice 47: a value overrides the geometry; solver test).

[x] **R3 — Empty `.model` parentheses.** `ModelStatement.open_paren_span`/`close_paren_span`
(the transformer records the tokens; no grammar change); `set_model_param` writes into `d()`.

[x] **R4 — Directive text over several lines.** `add`, `replace` and `set` take a sequence of
physical lines, joined with the terminator of the insertion point; a `str` with a line break is
an `EditError` that says to pass a list.

[x] **R5 — Docs and tests.** Decision 0007 amendment 1, architecture, m6-edits.md, m4-statements.md
(the new fields), editing.md recipes, CHANGELOG; unit, golden (input `review1_lf.cir`, five
cases: `model_switch`, `empty_parentheses`, `swap_include`, `control_block`, `continued_tran`),
negative (crafted cuts into a block or include; whole adds and removes allowed) and solver
tests (model switch 1.5 V → 2.0 V; a continued `.tran` with an added `.control` block runs).

### 10.3 Report (2026-10-31)

- The opaque check moved from step 3 to right after the splice (step 1), so a plan that cuts a
  block in half is reported as a cut, not as a parse error of the remains.
- `remove_value` keeps the separator before the value (`R2 out 0  rmod …`): deciding whether
  the gap is only blanks would mean scanning source text (P13); it stays a minimal diff.
- `directives.set` rejects opaque items like repeatable directives (they are not singletons).
- Limitations added: what a removed `.include`/`.lib` defined, and what an added `.if` block
  contains, is not verified (§7.8).
- Checks: ruff, ruff format, mypy --strict, lint-imports and pytest with `--require-solver
  ngspice` (1495 passed, 2 POSIX-only skips, coverage 98.8%). Status stays `READY FOR REVIEW`.
