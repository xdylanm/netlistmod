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

The project's `uv` and dev tools are in `.venv` and may not be on `PATH`. In that case start from
the venv's interpreter (`.venv/bin/python` on Linux and macOS), and read each `uv run` below this way:

```powershell
.venv\Scripts\python.exe -m uv run --env-file .env python -m pytest
```

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
| T9 | Differential testing against spicelib: optional, dev-only, not done in phase 1 (§12). |

Outside the tiers, the suite also runs the usage guides' examples and checks spec coverage and relative Markdown links.

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

The ngspice structural parser is tested in
`tests/grammar/ngspice/test_structure.py`; exact-byte, item-span, and negative
position checks are in `tests/roundtrip/test_ngspice_structure.py`. Positive
and negative source fixtures are in
`tests/corpus/ngspice/structure_basic/` and
`tests/corpus/ngspice/structure_rejects/`, each with provenance and SHA-256
hashes in `manifest.json`. The negative manifest also records expected error
lines and columns.

Element lines (M3) are tested in `tests/grammar/ngspice/test_elements.py`,
`test_numbers.py` and the generator oracle `test_element_oracle.py`. The
`elements_basic` (accept) and `elements_rejects` (one malformed or unsupported
line per file; the manifest records line, column and error class) corpora are
checked in `tests/roundtrip/test_ngspice_elements.py`. The parser option `rkm`
defaults to `False`: tests of RKM values pass `rkm=True`, including the
`kicad_basic` fixtures, which use `1k0`. `tests/solver/test_ngspice_solver_elements.py`
records the ngspice 47 value probes. It saves device values (`.save @r1[resistance]`) and
reads them from the raw file, runs LT-mode probes with `run(..., lt=True)` (a temporary
`.spiceinit` with `set ngbehavior=lt`), and runs each accept fixture with the model and
subcircuit definitions of `solver_stubs/elements_harness.inc` included. `tests/test_usage_docs.py` runs the doctest
examples in `docs/usage/elements.md`.

Statements and directives (M4) are tested in
`tests/grammar/ngspice/test_statements.py` and by the second generator in
`test_element_oracle.py` (statements, typed directives and nested subcircuit
blocks with element bodies). The `statements_basic` (accept) and
`statements_rejects` (one malformed statement per file; the manifest records
line, column and error class) corpora are checked in
`tests/roundtrip/test_ngspice_statements.py`, which also checks byte-exact
round-trip, item and subcircuit-body tiling and every sub-span over all accept
corpora. `tests/solver/test_ngspice_solver_statements.py` records the ngspice 47
probes (each paired with what the library does) and runs every
`statements_basic` file; `tests/test_usage_docs.py` also runs the examples in
`docs/usage/statements.md`. Each construct has a YAML spec entry under
`docs/grammars/ngspice/specs/`. Add an entry with a unique `id`, a
`manual_ref` (one citation or a list, each of the form
`[ngspice-manual] §2.4.4 "End-of-line comments"`, whose key is listed in
[references.md](references.md)), validation status, `grammar` names, `tests`
selectors, and solver version/date when applicable. Add a `// spec: <ID>` marker before
the corresponding grammar rule or terminal group in a `.lark` file. The
architecture test checks that every grammar definition is marked and listed,
spec references resolve to marked definitions, non-disputed entries have
tests, and the human-readable device matrix matches its packaged JSON source.
PyYAML is a MIT-licensed development dependency used only by this checker.

## Solver tests

Solver tests are local-only. Mark a test with
`@pytest.mark.solver("ngspice")` or `@pytest.mark.solver("ltspice")` and request
the `solver` fixture. Discovery checks the corresponding environment variable,
then `PATH`, then standard install locations. The fixture skips with a reason
when its solver is absent. To make absence fail instead:

```powershell
uv run --env-file .env python -m pytest --require-solver ngspice -m solver
```

`--require-solver` may be repeated, once per solver.

The test helpers run in temporary directories, use batch mode, and set a
timeout. No simulator is launched from `src/`. Run only solver tests with
`uv run --env-file .env python -m pytest -m solver --no-cov` (the coverage gate is for the
full suite). The session header names each solver the tests found, with its version and
path:

```text
solver ngspice: 47 at C:\...\Spice64\bin\ngspice_con.exe
solver ltspice: 26.1.1.0 at C:\...\LTspice\LTspice.exe
```

### The ngspice harness (M7)

Every ngspice test goes through `tests/support/ngspice.py`
([decision 0008](decisions/0008-validation-status-and-solver-harnesses.md)):

