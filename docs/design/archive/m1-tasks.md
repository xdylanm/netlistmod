# M1 task list — source layer

> **Status:** COMPLETE (2026-10-21)
> **Part of:** [phase-1-plan.md](./phase-1-plan.md) (milestone M1). Governed by [architecture.md](../../architecture.md) (§2 P1/P3, §5.1, §17). Follows the closing procedure in the plan (§4).

## 1. Scope

Deliver the bottom of the stack: `SourceText`, `Span`, the error hierarchy, the `Dialect` enum, decoding/encoding with a byte-exact round-trip guarantee, and the baseline T1/T3 tests. No grammar, no parsing, no editing.

**Exit (from the plan):** load/save of arbitrary text is byte-identical; the encoding policy is checked against LTspice-produced samples.

## 2. Current state

`src/netlistmod/{source,errors,dialects}.py` are docstring-only stubs. The layering contract (`pyproject.toml`) orders layers `edit > document > model > grammar > source > errors > dialects` (higher may import lower). M0 provides solver discovery, the corpus manifest check, and `uv run --env-file .env …`.

## 3. Decisions (confirmed by the maintainer)

1. **Bijective decoding.** The round-trip guarantee (P3) needs every byte sequence to decode to text that re-encodes to the same bytes. `cp1252` leaves five bytes undefined (0x81, 0x8D, 0x8F, 0x90, 0x9D). Decision: the default fallback list is `cp1252`, then `latin-1` (which maps every byte), so the fallback is total. The list stays configurable.
2. **Detection order** (architecture §5.1, refined): BOM (UTF-8, UTF-16 LE/BE) → strict UTF-8 → fallback list. A file whose BOM-declared encoding fails to decode is an `EncodingError` (no silent fallback). UTF-32 BOMs are rejected with `EncodingError` (unsupported). UTF-16 without a BOM is not detected unless the LTspice spike (T9) shows LTspice produces it.
3. **Line terminators.** The source layer treats `\n` and `\r\n` as line terminators. A lone `\r` is an ordinary character at this layer (never `str.splitlines()`, which also splits on `\x0b`, `\x0c`, `\u2028`, …). How the grammar treats a lone `\r` is decided in M2.
4. **`errors.py` is dependency-free.** It sits below `source` in the layering, so `ParseError` carries plain `line`, `column`, and a pre-rendered `excerpt` string rather than a `Span`. The source layer provides the excerpt helper; the grammar layer builds the error.
5. **New error class.** `EncodingError` (a `SpiceNetlistError`) is added to the §17 tree for decode/encode failures. §17 is descriptive, so no decision record is needed for the tree itself; the policy in items 1–3 is recorded in `docs/decisions/0001-source-text-policy.md` (T3).
6. **Dialect registry deferred.** M1 provides the `Dialect` enum with a display name only. The registry that maps a dialect to its grammar belongs with the loader in M2. There is no default dialect anywhere in the API (architecture §19, decision 17).

## 4. Tasks

Every task ends with `ruff check`, `ruff format --check`, `mypy --strict` and `pytest` green. Run through `uv run --env-file .env python -m …`.

### Design and decision record

**T1 — Decision record 0001: source-text policy.**
Write `docs/decisions/0001-source-text-policy.md` (from `TEMPLATE.md`) capturing decisions 1–3 above (bijective fallback, detection order and BOM rules, line-terminator definition), with rationale and consequences. Add a sentence to architecture §5.1 pointing to it, and add `EncodingError` to the §17 tree.
*Done when:* the record exists, the architecture links to it, and the record states the confirmed decisions.

### Core types

**T2 — `errors.py`.**
Implement the §17 hierarchy: `SpiceNetlistError` → `ParseError(line, column, excerpt)`, `UnsupportedConstruct`, `EditError`, `TopologyError`, `TopologyViolation`, plus `EncodingError`. Each message includes position/context where it has any. No imports from other `netlistmod` modules.
*Done when:* unit tests cover the hierarchy (`issubclass` relations), `ParseError` message formatting (line, column, excerpt with caret), and that `errors.py` imports nothing from the package.

