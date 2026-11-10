# Element nodes, grammar and spans

> **Status:** ACTIVE — living reference, kept current with the code; began as the M3 design note (D2 of
> [m3-tasks.md](./archive/phase-1/m3-tasks.md)). [Decision 0004](../decisions/0004-element-and-value-grammar.md)
> and [decision 0009](../decisions/0009-ltspice-dialect.md) record why. The element operations of
> [edit-layer.md](./edit-layer.md) edit the sub-spans of section 4, and its §2 adds where new fields go.
> Sections 2 and 3 describe the ngspice grammar; section 5 gives what LTspice changes.

## 1. Node and value shapes

All are frozen, slotted dataclasses (`netlistmod.model`, exported from `netlistmod`).

| Type | Fields |
|---|---|
| `NumericValue` | `text`, `span`, `notation: "standard" \| "rkm"`, `solver_mismatch: bool` (`"rkm"` is also an LTspice embedded decimal) |
| `Formula` | `text` (without delimiters), `delimiter: "{" \| "'" \| '"'` or empty for a bare LTspice `.param` expression, `span` (with delimiters) |
| `Value` | alias `NumericValue \| Formula` |
| `ModelReference` | `model_name`, `span` |
| `SubcktReference` | `name`, `span` |
| `ElementReference` | `designator`, `span` (the inductors of a `K` line) |
| `ValueList` | `text`, `values: tuple[Value, ...]`, `span` (first to last); a list of values: an LTspice `tc=a,b`, an `ic=`, and a CPL model's matrix (`R=1 0 1`, decision 0019) |
| `Identifier` | `name`, `span`; a bare word, such as an option value or an LTspice `mfg=` |
| `ParamAssignment` | `name`, `value: Value \| ValueList \| Identifier`, `span` (name to end of value), `name_span` |
| `Flag` | `name`, `span`, `value: Value \| None` (the diode's `off`; an LTspice flag may take a value, which `span` then includes) |
| `AcSpec` | `magnitude: Value`, `phase: Value \| None`, `span` (keyword to last value) |
| `Node` | `name`, `span` |

`Component` (keyword-only fields) is the base of every element: `designator`,
`designator_span`, `nodes`, `params`, `span`, `trailing_comments`. Subclasses:

| Node | Extra fields |
|---|---|
| `Resistor`, `Capacitor`, `Inductor` | `value: Value \| None`, `value_keyword: str \| None`, `model: ModelReference \| None`, `flags` (an LTspice `noiseless`); `Capacitor.charge` and `Inductor.flux`: `Formula \| None`, the behavioural forms (ngspice `q=`, LTspice `Q=` and `Flux=`), with `value` `None`; LTspice's hysteretic L has no value and its core parameters in `params` (decision 0016 item 4) |
| `MutualCoupling` | `inductors: tuple[ElementReference, ...]`, `value: Value`; `nodes == ()` |
| `VoltageSource`, `CurrentSource` | `dc: Value \| None`, `dc_keyword: bool`, `ac: AcSpec \| None`, `flags` (an LTspice `load`); `params == ()` in ngspice |
| `Diode` | `model: ModelReference`, `flags: tuple[Flag, ...]`, `area: Value \| None` (LTspice's positional area) |
| `BipolarTransistor`, `Mosfet`, `Jfet`, `Mesfet` (subclasses of `Transistor`, for `isinstance`) | `model: ModelReference`, `flags: tuple[Flag, ...]` (`off`, and an ngspice VDMOS's `thermal`), `area: Value \| None` (a positional area: J and Z, and an LTspice Q); `nodes` are the nodes as written (decision 0014) |
| `Vcvs` (E), `Vccs` (G), `Cccs` (F), `Ccvs` (H), subclasses of `ControlledSource` | `value: Value` (the gain); `nodes` of E and G are the output pair then the control pair, with a `control_nodes` property; F and H have two `nodes` and `control: tuple[ElementReference, ...]`, the controlling sources (one for the linear form, N for POLY in line order, none for `value=`; decision 0017 item 2); `params` holds ngspice's `m=` on F and G (decision 0015). The expression forms (ngspice `vol=`, `cur=`, `value`; LTspice `value=`) have `value` `None`, `expression: Formula` and `form` (the keyword, lower case); F and H then have `control` `()` (decision 0016 item 3, as amended by 0017). The forms of M15b (decision 0017) have `value` `None` and `form` `"table"`, `"poly"`, `"laplace"`, `"freq"`, `"and"`, `"or"`, `"nand"` or `"nor"`, and use three more fields: `table: Table \| None` (TABLE, `table=`, FREQ and the gates' two points), `dimension: int \| None` (POLY's or a gate's `N` as written) and `coefficients: tuple[Value, ...]` (POLY's). `expression` is then the formula the line writes: the input of ngspice `TABLE {expr}` and `FREQ {expr}`, or LTspice's `Laplace=` transfer function; it is `None` for the four-node TABLE, `table=`, POLY and the gates, which read their control nodes. `window=`, `nfft=`, `mtol=` and `m=` are in `params` |
| `Table`, `TablePoint` | `Table.points: tuple[TablePoint, ...]`, `layout` (`"pairs"`: each point in its own parentheses; `"flat"`: one parenthesised list), `format: tuple[str, ...]` (FREQ's words as written, empty for the other forms) and `span`; `TablePoint.values: tuple[Value, ...]` (two, or three for FREQ) and `span` (decision 0017 item 1) |
| `BehavioralSource` (B) | `quantity: str` (`"v"`, `"i"`, and on LTspice `"r"` or `"p"`), `expression: Formula`; `params` holds the trailing parameters (ngspice `tc1=`, `tc2=`, `temp=`, `dtemp=`; LTspice `ic=`, `tripdv=`, `tripdt=`, `Rpar=`, `vprx=`) (decision 0016) |
| `VoltageSwitch` (S), `CurrentSwitch` (W), subclasses of `Switch` | `model: ModelReference`, `flags: tuple[Flag, ...]` (`on` or `off`); S has four `nodes` and `control_nodes`, W two `nodes` and `control`, a tuple of the one controlling source |
| `LosslessLine` (T), `LossyLine` (O), `RcLine` (U), `TxlLine` (Y), `CoupledLine` (P), subclasses of `TransmissionLine` (decision 0019) | T has no extra field: `Z0=` (or `Zo=`), `TD=`, `F=`, `NL=` and ngspice's `IC=` (a `ValueList` of four values) are `params`. O, U, Y and P have `model: ModelReference`; U's `l=` and `n=` and Y's and P's `len=` are `params`. T, O, Y and P have `port1` and `port2` properties (each port's nodes, then its reference node; on P a port is its X nodes and its reference), and P has `conductors` (X). U has three `nodes` and no ports. Y's and P's reference nodes are ground. |
| `CodeModelDevice` (ngspice A; decision 0020 items 2 and 4) | `model: ModelReference` (the last name on the line), `ports: tuple[CodeModelPort, ...]`; `nodes` is every node of every port in order, without `null` and `%vnam` sources; `params == ()` (a code model's values are on its `.model`); a `control` property holds the `%vnam` sources, controlling references like F's |
| `CodeModelPort`, `CodeModelConnection` | `CodeModelPort.vector: bool`, `connections`, `span` (with the brackets of a vector), `port_type: str \| None` (a type before a vector, such as `%v[a b]` or `%vd [a b c d]`); `CodeModelConnection.port_type: str \| None` (as written: `%v`, `%vd`, `%vnam` …), `nodes` (one, or two for a differential type), `inverted` (a `~`), `null`, `source: ElementReference \| None` (a `%vnam`'s source) and `span` |
| `OsdiDevice` (ngspice N; decision 0020 item 6) | `model: ModelReference` (the last name before the first `name=value`); the instance parameters are `params` |
| `SpecialFunction` (LTspice A; decision 0020 items 3 and 7) | `function: Identifier` (one of the 13 names, as written); eight `nodes`, with `inputs` (1 to 5), `outputs` (6 and 7) and `common` (8) properties; the named parameters are `params` |
| `FrequencyAnalyzer` (LTspice `@`; decision 0020 item 7) | `impedance: Flag \| None` (`zm`), `reference_net` and `intermediate_net: Node \| None` (what `refnode=` and `intnode=` name: node references, not terminals); two `nodes`; `params` holds every named parameter, `flist=`, `pp=`, `nmax=` and `ac=` as a `ValueList` when they hold more than one value |
| `FraProbe` (LTspice `&`; decision 0020 item 8) | `analyzer: ElementReference` (`@` and the probe's suffix; its span is the probe's designator); four `nodes`, with `output_pair` and `input_pair` properties |
| `SubcktInstance` | `subckt: SubcktReference` |

Deviation from task 3.1: `AcSpec.magnitude` is required, because the manual requires ACMAG
after `AC` (§4.1).

## 2. Spec IDs (T7)

`NG-FLD-001` separators · `NG-NOD-001` names · `NG-NUM-001` numbers · `NG-NUM-002` trailing
letters · `NG-NUM-003` RKM · `NG-NUM-004` `µ` · `NG-VAL-001` formulas · `NG-PAR-001`
parameters, models, flags · `NG-RES-001` · `NG-CAP-001` · `NG-IND-001` · `NG-MUT-001` ·
`NG-SRC-001` · `NG-DIO-001` · `NG-SUB-001` · `NG-UNS-001` unsupported forms · `NG-XTR-001` the
transistor line shape · `NG-BJT-001` · `NG-MOS-001` · `NG-JFT-001` · `NG-MES-001` (M13) · `NG-CTL-001`
the shape of the dependent sources and switches · `NG-VCV-001` · `NG-VCC-001` · `NG-CCC-001` ·
`NG-CCV-001` · `NG-SWV-001` · `NG-SWC-001` (M14) · `NG-TLL-001` T · `NG-LTR-001` O · `NG-URC-001` U
· `NG-TXL-001` Y · `NG-CPL-001` P (M16) · `NG-COD-001` A · `NG-OSD-001` N (M17). Every grammar
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
| source function (§4.1.1–§4.1.9) | `stimulus`, `pwl_stimulus`, `external_kw`, each with `fn_list` and `fn_param` | `stimulus: SourceSpec` (`SourceSpec`: `name`, `name_span`, `args`, `params`, `span`, `forever`) |
| `DISTOF1`, `DISTOF2` (§4.1) | `distof1_kw`, `distof2_kw` | `distortion: tuple[SourceSpec, ...]` |
| `portnum`, `z0` (§4.1.11) | `port_param` | `params` |
| `DXXX n+ n- mname params [off]` (§7.2) | `diode: D_NAME node node model (param \| flag)*` | `model`, `params`, `flags` |
| `QXXX nc nb ne [ns [tj]] mname params [off]` (§7.3.1) | `bjt: Q_NAME node node node` then 1 to 3 `t_name`/`t_number`, the last a `t_name`, then `_ng_ttail` | `nodes`, `model`, `params`, `flags` |
| `MXXX nd ng ns [nb [tc]] mname params [off] [thermal]` (§7.6.1, §7.7) | `mosfet: M_NAME node node node` then as `bjt`, then `_ng_mtail` | `nodes`, `model`, `params`, `flags` |
| `JXXX nd ng ns mname [area] params [off]` (§7.4.1), `ZXXX` (§7.5.1) | `jfet`, `mesfet: …_NAME node node node t_name t_area? _ng_ttail` | `nodes`, `model`, `area`, `params`, `flags` |
| `EXXX n+ n- nc+ nc- value`, `GXXX … value <m=val>` (§4.2.2, §4.2.1) | `vcvs`, `vccs: …_NAME node node node node value`, then `ctl_m` on G; or `…_NAME node node nonlinear_form` (unsupported) | `nodes`, `value`, `params` |
| `FXXX n+ n- vnam value <m=val>`, `HXXX n+ n- vnam value` (§4.2.3, §4.2.4) | `cccs`, `ccvs: …_NAME node node ctl_ref value`, then `ctl_m` on F; or `cc_form` (POLY, unsupported) | `nodes`, `control`, `value`, `params` |
| `SXXX n+ n- nc+ nc- model <ON|OFF>`, `WXXX n+ n- vnam model <ON|OFF>` (§3.3.15) | `vswitch`, `cswitch`, with `sw_state` | `nodes`, `control` (W), `model`, `flags` |
| `TXXX n1 n2 n3 n4 Z0=… TD=…` or `F=… [NL=…]`, `IC=v1,i1,v2,i2` (§6.1) | `lossless_line: T_NAME node node node node` then `t_param` and `ic_param` | `nodes`, `params` |
| `OXXX n1 n2 n3 n4 mname` (§6.2) | `lossy_line: O_NAME node node node node model` | `nodes`, `model` |
| `UXXX n1 n2 n3 mname l=len [n=lumps]` (§6.3) | `rc_line: U_NAME u_word+` then `u_param`: four names are a URC line, any other shape the digital U (`UnsupportedConstruct`) | `nodes`, `model`, `params` |
| `YXXX n1 0 n2 0 mname [len=…]` (§6.4.1) | `txl_line: Y_NAME node node node node model line_len*` | `nodes`, `model`, `params` |
| `PXXX ni1 … gnd1 no1 … gnd2 mname [len=…]` (§6.4.2) | `coupled_line: P_NAME t_name+ line_len*`; the last name is the model | `nodes`, `model`, `params` |
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

## 5. LTspice

The rules are in [decision 0009](../decisions/0009-ltspice-dialect.md) items 3, 6, 7 and 9, and the syntax facts in [docs/grammars/ltspice/](../grammars/ltspice/README.md). The shapes above serve both dialects. What differs:

- **Spec IDs:** `LT-FLD-001`, `LT-NOD-001`, `LT-NUM-001` to `LT-NUM-004`, `LT-VAL-001`, `LT-RES-001`, `LT-CAP-001`, `LT-IND-001`, `LT-MUT-001`, `LT-SRC-001`, `LT-DIO-001`, `LT-SUB-001`, `LT-UNS-001`, and for M13 `LT-XTR-001`, `LT-BJT-001`, `LT-MOS-001`, `LT-JFT-001`, `LT-MES-001`, and for M14 `LT-CTL-001`, `LT-VCV-001`, `LT-VCC-001`, `LT-CCC-001`, `LT-CCV-001`, `LT-SWV-001`, `LT-SWC-001`.
- **R, C, L:** no model form and no keyword form, so `model` and `value_keyword` are `None`. The parameter names of each letter are a closed list.
- **V, I:** `params` holds `Rser` and `Cpar` on V, and `R=` on I. `flags` holds I's `load`.
- **D:** `area` is the positional area; `area=` written out is a parameter.
- **Q, M, J, Z:** Q and M take 3 or 4 nodes, J and Z exactly 3. Q, J and Z take a positional `area`. Each letter's parameter names are a closed list (decision 0014 item 6), and M has no `thermal` flag. An embedded decimal such as `1n5` is an area only where no further name may follow.
- **E, F, G, H, S, W:** no parameter on any of the six. A switch's state may take a value (`off=1`). value= and POLY after the output nodes, and table= and Laplace= after E's and G's control nodes, are unsupported (M15).
- **T, O, U (M16, decision 0019):** T takes `Zo=` (or `Z0=`) and `Td=`, the reference's names; `F=`, `NL=`, `IC=`, `rel=` and `abs=` are refused. O is as on ngspice. U is only a URC line: three nodes, a model, `L=` and `N=`. A bare name in a T or U value (`Zo=z`, `L=len`) is refused with a message suggesting braces, as on every LTspice element (review R2). Y and P are not LTspice letters. The spec IDs are `LT-TLL-001`, `LT-LTR-001` and `LT-URC-001`.
- **X:** open parameter names, with or without `params:`.
- **K:** three or more inductors, as in ngspice.
- **Numbers:** the embedded decimal is native (`notation == "rkm"`), and there is no `rkm` option.
- **Separators:** no comma separator and no `\\` continuation; see the comment rules in decision 0009 item 9.

## Behavioural expressions (M15, decision 0016)

An expression is a `Formula`. In quotes or braces it has that `delimiter` and its `text` is
inside them; bare, `delimiter` is `""` and the span covers the text as written, blanks and `+`
continuations included. A bare expression ends at the line end or before the first blank that
is followed by a name and `=` (not `==`), so a trailing parameter ends it and an unknown one is
refused. In the grammar a bare expression is one `B_PIECE` per physical line (P13).

Refused with their own message: two quantities on one B line, a B line with no expression,
ngspice's `r=` and `p=` on B, a bare expression after ngspice's `vol=` or `cur=`, and on LTspice
`Rpar=` on a `V=` or `P=` B, ngspice's `vol=` and its `TABLE {...} =`. The M15b forms (TABLE,
POLY, Laplace, FREQ and AND/OR/NAND/NOR) are `UnsupportedConstruct`.
