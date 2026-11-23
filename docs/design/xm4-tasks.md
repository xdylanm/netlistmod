# X-M4 task list — xyce transistors

> **Status:** ACTIVE (2026-11-22)
> **Follows:** [X-M3](./archive/xyce/xm3-tasks.md) (merged as #32) and decisions [0026](../decisions/0026-the-xyce-dialect.md) to [0030](../decisions/0030-xyce-stimulus-and-port.md). Plan: [xyce-plan.md](./xyce-plan.md) sections 3, 8 and 8.1. Governed by [architecture.md](../architecture.md) (§2, §6, §7, §9.3, §10, §11, §12) and [decision 0014](../decisions/0014-transistors.md).

## 1. Scope

X-M4 makes the hidden xyce dialect read the transistor letters Q, M, J and Z, which it refuses today as `planned` in `xyce-devices.json`. The dialect stays hidden (decision 0026 item 4).

- **In:**
  - **Q** ([xyce-ref] §2.3.17 p241–242): 3 to 5 nodes, the bracketed substrate (already a `manual-error` row: Xyce reads `[s]` as a node named `[s]`), VBIC's and HICUM's thermal node, the area, instance parameters.
  - **M** ([xyce-ref] §2.3.20 p292–294): 3 to 7 nodes (MVS 3 or 5, BSIM-SOI 4 to 7, `TNODEOUT`), `IC=` lists, instance parameters.
  - **J and Z** ([xyce-ref] §2.3.18 p286, §2.3.19 p290): as on ngspice, with a positional area.
  - **Models:** the xyce model types NPN, PNP, NJF, PJF, NMF, PMF, NMOS, PMOS (and VDMOS, if Xyce has it) in `model-types.json`; **binned model names** (`nch` selecting `nch.1`, `nch.2`; [xyce-ref] §2.1.21 p89–90), held for X-M4 by xm1-tasks 5.1, so that a binned instance gets no false `UNRESOLVED_MODEL` (plan risk 5).
  - **The document and edit layers:** the X-M4 sites of plan section 8.1 (the transistor rule in `model/_rules_elements.py`, `_transistor`; `_POSITIONAL_AREAS` in `edit/_ops_common.py` for Q, J, Z); `set_param` on the area and the model edits on the four letters.
  - **`.PREPROCESS REMOVEUNUSED`,** left `UnsupportedConstruct` until X-M4 (decision 0028 item 1): revisit now that M and Q exist.
  - **Spec entries, corpus files with manifests, solver tests and discrepancy rows** with categories (decision 0029) for every construct read (§10).
  - **Node counts and the model's `LEVEL`:** whether to check a line's node count against a visible model's `LEVEL` (BSIM-SOI with `TNODEOUT`, MVS, VBIC, HICUM), beyond decision 0014 item 2, which counts by letter only (A1).
- **Not in X-M4:** S, W and the controlled sources (X-M5); a public `Dialect.XYCE` (X-M8).

## 2. Decisions

1. **Workflow as X-M3:** developer and reviewer subagents report to the lead; gates carry the maintainer's decisions; one commit per completed task; one pull request.
2. **Provenance** as decision 0026 items 2 and 3: Xyce source and headers are never read; the manuals are paraphrased and cited by section and page; nothing produced by Xyce is committed.
3. **The manual is the reference and the solver is observed** (decision 0029): every difference is a `discrepancies.md` row with its category.
4. **Reuse first** (§9.3 item 4): `BipolarTransistor`, `Mosfet`, `Jfet`, `Mesfet` and decision 0014's boundary rule. New fields, `Literal` values and `DiagnosticCode` members go on the X-M8 checklist (plan section 8.2). ngspice and LTspice do not change.

## 3. Stages and gates

1. **Stage 1 — research and probes** (A1, A2). Nothing in `src/` changes.
2. **G1 —** the lead writes section 5.1; the maintainer decides the questions.
3. **Stage 2 — implementation** (B1 to B5).
4. **R1 —** an independent review; findings are fixed or recorded.
5. **The pull request,** READY FOR REVIEW.

## 4. Tasks

### Stage 1

- [x] **A1 — The lines.** Q, M, J and Z in the manual against decision 0014 and today's ngspice and LTspice rules: node counts per letter (Q's bracketed substrate and the unbracketed VBIC thermal node in the manual's example; M's MVS, BSIM-SOI and `TNODEOUT` forms), the boundary rule, area (positional or named), flags (`off`), instance parameters (open or closed lists), `IC=` lists, a number or keyword in the model's place. **Node counts and `LEVEL`:** which `LEVEL` values (and `TNODEOUT`) fix the count for each letter, what Xyce does with a count that is wrong for the model, and whether the library should check a line against a visible `.model` (in the same scope; an included model it cannot see), with the diagnostic or refusal that would carry it, or keep decision 0014 item 2's count by letter. Probes for what the manual leaves unclear; options with a recommendation.
- [ ] **A2 — Models and the edit layer.** The xyce model types for the four letters; binned names: which letters bin, how `L=`/`W=` select a bin, and what the index and `UNRESOLVED_MODEL` / `MODEL_TYPE_MISMATCH` should do; the plan section 8.1 sites and the edits (`set_param` on the area, `set_model`, `remove_param`); `.PREPROCESS REMOVEUNUSED` (keep refused, or read it with a diagnostic). Probes; options with a recommendation.

