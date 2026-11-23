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

- [ ] **A1 — The lines.** Q, M, J and Z in the manual against decision 0014 and today's ngspice and LTspice rules: node counts per letter (Q's bracketed substrate and the unbracketed VBIC thermal node in the manual's example; M's MVS, BSIM-SOI and `TNODEOUT` forms), the boundary rule, area (positional or named), flags (`off`), instance parameters (open or closed lists), `IC=` lists, a number or keyword in the model's place. **Node counts and `LEVEL`:** which `LEVEL` values (and `TNODEOUT`) fix the count for each letter, what Xyce does with a count that is wrong for the model, and whether the library should check a line against a visible `.model` (in the same scope; an included model it cannot see), with the diagnostic or refusal that would carry it, or keep decision 0014 item 2's count by letter. Probes for what the manual leaves unclear; options with a recommendation.
- [ ] **A2 — Models and the edit layer.** The xyce model types for the four letters; binned names: which letters bin, how `L=`/`W=` select a bin, and what the index and `UNRESOLVED_MODEL` / `MODEL_TYPE_MISMATCH` should do; the plan section 8.1 sites and the edits (`set_param` on the area, `set_model`, `remove_param`); `.PREPROCESS REMOVEUNUSED` (keep refused, or read it with a diagnostic). Probes; options with a recommendation.

### Stage 2

- [ ] **B1 — Decision record** for the G1 decisions (decision 0031).
- [ ] **B2 — Q, J and Z** in `xyce.lark` and the transistor rules.
- [ ] **B3 — M.**
- [ ] **B4 — Models, binning and the document and edit layers** (and `REMOVEUNUSED`, as G1 decides).
- [ ] **B5 — Evidence:** spec entries, corpus files with manifests, solver tests, discrepancy rows (the `[s]` row's Library column), `devices.md` and `xyce-devices.json`, the README status table, the X-M8 checklist.

## 5. Findings and log

### 5.1 G1 decisions

(Written at G1.)

### 5.2 Log

- 2026-11-22: task list written; X-M3 merged as #32.
- 2026-11-22: the maintainer kept binned model names (held from xm1-tasks 5.1) and the `.PREPROCESS REMOVEUNUSED` revisit (decision 0028 item 1) in X-M4's scope, though the plan's X-M4 row names neither; and added to A1 the question of checking node counts against the model's `LEVEL`.
