# 0003 — Grammar composition and opaque regions

- **Status:** proposed
- **Date:** 2026-10-22
- **Context:** M2 needs independent strict LALR grammars, positioned parse
  trees, immediate continuations, nested opaque conditionals, and separate
  dialect grammars. Syntax belongs in Lark (architecture P13); Python maps
  rules to typed nodes and adds error detail.
- **Decision:**
  - `grammar/loader.py` owns the dialect-to-grammar registry and builds cached
    LALR parsers with the contextual lexer, propagated positions, and
    `strict=True`. Each dialect overlay imports its core grammar with
    `%import`. Both `core.lark` and `ngspice.lark` also build independently in
    strict mode.
  - Lark `%import` does not carry `%ignore` declarations into the importing
    grammar; overlays redeclare the ignores they need. Importing each rule and
    terminal by name keeps its tree/token name unprefixed. Names omitted from
    an explicit import receive a `core__` prefix, including aliases, so the
    transformer handles those core aliases explicitly.
  - `%extend statement` adds ngspice-specific opaque commands and blocks.
    `%override DOT_NAME.4` excludes block delimiters at the same priority as
    the generic dot-command terminal. The explicit priority is required for
    strict mode to classify `.endc` and `.endif` correctly.
  - The ignored `CONT.7` terminal matches only a newline followed immediately
    by optional horizontal whitespace and `+`. `LINE_END.8` terminates titles,
    comments, blank lines, `.end`, `.include` and `.lib`, and outranks
    `CONT`; consequently a
    continuation after any of those lines fails. `NL.5` terminates
    continuable statements, so `CONT` wins only when a `+` immediately follows
    such a statement. Interleaved blank/comment lines are not skipped. A
    statement's `rest` accepts an end-of-line comment anywhere in its token
    sequence: a comment runs to the end of its line, so text after it can only
    come from a continuation line. `.include` and `.lib` use `line_rest`
    instead, ended by `LINE_END`, because they cannot be continued.
  - Backslash continuation is a token, `BS_CONT.7`, inside `rest`, not an
    ignored terminal (the M2 review-2 task asked for an ignored terminal;
    this deviation is recorded there). Ignored terminals are active in every
    lexer state, so an ignored `\\` terminal would silently drop a line
    holding only `\\`; as a `rest` token it is recognised only inside a
    continuable statement, and `line_rest` (`.include`, `.lib`) does not
    accept it. Its lookahead requires the next line to start with statement
    text. `TEXT` excludes a `\\` that ends the line, so it never swallows
    the continuation.
  - Priorities are deliberate: ignored `WS.9`; `LINE_END.8`; `CONT.7` and
    `BS_CONT.7` (they cannot match at the same position);
    `TITLE_KW.6`; `NL.5`; keywords and dot names at 4; comment, quoted,
    title-argument, and trailing-comment terminals at 3; free-text terminals
    at 2. Lark strict mode checks equal-priority collisions only for
    terminals interegular can model; terminals with lookarounds (listed in
    `tests/architecture/test_contracts.py`) are skipped without an error and
    were reviewed by hand. The test pins that list.
  - Opaque `.control` blocks are matched with grammar rules and do not nest.
    `.if` blocks use recursive grammar rules and may nest; `.else` and
    `.elseif` remain block content. End delimiters are recognized by
    block-scoped terminals. Unterminated blocks are reported at their opener
    using the parser state, with the missing closing directive in the error.
  - The text terminals exclude CRLF's carriage return but allow a lone CR
    within title, comment, and directive text using `\r(?!\r?\n)`. LF and CRLF
    are the only physical-line endings. The grammar, rather than a Python
    scanner or multiline regex, enforces these rules.
  - A Lark `Transformer` has one method per grammar rule/alias and converts the
    positioned tree to immutable nodes. It does not parse syntax or scan
    source lines. Each top-level item receives a span from the previous
    item's end to the rule end; raw statement text is sliced from source
    positions. The final item includes trailing ignored whitespace so spans
    tile the source.
  - `.lib` is a single opaque statement in M2. The `.lib name` … `.endl`
    definition-block form remains a documented limitation.
- **Validation:** strict-mode builds pass independently for the core and
  ngspice grammar. Tests cover the accept/reject table, nested `.if`, block
  errors, source positions, spans, and a 20,000-line continuation performance
  bound.
- **Consequences:** future dialects remain independent grammar overlays and
  must explicitly import/redeclare needed grammar items and ignores. Python
  must not grow handwritten syntax recognition outside Lark.