**T3 — `dialects.py`.**
`Dialect` enum (`NGSPICE`, `LTSPICE`) with lowercase string values and a `display_name`; `Dialect.from_name(str)` (case-insensitive; `ValueError` listing valid names). No default value and no registry (decision 6).
*Done when:* unit tests cover parsing, error text, and that no public function in the package defaults the dialect (a small architecture-style test over signatures can be added in M2 when functions exist).

**T4 — `Span` in `source.py`.**
Frozen, ordered dataclass `Span(start, end)`: half-open, in characters, validates `0 <= start <= end`. Provide `length`, `is_empty` (insertion point), `overlaps(other)`, `contains(offset)`, and `hull(other)`. Overlap semantics follow architecture §7.5: two non-empty spans overlap iff they share at least one character; a zero-width span overlaps a non-empty span only if it lies strictly inside it; two zero-width spans never overlap (submission order is preserved by the edit plan later).
*Done when:* T1-tier tests cover every boundary case (adjacent spans, insertion at a boundary, insertion inside, equal spans, invalid construction), and a Hypothesis test checks `overlaps` is symmetric.

**T5 — `SourceText` decode and encode.**
Frozen dataclass `SourceText(text, encoding, bom)`:
- `SourceText.from_bytes(data, *, fallback_encodings=DEFAULT_FALLBACKS)` implements the detection order (decision 2). Encoding names are normalized (`utf-8`, `utf-16-le`, `utf-16-be`, `cp1252`, `latin-1`); `bom` records whether a BOM was present and stripped from `text`.
- `to_bytes()` re-encodes with the recorded encoding and BOM, raising `EncodingError` if the text is not representable (e.g. text inserted by an edit later).
- `with_text(new_text)` returns a new `SourceText` with the same encoding and BOM; the original is never mutated.
- The text is never newline-translated: decoding goes through bytes, never through text-mode I/O.
*Done when:* unit tests cover each encoding and BOM, the fallback order, the error cases (BOM-declared decode failure, UTF-32 BOM, empty fallback list exhausted), an empty file, a BOM-only file, and `to_bytes` rejecting unencodable text.

**T6 — `SourceText` file I/O.**
`SourceText.read(path)` reads bytes and calls `from_bytes`. `write(path)` encodes first (so a failure writes nothing), then writes to a temporary file in the same directory and replaces the target (`os.replace`), so an interrupted write cannot leave a truncated netlist. No text-mode I/O anywhere.
*Done when:* tests show an unencodable text leaves the existing file untouched, a successful write is byte-exact, and no temporary files remain afterwards.

**T7 — Line index and positions.**
`SourceText` exposes `line_count`, `line_span(line)` (1-based, including its terminator), `position(offset) -> (line, column)` (1-based; columns count characters, a tab counts as one), `offset(line, column)`, and `excerpt(offset)` (the source line plus a caret line for `ParseError`). Lines end at `\n` (with a preceding `\r` part of the terminator); a final line without a terminator is a line; an empty text has one empty line. Computed lazily and cached without mutating the public value.
*Done when:* tests cover CRLF, mixed endings, lone `\r` (not a terminator), no final newline, an empty text, a trailing newline (no phantom extra line), offsets at line boundaries and EOF, and out-of-range offsets (`ValueError`).

**T8 — Public exports.**
Export `Dialect`, `Span`, `SourceText` and the error classes from `netlistmod/__init__.py` with `__all__`. Add the version string (single source of truth: `pyproject.toml` via `importlib.metadata`).
*Done when:* `tests/test_package.py` asserts the exports, and `mypy --strict` passes on a consumer snippet.

### Encoding validation against LTspice

