# M11 task list — Carried limits and messages

> **Status:** READY FOR REVIEW — T1–T10 are done, with the results in section 5; T11 follows the maintainer's approval
> **Part of:** [phase-2-plan.md](./phase-2-plan.md) (milestone M11). Governed by [architecture.md](../architecture.md) (§2, §7, §15, §17).

## 1. Scope

M11 settles the two limits where the library accepts input and the result can be wrong, clears the carried message work, and settles LTspice `.end`, so that M12 starts from a clean base.

- **In:** `.lib` blocks (limit 6); settling `directives.add` over a singleton (limit 9); H5–H8 from [phase-2-code-changes.md](./archive/phase-2/phase-2-code-changes.md); recording that LTspice `.end` stays required (limit 2); a decision record for these.
- **Not in M11:** new element letters, stimulus specs or edit operations. Opening a library file, or editing inside a `.lib` block, which is a later candidate (decision 1). Refusing combinations of *different* analyses: LTspice stops on `.tran` with `.ac`, but ngspice runs them, and the library does not validate solver inputs.

**Exit:** both limits are closed with tests, and `phase-2-code-changes.md` is archived.

## 2. Decisions (maintainer, 2026-11-03)

Decision 2 reverses the plan's item. "Alternative" marks an option considered and not chosen.

1. **`.lib` blocks are opaque, on both dialects, and the library does not ask whether a solver would run them.** Both solvers refuse a block in a netlist (section 3), but the library does not validate whether a netlist can run. It only has to read the file correctly, so the block's body is not topology.
   - `.lib name` … `.endl` is an `OpaqueBlock`: preserved exactly, not read, added, replaced or removed whole, and never edited inside. `.lib name` with no `.endl` stays an `OpaqueStatement`, because that is LTspice's file form.
   - A block counts like an `.include` for unresolved names, as `.if` does under decision 4.
   - The cost is one more multi-line lookahead terminal, which strict mode cannot check (limit 3), and which the existing test pins.
   - *Alternative:* refuse the block at load. That would be validating solver behaviour, and it would close off the route to library files.
   - **Later candidate, not in v1: library files.** Whether a file is a netlist or a library cannot be told from the file: the extension is not binding, a section file can have an `.end`, and blocks look the same in both. The caller would say which it is, as with a dialect (P7). This needs an explicit way to open a library file, with no title or `.end`, and typed section contents, so that `set_model_param` can reach a model in a section. Opaque blocks leave this open. Decide after using the beta.
2. **`directives.add` stays literal.** It adds the line it is given, even over an existing `.ac` or `.tran`, because two lines can be meant: ngspice runs both and gives a plot for each. `directives.set` remains the upsert. LTspice stops on a second analysis, which is loud at the solver, and the library does not validate solver inputs. Limit 9 closes as documented behaviour, and the plan's refusal is dropped. *Considered and not chosen:* refusing it on both dialects or on LTspice only, or a `repeat=True` argument.
3. **H6: rename the code to `UNTYPED_DIRECTIVE_PRESERVED`.** The message already says "not typed"; only the code says "unknown". It is wrong on both dialects: ngspice `.print` and every LTspice command that gets it are documented commands. One accurate code needs no list of commands in Python. Callers filtering on the old name must change, which is allowed before 1.0 (§18) and goes in the CHANGELOG. `UnknownDirective` keeps its name. *Alternatives:* a second code for LTspice only, which leaves `.print` "unknown"; or keep the code and only document it.
4. **H8: treat an `.if` block like an `.include`, for diagnostics and for `set_model`.** An `UNRESOLVED_*` diagnostic becomes info and says the name may be in the block, and `set_model` accepts such a name with `allow_external=True`. Both share one reason: the name may be defined where the library does not read. *Alternative:* diagnostics only, which would warn less but still refuse the edit.
5. **One decision record, 0012.** It covers limits 2, 6 and 9 and H6 and H8, as 0010 did for phase 1. *Alternative:* the plan's separate records, which would be five short files for one milestone.

H5 and H7 needed no decision. H5 raises `TypeError` in both cases, which `phase-2-code-changes.md` offers as the first choice.

## 3. Starting point (2026-11-03, `f1e5531`)

Probes on ngspice 47 and LTspice 26.1.1, run from a scratch script.

**`.lib x` … `.endl`:**

| Where | ngspice 47 | LTspice 26.1.1 | Library today |
|---|---|---|---|
| In the netlist, with or without a call to it | Stops: "unimplemented dot command" on the header | Stops: looks for a file `x`, then `.endl` is "only allowed in library files" | ngspice: **parses, and the body counts as topology.** LTspice: `ParseError` on `.endl` |
| In a separate file, called with `.lib "file" x` | Runs; section elements are added | Runs; models are imported and elements are ignored | Never read (§7.8) |
| A stray `.endl` | Stops | Stops | ngspice: `UnknownDirective`. LTspice: `ParseError` |
| `.lib file`, one field, file exists | Stops | Runs | Opaque statement |

