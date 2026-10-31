# M5 task list — document and semantic layer (ngspice)

> **Status:** READY FOR REVIEW — implemented 2026-10-31 (section 9); approved by the maintainer (2026-10-31); section 2 records the decisions.
> **Part of:** [phase-1-plan.md](./phase-1-plan.md) (milestone M5). Governed by [architecture.md](../architecture.md) (§2 P1–P4, P8, P13; §3 layer [3]; §5.4; §7.1, §7.7, §7.8; §8; §17; §21). Builds on M2–M4: the parser returns typed nodes with spans that tile the source ([m3-elements.md](./m3-elements.md), [m4-statements.md](./m4-statements.md), decisions 0002–0005). Citations use the manual edition in [references.md](../references.md).

## 1. Scope

The read-only document layer (`src/netlistmod/document/`, architecture §3 layer [3], §4):

- **`Netlist`**: loads a file or text with an explicit dialect and holds the `SourceText` and the parse result (P1).
- **`Line` / `Lines`** (§5.4): the ordered, searchable sequence of items, with insertion points that M6 will use.
- **Indexes and symbol tables** (§8): elements by designator and definition scope; `.param`, `.model` and `.subckt` by name and scope; directives by kind.
- **Reference resolution** (read-only):
  - element → model;
  - X → subcircuit;
  - K → inductors;
  - formula → parameter names;
  - `.dc` source, `.save i(src)` → element.
- **Topology** (§7.7): a `TopologyView` with `nets()`, `elements_on_net()`, `connections()` and subcircuit ports, and the **topology signature** that M6's write-time check compares.
- **Diagnostics as data** (§8, §17): unresolved references, duplicates, port-count mismatches and the gated-syntax notes already recorded on nodes in M3/M4 (`notation="rkm"`, `solver_mismatch`, `.ends` name).
- **Docs:** `docs/grammars/ngspice/names.md` (case, ground, net identity) and `scoping.md` (the simple scope model, validated against ngspice 47), plus a design note for the semantic API.
- **One grammar addition:** `.global`, because net identity depends on it (decision 3).

**Exit (from the plan):** queries tested on corpus circuits. **Optional checkpoint:** read-only use is demonstrable at this point (plan section 8, open point 3); T11 prepares a short demo if you want that early look.

## 2. Decisions (maintainer, 2026-10-31)

Most of these are architecture §21 items. The maintainer accepted every recommendation below as written (2026-10-31). "Recommendation" marks the accepted choice; an alternative mentioned alongside was not chosen. Decision record 0006 (D1) records them. The probe evidence is in section 7.

1. **API entry points.**
   *Recommendation:*
   - `Netlist.load(path, *, dialect, rkm=False, fallback_encodings=...)`, `Netlist.from_text(text, *, dialect, rkm=False)` and `Netlist.from_source(source, *, dialect, rkm=False)`. `dialect` has no default (decision 17).
   - The netlist is immutable in M5. `to_bytes()` returns the original bytes (P3).
   - `save()` and every editing method arrive in M6, because `save` includes write-time verification (§7.6).
   - Queries return the M3/M4 node objects; no new copies.
2. **The line model** (§5.4; §21 deferred "the line model for continuation lines, interleaved comments and anchor-relative insertion").
   *Recommendation:* a `Line` is one **logical** item, not one physical line. That means a statement with all its continuation lines and end-of-line comments, a blank line, a comment line, or a whole opaque block. Its span is the item span the parser already tiles.
   - Each `Line` exposes `item`, `span`, `first_line`/`last_line` (1-based physical line numbers from `SourceText`) and `scope`.
   - A subcircuit definition is one `Line` whose `body` is a nested `Lines`.
   - `insert_before(line)` and `insert_after(line)` return zero-width spans at the line's span start and end. Both are physical-line boundaries, because item spans run from the end of the previous terminator. M6 decides the text inserted there.
   - `find`, `find_all` and `index_of` (identity-based) search by node type and unwrap nested bodies when asked (`recursive=True`).
   - Amend §5.4, which says "one physical line" and "an optional trailing comment" (nodes now carry `trailing_comments`).
