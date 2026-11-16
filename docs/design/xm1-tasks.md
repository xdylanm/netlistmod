# X-M1 task list — xyce structure, names, numbers; R, C, L, V, I, D, X, K

> **Status:** ACTIVE — stage 2 (implementation)
> **Follows:** [X-M0](./archive/xyce/xm0-tasks.md) and [decision 0026](../decisions/0026-the-xyce-dialect.md). Plan: [xyce-plan.md](./xyce-plan.md) sections 3 to 6 and 8. Governed by [architecture.md](../architecture.md) (§2, §6, §7, §9.3, §10, §11, §12).

## 1. Scope

X-M1 makes the hidden xyce dialect read real netlists: the structure, names and numbers, parameters and expressions, subcircuits and models, and the first element letters. The dialect stays hidden (decision 0026 item 4).

- **In:**
  - **Structure:** the title, comments and continuation (`*`, `;`, `+` across comments), indented lines (decision X-D1), and whether `.END` is required (decision 0026 item 5).
  - **Names:** case, legal characters, ground, `$G` globals (X-D3), `:` hierarchy and `X1:node` on device lines (X-D2), `.PREPROCESS REPLACEGROUND`, `.GLOBAL`. `names.md` and `scoping.md` written.
  - **Numbers:** the scale factors (with `X` = 1e6 and `mil`, and no `a`), `rkm` refused.
  - **Parameters and expressions:** `.PARAM`, `.GLOBAL_PARAM`, `.FUNC`; braces, quotes and bare expressions (X-D5); the xyce formula grammar and reserved words (`**`, `^` as XOR, `log` base 10, `R1:R` accessors) as far as the expression scan needs them.
  - **Statements:** `.MODEL` (xyce's model types; binned names such as `nch.1`), `.SUBCKT`/`.ENDS` (`PARAMS:`, nesting, node 0 not a port), `.INC`/`.INCL`/`.INCLUDE`, `.LIB` (call and block), `.GLOBAL`, `.PREPROCESS REPLACEGROUND`.
  - **Elements:** R, C, L (the model before the value), V and I (DC and AC parts only; the transient functions stay refused until X-M3), D, X (`PARAMS:`, `M=`), K (with an optional model).
  - **The document and edit layers** for these: the X-M1 entries of the plan's section 8.1 (names, diagnostics, the index, model types, edits), so that topology, diagnostics and the edit methods work on xyce for these letters.
  - **Spec entries, corpus files with manifests, and solver tests** for every construct read (§10).
- **Not in X-M1:**
  - typed directives other than those above (`.tran`, `.ac`, `.dc`, `.op`, `.options`, `.step`, `.meas`, `.data`): X-M2. Until then they raise `UnsupportedConstruct`;
  - the transient source functions (X-M3) and every other letter (X-M3 to X-M7);
  - a public `Dialect.XYCE` (X-M8).

## 2. Decisions

1. **Workflow as X-M0** (decision 0026; X-M0 decision 3): developer and reviewer subagents report to the lead; gates carry the maintainer's decisions; one commit per completed task; one pull request.
2. **Provenance** as decision 0026 items 2 and 3. Xyce source and headers are never read; the manuals are paraphrased and cited by section and page; nothing produced by Xyce is committed.
3. **The grammar follows the manual** (decision 0026 item 5). Where the binary is more lenient, the difference is a `discrepancies.md` row; where the manual is silent, the solver decides and the entry is `observed` (§11.3 rule 3).
4. **Reuse first.** An xyce construct reuses the ngspice node and rule where the reading is the same (§9.3 item 4), and gets a dialect-specific node only where its meaning differs.

## 3. Stages and gates

1. **Stage 1 — research and probes** (A1 to A3). Reports to the lead; nothing in `src/` changes.
2. **G1 —** the lead writes section 5.1; the maintainer decides X-D1, X-D2, X-D3, X-D5, the `.END` rule and any question the reports raise.
3. **Stage 2 — implementation** (B1 to B7), in the order below, since most tasks touch `xyce.lark`.
4. **R1 —** an independent review; findings are fixed or recorded.
5. **The pull request,** READY FOR REVIEW.

## 4. Tasks

### Stage 1

- [x] **A1 — Structure and names.** From the manuals and probes: indented lines (X-D1) and what the library should do with them; `.END` strictness; `;` and `+` lines; name characters and case; ground and `.PREPROCESS REPLACEGROUND`; `$G` globals (X-D3); `:` hierarchy, `X1:node` on device lines and in expressions (X-D2), against today's nets layer and LTspice's `NODE_INTO_INSTANCE`; `.GLOBAL`. Options for each decision, with a recommendation.
- [x] **A2 — Numbers, parameters and expressions.** Scale factors (`X`, `mil`, `a`, `Meg` case), suffixes after scale factors; `.PARAM` forms (braced, quoted, bare; commas; functions), `.GLOBAL_PARAM`, `.FUNC`; bare expressions in instance `name=` values (X-D5); scoping (body `.param` local, last definition wins, `.func` scope); the formula grammar: operators, functions, reserved words, accessors; how far the existing `formula.lark`/`formula_ltspice.lark` serve. Options for X-D5, with a recommendation.
- [x] **A3 — Statements and elements.** `.MODEL`, `.SUBCKT`/`.ENDS`, includes, `.LIB` call and block, and R, C, L, V, I (DC/AC), D, X, K: each form in the manual against today's ngspice rules and nodes (reuse, reuse with differences, new); the R/C/L model-before-value order and what it means for the nodes and for edits (`set_value`, `set_model`, insertion order); xyce's model types; binned model names. Probes for anything the manual leaves unclear.

### Stage 2

- [x] **B1 — Decision record(s)** for the G1 decisions (X-D1, X-D2, X-D3, X-D5, `.END`), and the architecture sections they amend.
- [x] **B2 — Structure, names and numbers** in `xyce.lark`, the names layer and the value grammar; `names.md`, `numbers.md`.
- [x] **B3 — Parameters and expressions:** `.PARAM`, `.GLOBAL_PARAM`, `.FUNC`, the xyce formula grammar and reserved words; `scoping.md`.
- [x] **B4 — Statements:** `.MODEL` and model types, `.SUBCKT`/`.ENDS`, includes, `.LIB`, `.GLOBAL`, `.PREPROCESS REPLACEGROUND`.
- [ ] **B5 — Elements:** R, C, L, V, I (DC/AC), D, X, K; `devices.md`.
- [ ] **B6 — The document and edit layers:** the X-M1 lines of the plan's section 8.1; topology, diagnostics and edits on xyce for the letters read.
- [ ] **B7 — Evidence:** spec entries for every construct, corpus files with manifests, solver tests (accept and reject probes, values and nets compared with Xyce), the README status table.

## 5. Findings and log

### 5.1 G1 decisions

From the stage 1 reports: A1 (structure and names), A2 (numbers, parameters and expressions) and A3 (statements and elements). All probes are on XyceNF Release 7.10.0 and are kept outside the repository. Each point gives *Recommendation:*, then the decision. **Every point not marked otherwise was decided as recommended (maintainer, 2026-11-16).**

**Structure and names (A1)**

1. **X-D1, indented lines.** The manual and the binary agree: an indented line that is not `+` is a comment ([xyce-ug] §4.1.3.1 p43; [xyce-ref] §2.1.39.1 p163). That holds for an element, `.op`, `.param` or `.END`, and an indented line between a statement and its `+` line does not break the join. Options:
   - (a) read it as a comment;
   - (b) keep refusing it, a recorded strictness exception;
   - (c) read it as a comment of its own kind and report it.

   *Recommendation:* (c). The grammar has a distinct node for an indented line (P13), and a new `DiagnosticCode` (warning) says that Xyce reads it as a comment. An indented `*` or `;` line is a plain comment. An indented `+` continues. Edits refuse inserted statement text that begins with whitespace.
   **Decided (maintainer, 2026-11-16): as recommended.**
2. **`.END`.** The manual says it is required and last (ug §4.1.1 p40). The binary runs without it, ignores text after it, and accepts `.end junk`.

   *Recommendation:* required, last, with only blank lines after it, as on the other dialects. A `;` comment is allowed on its line, since `;` may end any line (ug p43). `.end <text>` is refused. Each difference is a discrepancy row.
3. **`;` and `+`.** `;` starts a comment line or ends any line, with no space needed. `+` joins the last non-comment line across blank, `*`, `;` and indented lines (ug §4.1.3.2 p43); a `+` line holding only `;` is fine.

   *Recommendation:* the overlay follows the manual. The lines between a statement and its `+` line belong to the statement's `Line` (§5.4), so no insertion point falls between them, and their comments are kept in `trailing_comments` where the grammar stays LALR. Removal on xyce takes ngspice's plain path (`_ops_common.py:254`, keyed per dialect).
4. **Name characters and case.** The manual allows printable ASCII except whitespace, `( ) { } , : ; " '` (ref §2.3.2 p184). The binary also takes `"` and non-ASCII, and folds case in ASCII only (`Ä` ≠ `ä`).

   *Recommendation:*
   - the manual's class, minus `=`;
   - `[` and `]` are legal;
   - `:` only inside element node fields (point 7);
   - non-ASCII refused;
   - the ASCII fold, now observed;
   - discrepancy rows for `"` and non-ASCII.
5. **Ground and `.PREPROCESS REPLACEGROUND`.** `0` is ground. With `REPLACEGROUND TRUE`, `GND`, `GND!` and `GROUND` in any case are aliases of `0`, but `GROUND!` is not (ref §2.1.28 p125). Its effect covers the whole netlist, wherever it is written (in a body too, but not after `.END`). A second statement, `1` or `yes`, or a missing value stops Xyce.

   *Recommendation:*
   - a typed `PreprocessDirective` (TRUE/FALSE keywords), allowed in a body, whose flag changes net identity netlist-wide;
   - the flag enters the topology signature, and no edit changes it (P4);
   - a second statement raises `ParseError`, since Xyce stops;
   - the other `.PREPROCESS` forms raise `UnsupportedConstruct`.
6. **X-D3, `$G` globals.** Every node whose name begins `$G`, in any case, is global in every scope (ref §2.3.1.1 p182; ug §4.1.2.1 p41).

   *Recommendation:* a per-dialect prefix table in `is_automatic_global` (LTspice `$g_`, xyce `$g`), and `Net.global_` for those nets.
7. **X-D2, `X1:node`.** A node path `X1:m`, or `X1:X2:m`, reaches an internal node of the instance, relative to the scope it is written in (ref §2.3.1.2 p182–183). An interface node, a missing node or a missing instance is a separate net. The library's nets are per definition, not per instance, so it cannot join `X1:m` to one instance's `m`. Options:
   - (a) refuse it, a recorded exception (the grammar can't tell `X1:m` from a plain `a:b`);
   - (b) read it as its own net and report it, as LTspice's `NODE_INTO_INSTANCE`;
   - (c) model the join, which needs a per-instance net view (an architecture change).

   *Recommendation:* (b). An xyce reading resolves the path through `X` designators and reports `NODE_INTO_INSTANCE` (warning) when it names an internal node. §7.8's known limit extends to xyce. Expression reads such as `V(X1:m)` go through the same reading.
   **Decided (maintainer, 2026-11-16): as recommended.**
8. **`.GLOBAL`.** Top level only; position-independent; at least one name (ref §2.1.11 p44).

   *Recommendation:* reuse `global_stmt` and `GlobalDirective`. Commas are refused, with a discrepancy row, since Xyce accepts them.

**Statements and elements (A3)**

9. **Xyce sorts R, C and L words by lookup, not position.**
   - Both `R1 a 0 rmod 2k` (the manual's order) and `R1 a 0 2k rmod` (ngspice's) run.
   - An undefined name in either place becomes the value.
   - A bare parameter name is a value (`R1 a 0 rv`).
   - A defined `.model 2k` is taken as the model.

   *Recommendation:*
   - (a) The manual's order only: the model, if any, right after the nodes, then the value. `R1 a 0 2k rmod` is refused with the hint "Xyce writes the model before the value". A word after the nodes is the model, and a field that reads as a number is the value (decision 0024 item 7 holds).
   - (b) A diagnostic when that word names no visible model but a visible `.param`.
   - (c) A warning on a `.model` whose name reads as a number.

   Each difference is a discrepancy row.
   **Decided (maintainer, 2026-11-16): as recommended.**
10. **R, C and L details.**
    - R: the value is optional (Xyce uses 1 kΩ with a warning).
    - C: model-only is grammatical (the semiconductor form with `L=`/`W=`), and `Q=` is the charge form.
    - L: the value is required.
    - `TC=a,b` lists are allowed. `resistance=` and the other long keywords are refused.
    - A positional value together with `R=`, or a value together with `Q=`, raises `ParseError`; Xyce silently prefers one (P5).

    *Recommendation:* as listed. R with no value gets a warning diagnostic.
    **Decided (maintainer, 2026-11-16): as recommended, except that R requires a value.** An R line with no positional value and no `R=` raises `ParseError`, although Xyce runs it as 1 kΩ with a warning (a discrepancy row). *Narrowed (maintainer, 2026-11-16):* the model-geometry form, a model with both `L=` and `W=`, is still accepted, since Xyce computes RSH × L/W for it. Only an R that Xyce would set to the 1 kΩ default is refused: no value, no `R=`, and not that form. A lead probe on XyceNF 7.10.0 found `rmod L=30u W=1u` with `RSH=100` gives 3 kΩ, while an explicit value replaces the geometry (`rmod 2k L=30u W=1u` gives 2 kΩ). `remove_value` on R is allowed only on the geometry form, as on C's semiconductor form.
11. **The edits follow the order.**
    - `set_value` inserts after the model.
    - `set_model` inserts right after the nodes, and is allowed with `R=`.
    - `remove_value` removes a whole `R=v` field. It is refused on L, and on C unless `L=`, `W=` or `Q=` is written.
    - The positional-area branch (`_ops_elements.py`) and the `:359` refusal become dialect tables.

    *Recommendation:* as listed.
12. **K** may take a CORE model after the coupling, which adds a field, `MutualCoupling.model` (best-effort under decision 0024). Xyce also runs one inductor without a model, which the manual does not allow.

    *Recommendation:* add the field. A single inductor needs a model; the other case is a discrepancy row.
13. **D:** the model, an optional positional area, then flags (`OFF`, also `OFF=1`) and parameters, as LTspice's D. Xyce silently drops a number written before the model; the library refuses it (decision 0024 item 7).
14. **V and I (DC and AC):**
    - the order is fixed: `[DC] v`, then `AC [mag [ph]]`, then a function, with no function before DC;
    - no commas and no port parameters;
    - a transient function raises `UnsupportedConstruct` for the whole line until X-M3.

    A bare `AC` (the manual makes the magnitude optional) is refused with "write `AC 0`", because `AcSpec.magnitude` is not optional (a recorded strictness exception).

    *Recommendation:* as listed.
15. **X:** `PARAMS:` is optional (LTspice's `x_last` without its comma), `M=` is an ordinary parameter, and a comma raises `ParseError`.
16. **`.SUBCKT`/`.ENDS`.**
    - `PARAMS:` defaults are optional, with no comma, though the manual's own example uses one and Xyce stops on it.
    - At least one port; node 0 is not a port.
    - Nesting is local.
    - `.ENDS name` is not checked by Xyce.
    - A repeated `.model` or `.subckt` stops Xyce, while a repeated `.param` takes the last value, so `_REPEAT_STOPS` is split by kind.
    - Top-level-only statements in a body stay `ParseError`, though Xyce runs `.tran` there (the manual says a body should hold only devices, `.MODEL`, `.PARAM` and `.FUNC`).
17. **Includes and `.LIB`.**
    - `.INC`, `.INCL` and `.INCLUDE`, quotes optional, continuable.
    - `.LIB` with one field opens a block that must close with `.ENDL <same name>` (Xyce stops otherwise). Two or more fields are a call. Xyce loads only the first of several entries, which the manual allows; the library accepts the call as opaque text, with an info diagnostic.
18. **`.MODEL`.**
    - Parameters with or without one pair of parentheses; no commas.
    - A repeated parameter or a repeated model is an error.
    - Binned names (`nch.1`) lex as ordinary names; MOSFET bin resolution is X-M4's.
    - xyce's model types replace the shared list (a replace mode in `model-types.json`, which leaves ngspice and LTspice as they are), adding CORE for K.

**Numbers, parameters and expressions (A2)**

19. **Numbers: Xyce has two readers.** Both take the scale factors T, G, Meg, X (1e6), K, mil, m, u, n, p and f, in any case (`M` is milli), and `a` is amperes (ref §3.1 p835). After the scale, a unit may follow:
    - **in a device field**, one of {a, amp, c, f, farad, h, henry, hertz, hy, hz, m, ohm, s, v, vdc, volt}, so `1kohm` is accepted;
    - **in an expression or `.param`**, only one of {a, f, h, hz, m, s, v}, then an optional `j` (imaginary), so `.param r=1kohm` is an error.

    Refused by both: `1kk`, `1z`, RKM forms and `µ`. The manual lists `µ` (ug Table 4-1 p42) and the binary refuses it.

    *Recommendation:* the two closed lists as observed (`observed` entries). Lexer artefacts the binary takes (`1keg`, `1kmeg`, `1e`) are refused, each with a discrepancy row, and so is `µ`.
    **Decided (maintainer, 2026-11-16): as recommended.**
20. **`.PARAM`:** reuses `ParamStatement`, with:
    - commas optional, and blanks around `=`;
    - function assignments `f(x)={…}` (a braced or quoted body);
    - complex values with `J`;
    - no strings.

    **`.GLOBAL_PARAM`** reuses it with its own keyword, top level only and without functions. **`.FUNC`** is a new node, one per line, with an optional `=` and a braced or quoted body. A built-in function name, or `pi` or `exp` as an argument, is refused (the manual forbids them; Xyce silently ignores them). A repeated function is an error diagnostic, since Xyce stops.
21. **X-D5, bare expressions.** The manual allows them in `.param`, `.global_param` and instance `name=` values (ref §2.2 p164; ug §4.3.4 p48). On a `.param`, Xyce deletes every blank inside the value up to the next `name =`, so `a=1 2` is 12. On an instance line, blanks split the field. Options:
    - (a) copy Xyce's rule;
    - (b) refuse every bare expression;
    - (c) accept only a space-free bare value, ending at a blank, a comma outside parentheses, `;` or the line end.

    *Recommendation:* (c), recorded as an exception to §6.3 rule 10. A bare value is a `Formula` with no delimiters, as on LTspice. This is exactly Xyce's rule on instance lines. On `.param` it is stricter: `a = 1 + 2` raises `ParseError` with a "use braces" hint, and gets a discrepancy row. `.subckt` `PARAMS:` defaults and V/I DC values take no bare value (Xyce refuses them).
    **Decided (maintainer, 2026-11-16): as recommended.**
22. **A repeated `.param`.** The manual says the last definition is used (ref p120). Xyce 7.10 uses the **first**, and its own warning says so; `-redefined_params` changes it. For `PARAMS:` lists it uses the last.

    *Recommendation:* `DUPLICATE_DEFINITION` at warning severity, resolved to the first definition (what the solver does by default), with a discrepancy row. The alternative is to follow the manual and resolve to the last.
    **Decided (maintainer, 2026-11-16): as recommended.**
23. **Order.** Parameters and functions may be used before their definition, even though the manual's `.FUNC` wording says otherwise. *Recommendation:* no `PARAM_USED_BEFORE_DEFINITION` on xyce, as on LTspice.
24. **A body `.param` that repeats a `PARAMS:` name** is shadowed by the default or the instance value. *Recommendation:* a warning. A `.param` and a `.global_param` with the same name: the `.param` wins.
25. **Reserved words:** time, freq, hertz, vt, temp, temper, gmin, pi and exp. Defining one as a parameter, `PARAMS:` name or `.func` argument raises `ParseError`. Xyce stops on five of them and silently ignores `hertz`, `temper`, `pi` and `exp` (discrepancy rows). A definition never masks them.
26. **The formula grammar** is a new `formula_xyce.lark`, built from `formula.lark`:
    - `**` is the power operator, and `^` a boolean XOR at the logical level;
    - `|`, `&` and unary `~`; no unary `!` and no backslash; `%` kept;
    - names may hold `.`, `#`, `@`, the backtick, `$` and `:`, but not `[` or `]`;
    - numbers as point 19, with `j`;
    - the brace and quote terminals exclude only `{ } ;` and line ends.

    A call to a `.FUNC` resolves as a reference of kind `function`, scoped like a parameter. `V(X1:A)` goes through point 7's reading. `dev:param` accessors appear only in `.print`, which is X-M2's.
27. **Parameter names:** a letter or `_`, then letters, digits, `_` and `.`; `.` is accepted but undocumented, a discrepancy row. Function names may also hold `#`, `@` and the backtick (ref p43).
28. **Commas in `PARAMS:`** are refused by 7.10, including the manual's own example (point 16), on both `.subckt` and instance lines. *Recommendation:* refused, with a discrepancy row.

### 5.2 Log

- 2026-11-15: task list written; X-M0 archived (approved and merged as #26).
- 2026-11-16: stage 1 reports in (A1 to A3; resumed after a usage limit); section 5.1 written.
- 2026-11-16: G1, first round: points 1 (X-D1), 7 (X-D2), 9 (the R, C and L order), 19 (numbers), 21 (X-D5) and 22 (repeated `.param`) decided as recommended. The maintainer reviews the remaining points before stage 2.
- 2026-11-16: G1, second round: every other point decided as recommended, except point 10: an R line requires a value.
