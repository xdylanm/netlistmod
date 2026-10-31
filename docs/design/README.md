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
- Stay flat until `archive/` grows past roughly a dozen files; then group by phase
  (`archive/phase-1/`).

## Index

| Document | Status |
|---|---|
| [phase-1-plan.md](./phase-1-plan.md) | ACTIVE |
| [m3-elements.md](./m3-elements.md) | ACTIVE |
| [m4-statements.md](./m4-statements.md) | ACTIVE |
| [archive/m0-tasks.md](./archive/m0-tasks.md) | COMPLETE (2026-10-20) |
| [archive/m1-tasks.md](./archive/m1-tasks.md) | COMPLETE (2026-10-21) |
| [archive/m2-tasks.md](./archive/m2-tasks.md) | COMPLETE (2026-10-30) |
| [archive/m2-review2-tasks.md](./archive/m2-review2-tasks.md) | COMPLETE (2026-10-30) |
| [archive/m3-tasks.md](./archive/m3-tasks.md) | COMPLETE (2026-10-30) |
| [archive/m4-tasks.md](./archive/m4-tasks.md) | COMPLETE (2026-10-31) |
