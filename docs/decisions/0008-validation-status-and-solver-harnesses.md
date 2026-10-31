# 0008 — Validation status and solver harnesses

- **Status:** proposed (M7; the section 2 decisions of [m7-tasks.md](../design/m7-tasks.md)
  were accepted by the maintainer on 2026-10-31; this record awaits the M7 review)
- **Date:** 2026-10-31
- **Context:** M7 turns the solver checks that M2–M6 added one milestone at a time into a
  checked validation layer (architecture §10.3 (a)–(d), §11). Architecture §11.2 lists the four
  status words of a spec entry but not their meaning; §10.3 asks for solver acceptance, edited
  results, unedited round trips and validated behaviors without saying how fixtures that need
  files kept outside the repository are run, or how a status is tied to evidence. The maintainer
  accepted the recommendations of [m7-tasks.md](../design/m7-tasks.md) section 2 on 2026-10-31;
  this record states them and the points settled while implementing (T1–T8). Probe evidence:
  m7-tasks.md section 7 and `tests/solver/`.
- **Decision:**
  1. **Status meanings** (§11.2).
     - `validated`: the manual describes the construct, and ngspice reads every form the
       library **accepts** the way the library models it. Forms the library rejects but ngspice
       tolerates do not change the status; they are rows in `discrepancies.md`.
     - `observed`: the manual is silent, and the library's behavior rests on what ngspice does
       (§11.3 rule 3).
     - `disputed`: ngspice reads a form the library accepts differently from the library's
       model, and the library does not flag it.
     - `documented`: no solver evidence. Allowed only with a `validation_note:` saying why the
       solver cannot decide.
  2. **Checked status** (`tests/architecture/test_spec_coverage.py`). `validated` and `observed`
     need a non-empty `validated_on` (each item has `solver`, `version` and `date`) and a
     `tests/solver/` test in `tests`; `disputed` needs a `discrepancies.md` row naming the id;
     `documented` needs `validation_note`. The same rules apply to the rule tables of
     `names.md` and `scoping.md` (a `validation_note:` in the tests cell for `documented`); each
     of those documents has one `Validated on: ngspice 47 (date)` line, and the status column
     takes the four words only.
  3. **Running every fixture.** A corpus manifest's fixture entry may carry a `solver` field:
     absent means "runs as is"; `{"skip": "<reason>"}`; or any of `{"stubs": {"<include path>":
     "<stub file>"}}` and `{"harness": "<stub file>"}`. A test checks that every accept fixture
     runs or has a reason. Stubs live in the new family `tests/corpus/ngspice/solver_stubs/`
     (author `xdylanm`, MIT); they are included by ngspice and never parsed by the library, so
     they may use phase 2 elements. The test support points each include at its stub with the
     edit API: a `.lib` line with `directives.replace`, an `.include` line with
     `directives.remove` and `add_include` in one batch (the API adds includes only through
     `add_include`, decision 0007 amendment 1). For (c), each runnable fixture is run as loaded
     and after `load(...).save(...)`; the raw files must be identical except their `Date:`
     line.
  4. **Edit results** ((b)): one solver test per M6 operation family against a closed form;
     linear DC and AC results to `1e-6` relative from the raw file, diode, coupling and
     transient results to `1e-3`. Each test also asserts the unedited result.
  5. **Solver-backed property test:** Hypothesis sequences of `set_value`/`params.set` edits on
     a three-resistor ladder, applied one by one or as one batch, compared with the computed
     `v(out)` (`max_examples=20`, `deadline=None`, `derandomize=True`).
  6. **Shared test support** `tests/support/ngspice.py`: `run` (netlist, text, bytes or path;
     stubs, harness, LT mode) returning a `Run` with the exit code, the log and the raw file;
     a clean-room ASCII raw-file reader; `op`, `ac`, `tran_rows`; `ensure_runs`; `with_stubs`.
     `solvers.py` keeps discovery and `run_ngspice` (P9: `src/` is untouched).
  7. **Versions:** a `pytest_report_header` prints each discovered solver's version and path;
     `validated_on` items are appended when an entry is re-validated, never replaced; no
     committed observation files.
  8. **New discrepancies** are recorded and the grammar is unchanged (P5): a stray `.endc`;
     node names with `[ ]` (and, found in M7, `%`, `<`, `~`, `(`); `params:` on an X line.
  9. **CI** stays deferred; M7 is local-only (§10.3).

  Settled while implementing:

  10. **Every run writes a raw file** (`-r`). ngspice 47 then runs a file's analysis lines
      without `.print`. `ensure_runs` adds an **`.op` line** (`directives.add`) to a file with
      no analysis, not the `.control`/`op`/`.endc` block m7-tasks.md suggested: with `-r`, an
      `op` command in a control block writes nothing to the raw file (probed; no raw file at
      all), while an `.op` line does, also when a control block is present.
  11. **ASCII raw files.** ngspice 47's `spinit` sets `filetype=ascii`, which wins over the
      environment variable `SPICE_ASCIIRAWFILE`; only a `.spiceinit` with `set
      filetype=binary` gives a binary file (probed on the installed binary and its `spinit`).
      The helper sets `SPICE_ASCIIRAWFILE=1` anyway, for builds without that `spinit` line, and
      the reader fails loudly on `Binary:`. Raw files have CRLF line endings either way.
  12. **Device values from the raw file.** With `-r` ngspice 47 prints no device tables in the
      log, so the M3 value probes save `@r1[resistance]` (`@c1[capacitance]`) and read it from
      the operating point (ngspice names some of these vectors `v(@r1[resistance])`).
  13. **The `harness` manifest form** (an addition to item 3): the `elements_basic` fixtures
      refer to models and subcircuits they do not define; the definitions the M3 test inserted
      before `.end` are now the stub `elements_harness.inc`, included before `.end`.
- **Consequences:**
  - The architecture is amended: §11.2 gives the status meanings and `validation_note`;
    §10.3 describes the manifest `solver` field, stubs, the raw-file comparison for (c) and the
    report header; §10.5 lists the stub family.
  - Every spec entry now has solver evidence: `NG-DIR-001`, `NG-NOD-001`, `NG-PAR-001`,
    `NG-UNS-001` and `NG-VAL-001` moved from `documented` to `validated`; `NG-STR-001` got its
    `validated_on`; S9 of `scoping.md` moved to `validated` and S5's status word is now
    `validated` (its discrepancy row stays).
  - `structure_basic.cir` cannot run in ngspice 47 with any stub: it has `.if {enabled}`, and
    it includes one `models.lib` both whole and as a library section. It is skipped with that
    reason; an equivalent sample runs in `test_structure_sample_runs_with_a_valid_condition`.
  - The library accepts `.if {expr}` (opaque block, condition not checked), which ngspice 47
    stops at. M7 raised it as a candidate `disputed` for `NG-OPA-001`; the maintainer kept the
    entry `validated` (2026-10-31). It is recorded in `discrepancies.md`; the grammar is
    unchanged.
  - The solver suite grows from 168 to 334 tests (about 75 s locally); its runtime is recorded in
    `docs/testing.md`.
