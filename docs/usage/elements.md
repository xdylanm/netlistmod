# Parsing element lines

This guide describes ngspice; [LTspice](#ltspice) differs as noted at the end. The parser turns the phase 1 element lines into typed nodes: `Resistor`,
`Capacitor`, `Inductor`, `MutualCoupling`, `VoltageSource`, `CurrentSource`, `Diode` and
`SubcktInstance`, all subclasses of `Component`. Each node keeps the text of every value and
a span for every field. The library never evaluates a value.

```python
>>> from netlistmod import Dialect, ParseError, SourceText, parse
>>> source = SourceText("Divider\nV1 in 0 DC 3\nR1 in out 2k7 ; top\nR2 out 0 {rbot}\n.end\n")

```

`2k7` is RKM notation. ngspice reads it as 2.7k only in LT compatibility mode (otherwise it
silently reads 2k), so the parser rejects it unless you pass `rkm=True`:

```python
>>> try:
...     parse(source, Dialect.NGSPICE)
... except ParseError as error:
...     print(error.line, error.column)
3 11
>>> result = parse(source, Dialect.NGSPICE, rkm=True)
>>> r1 = result.items[2]
>>> r1.designator, [node.name for node in r1.nodes]
('R1', ['in', 'out'])
>>> r1.value.text, r1.value.notation
('2k7', 'rkm')
>>> source.text[r1.value.span.start : r1.value.span.end]
'2k7'
>>> [source.text[span.start : span.end] for span in r1.trailing_comments]
['; top']
>>> result.items[3].value.text, result.items[3].value.delimiter
('rbot', '{')
>>> v1 = result.items[1]
>>> v1.dc.text, v1.dc_keyword, v1.ac is None
('3', True, True)

```

What the parser accepts (details and citations are in
[numbers.md](../grammars/ngspice/numbers.md) and the
[spec entries](../grammars/ngspice/specs/)):

- **Fields** are separated by blanks, a single comma, or a `+` continuation line. Blanks may
  surround `=`. Every line of a continued element may end in a `;`, `$` or `//` comment.
- **Values** are numbers with optional scale factors and trailing letters (`10k`, `1kOhm`,
  `1µ`), formulas (`{expr}` or `'expr'`), or, with `rkm=True` and for R and C only, RKM values.
  Bare expressions such as `1.1*Rx` are rejected.
- **R, C, L**: a value, a model, or both, then `name=value` parameters; or a keyword value
  (`r=1k`, `c={c0}`, `l='expr'`), recorded in `value_keyword`. Parameter names are not
  checked.
- **K**: two or more inductor names, then the coupling value.
- **V, I**: an optional DC value (with or without `DC`), then an optional `AC` magnitude and
  phase. Stimulus functions (`PULSE`, `SIN`, `PWL`, …) and `DISTOF` raise
  `UnsupportedConstruct` at the keyword.
- **D**: a mandatory model, then parameters and `off`.
- **X**: one or more nodes, the subcircuit name, then parameters. A double-quoted string is
  allowed as a parameter value. `params:` is rejected.

The charge form `C… q='expr'` and every element letter outside the phase 1 set raise
`UnsupportedConstruct`. A malformed element line raises `ParseError` with its line, column,
excerpt and expected tokens.

## LTspice

The nodes are the same. These forms differ ([decision 0009](../decisions/0009-ltspice-dialect.md)):

```python
>>> from netlistmod import Diode, VoltageSource
>>> source = SourceText(
...     "t\n"
...     "R1 a 0 2k7 tc=1,2 noiseless\n"
...     "V1 a 0 3 Rser=1\n"
...     "D1 a 0 dm 2 off\n"
...     ".model dm D\n"
...     ".end\n"
... )
>>> _, r1, v1, d1, *_ = parse(source, Dialect.LTSPICE).items
>>> r1.value.text, r1.value.notation
('2k7', 'rkm')
>>> r1.params[0].value.text, r1.flags[0].name
('1,2', 'noiseless')
>>> v1.params[0].name
'Rser'
>>> d1.area.text, d1.flags[0].name
('2', 'off')

```

- The embedded decimal needs no option, and `M` is milli.
- Each letter's parameter names are a closed list, so a misspelt `Rsr=1` fails at load.
- R, C and L have no model form and no keyword form:

```python
>>> try:
...     parse(SourceText("t\nR1 a 0 rmod\n.end\n"), Dialect.LTSPICE)
... except ParseError as error:
...     print(error.line)
2

```
