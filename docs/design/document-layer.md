# The read-only document layer

> **Status:** ACTIVE — living reference, kept current with the code; began as the M5 design note (D2 of
> [m5-tasks.md](./archive/phase-1/m5-tasks.md)). [Decision 0006](../decisions/0006-document-layer-names-scope-and-diagnostics.md)
> and [decision 0009](../decisions/0009-ltspice-dialect.md) record why. Rules:
> [ngspice names](../grammars/ngspice/names.md), [ngspice scoping](../grammars/ngspice/scoping.md),
> [LTspice names](../grammars/ltspice/names.md), [LTspice scoping](../grammars/ltspice/scoping.md).
> The edit layer ([edit-layer.md](./edit-layer.md)) extends this `Netlist`.

## 1. Public API

Everything below is exported from `netlistmod`; import it from there (submodules such as
`netlistmod.document` are internal). Nothing is mutable.
`ScopePath = tuple[str, ...]`: folded subcircuit names from the top level, `()` for the top level;
every `scope=` argument is keyword-only and accepts any case.
`Dialect` is a `StrEnum` (`Dialect.NGSPICE`, `Dialect.LTSPICE`): `str(Dialect.NGSPICE)` is
`"ngspice"`. `Dialect.display_name` is the conventional spelling (`"ngspice"`, `"LTspice"`), and
`Dialect.from_name(name)` accepts a value or a member name in any case, with blanks around it
(`ValueError` otherwise).

### `Netlist`

| Member | Signature / type | Notes |
|---|---|---|
| `load` | `(path, *, dialect, rkm=False, fallback_encodings=DEFAULT_FALLBACKS) -> Netlist` | bytes, no newline translation |
| `from_text` | `(text, *, dialect, rkm=False) -> Netlist` | UTF-8, no BOM; `rkm=True` with `Dialect.LTSPICE` is a `ValueError` |
| `from_source` | `(source: SourceText, *, dialect, rkm=False) -> Netlist` | |
| `source`, `text`, `dialect`, `rkm` | properties | the source exactly as read (P1); `SourceText(text, encoding, bom)` |
| `parse_result` | `ParseResult` | the parsed items ([elements.md](./elements.md), [statements.md](./statements.md)) |
| `to_bytes()` | `-> bytes` | the original bytes (P3) |
| `slice(span)` | `-> str` | source text of a span |
| `lines` | `Lines` | top-level logical lines |
| `scopes` | `tuple[Scope, ...]` | depth first, top level first |
| `scope(path=())` | `-> Scope` | `KeyError` if absent; `TypeError` for a `str` or a `Scope` (section 1, `Scope`) |
| `params`, `models`, `subckts` | `Mapping[str, tuple[...]]` | top-level tables (folded name → definitions) |
| `element(designator, *, scope=())` | `-> Component` | first of a repeated designator; `KeyError` |
| `elements(*, scope=(), recursive=False)` | `-> tuple[Component, ...]` | source order |
| `references` | `tuple[Reference, ...]` | every reference, source order |
| `references_to_param(name, *, scope=())` | `-> tuple[Reference, ...]` | those resolving to that scope's definitions |
| `resolve(reference)` | `-> object \| None` | `reference.target`; `ValueError` for a foreign reference |
| `topology` | `TopologyView` | |
| `nets`, `elements_on_net`, `connections`, `ports`, `signature` | delegate to `topology` | |
| `diagnostics` | `tuple[Diagnostic, ...]` | computed once at load |
| `expression_reads(designator, *, scope=())` | `-> tuple[ExpressionRead, ...]` | delegates to `topology`; section 8 |

### `Line`, `Lines`

`Line(item, span, first_line, last_line, scope, body=None)`; compares by identity. `body` is a
`Lines` for a `SubcktDefinition`, else `None`.

