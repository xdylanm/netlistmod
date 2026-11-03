# M4 task list — statements and directives (ngspice)

> **Status:** COMPLETE (2026-10-31) — review approved after round 1 (section 10; R1 done, section 10.5). Implemented 2026-10-30 (section 9 is the report); section 2 records the decisions.
> **Part of:** [phase-1-plan.md](./phase-1-plan.md) (milestone M4). Governed by [architecture.md](../../../architecture.md) (§2 P2, P4, P5, P8, P13; §5.2; §6.3, §6.5; §7.1; §10; §11). Builds on M2 ([m2-tasks.md](./m2-tasks.md)) and M3 ([m3-tasks.md](./m3-tasks.md), [elements.md](../../elements.md), [decision 0004](../../../decisions/0004-element-and-value-grammar.md)). Citations use the manual edition in [references.md](../../../references.md).

## 1. Scope

Typed nodes with spans for the statements and directives that phase 1 needs. Today each of these is an `UnknownDirective`:

| Construct | Node | Manual |
|---|---|---|
| `.param` | `ParamStatement` | `[ngspice-manual] §2.11.1 ".param line"`, §2.11.2 "Brace expressions in circuit elements:" |
| `.model` | `ModelStatement` | §2.5 ".MODEL Device Models", §3.2.2 "Instance and model parameters" |
| `.subckt` … `.ends` | `SubcktDefinition` (contains its body) | §2.6.1 ".SUBCKT Line", §2.6.2 ".ENDS Line", §2.11.3 "Subcircuit parameters" |
| `.tran` | `TranDirective` | §11.3.10 ".TRAN: Transient Analysis" |
| `.ac` | `AcDirective` | §11.3.1 ".AC: Small-Signal AC Analysis" |
| `.dc` | `DcDirective` | §11.3.2 ".DC: DC Transfer Function" |
| `.op` | `OpDirective` | §11.3.5 ".OP: Operating Point Analysis" |
| `.options` (`.option`) | `OptionsDirective` | §11.1 "Simulator Variables (.options)" |
| `.temp` | `TempDirective` | §2.14 ".TEMP" |
| `.ic`, `.nodeset` | `IcDirective`, `NodesetDirective` | §11.2.2 ".IC: Set Initial Conditions", §11.2.1 ".NODESET: Specify Initial Node Voltage Guesses" |
| `.save` | `SaveDirective` | §11.6.1 ".SAVE: Name vector(s) to be saved in raw file" |
| `.meas` (`.measure`) | `MeasureDirective` | §11.4 "Measurements after AC, DC and Transient Analysis" |

Every other dot-command stays an `UnknownDirective`, preserved verbatim. That includes `.print`, `.plot`, `.probe`, `.four`, `.global`, `.func`, `.noise`, `.tf`, `.sens`, `.pz`, `.disto`, `.csparam` and `.opt`. Architecture §6.5 lists `.probe` beside `.save`; it stays unknown in M4 (decision 7).

**Exit (from the plan):** same criteria as M3. Each construct parses, malformed input is rejected with positions, and each construct has a spec entry and tests.

## 2. Decisions (maintainer, 2026-10-30)

The maintainer accepted every recommendation below as written (2026-10-30). "Recommendation" marks the accepted choice; an "Alternative" was considered and not chosen. Decision record 0005 (D1) records them. The probe evidence is in section 7.

1. **How a subcircuit definition is represented.**
   *Recommendation:* the grammar matches `.subckt` … `.ends` as one block, nesting by recursion (§2.6.1 allows nested definitions). The result is a container node, `SubcktDefinition(header, body, ends, span)`, where `body` holds the typed items inside it (elements, `.param`, `.model`, nested definitions, comments, blank lines).
   - Top-level item spans still tile the file; body items tile the text between the header and the `.ends` line.
   - An unterminated `.subckt` reports its opening line, like `.control` in M2.
   - A stray `.ends` is a `ParseError` (ngspice 47 also fails).
   *Alternative:* flat `SubcktStart`/`SubcktEnd` items with no nesting in the result. Rejected because the M5 topology signature needs the scope of each element (§7.7), and the grammar should own the block structure (P13).
2. **What may appear inside a subcircuit body.** §2.6.1: "Control lines may not appear within a subcircuit definition", but the manual does not define "control line". ngspice 47 accepts `.tran` inside a definition.
   *Recommendation (narrow):*
   - **Allowed:** elements, comments, blank lines, `.param`, `.model`, nested `.subckt`, `.include`/`.lib` (opaque), `.if` blocks, unknown dot-commands (preserved).
   - **Rejected with a positioned `ParseError`:** the M4 analysis, option and output directives (`.tran`, `.ac`, `.dc`, `.op`, `.options`, `.temp`, `.ic`, `.nodeset`, `.save`, `.meas`), `.control` blocks, `.title` and `.end`.
   - The difference from ngspice goes into `discrepancies.md`.
