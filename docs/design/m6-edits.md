# M6 design note — the edit layer

> **Status:** ACTIVE — written with M6 (D2 of [m6-tasks.md](./m6-tasks.md)); awaiting the
> maintainer's review together with the M6 implementation (the review before T3 that the task
> list asks for did not happen: see the M6 report). [Decision 0007](../decisions/0007-edit-lifecycle-and-edit-semantics.md)
> records why. Builds on [m3-elements.md](./m3-elements.md) (element sub-spans),
> [m4-statements.md](./m4-statements.md) (statement sub-spans) and [m5-document.md](./m5-document.md)
> (`Netlist`, `Lines`, scopes, signature), which stay ACTIVE as the references for node shapes.

## 1. Layering and lifecycle

- `document/` does not import `edit/` (import-linter). `netlistmod.edit.Netlist` subclasses
  the read-only `netlistmod.document.Netlist` and adds the edit methods (a facade by
  inheritance, not a protocol); `netlistmod.Netlist` is the editable class. The base class's
  constructors return `Self`, so `Netlist.load(...)` builds the editable class.
- Package layout (architecture §4): `plan.py` (`Edit`, `EditPlan`, `SlotCheck`, `apply_edits`),
  `conventions.py` (decision 0007 item 4), `placement.py` (`Placement`, `insertion_point`),
  `verify.py` (`apply_plan` and the checks), `operations.py` (one plan builder per operation)
  and `api.py` (`Netlist`, `Batch`, `ParamTable`, `DirectiveEditor`). `operations.py` is an
  addition to the layout of task 3.1: it keeps the plan builders apart from the classes that
  expose them.
- **Immutable and eager.** An edit method builds edits against the current text, applies them
  through `apply`, and returns a new `Netlist` that carries the original load's signature
  (`baseline`) and file path (`path`). A failing edit raises; the netlist is unchanged.
- **Batches.** `with nl.batch() as b: …` collects the edits of several operations, each
  computed against `nl`; on a clean exit they are applied as one plan (`b.result`). A failure
  in an operation or the verification leaves nothing applied. `b.plan` shows the edits so far.
- **Stale handles.** Operations that take a `Line` (or its item) look it up by identity in the
  netlist being edited; one from another netlist is an `EditError`.

## 2. API

`ScopePath` is a tuple of subcircuit names, `()` for the top level. Every element operation
takes `scope: ScopePath = ()` and `in_definition: bool = False`; a non-empty `scope` without
`in_definition=True` is an `EditError` (P11). Elements are found in their own scope only; an
unknown scope, an unknown designator and a repeated designator are `EditError`s. On a
`Netlist` every operation returns a new `Netlist`; on a `Batch` it returns `None`.

### Element operations

| Method | Applies to | Slot edited (sub-span) | Insertion when absent | Errors (`EditError` unless noted) |
|---|---|---|---|---|
| `set_value(d, value)` | R, C, L | `value.span` (for `r=1k`: `1k`) | after the last node: ` value` | D, X: no value slot; K: use `set_coupling` |
| | V, I | `dc.span` | — (replace only; never adds `DC`) | no DC value: use `set_dc` |
| `set_formula(d, expr)` | as `set_value` | as `set_value`, text `{expr}` | as `set_value` | as `set_value` |
| `set_param(d, name, value)` | R, C, L, D | `params[i].value.span`; a value keyword (`r`, `resistance`, `c`, `capacitance`, `l`, `inductance`) edits `value.span` when the value is written that way | after the last field: ` name=value` | X: use `set_instance_param`; V, I, K: no parameters; value keyword on a positional value: use `set_value`; repeated name |
| `set_model(d, model, allow_external=False)` | R, C, L, D with a model | `model.span` | — | model type not allowed for the letter (table in `document/model-types.json`); model not visible; not visible and `allow_external` with no `.include`/`.lib` in scope; no model to replace |
| `set_dc(d, value)` | V, I | `dc.span` | after the last node: ` DC value` | not a source |
| `set_ac(d, mag, phase=None)` | V, I | `ac.magnitude.span`, and `ac.phase.span` when `phase` is given | after the DC part (or nodes): ` AC mag [phase]`; a missing phase after the magnitude: ` phase` | not a source |
| `set_coupling(d, value)` | K | `value.span` | — | not a K line |
| `set_instance_param(d, name, value)` | X | `params[i].value.span` | after the last field: ` name=value` | not an X line; repeated name |

"The last field" is the field ending last among the nodes, value, model, parameters, flags,
subcircuit name and AC part, on whichever physical line it is (decision 0007 item 5). The text
goes right after it, so a trailing comment or a continuation stays after the new field.

### Statement operations

