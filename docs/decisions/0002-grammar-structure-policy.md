# 0002 — Grammar structure policy

- **Status:** proposed — superseded by the M2 rework (strict, grammar-only); to be rewritten, not accepted
- **Date:** 2026-10-21
- **Context:** The ngspice grammar needs explicit policies for source structure
  that affect round-tripping, title interpretation, and content at the end of a
  netlist. The policy is based on probes run against ngspice 47.
- **Decision:**
  - The first physical line is always a `Title`, including an empty line or a
    line that resembles a statement. The node records whether its content is
    an explicit `.title` statement or an implicit title. A later `.title`
    creates another `Title`; ngspice replaces the displayed title with the
    later value, while the parser retains both source nodes.
  - `.end` is optional. `ParseResult.end_present` records its presence. A
    missing `.end` is accepted without a diagnostic until the diagnostics API
    exists.
  - After `.end`, the parser accepts blank and comment lines only. ngspice 47
    accepts trailing comments and silently ignores an element line, but
    rejects a following unknown dot-command. The parser rejects all following
    statements rather than silently discarding potentially meaningful source.
  - LF and CRLF are physical-line terminators. A lone CR is ordinary
    character data: it is accepted in free text (titles, comments, opaque
    regions and opaque statements) and rejected elsewhere.
  - A `*` comment line is accepted with optional leading spaces or tabs.
    Semicolon (`;`) and dollar (`$`) markers start trailing comments, with or
    without whitespace before the marker, outside quoted and braced text.
  - A continuation line joins the preceding eligible statement. ngspice 47
    joins a continuation across intervening `*` comment and blank lines; those
    physical lines are included in the statement span. A `+` on the first
    line is part of the implicit title. A `+` after the title is preserved
    within its title span but does not change the title reported by ngspice.
  - `.control` blocks are opaque and non-nesting. `.if` blocks are opaque and
    nested. ngspice 47 accepts the probed `.control` block but rejects the
    probe form `.if 1`; the parser still recognizes conditionals as opaque
    structure, and that solver discrepancy is recorded in the relevant spec.
  - `.include` and `.lib` remain opaque single statements. A `.lib ... .endl`
    definition block is not recognized in the main file in M2.
- **Probe record (ngspice 47, 2026-10-21):**
  - `R1 in 0 1k` in line 1 is reported as `Circuit: r1 in 0 1k`; that resistor
    is treated as the title, not an element.
  - A later `.title replacement` changes the `Circuit:` title. `.TITLE`,
    `.END`, and tab-separated element fields are accepted case-insensitively
    and as separators, respectively. `.title` with no text yields an empty
    displayed title.
  - A complete circuit without `.end` exits successfully. An unknown dot
    command after `.end` fails; a comment after `.end` succeeds; a following
    element is ignored by the solver.
  - A leading `+` is reported verbatim as the first-line title. A continuation
    line after the title does not change that title. A `+` after `.end` is
    ignored by the solver.
  - Comment and blank lines between `V1 in 0` and `+ DC 2` still produce a
    2-volt node, matching the unbroken `V1 in 0 DC 2` statement.
  - Indented `*` comments and trailing `;`/`$` comments, both separated and
    adjacent to the preceding text, are accepted.
  - `.control`/`.endc` with `op` is accepted. The tested `.if 1` block is
    rejected with a netlist syntax error. Missing `.include` and `.lib` files
    produce solver errors naming the missing file.
  - A file containing only a lone CR is not split into physical lines and is
    reported as an empty netlist.
- **Consequences:** The parser's post-`.end` policy is intentionally stricter
  than ngspice's handling of ignored element and continuation lines. The
  source-level structural parser does not treat solver-side silent omission as
  permission to discard source content. The behavior and the remaining
  `.if` probe uncertainty are covered by solver-backed tests.