3. **The `.subckt` line.**
   - **Ports:** at least one; `0` is rejected (§2.6.1, "cannot be zero"; ngspice 47 accepts it, so this is a discrepancy).
   - **Default parameters:** `name=value` after the ports, as in §2.11.3. A value is a number, a brace formula or a double-quoted string, as on X lines.
   - **`params:`** is rejected, as on X lines in M3.
   - **`.ends`:** the name is optional. A name that does not match is accepted ("is not checked", §2.6.2), and the node records it. M5 may report a mismatch as a diagnostic.
4. **Bare expressions in `.param`.** §2.11.1 says expressions "should be put within braces … or … single quotes". It also says they are not always needed "when spaces are used sparingly", and ngspice 47 accepts `.param c = a+1k` and `.param c = a` but fails on `.param c = a + 1k`.
   *Recommendation:* a value is a number, a brace formula, a single-quoted formula or a double-quoted string. A bare expression, including a lone identifier (`.param c = a`), is a `ParseError` whose message suggests braces. This matches architecture §6.3 rule 10, which also bars bare formulas on element lines.
   *Alternative:* accept one blank-free bare token as a formula with no delimiter. Choose this if your KiCad exports write bare expressions in `.param`.
5. **`.model`.** The form is `.model name type params`. Parameters may be wrapped in parentheses (§2.5 general form) or written without them (§3.2.2 example), separated by blanks or commas, and continued across lines (all accepted by ngspice 47).
   - **Type:** any name, recorded as text. Table 2.3 lists 17 types, but XSPICE code models use other type names, and the library does not validate models (non-goal 8). M6 needs the type text for its same-type check on `set_model` (§7.2).
   - **Parameter values:** number, brace formula or quoted formula. *Settle (T3):* parameters without a value.
6. **How deeply directives are typed.** Each directive gets the fields that M5 lookups and M6 edits need, each with a span:
   - `.tran tstep tstop [tstart [tmax]] [uic]`
   - `.ac dec|oct|lin n fstart fstop`
   - `.dc src start stop incr [src2 start2 stop2 incr2]`
   - `.op` (no arguments)
   - `.options` as a list of `name` or `name=value` items
   - `.temp value`
   - `.ic` and `.nodeset` as lists of `v(node)=value` items, plus `.nodeset all=value`
   - `.save` as a list of output vectors. Each vector is kept as text with its span; the forms are `name`, `v(n)`, `v(n1,n2)`, `i(src)`, `src#branch`, `@dev[param]` and `all`.
   - **`.meas`/`.measure`: shallow typing.** Only the analysis (`dc`, `ac`, `tran`, `sp`) and the result name are typed; the rest of the line is preserved text with a span. The measurement language has several general forms and embedded `par('…')` expressions (§11.4); a full grammar would be larger than the rest of M4. It can be extended later without changing the node's existing fields.
   Argument values are numbers or formulas; RKM does not apply (it is limited to R and C values, decision 0004).
7. **Aliases and keyword spelling.** `.options` and `.option` (both used throughout the manual) are typed; `.opt` is not in the manual and stays an `UnknownDirective` (ngspice 47 accepts it). `.meas` and `.measure` are both typed. Keywords are case-insensitive. `.probe` stays unknown in M4 (§11.6.5 has its own sublanguage), and architecture §6.5 is amended to say so.
8. **Corpus provenance:** new families `statements_basic` and `statements_rejects`, authored in this repository. Author `xdylanm`, MIT (confirmed by the maintainer, 2026-10-30).

Smaller choices are marked "settle" in the tasks: pick the narrowest reading, cite the manual, and record the choice in the spec entry and the report.

## 3. Design

### 3.1 Nodes (proposed; D2 finalizes them in a design note)

Frozen, slotted dataclasses, exported like the M3 nodes. Every sub-span covers exactly its text, never a separator (as in [elements.md](../../elements.md) §4). These are what M6 replaces.

