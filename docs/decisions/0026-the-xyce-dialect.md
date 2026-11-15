# 0026 — The xyce dialect (X-D0)

- **Status:** accepted (2026-11-15, maintainer; X-M0 decisions 1 to 3 and gate G1)
- **Date:** 2026-11-15
- **Amends:** architecture §4 (`dialects.py`), §9.2, §9.3 item 1 and §12, for the xyce dialect planned in [xyce-plan.md](../design/xyce-plan.md).
- **Context:**
  - **The plan.** xyce is the third dialect (§9.2). M21 found that adding it changes nothing the 1.0 contract covers ([decision 0024](0024-the-1-0-public-api.md) item 11), and planned it as milestones X-M0 to X-M8. X-M0 ([xm0-tasks.md](../design/archive/xyce/xm0-tasks.md)) sets up the dialect, the solver harness and the documentation.
  - **The contract binds what is released.** Once a release reads an xyce form, changing that reading needs a major version (decision 0024 item 3). Releases are made independently of milestones, so a half-built grammar could be released between X-M0 and X-M8.
  - **Xyce is GPLv3,** and its manuals are Sandia reports with the NTESS copyright and no licence for their text (X-M0 task A1). The solver is a free download that runs on the maintainer's Windows machine (task A3).
  - **The binary is more lenient than the manual** in places (X-M0 section 5.1 point 4): `.END` is not required, text after `.END` and unknown dot-commands are ignored with a warning at most, and `//` (which the manual's examples use) is not a comment.
- **Decision:**
  1. **The references** are `[xyce-ref]` and `[xyce-ug]`, Version 7.10 (SAND2025-05993 and SAND2025-05995), recorded in `docs/references.md`. They are cited by section and printed page, and paraphrased (§11.3 rule 4).
  2. **Provenance.** Xyce's source code, including the headers installed with it, is never read (P10). Running the binary to observe behaviour is allowed (§10 T8, P8).
  3. **Evidence as for ngspice.** Solver tests run Xyce locally and generate raw files and logs at test time. Nothing produced by Xyce is committed, and fixtures are authored here. `validated_on` records the version that Xyce's `-v` prints (`XyceNF Release 7.10.0`). CI installs no solver (decision 0011).
  4. **Hidden until X-M8.** The xyce milestones merge to `main`, but `Dialect` gains its public `XYCE` member only after the X-M8 review.
     - **Until then** the dialect is `netlistmod.dialects._XYCE`, an instance of `Dialect` that the enum does not register. It is absent from `list(Dialect)`, `Dialect.__members__`, `Dialect("xyce")`, `Dialect["XYCE"]` and `Dialect.from_name`, and it is bound to no public name. It passes `isinstance(…, Dialect)`, so no annotation or public signature changes. For the same reason `_XYCE in Dialect` is true while it is hidden (`"xyce" in Dialect` is not).
     - **It relies on `Enum` internals** that Python does not document. An architecture test checks both properties on every Python that CI runs; it cannot be pickled.
     - **A release before X-M8** ships xyce's grammar files as package data, reachable only through the private name. Nothing public changes, and the 1.0 contract does not cover the hidden dialect.
     - **At X-M8** `XYCE` becomes a member (decision 0024 item 11 makes that a minor change), `_XYCE` becomes an alias for it, and the guard tests are removed.
  5. **The grammar follows the manual** (P5, §11.3), as for the other dialects. Where the binary is more lenient, the difference is a row in `docs/grammars/xyce/discrepancies.md`. Whether `.END` is required is decided in X-M1, and the closed list of dot-commands in X-M2.
  6. **X-M0's xyce reads only structure:** the title (line 1, even when blank), comment lines, blank lines and `.END`. Every element line and every other dot-command raises `UnsupportedConstruct`, until the milestone that reads it. So does an indented line other than a `*` comment: Xyce reads every indented line as a comment ([xyce-ug] §4.1.3 p43), and until decision X-D1 (X-M1) the library refuses such a line rather than read it either way. A line that begins with `;` (an in-line comment, §4.1.3.1 p43) and a `+` line after comment or blank lines (§4.1.3.2 p43) are refused too, until X-M1 reads comments and continuation. Code that branches on a dialect and that an xyce load can reach is keyed per dialect, so a missing entry fails loudly. Branches xyce cannot reach yet are listed in the xyce plan, each with its milestone.
- **Consequences:**
  - §4 and §9.3 describe the hidden phase; §12 lists the Xyce manuals and binary among the allowed sources; §9.2 points to the plan.
  - `docs/grammars/xyce/` exists from X-M0 with spec entries for what X-M0 reads.
  - The test harness gains `XYCE_EXE` and `--require-solver xyce`. `tests/support/raw.py` reads Xyce's ASCII raw files.
  - Decisions X-D1 to X-D6 of the plan remain open, each for its milestone.
