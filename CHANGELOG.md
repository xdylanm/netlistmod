# Changelog

## Unreleased

- Add the read-only document layer (M5, decision 0006): `Netlist.load`,
  `Netlist.from_text` and `Netlist.from_source` (explicit dialect), logical
  `Line`/`Lines` with search and insertion points, definition `Scope`s with
  `params`/`models`/`subckts`/`elements` tables, `Reference` resolution
  (element → model, X → subcircuit and defaults, K → inductors, `.dc` and
  `.save i(...)` → elements, formula names → parameters), a `TopologyView`
  (`nets`, `elements_on_net`, `connections`, `ports`) with `Net` and
  `Connection`, the exact-text `TopologySignature` with `digest()`, and
  `Diagnostic`/`DiagnosticCode` (new codes `UNRESOLVED_ELEMENT`,
  `DUPLICATE_ELEMENT`, `SUBCKT_PORT_MISMATCH`, `PARAM_USED_BEFORE_DEFINITION`,
  `ENDS_NAME_MISMATCH`). Names and scoping follow `names.md` and `scoping.md`,
  validated against ngspice 47.
- Add a formula grammar (`grammar/formula.lark`, `NG-FML-001`) that finds the
  parameter names in brace and quoted formulas without evaluating them.
- Grammar change that alters what parses: `.global` is a typed
  `GlobalDirective(nodes)` (`NG-GLB-001`) instead of an `UnknownDirective`, needs
  at least one node, and is rejected inside a subcircuit body (ngspice 47
  accepts it there: recorded discrepancy).
- `UnknownDirective` records `name_span`.
- Parse ngspice statements and directives into typed nodes with spans
  (decision 0005): `ParamStatement`, `ModelStatement`, `SubcktDefinition` (with
  its body and `EndsLine`; definitions nest), and the `Directive` subclasses
  `TranDirective`, `AcDirective`, `DcDirective` (`DcSweep`), `OpDirective`,
  `OptionsDirective` (`OptionItem`), `TempDirective`, `IcDirective`,
  `NodesetDirective` (`NodeCondition`), `SaveDirective` (`OutputVector`) and
  `MeasureDirective` (shallow). New value type `Identifier` for option values
  such as `method=gear`.
- Grammar changes that alter what parses: `.param`, `.model`, `.subckt`,
  `.ends`, `.tran`, `.ac`, `.dc`, `.op`, `.options`/`.option`, `.temp`, `.ic`,
  `.nodeset`, `.save` and `.meas`/`.measure` are no longer `UnknownDirective`
  and are checked strictly per the manual. Rejected: bare `.param` expressions,
  the reserved names `time`/`temper`/`hertz`, a `.subckt` port `0`, the analysis,
  option and output directives, `.control`, `.title` and `.end` inside a
  subcircuit, a stray `.ends`, and malformed directive arguments. An
  unterminated `.subckt` and an unclosed `(` are reported at their opener.
  `.opt`, `.probe`, `.print` and other dot-commands stay `UnknownDirective`.
- The `params:` error message now covers `.subckt` lines as well as `X` lines.
- `.save` accepts the standard output-vector forms of the manual (`v(a, b)` with
  blanks, `vr`, `vi`, `vm`, `vp`, `vdb`, `i(src)`) and records their function and
  node or source names; `ir(…)` … `idb(…)` are rejected (M4 review round 1).
- Parse the phase 1 ngspice element lines (R, C, L, K, V, I, D, X) into typed,
  immutable nodes (`Resistor`, …, `SubcktInstance`, base `Component`) with
  value slots (`NumericValue`, `Formula`, `ModelReference`, `ParamAssignment`,
  `AcSpec`, …) and a span for every field (decision 0004).
- `parse()` takes a keyword-only `rkm` option (default `False`). RKM values
  (`2k7`, `4R7`, `4p7`) are a `ParseError` without it. With it they are read per
  IEC 60062 for R and C, and values ngspice reads differently (`1M0`, `4F7`) are
  marked `solver_mismatch`.
- Grammar changes that alter what parses: R, C, L, K, V, I, D and X lines are now
  parsed instead of raising `UnsupportedConstruct`. Source stimulus functions,
  `DISTOF`, the capacitor `q=` form and other element letters still raise it,
  and `params:` on an `X` line is a `ParseError`. A supported letter where no
  element may stand (after `.end`) is a `ParseError`.
- `parse()` reports every syntax error before an RKM value, unsupported form or
  `params:` that it rejects.
- Removed the 20,000-line timing test of the structural parser: no performance
  bound applies at this stage.
- Implemented byte-preserving source text and spans, including BOM-aware
  decoding, configurable fallbacks, atomic file writes, and line/column
  diagnostics.
- Added the public error hierarchy, `Dialect` enum, and package exports.
- Added a strict, cached ngspice LALR parser for source structure, including
  grammar-defined syntax, typed title/comment/directive/opaque nodes,
  immediate continuation spans, required final `.end`, and positioned errors
  for unsupported element lines.
- Added ngspice 47 discrepancy probes, grammar/spec traceability, positive and
  negative structural corpora, property/performance tests, and wheel resource
  checks.
- Spec entries now cite the ngspice manual as `[ngspice-manual] §<section>
  "<title>"` against the edition recorded in `docs/references.md`; the spec
  checker enforces the form and rejects the previous, incorrect section numbers.
- `//` is an end-of-line comment delimiter alongside `;` and `$` (manual
  §2.4.4); a standalone `//` line is still rejected, and a path containing
  `//` must be quoted.
- Each line of a continued statement may end in an end-of-line comment
  (manual §2.4.5). Statement nodes now have `trailing_comments` (a tuple of
  spans) instead of `trailing_comment`.
- `.include` and `.lib` can no longer be continued (manual §2.4.5); a `+`
  line after them is a positioned syntax error.
- A line ending in `\\` continues a statement (manual §2.4.5); the next line
  must start with statement text.
- Made `SourceText.write()` preserve existing permission bits and write through
  symlinks; new files use normal umask-derived permissions.
