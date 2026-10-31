# 0007 — Edit lifecycle and edit semantics

- **Status:** proposed
- **Date:** 2026-10-31
- **Context:** M6 builds the edit layer (architecture §3 layers [4] and [5], §7). Architecture
  §21 left unresolved question 1 (the edit lifecycle) and the `set_model` half of question 2
  (models that only an `.include` could define) open for M6, and deferred the text conventions
  of inserted lines, placement semantics, directive and `.param` matching, and the edit argument
  of hierarchical addressing. Decision 0006 deferred `MODEL_TYPE_MISMATCH`. The maintainer
  accepted the recommendations of [m6-tasks.md](../design/m6-tasks.md) section 2 on 2026-10-31;
  this record states them and the points settled while implementing (T3–T5). ngspice 47 was
  probed for the directive rules ([m6-tasks.md](../design/m6-tasks.md) section 7, re-recorded in
  `tests/solver/test_ngspice_solver_edits.py`). API and slot details:
  [m6-edits.md](../design/m6-edits.md).
- **Decision:**
  1. **Lifecycle: immutable and eager** (§21 question 1). Each edit method returns a **new**
     `Netlist`; the old one is unchanged. The call builds an `EditPlan` against the current
     text, applies it, re-parses and verifies (item 8) before returning, so a failing edit
     raises and nothing changes.
     - Read-back works at once: the returned netlist is fully indexed.
     - Nodes and `Line`s belong to the netlist they came from; passing one from another netlist
       to an edit raises `EditError`. Callers address by designator and scope.
     - `netlist.batch()` collects several operations and applies them as **one** plan with one
       re-parse and verification; it is all or nothing.
     - Two edits to the same span in one plan are an `EditError` (never last-wins, §7.5); two
       insertions at the same point keep their submission order.
     - Every derived netlist carries the topology signature of the **original** load, and
       verification always compares against it (§7.6).
  2. **Edits inside a subcircuit definition** (§7.4, P11). An edit is addressed by designator
     and definition scope (`scope=("amp",)`, decision 0006). A non-empty `scope` also requires
     `in_definition=True`, otherwise `EditError` saying that the edit would change every
     instance. The per-instance alternative is `set_instance_param` on the `X` line. The tuple
     stays the only addressing; there is no string path form.
  3. **`set_model`** (§7.2; §21 question 2). The new model is resolved in the element's scope
     chain (decision 0006). When it resolves, its type must be the one allowed for the element
     letter: R → `R`, C → `C`, L → `L`, D → `D` (manual §2.5, Table 2.3; case-insensitive);
     otherwise `EditError`. When it does not resolve, `EditError`, unless the caller passes
     `allow_external=True` **and** a searched scope has an opaque `.include`/`.lib`: then the
     edit is made and the new netlist carries the usual `UNRESOLVED_MODEL` info diagnostic.
     `set_model` replaces an existing model name; adding a model to an element that has none is
     an `EditError`. At load, the new warning `MODEL_TYPE_MISMATCH` marks an element whose
     resolved model has a type not allowed for its letter (the table is data,
     `document/model-types.json`).
  4. **Text conventions for inserted text** (§21 deferred).
     - An inserted line ends with the terminator of the physical line just before the insertion
       point (of the first line when inserting at the start). Mixed endings stay locally
       consistent and are never normalised (P3).
     - Placements never insert after `.end`, so a missing final newline is never touched.
     - Dot-command keywords are lowercase (`.param`, `.include`); one blank between fields;
       `name=value` without blanks; one assignment per new `.param` line; no indentation, also
       in a subcircuit body. The element keywords `DC` and `AC` are written uppercase, as the
       manual writes them (§4.1).
     - A value or formula replaces exactly the slot's sub-span (for `r=1k`, only `1k`).
       `set_formula("Rx*2")` writes `{Rx*2}`; `set_value` and every other value argument take
       the text as given (a string value is quoted by the caller).
  5. **Where added fields go.** A new instance parameter goes after the element's last field
     (its last parameter, flag, model, value or node, on whichever physical line that is), as
     one blank plus `name=value`, before any trailing comment or continuation. A value where none
     exists (`R1 a b rmod`) goes after the last node. A new `.model` parameter goes after the
     last parameter, inside the parentheses when there are any; a model written with empty
     parentheses has no parameter to anchor on and is an `EditError`. `set_ac` without an `AC`
     part appends `AC mag [phase]` after the DC part (or the nodes); with one, it replaces the
     magnitude, and the phase if given (inserting it after the magnitude when absent). Removing
     an instance or model parameter is not offered.
  6. **Placement.** `Placement.AFTER_TITLE`, `Placement.AFTER_LAST_PARAM` (after the title when
     there is no top-level `.param`), `Placement.BEFORE_END`, `Placement.before(line)` and
     `Placement.after(line)`. Defaults: `.param` → `AFTER_LAST_PARAM`; directives →
     `BEFORE_END`; `.include` → `AFTER_TITLE`. Directives and `.include` are top-level only. A
     `.param` added inside a definition goes after the definition's last body `.param`, else at
     the start of the body; an anchor must then be a line of that body. An anchor from another
     netlist, before the title, after `.end`, or in the wrong scope is an `EditError`.
  7. **Matching and upsert.**
     - `params.set(name, value, scope=…)`: when the name is assigned in that scope (folded;
       defaults count), the value of the **effective** (last) assignment is replaced; otherwise a
       `.param` line is added. Earlier repeats are left as they are.
     - `directives.set(text)` for the singleton kinds `.tran`, `.ac`, `.dc`, `.op` and `.temp`
       replaces the one line of that kind or adds one; with two or more, `EditError`. For the
       repeatable kinds (`.options`, `.ic`, `.nodeset`, `.save`, `.meas`, unknown dot-commands),
       `set` is an `EditError`.
     - `add`, `replace` and `set` accept text that parses as exactly **one** physical line holding
       a typed directive or an unknown dot-command. An element, `.subckt`, `.global`,
       `.include`/`.lib` or opaque block is a `TopologyError`; several lines, a `.param`, `.model`,
       `.title` or `.end`, a different kind (for `set`) or a syntax error is an `EditError`. The
       text is classified by parsing it in a probe netlist before the plan is applied.
     - `remove(line)` and `replace(line, …)` accept typed and unknown directives only. An element,
       definition, `.global`, `.include`/`.lib` or opaque block is a `TopologyError`; any other
       line (`.param`, `.model`, title, `.end`, blank, comment) is an `EditError`.
     - A name that is repeated where an edit needs one target (a designator, an instance or
       `.model` parameter) is an `EditError`.
  8. **Verification** (§7.6; amends decision 18). Every apply runs, in order: (1) the splice
     (§7.5 rules); (2) a re-parse with the same dialect and `rkm` (a failure is an `EditError`
     carrying the `ParseError`); (3) the signature compared with the load baseline
     (`TopologyViolation`, naming the first differing entry), and the opaque items
     (`.control`/`.if` blocks, `.include`/`.lib` statements) compared with those before
     the plan: unchanged and in order, apart from added `.include` statements
     (`TopologyViolation`; the signature does not cover opaque content, so a plan passed
     to `apply` could otherwise edit a block or drop an include); (4) a check that every character
     outside the edited spans is identical, always on; (5) a **slot check**: each edited slot
     re-parses as a node of the expected kind whose span is exactly the replacement. Step 5
     verifies that an edit landed where intended (`set_value("1k 2k")` would add a model `2k`); it
     does not validate the caller's value, which stays the caller's responsibility.
     `save(path=None)` re-verifies, encodes in the original encoding (`EncodingError` before any
     write) and writes atomically. An unedited netlist saves its original bytes (P3).
  9. **`add_include(path)`** (§7.9) writes `.include "path"` at `AFTER_TITLE` by default. The
     path is written as given and never read. Adding an include whose statement text equals an
     existing one is an `EditError`. What the included file adds is outside the topology check
     (§7.8, §7.9); ngspice resolves a relative path from the netlist file's folder.
  10. **Low-level plans.** `Edit(span, text, reason)`, `EditPlan` and `apply_edits(text, plan)`
      are public. A plan reaches a `Netlist` only through `netlist.apply(plan)`, which runs the
      same verification, so the restricted API cannot be bypassed.
  11. **Layering.** `document/` does not import `edit/`. `netlistmod.edit.Netlist` subclasses
      the read-only `netlistmod.document.Netlist` and adds the edit methods; `netlistmod.Netlist`
      is the editable class.