- **Values.** `ParamAssignment` and `Value` from M3 are reused. `.param` and `.subckt` defaults also accept a double-quoted string, as `Formula(delimiter='"')` already allows on X lines.
- `Directive`, a keyword-only base: `keyword` (as written, e.g. `.TRAN`), `keyword_span`, `span`, `trailing_comments`.
- `ParamStatement(assignments: tuple[ParamAssignment, ...])`.
- `ModelStatement(name, name_span, model_type, model_type_span, params: tuple[ParamAssignment, ...], parenthesized: bool)`.
- `SubcktDefinition(name, name_span, ports: tuple[Node, ...], params: tuple[ParamAssignment, ...], body: tuple[BodyItem, ...], ends: EndsLine, header_span, span)` with `EndsLine(name: str | None, name_span: Span | None, span)`. `BodyItem` is the subset of `TopLevelItem` allowed by decision 2, plus `SubcktDefinition`.
- `TranDirective(tstep, tstop, tstart, tmax, uic: Flag | None)`; `AcDirective(variation, variation_span, points, fstart, fstop)`; `DcDirective(sweeps: tuple[DcSweep, ...])` with `DcSweep(source, source_span, start, stop, increment)`; `OpDirective()`; `TempDirective(value)`.
- `OptionsDirective(options: tuple[OptionItem, ...])` with `OptionItem(name, name_span, value: Value | None, span)`.
- `IcDirective` / `NodesetDirective(conditions: tuple[NodeCondition, ...])` with `NodeCondition(node: Node | None, value, span)`; `node is None` means `all=` (`.nodeset` only).
- `SaveDirective(vectors: tuple[OutputVector, ...])` with `OutputVector(text, span)`.
- `MeasureDirective(analysis, analysis_span, result, result_span, body_text, body_span)`.

### 3.2 Grammar approach

- Statement and directive rules go in `core.lark` where the form is common SPICE, and are composed into `ngspice.lark` as in M2/M3, each with a `// spec:` marker. Keywords are string terminals at `DOT_NAME`'s priority, so Lark re-types an exact match (§6.3 rule 12).
- **Fields reuse the M3 separator design** (decision 0004 items 4–6): every field rule starts with its own `SEP`/`CSEP`/`BS_CONT`, `=` is the `EQ` token, and lists are right-recursive where a field is classified by what follows it. No new lookaround terminal: the pinned list in `tests/architecture/test_contracts.py` must not grow without the maintainer's approval (M2 finding 6.4).
- **New tokens:**
  - parentheses for `.model` and for the `v(…)`/`i(…)` forms in `.ic`, `.nodeset` and `.save`. They are valid only in those rules; outside formulas, element lines keep rejecting them (decision 0004 item 4).
  - `@dev[param]` and `name#branch` for `.save`.
- `.subckt` body rules: a `body_line` alternative set that excludes the rejected directives of decision 2. The rejected directives must still be *recognised* inside a body, so the error is positioned and clear: it should say that the directive is not allowed in a subcircuit, not report an unexpected token. They are matched by a grammar rule whose transformer method raises, like the M3 `params:` rule.
- `.ends` joins `.endc`, `.endif`, `.else` and `.elseif` in the stray-terminator exclusion of `DOT_NAME` (`ngspice.lark` `%override`). The exclusion already exists, so the pinned list does not grow. The loader's `_BLOCKS` table gains `.subckt` for the unterminated-block error.
- **No performance bound** (decision 0004 item 10); the parse stays two-pass.

## 4. Tasks

Every task ends with `ruff check`, `ruff format --check`, `mypy --strict`, and `pytest` (coverage gate) green, run as `uv run --env-file .env python -m <tool>` (AGENTS.md; on Smart App Control failures follow docs/testing.md). Syntax stays in the grammar (P13). Where a task says "settle", state the choice with its manual citation (or `observed` with probe evidence) in the spec entry and the report; default to the narrowest reading.

### Decisions and design

[x] **D1 — Decision record 0005: statement and directive grammar.**
Record the section 2 outcomes, the subcircuit block and body rules, the new tokens (parentheses, `@`, `#`, brackets) and where they are valid, and the directive typing depth. Amend architecture §5.2 (`SubcktDefinition` contains its body; the directive node family), §6.5 (typed directive list; `.probe` stays unknown) and §6.3 rule 9 if the node-name class changes. Status `proposed` until the maintainer accepts it.
*Done when:* the record and the architecture agree with the shipped grammar.

[x] **D2 — Design note `docs/design/m4-statements.md`.**
Final node shapes (3.1), the spec IDs (T9), a manual-form → rule → node-field table per construct, and what each span and sub-span covers. Include body tiling, and say which sub-spans M6 replaces: `.param` values, `.model` parameter values, directive arguments, and whole directive lines for replace and remove (§7.2). Keep it short, as with `m3-elements.md`.
*Done when:* the maintainer has reviewed it (can run in parallel with S1).

[x] **S1 — Spike: subcircuit blocks and rejected body directives.**
Questions: (a) can `.subckt` … `.ends` nest by recursion under strict LALR, with element and statement lines shared between the top level and the body, without duplicating every line rule? (b) Can the decision 2 directives be recognised inside a body and rejected with a clear, positioned error? (c) Does the unterminated-block error find the innermost open `.subckt`? (d) Spans and tiling of body items, including continued lines and a body that is only comments.
Acceptance: one design that builds under `strict=True` and passes the section 6 subcircuit rows. Report with evidence if none does.

### Implementation

