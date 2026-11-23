# 0030 — xyce transient functions and the P port

- **Status:** accepted (2026-11-22, maintainer; X-M3 gate G1)
- **Date:** 2026-11-22
- **Amends:** [decision 0027](0027-xyce-structure-names-and-values.md) item 6 (a transient function on V or I is refused whole until X-M3), for the hidden xyce dialect only.
- **Context:** X-M3 ([xm3-tasks.md](../design/archive/xyce/xm3-tasks.md)) makes the hidden xyce dialect read the transient functions of V and I and the P port. Stage 1 compared the Xyce 7.10 reference manual (§2.3.9 to §2.3.11, §6.1.12) with the XyceNF 7.10.0 binary (section 5.1, points 1 to 29). The maintainer decided each point at G1. Differences between the manual and the binary are rows in `docs/grammars/xyce/discrepancies.md`, with categories under [decision 0029](0029-xyce-discrepancy-categories.md). Item numbers below are xm3-tasks.md section 5.1 points, which hold the evidence.
- **Decision:**
  1. **The line** (points 1, 2): `[[DC] v] [AC mag [ph]] [function]`, in that order, with at most one function, which comes last.
  2. **The functions** PULSE, SIN, EXP, PAT, PWL and SFFM (points 3 to 6, 10, 13):
     - The parentheses are optional and must be balanced around the whole list.
     - There are no commas.
     - Each argument is a number (the device-field reader), a braced formula or a quoted formula.
     - The argument counts are checked per function: PULSE 1–7, SIN 3–6, EXP 2–6, SFFM 2–5, PAT 7.
     - PWL takes an even count of at least 2.
     - Every name folds case. There is no `SINE`.
  3. **No keyword arguments** on PULSE, SIN, EXP, SFFM or PAT (point 7), except PAT's `R=`.
  4. **PAT** (points 8, 9): DATA is a `b`/`B` bit string in position 7, held in `SourceSpec.args`, which widens to `Value | Identifier`. The repeat count is `R=n` only. A positional eighth field is refused with a hint (`manual-error`: Xyce ignores it).
  5. **PWL** (points 11, 12):
     - `TD=` and `R=` stand after the pairs or the file name, outside the parentheses, in either order, at most once each. This also holds for PAT's `R=`. R's range is not checked.
     - `FILE` takes a double-quoted or bare path and is held as a `FILE` parameter. The path is never read, and the document layer gives it no file reference, since Xyce resolves it against the working directory.
  6. **The P port** (points 16 to 21, 26):
     - The form is `P n+ n- [[DC] v] port=n [Z0=v] [AC …] [function]`. `port=` and `Z0=` may come in either order, between the DC and AC parts.
     - `port=` is required. It takes an unsigned integer literal of at least 1, or a braced or quoted formula.
     - `Z0=` takes a device-field number or a formula.
     - Both need the `=`. No other parameter is allowed.
     - P is allowed in a subcircuit body.
     - The node is `PortSource`, a sibling of `VoltageSource` and `CurrentSource` under `_IndependentSource`, with `port` and `Z0` held in `params`.
  7. **No new diagnostics** (points 15, 23):
     - Under `.HB`, a DC sweep uses a function source's time-0 value. This is a row (`imprecise`).
     - `.LIN`'s port numbering (1..N) is a row (`library-limit`).
  8. **Per-dialect tables** (points 27 to 29; decision 0026 item 6):
     - the source kinds that may carry named parameters (xyce: P);
     - the kinds that need a value (xyce: none).

     The P edits keep the order of item 6. `remove_param` refuses `port`.
  9. **New names** (`PortSource`, the widened `SourceSpec.args`) are best-effort additions under decision 0024 item 11. They are kept for the X-M8 release notes (xyce-plan.md section 8.2). ngspice and LTspice do not change.
- **Consequences:**
  - `xyce.lark` replaces `src_function` with the typed functions and adds the P line. `xyce-devices.json` no longer plans P.
  - `_rules_sources.py`, `edit/_ops_sources.py` and their xyce tables change.
  - Spec entries, corpus, solver tests and discrepancy rows cover each construct.
