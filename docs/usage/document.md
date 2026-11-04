# Reading a netlist: lines, references, nets and diagnostics

This guide describes ngspice; [LTspice](#ltspice) differs as noted at the end. `Netlist` is the read-only document layer. It parses a netlist with an explicit dialect
and answers queries about its lines, symbol tables, references, topology and diagnostics.
Editing and `save()` are described in [editing.md](./editing.md) (M6). The rules behind the answers are in
[names.md](../grammars/ngspice/names.md) and [scoping.md](../grammars/ngspice/scoping.md);
the API is listed in [document-layer.md](../design/document-layer.md). The examples below are
executed by the test suite.

## Load

```python
>>> from netlistmod import Dialect, Netlist
>>> text = (
...     "amplifier\n"
...     ".global vcc\n"
...     ".param rload=10k\n"
...     "VCC vcc 0 DC 5\n"
...     "VIN IN 0 DC 1\n"
...     "XA in out amp g=3\n"
...     "RL out GND {rload}\n"
...     ".subckt amp a y g=2\n"
...     "R1 a mid 1k\n"
...     "R2 mid y {g*1k}\n"
...     "R3 vcc mid 100k\n"
...     ".ends amp\n"
...     ".op\n"
...     ".end\n"
... )
>>> netlist = Netlist.from_text(text, dialect=Dialect.NGSPICE)
>>> netlist.to_bytes() == text.encode("utf-8")
True

```

`Netlist.load(path, dialect=...)` reads a file as bytes and keeps its encoding, BOM and line
endings; `Netlist.from_source(source, dialect=...)` takes a `SourceText`. The dialect is always
required; `rkm=True` accepts RKM values such as `2k7`.

## Lines

A line is one logical item: a statement with its continuation lines and comments, a comment
line, a blank line or an opaque block. A subcircuit definition is one line with a `body`.

```python
>>> [type(line.item).__name__ for line in netlist.lines]  # doctest: +NORMALIZE_WHITESPACE
['Title', 'GlobalDirective', 'ParamStatement', 'VoltageSource', 'VoltageSource',
 'SubcktInstance', 'Resistor', 'SubcktDefinition', 'OpDirective', 'End']
>>> from netlistmod import Resistor, SubcktDefinition
>>> amp = netlist.lines.find(SubcktDefinition)
>>> amp.first_line, amp.last_line
(8, 12)
>>> [(line.scope, line.item.designator) for line in netlist.lines.find_all(Resistor, recursive=True)]
[((), 'RL'), (('amp',), 'R1'), (('amp',), 'R2'), (('amp',), 'R3')]
>>> point = netlist.lines.insert_after(amp)  # a zero-width span at a physical line boundary
>>> point.is_empty, netlist.text[point.start :]
(True, '.op\n.end\n')

```

## Elements and references

Scopes are subcircuit **definitions**, addressed by a tuple of names: `()` is the top level and
`("amp",)` the body of `.subckt amp`, shared by every instance. Names compare case-insensitively.

```python
>>> netlist.element("r2", scope=("AMP",)).value.text
'g*1k'
>>> [(ref.kind, ref.name, ref.scope, type(ref.target).__name__) for ref in netlist.references]
... # doctest: +NORMALIZE_WHITESPACE
[('subckt', 'amp', (), 'SubcktDefinition'),
 ('subckt_param', 'g', (), 'ParamAssignment'),
 ('param', 'rload', (), 'ParamAssignment'),
 ('param', 'g', ('amp',), 'ParamAssignment')]
>>> [netlist.slice(ref.span) for ref in netlist.references_to_param("RLOAD")]
['rload']

```

## Nets and connections

`0` and `gnd` are one ground net; a net inside a definition is local to it unless it is ground,
a port or a `.global` node.

```python
>>> [(net.name, net.scope) for net in netlist.nets()]
[('vcc', ()), ('0', ()), ('in', ()), ('out', ())]
>>> [(net.name, net.scope) for net in netlist.nets(("amp",))]
[('a', ('amp',)), ('y', ('amp',)), ('mid', ('amp',)), ('vcc', ())]
>>> netlist.topology.net("gnd").spellings
('0', 'GND')
>>> [element.designator for element in netlist.elements_on_net("in")]
['VIN', 'XA']

```

Queries are per definition scope: even for a `.global` net, `elements_on_net` lists only the
elements of the scope asked for.

```python
>>> [e.designator for e in netlist.elements_on_net("vcc")]
['VCC']
>>> [e.designator for e in netlist.elements_on_net("vcc", ("amp",))]
['R3']
>>> [(c.terminal, c.node.name, c.net.name) for c in netlist.connections("XA")]
[(0, 'in', 'in'), (1, 'out', 'out')]
>>> [net.name for net in netlist.ports("amp")]
['a', 'y']

```

## Diagnostics

Diagnostics are data, computed once at load, never raised.

```python
>>> broken = Netlist.from_text(
...     "t\nR1 a b {rx}\n.param rx=1k\nD1 b 0 dm\nX1 a b c div\n"
...     ".subckt div p q\n.ends\n.print op v(a)\n.end\n",
...     dialect=Dialect.NGSPICE,
... )
>>> for d in broken.diagnostics:
...     print(d.line, d.column, d.code.value, d.severity)
2 9 PARAM_USED_BEFORE_DEFINITION warning
4 8 UNRESOLVED_MODEL warning
5 10 SUBCKT_PORT_MISMATCH warning
8 1 UNTYPED_DIRECTIVE_PRESERVED info
>>> broken.diagnostics[1].message
'model `dm` is not defined (searched: top level)'

```

## Topology signature

The signature holds the exact text of every topology token. Formatting, comments, values,
parameters and other directives do not change it; a renamed node, even by case only, does.

```python
>>> reformatted = Netlist.from_text(
...     text.replace("RL out GND {rload}", "RL  out  GND\n+ 22k ; load"),
...     dialect=Dialect.NGSPICE,
... )
>>> reformatted.signature() == netlist.signature()
True
>>> renamed = Netlist.from_text(text.replace("GND", "gnd"), dialect=Dialect.NGSPICE)
>>> renamed.signature() == netlist.signature(), renamed.nets() == netlist.nets()
(False, True)
>>> len(netlist.signature().digest())
64

```

## Limits

Elements, models and parameters inside `.if` and `.lib` blocks and `.include`/`.lib` files are not
seen (§7.8). An unresolved reference in a scope with any of these is reported as `info`. A
name defined only inside an `.if` block is reported as a warning, although the solver may see it.
`references_to_param` does not see `.meas` bodies, unknown dot-commands such as `.func`, or opaque
items, so an empty answer does not prove that a parameter is unused.
Formula names are found by a grammar (`NG-FML-001`); a formula it cannot parse gives no
references. A read-only demo is in [examples/read_only_demo.py](./examples/read_only_demo.py).

## LTspice

The API is the same. Names compare by Unicode case folding, `0` and `GND` are ground, and `$G_*` nodes are global ([LTspice names](../grammars/ltspice/names.md), [LTspice scoping](../grammars/ltspice/scoping.md)).

```python
>>> lt = Netlist.from_text(
...     "t\nR1 $G_vdd GND 1k\nX1 a s\n.subckt s p\nR1 p $g_VDD 1k\n.ends\n"
...     ".step param rx 1 2 1\nR2 a 0 {rx}\n.end\n",
...     dialect=Dialect.LTSPICE,
... )
>>> [net.global_ for net in lt.nets() if net.name.startswith("$g")]
[True]
>>> [net.name for net in lt.nets()][:2]
['$g_vdd', '0']
>>> lt.diagnostics  # rx is defined by the .step
()

```

The diagnostics that report RKM values are not used, and `NODE_INTO_INSTANCE` is LTspice's own; see the [error reference](./errors.md).
