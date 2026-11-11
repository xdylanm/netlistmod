# Parsing element lines

This guide describes ngspice; [LTspice](#ltspice) differs as noted at the end. The parser turns element lines into typed nodes: `Resistor`,
`Capacitor`, `Inductor`, `MutualCoupling`, `VoltageSource`, `CurrentSource`, `Diode`,
`BipolarTransistor`, `Mosfet`, `Jfet`, `Mesfet` and `SubcktInstance`, all subclasses of `Component`. Each node keeps the text of every value and
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
  phase, and a source function in `stimulus` (`PULSE`, `SIN`, `PWL`, …), before or after them.
  `distortion` holds ngspice's `DISTOF1` and `DISTOF2`. A function needs its parentheses, and its
  arguments are numbers or formulas.
- **D**: a mandatory model, then parameters and `off`.
- **X**: one or more nodes, the subcircuit name, then parameters. A double-quoted string is
  allowed as a parameter value. `params:` is rejected.

## Transistors

Q, M, J and Z lines become `BipolarTransistor`, `Mosfet`, `Jfet` and `Mesfet`, subclasses of
`Transistor`, which holds the fields they share ([decision 0014](../decisions/0014-transistors.md)). After the three fixed nodes, the model is
the last name before any area, flag or parameter, so the names in between are nodes:

```python
>>> source = SourceText(
...     "t\n"
...     "Q1 c b e s qn off area=2\n"
...     "M1 d g s tj tc vd thermal\n"
...     "J1 d g s jn 2\n"
...     ".model qn NPN\n"
...     ".model vd VDMOS pchan\n"
...     ".model jn NJF\n"
...     ".end\n"
... )
>>> _, q1, m1, j1, *_ = parse(source, Dialect.NGSPICE).items
>>> [node.name for node in q1.nodes], q1.model.model_name, q1.flags[0].name, q1.params[0].name
(['c', 'b', 'e', 's'], 'qn', 'off', 'area')
>>> len(m1.nodes), m1.model.model_name, m1.flags[0].name
(5, 'vd', 'thermal')
>>> j1.area.text
'2'

```

- **Nodes:** Q and M take 3 to 5, J and Z exactly 3. The count is not checked against the
  model's type, so a 3-node NMOS line loads and ngspice stops on it. A node that is not written,
  such as a BJT's substrate, is not added: ngspice grounds it, and the topology lists what the
  line writes.
- **Area:** J and Z take it positionally (`area`), and Q only as `area=`, `areab=` or `areac=`.
- **Model:** a model named with a plain number, or the keyword `off`, is a `ParseError` at it.
- **`.model`:** a bare `pchan` or `nchan` is in `flags`, and a dotted value such as
  `version=3.3.0` is an `Identifier`, never a number.

## Dependent sources and switches

E, G, F and H lines become `Vcvs`, `Vccs`, `Cccs` and `Ccvs` (subclasses of
`ControlledSource`), and S and W lines `VoltageSwitch` and `CurrentSwitch` (subclasses of
`Switch`) ([decision 0015](../decisions/0015-controlled-sources.md)). A control is topology: E,
G and S list their control nodes after the output nodes, and F, H and W name their controlling
sources in `control`, a tuple: one source for the linear form, N for `POLY`, none for LTspice's
`value=` ([decision 0017](../decisions/0017-tables-polynomials-and-transfer-functions.md)).

```python
>>> source = SourceText(
...     "t\n"
...     "E1 out 0 in 0 2\n"
...     "F1 0 out Vsense 3 m=2\n"
...     "S1 out 0 in 0 sm OFF\n"
...     ".model sm SW vt=0.5\n"
...     ".end\n"
... )
>>> _, e1, f1, s1, *_ = parse(source, Dialect.NGSPICE).items
>>> [node.name for node in e1.control_nodes], e1.value.text
(['in', '0'], '2')
>>> [source.designator for source in f1.control], f1.value.text, f1.params[0].name
(['Vsense'], '3', 'm')
>>> s1.model.model_name, s1.flags[0].name
('sm', 'OFF')

```

- **Gain:** one value, a number or a formula. `gain=2` and a second value are refused.
- **`m=`:** on F and G only.
- **Switches:** the model is mandatory; the state is `on`, `off` or absent, never both.
- **Controlling source:** found in the line's own scope only. One that is missing gives `UNRESOLVED_ELEMENT`, and one that is not a voltage source gives `CONTROL_SOURCE_MISMATCH`.
- **Expression forms:** E `vol=` and G `cur=` (in quotes or braces), and `value` on both, load
  with `value` `None`, the expression in `expression` and the keyword in `form`.
- **Nonlinear forms** (decision 0017): `value` is `None` and `form` is `"table"`, `"poly"`,
  `"laplace"`, `"freq"`, `"and"`, `"or"`, `"nand"` or `"nor"`. `table` holds the points of
  ngspice `TABLE`, `FREQ` and the gates and of LTspice `table=` (`Table`: `points`, `layout`,
  `format`; `TablePoint.values`), `dimension` is POLY's or a gate's `N`, and `coefficients` are
  POLY's. `expression` is the formula a line writes (`TABLE {expr}`, `FREQ {expr}`, `Laplace=`), and
  `None` for the four-node `TABLE`, `table=`, POLY and the gates, which read their control nodes.
  POLY's control nodes follow the output pair in `nodes`, and its controlling sources are `control`;
  both are counted from `N`, which must be an integer literal. `window=`, `nfft=`, `mtol=` and `m=`
  are in `params`. The points of an ngspice `TABLE` are numbers; a bare expression there, a net
  named `table`, a gate whose inputs are not `2N`, a `FREQ` first frequency of several characters
  right after its `(` (write `( 1e7, ...)`) and `FREQ` format words that contradict each other are
  refused, because the solver stops or reads them differently (`discrepancies.md`).

## Behavioural sources and expressions

A B line becomes a `BehavioralSource`, with its `quantity` and `expression`
([decision 0016](../decisions/0016-behavioral-expressions.md)). The expression may be in braces,
in quotes, or bare; a bare one runs to the line end or the first trailing parameter, and may
hold blanks and continuations. A capacitor's charge form `q=` is in `charge`.

```python
>>> source = SourceText(
...     "t\n"
...     "B1 out 0 V = 2 * v(in) tc1=1m\n"
...     "B2 0 out i={1m*v(in)}\n"
...     "C1 in 0 q='1n*v(in)'\n"
...     ".end\n"
... )
>>> _, b1, b2, c1, *_ = parse(source, Dialect.NGSPICE).items
>>> b1.quantity, b1.expression.text, b1.expression.delimiter, b1.params[0].name
('v', '2 * v(in)', '', 'tc1')
>>> b2.quantity, b2.expression.text, b2.expression.delimiter
('i', '1m*v(in)', '{')
>>> c1.value, c1.charge.text
(None, '1n*v(in)')

```

- **One quantity:** `v=` or `i=` (on LTspice also `R=` and `P=`); two, or none, are refused.
- **What an expression reads** is not topology: `Netlist.expression_reads` lists it, and a
  node no element connects to gives `UNRESOLVED_NODE`.

Every element letter of both dialects is supported. An ngspice U line that is not a URC line is
the digital U, which raises `UnsupportedConstruct` (out of scope for v1). A malformed element line
raises `ParseError` with its line, column, excerpt and expected tokens.

## Transmission lines

T (lossless), O (lossy, LTRA) and U (uniform RC) load on both dialects, and Y (TXL) and P (CPL)
on ngspice ([decision 0019](../decisions/0019-transmission-lines.md)). Each is a
`TransmissionLine`; every node is topology, and the named parameters are in `params`.

```python
>>> from netlistmod import Dialect, LosslessLine, Netlist
>>> text = (
...     "t\nT1 a 0 b 0 Z0=50 TD=1n\nO1 a 0 c 0 lmod\nP1 a1 a2 0 b1 b2 0 pmod len=2\n"
...     ".model lmod ltra r=1 l=50n c=20p len=1 nosteplimit\n"
...     ".model pmod cpl length=1 R=1 0 1 L=50n 5n 50n G=0 0 0 C=20p -2p 20p\n.end\n"
... )
>>> netlist = Netlist.from_text(text, dialect=Dialect.NGSPICE)
>>> t1 = netlist.element("T1")
>>> isinstance(t1, LosslessLine), [node.name for node in t1.port2]
(True, ['b', '0'])
>>> p1 = netlist.element("P1")
>>> p1.conductors, p1.model.model_name, [(p.name, p.value.text) for p in p1.params]
(2, 'pmod', [('len', '2')])
>>> [flag.name for flag in netlist.models["lmod"][0].flags]
['nosteplimit']
>>> netlist.models["pmod"][0].params[1].value.text
'1 0 1'

```

- **T** takes `Z0=` (or `Zo=`, the same parameter on both dialects), then `TD=`, or `F=` with an
  optional `NL=`, and on ngspice `IC=`, four comma-separated values. `Z0=` and exactly one length
  form must be given. LTspice T takes only `Zo=` (or `Z0=`) and `Td=`.
- **O** takes four nodes and an LTRA model, and nothing after it.
- **U** is a URC line: three nodes, a URC model, `l=` (required) and `n=`. Any other ngspice U
  line is the digital U, which raises `UnsupportedConstruct`: it is out of scope for v1.
- **Y** and **P** take an optional `len=`. Their reference nodes (Y's second and fourth, and
  each P port's last) must be ground, since ngspice ignores them. P holds one to eight lines:
  2X+2 nodes, then the model.
- **`.model`:** an ngspice LTRA model takes LTRA's flags (`nosteplimit` and the others of
  §6.2.1), and a CPL model's `R=`, `L=`, `G=` and `C=` take a list of values (a `ValueList`).

## Code models, OSDI devices and frequency analysis

ngspice's A lines are XSPICE code models and its N lines OSDI (Verilog-A) devices; LTspice's A
lines are special functions, `@` its frequency response analyzer and `&` the analyzer's probe
([decision 0020](../decisions/0020-special-and-mixed-signal-devices.md)).

```python
>>> from netlistmod import CodeModelDevice
>>> text = (
...     "t\nV1 in 0 1\nVs in x 0\na1 %v [in1 %vd(in2 0)] out sum\na2 %vnam Vs [~d null] g\n"
...     "N1 out 0 rmod w=1u\n.model sum summer(in_gain=[2.0 1.0] fraction=FALSE)\n"
...     ".model rmod r2_cmc(rsh=200)\n.end\n"
... )
>>> netlist = Netlist.from_text(text, dialect=Dialect.NGSPICE)
>>> a1 = netlist.element("a1")
>>> isinstance(a1, CodeModelDevice), [node.name for node in a1.nodes], a1.model.model_name
(True, ['in1', 'in2', '0', 'out'], 'sum')
>>> [(c.port_type, [n.name for n in c.nodes]) for c in a1.ports[0].connections]
[(None, ['in1']), ('%vd', ['in2', '0'])]
>>> a2 = netlist.element("a2")
>>> [s.designator for s in a2.control], [(c.inverted, c.null) for c in a2.ports[1].connections]
(['Vs'], [(True, False), (False, True)])
>>> netlist.models["sum"][0].params[0].value.text
'[2.0 1.0]'
>>> netlist.element("N1").model.model_name
'rmod'

```

- **ngspice A** writes its ports, then its model, the last name. A port is a connection or a
  vector `[ … ]`; a connection is an optional port type (`%v`, `%i`, `%vd` … of Table 8.1) and its
  node, two for a differential type, with or without parentheses, or `null`, or `%vnam` and a
  source. `~` inverts a digital node. `nodes` holds every node, without `null` and the `%vnam`
  sources, which are controlling references like F's. A code model takes no parameter on its
  line; its `.model` takes vectors, `TRUE` and `FALSE`, and quoted strings, which a built-in
  type does not.
- **N** writes its nodes, then the model, then the instance parameters. The library does not check
  the node count or the parameter names, which the Verilog-A module defines; ngspice loads the
  module with `pre_osdi` in a `.control` block.
- **LTspice A** writes eight nodes, one of 13 function names (`BUF`, `AND`, `OR`, `XOR`,
  `SCHMITT`, `DFLOP`, `SRFLOP`, `VARISTOR`, `MODULATOR`, `OTA`, `PHASEDET`, `COUNTER`,
  `SAMPLEHOLD`; the reference's symbol names such as INV are not netlist names), then named
  parameters, separated by blanks: a comma is refused, as on every LTspice element line.
- **`@`** writes two nodes, then `zm` and the reference's parameters in any order; `flist=`,
  `pp=`, `nmax=` and `ac=` take a list of blank-separated values; only `ac=` may write its
  magnitude and phase with a comma (`ac=1,0`). `refnode=` and `intnode=` name nets the analyzer measures,
  which are node references, not connections. **`&`** writes four nodes, and measures with the
  `@` of its suffix (`&1` with `@1`).

```python
>>> lt = Netlist.from_text(
...     "t\nA1 in 0 0 0 0 nq q 0 BUF Vhigh=5\n@1 in q fstart=1k fend=10k refnode=in\n"
...     "&1 q 0 in 0\n.end\n",
...     dialect=Dialect.LTSPICE,
... )
>>> a1 = lt.element("A1")
>>> a1.function.name, [n.name for n in a1.outputs], a1.common.name
('BUF', ['nq', 'q'], '0')
>>> lt.element("@1").reference_net.name, lt.element("&1").analyzer.designator
('in', '@1')

```

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
- E, F, G, H, S and W take no parameter. A switch's state may take a value (`off=1`). A controlling source inside an instance (`X1:Vq`), which LTspice reads, is kept as text and is reported as info. `value=`, `POLY`, `table=` and `Laplace=` are read since M15 and M15b.
- Q and M take 3 or 4 nodes, and Q a positional area. Each transistor letter has the reference's
  closed parameter list: Q `temp`; M `L W AD AS PD PS NRD NRS m temp IC`; J `temp`; Z `m temp`;
  and `off`. M has no `thermal` flag, and Z's model may be an IGBT (`NIGBT`, `PIGBT`):

```python
>>> _, q1, z1, *_ = parse(
...     SourceText("t\nQ1 c b e 0 qn 2 temp=30\nZ1 c g e zi\n.model zi NIGBT\n.end\n"),
...     Dialect.LTSPICE,
... ).items
>>> [node.name for node in q1.nodes], q1.area.text, z1.model.model_name
(['c', 'b', 'e', '0'], '2', 'zi')

```

- Each letter's parameter names are a closed list, so a misspelt `Rsr=1` fails at load.
- R, C and L have no model form and no keyword form:

```python
>>> try:
...     parse(SourceText("t\nR1 a 0 rmod\n.end\n"), Dialect.LTSPICE)
... except ParseError as error:
...     print(error.line)
2

```