`Lines` is a `Sequence[Line]` (slicing returns `Lines`) with `walk()` (depth first, a body after
its definition line), `find(kind, *, recursive=False) -> Line | None`, `find_all(kind, *,
recursive=False) -> tuple[Line, ...]`, `index_of(line_or_item) -> int` (identity, this sequence
only; `ValueError`), `point_before(line) -> Span` and `point_after(line) -> Span` (zero-width
spans at the line's start and end, after its terminator; `ValueError` unless the line is in this
sequence or its bodies). They insert nothing: an edit inserts a line through
`Placement.before(line)` or `Placement.after(line)`, and cannot insert after `.end`.

### `Scope`

Read-only properties: `path: ScopePath`, `display` (names as written), `definition:
SubcktDefinition | None`, `lines`, `parent`, `children`, `dialect`, `params`, `models`,
`subckts`, `elements` (each `Mapping[folded name, tuple in source order]`) and
`may_define_elsewhere: bool` (the scope holds an `.include` or `.lib` statement, or an `.if` or
`.lib` block, whose names the tables do not show; §7.8). Methods: `fold(name)` (the dialect's
folded form), `chain()` (self, then enclosing scopes), `walk()`, `describe()`. Assigning an
attribute is an `AttributeError`.

A `scope=` argument, and `Netlist.scope(path)`, take the path, not a `Scope`: a `Scope` is a
`TypeError` that says to pass `Scope.path`, and a `str` is a `TypeError` that says to write a
one-name tuple (`("amp",)`).

### `Reference`

`Reference(kind, name, span, scope, owner, target)`; compares by identity. `kind` is a
`ReferenceKind`, the `Literal` of `"model"`, `"subckt"`, `"param"`, `"subckt_param"`, `"element"`, `"node"`, `"function"`, `"data"`. `span` covers the name as written,
`owner` is the item holding it, `target` the resolved node or `None`. Deviation from task 3.2:
`owner` is added (the edit layer needs the item to edit).

| Kind | From | Target |
|---|---|---|
| `model` | the model of every element that names one (R, C, L, D, Q, M, J, Z, S, W, O, U, Y, P, ngspice A and N); LTspice `ako:` and `.step` model sweeps | `ModelStatement` |
| `subckt` | X subcircuit name | `SubcktDefinition` |
| `subckt_param` | X `name=value` (the name) | the definition's default `ParamAssignment`, or `None` (not diagnosed: ngspice 47 ignores an unknown one) |
| `param` | a bare identifier in a formula anywhere (values, parameters, `.param`, `.model`, defaults, X parameters, directive arguments, expressions); an LTspice `.step param` name that a `.param` line also defines | the `ParamAssignment` (last in its scope) |
| `element` | K inductors; the controlling sources of F, H and W, and an ngspice A's `%vnam` sources; an LTspice `&` probe's analyzer; `.dc` sources (not `TEMP`); `.save i(src)`; LTspice `.ic i(L1)` and `.step` sources; `i(src)` in a behavioural expression | `Component` |
| `node` | each name in `v(a)` or `v(a,b)` in a behavioural expression; an LTspice `@`'s `refnode=` and `intnode=` | `Net`, or `None` |
| `function` | xyce only: a call in a formula to a name that is not a built-in function | the `FunctionDefinition` (first in its scope), or `None` |
| `data` | xyce only: a `DATA=` field of `.AC`, `.DC` or `.STEP` | the top-level `DataTable` of that name (the last of a repeated one), or `None` |

On xyce (section 9) a `.DC` or `.STEP` target is a `param`, `element` or `model` reference by
what it resolves to, and each node of an `.IC`, `.DCVOLT` or `.NODESET` condition is a `node`
reference.

### `TopologyView`

| Member | Notes |
|---|---|
| `nets(*, scope=()) -> tuple[Net, ...]` | first-use order: ports, element nodes, top-level `.global` nodes, in line order |
| `net(name, *, scope=()) -> Net` | `KeyError` if no element of the scope uses it |
| `elements_on_net(net: Net \| str, *, scope=())` | elements of that scope only |
| `connections(designator, *, scope=()) -> tuple[Connection, ...]` | `K` has none; `KeyError` |
| `ports(subckt, *, scope=()) -> tuple[Net, ...]` | definition resolved like an X line; nets of the definition's scope |
| `signature() -> TopologySignature` | section 3 |
| `expression_reads(designator, *, scope=()) -> tuple[ExpressionRead, ...]` | section 8; `KeyError` |

