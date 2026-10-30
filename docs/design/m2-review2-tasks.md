# M2 second review — required fixes

> **Status:** READY FOR REVIEW — F1–F6 done (2026-10-30); exit report in section 6. Do not archive until the maintainer approves the re-review.
> **Part of:** [m2-tasks.md](./m2-tasks.md) (milestone M2, second review round). Governed by [architecture.md](../architecture.md) (P5, P8, P13, §6.3, §11). The M2 task list stays open until this round passes the maintainer's re-review; archive both together then.

## 1. Context

The reworked grammar is accepted in structure (real Lark rules, thin transformer, all checks green). Review against the ngspice manual found places where it does not match the manual, which the strict policy (P5, P8) forbids. This list fixes them. Everything not listed here stays as delivered.

## 2. Decisions (maintainer, 2026-10-22)

1. **Citations.** Cite the ngspice manual with a proper reference and the correct section numbers (F1).
2. **`//` is an end-of-line comment delimiter** (manual §2.4.4). A standalone `//` line stays rejected.
3. **`.include` and `.lib` cannot be continued** (manual §2.4.5), by either continuation form. `.title` already cannot be.
4. **Backslash continuation is supported** (manual §2.4.5): a line ending in two backslashes continues on the next line.
5. **`.end` stays strict:** no trailing comment (`.end ; c` and `.end // c` remain syntax errors). Record the reading in the spec: §2.4.2 defines `.end` as the last line with no comment form; §2.4.4's `<any command>` is read as applying to commands that take arguments.

Noted, no change required: a very deeply nested `.if` (about 300 levels) raises `RecursionError`; the Hypothesis oracle keeps its current generator (broader generation is scheduled for the end of phase 1, see 4); the authors and licenses of `structure_basic` and `structure_rejects` (`xdylanm`, MIT, authored in this repository) are confirmed.

## 3. Tasks

Every task ends with `ruff check`, `ruff format --check`, `mypy --strict`, and `pytest` (coverage gate) green, run as `uv run --env-file .env python -m <tool>` (see AGENTS.md). Syntax stays in the grammar (P13): no regular expressions or line scanning in Python.

