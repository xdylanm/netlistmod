# Design documents

Active plans and design notes live in this folder. Completed work records move to
[archive/](./archive/) so that this folder only shows what is current.

## Conventions

- Every document starts with a `Status:` line: `DRAFT`, `READY` (approved, not started), `ACTIVE`, `READY FOR REVIEW` (implemented, awaiting the maintainer), or `COMPLETE (date)`.
- When a milestone or design finishes and the maintainer has **approved its review**, `git mv`
  its task list or design note into `archive/` (keep the file name), set the status to
  `COMPLETE`, and fix relative links. A finished implementation is `READY FOR REVIEW`, not
  `COMPLETE`, and stays in this folder until then. The plan that owns it keeps a link to the
  archived record.
- Archived files are history: do not edit them except to fix links. Changes to
  normative behavior go through a decision record in `../decisions/`.
- **Living references** (`elements.md`, `statements.md`, `document-layer.md`, `edit-layer.md`) describe the library as it is, not a piece of work. They stay `ACTIVE` in this folder and are not archived. A change to the public API updates them in the same commit; `tests/architecture/test_design_notes.py` fails if a public name is missing. Their state at each milestone is in Git history. They were renamed in M9 from `m3-elements.md`, `m4-statements.md`, `m5-document.md` and `m6-edits.md`, the names the archived task lists still use in prose.
- Stay flat until `archive/` grows past roughly a dozen files; then group by phase
  (`archive/phase-1/`).

## Index

| Document | Status |
|---|---|
| [phase-1-plan.md](./phase-1-plan.md) | ACTIVE |
| [m9-tasks.md](./m9-tasks.md) | READY FOR REVIEW |
| [phase-1-review.md](./phase-1-review.md) | READY FOR REVIEW |
| [m9-code-changes.md](./m9-code-changes.md) | READY |
| [elements.md](./elements.md) | ACTIVE (living reference) |
| [statements.md](./statements.md) | ACTIVE (living reference) |
| [document-layer.md](./document-layer.md) | ACTIVE (living reference) |
| [edit-layer.md](./edit-layer.md) | ACTIVE (living reference) |
| [archive/m0-tasks.md](./archive/m0-tasks.md) | COMPLETE (2026-10-20) |
| [archive/m1-tasks.md](./archive/m1-tasks.md) | COMPLETE (2026-10-21) |
| [archive/m2-tasks.md](./archive/m2-tasks.md) | COMPLETE (2026-10-30) |
| [archive/m2-review2-tasks.md](./archive/m2-review2-tasks.md) | COMPLETE (2026-10-30) |
| [archive/m3-tasks.md](./archive/m3-tasks.md) | COMPLETE (2026-10-30) |
| [archive/m4-tasks.md](./archive/m4-tasks.md) | COMPLETE (2026-10-31) |
| [archive/m5-tasks.md](./archive/m5-tasks.md) | COMPLETE (2026-10-31) |
| [archive/m6-tasks.md](./archive/m6-tasks.md) | COMPLETE (2026-10-31) |
| [archive/m7-tasks.md](./archive/m7-tasks.md) | COMPLETE (2026-10-31) |
| [archive/m8-tasks.md](./archive/m8-tasks.md) | COMPLETE (2026-11-02) |
