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
formatting, type checks, and hooks through `uv run --env-file .env python -m <tool>`
(for example `python -m pytest`, `python -m mypy`, `python -m ruff check`).
Solver tests are local-only and skip with a reason when a solver is unavailable.

### Use the project virtual environment by default

Do not expect `uv` or the dev tools on `PATH`: they are installed in `.venv`, so a bare `uv` fails
with "command not found" even though the project is set up. Do not install them or look for another
copy. Start every command from the venv's interpreter, which is also the signed one that Smart App
Control allows (below):

```powershell
.venv\Scripts\python.exe -m uv run --env-file .env python -m pytest
```

Elsewhere in the docs, read `uv run ...` as this form when `uv` is not on `PATH`. On Linux the
interpreter is `.venv/bin/python`.

### Windows Smart App Control (read before debugging a tool failure)

On the maintainer's Windows machine, Smart App Control can block unsigned
executables and native extensions. A tool may then fail with `DLL load failed`,
OS error 4551 ("An Application Control policy has blocked this file"), or a
mypy/pytest internal error or crash that is not caused by the code. Always invoke
tools as `python -m <tool>` (the signed interpreter), never through the
`pytest.exe`/`mypy.exe` shims. If a tool still crashes with an unexplained
internal error, rerun it once; if it passes, treat it as host noise and do not
change code, configuration, or dependencies in response. If it fails repeatedly,
report it instead of working around it. Details: [docs/testing.md](docs/testing.md).