| Method | Edit | Insertion | Errors |
|---|---|---|---|
| `params.set(name, value, scope=(), in_definition=False, placement=None)` | the value of the **last** assignment of `name` in `scope` (defaults count) | `.param name=value` + terminator at `placement` (default `AFTER_LAST_PARAM`) | scope rules; a bare expression does not parse (the `ParseError` suggests braces) |
| `set_model_param(model, name, value, scope=(), in_definition=False)` | the value of parameter `name` of the first `.model model` in `scope` | after the last parameter (inside `( … )`), or after the type: ` name=value` | no such model in `scope`; repeated parameter; empty parentheses |

`params` is still the read-only mapping of top-level parameters (a `ParamTable`, which is a
`Mapping`); `set` is its only addition.

### Directive operations (`netlist.directives`, a `DirectiveEditor`)

| Method | Edit | Errors |
|---|---|---|
| `add(text, placement=BEFORE_END)` | insert `text` + terminator | text classification below; placement errors |
| `replace(line, text)` | replace the whole `line.span` with `text` + the line's terminator | `line` must be a top-level typed or unknown directive |
| `remove(line)` | delete `line.span` | as `replace` |
| `set(text)` | singleton kinds (`.tran`, `.ac`, `.dc`, `.op`, `.temp`): `replace` the one line of the kind, or `add` before `.end` | two or more lines of the kind; a repeatable kind |
| `add_include(path, placement=AFTER_TITLE)` (on the netlist) | insert `.include "path"` + terminator | an include with the same statement text; a path that does not parse (a `"` or a line break) |

**Text classification.** The text is parsed as the only line of a probe netlist
(`probe` / text / `.end`) with the netlist's dialect and `rkm`. It must be exactly one physical
line holding a `Directive` or an `UnknownDirective`. An element, `.subckt`, `.global`,
`.include`/`.lib` or opaque block is a `TopologyError`; a `.param`, `.model`, `.title`, comment,
blank, several lines or a syntax error is an `EditError`.

**Line targets** (`replace`, `remove`): an element, definition, `.global`, `.include`/`.lib` or
opaque block is a `TopologyError`; a `.param`, `.model`, title, `.end`, blank or comment line,
or a line inside a definition, is an `EditError`.

### Placement

| Placement | Top level | Inside a definition (`.param` only) |
|---|---|---|
| `AFTER_TITLE` | after the title line | `EditError` |
| `AFTER_LAST_PARAM` | after the last top-level `.param`, else after the title | after the body's last `.param`, else after the header |
| `BEFORE_END` | before the `.end` line | `EditError` |
| `before(line)` | before `line` (not the title) | before a line of that body |
| `after(line)` | after `line` (not `.end`) | after a line of that body |

An anchor that is not a line of the target sequence (another netlist, another scope) is an
`EditError`. All points are physical-line boundaries; nothing is inserted after `.end`.

### Netlist-only members

| Member | Notes |
|---|---|
| `batch() -> Batch` | section 1 |
| `apply(plan: EditPlan \| Iterable[Edit]) -> Netlist` | full verification; an empty plan returns the netlist itself |
| `verify() -> None` | re-parse and compare with the baseline |
| `save(path=None) -> None` | `verify()`, then `SourceText.write` (atomic, original encoding and BOM); `path` defaults to the loaded file; `EditError` without either |
| `baseline: TopologySignature` | the signature of the original load |
| `path: Path \| None` | the loaded file |

### Plans

`Edit(span, text, reason="", slots=())`; `SlotCheck(kinds, description, start=0, end=None)`
names the part `text[start:end]` that must re-parse as a node of one of `kinds`.
`EditPlan(edits)` keeps submission order; `ordered()` sorts by start, puts an insertion before
a replacement at the same offset, keeps the order of insertions at one point, and raises
`EditError` for overlapping edits (two replacements sharing a character, or an insertion
strictly inside a replacement). `apply_edits(text, plan) -> str` splices; it never mutates.

## 3. Verification

`verify.apply_plan` runs, in order (decision 0007 item 8):

1. the splice (`apply_edits`; overlap and out-of-range spans are `EditError`s);
2. the re-parse with the same dialect and `rkm`; a `ParseError` or `UnsupportedConstruct` is
   wrapped in an `EditError` (its message names the operations and includes the parse error,
   which for RKM text names `rkm=True`);
3. the signature against the baseline: `TopologyViolation` naming the first differing entry,
   or the first added or removed one; then the opaque items (`.control` and `.if` blocks,
   `.include` and `.lib` statements, with their text) against those of the text the plan was
   applied to: the same, in order, apart from added `.include` statements
   (`TopologyViolation`). The signature excludes opaque content, so without this check a plan
   passed to `apply` could edit a `.control` block, drop an `.include` or add an `.if` block
   that hides an element (found while writing T10);
4. the outside-text check: each stretch between edits, at its shifted position, equals the
   original (`TopologyViolation` otherwise); always on;
5. the slot checks: a node of the expected kind with exactly the slot's span must exist in the
   new parse, otherwise `EditError` ("does not re-parse as a value").

Directive text is classified (section 2) **before** the plan is applied, so a line that would
change the topology is reported as the `TopologyError` of the misused API rather than a
`TopologyViolation`.

