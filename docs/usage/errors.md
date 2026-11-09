# Errors and diagnostics

The library reports problems in two ways. An **exception** means the requested parse or edit did not happen, and nothing was written. A **diagnostic** is a finding about a netlist that did load; it is data and is never raised. This page covers both dialects, and the examples are executed by the test suite. The rules are in architecture §17.

```python
>>> from pathlib import Path
>>> from tempfile import TemporaryDirectory
>>> from netlistmod import Dialect, Netlist, SourceText, parse
>>> def report(text, dialect=Dialect.NGSPICE, **options):
...     for d in Netlist.from_text(text, dialect=dialect, **options).diagnostics:
...         print(d.line, d.column, d.code.value, d.severity)

```

## Exceptions

All of these derive from `SpiceNetlistError`, so one `except` can catch them.

### `SpiceNetlistError`

The base class. It is never raised itself.

```python
>>> from netlistmod import EditError, SpiceNetlistError
>>> issubclass(EditError, SpiceNetlistError)
True

```

### `ParseError`

The text does not match the dialect's grammar. The library does not guess: it stops at the first error. `line` and `column` are 1-based, `excerpt` shows the line with a caret, and `expected` names what would have been valid there.

```python
>>> from netlistmod import ParseError
>>> try:
...     parse(SourceText("title\nR1 a 0 1k\n"), Dialect.NGSPICE)
... except ParseError as error:
...     print(error.line, error.column)
2 11

```

`reason` adds a sentence where the library can say more. A line that ends before its fields do says so, and `expected` then leaves out separators and comments, which would not help. Text after `.end` is told that the netlist ends there. Some forms that a solver runs and the library refuses on purpose name the form to write instead, such as a positional area on an ngspice Q ([decision 0014](../decisions/0014-transistors.md) item 5) or `gain=` on a dependent source ([decision 0015](../decisions/0015-controlled-sources.md) item 6).

```python
>>> try:
...     parse(SourceText("title\nQ1 c b e qm 2\n.end\n"), Dialect.NGSPICE)
... except ParseError as error:
...     print(error.column, error.reason)
13 `2` after the model is a positional area, and an ngspice Q writes its area as `area=2`
>>> try:
...     parse(SourceText("title\nE1 out 0 in 0 gain=2\n.end\n"), Dialect.NGSPICE)
... except ParseError as error:
...     print(error.column, error.reason)
15 `gain=` is not a form of the ngspice manual §4.2: write the gain positionally, as the value after the nodes (`E1 out 0 in 0 2`) or after the controlling source (`F1 out 0 Vs 2`)
>>> try:
...     parse(SourceText("title\nR1 a 0\n.end\n"), Dialect.NGSPICE)
... except ParseError as error:
...     print(error.reason)
this line ends too early
>>> try:
...     parse(SourceText("title\n.end\nR1 a 0 1k\n"), Dialect.NGSPICE)
... except ParseError as error:
...     print(error.reason)
the netlist ends at `.end`: only blank lines may follow it

```

**What to do:** correct the line, or check that the right dialect is selected. If a solver accepts the line, the dialect's `discrepancies.md` under `docs/grammars/` may list it as a deliberate difference.

### `UnsupportedConstruct`

The dialect has this construct, but the library does not support it yet. It is separate from `ParseError` so that a caller can tell "not yet" from "wrong".

```python
>>> from netlistmod import UnsupportedConstruct
>>> try:
...     parse(SourceText("title\nT1 a 0 b 0 z0=50 td=1n\n.end\n"), Dialect.NGSPICE)
... except UnsupportedConstruct as error:
...     print(error.line, error.column)
2 1

```

**What to do:** the library supports R, C, L, K, V, I, D, X, the transistors Q, M, J and Z, and the linear forms of E, F, G, H, S and W, with DC, AC and source functions. Other letters wait for later phase 2 milestones; ngspice's `LAPLACE` is a `ParseError`, because ngspice does not offer it. There is no way to skip the line.

### `EditError`

The edit cannot be applied: the target does not exist or is ambiguous, the value is the wrong kind, or the new text would not land as one value. The original netlist is unchanged.

```python
>>> netlist = Netlist.from_text("t\nR1 a 0 1k\n.end\n", dialect=Dialect.NGSPICE)
>>> try:
...     netlist.set_value("R9", "2k")
... except EditError as error:
...     print(type(error).__name__)
EditError

```

In a batch, a second upsert of one target is an `EditError` when it is submitted, even if the target does not exist yet. Each operation in a batch is computed against the netlist the batch was opened on, so the two would otherwise each add the target, and one of the duplicates can stop a solver. The first one stays in the batch.

```python
>>> with netlist.batch() as batch:
...     batch.set_param("R1", "m", "1")
...     try:
...         batch.set_param("R1", "m", "2")
...     except EditError as error:
...         print(error)
set_param R1 m in top level: this batch already sets this target, and each operation is computed against the netlist the batch was opened on; make one upsert per target
>>> batch.result.text
't\nR1 a 0 1k m=1\n.end\n'

```

