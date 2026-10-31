# Architecture

> **Status:** DRAFT v0.1 — initial design reference for maintainers, contributors and coding agents
> **License of this library:** MIT

## 0. How to use this document

- **Audience:** maintainers, contributors, and coding agents implementing the library.
- **Normative language:** MUST / SHOULD / MAY are used in the RFC 2119 sense. Sections 2 (Principles), 7 (Editing model), 10 (Testing), 11 (Reference manuals) and 12 (Licensing and provenance) are normative. The rest is descriptive.
- **Conflicts:** if code and this document disagree, one of them is wrong. Fix the code, or change this document through a decision record in `docs/decisions/`. Never diverge silently.
- **Level of detail:** this document states high-level principles and boundaries. Detailed functional requirements live in design documents under `docs/design/`, written as each part is implemented. Illustrative sketches (e.g. Section 16) are not requirements.
- **Prototype code:** the existing `.lark`/`.py` files are exploratory. They are not expected to match this document and may be used as a starting point.
- **Decisions and open items:** Section 19 lists confirmed decisions. Section 21 lists unresolved questions and items deferred to design and implementation. Agents MUST NOT silently resolve an item in Section 21; they raise it.

---

## 1. Purpose and scope

### 1.1 What the library is

A Python library that reads SPICE netlists, lets a caller **edit element values, properties and analysis directives in place**, and writes the netlist back with a **minimal diff**, while **guaranteeing the circuit topology and element types are unchanged**.

### 1.2 Typical workflow

```
schematic (KiCad / LTspice)
   │  netlist export (KiCad: manual or tool; LTspice: external export of .asc)
   ▼
netlist file (.cir / .net / .sp)
   │
   ▼
this library:  load  ->  edit values / params / directives  ->  save
   │
   ▼
edited netlist file  ->  solver run by the CALLER (ngspice / LTspice), never by this library
```

Examples of intended use: set `R22` to `2.2k`; replace `R1`'s literal value with `{Rx}` and add `.param Rx = 22k`; set up a `.tran` analysis; sweep a `.param` across many single-shot runs.

### 1.3 Goals

| ID | Goal |
|----|------|
| G1 | Parse netlists of supported dialects into a typed model; every node carries its source span. |
| G2 | Edit properties (values, formulas, instance parameters, `.param`, `.model` parameters, source stimulus specs) and analysis/control directives. |
| G3 | Byte-exact round-trip of unedited input; minimal diff for edited input. |
| G4 | Guarantee topology preservation, verified at write time. |
| G5 | Provide read-only queries: elements, nets, connectivity, and symbol tables (params, models, subcircuits). |
| G6 | Support **ngspice** and **LTspice** netlists in v1; make adding **qspice** and **xyce** a documented, mechanical process. |
| G7 | Trace every grammar construct to a reference manual and a test. |
| G8 | Be thoroughly documented for humans and for agents (`docs/`). |

### 1.4 Non-goals (explicit)

The library MUST NOT do the following, and agents MUST NOT add them without a decision record:

1. **Launch simulators.** Only the test suite does (Section 10.3).
2. **Read simulation outputs** (`.raw`, `.log`) or plot anything.
3. **Modify topology:** add, remove, reorder or reconnect elements; rename nets; change element types or designators; alter subcircuit port lists or structure. Test harnesses are built by a separate tool (Section 7.9).
4. **Parse or edit schematic formats** (`.asc`, `.qsch`, KiCad schematics). LTspice schematics are converted by an external export step.
5. **Convert between dialects** (v1). The architecture must not preclude it later (Section 9.4).
6. **Evaluate expressions** or do unit arithmetic. The simulator does that.
7. **Parse or edit `.control` / `.endc` scripting blocks.** They are preserved verbatim as opaque regions (Section 6.6).
8. **Validate model parameter sets** (e.g. whether a diode model's parameters are physically sensible).
9. **Create netlists from scratch.** Input is always an existing netlist.
10. **Provide a CLI or GUI** (v1).

### 1.5 Related projects

- **spicelib** (nunobrum, GPL-3.0): prior art and behavioral reference. It MUST NOT be copied from (Section 12).

---

## 2. Design principles (normative)

**P1 — Source text is the single source of truth.**
The library holds the original text exactly as read (decoded string plus encoding metadata). Every other representation is a view over it. There is no second copy of the netlist that can drift.

**P2 — Typed view, not a parallel tree.**
Typed nodes are immutable records holding parsed values and **source spans**. Editing never mutates a node. An edit produces an *edit plan* (a list of span replacements) applied to the source text, after which the document is re-parsed.

**P3 — Minimal diff, exact round-trip.**
Unedited text is never regenerated or reformatted. `load(x).save()` MUST equal `x` byte-for-byte, including line endings (including mixed), trailing whitespace, tabs, blank lines, a missing final newline, BOM and encoding.

**P4 — Topology is read-only.**
Node connections, element types and designators, and subcircuit structure cannot be changed through any public API. This is enforced three ways: API shape (no setter exists), a topology signature computed at load, and a write-time check that re-parses the output and compares signatures (Section 7).

**P5 — Strict by default; fail loudly.**
An element line the grammar does not recognise is an error with line, column and context, never a silent pass-through. Ambiguity in a grammar is a build failure (`strict=True`), never a silent default. Edits that are not provably safe raise.

The producer of a netlist is responsible for well-formed input: the library edits a netlist, it does not repair one. The grammar follows the language **as written in the reference manuals**. A construct a solver tolerates but the manual does not allow (for example a netlist without `.end`) is rejected, even though the solver would run it. Exceptions are explicit and recorded; v1 has one, the RKM mode option (Section 19, decision 8).

**P6 — The grammar is a documented, checked artifact.**
Each supported construct has a spec entry citing the reference manual and linking to its tests. CI fails if a supported construct lacks tests.

**P7 — Dialects are separate grammars over a shared core.**
There is no "accept any dialect" grammar, because the same device letter can mean different things in different dialects. The caller MUST select the dialect explicitly: there is no default and no auto-detection.

**P8 — Documented behavior is validated, not assumed.**
The reference manuals define what the grammar accepts (P5); solvers validate what constructs mean. Any behavior the library relies on has a test; where practical it is also validated against the real solver. Where the manual and the solver disagree, the grammar follows the manual and the disagreement is recorded (Section 11.3).

**P9 — No simulator launching in `src/`.**
Enforced by an architecture test (Section 10.2, T7).

**P10 — Clean-room provenance.**
Tests and corpus are independently authored and tracked. No GPL-licensed material is copied (Section 12).

**P11 — Edits state their scope.**
Editing an element inside a subcircuit definition affects every instance. The API forces the caller to say which is meant (Section 7.4).

**P12 — Built for agents as well as humans.**
Small modules, explicit invariants, layering rules that can be checked mechanically, and documentation kept next to the code it describes.

**P13 — Syntax lives in the grammar.**
Every syntactic rule (what a line, comment, continuation, keyword, statement or block is) MUST be expressed in the `.lark` files. Python code MAY (a) build parsers, (b) convert a parse tree into typed nodes with spans, one transformer method per rule, without re-scanning source text, and (c) enrich errors (positions, expected tokens, classifying an unsupported element letter from the failure position). Python code MUST NOT recognise, split, classify or validate syntax with regular expressions or string scanning. This is checked mechanically where possible (for example, no `re` import under `src/netlistmod/model/`) and in review.

---

## 3. Architecture overview

```
 file bytes
    │  decode (BOM / encoding detection), newline="" (no translation)
    ▼
 SourceText  (str + encoding + bom)                       source.py
    │
    ▼
 [1] Parser    Lark LALR, contextual lexer,               grammar/
     per-dialect grammar, propagate_positions, strict
    │  parse tree with positions
    ▼
 [2] Transformer -> typed nodes with spans                model/
    │
    ▼
 [3] Document   ordered Lines, element/param/model/       document/
     subckt indexes, topology view + signature
    │
    ▼
 [4] Edit API   restricted operations -> EditPlan         edit/
    │  [(Span, replacement_text), ...]
    ▼
 [5] Apply + Verify   splice -> reparse -> compare        edit/
     topology signature -> new SourceText
    │
    ▼
 save (original encoding, line endings preserved)
```

**Layering rule:** a layer MAY import only from layers above it in this diagram (i.e. [4] may use [3], [2], [1]; never the reverse). An architecture test enforces this.

**Why a re-parse after every edit set?** Parsing is cheap for the circuits in scope, and it makes the verifier independent of the splice logic. A bug in the splicer cannot silently produce a netlist that passes its own check.

---

## 4. Package layout

```
repo/
  pyproject.toml
  README.md
  AGENTS.md                  # short agent rules; points to docs/architecture.md
  CONTRIBUTING.md
  CHANGELOG.md
  LICENSE                    # MIT
  .gitattributes             # tests/corpus/** -text  (see Section 13)
  .pre-commit-config.yaml
  .github/workflows/
  src/netlistmod/
    __init__.py              # public API re-exports only
    py.typed
    errors.py
    source.py                # SourceText, Span
    dialects.py              # Dialect enum
    grammar/
      core.lark
      ngspice.lark
      ltspice.lark
      loader.py              # dialect registry and strict parser builder
    model/
      values.py              # NumericValue, Formula, ModelReference, ...
      nodes.py               # Component subclasses, statements
      transform.py           # Lark Transformer
    document/
      document.py            # Netlist
      lines.py               # Line, Lines (ordered, searchable)
      index.py               # element / param / model / subckt indexes
      topology.py            # TopologyView, signature
    edit/
      plan.py                # Edit, EditPlan, apply_edits
      api.py                 # restricted public editing operations
      placement.py           # directive placement strategies
      verify.py              # write-time verification
  tests/
    unit/  grammar/  roundtrip/  edits/  property/  negative/  architecture/  solver/
    corpus/<dialect>/<family>/        # provenance-tracked fixtures
    support/solvers.py                # solver discovery (tests only)
  docs/
    architecture.md          # this file
    design/  usage/  grammars/<dialect>/  testing.md  provenance.md  decisions/
```

---

## 5. Data model

### 5.1 Source and spans

- `SourceText` holds the decoded `str`, the detected encoding, and whether a BOM was present. Files MUST be read and written as bytes so there is no newline translation.
- `Span(start, end)` is **half-open, in characters of the decoded string** (not bytes). Zero-width spans (`start == end`) denote insertion points.
- The encoding recorded at load is used at save. Encoding detection order: BOM, then UTF-8, then a configurable fallback list (default includes `cp1252`, since LTspice netlists may contain a Windows-1252 `µ`). This policy MUST be validated against LTspice-generated fixtures.
- The confirmed fallback, BOM, and line-terminator policy is recorded in [decision 0001](decisions/0001-source-text-policy.md).

### 5.2 Node families

| Family | Examples | Notes |
|---|---|---|
| Element | `Resistor`, `Capacitor`, `Inductor`, `Diode`, `VoltageSource`, `CurrentSource`, `SubcktInstance`, `MutualCoupling`, ... | Subclass `Component`. Carry designator, nodes, value slot(s), instance params, span. |
| Statement | `Title`, `ParamStatement`, `ModelStatement`, `SubcktDefinition`, `End` | Dot-statements with structure the library understands. `SubcktDefinition` contains its body; body items tile the text between its header and its `.ends` line ([decision 0005](decisions/0005-statement-and-directive-grammar.md)). |
| Directive | `Directive` subclasses (`TranDirective`, `AcDirective`, `DcDirective`, `OpDirective`, `OptionsDirective`, `TempDirective`, `IcDirective`, `NodesetDirective`, `SaveDirective`, `MeasureDirective`) and `UnknownDirective(raw)` | Unknown dot-commands are preserved verbatim (see 6.5). Shapes and spans: [docs/design/m4-statements.md](design/m4-statements.md). |
| Opaque | `OpaqueBlock` | `.control` ... `.endc`; preserved verbatim, never edited. |

### 5.3 Value slots

A value slot is one of a **small closed family**; its kind determines which edits are legal.

```python
@dataclass(frozen=True)
class NumericValue:      text: str; span: Span; notation: "standard" | "rkm"; solver_mismatch: bool
                                                            # 1k, 2k7, 1e-6, 100R
@dataclass(frozen=True)
class Formula:           text: str; delimiter: str; span: Span   # {Rx*2}, "…", '…'
@dataclass(frozen=True)
class ModelReference:    model_name: str; span: Span
# SourceSpec (DC/AC/PULSE/SIN/...), BehavioralExpression: required by the end of phase 2
```

- `Resistor`/`Capacitor`/`Inductor`: `value: NumericValue | Formula | None`, `model: ModelReference | None`, `params: list[ParamAssignment]`. Both optional slots exist because ngspice allows a semiconductor-model form (`R1 a b rmodel w=2u l=10u`).
- `Resistor`/`Capacitor`/`Inductor` also record `value_keyword` when the value is written `r=1k` (and similar).
- `Diode`: `model: ModelReference` (mandatory), no numeric value.
- `VoltageSource` / `CurrentSource` (phase 1): `dc: NumericValue | Formula | None`, `dc_keyword: bool`, `ac: AcSpec | None` (`AcSpec(magnitude, phase, span)`); full stimulus specs are a typed node to be added before phase 2 completes ([decision 0004](decisions/0004-element-and-value-grammar.md)).
- Node and value shapes are detailed in [docs/design/m3-elements.md](design/m3-elements.md).
- The type of a slot is the basis of edit validation: `set_value` on a `ModelReference` slot is an `EditError`.

### 5.4 Lines

A `Line` is one physical line: its typed content (or `None` for blank/comment-only), an optional trailing comment, and a span covering the line including its newline. `Lines` is the ordered, searchable sequence: `find`, `find_all`, `index_of` (identity-based), and anchor-relative insertion points (`insert_before`, `insert_after`). Content extraction MUST unwrap structural wrapper rules recursively so searches by node type work regardless of grammar nesting.

---

## 6. Grammar design

### 6.1 Files and composition

- `core.lark`: terminals and rules for constructs whose syntax is the same across supported dialects (comments, title, `.end`, R/C/L/V/I/D and other letters with common form, `.param`, `.model`, `.subckt`, common directives).
- `<dialect>.lark`: dialect overlay adding or overriding constructs (device letters with dialect-specific meaning, dialect-only directives, numeric-notation differences).
- `grammar/loader.py` owns the dialect-to-grammar registry; `dialects.py` defines only the `Dialect` enum.
- Each dialect grammar is composed from core + overlay with Lark relative `%import` and MUST compile independently under `strict=True`.

### 6.2 Parser configuration

- **Lark, LALR, contextual lexer, `propagate_positions=True`, `strict=True`.**
- `strict=True` turns shift/reduce, reduce/reduce and terminal-collision problems into build errors. A grammar that only works because Lark resolves a conflict silently is a bug.
- Earley MAY be used for grammar exploration but MUST NOT ship. Lesson from the prototype: Earley parsed an input that LALR rejected because its dynamic lexer tolerates terminal overlap. That is not evidence the grammar is correct.

### 6.3 Lexical rules (learned in the prototype)

| # | Rule | Why |
|---|------|-----|
| 1 | `NEWLINE` is a real token; only *inline* whitespace is ignored (`%ignore WS_INLINE`). Statements are terminated by `NEWLINE`. | With all whitespace ignored, "end of statement" had to be guessed from token shape; LALR states merged and designator-like model names (e.g. `V0`, `D1N4148`) collided with statement starts. |
| 2 | Top-level shape: the first physical line is always the title; then body lines; `.end` is **required** and is the last statement; after it only blank lines. A missing newline after `.end` is tolerated. | The ngspice manual: the first line must be the title, and the last line must be `.end`. Anything else is a syntax error (P5). A final-newline alternative is spelled out explicitly: an empty optional newline is a shift/reduce conflict under `strict=True`. See [decision 0002](decisions/0002-grammar-structure-policy.md). |
| 3 | Continuation: `+` as the first non-blank character of the line *immediately* following the continued line is an **ignored terminal**; two backslashes immediately before the line terminator are a token of the statement's text rule, so they are recognised only inside a continuable statement (an ignored terminal would silently drop a line holding only `\\`). Blank and comment lines may not intervene. A `+` line after a comment, blank, title or `.end` line is a syntax error, and `.title`, `.lib` and `.include` cannot be continued. | The manual (§2.4.5): follow-up lines "have to follow immediately after each other", and `.title`, `.lib` and `.include` do not allow continuation. The ignored `+` terminal keeps statement rules free of continuation syntax while source spans stay correct. See [decision 0003](decisions/0003-grammar-composition-and-opaque-regions.md). |
| 4 | Keywords are **named terminals**, case-insensitive (`"…"i`), written as quoted strings rather than regexes where possible. | Anonymous literals are filtered from the tree; unescaped `.` in a regex is a wildcard (a prototype bug made `.param` collide with `CPARAM`). |
| 5 | In regex literals, `/` MUST be escaped and every literal closed. | An unclosed literal makes Lark report the error far from its cause. |
| 6 | Terminals that can match the same string MUST NOT be candidates in the same parser state unless disambiguated structurally. | Enforced by `strict=True`. |
| 7 | Free-text terminals (e.g. title text) MUST start with a non-whitespace character. | Otherwise they collide with the ignored-whitespace terminal. Spans recover the leading whitespace. |
| 8 | Delimited-expression terminals exclude their own delimiters (`\{[^{}]*\}`, not `[^"]*`). | Otherwise they swallow across multiple groups and lines. |
| 9 | Net names use a permissive class (word chars plus `/ . + -`). Identifiers are distinguished by grammar position, not by lexer class. | KiCad emits hierarchical names like `/Vout`. |
| 10 | Bare unquoted formulas (`R1 a b 1.1*Rx+1000`) are **not** accepted until validated against the solver. | A catch-all terminal would silently accept typos such as `1kk`. |
| 11 | Transformer methods for rules with adjacent optional slots MUST dispatch on node *type*, not position. | Positions shift when slots are absent. |
| 12 | Terminal priorities are used deliberately and commented in the grammar. Keywords share the priority of the generic name terminal so Lark re-types an exact match; block-scoped name terminals keep block terminators out of the top-level name. | Lark only collision-checks terminals of equal priority, so an accidental priority gap hides a conflict. |
| 13 | A lone `\r` is ordinary text only inside free-text terminals (written `\r(?!\r?\n)`); `\r?\n` is the only terminator. Anywhere else a lone `\r` is a syntax error. | Preserves the source-layer rule that only LF and CRLF end a line ([decision 0001](decisions/0001-source-text-policy.md)). |

### 6.4 Numeric literals

- Standard form: number, optional scale suffix (`t g meg k mil m u n p f a`, plus the observed `µ`), case-insensitive, `meg` for mega. `m`/`M` is milli, always. Letters after a number are part of the value text (ngspice ignores them).
- **RKM notation** (`2k7` = 2.7k, `4n7`, `R47`): the ngspice manual accepts it only in LTspice-compatibility mode. The grammar has dedicated RKM terminals; the parser option `rkm` (default off) decides whether they are accepted, for R and C values only, and the node records `notation="rkm"`. Letters follow IEC 60062 (IEC 60062:2016): `M` in mid-value position is mega for R and milli for C. ngspice reads R `1M0` as milli and C `4F7` as femto even in compatibility mode; such values are marked (`RKM_SOLVER_MISMATCH`). See [decision 0004](decisions/0004-element-and-value-grammar.md) and `docs/grammars/ngspice/numbers.md`.
- By the end of phase 2 the grammar MUST cover the full range of value specifications in the ngspice manual (scale-factor table and numeric forms), each with a spec entry and tests.
- Interpretation of the numeric value is out of scope (non-goal 6); the library stores the text.

### 6.5 Directives

- Known directives get typed nodes (`.tran`, `.ac`, `.dc`, `.op`, `.options`/`.option`, `.temp`, `.ic`, `.nodeset`, `.save`, `.meas`/`.measure`; `.step` for LTspice). `.probe` stays an `UnknownDirective` in v1 phase 1: it has its own sublanguage (decision 0005). These directives are top-level only; inside a `.subckt` body they are a `ParseError`.
- `.include` and `.lib` statements are **opaque**: preserved verbatim, not resolved, not read, not indexed. The library may add an `.include` (Section 7.9) but never interprets one.
- The first physical line is always the `Title` (implicit unless it is a `.title` statement; the node records which). `.title` may also occur later and replaces the displayed title; both source nodes are retained. `.end` is required (Section 6.3, rule 2). See [decision 0002](decisions/0002-grammar-structure-policy.md).
- An **unknown dot-command** is preserved as `UnknownDirective(raw)`: it is not topology, so preserving it is safe.
- An **unknown element letter** is an error (P5): an unparsed element would be a blind spot in the topology guarantee.

### 6.6 Opaque regions

`.control` ... `.endc` is matched as a single opaque block and preserved verbatim. It is not editable and not interpreted. (Rationale: it is a second language with its own dialect drift, and parametric work is done by running separate single-shot netlists.)

Conditional blocks (`.if` ... `.endif`) are likewise opaque: they are not parsed, and elements inside them are not indexed. Netlists whose topology depends on conditionals are out of scope (Section 7.8).

Opaque blocks are matched by grammar rules (nesting by recursion for `.if`), not by scanning. A `.control` or `.if` block after `.end` is a syntax error: the netlist ends at `.end`, even though ngspice would run a trailing `.control` block.

### 6.7 Device letters and dialects

A per-dialect matrix at `docs/grammars/<dialect>/devices.md` lists every device letter with its status: `supported`, `planned`, or `error`. The same letter can mean different devices across dialects (e.g. `P`, `U`, `Y`), which is why a union grammar is not possible. Letters unique to a dialect (ngspice `N`; LTspice `Ö`; qspice's non-ASCII letters) live only in that dialect's overlay.

**Phasing.** Both phases are part of v1 (device letters per Section 19). Phase 1 is a gate: phase 2 starts only after the maintainer has confirmed the phase 1 result following a hands-on review. v1 is complete when every element type in the dialect's device matrix is **supported** and the full range of value specifications is covered (Section 6.4): by the end of phase 2, all ngspice and LTspice elements MUST be supported. Until then, a netlist containing an element not yet supported fails with `UnsupportedConstruct` (P5).

---

## 7. Editing model (normative)

### 7.1 Statement classes

| Class | Contents | Permission |
|---|---|---|
| **Topology** | Element line structure: designator, element type, ordered node list; `.subckt` name, ports and body structure; `K` coupling targets | Read-only |
| **Properties** | Numeric values, formulas, instance parameters, model name (same model type), `.param` definitions, `.model` parameters, source stimulus specs | Editable (and `.param` addable) |
| **Directives** | `.tran`, `.ac`, `.dc`, `.op`, `.options`, `.temp`, `.ic`, `.nodeset`, `.save`, `.meas`, `.step`, unknown dot-commands | Addable, replaceable, removable |
| **Opaque** | `.control` blocks, conditional blocks, `.include` / `.lib` statements | Untouchable (an `.include` may be added, Section 7.9) |

### 7.2 Allowed operations

- Set a numeric value, or replace it with a formula or parameter reference (`R1 a b 10k` → `R1 a b {Rx}`).
- Set or add an instance parameter on an existing element.
- Set an element's model name. The new model MUST resolve (via the symbol table) and MUST have the same model type as the current one.
- Add or set a `.param`; edit `.model` parameters.
- Edit source stimulus specifications of existing sources.
- Add, replace or remove directives, with a placement strategy (after title, after the last `.param`, before `.end`, relative to an anchor `Line`).
- Add an `.include` of a harness file as a directive.

### 7.3 Forbidden operations (raise `TopologyError` or have no API)

Adding, removing or reordering elements; changing any node of an element; changing an element's type or designator; renaming a net; adding or removing `.subckt` definitions or changing their ports; editing opaque blocks.

### 7.4 Edit scope inside subcircuits

Elements inside `.subckt` are addressed by hierarchical path. An edit to the definition affects **every instance** and requires an explicit `scope=Definition` argument. The topology-safe per-instance alternative is an instance-parameter override on the `X` line (`X1 a b amp Rx=5k` where `.subckt amp` is defined elsewhere).

### 7.5 Edit plans

- An `Edit` is `(Span, replacement_text)` plus a reason string for diagnostics. An `EditPlan` is a list of edits.
- Application rules: edits are sorted by position; they MUST NOT overlap; zero-width insertions are allowed; multiple insertions at the same position keep their submission order; offsets always refer to the **original** text; the original `SourceText` is never mutated.
- Typical uses: value replacement (non-zero-width span), directive insertion (zero-width span at an anchor line boundary).

### 7.6 Write-time verification

On `save()` (and on request via `verify()`):

1. Apply the plan to the original text.
2. Re-parse the result with the same dialect. A parse failure is an error and nothing is written.
3. Compute the topology signature of the result and compare with the signature taken at load. Any difference raises `TopologyViolation`.
4. (Debug/test mode) assert that all text outside edited spans is identical to the original.

### 7.7 Topology signature

The signature is a canonical, hashable value built from typed nodes: for every element, `(scope_path, designator, element_type, ordered_nodes)`; for every subcircuit, `(name, ordered_ports)`; for every subcircuit instance, its connections and referenced subcircuit name. Comments, whitespace, values, params and directives are excluded.

### 7.8 Known limits (documented, not solved)

- **Expressions can hide connectivity.** A behavioral source formula such as `V(n1)*2` depends on nets not in the element's node list. The library guarantees node-list topology only.
- **`.include` / `.lib` content is outside the parsed file.** These statements are opaque and never resolved or read. Topology, symbol tables and reference resolution cover the main file only; references to models, subcircuits or params defined in included files are not visible to the library.
- **Conditional blocks are opaque.** Netlists in which `.if`/`.else`/`.endif` changes topology are explicitly out of scope; the topology guarantee does not extend into conditional blocks.
- **Replacement text is not validated.** In v1 the caller is responsible for the validity of the text it supplies. The library may take on more validation as the grammar matures.

### 7.9 Test harnesses

Adding sources, loads or probes changes the circuit and is out of scope. A separate tool prepares a harness (a file referring to existing net names); this library permits adding **only** an `.include` directive that pulls it in. The strict equality check in 7.6 therefore needs no exclusions.

---

## 8. Semantic layer (v1 scope: symbol tables and read-only queries)

In scope:

- **Element index** by designator and hierarchical path.
- **Symbol tables:** `params`, `models`, `subckts` with lookup by name.
- **Reference resolution** (read-only): element → model; subcircuit instance → definition; formula → parameter names. Parameter-name extraction from a formula is a best-effort identifier scan, not an evaluator; function names are excluded using a per-dialect list; limits are documented.
- **Topology queries:** `nets()`, `elements_on_net(net)`, `connections(designator)`, subcircuit ports. These let external tools (e.g. the harness tool, the controller's consistency checks) validate against the netlist without writing their own parser.
- **Diagnostics:** unresolved model/subckt/param references, duplicate definitions, dialect-gated syntax. Diagnostics are data, not exceptions.
- **Names and net identity:** case sensitivity of designators, models, params and subcircuits, and the identity of nets (including ground aliases), are defined per dialect in `docs/grammars/<dialect>/names.md`. The topology signature and all queries use these rules.
- **Scoping:** parameter scoping rules are defined per dialect in `docs/grammars/<dialect>/scoping.md`. Simulators are reported to differ here; the behavior MUST be validated against the solver before being relied on. Until then v1 documents a simple scope model and its limitations.

Out of scope: expression evaluation, unit arithmetic, hierarchy flattening, model-parameter validation.

---

## 9. Dialect support

### 9.1 v1 targets

| Dialect | Input | Notes |
|---|---|---|
| **ngspice** | `.cir`, `.sp`, `.net`, KiCad-exported netlists | Primary target. Reference: ngspice manual, SPICE3 manual. |
| **LTspice** | `.net` / `.cir` netlists | Netlists **only**. `.asc` schematics are converted by an external LTspice netlist-export step; the library never reads `.asc`. Reference: `analogdevicesinc/ltspice-reference`. |

LTspice can generate a netlist from the command line (spicelib's documentation describes this as its own workflow). The exact switch and its cross-platform behavior MUST be verified and documented in `docs/usage/ltspice-export.md`. Edits made to the exported netlist do not flow back to the `.asc`.

### 9.2 Planned

**qspice** and **xyce**, matching spicelib's dialect list. Both have device letters that collide with other dialects; each is a separate overlay.

### 9.3 Adding a dialect (checklist)

1. Add a `Dialect` enum member and registry entry.
2. Create `grammar/<dialect>.lark` (overlay on `core.lark`); build under `strict=True`.
3. Create `docs/grammars/<dialect>/` with `devices.md`, `names.md`, `scoping.md`, `numbers.md`, and one spec entry per construct.
4. Add dialect-specific nodes only where semantics differ; reuse common nodes otherwise.
5. Add corpus fixtures with provenance, and tests for every spec entry.
6. Add solver-backed tests if the solver is obtainable (optional).
7. Update `CHANGELOG.md` and the supported-dialects table in the README.

---

## 10. Testing strategy (normative)

### 10.1 Principles

- The **majority of coverage is solver-free.** Most assertions are about text: the output netlist has exactly the expected diff.
- Solver runs are an **additional validation layer** for more complex edits and for validating documented behaviors.
- Every supported construct has at least one accept test. Every forbidden operation has a negative test.

### 10.2 Tiers

| Tier | Scope | Examples |
|---|---|---|
| T1 Unit | values, spans, transformer | span arithmetic; `2k7` stored verbatim |
| T2 Grammar conformance | spec entry ↔ tests | accept and reject examples per construct, per dialect |
| T3 Round-trip | byte-exact identity | CRLF, mixed endings, missing final newline, BOM, tabs, trailing whitespace, blank lines, non-ASCII `µ`, continuations |
| T4 Edit (golden diff) | input + operation → expected output | assert only the intended lines changed, via diff |
| T5 Property-based (Hypothesis) | invariants over generated netlists | round-trip identity; any sequence of allowed edits preserves the topology signature; edits are idempotent |
| T6 Negative | forbidden or malformed | forbidden ops raise; unknown element letter errors with position; wrong-type value edits raise |
| T7 Architecture | structure of `src/` | no `subprocess`/`os.system` imports; layering respected (e.g. `import-linter`); every `.lark` builds with `strict=True`; no GPL dependency in runtime requirements |
| T8 Solver-backed (optional) | acceptance and results | Section 10.3 |
| T9 Differential (optional, dev-only) | compare against spicelib on inputs authored here | Section 12 |

### 10.3 Solver-backed tests

- **Location:** solver-launching code lives only under `tests/` (`tests/support/solvers.py`).
- **Discovery:** environment variable (`NGSPICE_EXE`, `LTSPICE_EXE`), then `PATH`, then platform default install locations.
- **Markers:** `@pytest.mark.solver("ngspice")` / `("ltspice")`. If the solver is absent the test skips with a clear reason. `--require-solver <name>` turns a missing solver into a failure for jobs that are supposed to have it.
- **What they check:** (a) solver accepts the netlist; (b) results move as expected after an edit (e.g. a divider ratio against its closed form); (c) an unedited round-trip yields identical results; (d) each documented behavior that is marked solver-validated.
- **Hygiene:** temporary directory per run, batch mode only, timeout, no GUI. Record solver name and version with every result; spec entries record which versions a behavior was validated on.
- **Environment:** LTspice-backed tests run locally on a Windows machine with LTspice installed. **No solver is required in CI for v1.** An ngspice job on a Linux runner is encouraged but not a required check. LTspice-generated netlist fixtures are committed so the LTspice grammar is fully testable offline.
- **Optional:** version-stamped observation files committed from solver runs, so offline CI can compare against recordings, refreshed by a scheduled job.

### 10.4 Coverage requirements

- 100% of constructs marked `supported` in the spec entries have at least one accept test (checked by a script in CI).
- Line coverage target: see Section 19.
- Solver-validated status is tracked per spec entry; it is not a coverage gate in v1.

### 10.5 Corpus and provenance

Fixtures live in `tests/corpus/<dialect>/<family>/`, each family with a manifest recording origin (authored here, export of an own KiCad project, LTspice export of an own circuit, derived from a manual), license, author and date. See Section 12.

---

## 11. Reference manuals and validation (normative)

### 11.1 References

| Dialect | Reference |
|---|---|
| ngspice | [ngspice manual (HTML)](https://ngspice.sourceforge.io/docs/ngspice-html-manual/manual.xhtml); [PDF](https://ngspice.sourceforge.io/docs/ngspice-manual.pdf). Cited as `[ngspice-manual] §<section> "<title>"`; edition and access date in `docs/references.md`. |
| SPICE3 (background) | https://www.macspice.com/ug/sec1.html |
| LTspice | https://github.com/analogdevicesinc/ltspice-reference |

### 11.2 Spec entries

Each supported construct has an entry under `docs/grammars/<dialect>/` with front matter and a short paraphrased description:

```yaml
id: NG-NUM-004
dialect: ngspice
construct: RKM numeric notation (2k7, 100R)
manual_ref: ngspice manual, numeric/RKM section (record exact section)
status: documented        # documented | observed | validated | disputed
validated_on: []          # [{solver: ngspice, version: ..., date: ...}]
tests: [tests/grammar/ngspice/test_numbers.py::test_rkm_*]
notes: accepted by ngspice only in LTspice-compatibility mode (per manual); verify
```

### 11.3 Rules

1. A manual statement is a hypothesis. The library relies on a behavior only after a test exists for it.
2. Where the manual and the solver disagree, record both in `docs/grammars/<dialect>/discrepancies.md`. The grammar follows the manual (strict reading); solver leniency is not accepted, and is recorded so users can be told why a file the solver runs is rejected. Where the manual is silent, behavior observed from the solver may be encoded only as a spec entry marked `observed` (rule 3). The LTspice references are thinner than the ngspice manual, so more LTspice behavior will rest on `observed` entries.
3. If the solver accepts something the manual does not mention, mark it `observed` and include it only with a test.
4. Spec entries cite manual sections; they paraphrase and do not paste tables or long passages (copyright, and the repository is MIT).

---

## 12. Licensing and provenance (normative)

- **License:** MIT. Runtime dependencies MUST be permissively licensed (Lark is MIT; verify when pinning).
- **spicelib is GPL-3.0.** No code, test files, or fixtures may be copied or closely adapted from it. spicelib's issue titles and changelog may be used as *facts* about which cases matter (e.g. RKM values, KiCad `.title`, hierarchical net names); its test sources MUST NOT be read for the purpose of reproducing them.
- **Allowed sources:** content authored in this repository; exports from the maintainer's own KiCad projects; LTspice exports of circuits authored here; behaviors observed from solvers; paraphrased manual content with citations.
- **Needs verification before use:** any file from ngspice or LTspice distributions (licenses are mixed per directory/file), and the license of `analogdevicesinc/ltspice-reference`.
- **Optional oracle:** spicelib MAY be installed as a dev-only dependency group for differential tests (T9). It MUST NOT appear in runtime requirements or published extras, its code MUST NOT be vendored, and T9 tests skip when it is absent.
- **Contributors and agents:** `CONTRIBUTING.md` and `AGENTS.md` MUST state that GPL-derived code or tests are not accepted and that sources are declared in the corpus manifest. Clean-room discipline is process hygiene and an audit trail, not a legal guarantee; training-data exposure of agents cannot be fully excluded. Consider a legal review of this policy.
- `docs/provenance.md` records the policy and each fixture family's origin.

---

## 13. Project infrastructure

- **Python:** minimum version per Section 19. Full type annotations; `py.typed` shipped.
- **Packaging:** `pyproject.toml` (PEP 621), `src/` layout, Lark `.lark` files included as package data. Versioning: SemVer via git tags.
- **Dev environment:** `uv` with a lockfile (proposed).
- **Lint/format:** `ruff`. **Types:** `mypy --strict` (or pyright). **Tests:** `pytest`, `pytest-cov`, `hypothesis`.
- **Pre-commit hooks:** ruff, ruff-format, mypy, YAML/TOML checks, merge-conflict check. Hooks that rewrite whitespace or line endings (`trailing-whitespace`, `end-of-file-fixer`, `mixed-line-ending`) MUST exclude `tests/corpus/` and golden files, because those files intentionally contain trailing whitespace, CRLF, and missing final newlines.
- **`.gitattributes`:** `tests/corpus/** -text` (and golden outputs) so Git never converts line endings in fixtures.
- **GitHub Actions:**
  - lint + type check;
  - test matrix across OS (Linux, Windows, macOS) and supported Python versions;
  - strict grammar build check and spec-coverage check;
  - docs link check;
  - coverage reporting;
  - optional ngspice job (non-required);
  - release on tag with PyPI trusted publishing;
  - Dependabot for actions and dependencies.
- **Branch protection:** required checks are lint, types, tests, grammar build, spec coverage.
- **LTspice:** no CI job in v1; local procedure documented in `docs/testing.md`.

---

## 14. Documentation plan

```
docs/
  architecture.md          this file
  design/                  deeper design notes (edit plans, topology signature, lexing); archive/ holds completed work records
  usage/                   quick start, editing recipes, LTspice export, error reference
  grammars/<dialect>/      devices.md, names.md, numbers.md, scoping.md, discrepancies.md, spec entries
  testing.md               tiers, running solver tests locally, writing golden tests
  provenance.md            licensing policy, corpus origins
  decisions/               short decision records (NNNN-title.md)
```

Rules: documentation changes ship in the same change as the code; usage examples are executed in CI (doctest or `pytest --doctest-glob`); public API has docstrings; a decision record is required for any change to a normative section.

---

## 15. Agent working agreement (source for `AGENTS.md`)

1. Read `docs/architecture.md` before changing code; follow the layering rule.
2. Never weaken an invariant (round-trip, topology, strict grammar) to make a test pass; raise it instead.
3. Build every grammar with `strict=True`; a conflict is a defect.
4. Every new construct needs a spec entry, tests, and a manual citation.
5. Do not read or reproduce GPL-licensed sources (including spicelib tests); declare fixture origins.
6. Do not add solver launching to `src/`.
7. Do not resolve items in Section 21 silently.
8. If the project uses OpenSpec, `openspec/config.yaml` should point to this document for project-level principles.

---

## 16. Public API sketch (illustrative, not frozen)

```python
from netlistmod import Netlist, Dialect, Placement

nl = Netlist.load("amp.cir", dialect=Dialect.NGSPICE)

nl.element("R22").set_value("2.2k")
nl.element("R1").set_value_formula("Rx")            # R1 a b {Rx}
nl.params.add("Rx", "22k", placement=Placement.AFTER_TITLE)
nl.directives.set(".tran 1u 10m")                    # replaces an existing .tran or adds one
nl.directives.add_include("harness.cir")

nl.element("D1").set_model("dmod2")                  # EditError if types differ

nl.element("amp/R1", scope="definition")             # explicit scope inside subcircuits

nl.nets()                                            # read-only topology queries
nl.references_to_param("Rx")

nl.save("amp.edited.cir")                            # re-parses and verifies topology
```

---

## 17. Errors and diagnostics

```
SpiceNetlistError
├── ParseError            (line, column, source excerpt with caret)
├── UnsupportedConstruct  (known to exist in the dialect, not yet supported)
├── EditError             (invalid edit: wrong value kind, unresolved model, ambiguous scope)
├── TopologyError         (operation not permitted)
├── TopologyViolation     (write-time check failed; nothing written)
└── EncodingError         (source bytes could not be decoded or text could not be encoded)
```

Diagnostics (non-fatal, code + location): `UNRESOLVED_MODEL`, `UNRESOLVED_SUBCKT`, `UNRESOLVED_PARAM`, `DUPLICATE_DEFINITION`, `DIALECT_GATED_SYNTAX`, `RKM_SOLVER_MISMATCH` (an RKM value the solver reads differently from IEC 60062; [decision 0004](decisions/0004-element-and-value-grammar.md)), `UNKNOWN_DIRECTIVE_PRESERVED`.

---

## 18. Compatibility and versioning

- SemVer. Before 1.0 the public API may change; changes are listed in `CHANGELOG.md`.
- Grammar changes that alter what parses are changelog-worthy.
- Supported solver versions for validated behaviors are listed per spec entry.

---

## 19. Confirmed decisions

| # | Issue | Decision |
|---|---|---|
| 1 | Package and import name | `netlistmod` |
| 2 | Minimum Python version | 3.13 |
| 3 | Build backend / dev tooling | hatchling + uv |
| 4 | Type checker | mypy `--strict` |
| 5 | Grammar composition mechanism | implementer's choice (Lark `%import` vs. concatenation), subject to strict build per dialect |
| 6 | Device-letter phasing | Phase 1: R, C, L, V, I, D, X, K plus common directives. Phase 2: Q, J, M, E, F, G, H, B, S, W, T, plus the remaining ngspice letters A (XSPICE code models), N, O, P, U, Y, Z and every LTspice device letter not in phase 1 (the LTspice matrix is written in M8). By the end of phase 2 all ngspice and LTspice elements MUST be supported. Both phases are v1; phase 2 starts after the maintainer's hands-on review of phase 1. |
| 7 | Empty `.title` | Accept (title text optional) |
| 8 | Handling of RKM `M` ambiguity | add compatibility mode option to interpret values for R and C per RKM with automatic fallback to standard SPICE notation. |
| 9 | `.control` blocks | Opaque, preserved verbatim |
| 10 | Unknown dot-commands | Preserved as `UnknownDirective` |
| 11 | Line-coverage target | 90% |
| 12 | Scoping model for `.param` in subcircuits | Document a simple model; validate per dialect against the solver |
| 13 | Handling of `.include`/`.lib` | Opaque statements in v1: not resolved, read or indexed. Conditional blocks are also opaque; topology-changing conditionals are out of scope |
| 14 | ngspice job in CI | Optional, non-required |
| 15 | Docs site generator | Plain Markdown in `docs/` |
| 16 | Name case sensitivity and net identity | Defined per dialect in `docs/grammars/<dialect>/names.md` |
| 17 | Dialect selection | Always explicit from the caller; no default, no auto-detection |
| 18 | Validation of caller-supplied replacement text | None in v1 (caller's responsibility) |
| 19 | ngspice structural source policy | Strict, per the manual: the first line is always the title (flagged implicit or explicit); `.title` later replaces the displayed title; `.end` is required and last, with only blank lines after it; a missing final newline after `.end` is tolerated; `.control` after `.end` is rejected. See [decision 0002](decisions/0002-grammar-structure-policy.md). |
| 20 | Grammar composition and registry | Dialect overlays import `core.lark`; `grammar/loader.py` owns the registry; all syntax, including continuations and opaque blocks, is expressed in the grammar (P13). See [decision 0003](decisions/0003-grammar-composition-and-opaque-regions.md). |
| 21 | Strictness policy | The grammar follows the reference manuals; solver leniency is not accepted (P5, P8, §11.3). The only exception in v1 is the RKM mode option (decision 8). Further exceptions need a decision record. |
| 22 | Continuation and comments | Continuation is `+` on the immediately following line or a trailing double backslash; comment and blank lines may not intervene; `.title`, `.lib` and `.include` cannot be continued. End-of-line comment delimiters are `;`, `$` and `//` (a standalone `;`, `$` or `//` line is rejected; `.end` takes no trailing comment). All per the ngspice manual §2.4.4 and §2.4.5 (strict reading). |

---

## 20. Known risks

- **Continuation lines** join across intervening comments and blank lines in ngspice 47; this behavior and span tiling are covered by solver and property tests.
- **Scoping rules** differ between simulators and are not yet validated against solvers.
- **Hidden connectivity** in behavioral expressions can defeat the topology guarantee (documented limit).
- **Encoding:** verified for LTspice 26.1.1 (exports are UTF-8 without a BOM; see `docs/usage/ltspice-export.md` and decision 0001). Re-verify on LTspice upgrades and on KiCad exports.
- **LTspice CLI export** switch and behavior are unverified.
- **Agent contamination:** training exposure to GPL code cannot be excluded; process controls and review are the mitigation.
- **Grammar surface** grows with every dialect; the spec-entry checker and strict builds are the control.
- **Conditional blocks.** The M2 parser preserves nested `.if` blocks opaquely. The valid `.if (1)` … `.endif` form is accepted by ngspice 47; the earlier `.if 1` probe was invalid and is superseded by decision 0002.

---

## 21. Unresolved questions and deferred items

**Unresolved (need a decision before the edit layer is designed)**

1. **Edit lifecycle.** Section 3 says the document is re-parsed "after every edit set" and Section 7.6 verifies on `save()`. Open points:
   - Are edits staged (applied only at save or an explicit commit) or applied eagerly?
   - Can the caller read back after an edit (e.g. `references_to_param` right after `params.add`)?
   - What happens to element handles after a re-parse?
   - What is the boundary of an "edit set"?
   - How are two edits to the same span handled (error or last-wins), given that edits MUST NOT overlap?
2. **Model references vs. includes.** Setting a model requires the new model to resolve (Section 7.2), but models defined in `.include`/`.lib` files are not visible (Section 7.8). Should `set_model` then fail, warn, or be allowed with a diagnostic? The same question applies to the `UNRESOLVED_*` diagnostics.

**Deferred to design documents and implementation (resolve with tests)**

- Text conventions for inserted lines (EOL style, EOF without newline, keyword case, `.param` form) and placement semantics.
- Matching and upsert semantics of directive and `.param` operations (singleton vs. repeatable directives, existing names, subcircuit scope).
- The line model for continuation lines, interleaved comments and anchor-relative insertion.
- Hierarchical addressing and scope selection for subcircuit elements (Section 16 is illustrative only).
- ~~Interaction of the RKM mode option (a parser argument) with the grammar and diagnostics.~~ Resolved by [decision 0004](decisions/0004-element-and-value-grammar.md).
- The diagnostics API (delivery and severity).