[x] **T1 — `.param`.**
One or more `name=value` assignments; values per decision 4. Settle:
- name characters (§2.11.1 allows `! # $ % [ ] _` after the first letter; `$` also starts an end-of-line comment, §2.4.4; default: `$` ends the name);
- the reserved names `time`, `temper` and `hertz` (default: `ParseError`);
- `.param` with no assignment (default: `ParseError`);
- a repeated name on one line (default: accepted; M5 reports duplicates).

[x] **T2 — `.subckt` / `.ends`** (after S1).
Header (name, ports, defaults), body (decision 2), `.ends` with an optional name, and nesting. Settle: duplicate port names (default: accepted as syntax; M5 diagnostic); a definition with an empty body (default: accepted).

[x] **T3 — `.model`.**
Name, type and parameters, with and without parentheses, commas, and continuation inside the parentheses. Settle: an empty parameter list `D()`; unbalanced parentheses (error at the opener); a parameter without a value; a repeated parameter.

[x] **T4 — Analyses: `.tran`, `.ac`, `.dc`, `.op`.**
Per decision 6. Settle:
- for `.tran`, `uic` without `tstart`/`tmax`, and fields past `tmax`;
- the `.ac` variation keyword's case;
- for `.dc`, the sweep source: `TEMP`, a resistor, or any name (default: any name; M5 resolves it);
- `.op` with arguments (default: `ParseError`).

[x] **T5 — `.options`, `.temp`, `.ic`, `.nodeset`.**
Settle:
- for `.options`, option names (not checked, non-goal 8) and an empty `.options`;
- for `.temp`, more than one value;
- in `.ic`, `all=` (not in §11.2.2: rejected);
- `v( node )` with blanks inside the parentheses;
- a node name in `v(…)`, which follows the M3 name class.

[x] **T6 — `.save` and `.meas`.**
The vector forms of decision 6, and shallow `.meas`/`.measure`. Settle: `.save` with no vectors; a `.meas` analysis outside `dc|ac|tran|sp`; a `.meas` with only the analysis and result name.

[x] **T7 — Transformer, loader and errors.**
- Transformer methods per new rule, dispatching on node type (§6.3 rule 11).
- `_TERMINAL_NAMES` for every new terminal, and `.subckt` in `_BLOCKS`.
- The "not allowed inside a subcircuit" error.
- Update every M2/M3 test that expected one of these keywords to be an `UnknownDirective`.
- Update `docs/usage/structural-parse.md`, where the node list changes.
*Done when:* every error branch is covered.

### Validation, specs and tests

[x] **T8 — Solver probes (T8 tier).**
In `tests/solver/`:
- record the section 7 probes as discrepancy evidence, each paired with what the library does;
- check that every file in the new accept corpus runs in ngspice 47 without error;
- check that a subcircuit divider with an instance override (`X1 in out div r2=3k`) gives the closed-form result;
- check that a `.param` value referenced from an element changes the result as expected (a first M7-style check).
Update `discrepancies.md` and set `validated_on` in the spec entries.

[x] **T9 — Spec entries.**
One entry per construct, in the M2/M3 format:
- `NG-PRM-001` `.param`; `NG-MOD-001` `.model`; `NG-SBD-001` `.subckt`/`.ends` and body rules;
- `NG-TRN-001`, `NG-ACA-001`, `NG-DCA-001`, `NG-OPP-001` (`.op`);
- `NG-OPT-001` `.options`; `NG-TMP-001` `.temp`; `NG-ICN-001` `.ic`/`.nodeset`; `NG-SAV-001` `.save`; `NG-MEA-001` `.meas`.
Update `NG-DIR-001` (unknown dot-commands: list what is now typed; `.ends` added to the stray terminators).
*Done when:* the spec checker passes and every new rule and terminal carries a marker.

[x] **T10 — Tests and corpus.**
- *Corpus:* `statements_basic/` with small netlists covering each construct (including a nested subcircuit with a default and an override, a parenthesized multi-line `.model`, LF and CRLF, continuations and comments), and `statements_rejects/` with one file per reject in section 6 and a manifest giving the expected line and column. Each family has a manifest (origin: authored in this repository; author `xdylanm`, MIT, confirmed by the maintainer on 2026-10-30).
- *T1:* each sub-span slices back to its text.
- *T2:* one accept and one reject test per spec entry.
- *T3:* round-trip and tiling over all corpora, including body tiling.
- *T5:* extend the M3 Hypothesis oracle to generate `.param`, `.model`, typed directives and (nested) subcircuit blocks with element bodies, comparing kinds, names and nesting against the generator.
*Done when:* all pass with the 90% coverage gate.

[x] **T11 — Docs.**
`CHANGELOG.md`, `README.md` status, `docs/testing.md` (new corpora), the usage doc with an executed example, and the phase plan's M4 heading. Public names get docstrings.

[x] **T12 — Exit.**
Full check set, a fresh-clone test, and the solver tests. Report what changed, every "settle" decision with its citation, deviations from this list, and limitations. Set this document's status to `READY FOR REVIEW`. **Do not archive.**

