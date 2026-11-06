# The edit layer

> **Status:** ACTIVE — living reference, kept current with the code; began as the M6 design note (D2 of
> [m6-tasks.md](./archive/phase-1/m6-tasks.md)). [Decision 0007](../decisions/0007-edit-lifecycle-and-edit-semantics.md)
> and [decision 0009](../decisions/0009-ltspice-dialect.md) record why. Builds on
> [elements.md](./elements.md) (element sub-spans), [statements.md](./statements.md) (statement
> sub-spans) and [document-layer.md](./document-layer.md) (`Netlist`, `Lines`, scopes, signature).

## 1. Layering and lifecycle

- `document/` does not import `edit/` (import-linter). `netlistmod.edit.Netlist` subclasses
  the read-only `netlistmod.document.Netlist` and adds the edit methods (a facade by
  inheritance, not a protocol); `netlistmod.Netlist` is the editable class. The base class's
  constructors return `Self`, so `Netlist.load(...)` builds the editable class.
- Package layout (architecture §4): `plan.py` (`Edit`, `EditPlan`, `SlotCheck`, `apply_edits`),
  `conventions.py` (decision 0007 item 4), `placement.py` (`Placement`, `insertion_point`),
  `verify.py` (`apply_plan` and the checks), `operations.py` (one plan builder per operation, kept by family in `_ops_*.py` since M13 and imported from `operations.py`)
  and `api.py` (`Netlist`, `Batch`, `ParamTable`, `DirectiveEditor`). `operations.py` is an
  addition to the layout of task 3.1: it keeps the plan builders apart from the classes that
  expose them.
- **Immutable and eager.** An edit method builds edits against the current text, applies them
  through `apply`, and returns a new `Netlist` that carries the original load's signature
  (`baseline`) and file path (`path`). A failing edit raises; the netlist is unchanged.
- **Batches.** `with nl.batch() as b: …` collects the edits of several operations, each
  computed against `nl`; on a clean exit they are applied as one plan (`b.result`). A failure
  in an operation or the verification leaves nothing applied. `b.plan` shows the edits so far.
  Because each operation sees `nl` and not the batch so far, a second upsert of one target is an
  `EditError` naming the target, raised when it is submitted, whether or not the target exists
  yet (decision 0010 item 5). Nothing is merged and last-wins does not apply. The key is the
  operation family, the scope and the folded target: element and parameter name (`set_param`,
  `set_instance_param`), model and parameter name (`set_model_param`), parameter name
  (`params.set`), element (`set_dc`, `set_ac`), directive kind or `.step` quantity
  (`directives.set`), and include path as written (`add_include`). Different new parameters on
  one line stay valid, and so does one name in two scopes. `set_value`, `set_formula` and
  `set_model` are not keyed: a repeat fails when the plan is applied, as overlapping edits or a
  result that does not parse.
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
| | E, F, G, H | `value.span` (the gain) | — (the gain is mandatory) | — |
| | V, I | `dc.span` | — (replace only; never adds `DC`) | no DC value: use `set_dc` |
| `set_formula(d, expr)` | as `set_value` | as `set_value`, text `{expr}` | as `set_value` | as `set_value` |
| `set_param(d, name, value)` | R, C, L, D, Q, M, J, Z; `m=` on an ngspice F or G | `params[i].value.span`; `area` on J and Z edits or adds the positional `area.span` (right after the model) unless the line writes `area=`, and on an ngspice Q it is a parameter; a value keyword (`r`, `resistance`, `c`, `capacitance`, `l`, `inductance`) edits `value.span` when the value is written that way | after the last field: ` name=value` | X: use `set_instance_param`; V, I, K: no parameters; value keyword on a positional value: use `set_value`; repeated name |
| `set_model(d, model, allow_external=False)` | R, C, L, D, Q, M, J, Z, S, W | `model.span` | R, C, L without a model: after the value: ` model` | model type not allowed for the letter (table in `document/model-types.json`); model not visible; not visible and `allow_external` with no `.include`/`.lib` in scope; a value written `r=1k` (that form takes no model) |
| `set_switch_state(d, state)` | S, W | `flags[0].span`, with an LTspice value (`off=1`) | after the model: ` on` or ` off`; `None` removes the state and the gap before it | not a switch; a state other than `on`, `off` or `None` (decision 0015 item 10) |
| `remove_value(d)` | R, C, L with a model | deletes `value.span` (the separator before it stays) | — | no value; no model (the line would have neither); not R, C or L |
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
| `set_model_param(model, name, value, scope=(), in_definition=False)` | the value of parameter `name` of the first `.model model` in `scope` | after the last parameter (inside `( … )`); in empty parentheses right after `open_paren_span`: `name=value`; without parentheses after the type: ` name=value` | no such model in `scope`; repeated parameter |