The manual agrees: blocks are "inside the *.lib file" (`[ngspice-manual] §2.10 ".LIB"`). So does LTspice, whose error says `.endl` is only allowed in library files. Limit 6 is therefore a defect only on ngspice, and only for a netlist that the solver refuses anyway. The corpus has only the two-field form `.lib file section`, so no corpus file changes.

**Two lines of one kind:**

| Lines | ngspice 47 | LTspice 26.1.1 |
|---|---|---|
| `.tran`, `.ac` or `.dc` twice | Runs both, two plots | Stops: "More than one analysis specified" |
| `.op` twice | Runs both, two plots | Runs, one plot |
| `.temp` twice | Runs; the last wins | Stops: "Temperature already set elsewhere" |
| `.step` of one quantity twice | No such command | Stops |
| `.step` of two quantities | No such command | Runs, nested |

**Other starting facts:**
- The comment on `SINGLETON_DIRECTIVES` at `edit/operations.py:81` says a second line is never what is meant. For ngspice `.ac` and `.dc` that overstates it; fix the comment.
- `tests/edits/test_edit_negative.py:222` already relies on `add` writing a second line, then `set` refusing the ambiguity, so it stays as it is.
- LTspice's closed list means an unknown name is already a `ParseError`, so `UNTYPED_DIRECTIVE_PRESERVED` is never about a misspelling there. In ngspice a misspelt `.tarn` still lands on it.
- `.if` and `.control` are refused on LTspice, so H8 only affects ngspice.
- CI is green on `main`. Dependabot read its configuration: both first runs succeeded, which confirms the `uv` setting left open by M10, and it opened [PR 6](https://github.com/xdylanm/netlistmod/pull/6).

## 4. Tasks

[x] **T1 — Decision record 0012: carried limits.** Status `proposed` until M11 closes. It records the choices of section 2 and:
- LTspice `.end` stays required (limit 2), closing what decision 0009 item 4 left open. Edit placement and the round-trip tests depend on it.
- The one exception to the plan's compatibility rule: an ngspice netlist with a block keeps parsing, but its signature changes, because the body leaves the topology. No solver ran such a netlist, and no corpus file has one.
- On LTspice, such a netlist goes from `ParseError` to loading.
- Library files as a later candidate (decision 1), added to the deferred items in §21.
- Amendments to decision 0002, to architecture §7.2, §7.8, §17 and §19 decision 10 as needed, and to plan M11's `directives.add` bullet.
- `directives.add` stays literal (decision 2), closing limit 9.

[x] **T2 — Pin the compatibility rule.** Before any grammar change, add a test holding the topology signature and digest of every corpus file that parses, so that saved digests stay valid. First check whether `tests/document/test_document_corpus.py` already does this. Later milestones keep the test.

[x] **T3 — Opaque `.lib` blocks (limit 6, decision 1).** Tests first:
- **Grammar, both dialects:** a block rule like `.if`'s, wherever `.lib` is allowed today. A `.lib` line opens a block only when it has one field and an `.endl` line follows before the next one-field `.lib` line or `.end`. A two-field `.lib` line may stand in the body, because vendor libraries select one section from inside another. This needs a lookahead terminal; add it to the pinned list and to the spec entries.
- **What stays as it is:**
  - `.lib file section`, and one-field `.lib name` with no `.endl`, stay `OpaqueStatement`.
  - A stray `.endl` stays `UnknownDirective` on ngspice and `ParseError` on LTspice.
  - Blocks do not nest: in `.lib x`, `.lib y`, `.endl`, `.endl`, `.lib x` is a statement, `.lib y` … `.endl` is the block, and the last `.endl` is stray. Pin this with a test.
- **Model:** `OpaqueBlock.kind` gains `"lib"`. Nothing in the body reaches `nets()`, elements, symbol tables or the signature; this is the test that closes limit 6, with a net that only the body uses. `verify.py` already treats an `OpaqueBlock` as a black box; check that this holds.
- **Edits:** `directives.add`, `replace` and `remove` handle a whole block on both dialects, with golden diffs, and an edit elsewhere leaves the block byte-identical. An edit that names an element in the body finds nothing.
- **Corpus:** a positive file on each dialect with a manifest and byte-exact round trip, marked as not run by the solver sweep. Regenerate `tree_snapshot.json` only if it changes, and explain any change.
- **Solver tests, as evidence for the record:** both solvers stop on a block in a netlist. A section in a separate file runs, where ngspice adds its elements, and LTspice imports its models and ignores its elements.
- **Docs:** `NG-OPA-002`, `LT-OPA-001`, `scoping.md` on both dialects, `edit-layer.md` (which says LTspice refuses blocks) and `docs/usage/`.

[x] **T4 — `directives.add` stays literal (limit 9, decision 2).** No change to what it writes.
- Tests that pin it on both dialects: `add` over each of the five kinds writes a second line, `set` on the result refuses the ambiguity, and `replace` and `remove` work on it.
- Solver tests for the table in section 3: ngspice gives two plots for two `.ac`, and LTspice stops.
- State the difference between `add` and `set` in `edit-layer.md`, `docs/usage/editing.md` and the docstrings, including that LTspice stops on a second analysis.
- Correct the comment on `SINGLETON_DIRECTIVES`.

[x] **T5 — H5, argument types.** `Index.scope` raises `TypeError` for a `str`, so `scope="ab"` can no longer address nested definitions `a` and `b`. `parse` raises a `TypeError` naming `SourceText`. A test for each, and a positive test that a tuple and a list still work as a scope.

[x] **T6 — H6, the code rename (decision 3).** Rename the `DiagnosticCode` member and value, then update §17, `docs/usage/errors.md`, the manifests and the tests. No behaviour changes: every line that had the old code has the new one.

[x] **T7 — H7, internal references in messages.**
- Remove `decision NNNN` and `architecture §` from every message a user can see. Where the sentence needs the rule, state the rule.
- A manual citation names its document, as in "(ngspice manual §2.5)", so that `§` is never ambiguous.
- Docstrings and comments keep their citations.
- Add a test in `tests/architecture/` that walks the `raise` and diagnostic message strings under `src/` and fails on an internal citation, so that later milestones' messages start clean and stay clean.
- Line and column in the `*_rejects` manifests do not move. Update any message assertion that quoted a citation.

[x] **T8 — H8, models in `.if` blocks (decision 4).**
- A scope with an opaque `.if` or `.lib` block counts the same as one with an `.include`. Rename `has_opaque_include` to say so.
- Update the call sites and their messages. The third site, the LTspice instance-node check in `document/diagnostics.py`, follows too: a `.lib` block may define the instance's subcircuit.
- Tests for a model, a subcircuit and a parameter defined only in `.if` or in a `.lib` block, at the top level and in a subcircuit body, including `set_model` with and without `allow_external`. A `.control` block does not count.
- A solver test that ngspice resolves a model defined in `.if (1)`.
- Update `docs/grammars/ngspice/scoping.md`, `docs/usage/errors.md` and §7.8.

[x] **T9 — Documentation and archive.**
- CHANGELOG lines for T3 and T5–T8, marking the behaviour changes and the rename.
- Update the device and limits text that names limits 2, 6 and 9, and the LTspice `.end` wording in the LTspice grammar docs.
- `git mv` `phase-2-code-changes.md` to `archive/phase-2/`, marked `COMPLETE`. Fix links, including in the phase 2 plan and index.

[x] **T10 — Final evidence and handover.** Open the pull request. Run the full local check set with `--require-solver ngspice --require-solver ltspice` on Windows, and record it and the green CI run in section 5. Set the status to `READY FOR REVIEW`, and update the plan's M11 heading and the index.

### After the maintainer's approval

[ ] **T11 — Close M11.** Merge on green with "Rebase and merge". Status `COMPLETE (date)`, `git mv` to `docs/design/archive/phase-2/`, fix links, update the plan and index, and accept decision 0012.

## 5. Results

**Full local run on `26fc680` (T10, Windows, Python 3.14.3, ngspice 47, LTspice 26.1.1.0):** 4993 passed, 2 skipped, 455 deselected, 9 minutes 55 seconds, coverage 98.93%, with `--require-solver ngspice --require-solver ltspice`. `ruff check`, `ruff format --check`, `mypy` (26 files), the named `mypy --strict` (30 files), the import contract (1 kept, 0 broken) and `pre-commit run --all-files` are all clean.

**CI on `26fc680` ([PR 7](https://github.com/xdylanm/netlistmod/pull/7), run 41778186149): all five jobs green,** with no solver found.

| Job | Python | Passed | Skipped | Deselected | Coverage |
|---|---|---:|---:|---:|---:|
| Ubuntu | 3.13.18 | 3833 | 1162 | 455 | 98.93% |
| Ubuntu | 3.14.10 | 3833 | 1162 | 455 | 98.93% |
| Windows | 3.13.17 | 3832 | 1163 | 455 | 98.93% |
| Windows | 3.14.10 | 3832 | 1163 | 455 | 98.93% |

The commit that records these results adds one test and changes docs; its run is on the pull request.

**Compatibility rule (T2).** All 153 recorded corpus digests are unchanged. The tree snapshot gained only the two new files, `structure_basic/lib_block.cir` and `edits_golden/add_lib_block.expected.cir`.

**Changes to tests that existed:**
- `test_review_package_holds_the_generated_spec_coverage` is removed. T3 changed two spec entries, so the archived phase 1 record no longer matches the generated report, which is the end its comment names. Plan M12 no longer lists it.
- The error names in `_expected_names` leave out `LIB_BLOCK_KW`, so no rejected file's `expected` list changed.
- `docs/usage/editing.md` examples lost their internal citations, as T7 requires.

**Found while doing T3, not changed:** a `+` line in an `.if` or `.control` body is a `ParseError` on ngspice, because the ignored continuation leaves two text tokens on one logical line. `.lib` blocks accept these lines, since vendor libraries are full of them. Accepting them in `.if` would be a small grammar change of its own.

**A limit of the block rule:** a one-field `.lib name` in a subcircuit body with a stray `.endl` after `.ends` opens a block that swallows `.ends`, so the file fails at load. The lookahead cannot stop at `.ends`, because a section may hold a whole `.subckt`.

**Not done:** no solver has been run on Linux, as in M10.
