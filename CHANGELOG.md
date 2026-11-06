# Changelog

## Unreleased

**Phase 1 summary.** A source-preserving editor for SPICE netlists, with no release yet.

- **Dialects:** ngspice, validated on ngspice 47, and LTspice, validated on LTspice 26.1.1 on Windows. The caller always selects the dialect.
- **Constructs:** R, C, L, K, V, I, D and X elements; `.param`, `.model`, `.subckt`; `.tran`, `.ac`, `.dc`, `.op`, `.options`, `.temp`, `.ic`, `.nodeset`, `.save`, `.meas`, `.global`; LTspice `.step`. Other dot-commands are preserved verbatim, and `.control`, `.if`, `.include` and `.lib` are opaque.
- **Guarantees:** an unedited save is byte-identical; an edit changes only its own text; each edit is re-parsed and checked against the topology signature of the load, and nothing is written if a check fails; `src/` never launches a solver.
- **Known limits:** Q, M and other device letters wait for phase 2. Contents of opaque items are not read. LTspice's `.end` is required although LTspice lets it be omitted. About 300 nested `.if` levels raise `RecursionError`. Python 3.13 is declared but untested: every run was on 3.14. No stress or performance testing was done (decision 0010), and CI starts with phase 2.

Changes:

- B now loads and edits on both dialects, as `BehavioralSource`, with its `quantity` (`v` or `i`, and on LTspice `r` or `p`), `expression` and trailing parameters (M15, decision 0016). An expression may be in braces, in quotes, or bare; a bare one may hold blanks and continuations and ends at the first trailing parameter.
- The expression forms of the dependent sources load: ngspice E `vol=` and G `cur=` (in quotes or braces) and `value` on both, and LTspice `value=` on E, F, G and H. They keep their M14 classes, with `value` `None` and the text in `expression`, so `ControlledSource.value`, `Cccs.control` and `Ccvs.control` may now be `None`. TABLE, POLY, Laplace, FREQ and AND/OR/NAND/NOR stay unsupported until M15b (M15).
- A capacitor's charge form (ngspice `q=`, LTspice `Q=`) and LTspice's `Flux=` and hysteretic inductor load, as `Capacitor.charge` and `Inductor.flux` (M15).
- Add `set_expression`, which replaces an expression and keeps its delimiters; `set_param` covers B's parameters. Add `Netlist.expression_reads`, the nets and sources an expression reads, which stay out of the topology signature, and the diagnostic `UNRESOLVED_NODE` (M15).
- The formula scan reads `{…}` inside a bare expression, continuations and LTspice's `~`; LTspice's `time` in a B or `value=` expression and `x` in `Q=` and `Flux=` are not parameter references (M15).
- Add the behavioural files to the `controlled_sources` corpus families, with the M15b ones marked pending (M15).
- E, F, G, H, S and W now load and edit on both dialects, as `Vcvs`, `Vccs`, `Cccs`, `Ccvs`, `VoltageSwitch` and `CurrentSwitch` (M14, decision 0015). Control nodes are nodes, and F, H and W name their controlling source in `control`; both are in the topology signature, so an edit cannot rewire a control. A controlling source is found in its own scope only, with `UNRESOLVED_ELEMENT` and the new `CONTROL_SOURCE_MISMATCH`. S and W take SW and CSW models. The nonlinear forms (`VALUE`, `TABLE`, `POLY`, `value=`, `table=`, `Laplace=`, `vol=`, `cur=`) stayed unsupported in M14.
- Add `set_switch_state`; `set_value` and `set_formula` set a dependent source's gain, and `set_param` its `m=` on an ngspice F or G (M14).
- Add the `controlled_sources` corpus families (M14).
- Q, M, J and Z now load and edit on both dialects, as `BipolarTransistor`, `Mosfet`, `Jfet` and `Mesfet` (M13, decision 0014). The model is the last name before any area, flag or parameter; ngspice takes 3 to 5 nodes on Q and M, LTspice 3 or 4, and J and Z take 3. The nodes are those written, so an omitted substrate is not added. A model named with a plain number or `off` is a `ParseError`. `set_model`, `set_param` (with `area` positional on J and Z, and on an LTspice Q) and `set_model_param` cover them, and `MODEL_TYPE_MISMATCH` knows their model types, with NIGBT and PIGBT on LTspice's Z only.
- `.model` takes a bare `pchan` or `nchan` (`ModelStatement.flags`) and a dotted value such as `version=3.3.0`, kept as an `Identifier` (M13). Real BSIM files and `jellybean.lib`'s `BS250_OJ` need them.
- Add the `kicad_transistors` and `ltspice_transistors` corpus families. A corpus manifest's `solver` field may name `external` files, such as `jellybean.lib` from `OPENJELLYBEAN_LIB`, which the solver sweeps copy in or skip (decision 0014 item 10).
- The transformer and the edit operations are split by element family (`model/_rules_*.py`, `edit/_ops_*.py`), with no change in behaviour (M13).
- The test suite runs LTspice on a hidden Windows desktop, so that it no longer takes the foreground window on every run. Tests only; the library is unchanged.
- Source functions now load and edit, as `VoltageSource.stimulus` and `CurrentSource.stimulus`, a typed `SourceSpec` (M12, decision 0013). ngspice: PULSE, SIN, SINE, EXP, PWL, SFFM, AM, TRNOISE, TRRANDOM, EXTERNAL, DISTOF1, DISTOF2 and the RF port parameters. LTspice: PULSE, SINE, SIN, EXP, SFFM, PWL with its file, repeat and scale forms, `wavefile=`, the trigger parameters, and on I `tbl=` and `step(...)`. `half_rectifier.net` now loads.
- Add `set_stimulus`, `set_stimulus_arg` and `remove_stimulus`, in batches too. `set_stimulus` leaves the DC and AC parts alone (M12, decision 0013). `set_param` edits ngspice's `portnum` and `z0`.
- **Behaviour change:** a `.lib name` … `.endl` block is now an opaque block on both dialects (M11, decision 0012). On ngspice its body no longer counts as topology, so a netlist with one has a different topology signature; on LTspice such a netlist now loads instead of raising `ParseError`. Neither solver runs a block in a netlist. Any other `.lib` line stays an opaque statement.
- **Behaviour change:** an opaque `.if` or `.lib` block now counts like an `.include` for unresolved names (M11 H8, decision 0012): an `UNRESOLVED_*` diagnostic in that scope is `info` and says so, and `set_model` accepts such a name with `allow_external=True`.
- **Renamed:** the diagnostic code `UNKNOWN_DIRECTIVE_PRESERVED` is now `UNTYPED_DIRECTIVE_PRESERVED`, because the commands that get it are often documented ones (M11 H6, decision 0012). Code that filters on the old name must change. `UnknownDirective` keeps its name.
- `directives.add` writing a second line of one kind is now documented and tested behaviour, because ngspice runs two `.ac` or `.dc` lines; `directives.set` is the upsert (M11, decision 0012). LTspice's `.end` stays required.
- A string as a scope, or a string passed to `parse`, now raises `TypeError` (M11 H5).
- Messages no longer cite internal documents, and a citation of the ngspice manual says so (M11 H7).
- Add CI on Linux and Windows with Python 3.13 and 3.14, with no solver, plus Dependabot (M10, decision 0011). macOS is not tested or claimed.
- A second upsert of one target in a batch is now an `EditError` naming the target, raised when it is submitted, whether or not the target exists yet (M9 H1, decision 0010 item 5). This covers `set_param`, `set_instance_param`, `set_model_param`, `params.set`, `directives.set` (by kind, or by `.step` quantity), `add_include`, `set_ac` and `set_dc`. Before, a repeated new target could write `m=1 m=2`, or two `.param` or `.tran` lines, one of which stops LTspice. Golden diffs do not change.
- A line that ends before its fields do now has the parse-error reason "this line ends too early", and `expected` leaves out separators, continuations and comments. Text after `.end` has a reason saying the netlist ends there, and is a `ParseError` even when its first letter is a planned device, which was an `UnsupportedConstruct` before. Line and column do not change (M9 H2). `tests/grammar/ngspice/tree_snapshot.json` is regenerated for this: 15 rejected files changed. 14 lost those names from `expected`, `structure_rejects/text_after_end.cir` went from `UnsupportedConstruct` to `ParseError`, and no node or position changed.
- Two edit messages are corrected (M9 H3): `directives.add(".model …")` says a `.model` line cannot be added and that `set_model_param` edits an existing one, and `Placement.after(line)` with a line of a subcircuit body says so, rather than calling the line stale.
- Public docstrings now cover LTspice: `set_param`, `set_model`, `remove_value`, `DirectiveEditor.set` and `Net` (M9 H4).
- Add the review package for phase 1 (M9, decision 0010): a README quick start, usage guides for both dialects, an error reference (`docs/usage/errors.md`), the demo `docs/usage/examples/edit_and_simulate.py`, and the broader oracle. The four design notes are now living references under topic names (`docs/design/elements.md`, `statements.md`, `document-layer.md`, `edit-layer.md`). New tests check that relative Markdown links resolve, and that the notes name each public name.
- `docs/usage/examples/edit_and_simulate.py` also runs `.op` on your own netlist and prints a net's voltage, with `--edit-value`, `--probe` and `--rkm` (M9 hands-on use).
- Add the LTspice dialect (M8, decision 0009). `Dialect.LTSPICE` parses, indexes, edits and
  verifies netlists with the phase 1 elements, through the overlay `ltspice.lark` on a `core.lark`
  that now holds only what both dialects share. ngspice parsing is unchanged. New for LTspice: the
  native embedded decimal in every value slot, closed lists of dot-commands and element parameters,
  a typed `.step` with an upsert, `.ic I(L...)`, Unicode name folding and `$G_*` global nodes.
  `parse_formula`, `reserved_words`, `device_matrix` and `fold` now take a dialect.
