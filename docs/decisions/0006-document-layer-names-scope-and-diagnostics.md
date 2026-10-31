# 0006 — Document layer: names, scope and diagnostics

- **Status:** accepted (2026-10-31, maintainer; the section 2 decisions of
  [m5-tasks.md](../design/archive/m5-tasks.md) were accepted on 2026-10-31 and this record after review)
- **Date:** 2026-10-31
- **Context:** M5 builds the read-only document layer (architecture §3 layer [3], §8): the
  `Netlist`, its lines, symbol tables, reference resolution, topology view and signature, and
  diagnostics. Several architecture §21 items were deferred to this point (the line model, the
  diagnostics API, hierarchical addressing) and §8 left names, net identity and scoping to
  per-dialect documents. ngspice 47 was probed for each rule ([m5-tasks.md](../design/archive/m5-tasks.md)
  section 7, re-recorded in `tests/solver/test_ngspice_solver_document.py`).
- **Decision:**
  1. **Entry points.** `Netlist.load(path, *, dialect, rkm=False, fallback_encodings=...)`,
     `Netlist.from_text(text, *, dialect, rkm=False)` and `Netlist.from_source(source, *,
     dialect, rkm=False)`; `dialect` has no default (decision 17). The netlist is immutable in
     M5; `to_bytes()` returns the original bytes; `save()` and editing arrive in M6. Queries
     return the M3/M4 node objects.
  2. **Line model.** A `Line` is one *logical* item: a statement with its continuation lines
     and end-of-line comments, a blank line, a comment line or a whole opaque block. Its span is
     the item span the parser tiles. A line has `item`, `span`, `first_line`/`last_line`
     (1-based physical lines) and `scope`; a subcircuit definition is one line whose `body` is a
     nested `Lines`. `insert_before(line)`/`insert_after(line)` return zero-width spans at the
     line's span start and end, which are physical-line boundaries. `find`, `find_all` and
     `index_of` (identity) search by node type, entering bodies with `recursive=True`.
  3. **Names and net identity** (`docs/grammars/ngspice/names.md`). Designators, model,
     subcircuit, parameter and node names compare case-insensitively by ASCII lower-casing.
     `0` and `gnd` (any case) are one ground net; `00` is a distinct net. Nets in a subcircuit
     definition are local to it except ground, its ports (bound to the instance's nodes) and
     `.global` nodes. `.global` is a typed `GlobalDirective(nodes)`, top level only: inside a
     body it is rejected like the other top-level statements (decision 0005). The `ngbehavior`
     and `no_auto_gnd` settings live outside the netlist and are ignored.
  4. **Scope model** (`docs/grammars/ngspice/scoping.md`). A top-level `.param` is global; a
     definition's defaults and body `.param` lines are local and mask global names. Models and
     subcircuits are local to the definition that contains them and visible in nested
     definitions (§2.6.1, validated; §2.11.4's "global and must be unique" is recorded as a
     conflict). Lookup is own scope, then each enclosing scope, independent of file order. A
     parameter used before its definition still resolves, with `PARAM_USED_BEFORE_DEFINITION`
     (strict reading of §2.11.1). A repeated `.param` resolves to the last assignment
     (`DUPLICATE_DEFINITION`, info); a repeated `.model` or `.subckt` in one scope resolves to the
     first, as ngspice 47 does (`DUPLICATE_DEFINITION`, warning). Element references (`K`
     inductors, `.dc` sources, `.save i(src)`) are looked up in their own scope only.
  5. **Hierarchical addressing.** M5 addresses definition scopes, not expanded instances: a
     scope is a tuple of subcircuit names (`()`, `("amp",)`, `("amp", "inner")`) and queries take
     `scope=`. There is no string path form and no instance-expanded view in M5.
  6. **Topology signature.** The signature uses the exact text of every topology token: each
     element's scope, designator, type and ordered nodes; each definition's name and ordered
     ports; each `X` line's nodes and subcircuit name; each `K` line's inductor references; and
     the `.global` node set. It excludes comments, whitespace, values, parameters, other
     directives and opaque blocks. It is hashable and ordered, with a stable `digest()` (SHA-256
     of a canonical JSON encoding). Queries keep the `names.md` rules. `.global` is topology.
  7. **Diagnostics API.** A frozen `Diagnostic(code, severity, message, span, line, column)`,
     `code` a `DiagnosticCode` string enum, `severity` `"warning"` or `"info"`.
     `Netlist.diagnostics` is a tuple computed once at load, in source order, never raised. New
     codes: `UNRESOLVED_ELEMENT`, `DUPLICATE_ELEMENT`, `SUBCKT_PORT_MISMATCH`,
     `PARAM_USED_BEFORE_DEFINITION` (warnings) and `ENDS_NAME_MISMATCH` (info).
     `MODEL_TYPE_MISMATCH` is deferred to M6, with the same-model-type rule of §7.2.
  8. **Unresolved references and includes** (the diagnostics half of §21 question 2). An
     `UNRESOLVED_*` diagnostic whose searched scopes contain an opaque `.include` or `.lib` is
     info, and its message says the name may be defined there; otherwise it is a warning. The
     `set_model` half stays open for M6.
  9. **Formula names.** A separate strict Lark grammar, `grammar/formula.lark`, parses the text
     of brace and single-quoted formulas per §2.11.5 (P13). An identifier followed by `(` is a
     call, `v(...)`/`i(...)` arguments are node and source names, and a bare word of the
     reserved list (data in `formula-reserved.json`) is not a parameter. Text the grammar does
     not accept gives no references and no error. Spec entry `NG-FML-001`.
  10. **Corpus provenance:** `document_basic` is authored in this repository by `xdylanm`, MIT.
- **Consequences:**
  - Architecture amendments: §4 (package layout), §5.2 (`GlobalDirective`), §5.4 (logical
    lines, insertion points), §7.1 (`.global` is topology), §7.7 (exact-text signature), §8
    (definition-scope addressing, model/subcircuit locality, the signature's exact text), §17
    (new codes and severities), §21 (line model, diagnostics API and the read-only part of
    hierarchical addressing resolved; the diagnostics half of question 2 recorded).
  - API, shapes and the encoding of signature entries: [m5-document.md](../design/m5-document.md).
    M6 builds its edit API on them.
  - Behavior change: `.global` was an `UnknownDirective` and was accepted inside a subcircuit
    body; it is now typed and rejected there (ngspice 47 accepts it: `discrepancies.md`).
  - Known limits: elements, models and parameters inside `.if` blocks and included files are
    not seen; an unresolved reference with only an `.if` block in its scopes stays a warning;
    plain `.save` names (`in`, `vin#branch`), `@dev[param]` and `.ic`/`.nodeset` nodes are not
    references; a formula with `!`, `#` or `%` in a name, or with the verbose operators, gives
    no references.
- **Amendment (2026-10-31, M5 review round 1, R1):** item 4's `PARAM_USED_BEFORE_DEFINITION` is
  judged within one scope. It fires only when the reference and the definition it resolves to
  are in the same scope and the reference comes before that scope's first definition of the
  name (a top-level `{rx}` before the top-level `.param rx`, or a body `{k}` before the body's
  own `.param k`). A reference that resolves to an enclosing scope's parameter gets no warning:
  §2.11.1 orders assignments through the expanded circuit, and a body is expanded where it is
  called, not where it is defined, so a definition placed before the global `.param` it uses is
  not late. Ordering such a reference against the `X` lines that call the definition would need
  an instance-expanded view, which §8 keeps out of scope.
