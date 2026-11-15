# 0025 — QSPICE's built-in help as the qspice reference

- **Status:** accepted (2026-11-15, maintainer; M21 section 5.1 item 5)
- **Date:** 2026-11-15
- **Amends:** architecture §12 (allowed sources) and §11 for the planned qspice dialect (§9.2).
- **Context:**
  - **No public manual.** Qorvo publishes no qspice language reference online. The only manual is the help, `QSPICE.chm`, that the QSPICE installer puts beside the program (M21 reviews Q1 and Q2).
  - **The help is proprietary.** Its licence agreement (the help's "Software License Agreement for QSPICE Software") says Qorvo owns the software and its documentation. The agreement licenses use of the software, and forbids distributing the software, making derivative works of it, and reverse-engineering it. It grants no right to reproduce the documentation, and its title page reserves all rights.
  - **LTspice had a public alternative.** §12 says LTspice's built-in help is neither cited nor copied, because the Apache-2.0 `ltspice-reference` serves as LTspice's manual (decision 0009). qspice has no such reference.
  - **The maintainer's reading of P5 and P8 (2026-11-15).** The manual is the reference for what the grammar accepts. That requires only that behaviour can be confirmed against the manual, not that the manual's text is quoted.
- **Decision:**
  1. **The reference.** QSPICE's built-in help is the qspice manual for §11, cited as `[qspice-help]` with its topic, for example `[qspice-help] "R-device"`. `docs/references.md` records the QSPICE build, the help's edition and the access date. A citation is re-checked when a newer help is adopted, as for the other manuals.
  2. **Paraphrase only.** Facts are written in the project's own words. A quotation is a few words at most, and only where the exact wording matters (a keyword, or a rule's key phrase). Tables, examples and passages are not reproduced.
  3. **The licence terms are respected:**
     - The help, its pages, extracts and images are never committed, published or distributed. A local copy for reading stays outside the repository, on the maintainer's machine.
     - The QSPICE software is not distributed, modified or reverse-engineered. Running it to observe behaviour (§10 T8, P8) is use of the software.
     - Example schematics and models shipped with QSPICE are not copied into the corpus. Fixtures are authored in this repository (§12).
     - Raw files, logs and timing numbers are not committed, as for LTspice (decision 0009 item 2), until a later decision allows otherwise.
  4. **Behaviour is still confirmed by the solver** (P8). Where the help and the solver disagree, or the help is silent, the rules of §11.3 apply, as for every dialect.
  5. **LTspice is unchanged.** LTspice keeps `ltspice-reference` as its manual, and its built-in help is still not cited (decision 0009).
- **Consequences:**
  - M21's qspice reviews (Q1 and Q2) are re-run from the help, and the qspice plan is written from them.
  - §12 lists QSPICE's help among the allowed sources under these conditions.
  - The local copy of the help is not covered by the repository's provenance records, because it is never in the repository. Its build and edition are recorded in `references.md` instead.
