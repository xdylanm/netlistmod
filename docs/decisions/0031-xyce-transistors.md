# 0031 — xyce transistors: Q, M, J, Z, binned models and `REMOVEUNUSED`

- **Status:** accepted (2026-11-22, maintainer; X-M4 gate G1)
- **Date:** 2026-11-22
- **Amends:** [decision 0014](0014-transistors.md) items 2 (node counts: xyce counts by letter, plus the LEVEL warning), 5 (area on xyce) and 8 (xyce model types); [decision 0028](0028-xyce-directives.md) item 1 (`.PREPROCESS REMOVEUNUSED` is no longer unsupported). The hidden xyce dialect only.
- **Context:** X-M4 ([xm4-tasks.md](../design/archive/xyce/xm4-tasks.md)) adds the transistor letters Q, M, J and Z to the hidden xyce dialect. Stage 1 compared the Xyce 7.10 reference manual ([xyce-ref] §2.1.21, §2.3.17 to §2.3.20, §2.1.29) with probes on the XyceNF 7.10.0 binary (section 5.1, points 1 to 26). The maintainer decided points 6, 12, 15, 19, 21, 24 and 26 one by one at G1 and accepted the recommendations on the rest. Differences between the manual and the binary are rows in `docs/grammars/xyce/discrepancies.md`, with categories under [decision 0029](0029-xyce-discrepancy-categories.md). Item numbers below are xm4-tasks.md section 5.1 points, which hold the evidence.
- **Decision:**
  1. **Lines and node counts** ([xyce-ref] §2.3.17 p241–243, §2.3.18 p286, §2.3.19 p290, §2.3.20 p292–296; points 1 to 3):
     - Q takes 3 to 5 nodes. An unbracketed substrate is a substrate. `[s]` is a node named `[s]` (the existing `manual-error` row gains its Library column).
     - M takes 3 to 7 nodes.
     - J and Z take exactly 3.
     - A longer line is a `ParseError`.
     - Counts are by letter, not by the model's type.
  2. **The boundary rule** (point 4): decision 0014 item 1 stands. A number in the model's place stays refused. `off` before the model is a node. `_check_model_name` adds `tnodeout` for M.
  3. **Area** (points 5, 6, 22): Q (level 1), J and Z take `area=` or a positional area, not both. M has no area. A positional area is read as the manual writes it, including when parameters follow it (the manual's J and Z form), although Xyce stops on most such lines (G1 point 6: `reads/stops`, `manual`). A positional area after a parameter is a `ParseError`. `off` after a positional area is read, and Xyce ignores it (`reads/ignores`). `area=` written twice is the repeat row.
  4. **Instance parameters** (points 7 to 9):
     - The lists are closed, as on R, C, L and D (`XY-IPN-001`), each the union of the letter's level tables. M's list (about 140 names, [xyce-ref] Tables 2-92 to 2-147) is extracted exactly in B3.
     - A name of another level is the level row (`reads/stops`).
     - `off` or `OFF=` is allowed on Q and M, refused on J and Z. `M=` is allowed on Q and M only. ngspice's `thermal` is refused.
     - `IC=` takes a comma list: at most 2 values on Q, at most 5 on M. J and Z have none.
     - `TNODEOUT=v` is an ordinary parameter (G1 point 24: no refusal on edits). A bare `TNODEOUT` is refused with the hint "write `TNODEOUT=1`" (`refuses/stops`, `manual-error`).
  5. **Node count against LEVEL** (points 11, 12, 20; G1 point 12, option B). The count by letter is the grammar's, with rows. The document layer also warns when a line's model resolves to a visible `.model` with a literal LEVEL and the count is outside that level's range, or when a node before the model names a visible model whose level takes the count so far. The warning says what Xyce does. It is silent when the model is unresolved or the level unknown. The level table is data in a new `model/xyce-levels.json` with a loader. A model's LEVEL is its last `level` parameter when that is a plain integer-valued number; level 1 is the default; for a set, each bin with a known level is checked. Topology stays the nodes written (P4). The warning has its own `DiagnosticCode`, `NODE_COUNT_MISMATCH` (a best-effort name).
  6. **Model types** (points 13, 14): Q takes NPN and PNP; M takes NMOS and PMOS; J takes NJF and PJF; Z takes NMF and PMF. There is no VDMOS type: it is NMOS or PMOS at `LEVEL=18`. `MODEL_TYPE_MISMATCH` stays a warning and says that Xyce 7.10 stops (it finds no valid model card); on an M it adds that hint.
  7. **Binning** (points 15 to 18; [xyce-ref] §2.1.21.2 p90, §2.1.25.21 p119; G1 point 15, option a; point 19, option b):
     - Only M bins. Any non-empty suffix makes a model `<name>.<suffix>` a bin of `<name>` (`reads/runs`, `imprecise`: the manual says "bin number").
     - Lookup finds an exact name first, anywhere in the scope chain. Then, for a `Mosfet` on xyce only, it gathers the `<name>.*` models of the chain.
     - No set is formed under a literal `MODEL_BINNING=false`, and none for a `head:param` target.
     - The library does not select a bin; Xyce does. Bin selection, an unselectable set (no `L=`/`W=`, or a bin missing a bound), mixed bins and the `.STEP` choice are rows (`library-limit` or `imprecise`), with no new diagnostic.
  8. **The index** (point 18): a set's reference targets its first bin (scope chain, then source order). A read-only accessor gives the whole set. `UNRESOLVED_MODEL` is silent when a set resolves. `MODEL_TYPE_MISMATCH` warns on each bin that is not NMOS or PMOS. `DUPLICATE_DEFINITION` already covers a repeated bin name.
  9. **The edit layer** (points 21 to 24):
     - `set_param(…, "area", …)` on Q, J and Z replaces an existing area, positional or named, in place. With none, it appends `area=v` at the end of the line (G1 point 21), since `area=` runs beside any parameter and after `off`. `area` on M stays an `EditError`. `_POSITIONAL_AREAS[_XYCE]` gains Q, J and Z for reading and replacing.
     - `set_model` resolves a set as the index does and refuses one whose bins are not all NMOS or PMOS. `set_model_param` on a set name is an `EditError` that asks for a bin.
     - `remove_param` keeps its `EditError` on a positional area; `area=` and `IC=…` are removed as parameters. `set_param("ic", …)` replaces the whole list. The `off` edits are unchanged.
  10. **`.PREPROCESS REMOVEUNUSED`** ([xyce-ref] §2.1.29 p126; point 25; G1 point 26, option c): read as an `UnknownDirective` with `UNTYPED_DIRECTIVE_PRESERVED`, as ADDRESISTORS. The grammar takes a closed comma list of at least one of C, D, I, L, M, Q, R, V, one line per netlist, in a body too; a repeated letter is read, as Xyce runs it (no row). There is no device warning. Topology stays as written (P4). Rows: blank separators and a trailing comma `refuses/runs`, `manual`; removal that depends on how instances connect `reads/runs`, `library-limit`. `XY-UNS-001` loses `REMOVEUNUSED`.
  11. **New names** are best-effort additions under decision 0024 item 11, kept for the X-M8 checklist (xyce-plan.md section 8.2): the `DiagnosticCode` `NODE_COUNT_MISMATCH`; the model-set accessor on the index; the data file `model/xyce-levels.json`. ngspice and LTspice do not change.
- **Consequences:**
  - `xyce.lark` gains the four rules with closed parameter lists and a typed `REMOVEUNUSED`. `xyce-devices.json` no longer plans Q, M, J and Z.
  - `model/_rules_elements.py`, `model/_rules_structure.py`, `document/index.py`, `document/diagnostics.py`, `document/models.py`, `edit/_ops_common.py`, `edit/_ops_elements.py` and their xyce tables change.
  - `model-types.json` gains the xyce transistor types and the new data file holds the level table.
  - Spec entries, corpus, solver tests and discrepancy rows cover each construct.
