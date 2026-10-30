# M2 second review — required fixes

> **Status:** ACTIVE — F1–F5 done; F6 open
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

[ ] **F6 — Exit.**
Run the full check set, a fresh-clone test, and the solver tests. Report what changed and every "settle" decision with its citation. Set this document's and `m2-tasks.md`'s status to `READY FOR REVIEW`. **Do not archive** either file.

## 4. Not in this round

The deep-nesting `RecursionError`; changes to the Hypothesis oracle; `+` requiring a following space (manual: "plus additional space"; leave as is unless the settle work shows a reason).

## 5. Carried to the end of phase 1

Broader testing, scheduled in the M9 review package: extend the independent Hypothesis oracle to generate CRLF and mixed endings, `+` and `\\` continuations, trailing comments (`;`, `$`, `//`), indentation, whitespace-only lines and block variants, and run the 20,000-line performance test in the same pass.