**What to do:** read the message, which names the operation and the target. For a repeated upsert, keep the one you mean, or apply the batch and edit its result. The operations and their errors are listed in [edit-layer.md](../design/edit-layer.md).

### `TopologyError`

The operation is not permitted, because it would change the circuit: for example removing an element or `.global`, or adding an element through the directive API.

```python
>>> from netlistmod import TopologyError
>>> try:
...     netlist.directives.add("R2 a 0 1k")
... except TopologyError as error:
...     print(type(error).__name__)
TopologyError

```

**What to do:** nothing in this library changes topology, by design (P4). Change the schematic or the source file by other means, and load it again.

### `TopologyViolation`

A write-time check failed: a plan passed to `apply` changed the topology signature, changed text outside its edits, or cut into an opaque block. Nothing is written.

```python
>>> from netlistmod import Edit, Span, TopologyViolation
>>> try:
...     netlist.apply([Edit(netlist.element("R1").nodes[0].span, "b")])
... except TopologyViolation as error:
...     print(type(error).__name__)
TopologyViolation

```

**What to do:** the public edit methods do not cause this, so look at the hand-built plan.

### `EncodingError`

The bytes could not be decoded, or the edited text cannot be written in the file's encoding. The file is left unchanged.

```python
>>> from netlistmod import EncodingError
>>> folder = TemporaryDirectory()
>>> path = Path(folder.name) / "latin.cir"
>>> _ = path.write_bytes("caf\xe9\nR1 a 0 1k\n.end\n".encode("cp1252"))
>>> loaded = Netlist.load(path, dialect=Dialect.NGSPICE)
>>> loaded.source.encoding
'cp1252'
>>> try:
...     loaded.set_value("R1", "{漢}").save()
... except EncodingError as error:
...     print(type(error).__name__)
EncodingError
>>> path.read_bytes() == "caf\xe9\nR1 a 0 1k\n.end\n".encode("cp1252")
True
>>> folder.cleanup()

```

**What to do:** use characters the file's encoding has. For a file that fails to decode, pass `fallback_encodings` to `Netlist.load`, or `encoding` to `SourceText.load`.

### Outside `SpiceNetlistError`

A wrong call, as opposed to a problem with the netlist, gets a standard Python exception:

| Exception | When |
|---|---|
| `ValueError` | An unknown dialect; `rkm=True` with `Dialect.LTSPICE`; a `Reference` from another netlist passed to `resolve` |
| `KeyError` | `element`, `scope` or `net` of a name that does not exist (a read, where an edit would give `EditError`) |
| `FileNotFoundError`, `OSError` | `Netlist.load` or `save` on a path that cannot be read or written |
| `RecursionError` | About 300 nested `.if` levels in ngspice (a known limit) |

## Diagnostics

`Netlist.diagnostics` is a tuple of `Diagnostic(code, severity, message, span, line, column)`, computed once at load, in source order. A severity is `warning` (probably a mistake, or the solver will object) or `info` (worth knowing).

### `UNRESOLVED_MODEL`

A model name that no visible `.model` defines. A warning, or `info` when a searched scope has an `.include`, a `.lib`, or an opaque `.if` or `.lib` block, which may define it.

```python
>>> report("t\nD1 a 0 dm\n.end\n")
2 8 UNRESOLVED_MODEL warning

```

**What to do:** add the `.model` or the `.include`. An `.if` block is not read either, so a model defined only there gets this warning.

### `UNRESOLVED_SUBCKT`

An `X` line's subcircuit is not defined. Severity as for `UNRESOLVED_MODEL`.

```python
>>> report("t\nX1 a b sub\n.end\n")
2 8 UNRESOLVED_SUBCKT warning

```

**What to do:** add the definition or the `.include`.

### `UNRESOLVED_PARAM`

A name in a formula that no visible `.param` or default defines. Severity as for `UNRESOLVED_MODEL`.

```python
>>> report("t\nR1 a 0 {rx}\n.end\n")
2 9 UNRESOLVED_PARAM warning

```

**What to do:** define the parameter, or correct the name.

### `UNRESOLVED_ELEMENT`

A `K` inductor, a `.dc` source, a `.save i(...)`, or an `i(...)` in a behavioural expression, that names no element of its scope. Severity as for `UNRESOLVED_MODEL`.

```python
>>> report("t\n.dc V9 0 1 0.1\n.end\n")
2 5 UNRESOLVED_ELEMENT warning

```

**What to do:** correct the designator. An element is looked up in its own scope only.

### `DUPLICATE_DEFINITION`

A name defined twice in one scope. For `.param` it is `info` in ngspice, which uses the last one, and a warning in LTspice, which stops. For `.model` and `.subckt` it is a warning in both.

```python
>>> report("t\n.param x=1\n.param x=2\n.end\n")
3 8 DUPLICATE_DEFINITION info
>>> report("t\n.param x=1\n.param x=2\n.end\n", Dialect.LTSPICE)
3 8 DUPLICATE_DEFINITION warning

```

**What to do:** remove one, unless the repetition is intended.

### `DUPLICATE_ELEMENT`

A designator used twice in one scope, case-insensitively. Edits refuse a repeated designator, because there is no single target.

