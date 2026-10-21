# Project rules

The authority for design and behavior is [docs/architecture.md](docs/architecture.md).
This file summarizes working rules; it does not replace or duplicate that document.

## Constitution

- **P1 (architecture §2):** source text is the single source of truth.
- **P2 (§2):** represent parsed content as typed views; edits are span replacements.
- **P3 (§2):** preserve exact round-trip text and make minimal diffs.
- **P4 (§2):** topology is read-only.
- **P5 (§2):** use strict grammar and fail loudly.
- **P6 (§2):** every grammar construct needs a spec entry and tests.
- **P7 (§2):** dialects are separate grammars; callers select a dialect.
- **P9 (§2):** never launch a simulator from `src/`.
- **P10 (§2, §12):** keep clean-room provenance; do not use GPL-derived code or tests,
  including material from spicelib.

## Working rules

- Follow the working agreement in architecture §15. Do not silently resolve open
  questions in §21 or weaken an invariant to make a test pass.
- Make architecture changes through a decision record in `docs/decisions/`.
- Detailed requirements belong in `docs/design/`.
- Follow the layer boundaries and package layout in architecture §§3–4.
- Add tests before or with each grammar construct (testing tiers T1–T9 in §10).
- Use golden-diff tests for edits. Corpus files need manifests and byte-exact
  preservation; `.gitattributes` disables text conversion for corpus and golden files.
- `prototype/` is exploratory and must not be imported by the package.

## Commands

Copy `.env.example` to `.env` and set local solver paths. Run tests, lint,
formatting, type checks, and hooks through `uv run --env-file .env ...`.
Solver tests are local-only and skip with a reason when a solver is unavailable.