## 4. Settled points (T3–T5)

| Point | Choice | Basis |
|---|---|---|
| `set_value` on a source with `dc_keyword=False` | replaces the value as written; without a DC value, `EditError` (use `set_dc`) | task T3 "replace only; never add `DC`" |
| `set_value` on a `K` line | `EditError` pointing to `set_coupling` | task T3 |
| `set_param` with a value keyword name | edits the value if written `r=…`, else `EditError` (use `set_value`) | a second `r=` would be read as a parameter next to a positional value |
| RKM text with `rkm=False` | `EditError` wrapping the `ParseError`, whose message names `rkm=True` | decision 0004 |
| `params.set` with a bare expression | `EditError` wrapping the `ParseError`, which says to write braces or single quotes | decision 0005 |
| String values | written as given; the caller writes the quotes | decision 18 (no validation or rewriting of values) |
| `DC`/`AC` keyword case | uppercase, as the manual writes them; dot-commands lowercase | decision 0007 item 4; behaviour table |
| Repeated designator, instance or model parameter | `EditError` (no single target) | P5: an edit that is not provably the intended one raises |
| `set_model` without a current model | `EditError` (adding a model is not offered) | §7.2 sets "an element's model name"; the type rule compares with the current one |
| `.model` with empty parentheses | `EditError` for an added parameter | the node has no span for `(`; P13 forbids finding it in the text |
| Directive text over several physical lines | `EditError` | decision 0007 item 7 ("exactly one line"); keeps inserted line endings consistent |
| Duplicate `.include` | identical statement text (`raw`) | the path is not parsed out of an opaque statement |

## 5. Coverage

### §7.2 allowed operations → methods

| §7.2 operation | Method | Tests |
|---|---|---|
| set a numeric value / replace it with a formula | `set_value`, `set_formula` | `tests/edits/test_edit_elements.py`, golden cases |
| set or add an instance parameter | `set_param`, `set_instance_param` | `test_edit_elements.py`, golden |
| set an element's model name | `set_model` | `test_edit_elements.py`, golden |
| add or set a `.param`; edit `.model` parameters | `params.set`, `set_model_param` | `test_edit_statements.py`, golden |
| edit source stimulus specs (phase 1: DC, AC) | `set_dc`, `set_ac` | `test_edit_elements.py`, golden |
| `K` coupling value | `set_coupling` | `test_edit_elements.py`, golden |
| add, replace or remove directives with placement | `directives.add/replace/remove/set`, `Placement` | `test_edit_directives.py`, golden |
| add an `.include` of a harness file | `add_include` | `test_edit_directives.py`, golden |

### §7.3 forbidden operations → no API / error

| §7.3 operation | How it is prevented | Negative test (`tests/edits/test_edit_negative.py`) |
|---|---|---|
| add, remove or reorder elements | no API; `apply(plan)` → `TopologyViolation`; `directives.add/remove/replace` of an element → `TopologyError` | `test_crafted_plans_that_change_topology_raise`, `test_directive_api_rejects_topology` |
| change a node | no API; crafted plan → `TopologyViolation` | crafted plans |
| change an element type or designator | no API; crafted plan → `TopologyViolation` | crafted plans |
| rename a net | no API; crafted plan → `TopologyViolation` | crafted plans |
| add or remove `.subckt` definitions, change their ports | no API; crafted plan → `TopologyViolation`; `directives.remove` of a definition → `TopologyError` | crafted plans, `test_directive_api_rejects_topology` |
| edit opaque blocks | no API; crafted plan → `TopologyViolation` (opaque check); `directives.remove/replace` → `TopologyError` | crafted plans, `test_directive_api_rejects_topology` |
| remove an `.include` or `.global` | `directives.remove` → `TopologyError`; crafted plan → `TopologyViolation` | crafted plans, `test_directive_api_rejects_topology` |

Other tests: `test_edit_plan.py` (T1, with a Hypothesis reference splice), `test_edit_verify.py`
(T2), `test_edit_lifecycle.py` (T6), `test_edit_golden.py` (T8; corpus
`tests/corpus/ngspice/edits_golden/`), `test_edit_properties.py` (T9) and
`tests/solver/test_ngspice_solver_edits.py` (T11).

## 6. `MODEL_TYPE_MISMATCH`

A warning at the model name of an R, C, L or D line whose model resolves (decision 0006 rules)
to a `.model` with a type not allowed for the element: R → `R`, C → `C`, L → `L`, D → `D`,
compared case-insensitively ([ngspice-manual] §2.5 Table 2.3; §3.3.2, §3.3.7, §3.3.10, §7.2).
The table is data, `src/netlistmod/document/model-types.json`, read by
`netlistmod.document.models`; `set_model` uses the same table. An unresolved model gives the
`UNRESOLVED_MODEL` diagnostic instead. Tests: `tests/document/test_diagnostics.py`, and the
`every_diagnostic.cir` fixture of `document_basic` (lines 26–27).
