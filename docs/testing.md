# Testing and local development

## Environment

Use Python 3.13 or newer and [uv](https://docs.astral.sh/uv/). From the
repository root:

```powershell
uv sync
Copy-Item .env.example .env
```

Edit `.env` to set `NGSPICE_EXE` and `LTSPICE_EXE` to local executable paths.
Quote values that contain special characters; forward slashes work in Windows
paths and avoid dotenv backslash escaping. `.env` is ignored by Git and is not
needed when a solver is available on `PATH` or in a standard install location.
Never put credentials in this file.

Run checks through uv so `.env` is loaded consistently:

```powershell
uv run --env-file .env python -m pytest
uv run --env-file .env python -m ruff check
uv run --env-file .env python -m ruff format --check
uv run --env-file .env python -m mypy --strict
uv run --env-file .env python -m pre_commit run --all-files
```

Use `python -m <tool>` (the signed interpreter) instead of the bare tool
executables; on Windows with Smart App Control the unsigned shims can be blocked
(see the note at the end of this document).

`pytest` enforces the project's 90% line-coverage target.

## Test tiers

Tests follow architecture §10:

| Tier | Purpose |
|---|---|
| T1 | Unit tests for values, spans, and transformation behavior. |
| T2 | Grammar conformance against construct specifications. |
| T3 | Byte-exact round-trip tests, including line endings and encoding. |
| T4 | Golden-diff tests for edits. |
| T5 | Hypothesis property tests for invariants. |
| T6 | Negative tests for malformed input and forbidden operations. |
| T7 | Architecture contracts: source boundaries, layering, strict grammars, and licensing. |
| T8 | Optional local simulator validation. |
| T9 | Documentation examples and spec-coverage checks. |

Corpus fixtures live under `tests/corpus/<dialect>/<family>/`. Each family has a
manifest with provenance and SHA-256 hashes; tests detect missing manifests or
any byte changes. Golden outputs are also byte-sensitive. Do not normalize
their whitespace or line endings.

Source-layer tests are in `tests/test_source.py`, `tests/test_errors.py`,
`tests/test_dialects.py`, and `tests/roundtrip/`. The byte-exact cases are
defined inline in Python so editors and Git cannot normalize their BOMs, NULs,
or line endings. They cover UTF-8/UTF-16 BOMs, CRLF and mixed endings, lone CR,
Windows-1252 `µ`, undefined Windows-1252 bytes, and filesystem write/read
round-trips. The corpus round-trip test covers every file under `tests/corpus/`.

## Solver tests

Solver tests are local-only. Mark a test with
`@pytest.mark.solver("ngspice")` or `@pytest.mark.solver("ltspice")` and request
the `solver` fixture. Discovery checks the corresponding environment variable,
then `PATH`, then standard install locations. The fixture skips with a reason
when its solver is absent. To make absence fail instead:

```powershell
uv run --env-file .env python -m pytest --require-solver ngspice -m solver
```

The test helpers run in temporary directories, use batch mode, and set a
timeout. No simulator is launched from `src/`. Run only solver tests with
`uv run --env-file .env python -m pytest -m solver`.

## Writing golden tests

Keep the input fixture immutable. Copy it to a temporary directory, apply the
operation to the copy, and compare the complete expected output (or a unified
diff) so unrelated formatting changes are caught. Preserve byte-level cases
such as CRLF, mixed endings, missing final newlines, BOMs, tabs, and trailing
whitespace; put golden files in `tests/golden/` so Git and pre-commit do not
rewrite them.

## M0 verification findings (2026-10-20)

### Toolchain

- Python 3.14.3 and uv 0.13.4 are installed locally. `uv sync` successfully
  manages the existing `.venv` and creates `uv.lock`.
- Lark is MIT-licensed. The selected floor is `lark>=1.2.2`; `strict=True` was
  verified against Lark 1.2.2 and the lock currently resolves Lark 1.3.1.
- `interegular` is a runtime dependency: Lark's `strict=True` uses it to detect
  terminal collisions (MIT-licensed, verified by the maintainer).

### ngspice 47

- Use the console executable `ngspice_con.exe` for batch tests. The configured
  `ngspice.exe` has a sibling console executable; discovery prefers that
  console build and also supports either executable through `PATH`.
- Batch invocation: `ngspice_con.exe -b -o <log> <netlist>`. A temporary copy
  of each KiCad fixture passed with `.op`, or with `.ac` plus `.print`; exit
  code was 0 and the output was written to the requested log.
- A fixture with no analysis directive returns exit code 1 and logs that no
  simulations ran because there is no `.plot`, `.print`, or `.fourier`
  statement. The committed fixtures are unchanged.

### LTspice 26.1.1

- The local executable reports file/product version 26.1.1.0. Batch
  simulation is headless with `LTspice.exe -b <netlist>`. It returned 0 for an
  `.op` circuit and wrote `.log` and `.raw` beside the input netlist, even when
  the process working directory was elsewhere.
- Schematic export is headless with `LTspice.exe -netlist <file.asc>`. It
  returned 0 and wrote `<file>.net` beside the schematic.
- The exported smoke netlist had no BOM and contained only ASCII. The path
  comment in the candidate export was normalized to a relative filename; see
  [the candidate manifest](../tests/corpus/ltspice/m0_export_candidate/manifest.json).

### M1 encoding samples

- The repository-authored `encoding_cp1252.asc` uses actual CP1252 bytes for
  `µ` and `°`. The companion `encoding_utf8.asc` is UTF-8 so it can include
  `Ω` (not representable in CP1252). Both exports were produced with LTspice
  26.1.1.0 and are UTF-8 without a BOM.
- LTspice preserves `µ` and `°` from the CP1252 schematic in the UTF-8 `.net`.
  It reads UTF-8 non-ASCII input as Windows-1252 instead: the companion export
  contains mojibake (`Âµ`, `Î©`, `Â°`). The path comments were normalized to
  relative filenames; the original generated netlist bytes otherwise remain
  unchanged. See the [encoding-sample manifest](../tests/corpus/ltspice/encoding_samples/manifest.json).

### Host-specific test note

Windows Smart App Control can block unsigned native extensions (for example
`hypothesis\_native*.pyd`) with `ImportError: DLL load failed ... An Application
Control policy has blocked this file` (OS error 4551; see the CodeIntegrity
event log). Run tools through the signed Python interpreter, e.g.
`.venv\Scripts\python.exe -m pytest` or `uv run python -m pytest`, rather than
through the unsigned console-script shims (`pytest.exe`, `mypy.exe`). With that
invocation the full suite passes on this host with all plugins enabled; the
earlier `-p no:hypothesispytest` workaround is no longer needed.
