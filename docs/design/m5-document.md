# M5 design note — the read-only document layer

> **Status:** ACTIVE — accepted by the maintainer (2026-10-31); implemented with M5; D2 of [m5-tasks.md](./archive/m5-tasks.md).
> [Decision 0006](../decisions/0006-document-layer-names-scope-and-diagnostics.md) records why.
> The reference M6 builds its edit API on. Rules: [names.md](../grammars/ngspice/names.md),
> [scoping.md](../grammars/ngspice/scoping.md). Kept ACTIVE after M6: the edit layer
> ([m6-edits.md](./m6-edits.md)) extends this `Netlist` and adds `MODEL_TYPE_MISMATCH`.

## 1. Public API

Everything is exported from `netlistmod` (and `netlistmod.document`). Nothing is mutable.
`ScopePath = tuple[str, ...]`: folded subcircuit names from the top level, `()` for the top level;
every `scope=` argument accepts any case.

### `Netlist`

| Member | Signature / type | Notes |
|---|---|---|
| `load` | `(path, *, dialect, rkm=False, fallback_encodings=DEFAULT_FALLBACKS) -> Netlist` | bytes, no newline translation |
| `from_text` | `(text, *, dialect, rkm=False) -> Netlist` | UTF-8, no BOM |
| `from_source` | `(source: SourceText, *, dialect, rkm=False) -> Netlist` | |
| `source`, `text`, `dialect`, `rkm` | properties | the source exactly as read (P1) |
| `parse_result` | `ParseResult` | the M3/M4 items |
| `to_bytes()` | `-> bytes` | the original bytes (P3) |
| `slice(span)` | `-> str` | source text of a span |
| `lines` | `Lines` | top-level logical lines |
| `scopes` | `tuple[Scope, ...]` | depth first, top level first |
| `scope(path=())` | `-> Scope` | `KeyError` if absent |
| `params`, `models`, `subckts` | `Mapping[str, tuple[...]]` | top-level tables (folded name → definitions) |
| `element(designator, scope=())` | `-> Component` | first of a repeated designator; `KeyError` |
| `elements(scope=(), *, recursive=False)` | `-> tuple[Component, ...]` | source order |
| `references` | `tuple[Reference, ...]` | every reference, source order |
| `references_to_param(name, scope=())` | `-> tuple[Reference, ...]` | those resolving to that scope's definitions |
| `resolve(reference)` | `-> object \| None` | `reference.target`; `ValueError` for a foreign reference |
| `topology` | `TopologyView` | |
| `nets`, `elements_on_net`, `connections`, `ports`, `signature` | delegate to `topology` | |
| `diagnostics` | `tuple[Diagnostic, ...]` | computed once at load |

### `Line`, `Lines`

`Line(item, span, first_line, last_line, scope, body=None)`; compares by identity. `body` is a
`Lines` for a `SubcktDefinition`, else `None`.

`Lines` is a `Sequence[Line]` (slicing returns `Lines`) with `walk()` (depth first, a body after
its definition line), `find(kind, *, recursive=False) -> Line | None`, `find_all(kind, *,
recursive=False) -> tuple[Line, ...]`, `index_of(line_or_item) -> int` (identity, this sequence
only; `ValueError`), `insert_before(line) -> Span` and `insert_after(line) -> Span` (zero-width;
`ValueError` unless the line is in this sequence or its bodies).

### `Scope`

`path`, `display` (names as written), `definition: SubcktDefinition | None`, `lines`, `parent`,
`children`, `params`, `models`, `subckts`, `elements` (each `Mapping[folded name, tuple in source
order]`), `has_opaque_include`, `chain()` (self, then enclosing scopes), `walk()`, `describe()`.

### `Reference`

`Reference(kind, name, span, scope, owner, target)`; compares by identity. `kind` is one of
`"model"`, `"subckt"`, `"param"`, `"subckt_param"`, `"element"`. `span` covers the name as written,
`owner` is the item holding it, `target` the resolved node or `None`. Deviation from task 3.2:
`owner` is added (M6 needs the item to edit).

