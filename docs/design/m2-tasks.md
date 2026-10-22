# M2 task list — grammar core (ngspice)

> **Status:** READY for implementation (decision 3.7 confirmed explicitly by the maintainer; the other proposed defaults in section 3 stand as no objection was raised)
> **Part of:** [phase-1-plan.md](./phase-1-plan.md) (milestone M2). Governed by [architecture.md](../architecture.md) (§2 P5–P7, §3, §6, §10, §11). Follows the closing procedure in the plan (§4). Builds on the M1 source layer ([archive/m1-tasks.md](./archive/m1-tasks.md)).

## 1. Scope

Deliver the structural grammar for ngspice: the grammar loader (LALR, contextual lexer, `strict=True`), the shared `core.lark` plus the ngspice overlay, and typed nodes with spans for everything that is *not* an element or a typed directive:

- physical-line structure, blank lines, comment lines and trailing comments, continuation lines;
- the title (including the implicit first line) and `.end`;
- opaque regions: `.control`…`.endc` and `.if`…`.endif`;
- opaque statements: `.include` and `.lib`;
- unknown dot-commands, preserved verbatim (`UnknownDirective`);
- `ParseError` with positions taken from `SourceText`, and `UnsupportedConstruct` for known-but-not-yet-supported element letters.

Not in M2: element lines and values (M3), `.param`/`.model`/`.subckt` and typed directives (M4), `Document`/`Lines`/indexes (M5), LTspice (M8). In M2 every element line is therefore an error, so M2 test inputs contain no elements. The three `kicad_basic` fixtures first parse in M3.

Also in M2: the two fixes carried over from the M1 review (findings 3 and 4, tasks T7 and T12).

**Exit (from the plan):** T2 grammar tests and T3 round-trip over the structural subset; the strict build is green.

## 2. Confirmed decisions

Made by the maintainer for this milestone:

1. **Missing `.end` is accepted**, with a non-fatal diagnostic. ngspice accepts it (probe below). Architecture §6.3 rule 2 (`line* end_line NEWLINE*`) therefore changes to an optional end line. The parse result records whether `.end` was present; the diagnostic itself is emitted when the diagnostics API exists (M5, architecture §21).
2. **The first line is always the title**, mirroring the solver, but it is *flagged*: the `Title` node records whether it was an explicit `.title` statement or an implicit first line. When an implicit first line looks like a statement (starts with a device letter or `.`), a diagnostic is added in M5. No `ParseError`.

Probe facts (ngspice 47, 2026-10-21) behind these decisions and the rest of the grammar design; they are re-recorded as solver-backed tests in T6:

| Input | ngspice 47 behavior |
|---|---|
| Line 1 is `R1 in 0 1k` | Reported as the circuit title; the resistor is silently lost. |
| `.title text` later in the file | Replaces the title. |
| No `.end` | Accepted (exit 0). |
| Garbage after `.end` | Error ("bad syntax of line", exit 1). |
| `*` comment line between a statement and its `+` line | Accepted (exit 0). Whether the continuation joins the earlier statement is not yet established (S1). |
| Blank line between a statement and its `+` line | Accepted (exit 0). Semantics not yet established (S1). |
| Line 1 starts with `+` | Taken verbatim as the title. |
| Lone `\r` (no `\n`) | Not a line terminator: the whole file is one title line, giving "empty netlist". Consistent with M1 decision 3. |

## 3. Design decisions (proposed defaults, accepted; 3.7 explicitly confirmed)