## 5. Dependencies between tasks

```
Section 2 decisions → D1
S1 → D1, D2 → T2
D2 → T1, T3, T4, T5, T6 (independent of each other)
T1–T6 → T7 → T9 → T10
T8 needs T7; its probes can start earlier
T10 → T11 → T12
```

## 6. Accept and reject table (minimum; extend in T1–T6)

| Input (inside a valid netlist) | Result |
|---|---|
| `.param pippo=5`; `.param po=6 pp=7.8`; `.param p={pp}`; `.param pop='pp+p'`; `.PARAM s="txt"` | accept |
| `.param c = a+1k`; `.param c = a`; `.param a = 123 * 3` | reject: bare expression (decision 4), positioned at the value |
| `.param`; `.param x=`; `.param time=1` | reject with position |
| `.model MOD1 npn (bf=50 is=1e-13 vbf=50)`; `.MODEL ind1 L tc1=0.001`; `.model dm D is=1e-14, n=1.5` | accept |
| `.model dm D(is=1e-14` / `+ n=1.5)` (continued) | accept; spans cover both lines |
| `.model dm D(is=1e-14`; `.model dm`; `.model` | reject with position |
| `.subckt div a b` / `R1 a b 1k` / `.ends` | accept |
| `.subckt div a b r2=1k` … `.ends div`; `.ends other` (mismatched name) | accept; `ends.name` recorded |
| nested `.subckt outer a b` / `.subckt inner p q` / … / `.ends inner` / `.ends outer` | accept |
| `.subckt div a b` / `.model dm D` / `.param k=2` / `* c` / `.include x.inc` / `.ends` | accept |
| `.subckt div a b` / `.tran 1u 10u` / `.ends`; same with `.control` … `.endc` | reject at the directive (decision 2) |
| `.subckt div a 0`; `.subckt div`; `.subckt div a b params: r=1` | reject with position |
| `.subckt div a b` without `.ends` | reject, reported at the `.subckt` line |
| `.ends` at top level | reject with position |
| `.tran 1ns 100ns`; `.tran 1ns 1000ns 500ns`; `.tran 1n 1u 0 10p uic` | accept |
| `.ac dec 10 1 10K`; `.ac lin 100 1 100HZ`; `.dc VIN 0.25 5.0 0.25`; `.dc VDS 0 10 .5 VGS 0 5 1`; `.dc TEMP -15 75 5`; `.op` | accept |
| `.tran 1ns`; `.ac dec 10 1`; `.ac log 10 1 1k`; `.dc VIN 0 5`; `.op 1` | reject with position |
| `.options reltol=.005 trtol=8`; `.option noacct`; `.temp 27` | accept |
| `.ic v(11)=5 v(4)=-5 v(2)=2.2`; `.nodeset v(12)=4.5`; `.nodeset all=1.5` | accept |
| `.ic all=1`; `.ic v(1)`; `.ic v(1=5` | reject with position |
| `.save i(vin) node1 v(node2)`; `.save @m1[id] vsource#branch`; `.save all @m2[vdsat]` | accept |
| `.measure tran tdiff TRIG v(1) VAL=0.5 RISE=1 TARG v(1) VAL=0.5 RISE=2`; `.meas ac vmax MAX vdb(out)` | accept (shallow) |
| `.meas foo x MAX v(1)`; `.meas tran` | reject with position |
| `.opt gmin=1e-12`; `.print tran v(1)`; `.probe v(1)` | `UnknownDirective` (unchanged) |
| any of the above continued with `+` or `\\`, with `;`/`$`/`//` comments | accept; spans cover every physical line |

## 7. Probe facts gathered while planning (ngspice 47, 2026-10-30)

Re-recorded as solver tests in T8. Divider `V1 in 0 DC 3` with two 1k resistors unless noted; the result is `v(out)` from `.op`.

| Input | ngspice 47 | Library (recommended) |
|---|---|---|
| `.tran 1u 10u` inside `.subckt` | accepted (1.5 V) | reject (decision 2): discrepancy |
| `.option reltol=1e-3`, `.opt gmin=1e-12` | both accepted | `.option` typed; `.opt` unknown |
| `.param c = a+1k` (a = 1k) | accepted (2.0 V: c = 2k) | reject (decision 4): discrepancy |
| `.param c = a` | accepted (1.5 V) | reject (decision 4): discrepancy |
| `.param c = a + 1k` | fatal error, exit 1 | reject |
| `.ends other` closing `.subckt div` | accepted | accept (§2.6.2) |
| `.ends` at top level | error ("Mismatch of .subckt ... .ends") | reject |
| `.subckt div a 0` | accepted | reject (§2.6.1): discrepancy |
| `.model dm D is=1e-14, n=1.5` (no parentheses, comma) | accepted | accept |
| `.model dm D(is=1e-14` / `+ n=1.5)` | accepted (same result) | accept |
| `.model dm D` inside a subcircuit, used outside it | error: model not found | accept as syntax; M5 scoping (§2.6.1, models are local) |
| nested `.subckt inner` inside `.subckt outer` | accepted (1.5 V) | accept |
| `X1 in out div r2=3k` with `.subckt div a b r2=1k` | accepted (2.25 V: override applied) | accept |

