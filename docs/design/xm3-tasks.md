# X-M3 task list — xyce stimulus and the P port

> **Status:** ACTIVE (2026-11-22; G1 decided, [decision 0030](../decisions/0030-xyce-stimulus-and-port.md))
> **Follows:** [X-M2.1](./archive/xyce/xm2.1-tasks.md) (merged as #31) and decisions [0026](../decisions/0026-the-xyce-dialect.md) to [0029](../decisions/0029-xyce-discrepancy-categories.md). Plan: [xyce-plan.md](./xyce-plan.md) sections 4 and 8. Governed by [architecture.md](../architecture.md) (§2, §6, §7, §9.3, §10, §11, §12).

## 1. Scope

X-M3 makes the hidden xyce dialect read the transient functions of the V and I sources, which X-M1 refuses whole (`src_function` in `xyce.lark`), and the P port device. The dialect stays hidden (decision 0026 item 4).

- **In:**
  - **The functions** PULSE, SIN, EXP, PAT, PWL (with `FILE "name"`, `TD=` and `R=`) and SFFM, with and without parentheses ([xyce-ref] §2.3.9, §2.3.10); reusing `SourceSpec` where the reading is the same as on ngspice or LTspice. PAT is new.
  - **The P port** ([xyce-ref] §2.3.11): `P n+ n- [[DC] v] port=<n> [Z0=v] [AC …] [tran]`, a new source-like node. The letter is ngspice's coupled line, so P is xyce-only.
  - **The document and edit layers:** the X-M3 line of the plan's section 8.1 (`model/_rules_sources.py`, `edit/_ops_sources.py`); the source edits (`set_stimulus`, `remove_stimulus` and the others that exist) on xyce and the P port; references a PWL `FILE` makes, if any.
  - **The open `.HB` and SIN question** from X-M2: a `.DC` sweep of a SIN source reports 0 when the netlist has `.HB`.
  - **Spec entries, corpus files with manifests, solver tests and discrepancy rows** with categories (decision 0029) for every construct read (§10).
- **Not in X-M3:** the controlled and behavioural sources (X-M5); `.LIN` beyond the P port's fields (an `UnknownDirective`, decision 0028 item 1); a public `Dialect.XYCE` (X-M8).

## 2. Decisions

1. **Workflow as X-M2** (decision 0026; X-M0 decision 3): developer and reviewer subagents report to the lead; gates carry the maintainer's decisions; one commit per completed task; one pull request.
2. **Provenance** as decision 0026 items 2 and 3: Xyce source and headers are never read; the manuals are paraphrased and cited by section and page; nothing produced by Xyce is committed, and no timing numbers.
3. **The manual is the reference and the solver is observed** (decision 0029): every difference is a `discrepancies.md` row with a category and its Library/Xyce pair.
4. **Reuse first** (§9.3 item 4). New fields, nodes, `Literal` values and `DiagnosticCode` members are best-effort additions (decision 0024 item 11) and go on the X-M8 checklist (plan section 8.2). ngspice and LTspice do not change (decision 0024).

## 3. Stages and gates

1. **Stage 1 — research and probes** (A1, A2). Reports to the lead; nothing in `src/` changes.
2. **G1 —** the lead writes section 5.1; the maintainer decides the questions the reports raise.
3. **Stage 2 — implementation** (B1 to B5).
4. **R1 —** an independent review; findings are fixed or recorded.
5. **The pull request,** READY FOR REVIEW.

## 4. Tasks

### Stage 1

- [x] **A1 — The transient functions.** Each of PULSE, SIN, EXP, PAT, PWL and SFFM in the manual against today's `SourceSpec` and its ngspice and LTspice rules (reuse, reuse with differences, new): the argument counts and defaults, parentheses or none, commas, braces and expressions in arguments, keyword arguments (`TD=`, `R=`, PWL `FILE`), PAT's bit string, a function after `AC` or before `DC`, a second function; the `.HB` and SIN question. Probes for what the manual leaves unclear. Options for each question, with a recommendation.
- [x] **A2 — The P port and the edit layer.** The P line's forms and fields against the V source and ngspice's coupled line; the node it needs; where P may stand and what `.LIN` needs from it; the source edits on xyce (the plan's section 8.1 sites) and on P. Probes; options with a recommendation.

### Stage 2

- [x] **B1 — Decision record** for the G1 decisions.
- [x] **B2 — The functions** in `xyce.lark` and the source rules.
- [x] **B3 — The P port.**
- [x] **B4 — The document and edit layers.**
- [x] **B5 — Evidence:** spec entries, corpus files with manifests, solver tests, discrepancy rows, the README status table, the X-M8 checklist.

## 5. Findings and log

### 5.1 G1 decisions

Stage 1 findings (A1: points 1 to 15; A2: points 16 to 29), probed on XyceNF 7.10.0 in print mode. Each point gives the recommendation; **(G1)** marks a question for the maintainer. Rows are `discrepancies.md` rows, given as Library/Xyce and category (decision 0029).

**The functions** ([xyce-ref] §2.3.9 p221–225, §2.3.10 p226–230; PWL notes §6.1.12 p846). V and I read alike.

1. **Order:** `[[DC] v] [AC mag [ph]] [function]`, as `xyce.lark` has it now. A function before `AC` (Xyce finds `AC` anywhere): `ParseError`, row `refuses/runs`, `manual`. A function before `DC` or a value stops Xyce too.
2. **A second function:** `ParseError`. Xyce stops on some pairs and silently ignores the second of others: row `refuses/ignores`, `manual`.
3. **Parentheses** are optional on all six functions and must be balanced around the whole list. Xyce runs unbalanced lists: row `refuses/runs`, `manual`. `PWL(…)` is read (`imprecise`, `reads/runs`). PSpice pair groups `(0,0)` stop Xyce and are refused.
4. **No commas:** every comma stops Xyce. Unlike ngspice's `fn_arg`. Optional row (`imprecise`; §6.1.12 hints at commas).
5. **Arguments:** `NUMBER | {…} | '…'`. A bare name stops Xyce, so no bare formula. `+` lines inside a list run.
6. **Counts per function** (PULSE 1–7, SIN 3–6, EXP 2–6, SFFM 2–5, PAT 7–8). Too few: `ParseError`, as Xyce. Too many: `ParseError`, row `refuses/ignores`, `manual`. No defaults are filled.
7. **(G1) Keyword arguments** on PULSE, SIN, EXP, SFFM, PAT (`PULSE(0 1 TD=10n)`, `V1=`…): undocumented, but Xyce reads them in any order. Recommend refusing them (`refuses/runs`, `manual`), except PAT's `R=` (point 9).
8. **(G1) PAT's DATA** is `b` or `B` then 0s and 1s, in the 7th place (a new terminal; anything else stops Xyce). It is not a `Value`. Recommend widening `SourceSpec.args` to `Value | Identifier`, keeping positions as the manual's table (X-M8 checklist). Alternatives: a `pattern` field, or a `DATA` parameter.
9. **(G1) PAT's R:** the manual makes R the 8th positional field. Xyce silently ignores a positional R and reads `R=n`. Recommend reading `R=` and refusing a positional R with a hint: `manual-error`, `refuses/ignores`. Alternative: read the positional R as the manual says (`manual`, `reads/ignores`).
10. **PWL pairs:** an even count of at least 2. Xyce runs an odd count, giving 0: row `refuses/runs`, `manual`. Time order is not checked.
11. **(G1) PWL `TD=` and `R=`:**
    - after the list or the file name, outside the parentheses, either order, at most once each, on both forms (`imprecise`; the synopsis has them after FILE only, the example inline);
    - before the list, inside the parentheses, or repeated: `ParseError` (`refuses/runs`, `imprecise`);
    - Xyce stops when R is not in 0 ≤ R < the last time. Recommend leaving the range unchecked: `reads/stops`, `library-limit`.
12. **(G1) PWL FILE:**
    - `FILE` (any case), then a double-quoted string or a bare path, then `TD=`/`R=`, held as a `FILE` parameter as on LTspice; the path is never read;
    - refused: `FILE=` and single quotes, on which Xyce stops ("Could not find file"; single quotes refused with the hint "write the path in double quotes", corrected at R1), parentheses around the FILE form (`imprecise`, `refuses/runs`), and extra tokens or a second `FILE` (`manual`, `refuses/ignores`);
    - a missing file: `reads/stops`, `library-limit`;
    - Xyce resolves a relative path against the working directory, not the netlist's folder, so recommend no file reference in the document layer;
    - `set_stimulus_arg` must write `FILE name` without `=` on xyce.
13. **Case** folds everywhere. `SINE` stops Xyce, so there is no `SINE` keyword on xyce.
14. **Reuse:** PULSE, SIN, EXP, SFFM and PWL reuse `SourceSpec`, with the differences above. PAT is new. xyce keeps its own `_xsrc` chain; core's `fn_list` (required parentheses, commas) does not fit.
15. **(G1) `.HB` and SIN (open from X-M2):** with a `.HB` line in the netlist and a DC sweep running, every source with a function takes its function's value at time 0, not its DC value; a swept function source does not follow the sweep. The manual is silent. Recommend a row (`imprecise`) and a new warning on a `.DC` or `.STEP` that sweeps a function source while `.HB` is present (X-M8 checklist). Alternatives: the row only, or the warning on every function source's DC value under `.HB`.

**The P port** ([xyce-ref] §2.3.11 p231, Table 2-35 p178; [xyce-ug] §7.11.2 p136).

16. **The form** `P n+ n- [[DC] v] port=<n> [Z0=v] [AC …] [function]`. Outside `.LIN` it is a V source in series with Z0 (default 50).
17. **`port=` is required.** Without it, Xyce runs an ideal V source that is not a port: `refuses/runs`, `manual`.
18. **The port number** is an unsigned integer literal of 1 or more, or a braced or quoted formula. Xyce stops on `1.5`, `1e0`, `1k`, a bare name and a second `port=`. Refused:
    - `1.0` (`refuses/runs`, `imprecise`);
    - `0` and negatives, which run outside `.LIN` (`refuses/runs`, `manual`);
    - `port 1` with no `=` (`refuses/runs`, `manual`).

    Blanks around `=` are allowed.
19. **Z0** uses the device-field number reader. A bare name and a second `Z0=` stop Xyce. Refused:
    - `100+10j`, whose imaginary part Xyce drops (`refuses/runs`, `manual`);
    - `Z0 100` with no `=`.

    `ZO` stops Xyce. No sign check.
20. **(G1) Field order:** Xyce needs the DC part first, then takes `port=` and `Z0=` anywhere. Recommend: DC, then `port=` and `Z0=` in either order, then AC, then the function. Xyce's other orders, `DC` with no value, and a comma are `refuses/runs`, `manual`. The bare-`AC` row extends to P.
21. **Lines:** exactly two nodes. P is allowed in a subcircuit body; each instance is a port. It takes no other parameter (`M=` and unknown names stop Xyce).
22. **Analyses:** P runs under `.DC`, `.OP`, `.AC`, `.TRAN` and `.HB`. `.DC P1`, `.STEP P1`, `P1:DCV0` and `P1:Z0` work. An F or H controlled by P stops Xyce (relevant at X-M5).
23. **(G1) `.LIN` numbering:** the ports of the flattened netlist must be exactly 1..N, or `.LIN` aborts. Without `.LIN` any numbering runs. Recommend a new warning when a top-level `.LIN` is present and the literal port numbers are not 1..N; a formula number is `library-limit` (X-M8 checklist). Alternative: no check in X-M3 and a row (`reads/stops`, `library-limit`).
24. **Undocumented:** `port=` on a V line makes it a `.LIN` port, and Xyce ignores `Z0=` on V. The existing row "Xyce ignores a parameter on V or I" is wrong for `port=`. The library keeps refusing; the row is corrected (`refuses/runs`, `manual`).
25. **ngspice's P** (a coupled line) shares only the letter. The nearest reuse is ngspice's `portnum`/`z0` on V, held in `params`.
26. **(G1) The node:** recommend a sibling of V and I under `_IndependentSource` (named `PortSource`, not `Port`), with `port=` and `Z0=` in `params`. Then `set_param` and `remove_param` work, and the controlled-source check still tells P from V. A V subclass would make `isinstance(…, VoltageSource)` mean something new. The code that learns it: `_SOURCES` (`edit/_ops_common.py`), `_PRIMARY_PARAMS` (`document/index.py`, `dcv0`), the `takes` tuple in `_ops_remove.py`, `_source_item` in `_rules_sources.py`. Nets and names need nothing.

**The edit layer** (plan §8.1).

27. **`model/_rules_sources.py:244`:** a per-dialect table of the source kinds that may carry named parameters (ngspice V; LTspice V and I; xyce P).
28. **`edit/_ops_sources.py:171`:** a per-dialect table of the kinds that need a value (LTspice I; none on ngspice or xyce, where a bare source runs as 0).
29. **Edits on P:**
    - `set_ac` and `set_stimulus` insert after the last of `port=` and `Z0=`, and a new `Z0=` goes right after `port=`;
    - `remove_param` refuses `port`;
    - `set_param` takes only `port` and `z0` on P, and `_PORT_PARAMS[_XYCE]` stays empty for V;
    - the other source edits work once P is in `_SOURCES`.

**Maintainer's decisions at G1 (2026-11-22), one by one:**

- **7:** refuse keyword arguments on PULSE, SIN, EXP, SFFM and PAT (`manual`).
- **8:** `SourceSpec.args` widens to `Value | Identifier`, with PAT's DATA in position 7 (X-M8 checklist).
- **9:** read PAT's `R=` and refuse a positional R with a hint (`manual-error`).
- **11:** `TD=` and `R=` stand after the list or the file name only, outside the parentheses, at most once each. This holds for PAT's `R=` too. R's range is not checked (`library-limit`).
- **12:** no file reference for PWL `FILE`; the path is held as text.
- **15:** a row only (`imprecise`), with no diagnostic.
- **18, 19:** the refusals as recommended.
- **20:** DC, then `port=` and `Z0=` in either order, then AC, then the function.
- **23:** no numbering check; a row (`reads/stops`, `library-limit`).
- **26:** `PortSource`, a sibling of V and I, with `port=` and `Z0=` in `params`.

Probes: the scratchpad folders `xm3-a1` and `xm3-a2` (not committed; decision 0026).

### 5.2 Log

- 2026-11-22: task list written; X-M2.1 merged as #31.
- 2026-11-22: A1 and A2 done (section 5.1); G1 questions for the maintainer.
- 2026-11-22: G1: the maintainer decided points 7 to 26 one by one (section 5.1).
- 2026-11-22: the maintainer accepted the remaining recommendations of section 5.1. B1 done: [decision 0030](../decisions/0030-xyce-stimulus-and-port.md).
- 2026-11-22: B2 done: `xyce.lark` reads PULSE, SIN, EXP, SFFM, PAT and PWL (pairs or `FILE`, `TD=`, `R=`) in place of `src_function`; `model/_rules_xyce_sources.py` gathers them into a `SourceSpec` (`args` widened to `Value | Identifier`) and checks counts, PAT's DATA and PWL's pairs; spec entries `XY-SRC-002` to `XY-SRC-004` (documented until B5).
- 2026-11-22: B3 done: the P line (`port_source`): DC, then `port=` and `Z0=` in either order (`port=` required, an integer of 1 or more or a formula), then AC and the function; a line without `port=` refused with its own message. `PortSource`, a sibling of V and I (`port` and `Z0` in `params`), in `BodyItem`, `ELEMENT_NAMES`, `_SOURCES`, `_PRIMARY_PARAMS` (`dcv0`) and `remove_param`'s kinds; P is `supported` in `xyce-devices.json`; spec entry `XY-POR-001` (documented until B5).
- 2026-11-22: B4 done: explicit per-dialect tables, `_PARAM_SOURCES` in `model/_rules_sources.py` (ngspice V, LTspice V and I, xyce P) and `_NEEDS_VALUE` in `edit/_ops_sources.py` (LTspice I; none on ngspice or xyce), with `_NAMED_ARGS` (xyce: PWL `TD=`/`R=`, PAT `R=`) for `set_stimulus_arg`; on P, `set_ac` and `set_stimulus` insert after `port=` and `Z0=`, a new `Z0=` goes right after `port=`, `set_param` takes only `port` and `z0`, `remove_param` refuses `port`; a PWL `FILE` path is replaced without `=` and makes no reference. Golden-diff tests in `tests/edits/test_xyce_source_edits.py`.
- 2026-11-22: B5 done: `XY-SRC-002` to `XY-SRC-004` and `XY-POR-001` validated by `tests/solver/test_xyce_source_probes.py` and `test_xyce_port_probes.py` (`XY-SRC-001` updated); corpus families `sources_basic` (CRLF twin, `wave.csv`) and `sources_rejects`; the discrepancy rows of section 5.1, with the V/I row corrected for `port=` (observed: `port=` on V makes V a port behind its `Z0=`, 50 Ohm by default), the `.HB` row and the `.LIN` numbering row; README, `devices.md`, `elements.md` and the X-M8 checklist. Full run with ngspice, LTspice and Xyce required: 14638 passed, 2 skipped, coverage 99.29%; hooks pass.
