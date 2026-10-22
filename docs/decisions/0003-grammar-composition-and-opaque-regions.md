# 0003 — Grammar composition and opaque regions

- **Status:** rejected — hand-written structure conflicts with architecture P13; to be rewritten in the M2 rework
- **Date:** 2026-10-21
- **Context:** M2 requires a strict, cached LALR grammar with useful source
  spans, continuation handling, nested opaque conditionals, and a mechanical
  path to future dialect overlays.
- **Decision:**
  - Compose each dialect overlay with `core.lark` using Lark relative `%import`
    (`ngspice.lark` imports `core.start`). The parser is loaded with
    `Lark.open_from_package`, `parser="lalr"`, `lexer="contextual"`,
    `propagate_positions=True`, and `strict=True`. The core grammar and the
    overlay both build independently in strict mode; the package registry is
    owned by `grammar/loader.py`, not `dialects.py`.
  - The core grammar tokenizes physical lines, retaining LF as a separate
    token. The dialect transformer performs explicit line classification and
    block matching. It records spans from Lark's token positions and checks
    that the resulting item spans tile the entire source. A catch-all physical
    line is not a pass-through: any ordinary non-directive line outside an
    opaque region is rejected as a parse error or a positioned
    `UnsupportedConstruct`.
  - Continuations are grouped during the dialect transform rather than by an
    ignored terminal. Eligible dot-statements absorb following `+` lines and
    any intervening blank/comment lines. Tests confirm the resulting source
    span includes every joined physical line. This also supports unknown
    directives and `.include`/`.lib` statements without losing exact text.
  - `.control` blocks are scanned to the first `.endc`; `.if` blocks are
    scanned with a nesting depth until the matching `.endif`. Unterminated
    blocks raise at the opening line. This scanner runs over explicit physical
    lines, not regexes over an unsegmented multiline source.
  - The physical-line terminal excludes LF but retains CR. A CR immediately
    before LF is the CRLF terminator; a lone CR remains ordinary content. The
    transform allows it only in free-text or opaque regions.
- **Validation:** strict builds pass for both grammar files. The S1 solver
  comparison confirms comment/blank-separated continuations join; the nested
  conditional and unterminated-block tests check matching and error offsets.
- **Consequences:** The grammar loader can register a dialect as a core grammar
  plus overlay. The line-oriented transformer is responsible for enforcing
  ngspice statement semantics; the Lark grammar remains deliberately small to
  avoid a catch-all terminal collision with dialect-specific device and
  directive terminals added in later milestones.