- Validate the LTspice dialect on LTspice 26.1.1 (M8 checkpoint B). A shared raw reader
  (`tests/support/raw.py`) and an LTspice harness (`tests/support/ltspice.py`); every accept fixture
  runs and gives identical results after an unedited save; edits are checked against closed forms;
  every `LT-*` entry and rule row has solver evidence. In LTspice, a definition in scope now masks a
  built-in constant (`.param pi=3k` gives a reference to `pi`), and a bare function name, `time` or
  `freq` is an ordinary parameter name, so `{sqrt}` alone gets `UNRESOLVED_PARAM`. New diagnostic
  `NODE_INTO_INSTANCE`: LTspice connects a node named `x1:n` to `n` inside the instance `X1`, which the
  library does not model.
  LTspice raw files and logs are never committed. `--require-solver` may be repeated (only the last
  value used to count). The `DUPLICATE_DEFINITION` message for a repeated LTspice `.model` or
  `.subckt` now says it stops LTspice only when the definition is used.
- Local solver validation (M7, decision 0008). Test and documentation changes only; no
  library code changed. A shared ngspice harness (`tests/support/ngspice.py`: `run`, a
  clean-room ASCII raw-file reader, `op`/`ac`/`tran_rows`, stub wiring through the edit API)
  replaces the per-file helpers; every accept fixture runs in ngspice (stubs for includes kept
  outside the repository, a `solver` field in corpus manifests) and gives identical results
  after an unedited save; every M6 edit operation is checked against a closed form, plus a
  solver-backed Hypothesis test. Spec-entry and rule statuses are now checked against their
  solver evidence; `NG-DIR-001`, `NG-NOD-001`, `NG-PAR-001`, `NG-UNS-001`, `NG-VAL-001` and
  scoping rule S9 are `validated`. New discrepancies: a stray `.endc`, node names with
  `[ ] % < ~ (`, and `params:` on an X line run in ngspice 47 and stay rejected. The pytest
  header names each solver and its version.