| Kind | From | Target |
|---|---|---|
| `model` | R/C/L model slot, D model | `ModelStatement` |
| `subckt` | X subcircuit name | `SubcktDefinition` |
| `subckt_param` | X `name=value` (the name) | the definition's default `ParamAssignment`, or `None` (not diagnosed: ngspice 47 ignores an unknown one) |
| `param` | a bare identifier in a `{…}` or `'…'` formula anywhere (values, parameters, `.param`, `.model`, defaults, X parameters, directive arguments) | the `ParamAssignment` (last in its scope) |
| `element` | K inductors; `.dc` sources (not `TEMP`); `.save i(src)` | `Component` |

### `TopologyView`

| Member | Notes |
|---|---|
| `nets(scope=()) -> tuple[Net, ...]` | first-use order: ports, element nodes, top-level `.global` nodes, in line order |
| `net(name, scope=()) -> Net` | `KeyError` if no element of the scope uses it |
| `elements_on_net(net: Net \| str, scope=())` | elements of that scope only |
| `connections(designator, scope=()) -> tuple[Connection, ...]` | `K` has none; `KeyError` |
| `ports(subckt, scope=()) -> tuple[Net, ...]` | definition resolved like an X line; nets of the definition's scope |
| `signature() -> TopologySignature` | section 3 |

`Net(name, scope, spellings, global_)`: `name` folded (`"0"` for ground); `scope` `()` for a
shared net (ground or `.global`, `global_=True`), else the definition scope; `spellings` as
written, first-seen order, across all scopes. Nets compare by `(name, scope)`.
`Connection(element, terminal, node, net)`; `terminal` is the 0-based node position.

### `Diagnostic`

`Diagnostic(code: DiagnosticCode, severity: "warning" | "info", message, span, line, column)`.

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
| element (R, C, L, V, I, D) | `("element", scope, designator, type name, (node, …))` |
| X line | `("instance", scope, designator, (node, …), subckt name)` |
| K line | `("coupling", scope, designator, (inductor, …))` |
| definition | `("subckt", scope, name, (port, …))` |
| last entry | `("global", (sorted set of .global node names))` |

`digest()` is the SHA-256 hex digest of `json.dumps(entries, ensure_ascii=False,
separators=(",", ":"))` encoded as UTF-8.

## 4. Diagnostics

| Code | Severity | Span | When |
|---|---|---|---|
| `UNRESOLVED_MODEL` / `_SUBCKT` / `_PARAM` / `_ELEMENT` | warning; info if a searched scope has `.include`/`.lib` | the name | reference not found; the message lists the scopes searched |
| `DUPLICATE_DEFINITION` | info (`.param`), warning (`.model`, `.subckt`) | the repeated name | a name defined again in one scope (defaults count as parameters) |
| `DUPLICATE_ELEMENT` | warning | the repeated designator | case-insensitive |
| `SUBCKT_PORT_MISMATCH` | warning | the X line's subcircuit name | node count ≠ port count |
| `PARAM_USED_BEFORE_DEFINITION` | warning | the name in the formula | the definition is in the reference's own scope and that scope's first definition starts after it (an enclosing scope's parameter is never "late": review R1) |
| `ENDS_NAME_MISMATCH` | info | the `.ends` name | names differ (case-insensitive) |
| `DIALECT_GATED_SYNTAX` | info | the value | `notation == "rkm"` |
| `RKM_SOLVER_MISMATCH` | warning | the value | `solver_mismatch` |
| `UNKNOWN_DIRECTIVE_PRESERVED` | info | the dot-command name | each `UnknownDirective` |

Order: by span start, then span end, then code order. `MODEL_TYPE_MISMATCH` (warning, at
the model name) was added by M6 ([m6-edits.md](./m6-edits.md) §6). It was **deferred** to
M6 (T7): the element-to-model-type table belongs with §7.2's same-type rule for `set_model`, and
M5 has no edit that needs it.

## 5. Formula scan

`grammar/formula.lark` (`NG-FML-001`) and `parse_formula(text) -> tuple[FormulaToken, ...] |
None`; `FormulaToken(kind, text, start, end)`, offsets relative to `Formula.text`, so the source
span is `formula.span.start + 1 + start`. Kinds: `parameter`, `reserved`, `function`, `node`,
`source`; only `parameter` tokens become references. `None` (no references, no error) when the
grammar does not accept the text. Double-quoted strings are not scanned.

## 6. For M6

- Insertion points are physical-line boundaries; the inserted text (EOL style, a missing final
  newline) is M6's decision.
- `Reference.owner` and `.span` give the item and the exact name span to replace.
- The signature is compared after re-parse (§7.6); `digest()` is for logs.