`params` is still the read-only mapping of top-level parameters (a `ParamTable`, which is a
`Mapping`); `set` is its only addition.

### Directive operations (`netlist.directives`, a `DirectiveEditor`)

| Method | Edit | Errors |
|---|---|---|
| `add(text, placement=BEFORE_END)` | insert `text` + terminator | text classification below; placement errors |
| `replace(line, text)` | replace the whole `line.span` with `text` + the line's terminator | line targets below |
| `remove(line)` | delete `line.span` | as `replace` |
| `set(text)` | singleton kinds (`.tran`, `.ac`, `.dc`, `.op`, `.temp`): `replace` the one line of the kind, or `add` before `.end`. LTspice `.step`: the same, by swept quantity | two or more lines of the kind (or quantity); a repeatable kind |
| `add_include(path, placement=AFTER_TITLE)` (on the netlist) | insert `.include "path"` + terminator | an include with the same statement text; a path that does not parse (a `"` or a line break) |

**Text.** `text` is one physical line (a `str`) or a sequence of physical lines (a continued
statement or a block, `[".tran 1u 10m", "+ 0 1u"]`); written, the lines are joined with the
terminator of the insertion point (or of the replaced line). It is parsed as the body of a probe
netlist (`probe` / lines / `.end`) with the netlist's dialect and `rkm`, and must be exactly one
item on exactly those lines: a `Directive`, an `UnknownDirective`, a whole `.control` or `.if`
block (`OpaqueBlock`) or a `.lib` statement. An element, `.subckt` or `.global` is a
`TopologyError`; an `.include` is an `EditError` pointing to `add_include`; a `.param`,
`.model`, `.title`, comment, blank, several items, a syntax error, or a `str` holding a line
break (the message says to pass a list) is an `EditError`. `set` accepts only the singleton
kinds.

**Line targets** (`replace`, `remove`): a top-level directive, unknown dot-command, `.control`
or `.if` block, or `.include`/`.lib` statement, taken whole. An element, definition or `.global`
is a `TopologyError`; a `.param`, `.model`, title, `.end`, blank or comment line, or a line
inside a definition, is an `EditError`. Removing an include removes whatever it defined from
the solver's view; that is not verified (§7.8).

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

1. the splice (`apply_edits`; overlap and out-of-range spans are `EditError`s), then the
   opaque check: no edit may cut into an opaque item (`.control`/`.if` block,
   `.include`/`.lib` statement) of the original text. An edit leaves it alone or covers it
   whole; otherwise `TopologyViolation`. The signature excludes opaque content, so without this
   check a plan passed to `apply` could edit inside a block (found while writing T10; narrowed
   to partial edits in review round 1). It runs before the re-parse, so a cut block is reported
   as such even when the remains do not parse;
2. the re-parse with the same dialect and `rkm`; a `ParseError` or `UnsupportedConstruct` is
   wrapped in an `EditError` (its message names the operations and includes the parse error,
   which for RKM text names `rkm=True`);
3. the signature against the baseline: `TopologyViolation` naming the first differing entry,
   or the first added or removed one;
4. the outside-text check: each stretch between edits, at its shifted position, equals the
   original (`TopologyViolation` otherwise); always on;
5. the slot checks: a node of the expected kind with exactly the slot's span must exist in the
   new parse, otherwise `EditError` ("does not re-parse as a value").

Directive text is classified (section 2) **before** the plan is applied, so a line that would
change the topology is reported as the `TopologyError` of the misused API rather than a
`TopologyViolation`.