[x] **F1 — Manual references.**
The specs, decisions 0002/0003, `discrepancies.md`, test docstrings and code comments cite sections that do not exist in the manual (§5.1.1, §5.2.1–5.2.4). Correct them against the current online copy, [ngspice manual (HTML)](https://ngspice.sourceforge.io/docs/ngspice-html-manual/manual.xhtml). The sections this milestone uses are: 2.1.1 Input file structure; 2.4.1 .TITLE; 2.4.2 .END Line; 2.4.3 Comments; 2.4.4 End-of-line comments; 2.4.5 Continuation lines; 2.8 .INCLUDE (check `.LIB` and `.control` sections and cite them too).
- Add `docs/references.md` with one entry per reference: key, title, publisher, URL, edition/version as shown in the manual, and access date. Key the ngspice manual as `[ngspice-manual]`; add the HTML link next to the PDF link in architecture §11.1.
- `manual_ref` in every spec entry uses the form `[ngspice-manual] §2.4.4 "End-of-line comments"`, with the version recorded in `docs/references.md`.
- Extend the spec checker: `manual_ref` must match `[<key>] §<number> "<title>"` and `<key>` must exist in `docs/references.md`. Add a self-test for a malformed or unknown reference.
*Done when:* no `§5.` citation remains (a test or grep check), every spec entry passes the new check, and the references file records the manual edition.

[x] **F2 — `//` end-of-line comments.**
Add `//` as a trailing-comment delimiter alongside `;` and `$` in the grammar (manual §2.4.4). A `//` comment runs to the end of the line, so quotes inside it cannot cause an error. A standalone `//` line (no command before it) is rejected, as are standalone `;` and `$` lines. Settle, cite and test whether `//` needs preceding whitespace (the manual only recommends a space; default: no requirement, as for `;` and `$`) and what happens in `.include a//b`, a path containing `//`; record the behaviour in the spec. Update `NG-COM-001`/`NG-TXT-001` and decision 0002 (remove the claim that the manual is silent on `//`).
*Also fixed (maintainer, 2026-10-30):* a comment on a continued line no longer ends the statement (§2.4.5 general form); `trailing_comment` became `trailing_comments`.
*Done when:* tests cover `.param n1=1 // new value`, `.options a // don't`, `.options a='x//y'` (quoted, accepted), a standalone `// c` line (rejected at its position), and the trailing-comment spans.

[x] **F3 — `.include` and `.lib` are not continuable.**
In the grammar, end `.include` and `.lib` statements with a terminator that outranks the continuation terminals, as titles, comments and `.end` already do, so a `+` line after them is a syntax error. Reject the backslash form for them as well (F4). Update `NG-OPA-002` and the discrepancies note.
*Done when:* `.include a` / `+ b` and `.lib a b` / `+ c` are rejected with positions, and a backslash at the end of an `.include`/`.lib` line does not continue it.

[x] **F4 — Backslash continuation.**
Support a line ending in two backslashes immediately before the line terminator (`\\` then LF or CRLF) as a continuation, for the same continuable statements as `+`, in the grammar (an ignored terminal, with free-text terminals written so they do not swallow the trailing backslashes). The continued line's leading whitespace is ignored. Settle, cite or mark `observed`, and test: trailing whitespace after the backslashes (default: not a continuation); mixing `+` and `\\` in one statement; a blank or comment line after `\\`; a single backslash or backslashes elsewhere in a line (ordinary text); CRLF. Spans of a continued statement cover every physical line. Probe ngspice 47 for the backslash form and for `.include` continuation, and record the results as discrepancy evidence (observations only). Update `NG-CNT-001`, decision 0002/0003, `architecture.md` §6.3 rule 3 if the terminal changes.
*Implementation choices (2026-10-30, maintainer delegated):* (1) `BS_CONT` is a token inside the statement's text rule, not an ignored terminal: an ignored terminal is active in every lexer state and would silently drop a line holding only `\\`, against P5. (2) The next line must start with statement text; a blank, `*` comment, `+` or comment-only line after `\\` is an error at the backslashes (ngspice 47 also fails). (3) `\\` followed by spaces is text (default kept; ngspice 47 continues; discrepancy). (4) `\\` at the end of an end-of-line comment is comment text (narrow reading; ngspice 47 continues; discrepancy). (5) `\\` at the end of `.include`/`.lib` is a syntax error (ngspice 47 treats it as part of the path and then fails). (6) Three backslashes are one literal backslash plus a continuation (ngspice 47 agrees). (7) `.foo a \\` at end of input fails at end of input. Probes: `tests/solver/` backslash tests; findings in `discrepancies.md`.
*Done when:* tests cover both forms, the error for a continuation after an unsupported line is positioned correctly, and a line using `\\` no longer produces a misleading "unsupported element" error.

[x] **F5 — Keep `.end` strict.**
No grammar change. Update `NG-END-001` and decision 0002 with the reading in decision 5 above, and keep the reject-corpus entry for a trailing comment on `.end`; add `.end // c`.
*Done when:* the spec and reject corpus match.

[x] **F6 — Exit.**
Run the full check set, a fresh-clone test, and the solver tests. Report what changed and every "settle" decision with its citation. Set this document's and `m2-tasks.md`'s status to `READY FOR REVIEW`. **Do not archive** either file.

## 4. Not in this round

The deep-nesting `RecursionError`; changes to the Hypothesis oracle; `+` requiring a following space (manual: "plus additional space"; leave as is unless the settle work shows a reason).

## 5. Carried to the end of phase 1

Broader testing, scheduled in the M9 review package: extend the independent Hypothesis oracle to generate CRLF and mixed endings, `+` and `\\` continuations, trailing comments (`;`, `$`, `//`), indentation, whitespace-only lines and block variants, and run the 20,000-line performance test in the same pass.

## 6. Exit report (F6, 2026-10-30)

Work is on branch `m2-review2`, one commit per task: F1 `ab37d5f`, F2 `3727821`, F3 `5661296`, F4 `c730c9d`, F5 `f466627`, F6 (this commit). Citations use the edition in [references.md](../references.md).

### 6.1 What changed

- **F1.** `docs/references.md`; every `manual_ref` uses `[ngspice-manual] §<n> "<title>"` with numbers checked against the HTML manual (47+, preface as of Mar 2026). The spec checker enforces the form and the key, and rejects the replaced citation forms.
- **F2.** `//` is an end-of-line comment delimiter (§2.4.4). Also fixed with the maintainer's approval: a comment on a line of a continued statement no longer ends the statement (§2.4.5 general form); `trailing_comment` became `trailing_comments`.
- **F3.** `.include` and `.lib` end at the line terminator (`line_rest` + `LINE_END`), so a `+` line after them is a positioned error (§2.4.5).
- **F4.** Backslash continuation (§2.4.5) as the `BS_CONT` token.
- **F5.** No grammar change; `.end` reading recorded; `.end // c` reject fixture.
- **F6.** Architecture test pinning the terminals that strict mode cannot collision-check (6.4); decision 0003 corrected; statuses set.

### 6.2 Settle decisions

| Point | Decision | Basis | ngspice 47 |
|---|---|---|---|
| Whitespace before `//` | Not required | §2.4.4 (space only recommended) | agrees |
| `.include a//b` | Path `a`, comment `//b`; quote paths with `//` | §2.4.4 | agrees (reports `a` missing) |
| Standalone `;`/`$`/`//` line | Rejected | §2.4.4 (comment after a command) | accepts `//` line (discrepancy) |
| Comment on a continued line | Allowed; next `+` or `\\` line still continues | §2.4.5 general form | agrees |
| `.include`/`.lib` + `+` line | Rejected at the `+` line | §2.4.5 | also fails |
| `.include`/`.lib` ending in `\\` | Syntax error at the backslashes | §2.4.5 | reads it as part of the path, then fails |
| `\\` followed by spaces | Text, not a continuation (default kept) | §2.4.5 "ending the line with two backslashes" | continues (discrepancy) |
| `\\` ending an end-of-line comment | Comment text, not a continuation | narrow reading of §2.4.4/§2.4.5 | continues (discrepancy) |
| `\\` ending a `*` comment, title or `.end` | Text (comment, title) or error (`.end`) | §2.4.1, §2.4.3, §2.4.2 | agrees for `*` comments |
| Blank, comment, `+` or comment-only line after `\\` | Error at the backslashes | §2.4.5 ("follow immediately") | also fails |
| Line holding only `\\` | Error | §2.4.5 | also fails |
| Mixing `+` and `\\` | Allowed on different lines of one statement | §2.4.5 | agrees |
| Single `\` or `\\` inside a line | Text | §2.4.5 | agrees |
| Three backslashes at line end | One literal backslash plus a continuation | §2.4.5 | agrees |
| `.end` with `;`/`$`/`//` comment | Rejected | §2.4.2 (no comment form); §2.4.4 applies to commands with arguments | accepts (discrepancy) |

### 6.3 Deviations from the task text

- **F4 asked for an ignored terminal.** `BS_CONT` is instead a token of the statement text rule (`rest`). An ignored terminal is active in every lexer state, so a line holding only `\\` would be silently dropped (P5). As a `rest` token it exists only inside continuable statements and `line_rest` cannot accept it. Recorded in decision 0003 and architecture §6.3 rule 3. `+` remains an ignored terminal.
- **`.include`/`.lib` with trailing `\\` is an error**, not path text. F3 asked only that it not continue; an error is the narrower outcome and avoids a path ending in two backslashes.

### 6.4 Findings for the maintainer

- **Strict mode does not collision-check terminals with lookarounds.** interegular cannot model them; Lark logs a warning and skips them without failing. Eight ngspice terminals are affected: `BLOCK_TEXT`, `BS_CONT`, `COMMENT_LINE`, `DOT_NAME`, `TEXT`, `TITLE_ARG`, `TITLE_TEXT`, `TRAILING_COMMENT` (all but `BS_CONT` predate this round). A manual review found no overlap between terminals of equal priority that can share a lexer state. `test_terminals_outside_strict_collision_checking_are_known` pins the list so it cannot grow silently, and `test_strict_mode_does_not_check_a_lookahead_terminal_for_collisions` demonstrates the gap. Decision 0003 previously claimed full checking; it is corrected. Rewriting these terminals without lookarounds is a design question left open.

### 6.5 Verification and limitations

- Full check set on the branch: `pytest` (with coverage gate, 96%), `ruff check`, `ruff format --check`, `mypy --strict`: green. Counts are in the F6 commit report.
- Solver tests ran against ngspice 47 (`ngspice_con.exe`); none skipped.
- Fresh clone of `f466627` into a temporary directory: the suite passed with the clone's `src/` first on `PYTHONPATH`. `uv` is not on PATH in this environment, so the clone was not set up with `uv sync`; the repository `.venv` interpreter was used.
- `pre-commit run --all-files`: every hook passes except `check-toml`, which Windows Smart App Control blocks repeatedly (WinError 4551; AGENTS.md). No TOML file changed in this round; `pyproject.toml` parses with `tomllib`.
- The two POSIX `SourceText.write()` tests remain skipped on Windows; they were not run on POSIX.
- Not in this round (section 4) and still open: deep `.if` nesting `RecursionError`; the Hypothesis oracle does not yet generate `\\` continuations or `//` comments (section 5).
