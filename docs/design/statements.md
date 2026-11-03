# Statement and directive nodes, grammar and spans

> **Status:** ACTIVE — living reference, kept current with the code; began as the M4 design note (D2 of
> [m4-tasks.md](./archive/phase-1/m4-tasks.md)). [Decision 0005](../decisions/0005-statement-and-directive-grammar.md)
> and [decision 0009](../decisions/0009-ltspice-dialect.md) record why. The statement and directive
> operations are specified in [edit-layer.md](./edit-layer.md). Sections 2 and 3 describe the ngspice
> grammar; section 5 gives what LTspice changes.

## 1. Node shapes

All are frozen, slotted dataclasses (`netlistmod.model`, exported from `netlistmod`). Every
typed dot-command has `keyword` (as written), `keyword_span`, `span` (the item span, which
tiles the source) and `trailing_comments` (every end-of-line comment, in source order).

| Node | Fields |
|---|---|
| `ParamStatement` | `assignments: tuple[ParamAssignment, ...]` |
| `ModelStatement` | `name`, `name_span`, `model_type`, `model_type_span`, `params`, `parenthesized`, `open_paren_span`, `close_paren_span` (the `(` and `)` tokens, `None` without parentheses; added in M6 review round 1), `ako: ModelReference \| None` (LTspice's `ako:` base) |
| `SubcktDefinition` | `name`, `name_span`, `ports: tuple[Node, ...]`, `params` (defaults), `body: tuple[BodyItem, ...]`, `ends: EndsLine`, `header_span` |
| `EndsLine` | `name: str \| None`, `name_span: Span \| None`, `span`, `trailing_comments` |
| `Directive` | base of the directives below (top level only) |
| `TranDirective` | `tstep`, `tstop`, `tstart \| None`, `tmax \| None`, `uic: Flag \| None`, `modifiers: tuple[OptionItem, ...]` (LTspice) |
| `AcDirective` | `variation`, `variation_span`, `points`, `fstart`, `fstop`, `frequencies` (LTspice `.ac list`; range fields `None`), `file` (LTspice `.ac file=`) |
| `DcDirective` | `sweeps: tuple[DcSweep, ...]`; `DcSweep(source, source_span, start, stop, increment, span, variation, values, file)`; the last three are LTspice's |
| `OpDirective` | — |
| `OptionsDirective` | `options: tuple[OptionItem, ...]`; `OptionItem(name, name_span, value: Value \| Identifier \| None, span)` |
| `TempDirective` | `value`, `others` (LTspice's further values) |
| `IcDirective`, `NodesetDirective` | `conditions: tuple[NodeCondition, ...]`; `NodeCondition(node: Node \| None, value, span, current)`, `node is None` for `all=` or for an LTspice `.ic i(L1)=…` (`current: ElementReference`) |
| `SaveDirective` | `vectors: tuple[OutputVector, ...]`; `OutputVector(text, span, function: str \| None, nodes: tuple[Node, ...], source: ElementReference \| None)` |
| `MeasureDirective` | `analysis`, `analysis_span`, `result`, `result_span`, `body_text`, `body_span` |
| `StepDirective` (LTspice) | `kind: "param" \| "source" \| "temp" \| "model"`, `name`, `name_span`, `model_type`, `model`, `variation`, `variation_span`, `start`, `stop`, `increment`, `values`, `file` |
| `GlobalDirective` | `nodes: tuple[Node, ...]`; not a `Directive` subclass, because it is topology |
| `Title` | `text`, `explicit` (written `.title`), `span` |
| `TitleDirective` | `text`, `span`; a `.title` after the first line |
| `BlankLine` | `span` |
| `CommentLine` | `text`, `span` |
| `UnknownDirective` | `name`, `raw`, `span`, `trailing_comments`, `name_span` |
| `OpaqueBlock` | `kind: "control" \| "if"`, `span` |
| `OpaqueStatement` | `kind: "include" \| "lib"`, `raw`, `span`, `trailing_comments` |
| `End` | `span` |

Values are `Value` (`NumericValue | Formula`, M3); `Identifier(name, span)` is new, for an
option value such as `gear`. `ParamAssignment` (M3) serves `.param`, `.model` parameters and
`.subckt` defaults. `BodyItem` is the union of items allowed in a body; `TopLevelItem` adds
`Title`, `TitleDirective`, `End` and the directives. Deviations from task 3.1: `Identifier`
(decision 0005 item 6), `DcSweep.span`, `EndsLine.trailing_comments`, and `SubcktDefinition`
also carries the keyword fields.

## 2. Spec IDs (T9)

`NG-PRM-001` `.param` · `NG-MOD-001` `.model` · `NG-SBD-001` `.subckt`/`.ends` and body rules ·
`NG-TRN-001` · `NG-ACA-001` · `NG-DCA-001` · `NG-OPP-001` · `NG-OPT-001` · `NG-TMP-001` ·
`NG-ICN-001` `.ic`/`.nodeset` · `NG-SAV-001` · `NG-MEA-001`. `NG-STR-001` (`body_line`,
`top_statement`), `NG-OPA-001` (`.control` top level only) and `NG-DIR-001` (`.ends` is a
stray terminator) were updated.

## 3. Grammar (form → rule → fields)

Fields reuse the M3 separator design: each field rule starts with its gap (`SEP`, `CSEP`,
`BS_CONT`, after optional comments and continuations), so `x_name`, `value`, `param` and
`x_param` are shared with element lines. Every statement ends with `NL` or `eol`.

| Manual form | Rule | Fields |
|---|---|---|
| `.param <ident> = <expr> …` (§2.11.1) | `param_stmt: PARAM_KW param_def+ …` | `assignments` |
| bare expression (§2.11.1) | `bare_value`, `bare_tail` | `ParseError` at the value |
| `.model mname type(pname=pval …)` (§2.5), unparenthesized (§3.2.2) | `model_stmt: MODEL_KW x_name x_name (param* \| model_paren)` | `name`, `model_type`, `params`, `parenthesized` |
| `.SUBCKT subnam N1 … <ident>=<value> …` (§2.6.1, §2.11.3) | `subckt_header: SUBCKT_KW x_name subckt_port+ x_param*` | `name`, `ports`, `params` |
| body | `subckt_def: subckt_header subckt_item* ends_line` | `body`, `header_span` |
| statements not allowed in a body | `not_in_subckt` | `ParseError` at the keyword |
| `.ENDS <SUBNAM>` (§2.6.2) | `ends_line: ENDS_KW x_name?` | `ends` |
| `.tran tstep tstop <tstart <tmax>> <uic>` (§11.3.10) | `tran_stmt: TRAN_KW value value (value value?)? uic?` | values in order, `uic` |
| `.ac dec\|oct\|lin n fstart fstop` (§11.3.1) | `ac_stmt: DOT_AC_KW ac_variation value value value` | `variation`, `points`, `fstart`, `fstop` |
| `.dc src start stop incr [src2 …]` (§11.3.2) | `dc_stmt: DOT_DC_KW dc_sweep dc_sweep?`; `dc_sweep: x_name value value value` | `sweeps` |
| `.op` (§11.3.5) | `op_stmt: OP_KW` | — |
| `.options opt opt=val …` (§11.1) | `options_stmt: (OPTIONS_KW \| OPTION_KW) option_item+` | `options` |
| `.temp value` (§2.14) | `temp_stmt: TEMP_KW value` | `value` |
| `.ic v(n)=val …` (§11.2.2), `.nodeset … \| all=val` (§11.2.1) | `ic_stmt`, `nodeset_stmt`; `node_condition: … V_OPEN WORD RPAR EQ …`; `nodeset_all` | `conditions` |
| `.save vector …` (§11.6.1) | `save_stmt: SAVE_KW output_vector+` | `vectors` |
| `V(N1<,N2>)`, `VR`/`VI`/`VM`/`VP`/`VDB`, `I(src)` (§11.6.2) | `voltage_vector: VOLTAGE_OPEN WORD (CSEP WORD)? RPAR`; `current_vector` | `function`, `nodes` or `source`; `IR` … `IDB` rejected |
| `.meas {DC\|AC\|TRAN\|SP} result …` (§11.4) | `meas_stmt: (MEAS_KW \| MEASURE_KW) meas_analysis x_name meas_body` | `analysis`, `result`, `body_text` |

## 4. Spans

- Item spans tile the source as before: from the end of the previous item to the end of the
  statement's last `NL`, so they include leading blanks, continuation lines and comments.
- In a `SubcktDefinition`, `header_span` runs from `span.start` to the end of the header line
  (with its continuations), the `body` items tile from there to `ends.span.start`, and
  `ends.span` runs to `span.end`. The same holds recursively for nested definitions.
- Sub-spans cover exactly their text, never a separator: `keyword_span`; every name span
  (`.param`/`.model`/default parameter names, model name and type, subcircuit name, ports,
  `.ends` name, `.dc` source, option names, `.ic` nodes, `.meas` analysis and result); every
  value span (with formula delimiters); each `OutputVector.span` (from the function to `)`,
  blanks inside included, so `text` is its slice) and its node or source spans; the `uic` flag;
  `variation_span`. `ParamAssignment.span`, `OptionItem.span`, `NodeCondition.span` (from `v(`
  or `all`) and `DcSweep.span` run from their first to their last token. `body_span` runs
  from the first to the last text token of the `.meas` body.
- **What M6 replaces:** `.param` values (`assignments[i].value.span`), `.model` parameter values,
  directive arguments (the value spans above, `variation_span`, option values, condition
  values), and whole directive lines (`span`) for replace and remove (architecture §7.2).
  Names, ports and `.subckt` structure are topology or identity and are not edited.

## 5. LTspice

The rules are in [decision 0009](../decisions/0009-ltspice-dialect.md) items 4, 5, 11 and 12, and the syntax facts in [docs/grammars/ltspice/](../grammars/ltspice/README.md). What differs:

- **Spec IDs:** `LT-PRM-001`, `LT-MOD-001`, `LT-SBD-001`, `LT-TRN-001`, `LT-ACA-001`, `LT-DCA-001`, `LT-OPP-001`, `LT-OPT-001`, `LT-TMP-001`, `LT-ICN-001`, `LT-SAV-001`, `LT-MEA-001`, `LT-STP-001`, `LT-GLB-001`, `LT-STR-001`, `LT-OPA-001`, `LT-DIR-001`, `LT-END-001`, `LT-MCH-001`.
- **`.end`** is required, with only blank lines after it (a deliberate exception, decision 0009 item 4).
- **Dot-commands** are a closed list. Anything else is a `ParseError`, including `.control` and `.if`. `.machine` is an `UnsupportedConstruct`.
- **`.tran`** may have one argument (`tstep` is then `None`) and modifiers.
- **`.ac`** also has `list` and `file=`; **`.dc`** a variation per sweep, up to three sweeps, and `list` or `file=` on the last; **`.temp`** a list.
- **`.param`** also has `.param x 3k` and bare expressions, which give a `Formula` with an empty `delimiter`.
- **`.model`** has `ako:`, and a string or bare word for `mfg` and `type` only.
- **`.ic`** has `i(L1)=value`; **`.meas`** may omit the analysis, and has `noise` and `op`; **`.save`** has device currents and wildcards.
- **`.step`** is a typed node, with no limit on nesting. A parameter swept by `.step param` counts as defined.