1. **Lone `\r`** (deferred from M1): it is an ordinary character, as in ngspice. It is accepted inside free text (title, comments, opaque regions) and is a `ParseError` anywhere else, because it is neither whitespace nor a terminator. `\r\n` is the only CR-bearing terminator.
2. **Title lexing.** The first physical line is one terminal (`TITLE_LINE`, the whole line without its terminator). The transformer decides explicit (`.title …`, case-insensitive) vs. implicit. This avoids a terminal collision between the free text and `.title`. A later `.title` line is an ordinary directive node (`Title`, explicit) and, as in ngspice, replaces the title; both nodes are kept.
3. **Content after `.end`:** only blank lines are allowed (architecture shape). Comment lines after `.end` are decided by the probe in T6 and recorded in decision 0002.
4. **Opaque statements and blocks keep their text and span; nothing is parsed inside.** Nested `.if` blocks are supported by the block rule, not by regular expressions (S2 decides the technique).
5. **`.lib` has two forms in ngspice** (`.lib file [section]` and a `.lib name` … `.endl` definition block). M2 treats every `.lib` line as one opaque statement; a definition block in the main file would have its body parsed normally and `.endl` is an unknown directive. This is documented as a limitation in the spec entry.
6. **Unknown dot-commands** are generic: `.name` followed by the rest of the logical line (continuations included). Typed keyword terminals added in M4 must take priority over the generic one without creating a collision. The generic rule is written so that this works.
7. **Parser output (confirmed).** M2 returns typed, immutable nodes with spans (`model/nodes.py`, `model/transform.py`), not just a Lark tree. Top-level items are `Title`, `BlankLine`, `CommentLine`, `UnknownDirective`, `OpaqueBlock`, `OpaqueStatement` (include/lib) and `End`, each with a `trailing_comment: Span | None` where applicable. `Lines`, indexes and `Document` are M5. Rationale: typed nodes with spans are the architecture's representation (P2, G1) and give M2 something meaningful to assert; converting Lark's `start_pos`/`end_pos` into `Span`s exercises the continuation-span risk now rather than in M3; M3–M5 then extend a working pipeline. The transformer must handle every grammar rule explicitly: an unhandled rule raises (never silently passes through a raw tree), and the tiling test (3.8) catches any gap. The node shapes are internal and unreleased, so they may be refined in M3.
8. **Item spans tile the source.** Each item's span covers its full logical line including terminator(s), and the item spans are contiguous and non-overlapping and cover `[0, len(text))`. This is the main grammar-level correctness invariant and is tested with Hypothesis (T11).
9. **Grammar-to-spec traceability.** Every top-level rule or terminal group in a `.lark` file is preceded by a `// spec: <ID>` comment. A test checks that each referenced ID exists, and that every `supported` spec entry is referenced by at least one rule. This closes the gap that spec entries are only checked against tests, not against the grammar.
10. **Dialect → grammar registry lives in `grammar/loader.py`.** `dialects.py` is the lowest layer and cannot import `grammar/`. The architecture §4 comment ("Dialect enum, registry") is amended in decision 0003.

## 4. Tasks

Every task ends with `ruff check`, `ruff format --check`, `mypy --strict`, and `pytest` (coverage gate) green. Run through `uv run --env-file .env python -m …`. Stop and raise a question (do not decide silently) wherever a task says so.

### Decisions and traceability

**T1 — Decision record 0002: grammar structure policy.**
Write `docs/decisions/0002-grammar-structure-policy.md` covering: optional `.end` + diagnostic; implicit first-line title (flagged); `.title` anywhere replaces; lone `\r` as an ordinary character; content after `.end`; comment forms accepted. Amend architecture §6.3 rule 2 (optional end line), §6.5 (`.title` anywhere), and §19 (add the two confirmed decisions). Record probe facts from the table above and the T6 results.
*Done when:* the record is accepted by the maintainer and the architecture points to it. (Items finalized by T6 are filled in when T6 completes.)

**T2 — Device letters outside the original phasing (resolved by the maintainer).**
The maintainer assigned the remaining ngspice letters A, N, O, P, U, Y and Z to phase 2 (architecture §19 decision 6), and requires all ngspice and LTspice elements to be supported by the end of phase 2. No letter is left unassigned.
*Done when:* the implementer has confirmed decision 6 in §19 and that T9 follows it.

### Spikes (one prototype each; throw-away code lives in `prototype/` or a temp directory)

Each spike answers its questions with a tiny grammar plus tests, under `strict=True`, using the contextual lexer. Results are recorded in decision 0003 (T8). If a spike fails its acceptance criterion, stop and report to the maintainer with the evidence instead of working around it.

**S1 — Continuation lines and comments (highest risk, architecture §20).**
Questions: (a) does an ignored terminal for newline + optional whitespace + `+` work with the contextual lexer, and keep `start_pos`/`end_pos` correct? (b) With ngspice, do `*` comment lines and blank lines between a statement and its `+` line join the statement? Establish by running ngspice (e.g. `V1 in 0` / `* c` / `+ DC 2`, then `.op`/`.print v(in)` and compare with the unbroken line) and record the result. (c) A leading `+` on the first line (title) and `+` after a title line. (d) `+` after `.end`; `+` inside opaque regions (must be untouched). (e) CRLF and mixed endings, and tab/space before `+`.
Acceptance: continuations work for unknown dot-commands and opaque statements with correct spans. If (b) shows that interleaved comments/blank lines *do* join, either the grammar supports them, or the feature is rejected with `UnsupportedConstruct` and a spec entry; report the choice to the maintainer before building on it.