3. **Names and net identity** (`names.md`; architecture decision 16).
   *Recommendation:* designators, model, subcircuit and parameter names, and node names are compared **case-insensitively**, by ASCII lower-casing as ngspice does (§2.1.3.4 for nodes; ngspice 47 for the rest, section 7).
   - `0` and `gnd` (any case) are one ground net. `00` is a distinct net (§2.1.3.5).
   - Nets inside a subcircuit definition are local to it, except ground, its ports (which bind to the instance's nodes) and `.global` nodes (§2.6.1, §2.7).
   - `.global` stays an `UnknownDirective` today, so M5 adds a typed `GlobalDirective(nodes)` (grammar task T1). Settle there whether `.global` may appear inside a subcircuit body (default: rejected like the other directives, decision 0005).
   - The `set ngbehavior` and `no_auto_gnd` settings live outside the netlist and are ignored; `names.md` says so.
4. **Scope model** (`scoping.md`; architecture decision 12, "document a simple model; validate per dialect against the solver").
   *Recommendation:*
   - **Parameters.** A top-level `.param` is global. Inside a definition, the `.subckt` defaults and body `.param` lines are local and mask global names (§2.11.4).
   - **Models and subcircuits.** They are local to the definition that contains them and visible in its nested definitions (§2.6.1). §2.11.4 says model and subcircuit names "are considered global and must be unique"; ngspice 47 follows §2.6.1 (a model defined inside a subcircuit is not found outside it). `scoping.md` records the conflict and the validated reading.
   - **Lookup.** A reference is resolved in its own definition scope first, then each enclosing scope, then the top level, independent of file order. ngspice 47 resolves models, subcircuits and even parameters defined after their use.
   - **Strict reading of §2.11.1.** "Before its first use, a parameter name must have been assigned a value." A parameter used before its definition still resolves, but gets the warning `PARAM_USED_BEFORE_DEFINITION`, and the difference is recorded in `discrepancies.md`.
   - **Redefinition.** A repeated `.param` resolves to the **last** assignment in the scope (ngspice 47) and gets `DUPLICATE_DEFINITION` (info). A repeated `.model` or `.subckt` name in one scope gets `DUPLICATE_DEFINITION` (warning).
5. **Hierarchical addressing** (§21 deferred; §16 is illustrative).
   *Recommendation:* M5 addresses **definition scopes**, not expanded instances: a scope is a tuple of subcircuit names (`()` for the top level, `("amp",)`, `("amp", "inner")`).
   - Queries take `scope=` as that tuple. `netlist.element("R1", scope=("amp",))` is the R1 inside the `amp` definition, shared by every instance.
   - No string path form in M5: `/` occurs in KiCad names, and `.` is ngspice's separator for **instance** paths (`x1.mid`, section 7). M6 may add one together with the `scope=Definition` edit argument (§7.4).
   - No flattened or instance-expanded view (§8, out of scope).
6. **What the topology signature compares** (§7.7, §8).
   *Recommendation:* the signature uses the **exact text** of every topology token, not the case-folded names: each element's scope, designator, type and ordered nodes; each definition's name and ordered ports; each X line's nodes and subcircuit name; each K line's inductor references; and the `.global` node set. It excludes comments, whitespace, values, parameters, other directives and the contents of opaque blocks (§7.8).
   - Exact text is stricter: a splice bug that only changes case (`GND` → `gnd`) is caught at save. Queries still use the `names.md` rules.
   - §8 says "the topology signature and all queries use these rules"; decision 0006 amends it.
   - Because `.global` changes connectivity, it is classified as **topology** (read-only) in §7.1, not as a removable directive.
   - The signature is a hashable, ordered value with a stable `digest()` (SHA-256 of a canonical encoding), so it can be logged and compared across runs.
7. **Diagnostics API** (§21 deferred "the diagnostics API (delivery and severity)"; §17).
   *Recommendation:*
   - A frozen `Diagnostic(code, severity, message, span, line, column)`, where `code` is a `DiagnosticCode` string enum and `severity` is `"warning"` or `"info"`. `netlist.diagnostics` is a tuple computed once at load, in source order. They are never raised (§8).
   - Codes, with the new ones marked ★ (each added to §17 by decision 0006):

   | Code | Severity | When |
   |---|---|---|
   | `UNRESOLVED_MODEL`, `UNRESOLVED_SUBCKT`, `UNRESOLVED_PARAM` | warning (info: decision 8) | reference not found in scope |
   | ★ `UNRESOLVED_ELEMENT` | warning | K inductor, `.dc` source, `.save i(src)` not found in scope |
   | `DUPLICATE_DEFINITION` | warning (info for `.param`) | repeated model, subcircuit or parameter name in one scope |
   | ★ `DUPLICATE_ELEMENT` | warning | two elements with the same designator in one scope (case-insensitive; ngspice 47 fails) |
   | ★ `SUBCKT_PORT_MISMATCH` | warning | X node count differs from the definition's port count (ngspice 47 fails) |
   | ★ `PARAM_USED_BEFORE_DEFINITION` | warning | decision 4 |
   | ★ `ENDS_NAME_MISMATCH` | info | `.ends other` (§2.6.2 "not checked") |
   | `DIALECT_GATED_SYNTAX` | info | RKM value (`notation="rkm"`; decision 0004) |
   | `RKM_SOLVER_MISMATCH` | warning | `solver_mismatch=True` (decision 0004) |
   | `UNKNOWN_DIRECTIVE_PRESERVED` | info | each `UnknownDirective` |

   - *Settle (T7):* `MODEL_TYPE_MISMATCH`, for example a resistor whose model has type `D`. The default is to defer it, because the element-to-model-type table belongs with M6's same-type rule (§7.2).
8. **Unresolved references when the file has `.include`/`.lib`** (§21 **unresolved** question 2, its diagnostics part).
   *Recommendation:* the reference may be defined in the included file, which the library never reads (§7.8). So an `UNRESOLVED_*` diagnostic whose scope chain contains an opaque `.include` or `.lib` has severity **info**, and the message says it may be defined there. Without one it is a **warning**. The `set_model` half of the question stays open for M6.
9. **Finding parameter names in formulas** (§8 "best-effort identifier scan", against P13 "no regular expressions or string scanning").
   *Recommendation:* a small separate Lark grammar, `grammar/formula.lark`, built strict and cached, that tokenizes formula text (identifiers, numbers with scale factors, operators, strings, `name(` calls) per §2.11.5. The document layer runs it over each `Formula.text`.
   - An identifier followed by `(` is a function call and never a parameter. So `V(n)`, `i(vm)` and user `.func` calls are excluded by syntax, not by a name list.
   - A bare identifier from the §2.11.6 reserved list (`time`, `temper`, `hertz`, …) is not a parameter. The list is data in the grammar package.
   - Text the formula grammar cannot tokenize gives no references and no error. It is reported only where the parameter is needed (a best-effort scan, §8).
   - P13 holds: syntax stays in a grammar, and the scan has a spec entry and tests.

## 3. Design

### 3.1 Package layout (architecture §4)

`document/document.py` (`Netlist`), `document/lines.py` (`Line`, `Lines`), `document/index.py` (`Scope`, symbol tables, element index, resolution), `document/topology.py` (`TopologyView`, `TopologySignature`), `document/diagnostics.py` (`Diagnostic`, `DiagnosticCode`), `document/names.py` (the `names.md` rules as functions: fold, ground test). `grammar/formula.lark` plus a loader entry. Everything is read-only; nothing under `document/` imports `edit/` (import-linter contract).

### 3.2 Shapes (proposed; D2 finalizes them)

- `Scope`: `path: tuple[str, ...]`, `definition: SubcktDefinition | None`, `lines: Lines`, `parent: Scope | None`, `children: tuple[Scope, ...]`, and its symbol tables (`params`, `models`, `subckts`, `elements`, each keyed by folded name and holding every definition in source order).
- `Reference`: `kind`, `name`, `span`, `scope`, `target` (the resolved node or `None`).
- `Net`: `name` (canonical: folded; `"0"` for ground), `scope`, `spellings` (the names as written), `global_: bool`.
- `Connection`: `element`, `terminal` (0-based node position), `node` (the `Node`), `net`.
- `TopologySignature`: a frozen, ordered tuple of entries plus `digest()`.

## 4. Tasks

Every task ends with `ruff check`, `ruff format --check`, `mypy --strict`, `lint-imports` (the import-linter contract), and `pytest` (coverage gate) green, run as `uv run --env-file .env python -m <tool>` (AGENTS.md; on Smart App Control failures follow docs/testing.md). P13 applies: no regular expressions or string scanning of source or formula text in `document/`. Where a task says "settle", state the choice with its basis in `names.md`, `scoping.md` or the design note, and in the report.

### Decisions and design

[x] **D1 — Decision record 0006: document layer, names, scope and diagnostics.**
Record the section 2 outcomes and amend the architecture:
- §5.4: logical lines, insertion points;
- §7.1: `.global` is topology;
- §7.7 and §8: the exact-text signature, definition-scope addressing, the model/subcircuit locality reading;
- §17: the new codes and severities;
- §21: mark the deferred items "line model", "diagnostics API" and "hierarchical addressing (read-only part)" resolved, and record the diagnostics half of unresolved question 2.
Status `proposed` until the maintainer accepts it.

[x] **D2 — Design note `docs/design/m5-document.md`.**
The public API (every method and property with its signature), the shapes of 3.2, the resolution order, how signature entries are encoded, and the diagnostics table. This note is what M6 builds its edit API on, so keep each rule to one line. Reviewed by the maintainer before T4.

[x] **D3 — `docs/grammars/ngspice/names.md` and `scoping.md`.**
Each rule with its manual citation, its `status` (`documented`/`observed`/`validated` with the ngspice 47 probe from section 7), and its tests, in the spirit of the spec entries (§11.2). Record the §2.11.4 / §2.6.1 conflict, the `.param` order discrepancy, and the settings the library cannot see (`no_auto_gnd`, `ngbehavior`).

### Implementation

[x] **T1 — `.global` (grammar).**
`GlobalDirective(nodes: tuple[Node, ...])` per §2.7: one or more node names, top level only. A spec entry `NG-GLB-001`, tests, and the corpus. Same separator design as M4; no new lookaround terminal.

[x] **T2 — Formula grammar.**
`grammar/formula.lark` and `parse_formula(text) -> tuple[FormulaToken, ...]`, or an equivalent that returns identifier and call tokens with offsets relative to the formula, which the document layer maps to source spans. It covers numbers with scale factors and trailing letters (as `NG-NUM-001/002`), identifiers per §2.11.1 name characters, the §2.11.5 operators, parentheses, commas, the ternary `?:`, and strings. Settle: constants such as `pi` (not in §2.11.6; default: an identifier, so it may be reported unresolved; check §2.11.5 and settle); `!` and `#` in identifiers. A spec entry `NG-FML-001`.

[x] **T3 — `Netlist`, `Line`, `Lines`.**
Per decisions 1 and 2. Tests: lines tile the source, nested bodies, `find`/`find_all`/`index_of` (identity), insertion points at every boundary (first item, before `.end`, inside a body, a file without a final newline), and `to_bytes()` round-trip over every corpus file.

[x] **T4 — Scopes, symbol tables and resolution.**
Per decisions 3–5, over the M3/M4 nodes:
- elements → models (`R`/`C`/`L` model slots, `D`);
- X → subcircuits;
- K → inductors in the same scope;
- `.dc` sweep sources and `.save i(src)` → elements (`.dc TEMP` is not a reference);
- formula identifiers → parameters (T2), for element values and parameters, `.param`, `.model` parameters, subcircuit defaults and X parameters, and directive arguments.
API: `params`, `models`, `subckts`, `element()`, `elements()`, `references_to_param(name, scope=)`, `resolve(reference)`. Settle:
- whether an X parameter (`X1 a b sub r2=3k`) is a reference to the definition's default `r2` (default: yes, a `Reference` of kind `subckt_param`);
- whether a `.ic v(node)` naming a net that no element uses is reported (default: no).

[x] **T5 — Topology view and signature.**
Per decisions 3 and 6. `nets(scope=())`, `elements_on_net(net, scope=())`, `connections(designator, scope=())`, `ports(subckt, scope=())`, and `signature()` with `digest()`. Ports of a definition are nets of its scope; ground and `.global` nets are shared across scopes. Elements in opaque `.if` blocks are not seen (§7.8): `names.md` and the API docstrings say so.

[x] **T6 — Diagnostics.**
Per decisions 7 and 8. Each code is emitted at the span named in the design note, with a message that names the construct and, for unresolved references, the scopes searched.

[x] **T7 — Settle `MODEL_TYPE_MISMATCH`** (decision 7). Either defer it with a note in the design note (default), or implement it from a table (element letter → allowed model types, from §2.5 Table 2.3) and say why.

### Validation, docs and tests

[x] **T8 — Solver probes (T8 tier).**
In `tests/solver/`, record the section 7 probes as tests that validate `names.md` and `scoping.md`, each paired with what the library reports:
- node, designator, model, subcircuit and parameter case;
- `gnd` and `00`;
- local nets (`x1.mid`) and `.global`;
- definition order;
- parameter masking and redefinition;
- port-count mismatch;
- duplicate designators.
Add a check that the nets the library reports for each `statements_basic` and `elements_basic` file match ngspice's node list for the same netlist. ngspice prints the list with `display` or after `op` in `.control`; check the manual and settle the command. Update `discrepancies.md`.

[x] **T9 — Tests and corpus.**
- *T1:* every class and query on small inline netlists.
- *Corpus:* a new authored family `document_basic/` (author `xdylanm`, MIT, confirmed by the maintainer on 2026-10-31), with circuits whose nets, connections, references and diagnostics are written out in the manifest as the expected results: a divider, an RC filter, a diode clamp, a two-level subcircuit with instance overrides and a `.global`, a coupled-inductor pair, a KiCad export with `/` names and `gnd`, and a file with every diagnostic code. Run the queries over every existing accept corpus too (no crash, every reference resolved or diagnosed).
- *T5 (Hypothesis):* (a) the signature is unchanged by any re-rendering that changes only whitespace, comments, continuation style, values, parameters or non-topology directives; (b) it changes when any topology token changes (designator, node, port, subcircuit name, K reference, `.global` node, element order); (c) `nets()` agrees with an independent oracle built by the generator.
*Done when:* all pass with the 90% coverage gate.

[x] **T10 — Docs.**
- A usage page `docs/usage/document.md` with executed examples (load, find, resolve, nets, connections, diagnostics, signature).
- `CHANGELOG.md`, `README.md` status, `docs/testing.md`, and the phase plan's M5 heading.
- Docstrings on every public name.

[x] **T11 — Optional checkpoint demo.**
`docs/usage/examples/read_only_demo.py` (executed by the usage test). It loads a `kicad_basic` netlist with `rkm=True` and prints its elements, nets, connections, resolved references and diagnostics. Mention it in the report so the maintainer can try read-only use before M6.

[x] **T12 — Exit.**
Full check set, a fresh-clone test, and the solver tests. Report what changed, every "settle" decision with its basis, deviations from this list, and limitations. Set this document's status to `READY FOR REVIEW`. **Do not archive.**

## 5. Dependencies between tasks

```
Section 2 decisions → D1, D2 (D2 reviewed before T4)
D3 can start with D1 and is completed with T8's results
T1, T2 (grammar; independent) → T4
T3 → T4 → T5 → T6 → T7
T8 needs T5–T6 for the library side; its probes can start earlier
T6 → T9 → T10, T11 → T12
```

## 6. Behaviour table (minimum; extend in T3–T6)

| Netlist (essentials) | Expected |
|---|---|
| `V1 IN 0 DC 3` / `R1 in OUT 1k` / `R2 out 0 1k` | nets `0`, `in`, `out` (folded); `in` has V1 and R1 |
| `V1 in GND …` / `R2 out gnd …` | one ground net `0` with spellings `GND`, `gnd` |
| `R2 out 00 1k` / `R3 00 0 1k` | `00` is a separate net from `0` |
| `R1 …` and `r1 …` at top level | `DUPLICATE_ELEMENT` at the second |
| `D1 a 0 DMOD` with `.model dmod d` (later in the file) | resolved; no diagnostic |
| `D1 a 0 dm` with no `.model dm` | `UNRESOLVED_MODEL` warning at `dm` |
| same, file also has `.include models.lib` | `UNRESOLVED_MODEL` info (decision 8) |
| `X1 in out DIV` with `.subckt div a b` defined after it | resolved |
| `X1 in out extra div` with a two-port `div` | `SUBCKT_PORT_MISMATCH` |
| `R1 in out {rx}` before `.param rx=3k` | resolved to `rx`; `PARAM_USED_BEFORE_DEFINITION` |
| `.param rx=1k` / `.param rx=3k` | `rx` resolves to the second; `DUPLICATE_DEFINITION` info |
| global `.param rx=3k`; `.param rx=1k` inside `div`; `{rx}` in both | top-level `{rx}` → global; body `{rx}` → local |
| `.model dm d` inside `div`, `D2 out 0 dm` at top level | `UNRESOLVED_MODEL` (models are local, §2.6.1) |
| `mid` used inside `div` and at top level | two nets: `("div",)` scope `mid` and top-level `mid` |
| `.global vcc` and `vcc` inside `div` | one net `vcc`, shared |
| `R1 a b {V(a)*2+gain}` | references `gain` only; `V(` is a call |
| `k1 l1 L2 0.9` | resolves to `L1` and `L2` (case-insensitive) |
| `K1 L1 L9 0.9` with no `L9` | `UNRESOLVED_ELEMENT` at `L9` |
| `.dc VIN 0 5 0.1` / `.dc TEMP -15 75 5` | `VIN` resolved (or `UNRESOLVED_ELEMENT`); `TEMP` is no reference |
| `.ends other` closing `div` | `ENDS_NAME_MISMATCH` info |
| `R1 a b 1M0` with `rkm=True` | `DIALECT_GATED_SYNTAX` and `RKM_SOLVER_MISMATCH` |
| `.print tran v(1)` | `UNKNOWN_DIRECTIVE_PRESERVED` info |
| reformat whitespace, comments, `+` vs `\\`, change a value | same signature |
| rename a node, reorder two elements, change `.global` | different signature |

## 7. Probe facts gathered while planning (ngspice 47, 2026-10-31)

Re-recorded as solver tests in T8. Divider `V1 in 0 DC 3`, two 1k resistors, `.op`, `print v(out)` unless noted.

| Input | ngspice 47 |
|---|---|
| `V1 IN 0`, `R1 in OUT`, `R2 out 0` | 1.5 V: node names are case-insensitive |
| `V1 in GND`, `R2 out gnd` | 1.5 V: `GND`/`gnd` are ground |
| `R2 out 00 1k`, `R3 00 0 1k` | 2.0 V: `00` is a distinct node |
| `R1 …` twice, or `R1` and `r1` | fatal error: duplicate designator (case-insensitive) |
| `D1 out 0 DMOD` with `.model dmod d` | resolved: model names are case-insensitive |
| `.model dm d` after `.control` … `.endc`, used earlier | resolved: definition order does not matter |
| `X1 in out DIV` with `.subckt div` | resolved: subcircuit names are case-insensitive |
| `.subckt div` before or after `X1` | resolved either way |
| `X1 in out extra div` (div has two ports) | fatal error |
| `.param RX=1k`, used as `{rx}` | resolved: parameter names are case-insensitive |
| `{rx}` used before `.param rx=3k` | resolved (0.75 V) despite §2.11.1 "before its first use" |
| `.param rx=1k` then `.param rx=3k` | the last assignment wins (0.75 V) |
| global `rx=3k`, `.param rx=1k` in `div` | the local value is used inside `div` (1.5 V) |
| `.model dm d` inside `div`, used at top level | error: model not found (models are local, §2.6.1) |
| `mid` inside `div` and at top level | separate nodes: `v(mid)` = 0, `v(x1.mid)` = 2.25 V |
| `.global vcc` used inside `div` | shared with the top-level `vcc` (1.5 V) |
| `k1 l1 L2 0.9` | accepted: inductor references are case-insensitive |

## 8. Out of scope for M5

Edits, `save()`, edit plans and verification (M6, including the `set_model` half of §21 question 2 and string path addressing); hierarchy flattening and instance-expanded queries (§8); expression evaluation (non-goal 6); model-parameter validation (non-goal 8); reading `.include`/`.lib` files (§7.8); elements inside `.if` blocks (§7.8); the LTspice dialect (M8).

## 9. Implementation report (2026-10-31)

**Settled** (each also in the named document):

- *T1:* `.global` is top level only and rejected in a body (NG-GLB-001; ngspice 47 accepts it
  there: `discrepancies.md`). It is a `GlobalDirective`, not a `Directive` subclass, because it
  is topology.
- *T2:* `pi` is an identifier (§2.11.5 has no constants; ngspice 47 rejects `{pi}`). `!`, `#` and
  `%` are not name characters in a formula (ngspice 47 cannot read `{a#b}`, `{a!b}`, `{a%b}`);
  `_`, `[` and `]` are. The formula grammar is a full §2.11.5 expression grammar, not only a
  tokenizer, so malformed text gives no references (NG-FML-001).
- *T4:* an X parameter is a `subckt_param` reference to the definition's default; an unknown one
  has `target=None` and no diagnostic (ngspice 47 ignores it). `.ic`/`.nodeset` nodes are not
  references and are not reported (`names.md`). A repeated `.model`/`.subckt` resolves to the
  **first** definition (ngspice 47: "redefinition … ignored"), a repeated `.param` to the last.
  Subcircuit defaults are parameters of the definition's own scope.
- *T7:* `MODEL_TYPE_MISMATCH` is deferred to M6 (`m5-document.md` section 4).
- *T8:* the node-list command is `display` after `op` in a `.control` block (§13.5.25); ngspice
  lists a numeric node as `V(13)` and an internal node by instance path (`x1.mid`).

**Deviations:**

- `Reference` has an extra `owner` field (the item holding the reference) for M6.
- `UnknownDirective` gained `name_span` (default `None`; the parser always sets it), so
  `UNKNOWN_DIRECTIVE_PRESERVED` points at the name.
- The M4 test that placed `.global gnd` in a body now uses `.probe` (decision 0006 behaviour
  change).
- D2 was not reviewed before T4: the design note was written with the implementation.
- Probe circuit for `x1.mid`: the recorded value is 2.0 V for the circuit in the test (a 1k load
  on `out`), not the 2.25 V of section 7, which used a different load.

**Limitations:** see decision 0006 "Known limits" (`.if` blocks and includes not seen; an `.if`
block does not soften an unresolved diagnostic; plain `.save` names, `@dev[param]` and
`.ic` nodes are not references; formulas with verbose operators give no references).
