# 0002 — Strict grammar structure policy

- **Status:** accepted (maintainer, 2026-11-02, M9 review)
- **Date:** 2026-10-22
- **Context:** M2 requires the netlist structure to be expressed in Lark, with
  source-preserving nodes produced by a transformer. The grammar follows the
  ngspice manual strictly, not every behavior accepted by ngspice 47.
- **Decision:**
  - The first physical line is always one title token. It is implicit unless it
    is an explicit `.title` line. A later `.title` is represented by a
    `TitleDirective`; neither title form splits on `;` or `$`.
  - `.end` is required and is the final statement. Its final newline is
    optional. Only blank lines may follow it. A comment, directive, block,
    second `.end`, continuation, or other text after `.end` is rejected.
  - A continuation is accepted only when its `+` line immediately follows a
    continuable statement. A blank line or comment line in between interrupts
    the continuation. A `+` after a title, comment, blank line, or `.end` is
    rejected. The first physical line beginning with `+` remains a title.
  - A line ending in `\\` immediately before LF or CRLF also continues a
    continuable statement (§2.4.5). The next line must start with statement
    text: a blank, comment, `+` or comment-only line after `\\` is an error,
    as is a line holding only `\\`. `\\` followed by spaces, or at the end of
    a comment, title, `.end`, is text or an error, never a continuation;
    ngspice 47 continues after trailing spaces and after an end-of-line
    comment, which is recorded as a discrepancy. `+` and `\\` may be mixed on
    different lines of one statement.
  - A `*` line is a full-line comment. `;`, `$` and `//` introduce
    end-of-line comments only after the start of a statement, with or without
    whitespace before the marker; a comment runs to the end of the line. A line
    holding only `;`, `$` or `//` is rejected, even though ngspice 47 accepts a
    standalone `//` line. A path containing `//` must be quoted: in
    `.include a//b` the path is `a`.
  - Each physical line of a continued statement may end in an end-of-line
    comment, and a `+` line after it still continues the statement, as in the
    general form of §2.4.5. Statement nodes keep every comment span in
    `trailing_comments`.
  - Matched single- or double-quoted segments protect `;`, `$` and `//` in generic
    text. Braces are ordinary text and do not protect comment markers. The
    manual is silent on this generic-text case; this is the narrow observed
    interpretation recorded in `NG-TXT-001`.
  - A trailing comment on `.end` (`;`, `$` or `//`) is rejected. The grammar
    interprets `.end` as its own final statement, with no trailing-comment
    form.
  - LF and CRLF terminate physical lines. A lone CR is accepted inside title,
    comment, and directive free text; it is not a physical-line terminator and
    is rejected where the grammar expects a line terminator, including after
    `.end`.
  - `.control` is an opaque non-nesting block and `.if` is an opaque nested
    block. The accepted conditional form is `.if (1)` … `.endif`; this rule is
    validated by ngspice 47 and the earlier `.if 1` probe is discarded.
  - `.include` and each `.lib` command line are opaque statements. They cannot
    be continued (§2.4.5): a `+` line after them is a syntax error. A `.lib
    name` … `.endl` definition block in the main file is not implemented in
    M2.
- **Manual basis and settled points:**
  - Citations refer to the manual edition recorded in
    [docs/references.md](../references.md). The structure decisions use
    `[ngspice-manual] §2.1.1 "Input file structure"`; continuation uses
    `[ngspice-manual] §2.4.5 "Continuation lines"`; title behavior uses
    `[ngspice-manual] §2.4.1 ".TITLE line"`; and the final directive uses
    `[ngspice-manual] §2.4.2 ".END Line"`. In particular, the grammar does not
    accept post-`.end` material or line-separated continuations merely because
    the solver happens to tolerate them.
  - `[ngspice-manual] §2.4.3 "Comments"` and
    `[ngspice-manual] §2.4.4 "End-of-line comments"` define the
    documented comment forms: `*` in the first column, and `;`, `$` and `//`
    after a command. §2.4.4 recommends, but does not require, a space before
    the marker; ngspice 47 treats `2//3` and `2 // 3` alike. The manual does
    not describe standalone `;`/`$`/`//` lines or comment markers in quoted or
    braced directive text. Those points are settled to reject standalone
    markers, honor matched quotes, and treat braces as ordinary text;
    `NG-COM-001` and `NG-TXT-001` identify these as observed policy, not
    manual guarantees. ngspice 47 accepts a standalone `//` line, cuts
    `.include sub//v.inc` at the `//`, and recognizes quoted include paths;
    its tested `.include {braced;$.inc}` path is truncated at the semicolon.
  - The manual's `.END` line (§2.4.2) defines `.end` as the last line of the
    input and gives it no comment form. The general form
    `<any command> ; <any comment>` of §2.4.4 is read as applying to commands
    that take arguments, which `.end` does not. A trailing comment on `.end`
    is therefore rejected, although ngspice 47 accepts it (recorded in
    `discrepancies.md`).
- **Solver evidence (ngspice 47, 2026-10-21):** missing `.end` is accepted;
  an element and a `.control` block after `.end` are ignored/run; a `+` after
  `.end` is ignored; comments or blank lines between a statement and its `+`
  line still join. These behaviors are recorded as discrepancies, not adopted
  parser rules. An unknown dot-command after `.end` errors. The valid `.if
  (1)` form is accepted; `.if 1` was an invalid probe.
- **Consequences:** `parse("")` and a missing `.end` raise `ParseError`. The
  grammar is intentionally stricter than ngspice where accepting input could
  hide or discard source. No solver behavior relaxes the manual policy.
- **Amendments at acceptance (2026-11-02, M9 review; wording only, no change of behaviour):**
  - A title does not split on `//` either, as `NG-TTL-001` and the `Title` node say.
  - `.if (1)` is the conditional form validated on ngspice 47, not the only form the grammar accepts. A block's header is opaque text and is not checked, so `.if 1` and a bare `.if` parse too (§7.8).
  - A `*` comment line may be indented (`NG-COM-001`).
  - These rules are ngspice's. LTspice's are in [decision 0009](0009-ltspice-dialect.md): for example, `.end` may carry a comment there, and `;` starts a comment line.
