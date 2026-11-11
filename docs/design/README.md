# Design documents

Active plans and design notes live in this folder. Completed work records move to
[archive/](./archive/) so that this folder only shows what is current.

## Conventions

- Every document starts with a `Status:` line: `DRAFT`, `READY` (approved, not started), `ACTIVE`, `READY FOR REVIEW` (implemented, awaiting the maintainer), or `COMPLETE (date)`.
- When a milestone or design finishes and the maintainer has **approved its review**, `git mv`
  its task list or design note into `archive/phase-N/` (keep the file name), set the status to
  `COMPLETE`, and fix relative links. A finished implementation is `READY FOR REVIEW`, not
  `COMPLETE`, and stays in this folder until then. The plan that owns it keeps a link to the
  archived record.
- Archived files are history: do not edit them except to fix links. Changes to
  normative behavior go through a decision record in `../decisions/`.
- **Living references** (`elements.md`, `statements.md`, `document-layer.md`, `edit-layer.md`) describe the library as it is, not a piece of work. They stay `ACTIVE` in this folder and are not archived. A change to the public API updates them in the same commit; `tests/architecture/test_design_notes.py` fails if a public name is missing. Their state at each milestone is in Git history. They were renamed in M9 from `m3-elements.md`, `m4-statements.md`, `m5-document.md` and `m6-edits.md`, the names the archived task lists still use in prose.
- `archive/` is grouped by phase: phase 1's records are in `archive/phase-1/` and phase 2's in `archive/phase-2/`.

## Index

| Document | Status |
|---|---|
| [phase-2-plan.md](./phase-2-plan.md) | ACTIVE |
| [m19-tasks.md](./m19-tasks.md) | ACTIVE |
| [elements.md](./elements.md) | ACTIVE (living reference) |
| [statements.md](./statements.md) | ACTIVE (living reference) |
| [document-layer.md](./document-layer.md) | ACTIVE (living reference) |
| [edit-layer.md](./edit-layer.md) | ACTIVE (living reference) |
| [archive/phase-2/m10-tasks.md](./archive/phase-2/m10-tasks.md) | COMPLETE (2026-11-03) |
| [archive/phase-2/m12-tasks.md](./archive/phase-2/m12-tasks.md) | COMPLETE (2026-11-04) |
| [archive/phase-2/m11-tasks.md](./archive/phase-2/m11-tasks.md) | COMPLETE (2026-11-04) |
| [archive/phase-2/m13-tasks.md](./archive/phase-2/m13-tasks.md) | COMPLETE (2026-11-06) |
| [archive/phase-2/m14-tasks.md](./archive/phase-2/m14-tasks.md) | COMPLETE (2026-11-06) |
| [archive/phase-2/m15-tasks.md](./archive/phase-2/m15-tasks.md) | COMPLETE (2026-11-06) |
| [archive/phase-2/m15b-tasks.md](./archive/phase-2/m15b-tasks.md) | COMPLETE (2026-11-09) |
| [archive/phase-2/m16-tasks.md](./archive/phase-2/m16-tasks.md) | COMPLETE (2026-11-09) |
| [archive/phase-2/m17-tasks.md](./archive/phase-2/m17-tasks.md) | COMPLETE (2026-11-10) |
| [archive/phase-2/m18-tasks.md](./archive/phase-2/m18-tasks.md) | COMPLETE (2026-11-11) |
| [archive/phase-2/phase-2-code-changes.md](./archive/phase-2/phase-2-code-changes.md) | COMPLETE (2026-11-03) |
| [archive/phase-1/m0-tasks.md](./archive/phase-1/m0-tasks.md) | COMPLETE (2026-10-20) |
| [archive/phase-1/m1-tasks.md](./archive/phase-1/m1-tasks.md) | COMPLETE (2026-10-21) |
| [archive/phase-1/m2-tasks.md](./archive/phase-1/m2-tasks.md) | COMPLETE (2026-10-30) |
| [archive/phase-1/m2-review2-tasks.md](./archive/phase-1/m2-review2-tasks.md) | COMPLETE (2026-10-30) |
| [archive/phase-1/m3-tasks.md](./archive/phase-1/m3-tasks.md) | COMPLETE (2026-10-30) |
| [archive/phase-1/m4-tasks.md](./archive/phase-1/m4-tasks.md) | COMPLETE (2026-10-31) |
| [archive/phase-1/m5-tasks.md](./archive/phase-1/m5-tasks.md) | COMPLETE (2026-10-31) |
| [archive/phase-1/m6-tasks.md](./archive/phase-1/m6-tasks.md) | COMPLETE (2026-10-31) |
| [archive/phase-1/m7-tasks.md](./archive/phase-1/m7-tasks.md) | COMPLETE (2026-10-31) |
| [archive/phase-1/m8-tasks.md](./archive/phase-1/m8-tasks.md) | COMPLETE (2026-11-02) |
| [archive/phase-1/m9-tasks.md](./archive/phase-1/m9-tasks.md) | COMPLETE (2026-11-03) |
| [archive/phase-1/phase-1-review.md](./archive/phase-1/phase-1-review.md) | COMPLETE (2026-11-03) |
| [archive/phase-1/phase-1-plan.md](./archive/phase-1/phase-1-plan.md) | COMPLETE (2026-11-03) |
