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
"Rebase and merge" after the maintainer's review, and only when CI is green. A ruleset protects
`main`: changes arrive by pull request, and the CI jobs must pass before a merge
([decision 0023](docs/decisions/0023-v1-beta-release.md) item 3).

## Compatibility

The public API and what SemVer covers are set in
[architecture §18](docs/architecture.md#18-compatibility-and-versioning). Removing or renaming a
public name, or changing a public signature, needs a major version; deprecate first, with a
`DeprecationWarning` for at least one minor release, as §18 describes. The tests treat warnings
as errors. Label each `CHANGELOG.md` entry **Breaking**, **Deprecated**, **Refused** or
**Accepted** where it applies.