- `run(solver, folder, source, *, harness=None, stubs=None, lt=False, cwd=None)` writes
  `source` (a `Netlist`, text, bytes or a path) to `folder/probe.cir`, runs
  `ngspice_con -b -r probe.raw -o ngspice.log probe.cir` and returns a `Run`:
  `returncode`, `log`, `raw_bytes`, `plots`, `ok` (exit code 0 and no log line with
  "error"), `plot(name)`, `voltage(node)` and `device(designator, parameter)`.
- `op`, `ac` and `tran_rows` run a netlist that must succeed and return its results
  (`{"v(out)": 1.5, …}`, complex values per frequency, one mapping per time point).
- A `Netlist` source is prepared with the edit API before it is saved: `with_stubs` points
  includes at stub files, `harness` (text) is written to `run_harness.inc` and included
  before `.end`, and `ensure_runs` adds an `.op` line when there is no analysis line.
- The raw-file reader (`read_raw`) is clean-room and reads ASCII raw files only. ngspice 47's
  `spinit` sets `filetype=ascii`; the helper also sets `SPICE_ASCIIRAWFILE=1`. A `.spiceinit`
  with `set filetype=binary` makes the reader fail loudly. Its unit tests
  (`tests/test_ngspice_raw_reader.py`) need no solver and use the samples in
  `tests/corpus/ngspice/solver_stubs/raw/`.

Read results from the raw file (15 significant digits), not from `.print` tables in the log
(7 digits): with `-r`, ngspice does not print device tables to the log.

### Running the corpus in ngspice

`tests/solver/test_ngspice_corpus.py` runs every accept fixture (a) and checks that an
unedited `load(...).save(...)` gives the same raw file except its `Date:` line (c). A
fixture's manifest entry may carry a `solver` field:

```json
"shiftscaleinvert.cir": {
  "sha256": "…",
  "solver": {"stubs": {"~/spice-models/opa/TL07X.cir": "tl072.lib"}}
}
```

- absent: the fixture runs as is (with an `.op` added when it has no analysis);
- `{"skip": "<reason>"}`: it cannot run in ngspice, for the reason given;
- `{"stubs": {"<include path as written>": "<stub file>"}}`: each `.include`/`.lib` line of
  that path is pointed at a copy of the stub;
- `{"harness": "<stub file>"}`: the stub is included before `.end`.

`tests/test_corpus_manifests.py::test_every_accept_fixture_runs_in_ngspice_or_has_a_reason`
checks that every accept fixture has a valid field. To add a stub:

1. Write a small stand-in in `tests/corpus/ngspice/solver_stubs/` with a header comment saying
   what it replaces. Use `.lib`, `.inc` or `.sub` (not `.cir`: accept families are globbed
   for `*.cir`). A stub is only included by ngspice, never parsed by the library, so it may
   use phase 2 elements. Give it a name different from the include it replaces.
2. Add its SHA-256 to `solver_stubs/manifest.json`.
3. Name it in the fixture's `solver` field and run the corpus test with
   `--require-solver ngspice`.

### Validation status and re-validation

Spec entries and the rule tables of `names.md` and `scoping.md` carry a status
(`validated`, `observed`, `disputed`, `documented`; decision 0008). The architecture test
`test_ngspice_statuses_are_backed_by_solver_evidence` requires a `validated_on` record and a
`tests/solver/` test for `validated` and `observed`, a `discrepancies.md` row for
`disputed`, and a `validation_note` for `documented`; the status table in
`docs/grammars/ngspice/README.md` must match the entries. New probes go in
`tests/solver/test_ngspice_validation.py` and assert what ngspice does and what the library
does.

To re-validate on a new ngspice version:

1. Install it, point `NGSPICE_EXE` at it and check the session header.
2. Run `uv run --env-file .env python -m pytest -m solver --no-cov --require-solver ngspice`.
3. For each failure, decide whether ngspice changed or the probe was wrong; a change in what
   ngspice accepts goes into `discrepancies.md` and may change a status (never weaken a test
   to make it pass, AGENTS.md).
4. When the suite passes, append a `validated_on` item (`solver`, `version`, `date`) to every
   entry the run covered (never replace one), update the `Validated on:` line of `names.md`
   and `scoping.md`, and update the status table in the ngspice README (the checker
   reports a stale row).

The ngspice solver suite (334 tests) runs in about 75 seconds on the maintainer's
machine (M7, ngspice 47); the corpus sweep is about a third of it.

### The LTspice harness (M8)

Every LTspice solver test goes through `tests/support/ltspice.py`
([decision 0009](decisions/0009-ltspice-dialect.md)). LTspice-backed tests run locally on Windows
with LTspice installed; nothing is needed offline, because the exports are committed.

