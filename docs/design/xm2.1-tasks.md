# X-M2.1 task list — discrepancy categories and X-M2's loose ends

> **Status:** ACTIVE — implementation
> **Follows:** [X-M2](./archive/xyce/xm2-tasks.md) (merged as #30) and its review R1. Plan: [xyce-plan.md](./xyce-plan.md) section 8. Governed by [architecture.md](../architecture.md) (§2, §10, §11) and decisions [0026](../decisions/0026-the-xyce-dialect.md), [0027](../decisions/0027-xyce-structure-names-and-values.md) and [0028](../decisions/0028-xyce-directives.md).

## 1. Scope

A short milestone between X-M2 and X-M3. It states, as a decision, how the library settles a difference between the Xyce manual and the Xyce binary; gives every row of `docs/grammars/xyce/discrepancies.md` a category under that rule, with a test that keeps the table consistent; and closes what X-M2's review R1 left open. The dialect stays hidden (decision 0026 item 4).

- **In:**
  - **The rule** (a decision record, section 2 below) and a **Category** column in `discrepancies.md`, every row classified, with a test.
  - **`.PRINT`** typed shallowly (R1 gap 3).
  - **Read-only accessors** for the scope's internal tables (R1 nit N6).
- **Not in X-M2.1:** the `.AC`, `.DC` and `.STEP` point counts stay unchecked (decided below); X-M3's sources and the P port; a public `Dialect.XYCE` (X-M8).

R1's other findings (the two blockers, the should-fix items, gaps 1 and 2 and the other nits) were fixed in X-M2 itself (the R1 commit of #30).

## 2. Decisions (maintainer, 2026-11-21)

1. **The manual is the reference; the solver's behaviour is observed.** A netlist generator should be explicit and precise, and should be able to require the grammar as documented, even where the solver is more lenient (it may accept other dialects' conventions or a person's shorthand). Each difference between the manual and the binary falls into one of these categories, and the category says which side the library follows:
   - **`manual`** — the manual is correct and precise, and the solver is lenient or has a bug. The library follows the manual: it refuses what the manual does not allow, and reads what the manual allows even where Xyce 7.10 stops on it (a solver bug, judged by the maintainer: the `.TRAN` schedule after tstart, the full `.TRAN` form, a zero-argument `.FUNC`).
   - **`imprecise`** — the manual is imprecise or incomplete, and the solver's behaviour fills the gap; the reading is `observed` (§11.3 rule 3). The library may be stricter than the solver where that removes an ambiguity (a blank inside a bare `.param` value).
   - **`manual-error`** — the manual is wrong (it documents a form the solver refuses or reads otherwise). The library follows the solver.
   - **`library-limit`** — not a manual-versus-solver question: the library's model cannot express or check the form (a bare `AC`, which the 1.0 `AcSpec` cannot hold; instance-parameter lists that are the union of the model levels; fields kept as untyped text).

   The category is a judgement where neither source is authoritative; the maintainer makes it, and the row records it.
2. **Consistency.** A row on which the library accepts a form that Xyce stops on is `manual` or `library-limit`. A row on which the library refuses a form that both the manual and Xyce accept is `library-limit`. A test keeps this true.
3. **A zero-argument `.FUNC`** stays read: the manual allows it, and Xyce 7.10 stopping on its call is taken as a solver bug (`manual`).
4. **Point counts stay unchecked:** `.AC DEC 1.5 1 10` and the `DEC`/`OCT` counts of `.DC` and `.STEP` are read as written, though Xyce stops on a count that is not an integer (`library-limit`).
5. **`.PRINT` is typed shallowly,** as `.MEAS` is: the print type from the manual's closed list, the rest kept as text. A warning when the type disagrees with the first analysis line (Xyce stops) or with the analysis that runs (Xyce prints nothing).

## 3. Tasks

- [x] **C1 — Decision record** for section 2, amending decision 0026 item 5 and decision 0027 item 12; `discrepancies.md`'s preamble states the rule.
- [x] **C2 — The Category column:** every row of `discrepancies.md` classified; the rows where the library accepts a form Xyce stops on gathered in one section; a test of decision 2. Any row whose category is a judgement not already made is listed for the maintainer.
- [x] **C3 — `.PRINT`:** the grammar, an internal node, the warning, spec entry, grammar, document and solver tests, the X-M8 checklist.
- [x] **C4 — Scope accessors** (R1 N6): read-only internal accessors in place of the cross-module reads of `Scope._data`, `Scope._functions` and `Scope._replace_ground`.
- [ ] **R1 — review;** the full run with ngspice, LTspice and Xyce; the pull request.

## 4. Log

- 2026-11-21: task list written, with the maintainer's decisions; X-M2 archived (approved and merged as #30).
- 2026-11-21: C1 done: [decision 0029](../decisions/0029-xyce-discrepancy-categories.md) records section 2 (the rule, the four categories, the consistency rule, decisions 3 to 5), amending decision 0026 item 5 and decision 0027 item 12; `discrepancies.md`'s preamble states the rule and the categories.
- 2026-11-21: C2 done: `discrepancies.md` has a Category column in every table and five sections by what the library does beside Xyce (Xyce runs and the library refuses; the manual and Xyce accept and the library refuses; the library reads and Xyce stops on or ignores; the library follows Xyce against the manual; the manual silent or imprecise), each with its allowed categories; `tests/architecture/test_xyce_discrepancies.py` checks the categories per section (decision 0029 item 2), the library side of each section, the columns and that every cited test exists. The `//` and `$` rows are one row; the point-count row covers `.DC` and `.STEP` (decision 0029 item 4, probed: "Points parameter on .DC or .STEP line must be an integer"), with a grammar test; a row for scoping.md S4 (`.FUNC` order). Judgement calls for the maintainer: `PARAMS:` reserved defaults, directives in a body and an R without a value (`imprecise`); a numeric `Q=` and `.PCE` (`manual`); two `.OPTIONS OUTPUT` lines, `[s]`, a `.SUBCKT` without ports and the merged `//`/`$` row (`manual-error`); the `-r` and hang rows (`imprecise`, by their section).
- 2026-11-21: C3 done: `.PRINT` is `PrintDirective` (internal; `TopLevelItem` grows by it) with a required print type of the manual's list (AC, AC_IC, DC, ES, HB, HB_FD, HB_IC, HB_STARTUP, HB_TD, NOISE, PCE, TRAN of §2.1.31's table, HOMOTOPY, SENS and TRANADJOINT of §2.1.31.6 and §2.1.31.7; any case), then at least one field kept as text, continuable, top level only; `TR` (hint "write `TRAN`"), another word, no type and no field are a `ParseError`. `PRINT_TYPE_MISMATCH` (warning; `_PRINT_RULES`, `None` on ngspice and LTspice) reports a type that does not agree with the first analysis line other than `.OP` (Xyce stops), and an analysis's type whose analysis does not run (Xyce writes nothing), `.HB` taking part, all from probes (`tests/solver/test_xyce_print_probes.py`, every type under every analysis). Spec entry `XY-PRT-001` (`observed`: which analyses a type agrees with rests on the binary); `XY-DIR-001` loses `.PRINT`; discrepancy rows for `TR` and a `.PRINT` without an output variable (`manual`), the first-line check (`manual`, the manual says such a line is not processed), the unchecked body (`library-limit`) and a bare `.PRINT`, which crashed and hung Xyce (with the hang row, never run); two rejection fixtures; edit golden test `print-removed`; the plan's section 8.2 checklist. ngspice and LTspice unchanged.
- 2026-11-21: C4 done: `document/index.py` has the read-only module functions `scope_functions`, `scope_data` and `scope_replaces_ground`, which `document/diagnostics.py`, `edit/_ops_statements.py`, the index's own helpers and the tests now use in place of `Scope._functions`, `Scope._data` and `Scope._replace_ground`. Module functions, as `step_quantity` is, rather than properties: `Scope` is a public class, so neither public properties (a public-API addition before X-M8) nor underscore properties (still a private name read across modules) fit; the attributes stay private and X-M8 decides (the plan's section 8.2 names the accessors). No behaviour change.