## 8. Out of scope for M4

`Document`, `Lines`, indexes, symbol tables, scoping, the topology signature, reference resolution and the diagnostics API (M5); edits and the directive matching and upsert rules (M6, §21); a full `.meas` grammar, `.probe`, `.print`/`.plot`, `.func`, `.global` and the other dot-commands listed in section 1; `.lib name` … `.endl` blocks (still not implemented, decision 0002); the LTspice grammar (M8); expression evaluation (non-goal 6) and model-parameter validation (non-goal 8).

## 9. Report (2026-10-30)

### What changed

- **Grammar** (`core.lark`; `ngspice.lark` imports it by name): `line` is split into
  `body_line` (allowed in a subcircuit body and at the top level) and `top_statement`.
  New rules for `.param`, `.model`, `.subckt` … `.ends` (one recursive block), the ten
  directives, and `not_in_subckt`, which recognises the top-level-only statements in a body
  so that the transformer rejects them at their keyword. `.ends` joins the stray terminators
  in the `DOT_NAME` override. Fields reuse the M3 gap design (`x_name`, `value`, `param`,
  `x_param` are shared with element lines). Strict build is green; **no new lookaround
  terminal**, so the pinned list is unchanged.
- **Model:** `ParamStatement`, `ModelStatement`, `SubcktDefinition`, `EndsLine`, the
  `Directive` base and its ten subclasses with `DcSweep`, `OptionItem`, `NodeCondition`,
  `OutputVector`; `Identifier` in `values.py`; `BodyItem` and the extended `TopLevelItem`.
  All exported (`BodyItem` from `netlistmod.model`, like `TopLevelItem`). Shapes:
  [statements.md](../../statements.md).
- **Loader:** an unterminated `.subckt` is found on the parser stack (the `SUBCKT_KW` token
  or a reduced `subckt_header`) and reported at its innermost open line; an unclosed `(` or
  `v(` is reported at the opener when the line ends; terminal names for every new terminal.
- **Records:** decision [0005](../../../decisions/0005-statement-and-directive-grammar.md)
  (accepted 2026-10-30); architecture §5.2 and §6.5 amended; 12 new spec entries, `NG-STR-001`,
  `NG-OPA-001` and `NG-DIR-001` updated; `discrepancies.md`; `provenance.md`.
- **Tests:** `test_statements.py` (173 cases), a second Hypothesis generator in
  `test_element_oracle.py` (statements, directives, nested subcircuits with element bodies),
  `roundtrip/test_ngspice_statements.py` (round-trip, item and body tiling and sub-spans over
  every accept corpus, the reject manifest), `solver/test_ngspice_solver_statements.py`
  (section 7 probes, settle probes, closed-form divider with override, `.param` reaching an
  element, every `statements_basic` file runs). Corpora `statements_basic` (4 files: LF, CRLF,
  mixed, no final newline) and `statements_rejects` (26). M2/M3 tests that used `.options a`
  or `.param n1=…` as unknown directives now use `.foo`; the `//` solver probe checks the
  typed `.param`. The `params:` message now covers `.subckt` too.
- **Checks:** ruff, ruff format, mypy `--strict`, pre-commit hooks and pytest (823 passed,
  2 POSIX-only skips, coverage 98%, ngspice 47 required and found) are green.

### Settle decisions (each also in its spec entry)