All errors derive from `SpiceNetlistError`. `EditError`, `TopologyError` and `TopologyViolation` are as above; `ParseError` and `UnsupportedConstruct` come from the parse; `EncodingError` comes from `save` when the text does not fit the file's encoding. The file is then left unchanged.

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
| `set_model` without a current model | adds the name after the value (R, C, L); `remove_value` drops the value | review round 1: switching to the semiconductor form, where a value overrides the geometry (ngspice 47) |
| `.model` with empty parentheses | the parameter goes right after `(`, from the new `open_paren_span` | review round 1; the span comes from the parse (P13) |
| Directive text over several physical lines | a sequence of lines, joined with the file's terminator; a `str` with a line break is an `EditError` | review round 1; the library never splits the caller's text, so line endings stay consistent |
| Duplicate `.include` | identical statement text (`raw`) | the path is not parsed out of an opaque statement |

## 5. Coverage

### §7.2 allowed operations → methods

| §7.2 operation | Method | Tests |
|---|---|---|
| set a numeric value / replace it with a formula | `set_value`, `set_formula` | `tests/edits/test_edit_elements.py`, golden cases |
| set or add an instance parameter | `set_param`, `set_instance_param` | `test_edit_elements.py`, golden |
| set an element's model name | `set_model` | `test_edit_elements.py`, golden |
| add or set a `.param`; edit `.model` parameters | `params.set`, `set_model_param` | `test_edit_statements.py`, golden |
| edit source stimulus specs | `set_dc`, `set_ac`, `set_stimulus`, `set_stimulus_arg`, `remove_stimulus` | `test_edit_elements.py`, `test_edit_stimulus.py`, golden |
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
| edit the contents of an opaque item | no API; a crafted plan that cuts into one → `TopologyViolation` (opaque check). Whole items may be added, removed or replaced (review round 1) | crafted plans, `test_whole_opaque_items_may_be_added_or_removed` |
| remove `.global` | `directives.remove` → `TopologyError`; crafted plan → `TopologyViolation` | crafted plans, `test_directive_api_rejects_topology` |

Other tests: `test_edit_plan.py` (T1, with a Hypothesis reference splice), `test_edit_verify.py`
(T2), `test_edit_lifecycle.py` (T6), `test_edit_golden.py` (T8; corpus
`tests/corpus/ngspice/edits_golden/`), `test_edit_properties.py` (T9) and
`tests/solver/test_ngspice_solver_edits.py` (T11).

## 6. `MODEL_TYPE_MISMATCH`

A warning at the model name of an R, C, L, D, Q, M, J, Z, S or W line whose model resolves
(decision 0006 rules) to a `.model` with a type not allowed for the element: R → `R`, C → `C`,
L → `L`, D → `D`, Q → `NPN`/`PNP`, M → `NMOS`/`PMOS`/`VDMOS`, J → `NJF`/`PJF`, Z → `NMF`/`PMF`,
S → `SW`, W → `CSW` (decision 0015 item 8), compared
case-insensitively ([ngspice-manual] §2.5 Table 2.3; §3.3.2, §3.3.7, §3.3.10, §7.2 to §7.7). On
LTspice Z also takes `NIGBT` and `PIGBT` (decision 0014 item 8). The table is data,
`src/netlistmod/document/model-types.json`, with a section per dialect, read by
`netlistmod.document.models`; `set_model` uses the same table. An unresolved model gives the
`UNRESOLVED_MODEL` diagnostic instead. Tests: `tests/document/test_diagnostics.py`, and the
`every_diagnostic.cir` fixture of `document_basic` (lines 26–27).

## 7. LTspice

The conventions, verification and placement are the same (decision 0009 item 17). The operations differ only where the dialect does:

- `set_param` also edits V and I parameters, the area of a D or Q line (positional, or written `area=`), and a flag's value in place (`off` becomes `off=1`). An `area` on an M line is an `EditError`: LTspice's M has no area.
- `set_model_param` after a bare `pchan` or `nchan` adds the parameter after the flag, as on ngspice.
- `set_model` and `remove_value` on an R, C or L line are an `EditError`: LTspice has no such model.
- `rkm=True` is a `ValueError`; embedded decimals need no option.
- `set_param` on E, F, G, H, S or W is an `EditError`: none of them takes a parameter (decision 0015 item 7).
- `set_stimulus` puts a new function before `Rser` and `Cpar`, after the DC and AC parts. Those parameters and the trigger parameters are the line's, so they stay when the function changes. A `set_stimulus_arg` name finds them too.
- `directives.add` and `set` parse their text with the LTspice grammar, so the blocks `.control` and `.if` are refused. A whole `.lib` block is accepted on both dialects (decision 0012).

`tests/edits` runs on both dialects, with `tests/support/dialects.py` marking the cases only one dialect reads.
