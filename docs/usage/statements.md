# Parsing statements and directives

This guide describes ngspice; [LTspice](#ltspice) differs as noted at the end. The parser types `.param`, `.model`, `.subckt` … `.ends` and the
analysis, option and output directives. Every node keeps the text of each value and a span
for each field; the library never evaluates a value. Other dot-commands (`.print`, `.probe`,
`.opt`, `.func`, …) stay `UnknownDirective`, preserved verbatim.

```python
>>> from netlistmod import Dialect, ParseError, SourceText, parse
>>> source = SourceText(
...     "Divider\n"
...     ".param rtop=1k rbot={2*rtop}\n"
...     ".model dm D(is=1e-14\n"
...     "+ n=1.5)\n"
...     ".subckt div a b r2=1k\n"
...     "R1 a b {rtop}\n"
...     "R2 b 0 {r2}\n"
...     ".ends div\n"
...     "V1 in 0 DC 3\n"
...     "X1 in out div r2=3k\n"
...     ".tran 1u 1m uic ; transient\n"
...     ".options reltol=1e-3 method=gear\n"
...     ".end\n"
... )
>>> result = parse(source, Dialect.NGSPICE)
>>> [type(item).__name__ for item in result.items]  # doctest: +NORMALIZE_WHITESPACE
['Title', 'ParamStatement', 'ModelStatement', 'SubcktDefinition', 'VoltageSource',
 'SubcktInstance', 'TranDirective', 'OptionsDirective', 'End']
>>> params = result.items[1]
>>> [(a.name, a.value.text) for a in params.assignments]
[('rtop', '1k'), ('rbot', '2*rtop')]
>>> model = result.items[2]
>>> model.name, model.model_type, model.parenthesized
('dm', 'D', True)
>>> [(p.name, p.value.text) for p in model.params]
[('is', '1e-14'), ('n', '1.5')]

```

A subcircuit definition contains its body. The body items tile the text between the header
and the `.ends` line, whose name is recorded but not checked:

```python
>>> div = result.items[3]
>>> div.name, [port.name for port in div.ports], [(p.name, p.value.text) for p in div.params]
('div', ['a', 'b'], [('r2', '1k')])
>>> [item.designator for item in div.body], div.ends.name
(['R1', 'R2'], 'div')
>>> source.text[div.header_span.start : div.header_span.end]
'.subckt div a b r2=1k\n'
>>> tran = result.items[6]
>>> tran.tstep.text, tran.tstop.text, tran.tstart, tran.uic.name
('1u', '1m', None, 'uic')
>>> [source.text[span.start : span.end] for span in tran.trailing_comments]
['; transient']
>>> [(o.name, o.value.text if hasattr(o.value, "text") else o.value.name)
...  for o in result.items[7].options]
[('reltol', '1e-3'), ('method', 'gear')]

```

The parser follows the manual strictly. A bare `.param` expression, an analysis inside a
subcircuit and a port named `0` are errors, although ngspice runs them
([discrepancies](../grammars/ngspice/discrepancies.md)):

```python
>>> def error(text):
...     try:
...         parse(SourceText(f"t\n{text}\n.end\n"), Dialect.NGSPICE)
...     except ParseError as exc:
...         return exc.line, exc.column, exc.reason
>>> error(".param c = a+1k")
(2, 12, 'bare expression in `.param`: write the expression in braces (`{...}`) or single quotes')
>>> error(".subckt div a b\n.tran 1u 1m\n.ends")[:2]
(3, 1)
>>> error(".subckt div a b\nR1 a b 1k")
(2, 1, 'unterminated `.subckt` block: `.ends` is missing before end of input')

```

What is typed (details and citations are in the [spec entries](../grammars/ngspice/specs/)
and [statements.md](../design/statements.md)):

- **`.param`**: `name=value` assignments separated by blanks. A value is a number, `{expr}`,
  `'expr'` or a `"string"`. `time`, `temper` and `hertz` are reserved.
- **`.model name type`**: parameters with or without parentheses, separated by blanks or a
  comma, continued across lines. The type is not checked.
- **`.subckt name ports [defaults]` … `.ends [name]`**: nested definitions are allowed. A body
  may hold elements, comments, `.param`, `.model`, `.subckt`, `.include`/`.lib`, `.if`
  blocks and unknown dot-commands; the directives below, `.control`, `.title` and `.end` are
  rejected there.
- **`.tran tstep tstop [tstart [tmax]] [uic]`**, **`.ac dec|oct|lin n fstart fstop`**,
  **`.dc src start stop incr [src2 …]`**, **`.op`**, **`.temp value`**.
- **`.options`/`.option`**: `name` or `name=value`; a value may be a name (`method=gear`).
- **`.ic`/`.nodeset`**: `v(node)=value` items; `.nodeset all=value`.
- **`.save`**: vectors kept as text with a span: `name`, `v(n)`, `v(n1, n2)`, the AC forms
  `vr`, `vi`, `vm`, `vp`, `vdb`, `i(src)`, `src#branch`, `@dev[param]`, `all`. The standard
  forms also record `function`, `nodes` or `source`. `ir(…)` … `idb(…)` are rejected.
- **`.meas`/`.measure`**: the analysis (`dc`, `ac`, `tran`, `sp`) and the result name are
  fields; the rest of the statement is kept as `body_text`.

## LTspice

The nodes are the same, with more forms and a typed `.step`, a `StepDirective` ([decision 0009](../decisions/0009-ltspice-dialect.md)):

```python
>>> source = SourceText(
...     "t\n"
...     ".param a 3k\n"
...     ".tran 1m\n"
...     ".ac list 1 10 100\n"
...     ".step param a 1 3 1\n"
...     ".model slow ako:fast D\n"
...     ".model fast D\n"
...     ".end\n"
... )
>>> _, param, tran, ac, step, slow, *_ = parse(source, Dialect.LTSPICE).items
>>> param.assignments[0].name, param.assignments[0].value.text
('a', '3k')
>>> tran.tstep, tran.tstop.text
(None, '1m')
>>> [f.text for f in ac.frequencies]
['1', '10', '100']
>>> step.kind, step.name, step.increment.text
('param', 'a', '1')
>>> slow.ako.model_name
'fast'

```

A bare `.param` expression, which ngspice refuses, is accepted: `.param x=2*pi*100` loads, and
`params.set` writes one as given (on ngspice the same edit is an `EditError`). The value is a
`Formula` with an empty delimiter:

```python
>>> from netlistmod import Netlist
>>> lt = Netlist.from_text("t\n.param x=2*pi*100\nR1 a 0 {x}\n.end\n", dialect=Dialect.LTSPICE)
>>> value = lt.params["x"][0].value
>>> type(value).__name__, value.text, value.delimiter
('Formula', '2*pi*100', '')
>>> lt.params.set("x", "2*3").text.splitlines()[1]
'.param x=2*3'

```

Dot-commands outside LTspice's closed list are a `ParseError`, and `.control` and `.if` are among them.