**T9 — LTspice encoding spike.**
Using only circuits authored in this repository: create a schematic whose component values, comments and text contain `µ` (U+00B5), and also `Ω` and `°` to probe characters outside cp1252. The `.asc` must be written as cp1252 bytes by a program, not by hand-editing UTF-8 (the `create` tool writes UTF-8). Export with `LTspice.exe -netlist`, then record: the encoding of the exported `.net` (BOM? UTF-8? cp1252? UTF-16?), how `µ`, `Ω` and `°` appear, and the `.asc` encoding. Optionally run the netlist through LTspice batch (`-b`) and through ngspice batch to see whether each accepts `µ` as a scale factor. Commit the schematic and export as a corpus family `tests/corpus/ltspice/encoding_samples/` with a manifest (normalize machine-specific path comments as in M0). Update `docs/usage/ltspice-export.md`.
*Done when:* findings are recorded with the LTspice version. If LTspice emits UTF-16 without a BOM or another unexpected encoding, stop and raise a decision instead of extending the detector silently.

### Round-trip tests (T3 tier)

**T10 — Byte-exact round-trip suite.**
In `tests/roundtrip/`: parametrized byte cases defined inline (not committed as files, so editors and Git cannot alter them): LF, CRLF, mixed endings, lone `\r`, no final newline, only newlines, empty file, tabs, trailing whitespace, blank lines, long lines, UTF-8 with and without BOM, UTF-16 LE/BE with BOM, cp1252 with `µ`, bytes undefined in cp1252 (the latin-1 fallback), and NUL bytes. Each case asserts `SourceText.from_bytes(data).to_bytes() == data` and that `write`/`read` through the filesystem is also identical.
*Done when:* all cases pass and the failures a naive `open(..., "r")` would cause (newline translation, BOM stripping) are demonstrated by at least one test comment or assertion.

**T11 — Corpus-wide round trip and Hypothesis property.**
A test that loads and saves every file under `tests/corpus/` (including the new LTspice samples and the M0 files) and asserts byte equality. A Hypothesis property test: for arbitrary text encoded in each supported encoding (with and without BOM where valid), `from_bytes(encoded).to_bytes() == encoded`; and for arbitrary byte strings that are not valid UTF-8, the default fallbacks round-trip.
*Done when:* both tests pass on this machine and run in the normal `pytest` invocation.

### Gates and closing

**T12 — Architecture contracts.**
Confirm the T7-tier tests still pass (no `subprocess`/`os.system` in `src/`, layering, no GPL dependency). If `errors` must stay below `source` (decision 4), add a layering note to the contract or the test explaining it. Add a test that `netlistmod.errors` imports no other package module.
*Done when:* the existing contracts and the new test pass.

**T13 — Coverage gate.**
The source layer is now real code, so enable the 90% line-coverage target (architecture §19, decision 11) as a failing threshold (`fail_under = 90` in the coverage config), and remove the "informational" wording in `docs/testing.md`.
*Done when:* `pytest` fails below 90% and the source layer is fully covered.

**T14 — Docs.**
Update `docs/testing.md` (new test locations, how the in-code byte cases work, the LTspice encoding findings), `CHANGELOG.md` (Unreleased: source layer, error hierarchy, dialect enum), and the README status line. Add docstrings to every public name. Add `docs/design/source-layer.md` only if the design needs more than the decision record and docstrings.
*Done when:* docs are consistent with the code and links resolve.

**T15 — M1 exit check and archive.**
Run the full check set (`ruff check`, `ruff format --check`, `mypy --strict`, `pytest` with the coverage gate, `pre-commit run --all-files`, the solver tests). Verify a fresh clone passes the corpus hash tests. Then close the milestone per the plan: set this document's status to `COMPLETE (date)`, `git mv` it to `docs/design/archive/`, fix its links, link it from the M1 heading in the plan, and update the index in the design README.
*Done when:* all checks are green and the archive step is done.

## 5. Dependencies between tasks

```
T1 → T2 → T4 → T5 → T6
T1 → T3
T5 → T7 → T8
T9 (independent; needs only M0) → T10, T11
T5, T6 → T10 → T11
T2, T3, T7, T8 → T12 → T13 → T14 → T15
```

## 6. Out of scope for M1

Grammar, parsing, tokens, typed nodes, `Document`, edit plans and verification, the dialect registry, and any decision on how the grammar treats a lone `\r` or continuation lines (M2).