### Stage 2

- [ ] **B1 — Decision record** for the G1 decisions (decision 0031).
- [ ] **B2 — Q, J and Z** in `xyce.lark` and the transistor rules.
- [ ] **B3 — M.**
- [ ] **B4 — Models, binning and the document and edit layers** (and `REMOVEUNUSED`, as G1 decides).
- [ ] **B5 — Evidence:** spec entries, corpus files with manifests, solver tests, discrepancy rows (the `[s]` row's Library column), `devices.md` and `xyce-devices.json`, the README status table, the X-M8 checklist.

## 5. Findings and log

### 5.1 G1 decisions

Stage 1 findings (A1: points 1 to 12; A2 to follow), probed on XyceNF 7.10.0 with `-syntax`, `-norun`, `-namesfile` and `.dc` runs. Each point gives the recommendation; **(G1)** marks a question for the maintainer. Rows are `discrepancies.md` rows, given as Library/Xyce and category (decision 0029). "The repeat row" is the row on a value or parameter written twice; "the level row" is the row on instance parameters of the model's LEVEL.

**How Xyce finds the model.** Xyce ends the nodes by the model's LEVEL: after the third node, the first name that is a `.model` whose level takes that many nodes is the model, wherever the model is defined (later in the file, in an `.include` or `.lib`, in an enclosing scope). LEVEL must be a literal (`level={lv}` stops). Too few nodes for the level always stop; too many either stop, are dropped silently, or are joined to internal nodes (a wrong circuit), by level.

**The lines** ([xyce-ref] §2.3.17 p241–243, §2.3.18 p286, §2.3.19 p290, §2.3.20 p292–296).

1. **Q nodes:** grammar 3 to 5. Observed per level (point 11). An unbracketed substrate runs as the substrate, as does the manual's VBIC example with an unbracketed thermal node. `[s]` is a node named `[s]` (L1, L12): the existing row gets its Library column (`reads/runs`, `manual-error`) and says an unbracketed name works. 6 or more: `ParseError`, row `refuses/runs`, `manual`.
2. **M nodes:** grammar 3 to 7 (most levels take exactly 4 and drop extras silently, VDMOS L18 too, unlike ngspice's 3; MVS L2000/L2001 take 3 and drop the bulk; BSIM-SOI per point 7). 8 or more: `ParseError`, row `refuses/ignores`, `manual`.
3. **J and Z:** exactly 3 (Xyce drops a 4th and 5th): `ParseError`, row `refuses/ignores`, `manual`. Z has level 1 only, J levels 1 and 2.
4. **The boundary rule** of decision 0014 agrees with Xyce on every valid line. They differ only when a node before the model names a visible model whose level takes the count so far (`Q1 c b 0 s qn` with `.model s npn` stops): row `reads/stops`, `library-limit`, or point 12's warning. A number in the model's place (`.model 2 npn`) runs: kept refused (decision 0014 item 4), row `refuses/runs`, `imprecise`. `off` before the model is a node, as the library reads it; `.model off npn` with `Q1 c b 0 off` runs and is refused, row `refuses/runs`, `imprecise`. A numeric 4th field is the substrate. `_check_model_name` adds `tnodeout` for M (point 7).
5. **Area** on Q (level 1), J and Z: positional or `area=`; both on a line stop, as the library refuses (no row). `area=` twice runs with the last: the repeat row, `refuses/runs`, `manual`. A positional area after a parameter runs as the area: `ParseError`, row `refuses/runs`, `manual`. VBIC, FBH, HICUM and MEXTRAM have no area and stop on both forms: the level row, `reads/stops`, `library-limit`. M has no area (both refused, agreeing). `_POSITIONAL_AREAS[_XYCE]` gains Q, J and Z.
6. **(G1) A positional area then parameters** (`<model> <area> <params>`, the manual's own J and Z form): Xyce stops on all but `<area> temp=` alone and `<area> off`. Options: (a) **recommended:** read it as the manual writes it, row `reads/stops`, `manual` (a solver bug); (b) refuse an area followed by any parameter but a lone `temp=`, following the solver.
7. **TNODEOUT** (§2.3.20 p292, Table 2-102 p326, p381): bare `TNODEOUT` always stops Xyce; `TNODEOUT=v` works, any value counting as set. Read `TNODEOUT=` as a listed parameter; refuse bare `TNODEOUT` with the hint "write `TNODEOUT=1`", row `refuses/stops`, `manual-error`.
8. **Instance parameters:** Xyce stops on an unknown name on all four letters, so closed lists as on R, C, L and D (`XY-IPN-001`), each the union of the letter's level tables: Q `AREA DT DTA DTEMP IC IC1 IC2 L M MULT N OFF SW_ET SW_NOISE TEMP TRISE W`; J and Z `AREA DTEMP TEMP`; M about 140 names (Tables 2-92 to 2-147, extracted exactly in B3). A name of another level only stops: the level row. `off` bare or `OFF=` on Q and M (as D's flag), refused on J and Z (agreeing). `M=` on Q and M only. ngspice's `thermal` is refused. A name written twice runs with the last: the repeat row. `temp=` with `dtemp=` runs, ignoring `dtemp` (optional row, `reads/ignores`, `imprecise`).
9. **`IC=` lists:** blanks around `=` and `,` and expressions run; a trailing or empty comma element stops. Q at most 2 values, M at most 5 (`ParseError` above, agreeing); a count above the level's limit but within 5 is `reads/stops`, `library-limit`. No `IC=` on J and Z (agreeing).
10. **Case, `+` lines, comments:** fold and run as elsewhere; no row.
11. **The observed level table** (manual agrees except where marked): Q L1 3–4; L11 3–4 (extras joined to internal nodes); L12 4–5 (extras joined); L23 4 (manual silent); L230 and L234 5; L504 4 and L505 5 (the manual has them the other way, `manual-error`). M: 4 on L1–3, 6, 9, 14, 18, 54, 102, 103, 107, 108, 260, 301, 2002; L10 4–6, or 5–7 with `TNODEOUT=`; L70 and L70450 4–7, exactly 7 with `TNODEOUT=1`; L77, L110, L111 4–5; L1031 and L10240 5; L2000 and L2001 3. J and Z 3. A repeated `level=` runs with the last (for A2).
12. **(G1) Node count and LEVEL** (decision 0014 item 2). Options:
    - (A) the count by letter (points 1 to 3) with rows only (too few `reads/stops`, extras dropped or joined `reads/ignores`/`reads/runs`, `library-limit`);
    - (B) **recommended:** (A) plus a document-layer warning when the model resolves to a visible `.model` with a literal LEVEL and the count is outside point 11's range, saying what Xyce does; also on a node that names a visible model whose level takes the count so far (point 4). Silent when the model is unresolved or the level unknown. It needs the level table as data (`xyce-devices.json` or `model-types.json`) and either a new `DiagnosticCode` (recommended, e.g. `NODE_COUNT_MISMATCH`, on the X-M8 checklist) or `MODEL_TYPE_MISMATCH` with its own message. Topology stays the nodes written;
    - (C) a `ParseError` when the model is visible: not recommended, as the grammar cannot see models and the outcome would depend on which file is open.

**Maintainer's decisions at G1 (2026-11-22):**

- **6:** (a), read a positional area followed by parameters as the manual writes it; row `reads/stops`, `manual`.
- **12:** (B), the count by letter with rows, plus a document-layer warning against a visible model's literal LEVEL, under a new `DiagnosticCode` (X-M8 checklist).

**Code sites (A1):** `xyce.lark` (the four rules, closed parameter lists with `*_unlisted` refusals, `off`/`OFF=`, an `IC=` list, `TNODEOUT=` and the bare refusal); `xyce-devices.json`; `_transistor` (a positional area after a parameter or beside `area=`; its area message is ngspice's) and `_check_model_name` in `model/_rules_elements.py`; `_POSITIONAL_AREAS`; for 12 (B) `document/diagnostics.py` near `MODEL_TYPE_MISMATCH`.

Probes: the scratchpad folder `xm4-a1` (not committed; decision 0026).

### 5.2 Log

- 2026-11-22: task list written; X-M3 merged as #32.
- 2026-11-22: the maintainer kept binned model names (held from xm1-tasks 5.1) and the `.PREPROCESS REMOVEUNUSED` revisit (decision 0028 item 1) in X-M4's scope, though the plan's X-M4 row names neither; and added to A1 the question of checking node counts against the model's `LEVEL`.
- 2026-11-22: A1 done (section 5.1, points 1 to 12); G1 questions 6 and 12 for the maintainer.
- 2026-11-22: G1 (A1): the maintainer accepted the recommendations on points 6 (a) and 12 (B).