`Net(name, scope, spellings, global_)`: `name` folded (`"0"` for ground); `scope` `()` for a
shared net (ground or `.global`, `global_=True`), else the definition scope; `spellings` as
written, first-seen order, across all scopes. Nets compare by `(name, scope)`.
`Connection(element, terminal, node, net)`; `terminal` is the 0-based node position.

### `Diagnostic`

`Diagnostic(code: DiagnosticCode, severity: Severity, message, span, line, column)`, where
`Severity` is the `Literal` `"warning" | "info"`.

## 2. Resolution order

- Model, subcircuit, parameter: own scope, then each enclosing scope, then the top level;
  file order is ignored. First match by folded name wins.
- In the matching scope: a parameter resolves to its **last** assignment, a model or subcircuit
  to its **first** definition (ngspice 47).
- A definition's defaults are parameters of the definition's own scope (listed before body
  `.param` lines); their formulas resolve from that scope.
- Element references: own scope only, first element with that designator.
- Not seen: items in `.if` blocks and in `.include`/`.lib` files (§7.8).

## 3. Signature encoding

`TopologySignature.entries` is a tuple of tuples in source order (a definition's entry, then its
body's entries, then the following lines), with exact text everywhere; `scope` is
`Scope.display` (definition names as written):

| Entry | Form |
|---|---|
| element (every `Component` but X and K) | `("element", scope, designator, type name, (node, …))` |
| ngspice A's ports | `("ports", scope, designator, structure)`, right after the element entry: for each port its position, whether it is a vector and its type, and each connection's type, nodes and `null`, as written (`~` is left out; decision 0020 item 4) |
| X line | `("instance", scope, designator, (node, …), subckt name)` |
| K line | `("coupling", scope, designator, (inductor, …))` |
| controlling source (F, H, W, and an ngspice A's `%vnam`) | `("control", scope, designator, source)`, one entry for each source after the element's own, in line order: one for the linear form, N for POLY, none for LTspice's `value=` (decision 0017 item 2), one for each `%vnam` of an A line. POLY's control nodes are in the element entry's `nodes`; swapping two POLY sources changes the order of the entries |
| definition | `("subckt", scope, name, (port, …))` |
| `.global` | `("global", (sorted set of .global node names))`, after the entries of the scopes |
| xyce `.PREPROCESS REPLACEGROUND` | `("replaceground", (value as written, …))`, last, only when the netlist has the statement (section 9) |

`digest()` is the SHA-256 hex digest of `json.dumps(entries, ensure_ascii=False,
separators=(",", ":"))` encoded as UTF-8.

## 4. Diagnostics

| Code | Severity | Span | When |
|---|---|---|---|
| `UNRESOLVED_MODEL`, `UNRESOLVED_SUBCKT`, `UNRESOLVED_PARAM`, `UNRESOLVED_ELEMENT` | warning; info if a searched scope has `.include`/`.lib`, or for an LTspice controlling source inside an instance (`X1:Vq`) | the name | reference not found; the message lists the scopes searched. An element reference (K's inductors, a controlling source of F, H or W) is searched in its own scope only |
| `DUPLICATE_DEFINITION` | info (`.param`), warning (`.model`, `.subckt`) | the repeated name | a name defined again in one scope (defaults count as parameters) |
| `DUPLICATE_ELEMENT` | warning | the repeated designator | case-insensitive |
| `SUBCKT_PORT_MISMATCH` | warning | the X line's subcircuit name | node count ≠ port count |
| `PARAM_USED_BEFORE_DEFINITION` | warning | the name in the formula | the definition is in the reference's own scope and that scope's first definition starts after it (an enclosing scope's parameter is never "late": review R1) |
| `ENDS_NAME_MISMATCH` | info | the `.ends` name | names differ (case-insensitive) |
| `DIALECT_GATED_SYNTAX` | info | the value | `notation == "rkm"` |
| `RKM_SOLVER_MISMATCH` | warning | the value | `solver_mismatch` |
| `UNTYPED_DIRECTIVE_PRESERVED` | info | the dot-command name | each `UnknownDirective` |
| `NODE_INTO_INSTANCE` | warning; info if the definition is in an include | the node | an LTspice `<instance>:<node>` that reaches into an instance of the same scope (decision 0009 item 19); an xyce one that names an internal node of the instance's definition (decision 0027 item 4; section 9) |
| `UNRESOLVED_NODE` | warning; info if the scope has an `.include`, `.lib` or opaque block, or for a node inside an instance of the scope (ngspice `x1.n`, LTspice `X1:n`) | the node name | a behavioural expression reads a node that no element of its own scope connects to, and that is not ground, a `.global` node or a port (decision 0016 item 6) |
| `CONTROL_SOURCE_MISMATCH` | warning | the controlling source's name | an F, H or W line whose controlling source resolves to an element that is not a V; the message names the independent voltage source (`V`) the reference expects, and says whether the solver runs this source (an E or H, and on LTspice an L) or stops on it (decision 0015 item 5) |
| `FRA_PROBE_IN_IMPEDANCE_MODE` | warning | the probe's designator | an LTspice `&` whose resolved analyzer (decision 0020 item 8) has the `zm` flag; LTspice stops on it (M18 D2) |
| `INDENTED_LINE_IGNORED` | warning | the line, without its line end | an xyce `IndentedLine`: a line that begins with blanks and is not a `*`, `;` or `+` line, which Xyce reads as a comment (decision 0027 item 1); also such a line between a statement and its `+` line, one of the statement's trailing comments (section 9) |
| `LIB_EXTRA_ENTRIES` | info | the entries after the first | an xyce `LibCall` with more than one entry, of which Xyce loads only the first (section 9) |
| `NUMERIC_MODEL_NAME` | warning | the model name | an xyce `.model` whose name reads as a number (section 9) |
| `FRA_RANGE_MISSING` | warning | the analyzer's designator | an LTspice `@`, in any scope, without `fstart=` or `fend=` and without `enabled=`, when the top level has a `.fra` command; LTspice stops in the `.fra` run (M18 D2) |
| `UNRESOLVED_DATA` | warning; info if the top level has `.include`/`.lib` | the table name | an xyce `DATA=` field that names no top-level `.DATA` table (section 9) |
| `ANALYSIS_IGNORED` | warning | the keyword | an xyce analysis Xyce does not run, or a `.DC` line that joins the first (section 9) |
| `STEPPED_ANALYSIS_FIELD` | warning | the parameter | an xyce `.TRAN`, `.AC` or `.DC` field that reads a parameter a `.STEP` sweeps (section 9) |
| `STEP_IGNORED` | warning | the keyword | an xyce `.STEP` line beside a `.STEP DATA=` line (section 9) |
| `STEPS_WITH_OP` | warning | the `.OP` keyword | two or more xyce `.STEP` lines when `.OP` is the analysis that runs (section 9) |
| `IC_WITH_NODESET` | warning | each `.NODESET` keyword | an xyce netlist with `.IC` or `.DCVOLT` and `.NODESET` (section 9) |
| `MEASURE_MODE_MISMATCH` | warning | the mode | an xyce `.MEAS` mode whose analysis does not run, or FFT without `.FFT` (section 9) |
| `CONDITION_IGNORED` | warning | the node | an xyce condition in a subcircuit body on a global node (section 9) |

Order: by span start, then span end, then code order. `MODEL_TYPE_MISMATCH` (warning, at
the model name) is specified with the edit layer ([edit-layer.md](./edit-layer.md) §6), because
its element-to-model-type table serves the same-type rule of `set_model`.

## 5. Formula scan

`grammar/formula.lark` (`NG-FML-001`) and `parse_formula(text) -> tuple[FormulaToken, ...] |
None`; `FormulaToken(kind, text, start, end)`, offsets relative to `Formula.text`, so the source
span is `formula.span.start + 1 + start`. Kinds: `parameter`, `reserved`, `function`, `node`,
`source`; only `parameter` tokens become references. `None` (no references, no error) when the
grammar does not accept the text. Double-quoted strings are not scanned.

## 6. What the edit layer uses

- Insertion points are physical-line boundaries; the edit layer chooses the inserted text (EOL
  style, a missing final newline).
- `Reference.owner` and `.span` give the item and the exact name span to replace.
- The signature is compared after re-parse (§7.6); `digest()` is for logs.

## 7. LTspice

The API and the signature encoding are the same; `$G_*` nodes count as global. What differs:

- **Names** compare by Unicode case folding after NFC, by `ParseResult.dialect` (`names.py`). `0` and `GND` in any case are ground.
- **Resolution:** a repeated `.subckt` still resolves to the first definition, and LTspice stops if it is used. A parameter swept by `.step param` counts as defined.
- **Formula scan:** the overlay `formula_ltspice.lark`, whose reserved words are only LTspice's built-in values, and a definition in scope masks them. A bare `.param` expression has no delimiter, so its offsets start at `span.start`.
- **`PARAM_USED_BEFORE_DEFINITION`** and **`DUPLICATE_DEFINITION`** follow the solver: for `.param`, the latter is a warning, because LTspice stops at a repeated definition.
- **`DIALECT_GATED_SYNTAX`** and **`RKM_SOLVER_MISMATCH`** are not used.

## 8. Expression reads (decision 0016)

`expression_reads(designator, *, scope=())` returns the reads of the element's expressions in
source order: B's expression, an expression form of E, F, G or H, C's charge, L's flux, and an
R, C or L formula value, and the expression of an ngspice `TABLE` or `FREQ` (decision 0017). `ExpressionRead(kind, name, span, target)`: `kind` is `"node"` (each
name in `v(a)` or `v(a,b)`) or `"source"` (`i(Vx)`); `span` covers the name; `target` is the
`Net` or the `Component`, or `None`. An element without an expression reads nothing; F's
controlling source is topology (section 3), not a read.

A node read resolves in the element's own scope, through ground, `.global` nodes and the
subcircuit's ports: a top-level net is not visible from inside a subcircuit, as for both
solvers. A source read resolves as an element reference. The reads never enter the signature.

The formula scan (section 5) reads, inside an expression, `{...}` within a bare expression,
`+` continuations and LTspice's `~`. The words an expression gives a meaning to are not
parameters there: LTspice's `time` in B and `value=`, `x` in `Q=` and `Flux=`, and `s` in `Laplace=` and B's `laplace=`. LTspice's
`time` elsewhere is still a name.

## 9. Xyce (hidden)

The dialect is the internal `netlistmod.dialects._XYCE` until X-M8 (decision 0026); its nodes
`IndentedLine`, `PreprocessDirective`, `GlobalParamStatement` and `FuncStatement` live in `netlistmod.model.nodes` and are not exported. The
API and the signature encoding are the same. What differs ([names.md](../grammars/xyce/names.md),
decision 0027 items 1 and 3):

- **Names** fold by ASCII lower case. `0` is the only ground, unless the netlist holds
  `.PREPROCESS REPLACEGROUND TRUE`, anywhere, a body included: then `GND`, `GND!` and `GROUND`
  in any case are ground in every scope (`Index.replace_ground`, the internal
  `Scope._replace_ground`, the `replace_ground=` argument of `names.is_ground` and
  `names.net_name`). The statement's value is
  the last signature entry, so no edit changes it (P4).
- **Globals:** a node whose name begins `$G`, in any case, is global (`is_automatic_global`, a
  per-dialect prefix table: LTspice `$g_`, xyce `$g`), as is a `.GLOBAL` name.
- **Scoping** ([scoping.md](../grammars/xyce/scoping.md)): a repeated parameter resolves to its
  **first** definition (a `DUPLICATE_DEFINITION` warning); order does not matter, so there is no
  `PARAM_USED_BEFORE_DEFINITION`; a `.GLOBAL_PARAM` is a top-level parameter listed after the
  `.PARAM` assignments, so a `.PARAM` of the same name wins; a body `.PARAM` that repeats a
  `PARAMS:` name is reported as shadowed; reserved words are never references.
- **Functions:** the scope's internal table `Scope._functions` (named at X-M8; xm1-tasks 5.1
  point 31) holds `.FUNC` lines and `.PARAM` function assignments, looked up like models; a call that is not a built-in (`builtin_functions`, from
  `formula-reserved.json`) is a `function` reference, and a function's arguments are not
  parameter references in its body. A repeated function is a `DUPLICATE_DEFINITION` warning
  (Xyce stops). An unresolved function is an `UNRESOLVED_PARAM` (message "function `f` is not
  defined"), with the severity of an unresolved parameter: a `.FUNC` is scoped like a `.PARAM`.
- **Formula scan:** `formula_xyce.lark` (`XY-FML-001`); a bare `.PARAM` value has no delimiter.
- **`.ENDS` names** are not checked by Xyce: `ENDS_NAME_MISMATCH` (info) says so. A repeated
  `.model` or `.subckt` is a `DUPLICATE_DEFINITION` warning that says Xyce stops.
- **`LIB_EXTRA_ENTRIES`** (info) reports a `.LIB` call that names more than one entry: Xyce
  loads only the first, with a warning.
- **Node paths into an instance** (decision X-D2, decision 0027 item 4; `names.md` N7): a node
  `X1:m` (or `X1:X2:m`) is resolved through the `X` designators of the scope it is written in,
  then of each definition. When it names an internal node of the definition, a node of a body
  element that is not a port, ground, a `$G` node or a `.GLOBAL` node, it is a
  `NODE_INTO_INSTANCE` warning: Xyce joins it to that node, and the library keeps it as a net of
  its own (§7.8). A port, ground, a global, a missing node or a missing instance is a net of its
  own in Xyce too, with no finding; a definition the netlist does not hold, with an include in
  scope, gives an info. An expression read such as `V(X1:m)` is an `UNRESOLVED_NODE` info, as on
  LTspice.
- **K's CORE model** (`MutualCoupling.model`) is a `model` reference: `UNRESOLVED_MODEL` and
  `MODEL_TYPE_MISMATCH` (it takes `CORE`) as for any model.
- **R, C and L words that Xyce sorts by lookup** (xm1-tasks 5.1 point 9): an `UNRESOLVED_MODEL`
  on an R, C or L whose model name is a visible parameter adds that Xyce reads the word as the
  value; a `.model` whose name reads as a number (`.model 2k R`) is a `NUMERIC_MODEL_NAME`
  warning, since the library reads that word on an element line as a value and Xyce as the model.
- **`INDENTED_LINE_IGNORED`** reports each `IndentedLine` (section 4), and each indented line
  inside a continued statement, which is one of its trailing comments: the grammar lexes it as
  `INDENTED_TRAILING`, and the parse records its span (`model.nodes.indented_comments`, internal),
  which `collect_diagnostics` takes as `indented`.
- **Sweep targets** (decision 0028 item 4; `index.py`'s `_SWEEP_LOOKUP`, a per-dialect table): a
  `.DC` sweep or `.STEP` target is resolved as Xyce resolves it. `TEMP` is no reference. A plain
  name is a parameter first (the effective assignment, the first on xyce), then an element of the
  scope (a device's primary parameter); unresolved, a `param` reference, which Xyce reports as an
  undefined variable. In `head:param`, split at the last `:`, the head is an element, a path
  `X1:R5` walked through the `X` lines and their definitions, or a model; unresolved, an
  `element` reference. A path whose last part is a device of the instance (`X1:R5`, the device
  without its parameter) is an unresolved `element` reference for the whole target, "element
  parameter" in the message with the hint to write `X1:R5:<param>`, a warning even with an
  include in scope, since Xyce stops on it. `Index.sweep_targets` (internal) maps these
  references to what they may name, so an unresolved one says "parameter or element", "element or model" or "element", adds
  that Xyce stops, and is info when a path reaches a definition an include may hold. ngspice and
  LTspice keep their `.dc` and `.step` references.
- **`DATA=`** on `.AC`, `.DC` and `.STEP` is a `data` reference to the top-level `.DATA` table
  of that name (the internal `Scope._data`, folded names in source order); a repeated name
  resolves to the last table, as Xyce uses. `UNRESOLVED_DATA` reports an unknown one.
- **The `.TRAN` schedule** (`TranDirective.schedule`): its `schedule` word is the field's own and
  no function reference; its arguments are scanned as any formula. `schedule` is not made a
  built-in function, since Xyce knows it in that field only.
- **Condition nodes** (decision 0028 items 2 and 6): each node of an `.IC`, `.DCVOLT` or
  `.NODESET` condition is a `node` reference resolved in the scope of its line, and is listed in
  `Index.condition_nodes` (internal), which routes it to the condition checks: a node that an
  expression in a condition's value reads is an ordinary expression node, on every dialect (a
  body condition in its definition: ports and body nodes, ground, globals). A path that names an internal node of
  an instance is a `NODE_INTO_INSTANCE` warning (info when the definition may be in an include),
  as on a device line; a node that nothing in the scope connects is an `UNRESOLVED_NODE` warning
  (info with an include), since Xyce ignores its condition; a `$G` or `.GLOBAL` node in a body's
  condition is a `CONDITION_IGNORED` warning: Xyce ignores it there.
- **What Xyce runs** (decision 0028 item 9; `diagnostics.py`'s `_DIRECTIVE_CHECKS`, a per-dialect
  table, false on ngspice and LTspice), all warnings, from the top level:
  - `ANALYSIS_IGNORED`: of `.TRAN`, `.AC`, `.DC` and `.NOISE` (an `UnknownDirective`, as the B5
    probes show) only the last line's analysis runs, each other line is reported; `.OP` gives way
    to any of them; when `.DC` runs, every `.DC` line after the first joins it into one nested
    sweep, the earlier lines innermost (its own message).
  - `STEPPED_ANALYSIS_FIELD`: a parameter reference in a `.TRAN`, `.AC` or `.DC` field whose
    target a `.STEP` sweeps (a `.DC` sweep of the parameter itself is not a field). The message
    is keyed per analysis (`_STEPPED_FIELD`): Xyce reads a `.TRAN` field once, and stops on an
    `.AC` or `.DC` one (R1 review).
  - `STEP_IGNORED` on each `.STEP` line beside a `.STEP DATA=` line; `STEPS_WITH_OP` on `.OP` when
    it runs with two or more `.STEP` lines.
  - `IC_WITH_NODESET` on each `.NODESET` when the netlist, in any scope, has `.IC` or `.DCVOLT`.
  - `MEASURE_MODE_MISMATCH` on a `.MEAS` mode whose analysis is not the one that runs (TRAN and
    TRAN_CONT need `.TRAN`, AC `.AC`, DC `.DC`, NOISE `.NOISE`), or FFT with no `.FFT` line; the
    message says Xyce stops, or, for DC under `.OP`, reports the measurement as FAILED.
- **`DUPLICATE_DEFINITION`** for directives, each a warning that says which one Xyce uses: a
  repeated `.OPTIONS` item of one package (the first; the OUTPUT package is left out, since two of
  its lines both apply; the package-less `.OPTION SCALE=` is PARSER's, as Xyce reads it), a
  repeated node in the `.IC` and `.DCVOLT` conditions or in the `.NODESET` conditions of one scope (the last), a repeated `.MEAS` result (the last) and a
  repeated `.DATA` name (the last). Two `.STEP` lines of one quantity are a repeat by the key
  `step_quantity` (internal): a device's name alone means its primary parameter (R, C and L
  theirs, V and I `DCV0`), only when the name resolves to that device and not to a parameter, so
  `R2` and `R2:R` are one quantity; Xyce nests them silently. LTspice keeps its `.step` rule and
  message (a per-dialect table, `_STEP_REPEATS`).