| Item | Choice | Basis |
|---|---|---|
| `.param` name characters (T1) | a letter, then letters, digits and `! # % [ ] _`; `$` ends the name (comment) | §2.11.1, §2.4.4 |
| `time`, `temper`, `hertz` (T1) | `ParseError` at the name | §2.11.1 |
| Empty `.param`, `name=` (T1) | rejected | §2.11.1 general form |
| Repeated name on one line (T1) | accepted (M5 reports duplicates) | task default |
| `.param` separators (T1) | blanks and continuations; no comma | §2.11.1 "a separating space" |
| Duplicate ports, empty body (T2) | accepted | task default |
| `D()` (T3) | accepted, `parenthesized=True`, no params | §2.5 (unspecified parameters take defaults); `observed` ngspice 47 |
| Unbalanced `(` (T3) | `ParseError` at the opener | task default |
| Parameter without value (T3) | rejected | §2.5 `pname=pval` |
| Repeated model parameter (T3) | accepted | syntax only (non-goal 8) |
| `uic` without `tstart`/`tmax` (T4) | accepted after `tstop`, `tstart` or `tmax` | §11.3.10 `<tstart <tmax>> <uic>` |
| Fields past `tmax` or after `uic` (T4) | rejected (ngspice 47 also fails) | §11.3.10 |
| `.ac` variation case (T4) | case-insensitive, recorded as written | keywords are case-insensitive (decision 7) |
| `.dc` source (T4) | any name; M5 resolves | §11.3.2 (source, resistor or TEMP) |
| `.op` with arguments (T4) | rejected | §11.3.5 |
| Option names, empty `.options` (T5) | not checked; empty rejected | non-goal 8; §11.1 general form |
| `.temp` with more than one value (T5) | rejected | §2.14 `.temp value` |
| `.ic all=` (T5) | rejected | §11.2.2 has no `all=` |
| `v( node )` (T5) | blanks inside the parentheses accepted (ignored like other inline blanks); `v (` rejected | `observed` ngspice 47 reads it the same |
| Node name in `v(…)` (T5) | the M3 name class | §6.3 rule 9 |
| `.save` with no vectors (T6) | rejected | §11.6.1 general form |
| `.meas` analysis other than `dc`, `ac`, `tran`, `sp` (T6) | rejected | §11.4.3 |
| `.meas` with only analysis and result (T6) | rejected | §11.4 (a measurement follows the result) |
| `.nodeset` mixing `v()` items and `all=` | rejected | §11.2.1 gives them as separate forms |

### Deviations from this task list

- **`.options` values may be names** (`method=gear`, §11.1.4), stored as the new
  `Identifier`; decision 6 named numbers and formulas only, which would reject a documented
  form. Recorded in decision 0005 item 6; confirmed by the maintainer (2026-10-30).
- **`.param` names use their own terminal** (`PARAM_NAME`), narrower than the M3 name class
  (letter first, §2.11.1); `.subckt` defaults keep `WORD`, as on X lines, because ports and
  default names share one lexer state.
- **Node shapes** (D2): `DcSweep.span`, `EndsLine.trailing_comments` and the keyword fields
  on `SubcktDefinition` were added; `Identifier` is new.
- **Bare-expression detection** also covers a value glued to a number (`1k+a`) and a field
  after a value (`123 * 3`), so all three section 6 rows are positioned at the value.
- Fresh clone (2026-10-30): `git clone`, `uv sync`, then pytest with
  `--require-solver ngspice`: 823 passed, 2 POSIX-only skips, coverage 98%.

### Limitations

- A `.meas` body is not parsed.
- A keyword prefix (`.ac decade …`, `.tran 1n 1u uicx`) fails at the first character after
  the keyword rather than at the word, because argument keywords are strings without a
  competing name terminal in their state.
- Error tokens reported from the contextual lexer's fallback can have odd names in
  `expected` (for example `title text`), but positions are exact.
- Model scoping (a `.model` inside a subcircuit is local, §2.6.1), `.ends` name mismatches
  and duplicate names are M5 diagnostics; the parser accepts them as syntax.

## 10. Review round 1 (2026-10-31)

### 10.1 Outcome

Accepted except for one finding. The rest of M4 holds up on review:
- **Checks:** 823 passed, 2 POSIX-only skips, 98% coverage, ruff and mypy `--strict` clean, ngspice required and found.
- **Grammar:** no new lookaround terminal; no text scanning in the transformer (P13).
- **Keywords:** keyword prefixes stay unknown or opaque as intended (`.opt`, `.params`, `.models`, `.transient`, `.icx`, `.measurement`, `.endsx`, and `.include` vs `.ic`).
- **Subcircuits:** the body rules match decision 2 (`.if` and `.include` allowed; `.tran`, `.control` and `.end` rejected at their keyword), and KiCad `/net` names work in `.subckt`, `.ic` and `.save`.
- **Records:** decision 0005, the architecture amendments, the design note and the spec entries agree with the shipped grammar.

### 10.2 Required change

[x] **R1 — `.save` must accept the documented output-vector forms.**
`OUTPUT_VECTOR` accepts only `v(n)`, `v(n1,n2)` (no blank), `i(src)`, `@dev[param]` and a plain name. The manual documents more:
- §11.6.1 says "the standard vector names are accepted" and describes `.save vm(out)` (only `v(out)` is stored).
- §11.6.2 "`.print` Lines" defines the standard forms: `V(N1<,N2>)`, written in its examples as `v(23, 17)` with a blank after the comma, and the AC forms `VR`, `VI`, `VM`, `VP`, `VDB` in place of `V`. It also says the corresponding replacements for `I` are "not yet implemented".

Today `.save vm(out)`, `.save vdb(out)` and `.save v(a, b)` are `ParseError`s. ngspice 47 accepts all three (probe below), so the grammar rejects documented syntax (P5, P8).

