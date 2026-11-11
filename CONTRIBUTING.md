# Contributing

Read [AGENTS.md](AGENTS.md) and [docs/architecture.md](docs/architecture.md)
before changing code. The architecture is authoritative; record proposed
architecture changes under `docs/decisions/` before implementing them.

## Clean-room and provenance

Do not copy or derive code, tests, or fixtures from GPL-licensed projects,
including spicelib. Author fixtures independently or export them from a project
you own. Each corpus family must have a manifest recording origin, license,
author, date, and notes, and a row in [docs/provenance.md](docs/provenance.md).
Preserve fixture bytes exactly.

## Development checks

Use Python 3.13 or newer and uv. Copy `.env.example` to `.env`, set local solver
paths if installed, and run checks as described in [docs/testing.md](docs/testing.md).
Solver tests must skip cleanly when the corresponding solver is unavailable.

## Pull requests

Each milestone is one pull request. CI runs lint, types and the solver-free tests on Linux and
Windows. It does not run solvers, so the local run with both solvers is still required. Merge with
"Rebase and merge" after the maintainer's review, and only when CI is green; on the current
repository plan this is a convention, not enforced by branch protection.
