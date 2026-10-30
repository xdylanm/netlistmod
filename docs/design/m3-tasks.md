# M3 task list — elements and values (ngspice)

> **Status:** READY — approved by the maintainer (2026-10-30); section 2 records the decisions.
> **Part of:** [phase-1-plan.md](./phase-1-plan.md) (milestone M3). Governed by [architecture.md](../architecture.md) (§2 P2, P4, P5, P8, P13; §5.2–5.3; §6.3–6.5, §6.7; §10; §11). Builds on the M2 grammar core ([archive/m2-tasks.md](./archive/m2-tasks.md), [archive/m2-review2-tasks.md](./archive/m2-review2-tasks.md)). Citations use the manual edition in [references.md](../references.md).

## 1. Scope

Parse the phase 1 element lines of the ngspice dialect into typed, immutable nodes with spans:

| Letter | Node | Manual |
|---|---|---|
| R | `Resistor` | `[ngspice-manual] §3.3.1 "Resistors"`, §3.3.2 "Semiconductor Resistors", §3.3.4 "Resistors, dependent on expressions (behavioral resistor)" |
| C | `Capacitor` | §3.3.6 "Capacitors", §3.3.7 "Semiconductor Capacitors", §3.3.9 "Capacitors, dependent on expressions (behavioral capacitor)" |
| L | `Inductor` | §3.3.10 "Inductors", §3.3.13 "Inductors, dependent on expressions (behavioral inductor)" |
| K | `MutualCoupling` | §3.3.12 "Coupled (Mutual) Inductors" |
| V, I | `VoltageSource`, `CurrentSource` | §4.1 "Independent Sources for Voltage or Current" |
| D | `Diode` | §7.1 "Instance lines and .model lines", §7.2 "Junction Diodes" |
| X | `SubcktInstance` | §2.6.3 "Subcircuit Calls", §2.11.3 "Subcircuit parameters" |

Cross-cutting, also in M3:

- **Fields and nodes:** field separators and node-name characters (§2.1.3.1 "Lines", §2.1.3.4 "Node names"). The ground alias and net identity are M5 (`names.md`).
- **Values:** `NumericValue` (numbers, scale factors, trailing letters; §2.1.3.2 "Numbers", §2.1.3.3 "Letters following a number"), `Formula` (brace and quoted expressions; §2.11.2 "Brace expressions in circuit elements"), `ModelReference`, instance parameters `name=value` (§3.2.2 "Instance and model parameters"), and the diode's `off` flag.
- **RKM notation** behind a parser option (architecture §19 decision 8; §12.11.6 "LTSPICE Compatibility mode").
- **Sources:** a plain value and the `DC` and `AC` keywords (phase 1, maintainer decision). Stimulus functions (`PULSE`, `SIN`, `EXP`, `PWL`, `SFFM`, `AM`, `TRNOISE`, `TRRANDOM`, `EXTERNAL`, `PORT`) and `DISTOF1`/`DISTOF2` raise `UnsupportedConstruct` (P5).
- Element lines take part in continuation (`+` and `\\`), trailing comments and span tiling exactly like M2's continuable statements.
- The device matrix moves R, C, L, V, I, D, X, K to `supported`. The M2 `UnsupportedConstruct` path stays for every phase 2 letter.

**Exit (from the plan):** every phase 1 element parses, malformed input is rejected with positions (T6 tier), and each construct has a spec entry and tests. The three `kicad_basic` fixtures parse.

## 2. Decisions (maintainer, 2026-10-30)

These resolve architecture §21 items and conflicts between the architecture and the manual. Decision record 0004 (task D1) records them.

