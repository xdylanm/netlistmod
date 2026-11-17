# 0027 — xyce structure, names, values and the first elements (X-D1, X-D2, X-D3, X-D5)

- **Status:** accepted (2026-11-16, maintainer; X-M1 gate G1)
- **Date:** 2026-11-16
- **Amends:** [decision 0026](0026-the-xyce-dialect.md) item 6 (what the hidden xyce dialect reads); architecture §6.3 rule 10 (an xyce exception), §7.8 (the known limit extends to xyce) and §19 decision 21 (strictness exceptions), for the hidden xyce dialect only.
- **Context:** X-M1 ([xm1-tasks.md](../design/archive/xyce/xm1-tasks.md)) makes the hidden xyce dialect read structure, names, numbers, parameters, expressions, subcircuits, models, includes and the letters R, C, L, V, I, D, X and K. Its stage 1 compared the Xyce 7.10 manuals with the XyceNF 7.10.0 binary (section 5.1, points 1 to 28). Where they differ, the grammar follows the manual (decision 0026 item 5), except as stated here. The maintainer decided every point at G1.
- **Decision:** Item numbers below refer to xm1-tasks.md section 5.1, which holds the evidence and the details.
  1. **X-D1, indented lines** (point 1). An indented line that is not `*`, `;` or `+` is read as a comment, as Xyce reads it, in a node of its own kind. A warning diagnostic reports that Xyce ignores it. An indented `+` line continues. Edits refuse inserted statement text that begins with whitespace.
  2. **Structure** (points 2 and 3).
     - `.END` is required and last, with only blank lines after it, and a `;` comment is allowed on its line; `.end <text>` is refused.
     - `;` starts a comment line or ends any line.
     - A `+` line joins the last non-comment line across blank, `*`, `;` and indented lines. Those lines belong to the statement's `Line`.
  3. **Names** (points 4, 5, 6 and 8).
     - Printable ASCII except whitespace and `( ) { } , : ; " ' =`; `[` and `]` are legal; non-ASCII is refused. Case folds in ASCII.
     - `:` is allowed only inside element node fields (item 4).
     - **X-D3:** every node whose name begins `$G`, in any case, is global in every scope.
     - **Ground:** `0` only. `.PREPROCESS REPLACEGROUND TRUE|FALSE` is a typed statement, allowed in a body. Its flag makes `GND`, `GND!` and `GROUND` aliases of `0` across the whole netlist. The flag is part of the topology signature, and no edit changes it (P4). A second such statement raises `ParseError`, and the other `.PREPROCESS` forms raise `UnsupportedConstruct`.
     - `.GLOBAL` is top level only, takes at least one name, and takes no commas.
  4. **X-D2, a node path into an instance** (point 7). `X1:m` (or `X1:X2:m`) on a device line is read as a net of its own. When it names an internal node of the instance's definition, it is reported as `NODE_INTO_INSTANCE`, as on LTspice. The library's nets are per definition, so the join Xyce makes is not modelled; §7.8's known limit extends to xyce.
  5. **R, C and L** (points 9 to 11). The model, if any, comes right after the nodes, then the value; the ngspice order is refused with a hint.
     - A word in the model's place is the model. A field that reads as a number is the value, never a model (decision 0024 item 7).
     - **R requires a value,** positional or `R=`, unless it has a model and `L=` (the geometry form, whose value Xyce computes from the model's `RSH`; a missing `W=` takes the model's `DEFW`, [xyce-ref] §2.3.7 p203). Xyce runs any other R with no value as 1 kΩ (or 1 kΩ times the model's `R`), with a warning; the library refuses it. An explicit value replaces the geometry.
     - **L requires a value.** C may have a model only (the semiconductor form) or `Q=` (the charge form).
     - A positional value together with `R=`, or a value together with `Q=`, raises `ParseError`.
     - The edits keep the order: the value goes after the model, and the model right after the nodes.
  6. **K, D, V, I and X** (points 12 to 15).
     - K takes an optional CORE model after the coupling, as a new field `MutualCoupling.model`; one inductor needs that model.
     - D takes its model, then an optional positional area, then flags and parameters.
     - V and I read `[DC] v`, then `AC [mag [ph]]`, in that order. A transient function raises `UnsupportedConstruct` for the whole line until X-M3. A bare `AC` is refused ("write `AC 0`"); it is a strictness exception, since the manual makes the magnitude optional.
     - X takes `PARAMS:` optionally, with no comma; `M=` is an ordinary parameter.
  7. **Statements** (points 16 to 18).
     - `.SUBCKT` takes at least one port, never `0`, and optional `PARAMS:` defaults without commas. Nesting is local.
     - `.INC`, `.INCL` and `.INCLUDE` take a path, quoted or not, and are continuable.
     - `.LIB` with one field opens a block, which must close with `.ENDL` and the same name. With two or more fields it is a call, read as opaque text, with an info diagnostic when it names more than one entry.
     - `.MODEL` takes its parameters with or without one pair of parentheses, and no commas.
     - xyce has its own model-type list.
  8. **Numbers** (point 19). Xyce has two closed readers, both taking the scale factors T, G, Meg, X, K, mil, m, u, n, p and f.
     - **Device fields** may add a unit from {a, amp, c, f, farad, h, henry, hertz, hy, hz, m, ohm, s, v, vdc, volt}.
     - **Expressions** may add a unit from {a, f, h, hz, m, s, v}, then `j`.

     Both readings are `observed`. `µ`, RKM forms and the binary's lexer artefacts are refused.
  9. **Parameters and functions** (points 20 to 25 and 27).
     - `.PARAM` takes optional commas, function assignments and complex values.
     - `.GLOBAL_PARAM` is top level only.
     - `.FUNC` is a new node; a built-in name, or `pi` or `exp` as an argument, is refused.
     - Order does not matter.
     - **A repeated `.param` resolves to the first definition,** as Xyce 7.10 does by default, with a `DUPLICATE_DEFINITION` warning. The manual says the last definition is used; that difference is a discrepancy row.
     - The reserved words are time, freq, hertz, vt, temp, temper, gmin, pi and exp, and a definition never masks them.
  10. **X-D5, bare expressions** (point 21). An exception to §6.3 rule 10 on xyce: a `.param` or `.global_param` value, or an instance `name=` value, may be a bare expression without blanks. It ends at a blank, a comma outside parentheses, `;` or the line end, and is a `Formula` without delimiters. A blank inside it raises `ParseError` with a hint to use braces. Xyce deletes those blanks on `.param`, which is a discrepancy row.
  11. **The formula grammar** (point 26) is `formula_xyce.lark`:
      - `**` is the power operator, and `^` a boolean XOR;
      - `|`, `&` and `~`;
      - names may hold `.`, `#`, `@`, the backtick, `$` and `:`;
      - numbers as item 8.

      A call to a `.FUNC` is a reference of kind `function`.
  12. **Every refusal of a form the binary accepts is a row** in `docs/grammars/xyce/discrepancies.md`, and every reading that rests only on the binary is an `observed` spec entry.
- **Consequences:**
  - New nodes or fields: the indented-comment kind, `PreprocessDirective`, `FuncDefinition` (or a `.FUNC` statement node) and `MutualCoupling.model`.
  - A new `DiagnosticCode` member for an indented line. Decision 0024 item 11 lets a minor release add these.
  - Per-dialect tables gain xyce entries for names, globals, ground, repeats, ordering, model types and edits (the plan's section 8.1, X-M1 lines).
  - `docs/grammars/xyce/` gains `names.md`, `numbers.md` and `scoping.md` in full, with spec entries, corpus files and solver tests for each construct.