- Add the edit layer (M6, decision 0007). `netlistmod.Netlist` (a subclass of the
  read-only `netlistmod.document.Netlist`) gains `set_value`, `set_formula`,
  `set_param`, `set_model` (type-checked, `allow_external=True` for models an
  `.include` may define), `set_dc`, `set_ac`, `set_coupling`,
  `set_instance_param`, `set_model_param`, `params.set` (upsert),
  `directives.add/replace/remove/set` with `Placement`, `add_include`, `batch()`,
  `apply(plan)`, `verify()` and `save(path=None)`. Edits are immutable and eager:
  each returns a new netlist, re-parsed and verified (signature against the load,
  opaque items, text outside the edits, slot checks); `TopologyError` and
  `TopologyViolation` guard topology. Low-level `Edit`, `EditPlan`, `SlotCheck`
  and `apply_edits` are public. Element scopes need `in_definition=True`.
- M6 review round 1 (decision 0007 amendment 1): whole `.control`/`.if` blocks and
  `.include`/`.lib` statements may be added, removed or replaced through `directives`
  (an edit that cuts into one is a `TopologyViolation`); directive text may be a list
  of physical lines (continued statements, blocks); `set_model` adds a model to an R,
  C or L line without one, and the new `remove_value` drops its value; `set_model_param`
  fills empty parentheses. `ModelStatement` gains `open_paren_span` and
  `close_paren_span`.
- New diagnostic `MODEL_TYPE_MISMATCH` (warning): an element's resolved model has
  a type not allowed for its letter (R → `R`, C → `C`, L → `L`, D → `D`;
  `document/model-types.json`).
- `Netlist.load`, `from_text` and `from_source` return `Self`.
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