1. **RKM option: interface and default** (§21 "Interaction of the RKM mode option..."; architecture decision 8).
   *Facts:* the manual defines RKM (`2k7`, `4R7`, `R47`) **only** in LT compatibility mode and only for R and C (§2.1.3.3, §12.11.6). Without that mode, ngspice 47 silently reads `2k7` as `2k`: the digits after the scale factor are dropped, with no warning (probe in section 7). The `kicad_basic` fixtures use `1k0`, which only gives the right result because the dropped digit is `0`.
   *Decision:* a keyword-only parser argument `rkm: bool = False` on `parse()`. Off (strict, the manual's default mode): digits after a scale or RKM letter are a `ParseError` at the value, with a message that names the option. On: RKM forms are accepted for R and C values only, per decision 2, and the `NumericValue` records `notation="rkm"`. The diagnostic `DIALECT_GATED_SYNTAX` is emitted once the diagnostics API exists (M5). Standard notation parses the same in both modes (this is the "automatic fallback" in architecture decision 8). The `kicad_basic` tests pass `rkm=True`.
2. **RKM follows IEC 60062** ([RKM code](https://en.wikipedia.org/wiki/RKM_code); architecture §6.4 already says `M` is mega for R and milli for C). With `rkm=True`, an RKM value is digits, one code letter in place of the decimal point, and optional digits (`4K7`, `470R`, `R47`, `1M0`, `15M0`, `4p7`):
   - **R:** `L` (milli), `R` (unit), `K`/`k` (kilo), `M` (mega), `G` (giga), `T` (tera).
   - **C:** `p`, `n`, `u`/`µ`, `m` (milli, also as `M`), `F` (unit).
   - `E` is **not** an RKM letter: `4E7` is standard exponent notation in both modes (ngspice 47 reads it as 4×10⁷), so standard notation wins.
   - A value with no digit after the letter (`47K`, `1M`, `470R`) is standard notation, read under the manual's rules (`1M` is 1 milli in ngspice). Only a letter followed by digits, or a leading `R`/`L` (`R47`), is RKM.
   - **Where ngspice disagrees with IEC 60062**, the library follows the standard and records the difference: ngspice 47 reads R `1M0`/`4M7` as **milli** and C `4F7` as **femto**, in both its default and LT modes (probe in section 7). Each such value gets the `notation="rkm"` marker and a diagnostic, proposed as `RKM_SOLVER_MISMATCH` (M5; a new code, recorded in decision 0004 and architecture §17), because the netlist will not simulate with the value it states. `discrepancies.md` records both cases.
   - The library still stores text only and does not compute values (non-goal 6). The letter meanings above decide only which forms are accepted and which ones get the mismatch diagnostic.
   - *Settle (T1):* case rules where IEC 60062 relies on case. Default: R codes are case-insensitive except that `M` (mega) must be uppercase and lowercase `m` mid-value on R is a `ParseError` with a hint to use `L`. C codes are case-insensitive.
3. **Scale-factor set.** Accept the manual's set (`t g meg k mil m u n p f a`, case-insensitive; §2.1.3.2) plus `µ` as an `observed` spec entry (§11.3 rule 3; ngspice 47 reads `1µ` as `1u`; LTspice exports contain it). Amend §6.4, which lacks `a` and `mil`.
4. **Letters after a number** are accepted as the manual states (§2.1.3.3: `10V`, `1UF`, `1kOhm`, even `1kk`). `NumericValue.text` keeps the whole token. This is the manual's rule, not the bare-formula catch-all that §6.3 rule 10 forbids; bare formulas (`1.1*Rx`) stay rejected.
5. **Field separators** (§2.1.3.1): commas between fields and optional blanks around `=` are accepted (both verified on ngspice 47). Parentheses occur only in phase 2 forms outside formulas, so in M3 a parenthesis outside a formula is a `ParseError`, recorded in the spec entry.
6. **Expression forms of R, C, L** (§3.3.4, §3.3.9, §3.3.13): `R1 a b {expr}`, `R1 a b 'expr'`, and the keyword forms `r=`/`resistance=`, `c=`/`capacitance=`, `l=`/`inductance=` with a numeric value or formula are accepted. They become the value slot, with the keyword recorded. The charge form `C ... q='expr'` raises `UnsupportedConstruct` (phase 2 `BehavioralExpression`). Formula contents are not parsed: a formula that refers to `V(n)` is accepted and documented as hidden connectivity (§7.8).
7. **Corpus provenance:** `elements_basic` and `elements_rejects` are authored in this repository by `xdylanm`, MIT.

Smaller choices are listed as "settle" in the tasks. The rule for those is to pick the narrowest reading, cite the manual, and record the choice in the spec entry and the report.

## 3. Design

### 3.1 Nodes (`model/nodes.py`, `model/values.py`)

Proposed shapes; D2 finalizes them in a design note before coding starts. All nodes are frozen and slotted, like the M2 nodes.

- `values.py` (new, architecture §4): `NumericValue(text, span, notation: Literal["standard", "rkm"])`, `Formula(text, delimiter: Literal["{", "'", '"'], span)` (text without delimiters, span with them), `ModelReference(model_name, span)`, `ParamAssignment(name, value: NumericValue | Formula, span, name_span)`, `Flag(name, span)` (`off`).
- `Node(name, span)` for an element terminal; the topology signature (M5) uses `name`.
- An abstract `Component` base: `designator`, `designator_span`, `nodes: tuple[Node, ...]`, `params: tuple[ParamAssignment, ...]`, `span`, `trailing_comments: tuple[Span, ...]`.
- `Resistor`/`Capacitor`/`Inductor`: `value: NumericValue | Formula | None`, `value_keyword: str | None` (`r`, `c`, `l`, ... when written `r=1k`), `model: ModelReference | None` (architecture §5.3). `Inductor` also covers `nt=`.
- `Diode`: `model: ModelReference` (mandatory), `flags: tuple[Flag, ...]`.
- `VoltageSource`/`CurrentSource`: `dc: NumericValue | Formula | None`, `dc_keyword: bool` (whether `DC` was written), `ac: AcSpec | None` with `AcSpec(magnitude: NumericValue | Formula | None, phase: NumericValue | Formula | None, span)`. This extends §5.3 ("value initially NumericValue | Formula") for the DC and AC keywords; D1 records it.
- `SubcktInstance`: `nodes`, `subckt: ModelReference`-like `SubcktReference(name, span)`, `params` (`m=` included).
- `MutualCoupling`: `inductors: tuple[ElementReference, ...]` (two or more, §3.3.12), `value: NumericValue | Formula`. Its inductor references are topology (architecture §7.1), not nets: `nodes` is empty.
- `TopLevelItem` gains these types; `ParseResult` is otherwise unchanged and item spans still tile the source.

### 3.2 Grammar approach

- Element rules live in `core.lark` where the form is shared across dialects (R, C, L, D, X, K, V, I are common SPICE), and are composed into `ngspice.lark` like the M2 statements. Each has a `// spec:` marker.
- One designator terminal per letter (`R_NAME`, ...), case-insensitive, at the priority of the M2 statement starters, so the contextual lexer only offers them at the start of a line. Phase 2 letters keep failing on the error path (`UnsupportedConstruct`).
- Element statements end with `NL` (continuable) and use the M2 comment and `BS_CONT` mechanics. **Do not copy `rest`;** element rules are structured, but the trailing-comment and backslash tokens must be allowed in the same places.
- **The main lexing risk** (spike S1): node names may be plain numbers (`R1 1 2 100`); model names may start with a digit (`1n4148`, accepted by ngspice 47); a value and a model name can be adjacent (`R1 a b 10k rmod`); and a parameter name is only known by the `=` after it, so `X1 a b sub rval=1k` needs two-token lookahead under LALR(1). Lookaround terminals are not collision-checked by strict mode (M2 finding 6.4), and the architecture test pins that list. Every new lookaround terminal therefore needs a written justification in decision 0004 **and** the maintainer's approval to extend the pinned list. Prefer structural solutions (for example, `=` as its own token, and a right-recursive name list whose last name is the subcircuit).
- `UnsupportedConstruct` for stimulus functions, `DISTOF`, and `q=` comes from **grammar rules that recognise them** (for example `STIMULUS_KW "(" ...`) and a transformer method that raises. It is not detected by scanning text (P13).

### 3.3 Errors

- For a supported letter, a malformed line is a `ParseError` with line, column, excerpt and expected tokens. Add readable names to `_TERMINAL_NAMES` for every new terminal.
- With `rkm=False`, an RKM value is a `ParseError` at the value whose message says that RKM notation needs `rkm=True` and LT compatibility mode in ngspice. This is error enrichment (P13 (c)): the grammar exposes a dedicated terminal or rule for the RKM form in both modes, and the transformer rejects it when the option is off. It must not be a string check.

## 4. Tasks

Every task ends with `ruff check`, `ruff format --check`, `mypy --strict`, and `pytest` (coverage gate) green, run as `uv run --env-file .env python -m <tool>` (AGENTS.md; on Smart App Control failures follow docs/testing.md). Syntax stays in the grammar (P13): no regular expressions or string scanning under `src/netlistmod/model/`. Where a task says "settle", state the choice with its manual citation (or `observed` with probe evidence) in the spec entry and the report; default to the narrowest reading.

### Decisions and design

[ ] **D1 — Decision record 0004: element and value grammar.**
Record the section 2 outcomes: the RKM option (interface, default, R/C only, `notation` field), the IEC 60062 letter sets and the ngspice mismatches with the `RKM_SOLVER_MISMATCH` diagnostic, the scale-factor set and `µ`, trailing letters, separators, expression forms, the source `dc`/`ac` slots, and how unsupported forms are recognised. Amend architecture §5.3, §6.4 (scale-factor set; cite IEC 60062 and the ngspice difference), §17 (new diagnostic code) and §21 (mark the RKM item resolved, linking 0004). Add IEC 60062 to `docs/references.md` (cite the standard by number and edition; the Wikipedia page is a secondary source). Status `proposed` until the maintainer accepts it.
*Done when:* the record and architecture agree with the shipped grammar.

[ ] **D2 — Design note `docs/design/m3-elements.md`.**
Final node and value shapes (3.1), the spec-ID scheme (T7), the field-by-field grammar of each element in a table (manual form → rule → node field), and what each element's span and sub-spans cover (designator, each node, each value, each parameter name and value). Keep it short. Sub-spans are what M6 edits will replace, so each must slice back to exactly the editable text.
*Done when:* the maintainer has reviewed it (this may run in parallel with S1).

### Spikes (throw-away grammars under `strict=True`, results into decision 0004)

[ ] **S1 — Lexing of names, numbers, values and parameters.**
Questions: (a) can node names (including numeric ones and KiCad `/net` names), numbers with scale factors and trailing letters, RKM forms, model names starting with a digit, and `name=value` parameters be lexed without collisions in the contextual lexer, preferably without new lookaround terminals? (b) Does LALR(1) handle `R n+ n- [value] [model] params*`, `X nodes... subckt params*` and `K L.. L.. [L..]* value` without conflicts? (c) Spans of each sub-token, including across `+` and `\\` continuations.
Acceptance: one design that builds under `strict=True`, accepts and rejects the section 6 table, and adds no unchecked terminal without the justification described in 3.2. If no design meets this, stop and report with evidence.

[ ] **S2 — Recognising unsupported forms in the grammar.**
Question: a grammar shape that recognises `PULSE(`...`)` and the other stimulus functions, `DISTOF1/2` and `q=` well enough to raise `UnsupportedConstruct` at the keyword's position, without parsing their arguments in full and without swallowing the rest of the line wrongly.
Acceptance: positioned `UnsupportedConstruct` for each listed form, including when it is continued.

### Implementation

[ ] **T1 — Values (`model/values.py`) and number grammar.**
Terminals and rules for numbers (integer, float, exponent, scale factor, trailing letters), RKM forms (decision 2: R and C letter sets, `E` excluded, standard notation when no digit follows the letter), brace and quoted formulas, and `name=value` parameters. The node records which values fall in the ngspice-mismatch cases (R `M` mid-value, C `F` mid-value) so that M5 can emit `RKM_SOLVER_MISMATCH` without re-reading the text: the grammar gives them their own terminal or rule. Settle: the RKM case rules of decision 2; sign handling (`-44`, `+1k`); `.5` and `5.`; exponent with a scale factor (`1e3k`); upper/lower case of `meg`/`mil`; whether a formula may contain a nested `{` (default: no, per §6.3 rule 8); the delimiters a `Formula` may use (`{}` and `'`; `"` for string parameters only, per §2.11.3); whether `1kk` produces an error (default per decision 4: accepted).
*Done when:* T1-tier tests cover each form, the stored text, and the spans.

[ ] **T2 — R, C, L.**
Grammar and nodes for value, keyword value (`r=`), model reference, instance parameters, and the expression forms of decision 6. Settle: `R1 a b` with no value and no model (ngspice requires one; the manual says "If value is not specified, then mname and length must be specified": reject, or accept as syntax and leave it to the solver? Default: accept as syntax only if the manual's general form allows it, and say which); value `0`; negative values.
*Done when:* every manual example in §3.3.1, §3.3.2, §3.3.6, §3.3.7 and §3.3.10 parses (paraphrased into authored fixtures, not copied), and the T6 cases in section 6 reject with positions.

[ ] **T3 — V and I.**
Plain value, `DC` value, `AC` magnitude and optional phase, in either order as §4.1 allows. Settle: a source with no value (`VMEAS 12 9`, valid per §4.1); `DC` without a value; a second `DC`; `AC` without a magnitude. Stimulus functions and `DISTOF` raise `UnsupportedConstruct` (S2).
*Done when:* the `kicad_basic` sources (`V1 /vin 0 DC 0 AC 1  `) and the manual's phase 1 examples parse; each unsupported form raises at its keyword.

[ ] **T4 — D.**
Mandatory model, instance parameters (`area`, `m`, `pj`, `ic`, `temp`, `dtemp`, `lm`, `wm`, `lp`, `wp`), the `off` flag. Settle: whether instance parameter names are checked against the manual's list (default: no; any `name=value` is accepted, because the library does not validate parameters, non-goal 8). Apply the same rule to R, C, L and X.
*Done when:* accept and reject tests pass with positions.

[ ] **T5 — X and K.**
`X` with one or more nodes, a subcircuit name and optional `name=value` parameters (including `m=`). Settle: whether `params:` (an HSPICE/LTspice form, not in the ngspice manual) is rejected (default: reject); an `X` line with no nodes. `K` with two or more inductor names and a coupling value (number or formula). Settle: a `K` naming a non-`L` element (syntax error or M5 diagnostic? default: grammar requires the `L` letter, §3.3.12).
*Done when:* accept and reject tests pass; `K` inductor references and `X` nodes have spans.

[ ] **T6 — Transformer, RKM option and errors.**
Transformer methods per new rule, dispatching on node type (§6.3 rule 11). `parse(source, dialect, *, rkm=False)`, with `rkm` passed through to the transformer (one cached parser per dialect; the option must not change the grammar). Error names for the new terminals; RKM-off message; `UnsupportedConstruct` stays for phase 2 letters. Update `ngspice-devices.json` and `devices.md` (R, C, L, V, I, D, X, K `supported`) and the `structure_rejects/element_line.cir` fixture (use a phase 2 letter; update its manifest).
*Done when:* every error branch is covered, and the device-matrix consistency test passes.

### Validation, specs and tests

[ ] **T7 — Spec entries.**
New entries under `docs/grammars/ngspice/specs/`, in the M2 format (`manual_ref` as `[ngspice-manual] §<n> "<title>"`, `grammar:`, `tests:`, `status`), for example: `NG-FLD-001` fields and separators; `NG-NOD-001` node names; `NG-NUM-001` numbers and scale factors; `NG-NUM-002` trailing letters; `NG-NUM-003` RKM (option); `NG-NUM-004` `µ` (`observed`); `NG-VAL-001` formulas; `NG-PAR-001` instance parameters and flags; `NG-RES-001`, `NG-CAP-001`, `NG-IND-001`, `NG-MUT-001`, `NG-SRC-001`, `NG-DIO-001`, `NG-SUB-001`; `NG-UNS-001` unsupported forms. Add `docs/grammars/ngspice/numbers.md` (architecture §9.3) summarising the number rules with citations (paraphrase only).
*Done when:* the spec checker passes, and every new rule and terminal carries a marker.

[ ] **T8 — Solver probes (T8 tier, discrepancy evidence and acceptance).**
In `tests/solver/`: (a) record the section 7 probes as tests (`2k7` read as `2k` without LT mode; `µ` as micro; comma separators; `r=`; digit-leading model name), each paired with what the library does; (b) every file in the new accept corpus runs in ngspice 47 without error; (c) a divider and an RC filter give the closed-form result, as a first M7-style check; (d) with `set ngbehavior=lt` in a temporary `.spiceinit`, `2k7`, `4R7`, `R47`, `4L7`, `4G7` and `4u7` are read per IEC 60062 (validates `NG-NUM-003`), while R `1M0` is read as milli and C `4F7` as femto in both modes (discrepancy evidence for decision 2); `4E7` is an exponent in both modes. Update `discrepancies.md`. LTspice's reading of `1M0` is checked in M8.
*Done when:* the tests pass locally and skip cleanly without the solver; spec entries carry `validated_on`.

[ ] **T9 — Tests and corpus.**
- *Corpus:* new authored families `elements_basic/` (one small netlist per element and value form, LF and CRLF, continuations, trailing comments) and `elements_rejects/` (one file per T6 case, manifest with expected line and column), with manifests (origin: authored in this repository; author `xdylanm`, MIT, confirmed by the maintainer on 2026-10-30). `kicad_basic` now parses with `rkm=True` and fails with the RKM message without it.
- *T2:* one accept and one reject test per spec entry.
- *T3:* round-trip and span tiling over all corpora.
- *T5:* extend the independent Hypothesis oracle from M2 to generate element lines of every phase 1 letter (random nodes, values, parameters, comments, `+` continuation), comparing kinds and designators/nodes/value texts against the generator. The broader generator work stays in M9 (plan section 4).
- *T1:* each sub-span slices back to its text (designator, nodes, value, model, parameter name and value).
- *Performance:* 20,000 element lines (mixed letters, 10% continued) parse in under 2 s.
*Done when:* all pass with the 90% coverage gate.

[ ] **T10 — Docs.**
Update `docs/usage/structural-parse.md` (or add `docs/usage/elements.md`) with an executed example, `CHANGELOG.md`, `README.md` status, `docs/testing.md` (new corpora, the `rkm` option in tests), and the phase plan's M3 heading (link this task list). Public names get docstrings.
*Done when:* docs match the code and links resolve.

[ ] **T11 — Exit.**
Full check set, a fresh-clone test, and the solver tests. Report what changed, every "settle" decision with its citation, deviations from this list, and limitations. Set this document's status to `READY FOR REVIEW`. **Do not archive.**

## 5. Dependencies between tasks

```
Section 2 decisions → D1
S1, S2 → D1 (records spike outcomes), D2
D2 → T1 → T2, T3, T4, T5 (independent of each other once T1 is in)
T2–T5 → T6 → T7 → T9
T8 needs T6 (library side) and can start its probes earlier
T9 → T10 → T11
```

## 6. Accept and reject table (minimum; extend in T2–T5)

| Input (element line, inside a valid netlist) | Result |
|---|---|
| `R1 1 2 100`; `RC1 12 17 1K`; `R2 5 7 1K ac=2K`; `RL 1 4 2K m=2` | accept |
| `R1 /vin /vout 10k`; `r1 a b 10kOhm`; `R1 a b r = 1k`; `R1 a,b 1k` | accept |
| `RMOD 3 7 RMODEL L=10u W=1u`; `R1 a b 10k rmod tc1=2m` | accept |
| `R1 a b {Rx*2}`; `R1 a b 'Rx*2'`; `R1 a b r={5k}` | accept |
| `R1 a b 2k7`; `R1 a b 4R7`; `R1 a b R47`; `R1 a b 4L7`; `C1 a b 4p7` | reject with `rkm=False` (RKM message); accept with `rkm=True` |
| `R1 net1 net2 1M0`; `C1 a b 4F7` | reject with `rkm=False`; with `rkm=True` accept (IEC: 1 MΩ, 4.7 F), marked as an ngspice mismatch |
| `R1 a b 1M`; `R1 a b 47K`; `R1 a b 4E7` | standard notation in both modes (`1M` is milli; `4E7` is an exponent) |
| `R1 a b 1m5` | reject in both modes (lowercase `m` is not an R code; hint `L`), subject to the T1 settle |
| `L1 a b 4u7` | reject in both modes (RKM is R and C only) |
| `R1 a b 1.1*Rx`; `R1 a b 1k)`; `R1 a b k=`; `R1 a` | reject with position |
| `CBYP 13 0 1UF`; `COSC 17 23 10U IC=3V`; `C1 15 5 cstd` | accept |
| `C1 a b q='1u*V(a,b)'` | `UnsupportedConstruct` at `q` |
| `LLINK 42 69 1UH`; `LSHUNT 23 51 10U IC=15.7MA` | accept |
| `K43 LAA LBB 0.999`; `K123 L1 L2 L3 0.97` | accept |
| `K1 L1 0.9`; `K1 L1 R2 0.9` | reject with position |
| `VCC 10 0 DC 6`; `VIN 13 2 0.001 AC 1`; `ISRC 23 21 AC 0.333 45.0`; `VMEAS 12 9` | accept |
| `VIN 3 0 PULSE(-1 1 2NS 2NS 2NS 50NS 100NS 5)`; `VIN 13 2 0.001 AC 1 SIN(0 1 1MEG)`; `VCARRIER 1 0 DISTOF1 0.1 -90.0` | `UnsupportedConstruct` at the keyword |
| `DBRIDGE 2 10 DIODE1`; `DCLMP aa cc DMOD AREA=3.0 IC=0.2`; `D1 a k 1n4148 off` | accept |
| `D1 a b` (no model) | reject with position |
| `X1 2 4 17 3 1 MULTI`; `X1 input output myfilter rval=1k cval=1n` | accept |
| `X1 a b sub params: r=1`; `X1` | reject with position |
| any of the above continued with `+` or `\\`, with `;`/`$`/`//` comments | accept; spans cover every physical line |
| `Q1 c b e npn` (phase 2 letter) | `UnsupportedConstruct` (unchanged from M2) |

## 7. Probe facts gathered while planning (ngspice 47, 2026-10-30)

Each is re-recorded as a solver test in T8. Divider `V1 in 0 DC 3`, `R1 in out ...`, `R2 out 0 ...`, `.op`, `print v(out)`:

| Values | `v(out)` | Reading |
|---|---|---|
| `2k0`, `1k0` | 1.0 | consistent with 2k:1k (the dropped digit is 0) |
| `2k7`, `1k` | 1.0 | `2k7` read as `2k`: digits after the scale factor are silently dropped without LT mode |
| `1kOhm`, `1kk` | 1.5 | trailing letters ignored (§2.1.3.3) |
| `1µ`, `1u` | 1.5 | `µ` read as micro (not in the manual's table) |
| `in,out` node separator; `r=1k` | 1.5 | comma separator and keyword value accepted |
| `D1 a 0 1n4148` with `.model 1n4148 d` | 0.629 | a model name may start with a digit |

RKM letters, default mode and with `set ngbehavior=lt` (same divider; C values measured as AC impedance):

| Value | Default mode | LT mode | IEC 60062 |
|---|---|---|---|
| R `2k7` | 2k | 2.7k | 2.7k |
| R `4R7` | 4 | 4.7 | 4.7 |
| R `R47` | error (exit 1) | 0.47 | 0.47 |
| R `4L7` | 4 | 4.7m | 4.7m |
| R `4G7` | 4G | 4.7G | 4.7G |
| R `1M0`, `4M7` | 1m, 4m | 1m, 4.7m | **1M, 4.7M** |
| R `4E7` | 4×10⁷ | 4×10⁷ | (4.7, `E` for `R`) |
| C `4u7` | 4u | 4.7u | 4.7u |
| C `1m0` | 1m | 1m | 1m |
| C `4F7` | femto | femto | **4.7 F** |

## 8. Out of scope for M3

`.param`, `.model`, `.subckt`/`.ends` and typed directives (M4); `Document`, `Lines`, indexes, topology signature, ground aliases, diagnostics API (M5); edits (M6); stimulus specs, behavioral expressions and every phase 2 letter (phase 2); the LTspice grammar (M8); expression evaluation (non-goal 6) and parameter validation (non-goal 8).
