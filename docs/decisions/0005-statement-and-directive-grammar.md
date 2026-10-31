# 0005 — Statement and directive grammar

- **Status:** accepted (2026-10-30, maintainer, after the M4 review)
- **Date:** 2026-10-30
- **Context:** M4 types the dot-statements and directives that phase 1 needs: `.param`,
  `.model`, `.subckt` … `.ends`, `.tran`, `.ac`, `.dc`, `.op`, `.options`, `.temp`, `.ic`,
  `.nodeset`, `.save` and `.meas` ([m4-tasks.md](../design/m4-tasks.md); section 2 records the
  maintainer's decisions of 2026-10-30). Until M4 each was an `UnknownDirective`. The open
  points were how a subcircuit definition is represented, what may stand in its body, how
  strictly `.param` values are read, how deeply directives are typed, which new tokens
  (parentheses, `@dev[param]`, `name#branch`) are needed and where they are valid, all under
  `strict=True` and without new lookaround terminals (M2 finding 6.4).
- **Decision:**
  1. **Subcircuit blocks.** The grammar matches `.subckt` … `.ends` as one block and nests by
     recursion: a definition is a `statement`, so it may stand in another body. The node is a
     container, `SubcktDefinition(name, ports, params, body, ends, header_span, …)`. Top-level
     item spans still tile the file; body items tile the text between the header and the
     `.ends` line, which is an `EndsLine(name | None, name_span, span)`. An unterminated
     `.subckt` is reported at its innermost open line (the loader finds the opener on the
     parser stack, as for `.control`), and a stray `.ends` is a `ParseError`: `.ends` joins the
     stray terminators excluded from `DOT_NAME` by the existing `%override`.
  2. **Body rules (narrow).** The top-level `line` is split into `body_line` (allowed in a
     body and at the top level: elements, comments, blank lines, `.param`, `.model`, nested
     `.subckt`, `.include`/`.lib`, `.if` blocks, unknown dot-commands) and `top_statement`
     (`.title`, the analysis, option and output directives, `.control`). A body is
     `subckt_item*`: a `body_line` or `not_in_subckt`, which recognises the top-level-only
     keywords, `.control` blocks and `.end` so that the transformer rejects them at their
     keyword with "not allowed inside a subcircuit definition". The keywords must be in the
     body's lexer states anyway: otherwise `DOT_NAME` would read `.tran` or `.end` in a body as
     an unknown dot-command. ngspice 47 accepts `.tran` in a body; this is a recorded
     discrepancy (§2.6.1, "Control lines may not appear within a subcircuit definition").
  3. **`.subckt` line.** At least one port; a port `0` is recognised (`ZERO_PORT`, a string
     re-typed from `WORD`) and rejected (§2.6.1). Defaults are `x_param` fields (number,
     formula or double-quoted string, as on X lines); `params:` is rejected. `.ends` takes an
     optional name that is recorded, not checked (§2.6.2).
  4. **`.param`.** One or more `name=value` assignments separated by blanks (no comma). Names
     use a dedicated terminal, `PARAM_NAME` (a letter, then letters, digits and
     `! # % [ ] _`, §2.11.1; `$` starts a comment). `time`, `temper` and `hertz` are string
     terminals re-typed from it and rejected. A value is a number, a brace or single-quoted
     formula or a double-quoted string. A bare expression is recognised by `BARE_EXPR`, the
     lowest-priority terminal (1), in place of a value, glued to a number (`1k+a`) or as a
     field after a value (`123 * 3`), and rejected at the value with a hint to use braces.
  5. **`.model`.** `.model name type`, then `param` fields (blanks, one comma, continuations),
     or a parenthesized list whose first parameter may follow `(` directly. The type is any
     name. An unclosed `(` is reported at the opener when the line ends (the loader finds
     the opener on the parser stack).
  6. **Directive typing depth** is that of the task list (decision 6), with one extension:
     an `.options` value may also be a name (`METHOD=name`, §11.1.4), stored as the new value
     type `Identifier`. `.meas`/`.measure` is shallow: analysis and result are fields, the rest
     is statement text with a span. `.save` vectors are one token each (`OUTPUT_VECTOR`), kept
     as text.
  7. **New tokens and where they are valid.** `LPAR`/`RPAR` (`(`, `)`) only in `.model` and,
     with `V_OPEN` (`v(` as one token), in `.ic`/`.nodeset`; a parenthesis on an element line
     is still a syntax error. `@dev[param]`, `name#branch`, `v(n1,n2)` and `i(src)` exist only
     inside `OUTPUT_VECTOR`, in `.save`. Statement keywords are strings at `DOT_NAME`'s
     priority (4); argument keywords (`uic`, `dec`, `oct`, `lin`, `all`, `tran`, `sp`) are
     strings at `WORD`'s priority (2), valid only where their rule names them. No new
     lookaround terminal: the pinned list in `tests/architecture/test_contracts.py` is
     unchanged.
  8. **Aliases.** `.options`/`.option` and `.meas`/`.measure` are typed; `.opt` and `.probe`
     stay `UnknownDirective`. Keywords are case-insensitive and recorded as written.
  9. **Corpus provenance:** `statements_basic` and `statements_rejects` are authored in this
     repository by `xdylanm`, MIT.
- **Consequences:**
  - Architecture §5.2 is amended (`SubcktDefinition` contains its body; the directive node
    family) and §6.5 (typed directive list; `.probe` stays unknown). §6.3 rule 9 is unchanged:
    node names keep the M3 class, including inside `v(…)`.
  - Shapes, spans and the manual-form → rule → field tables are in
    [m4-statements.md](../design/m4-statements.md); M6 edits replace those sub-spans.
  - Every case where ngspice 47 is more lenient is in `discrepancies.md`, paired with a test.
  - Known limits: a `.meas` body is not parsed; `.save` accepts only the listed vector forms
    (no `vdb(…)`, no blanks inside the parentheses); blanks inside `.ic v( n )` are ignored
    like other inline blanks; a keyword prefix such as `decade` after `.ac` fails at the
    letter after the keyword, not at the word.