Change:
1. Accept `v`, `vr`, `vi`, `vm`, `vp` and `vdb` (case-insensitive) with one node or two nodes, and keep `i(src)`. Settle `ir`/`ii`/`im`/`ip`/`idb`: default reject, because §11.6.2 says they are not implemented. Cite the reading in `NG-SAV-001`.
2. Treat blanks inside the parentheses and around the comma consistently. Accept `v( a )`, `v(a, b)` and `v(a ,b)` alike, as `.ic`/`.nodeset` already do for `v( node )` (T5 settle). If the vector stays one token, its text and span still cover the whole vector including the blanks. Otherwise, give `OutputVector` the parts M5 will need (the function and the node names with spans), and record the shape in `m4-statements.md`.
3. Record in `discrepancies.md` that ngspice 47 stores `.save v(in, out)` as the two vectors `v(in)` and `v(out)`, not as a difference. It also stores `vm(out)` and `vdb(out)` as `v(out)` (raw-file variable lists, probe below). This is an observation; the library only records the text.
4. Tests:
   - accept and reject cases in `test_statements.py`;
   - a `statements_basic` line using `vm(...)` and `v(a, b)`, with updated manifest hashes;
   - a solver probe asserting the raw-file variables for each form;
   - the `.save` limitation removed from section 9.
   No new lookaround terminal: the pinned list stays unchanged.

*Done when:* the forms above parse with exact spans, the rejected `i` variants fail with a positioned error, and the full check set is green.

Probe (ngspice 47, 2026-10-31; `V1 in 0 DC 1 AC 1`, `R1 in out 1k`, `C1 out 0 1u`, `.ac dec 2 1 1k`, one `.save` line; variables read from the raw file):

| `.save` argument | exit | raw-file variables |
|---|---|---|
| `vm(out)` | 0 | `v(out)` |
| `vdb(out)` | 0 | `v(out)` |
| `v(in, out)` | 0 | `v(in)`, `v(out)` |
| `v( out )` | 0 | `v(out)` |
| `i(V1)` | 0 | `i(v1)` |

### 10.3 Noted, no change required

- **Error messages** for a missing argument (`.tran 1ns`, `.model dm`) list separators as the expected tokens rather than naming the missing field. Positions are exact and this matches the M3 messages. Revisit with the M9 error reference if it reads poorly.
- **The keyword-prefix error position** (`.ac decade …` fails at the `a` after `dec`) is accepted as listed in section 9.
- **`.options a="x"`** (a string value) is rejected. §11.1 documents no string-valued option, so no change is needed.

### 10.4 Exit for this round

Run the full check set and the solver tests, append a short report under this section, and set the status to `READY FOR REVIEW`. **Do not archive.**

### 10.5 Report for round 1 (2026-10-31)

**R1 is done.** `.save` now accepts the standard output-vector forms of §11.6.2.
- **Grammar:** `voltage_vector` (`v`, `vr`, `vi`, `vm`, `vp`, `vdb`, case-insensitive, one or
  two nodes) and `current_vector` (`i(src)`). The function and `(` are one token at
  priority 3, above the plain-name `OUTPUT_VECTOR` (2), which now holds only `@dev[param]`
  and plain names. Blanks inside the parentheses are ignored; blanks around the comma belong
  to `CSEP`, so `v( a )`, `v(a, b)` and `v(a ,b)` parse alike.
- **Rejected forms:** `ir`, `ii`, `im`, `ip` and `idb` are recognised and rejected at the
  function (settle: §11.6.2 says they are not yet implemented). `i(a, b)` is rejected at its
  second name, and an unclosed `v(` is reported at the opener.
- **Node shape:** `OutputVector` gains `function`, `nodes: tuple[Node, ...]` and
  `source: ElementReference | None`, each name with its span; `text` is still the slice of
  the whole vector, blanks included. Recorded in `m4-statements.md`.
- **Records:** decision 0005 has a dated amendment, and `NG-SAV-001` adds the §11.6.2 citation
  and the new rules. `discrepancies.md` records what ngspice 47 stores: `v(in, out)` as
  `v(in)` and `v(out)`, and `vm`/`vdb` as `v`. The section 9 `.save` limitation is removed.
- **Tests:** new accept, parts and reject cases in `test_statements.py`. The `statements_basic`
  line `.save vm(out) vdb(out) v(in, out) v( in )` was added and the manifest hash updated. A
  solver probe (`run_ngspice` gained an optional `raw=` path) asserts the raw-file variables
  for each form in the review table. Node and source sub-spans are checked over the corpora.
- **Pinned list:** no new lookaround terminal; the pinned list is unchanged.
- **Checks:** ruff, ruff format, mypy `--strict`, pre-commit hooks and pytest
  (`--require-solver ngspice`): 853 passed, 2 POSIX-only skips, 98% coverage.