**S2 — Opaque regions.**
Questions: how to match `.control`…`.endc` (non-nesting) and `.if`…`.elseif`/`.else`…`.endif` (nesting) as single opaque items whose contents may be anything (including unsupported elements, unbalanced quotes). Candidates: (a) multi-line terminal regex; (b) context-free rules with a "line that is not a block delimiter" terminal; (c) a pre-pass that segments the source into regions and parses the segments with offset correction. Evaluate against `strict=True` (negative lookahead may not be supported by `interegular`; if so it must not silently disable collision checking), nesting, case-insensitivity, `.endc`/`.endif` missing (error with the opening line's position), and spans.
Acceptance: one technique that supports nested `.if`, passes strict mode honestly, and reports an unterminated block at its opening line.

**S3 — Free text and terminators.**
Question: terminal regexes for free text (title line, comment text, `.include` path, unknown-directive remainder) that exclude the `\r` of `\r\n` but accept a lone `\r` (decision 3.1), and that pass `strict=True`. Check `.title`/`TITLE_LINE` and all comment forms for collisions.
Acceptance: CRLF, LF, mixed, and lone-`\r` inputs all lex as specified; no collision warnings.

**S4 — Composition of core + overlay.**
Question: `%import`/`%override`/`%extend` across files vs. build-time concatenation (architecture §19 decision 5; implementer's choice, subject to strict build per dialect). Evaluate with a dummy second overlay so that adding LTspice later is mechanical; check error messages still point at the right file and line.
Acceptance: one mechanism that compiles each dialect independently under `strict=True` and keeps grammar error locations usable.

### Foundation

**T3 — Grammar loader and registry.**
`src/netlistmod/grammar/loader.py`: a registry mapping `Dialect` → grammar files (`core.lark` plus overlay), `build_parser(dialect)` (Lark, LALR, contextual lexer, `propagate_positions=True`, `strict=True`; cached; never Earley), and `parse_tree(source: SourceText, dialect: Dialect)`. Grammar files are read with `importlib.resources`. No default dialect (architecture §19, decision 17): `dialect` is a required argument everywhere.
*Done when:* tests cover building each registered dialect, that a missing/unknown dialect raises, that the parser is cached, and that no public function has a default for `dialect`.

**T4 — `core.lark` and `ngspice.lark`.**
Implement the grammar per S1–S4 for the scope in section 1. Start from the exploratory `prototype/ngspice.lark` but do not carry its known deviations: it makes the title mandatory, uses a `COMMENT` terminal that matches `*` anywhere (a conflict once expressions arrive in M3), and has the mandatory end line. A `*` comment is valid only at the start of a line; `;` and `$` trailing comments follow the dialect rules established by the T6 probes. Keywords are named, case-insensitive terminals. Each rule carries a `// spec:` comment (decision 3.9).
*Done when:* both files compile under `strict=True`, every construct in section 1 has a rule, and the T7 architecture tests pass.

**T5 — Typed nodes and transformer.**
`src/netlistmod/model/nodes.py` and `transform.py`: the node types from decision 3.7 as frozen dataclasses with `Span`s from `start_pos`/`end_pos` (character offsets). `Title(text, explicit, span)`; `UnknownDirective(name, raw, span)`; `OpaqueBlock(kind, span)` (`control`, `if`); `OpaqueStatement(kind, span)` (`include`, `lib`); `End(span)`; the parse result also records whether `.end` was present (decision 1). Transformer methods dispatch on node type, not position (architecture §6.3 rule 11).
*Done when:* unit tests (T1 tier) check each node, the explicit/implicit title distinction (`.title X`, `.TITLE`, `.title` with no text, an implicit first line, a first line that is blank), and that spans slice back to the expected source text.

### Validation against the solver

**T6 — ngspice behavior probes as solver-backed tests.**
In `tests/solver/` (marker `solver("ngspice")`), reproduce the probe table in section 2 as tests that assert what ngspice reports (e.g. the `Circuit:` title line in the log and the exit code), using temporary copies and the M0 helpers. Add probes for: indented `*` comment lines; `;` and `$` trailing comments (with and without leading whitespace); keyword case (`.END`, `.Title`); tabs as separators; `.title` with and without text; content after `.end` (blank, comment, dot-command, element); `.control`/`.endc` and `.if`/`.endif` handling by the solver; `.lib`/`.include` lines (with a nonexistent file, to see what is reported). Run the equivalent S1 questions as a result check (continuation joining).
*Done when:* the tests pass locally with the solver and skip cleanly without; each probe result is written into the matching spec entry (T12) with solver name, version, and date, and into decision 0002 where it decides policy (T1).

### Error handling (includes M1 review finding 3)

**T7 — `ParseError` and `UnsupportedConstruct` from Lark errors.**
Map Lark exceptions (`UnexpectedCharacters`, `UnexpectedToken`, `UnexpectedEOF`) to `ParseError` built **only** from `SourceText.position(offset)` and `SourceText.excerpt(offset)`, never from Lark's own line/column (they disagree at EOF: Lark reports `(2, 1)` after a trailing newline, whereas `SourceText.position` reports `(1, 3)` because M1 defines no phantom line). Keep the M1 convention and test it explicitly. Add the expected-token information to the message in a stable, readable form. When the offending token starts a statement whose first character is a device letter listed in the dialect matrix (T9), raise `UnsupportedConstruct` (with line, column, excerpt) for `supported`/`planned` letters and `ParseError` for letters with status `error`; unknown letters are `ParseError`. Also make `SourceText.excerpt` preserve tabs in the caret padding so the caret aligns under the offending character in tab-indented lines.
*Done when:* T6-tier negative tests cover: unknown character, unexpected token mid-line, EOF in an unterminated opaque block (position of the opening line), unsupported/planned/unknown element letters, a lone `\r` outside free text, content after `.end`, errors at line 1 and on the last line without a newline, after a CRLF and after tabs, and the EOF-after-trailing-newline case; each asserts line, column, and excerpt text.

### Device matrix and spec entries

**T8 — Decision record 0003: grammar composition, opaque regions, registry location.**
Write `docs/decisions/0003-grammar-composition-and-opaque-regions.md` from the S1–S4 results: the composition mechanism, the continuation approach (including the answer to S1(b)), the opaque-region technique, the lexical rules for free text and terminators, and the registry location (amending architecture §4). Update architecture §6.1/§6.3 accordingly.
*Done when:* the record exists and is consistent with the shipped grammar; any limitation is listed.

**T9 — `docs/grammars/ngspice/devices.md`.**
The per-dialect device-letter matrix (architecture §6.7): every ngspice letter with status `supported`, `planned` (all of phase 2, including A, N, O, P, U, Y, Z), or `error` (a letter ngspice does not define), linking each planned letter to its phase and milestone. In M2 no element is `supported`. The loader reads the statuses (for T7) from a machine-readable form kept in sync with the document (for example a front-matter table checked by a test against the Markdown).
*Done when:* a test fails if the machine-readable matrix and the document disagree.

**T10 — Spec entries and spec-coverage check.**
Create the `docs/grammars/ngspice/` spec entries (format of architecture §11.2) for each M2 construct, e.g. `NG-STR-…` structure, comments, continuation, title, end, opaque blocks, opaque statements, unknown directives, with manual citations (record exact sections; paraphrase only), `status` (`documented`/`observed`/`validated`), `validated_on` from T6, and test references. Add `tests/architecture/test_spec_coverage.py`: parses the entries (PyYAML as a dev dependency, MIT-licensed; confirm the license), checks that every `tests:` reference resolves to an existing test, that every `supported` entry has at least one, and the grammar↔spec traceability of decision 3.9. Add `docs/grammars/ngspice/discrepancies.md` for any manual/solver disagreements found.
*Done when:* the checker passes on the real entries and has self-tests proving it fails on an entry with a missing test, a dangling reference, and an unreferenced supported entry.

### Tests (T2/T3/T5/T6 tiers)

**T11 — Grammar test suite.**
- *Accept/reject (T2):* one accept and one reject test per spec entry in `tests/grammar/ngspice/`.
- *Corpus:* author `tests/corpus/ngspice/structure_basic/` (title only; comments; blank lines; unknown directives with continuations; `.control` block; nested `.if`; `.include`/`.lib`; missing `.end`) with a manifest (origin: authored in this repository; confirm author/license with the maintainer).
- *Round trip (T3):* for each corpus file and for inline byte cases (CRLF, mixed endings, no final newline, tabs, trailing whitespace, lone `\r` in free text, non-ASCII `µ`): the parse succeeds, item spans tile the source, and `SourceText.from_bytes(data).to_bytes() == data`.
- *Property (T5, Hypothesis):* generate structural netlists from a strategy (random mixes of the item kinds, random line endings, random continuation placement) and assert: parse succeeds, spans tile the source, concatenated item text equals the source, the parse result is stable under re-parse. Include shrinking-friendly strategies and a fixed seed example.
- *Negative (T6):* the T7 cases above.
*Done when:* all pass, including the 90% coverage gate on `grammar/` and `model/`.

**T12 — `SourceText.write()`: permissions and symlinks.**
`write()` currently creates the temporary file with mode 0600 and replaces a symlink with a regular file. Fix: (a) write through a symlink (resolve the target, then place the temporary file in the *target's* directory and replace the target); (b) an existing file keeps its permission bits (`shutil.copymode`); (c) a new file gets the normal umask-derived permissions rather than 0600; (d) on any failure the target is untouched and no temporary file remains (already tested). Document what is *not* preserved (ownership, hard links, extended attributes). POSIX-only behavior cannot be exercised on this Windows machine: add tests that skip with a clear reason on Windows (and when symlinks cannot be created), run them under WSL or another POSIX environment if available, and say in the report whether that was done. On Windows, add a test that a read-only target raises `PermissionError` and is left intact.
*Done when:* the tests pass on Windows (with the POSIX ones skipped for a stated reason) and the maintainer is told whether they ran on POSIX.

### Gates and closing

**T13 — Architecture and packaging checks.**
Confirm the T7-tier contracts still pass (no `subprocess` in `src/`, layering, no GPL runtime dependency, every packaged `.lark` builds under `strict=True`, now non-vacuously). Add a test that the registry covers every `Dialect` member except those explicitly pending (LTspice until M8), and a packaging test that builds the wheel (`uv build`) and asserts the `.lark` files are inside it and loadable from the installed wheel.
*Done when:* the new and existing contracts pass; the wheel test passes in a clean temporary environment.

**T14 — Docs.**
Update `docs/testing.md` (new test locations, the solver probes, how to add a spec entry and its `// spec:` marker), `README.md` status, `CHANGELOG.md` (Unreleased), and `docs/usage/` only if user-visible behavior exists. Public names get docstrings.
*Done when:* docs match the code and links resolve.

**T15 — M2 exit check and archive.**
Run the full check set (`ruff check`, `ruff format --check`, `mypy --strict`, `pytest` with the coverage gate, `pre-commit run --all-files`, the solver tests). Verify a fresh clone passes the corpus hash tests and the packaging test. Then close the milestone per the plan: set this document's status to `COMPLETE (date)`, `git mv` it to `docs/design/archive/`, fix its links, link it from the M2 heading in the plan, and update the index in the design README. Report open items for M3.
*Done when:* all checks are green and the archive step is done.

## 5. Dependencies between tasks

```
T1, T2                      (independent, first)
S1, S2, S3 → S4             (S4 needs the shapes S1–S3 produce)
S1–S4 → T8 → T3 → T4 → T5
T6 (needs only M0/M1)       → T1 (fills policy), T10 (validated_on)
T9 → T7                     (matrix drives UnsupportedConstruct)
T4, T5, T7 → T10 → T11
T12                         (independent; SourceText only)
T11, T12 → T13 → T14 → T15
```

## 6. Out of scope for M2

Elements, values, `.param`/`.model`/`.subckt`, typed directives, `Document`/`Lines`/indexes, the diagnostics API (the missing-`.end` and implicit-title *facts* are recorded in the parse result only), LTspice grammar and dialect specifics (M8), and edit planning.

## 7. Deferred minor items from the M1 review (not in M2)

`SourceText` with a bare `"utf-16"` encoding name; `Dialect` as `StrEnum`; `--require-solver` accepting several solvers; solver discovery returning `None` instead of raising on non-Windows LTspice.