- `run(solver, folder, source, *, harness=None, stubs=None, name="probe.cir")` writes `source` (a
  `Netlist`, text, bytes or a path) to `folder/probe.cir`, runs `LTspice.exe -b -ascii` and returns a
  `Run`: `returncode`, `log`, `raw_bytes`, `op_raw_bytes`, `plots`, `ok` (exit code 0 and no
  `file(line): message` line), `errors`, `comparable`, `plot(name)` and `voltage(node)`.
- `op`, `op_steps`, `ac` and `tran_rows` run a netlist that must succeed. `op_steps` gives one mapping
  per `.step` value; `tests.support.raw.sweeps` splits a stepped `.tran`, `.ac` or `.dc` plot.
- A `Netlist` source is prepared as for ngspice. `ensure_runs` adds an `.op` line unless there is an
  analysis, including the untyped `.noise` and `.tf`.
- The reader (`tests/support/raw.py`) is shared with ngspice. An AC analysis writes its bias point to
  `<name>.op.raw`, which the `Run` holds too. The first row of a `uic` transient holds zeros, so an
  initial value is in the second row.

**Never commit an LTspice raw file, log, or timing number** (decision 0009 item 2). The reader's unit
tests (`tests/test_ltspice_raw_reader.py`) use synthetic strings written in the test.

`tests/solver/test_ltspice_solver_corpus.py` runs every accept fixture and compares an unedited save, leaving
out `Title:` (the absolute path) and `Date:`. A manifest's `solver` field takes the ngspice forms and
`{"warning": "<text>"}`, the one message the run may write as a `file(line):` line.
`test_ltspice_validation.py` probes each `LT-*` entry, `test_ltspice_discrepancies.py` each row of
`discrepancies.md` and every `*_rejects` fixture, `test_ltspice_solver_document.py` the rule tables,
and `test_ltspice_edit_results.py` and `test_ltspice_edit_properties.py` the edits.

To re-validate on a new LTspice version, turn off Default Devices and Default Libraries and close the
GUI ([export guide](usage/ltspice-export.md)), then follow the ngspice steps above with
`--require-solver ltspice`, and re-export with `tests/test_ltspice_export.py`, which shows version
drift. Append `validated_on` items with `solver: ltspice`.

The LTspice solver suite (800 tests) runs for much longer than a normal test run, so it is worth
starting on its own (`-m solver -k ltspice`). If a local LTspice timeout appears, close the GUI and rerun once.

The document layer (M5) is tested in `tests/document/`: lines and insertion
points, resolution, topology (with Hypothesis properties of the signature and an
independent net oracle), diagnostics, and the `document_basic` corpus, whose
manifest lists the expected nets, connections, references and diagnostics. The
formula grammar is tested in `tests/grammar/ngspice/test_formula.py`. The ngspice
probes for names, net identity and scoping are in
`tests/solver/test_ngspice_solver_document.py`; one compares the library's nets
with the node list ngspice prints with `display` after `op` (manual §13.5.25).

The ngspice structural probes are in
`tests/solver/test_ngspice_solver_structure.py`. They record strict-policy
discrepancies, title handling, `//` lines, quoted/braced include-path behavior,
valid `.if (1)` syntax, and continuation behavior. The ngspice 47 probes were
run locally; details and paired parser-rejection tests are documented in
`docs/grammars/ngspice/discrepancies.md`. POSIX-only `SourceText.write()`
mode/symlink tests skip on Windows and were not run anywhere during this
rework. Ownership, hard-link relationships, and extended attributes are not
preserved when an atomic write replaces a file.

## Writing golden tests

Golden edit cases (T4 tier) live in `tests/corpus/ngspice/edits_golden/`
(`.gitattributes` keeps them byte-exact; pre-commit excludes `tests/corpus/`).
Each case in that family's `manifest.json` names an input fixture, a list of
steps and an expected fixture; `tests/edits/golden.py` documents the step format
and `tests/edits/test_edit_golden.py` compares the result byte for byte, with a
unified diff in the failure message. To add a case:

1. Add (or reuse) an input `.cir`; never edit an existing input in place.
2. Add the case to `cases` in the manifest, with `"expected": "<case>.expected.cir"`.
3. Produce the expected file by running the case (`tests.edits.golden.run_case`)
   and **review the diff against the input by hand**: only the intended slots
   or lines may change, with the line endings of their neighbours.
4. Record the SHA-256 of every new file under `fixtures`.

Preserve byte-level cases such as CRLF, mixed endings, missing final newlines,
BOMs, tabs, and trailing whitespace.

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
