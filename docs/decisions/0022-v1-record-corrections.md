# 0022 — v1 record corrections

- **Status:** proposed (2026-11-11; M19 D3a)
- **Date:** 2026-11-11
- **Amends:** architecture §2 (P5), §6.3 rule 10, §7.7, §17 and §19 decision 21.
- **Context:** M19 reviewed the records before the v1 review package ([m19-tasks.md](../design/m19-tasks.md), section 5.1, findings A2-1, 2, 3, 7 and 11). Five rules of the architecture had not kept up with decisions 0009 to 0021: each states less than those decisions decided. The maintainer chose one record that brings the text up to date (section 5.1.1 point 3). Every item restates an earlier decision. No behaviour changes: no grammar, code, diagnostic or test changes with this record.
- **Decision:**
  1. **The recorded exceptions to decision 0002** (amends §2 P5 and §19 decision 21). P5 and decision 21 named the RKM mode option as the only exception. The exceptions in v1 are:
     - the RKM mode option (§19 decision 8);
     - ngspice `SINE`, read as `SIN` (decision 0013 item 3);
     - `Z0` and `Zo` as one parameter (decision 0019 item 3);
     - the 13 LTspice A function names that LTspice's own symbols write (decision 0020 item 3);
     - LTspice's required `.end`, stricter than the reference (decision 0009 item 4, kept by decision 0012 item 3).

     P5 now points to §19 decision 21, which lists them. A form the manual is silent on, such as LTspice's `.subckt` parameter commas (decision 0021 item 4), is an `observed` spec entry (§11.3 rule 3), not an exception.
  2. **The topology signature's entries** (amends §7.7). §7.7 gave F, H and W one controlling source and did not name A's entries. The signature has:
     - a `control` entry for each controlling source of F, H and W, in line order: one for the linear form, N for POLY, none for an expression form (decision 0015 item 3, decision 0017 item 2);
     - for an ngspice A line, a `ports` entry (each port's position, vector flag and type, and each connection's type, nodes and `null`) and a `control` entry for each `%vnam` source (decision 0020 item 4).
  3. **`CONTROL_SOURCE_MISMATCH` is listed** (amends §17). The code of decision 0015 item 5, a warning on an F, H or W controlling source that is not a V, was the one `DiagnosticCode` §17 did not list.
  4. **Where a bare expression is read** (amends §6.3 rule 10). The rule said bare formulas are not accepted. They are refused in a value slot (`R1 a b 1.1*Rx+1000`) and in an ngspice `.param`. A bare expression is read where a decision gives it an end: a behavioural expression (decision 0016 item 2, and LTspice `Laplace=` in decision 0017) and an LTspice `.param` value (decision 0009 item 12).
  5. **When an unresolved name is info** (amends §17). The rule named only an opaque `.include` or `.lib` statement. An `UNRESOLVED_*` diagnostic is also info when:
     - an opaque `.if` or `.lib` block stands in a scope searched, since it counts as an `.include` does; a `.control` block does not (decision 0012 item 5);
     - the name reaches into a subcircuit instance of its scope, which the solver reads and the library does not resolve: LTspice `X1:Vq` (decision 0015 item 4), and the expression reads of decision 0016 item 6.
- **Consequences:**
  - **Architecture:** each amended place cites this record. Descriptive text was brought up to date in the same change (§1.4, §4, §5.2, §5.3, §6.5, §6.7, §7.6, §8, §11.2, §13, §14 and §21); it needs no decision.
  - **Run times:** the maintainer removed the whole-suite run times and the LTspice suite times from the archived task lists and the phase 2 plan on 2026-11-11 (m19-tasks.md section 5.1.1 point 5), since decision 0009 item 2 keeps LTspice timing numbers out of the repository. This is an exception to the rule that an archived file changes only to fix links. Times of ngspice-only and solver-free runs may stay. New records give no run times.
  - **Rules:** `AGENTS.md` lists P8, P11, P12 and P13 with the other principles, and `CONTRIBUTING.md` asks for a `docs/provenance.md` row for each corpus family (§12).
