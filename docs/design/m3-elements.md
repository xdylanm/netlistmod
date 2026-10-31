# M3 design note — element nodes, grammar and spans

> **Status:** ACTIVE — reviewed with M3 (2026-10-30); the reference for element shapes and spans
> until M6 edits build on them (D2 of [m3-tasks.md](./archive/m3-tasks.md)). Records the shapes
> that shipped; [decision 0004](../decisions/0004-element-and-value-grammar.md) records why.
> Kept ACTIVE after M6: the element operations of [m6-edits.md](./m6-edits.md)
> edit the sub-spans of section 4, and m6-edits.md §2 adds where new fields go.

## 1. Node and value shapes

All are frozen, slotted dataclasses (`netlistmod.model`, exported from `netlistmod`).

| Type | Fields |
|---|---|
| `NumericValue` | `text`, `span`, `notation: "standard" \| "rkm"`, `solver_mismatch: bool` |
| `Formula` | `text` (without delimiters), `delimiter: "{" \| "'" \| '"'`, `span` (with delimiters) |
| `Value` | alias `NumericValue \| Formula` |
| `ModelReference` | `model_name`, `span` |
| `SubcktReference` | `name`, `span` |
| `ElementReference` | `designator`, `span` (the inductors of a `K` line) |
| `ParamAssignment` | `name`, `value: Value`, `span` (name to end of value), `name_span` |
| `Flag` | `name`, `span` (the diode's `off`) |
| `AcSpec` | `magnitude: Value`, `phase: Value \| None`, `span` (keyword to last value) |
| `Node` | `name`, `span` |

`Component` (keyword-only fields) is the base of every element: `designator`,
`designator_span`, `nodes`, `params`, `span`, `trailing_comments`. Subclasses:

| Node | Extra fields |
|---|---|
| `Resistor`, `Capacitor`, `Inductor` | `value: Value \| None`, `value_keyword: str \| None`, `model: ModelReference \| None` |
| `MutualCoupling` | `inductors: tuple[ElementReference, ...]`, `value: Value`; `nodes == ()` |
| `VoltageSource`, `CurrentSource` | `dc: Value \| None`, `dc_keyword: bool`, `ac: AcSpec \| None`; `params == ()` |
| `Diode` | `model: ModelReference`, `flags: tuple[Flag, ...]` |
| `SubcktInstance` | `subckt: SubcktReference` |

Deviation from task 3.1: `AcSpec.magnitude` is required, because the manual requires ACMAG
after `AC` (§4.1).

## 2. Spec IDs (T7)

`NG-FLD-001` separators · `NG-NOD-001` names · `NG-NUM-001` numbers · `NG-NUM-002` trailing
letters · `NG-NUM-003` RKM · `NG-NUM-004` `µ` · `NG-VAL-001` formulas · `NG-PAR-001`
parameters, models, flags · `NG-RES-001` · `NG-CAP-001` · `NG-IND-001` · `NG-MUT-001` ·
`NG-SRC-001` · `NG-DIO-001` · `NG-SUB-001` · `NG-UNS-001` unsupported forms. Every grammar
definition, including `_` sub-terminals, carries a `// spec:` marker.

## 3. Element grammar (field by field)

Every field rule begins with its separator (`SEP`, `CSEP` or `BS_CONT`, after optional gap
material) and returns one slot. `[x]` is optional and `x*` repeats.

| Manual form | Rule | Node fields |
|---|---|---|
| `RXXX n+ n- value [mname] params` (§3.3.1, §3.3.2) | `resistor: R_NAME node node r_value model? param* …` | `nodes`, `value`, `model`, `params` |
| `RXXX n+ n- mname params` (§3.3.2) | `R_NAME node node model param*` | `model`, `value=None` |
| `RXXX n+ n- r=value params` (§3.3.1, §3.3.4) | `R_NAME node node r_keyword_value param*` | `value`, `value_keyword` |
| C, L (§3.3.6–§3.3.13) | as R with `c_value`/`value` and `c_`/`l_keyword_value` | same |
| `CXXX n+ n- q='expr'` (§3.3.9) | `charge` | raises `UnsupportedConstruct` |
| `KXXX Lyyy Lzzz [Lwww…] value` (§3.3.12) | `mutual_coupling: K_NAME inductor_ref inductor_ref+ value` | `inductors`, `value` |
| `VXXX n+ n- [[DC] value] [AC mag [phase]]` (§4.1) | `V_NAME node node dc_spec? (ac_spec value?)? …` | `dc`, `dc_keyword`, `ac` |
| stimulus function, `DISTOFn` (§4.1) | `stimulus: … STIMULUS_KW rest NL` | raises `UnsupportedConstruct` |
| `DXXX n+ n- mname params [off]` (§7.2) | `diode: D_NAME node node model (param \| flag)*` | `model`, `params`, `flags` |
| `XXXX n1 [n2…] subnam params` (§2.6.3, §2.11.3) | `subckt_instance: X_NAME node (x_node \| x_last)` | `nodes`, `subckt`, `params` |
| `params:` (HSPICE) | `params_keyword` | raises `ParseError` |

An element line ends with `NL`, or with `eol` (blanks, comments or continuations, then `NL`).

## 4. Spans

- The item `span` tiles the source like every top-level item: from the end of the previous
  item to the end of the element's last `NL`, so it includes leading blanks, every
  continuation line and every comment.
- Sub-spans cover exactly their text, never a separator. These are what M6 edits replace:
  - `designator_span`: the designator;
  - each `Node.span`: the node name;
  - `value.span`: the number, or the formula with its delimiters (for `r=1k`, only `1k`);
  - `model.span`, `subckt.span`, each `ElementReference.span`: the name;
  - `ParamAssignment.name_span` and `value.span`: the name and the value, with `span` running
    from one to the other (it includes `=` and any blanks around it);
  - `AcSpec.span`: from `AC` to the last AC value.
- `trailing_comments` lists the span of every end-of-line comment of the element in source
  order, including comments on earlier lines of a continued element.