```python
>>> report("t\nR1 a 0 1k\nr1 b 0 1k\n.end\n")
3 1 DUPLICATE_ELEMENT warning

```

**What to do:** rename one in the source.

### `SUBCKT_PORT_MISMATCH`

An `X` line's node count differs from the definition's port count.

```python
>>> report("t\nX1 a b c div\n.subckt div p q\nR1 p q 1k\n.ends\n.end\n")
2 10 SUBCKT_PORT_MISMATCH warning

```

**What to do:** correct the line or the definition. Solvers stop at this.

### `PARAM_USED_BEFORE_DEFINITION`

A formula uses a parameter that its own scope defines only later in the file. ngspice reads top-level `.param` lines first in some cases but not all, so this is a warning. It is not used for LTspice, where line order does not matter.

```python
>>> report("t\nR1 a b {rx}\n.param rx=1k\n.end\n")
2 9 PARAM_USED_BEFORE_DEFINITION warning

```

**What to do:** move the `.param` above its first use.

### `MODEL_TYPE_MISMATCH`

An element's model resolves to a `.model` whose type the element cannot use.

```python
>>> report("t\nD1 a 0 dm\n.model dm NPN\n.end\n")
2 8 MODEL_TYPE_MISMATCH warning

```

**What to do:** correct the model name or the type.

### `ENDS_NAME_MISMATCH`

The name on `.ends` differs from the `.subckt` name.

```python
>>> report("t\n.subckt a p\nR1 p 0 1k\n.ends b\n.end\n")
4 7 ENDS_NAME_MISMATCH info

```

**What to do:** correct it. The library pairs them by nesting, not by name.

### `DIALECT_GATED_SYNTAX`

An ngspice value in RKM notation, which needs `rkm=True` and `ngbehavior=lt` in ngspice. Not used for LTspice, where it is native.

```python
>>> report("t\nR1 a 0 2k7\n.end\n", rkm=True)
2 8 DIALECT_GATED_SYNTAX info

```

**What to do:** nothing if the file is run with that setting.

### `RKM_SOLVER_MISMATCH`

An ngspice RKM value that ngspice 47 reads differently from the notation's meaning, so the library flags the value and keeps its text.

```python
>>> report("t\nR1 a 0 1M0\n.end\n", rkm=True)
2 8 DIALECT_GATED_SYNTAX info
2 8 RKM_SOLVER_MISMATCH warning

```

**What to do:** write the value without RKM notation; see the ngspice `discrepancies.md`.

### `UNTYPED_DIRECTIVE_PRESERVED`

A dot-command the library does not type. It may well be a documented command, such as ngspice `.print` or LTspice `.backanno`. Its text is kept exactly, and its contents are not read, so references inside it are not seen.

```python
>>> report("t\n.print op v(a)\n.end\n")
2 1 UNTYPED_DIRECTIVE_PRESERVED info

```

**What to do:** nothing, unless it is a misspelling. In ngspice a misspelt `.tarn` lands here; LTspice rejects it at load.

### `NODE_INTO_INSTANCE`

LTspice only. A node named `<instance>:<node>` connects to that node inside the instance, which the library does not model: it treats the name as a net of its own. A warning, or `info` when the definition is in an include.

```python
>>> report("t\nX1 a s\n.subckt s p\nR1 p n 1k\n.ends\nR2 x1:n 0 1k\n.end\n", Dialect.LTSPICE)
6 4 NODE_INTO_INSTANCE warning

```

**What to do:** remember that `nets` and `connections` do not show this join. Edits are not affected.

### `CONTROL_SOURCE_MISMATCH`

An F, H or W line names a controlling source that exists but is not a voltage source. The ngspice manual and the LTspice reference name a voltage source; both solvers also read an E or H there (LTspice an L too) and stop on anything else, and the message says which applies to the source named ([decision 0015](../decisions/0015-controlled-sources.md) item 5). A warning.

```python
>>> report("t\nR1 a 0 1k\nF1 0 b R1 2\nR2 b 0 1k\n.end\n")
3 8 CONTROL_SOURCE_MISMATCH warning

```

**What to do:** sense the current with a 0 V voltage source in series with the element, and name that source.

### `UNRESOLVED_NODE`

A behavioural expression reads a node, as `v(a)` or `v(a,b)`, that no element of its scope connects to and that is not ground, a `.global` node or a subcircuit port. ngspice reports a singular matrix and LTspice "No such node". A warning, or `info` where the scope has an `.include`, `.lib` or opaque block, or where the name reaches into a subcircuit instance of the scope (ngspice `v(x1.n)`, LTspice `V(X1:n)`), which both solvers read and the library does not resolve ([decision 0016](../decisions/0016-behavioral-expressions.md) item 6).

```python
>>> report("t\nR1 a 0 1k\nB1 b 0 V=2*v(nonode)\nR2 b 0 1k\n.end\n")
3 14 UNRESOLVED_NODE warning

```

**What to do:** correct the node name. Inside a subcircuit, a top-level net is not visible: pass it in as a port, or make it `.global`. `Netlist.expression_reads` lists what an expression reads.