- **Consequences:**
  - Architecture amendments: §7.2 (placement, upsert, `set_model`), §7.4 (`in_definition`), §7.5
    (batches), §7.6 (the outside-text check always on, the slot check), §16 (points to the design
    note), §17 (`MODEL_TYPE_MISMATCH`), §19 decision 18 (clarified), §21 (question 1, the
    `set_model` half of question 2, text conventions, matching and upsert, the edit part of
    hierarchical addressing and placement resolved).
  - Edits are never staged; each call re-parses the whole netlist (§3: parsing is cheap for the
    circuits in scope). A batch is the way to make many edits with one re-parse.
  - Known limits: argument-level directive edits, removing parameters or models, editing
    stimulus specs and `.meas` bodies, and string path addressing are out of scope; duplicate
    `.include` detection compares statement text, so the same path spelled differently is not
    caught; what an included harness adds is not verified.
- **Amendment 1 (2026-10-31, M6 review round 1, maintainer).** Principle: allow an operation
  that *may* leave topology unaffected; keep opaque contents a black box.
  1. **Whole opaque items** (amends items 7 and 8, architecture §7.1–§7.3, §7.6, §7.8, §7.9).
     A `.control` or `.if` block or an `.include`/`.lib` statement may be added, removed or
     replaced whole: `directives.remove` and `directives.replace` accept such a top-level line,
     and `directives.add`/`replace` accept a whole block or a `.lib` statement (an `.include`
     still goes through `add_include`). Verification step 3's comparison of opaque items is
     replaced by a check, run right after the splice, that no edit cuts into an opaque item of
     the original text (`TopologyViolation`): an edit either leaves it alone or covers it
     whole. What a removed include defined, or what an added `.if` block contains, is not
     verified (§7.8); for example, swapping the `.include` that defines a behavioural
     subcircuit is now possible.
  2. **Directive text over several lines** (amends item 7). `add`, `replace` and `set` take one
     physical line or a sequence of physical lines (`[".tran 1u 10m", "+ 0 1u"]`), joined with
     the line ending of the insertion point (item 4). The lines must hold exactly one item; a
     single string with a line break is an `EditError` that says to pass a list.
  3. **Model name and value of R, C, L** (amends items 3 and 5). `set_model` adds a model name
     right after the value of an R, C or L line that has none (same resolution and type rules;
     a value written `r=1k` takes no model). `remove_value` removes the value of an R, C or L
     line that names a model, so the model's geometry applies: ngspice 47 uses a given value
     over the geometry (`R2 out 0 1k rmod l=20u w=1u` reads 1k, without `1k` it reads
     rsh·l/w). Only the value text is removed; the separator before it stays.
  4. **Empty `.model` parentheses** (amends item 5). `ModelStatement` records
     `open_paren_span` and `close_paren_span` (the `(` and `)` tokens; `None` without
     parentheses), so `set_model_param` adds `name=value` right after `(` of `d()`. A model-layer
     field, not a grammar change.
