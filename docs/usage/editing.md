# Editing a netlist

This guide's examples use ngspice; [LTspice](#ltspice) differs as noted at the end. `netlistmod.Netlist` edits values, parameters and directives in place and writes the netlist
back with a minimal diff, without changing its topology (M6,
[decision 0007](../decisions/0007-edit-lifecycle-and-edit-semantics.md)). Every edit method
returns a **new** netlist that has been re-parsed and verified; the original is unchanged. The
operations, the slots they edit and their errors are listed in
[edit-layer.md](../design/edit-layer.md). The examples below are executed by the test suite.

```python
>>> from netlistmod import Dialect, Netlist
>>> text = (
...     "amplifier\n"
...     "V1 in 0 DC 3\n"
...     "R1 in out 10k ; top\n"
...     "R22 out 0 1k\n"
...     ".tran 1u 5u\n"
...     ".end\n"
... )
>>> netlist = Netlist.from_text(text, dialect=Dialect.NGSPICE)

```

## Set a value

```python
>>> edited = netlist.set_value("R22", "2.2k")
>>> print(edited.text, end="")
amplifier
V1 in 0 DC 3
R1 in out 10k ; top
R22 out 0 2.2k
.tran 1u 5u
.end
>>> netlist.element("R22").value.text  # the original netlist is unchanged
'1k'

```

The value is written as given into exactly the value's span: blanks, comments and the rest of
the line stay as they were. Text that would not land as one value is rejected:

```python
>>> netlist.set_value("R22", "1k 2k")
Traceback (most recent call last):
...
netlistmod.errors.EditError: set_value R22: `1k 2k` does not re-parse as a value; the text would change more than the intended slot

```

## Edit a source's function, DC and AC parts separately

A V or I line has three separate parts, and each operation changes only its own. `set_stimulus`
replaces the function, or adds one after the DC and AC parts. `set_dc` and `set_ac` edit those
parts, and they stay when the function changes.

```python
>>> from netlistmod import Dialect, Netlist
>>> source = Netlist.from_text(
...     "t\nV1 a 0 DC 2 AC 1 SIN(0 1 1k)\nR1 a 0 1k\n.end\n", dialect=Dialect.NGSPICE
... )
>>> print(source.set_stimulus("V1", "PULSE(0 5 1u)").text, end="")
t
V1 a 0 DC 2 AC 1 PULSE(0 5 1u)
R1 a 0 1k
.end
>>> print(source.set_dc("V1", "3").set_ac("V1", "2").text, end="")
t
V1 a 0 DC 3 AC 2 SIN(0 1 1k)
R1 a 0 1k
.end

```

`set_stimulus_arg` sets one argument by 0-based position, or by a name the line writes as
`name=value`, such as a PWL's `td`. A position one past the end appends, and a further one is an
`EditError`, because the library does not invent the arguments between. Argument counts are not
checked: that is the solver's job. `remove_stimulus` removes the function and keeps the rest.

```python
>>> print(source.set_stimulus_arg("V1", 1, "5").set_stimulus_arg("V1", 3, "1u").text, end="")
t
V1 a 0 DC 2 AC 1 SIN(0 5 1k 1u)
R1 a 0 1k
.end
>>> print(source.remove_stimulus("V1").text, end="")
t
V1 a 0 DC 2 AC 1
R1 a 0 1k
.end

```

## Replace a value with a formula and add the `.param`

`set_formula` writes `{expression}`. `params.set` replaces the value of an existing parameter,
or adds a `.param` line after the last one (after the title when there is none). A batch makes
both edits one plan with one verification; if any operation fails, nothing is applied.

```python
>>> with netlist.batch() as batch:
...     batch.set_formula("R1", "Rx")
...     batch.params.set("Rx", "22k")
>>> edited = batch.result
>>> print(edited.text, end="")
amplifier
.param Rx=22k
V1 in 0 DC 3
R1 in out {Rx} ; top
R22 out 0 1k
.tran 1u 5u
.end
>>> [reference.name for reference in edited.references_to_param("rx")]
['Rx']
>>> print(edited.params.set("Rx", "47k").text.splitlines()[1])
.param Rx=47k

```

## Set up an analysis

`directives.set` replaces the one `.tran`, `.ac`, `.dc`, `.op` or `.temp` line of that kind, or
adds one before `.end`. `directives.add` is different: it writes the line it is given even if one of
its kind exists, because ngspice runs two `.ac` or `.dc` lines and gives a plot for each. LTspice stops
on a second analysis, and the library does not check for that. Repeatable directives (`.options`, `.save`, `.ic`, …) are added,
replaced or removed explicitly.

```python
>>> from netlistmod import OpDirective, Placement, TranDirective
>>> edited = netlist.directives.set(".tran 1u 10m").directives.add(".save v(out)")
>>> print(edited.text, end="")
amplifier
V1 in 0 DC 3
R1 in out 10k ; top
R22 out 0 1k
.tran 1u 10m
.save v(out)
.end
>>> tran = edited.lines.find(TranDirective)
>>> print(edited.directives.remove(tran).directives.set(".op").text, end="")
amplifier
V1 in 0 DC 3
R1 in out 10k ; top
R22 out 0 1k
.save v(out)
.op
.end

```

An inserted line takes the line ending of the line before it, so a CRLF file gets CRLF lines.
A placement can also be `Placement.AFTER_TITLE`, `Placement.AFTER_LAST_PARAM` or relative to a
line: `Placement.before(line)` / `Placement.after(line)`, where `line` comes from the netlist
being edited.

## Sweep a parameter across runs

Each run is a separate single-shot netlist; the library never launches a simulator.

```python
>>> import tempfile
>>> from pathlib import Path
>>> base = netlist.set_formula("R22", "rbot")
>>> folder = Path(tempfile.mkdtemp())
>>> for index, value in enumerate(["1k", "2.2k", "4.7k"]):
...     base.params.set("rbot", value).save(folder / f"run{index}.cir")
>>> print((folder / "run1.cir").read_text().splitlines()[1])
.param rbot=2.2k

```

## Add a test harness

Sources, loads and probes are prepared in a separate file by a harness tool; the netlist only
gains an `.include` of it (architecture §7.9). The path is written as given and never read.
ngspice resolves a relative path from the netlist file's folder, not from the working
directory (validated on ngspice 47).

```python
>>> print(netlist.add_include("harness.cir").text.splitlines()[1])
.include "harness.cir"

```

## Edit inside a subcircuit

An element of a definition is addressed by its scope. Editing a definition changes every
instance, so it needs `in_definition=True`; one instance is changed with a parameter override
on its `X` line.

```python
>>> amp = Netlist.from_text(
...     "t\nX1 in out amp\nX2 out o2 amp\n.subckt amp a b g=1\nR1 a b {g*1k}\n.ends\n.end\n",
...     dialect=Dialect.NGSPICE,
... )
>>> amp.set_value("R1", "5k", scope=("amp",))
Traceback (most recent call last):
...
netlistmod.errors.EditError: scope ('amp',) edits the definition of subcircuit `amp`, which changes every instance of it; pass in_definition=True to confirm, or use set_instance_param on an X line to change one instance
>>> print(amp.set_value("R1", "5k", scope=("amp",), in_definition=True).text.splitlines()[4])
R1 a b 5k
>>> print(amp.set_instance_param("X2", "g", "3").text.splitlines()[2])
X2 out o2 amp g=3

```

## Switch a resistor to its semiconductor model

ngspice uses a given value over the model's geometry, so the switch adds the model and its
`l`/`w`, then removes the value (only the value text goes; the blank before it stays).

```python
>>> div = Netlist.from_text(
...     "t\nV1 in 0 DC 3\nR1 in out 1k\nR2 out 0 1k\n.model rmod r rsh=100\n.op\n.end\n",
...     dialect=Dialect.NGSPICE,
... )
>>> with div.batch() as batch:
...     batch.set_model("R2", "rmod")
...     batch.set_param("R2", "l", "20u")
...     batch.set_param("R2", "w", "1u")
>>> print(batch.result.text.splitlines()[3])
R2 out 0 1k rmod l=20u w=1u
>>> print(batch.result.remove_value("R2").text.splitlines()[3])
R2 out 0  rmod l=20u w=1u

```

`set_model_param` also fills empty parentheses: `.model dz d()` becomes `.model dz d(n=1.5)`.

## Edit a transistor

`set_model` checks the new model's type against the letter (an NPN or PNP for Q), and
`set_param` writes `area` where the dialect writes it: positionally for J and Z, as `area=` on
an ngspice Q ([decision 0014](../decisions/0014-transistors.md)).

```python
>>> amp = Netlist.from_text(
...     "t\nV1 c 0 5\nV2 b 0 0.7\nQ1 c b 0 qn\nJ1 c b 0 jn\n"
...     ".model qn NPN\n.model qp PNP\n.model jn NJF\n.op\n.end\n",
...     dialect=Dialect.NGSPICE,
... )
>>> with amp.batch() as batch:
...     batch.set_model("Q1", "qp")
...     batch.set_param("Q1", "area", "2")
...     batch.set_param("J1", "area", "3")
...     batch.set_model_param("jn", "beta", "2m")
>>> print("\n".join(batch.result.text.splitlines()[3:7]))
Q1 c b 0 qp area=2
J1 c b 0 jn 3
.model qn NPN
.model qp PNP
>>> amp.set_model("Q1", "jn")
Traceback (most recent call last):
  ...
netlistmod.errors.EditError: model `jn` has type `NJF`, but `Q1` takes a model of type `NPN`, `PNP`

```

## Edit a dependent source or a switch

The gain of E, F, G and H is the value, and `set_switch_state` sets or removes a switch's
initial state ([decision 0015](../decisions/0015-controlled-sources.md)). A control node or a
controlling source cannot be edited: any change to one is a `TopologyViolation`.

```python
>>> amp = Netlist.from_text(
...     "t\nV1 in 0 2\nVs in a 0\nR1 a 0 1k\nH1 out 0 Vs 1k\nR2 out 0 1k\n"
...     ".model sm SW\nS1 out 0 a 0 sm\n.op\n.end\n",
...     dialect=Dialect.NGSPICE,
... )
>>> with amp.batch() as batch:
...     batch.set_formula("H1", "2*rt")
...     batch.set_switch_state("S1", "off")
>>> print("\n".join(line for line in batch.result.text.splitlines() if line[:2] in ("H1", "S1")))
H1 out 0 Vs {2*rt}
S1 out 0 a 0 sm off

```

## Edit a behavioural expression

`set_expression` replaces the text of an expression and keeps its delimiters: braces, quotes
or none ([decision 0016](../decisions/0016-behavioral-expressions.md)). It works on B, the
expression forms of E, F, G and H, a capacitor's charge, an inductor's flux and an R, C or L
formula value. The quantity (`V=`, `I=`) and the form (`vol=`, `value`) cannot be changed, and
the trailing parameters use `set_param`. What the expression reads is not topology, so the
signature does not change.

```python
>>> behavioural = Netlist.from_text(
...     "t\nV1 in 0 1\nR1 in 0 1k\nB1 out 0 V = 2 * v(in) tc1=0\nR2 out 0 1k\n.op\n.end\n",
...     dialect=Dialect.NGSPICE,
... )
>>> edited = behavioural.set_expression("B1", "3 * v(in)").set_param("B1", "tc1", "1m")
>>> print(next(line for line in edited.text.splitlines() if line.startswith("B1")))
B1 out 0 V = 3 * v(in) tc1=1m
>>> [(read.kind, read.name) for read in edited.expression_reads("B1")]
[('node', 'in')]

```

## Edit a table or a polynomial

`set_table` replaces the points of an ngspice `TABLE`, `FREQ` or gate, or of an LTspice `table=`,
and `set_poly_coefficients` replaces the coefficients of a `POLY`
([decision 0017](../decisions/0017-tables-polynomials-and-transfer-functions.md)). The number of
points or coefficients may change; the dimension, the control nodes and the controlling sources
are topology, so a change to one is a `TopologyViolation`. The expression of a `TABLE` or `FREQ`
and a `Laplace=` formula use `set_expression`.

```python
>>> from netlistmod import EditError
>>> nonlinear = Netlist.from_text(
...     "t\nV1 in 0 2\nR1 in vx 1k\nR2 vx 0 2k\nR3 a 0 1k\nR4 b 0 1k\n"
...     "E1 a 0 TABLE {v(vx)} = (0,0) (2,4)\nE2 b 0 POLY(1) vx 0 0 2\n.op\n.end\n",
...     dialect=Dialect.NGSPICE,
... )
>>> edited = nonlinear.set_table("E1", [("0", "0"), ("1", "1"), ("2", "5")])
>>> edited = edited.set_poly_coefficients("E2", ["0", "3", "4"])
>>> print("\n".join(line for line in edited.text.splitlines() if line.startswith("E")))
E1 a 0 TABLE {v(vx)} = (0,0) (1,1) (2,5)
E2 b 0 POLY(1) vx 0 0 3 4
>>> edited.signature() == nonlinear.signature()
True
>>> try:
...     nonlinear.set_poly_coefficients("E2", ["1"])
... except EditError as error:
...     print(error)
a POLY line takes at least 2 coefficients on ngspice; `E2` was given 1

```

## Edit a transmission line

`set_param` sets a line's parameters, `set_model` its model, and `remove_param` and
`remove_model_param` take a parameter out ([decision 0019](../decisions/0019-transmission-lines.md)).
A T keeps the spelling of its impedance, and its length form is switched in one batch:

```python
>>> from netlistmod import Dialect, Netlist
>>> line = Netlist.from_text(
...     "t\nT1 a 0 b 0 Zo=50 TD=1n\nR1 b 0 50\n.end\n", dialect=Dialect.NGSPICE
... )
>>> print(line.set_param("T1", "z0", "75").source.text.splitlines()[1])
T1 a 0 b 0 Zo=75 TD=1n
>>> with line.batch() as batch:
...     batch.set_param("T1", "f", "100meg")
...     batch.set_param("T1", "nl", "0.1")
...     batch.remove_param("T1", "td")
>>> print(batch.result.source.text.splitlines()[1])
T1 a 0 b 0 Zo=50 f=100meg nl=0.1

```

A CPL matrix is set as a whole list, and `remove_model_param` takes a parameter out of a `.model`:

```python
>>> cpl_text = (
...     "t\nP1 a1 a2 0 b1 b2 0 pmod\n.model pmod cpl length=1\n+R=1 0 1\n+L=50n 5n 50n\n"
...     "+G=0 0 0\n+C=20p -2p 20p\n.model lm ltra(r=10 l=50n c=20p len=1)\n.end\n"
... )
>>> cpl = Netlist.from_text(cpl_text, dialect=Dialect.NGSPICE)
>>> print(cpl.set_model_param("pmod", "L", "60n 6n 60n").source.text.splitlines()[4])
+L=60n 6n 60n
>>> print(cpl.remove_model_param("lm", "r").source.text.splitlines()[7])
.model lm ltra(l=50n c=20p len=1)

```

A removal never touches a comment: a field that is alone on its `+` line goes with the line
break before it, so a comment after it moves to the end of the line before
(`R1 a 0 1k` / `+ m=2 ; note` becomes `R1 a 0 1k ; note`). A removal that leaves a line without
what it needs (a T's `Z0=`, a U's `l=`) is refused by the verification. Nodes, P's line count and an O line's (absent) parameters are not editable.

## Continued lines, blocks and includes

Text over several physical lines is passed as a list; the lines are joined with the file's
line ending. A `.control`, `.if` or `.lib` block, or an `.include`/`.lib` statement, is added, replaced
or removed whole; its contents are never edited, and what it brings in is not verified.

```python
>>> lib = Netlist.from_text(
...     "t\n.include old.lib\nX1 in out amp\n.tran 1u 5u\n.end\n", dialect=Dialect.NGSPICE
... )
>>> from netlistmod import OpaqueStatement
>>> swapped = lib.directives.remove(lib.lines.find(OpaqueStatement)).add_include("new.lib")
>>> with swapped.batch() as batch:
...     batch.directives.set([".tran 1u 10m", "+ 0 1u"])
...     batch.directives.add([".control", "run", ".endc"])
>>> print(batch.result.text, end="")
t
.include "new.lib"
X1 in out amp
.tran 1u 10m
+ 0 1u
.control
run
.endc
.end

```

## What cannot be edited

Topology has no setter. Where an API could be misused it raises `TopologyError`, and a plan
that changes the topology anyway raises `TopologyViolation`; nothing is returned or written.

```python
>>> netlist.directives.add("R9 out 0 1k")
Traceback (most recent call last):
...
netlistmod.errors.TopologyError: directives.add: `R9 out 0 1k` is a resistor line (an element), which is topology; only directives and whole opaque items can be added or replaced
>>> from netlistmod import Edit
>>> node = netlist.element("R22").nodes[0]
>>> netlist.apply([Edit(node.span, "mid")])
Traceback (most recent call last):
...
netlistmod.errors.TopologyViolation: the edit changes the topology at signature entry 2: expected ('element', (), 'R22', 'Resistor', ('out', '0')), found ('element', (), 'R22', 'Resistor', ('mid', '0')); nothing was written

```

## Save

`save(path)` verifies again and writes atomically in the original encoding, BOM and line
endings; without a path it writes back to the file the netlist was loaded from. An unedited
netlist saves its original bytes. Text that the original encoding cannot hold raises
`EncodingError` before anything is written.

```python
>>> path = folder / "amplifier.cir"
>>> _ = path.write_bytes(text.replace("\n", "\r\n").encode("cp1252"))
>>> loaded = Netlist.load(path, dialect=Dialect.NGSPICE)
>>> loaded.set_value("R22", "2.2k").save()
>>> path.read_bytes().splitlines()[3]
b'R22 out 0 2.2k'
>>> b"\r\n" in path.read_bytes()
True
>>> import shutil
>>> shutil.rmtree(folder)

```

## LTspice

Conventions, verification and `save()` are the same, and the examples above that use forms both dialects read work unchanged. Some operations go further or are refused ([decision 0009](../decisions/0009-ltspice-dialect.md) item 17):

```python
>>> lt = Netlist.from_text(
...     "t\nV1 a 0 3\nD1 a 0 dm 2 off\nR1 a 0 1k\n.model dm D\n.step param x 1 2 1\n.end\n",
...     dialect=Dialect.LTSPICE,
... )
>>> lt = lt.set_param("V1", "Rser", "1").set_param("D1", "area", "4").set_param("D1", "off", "1")
>>> lt = lt.directives.set(".step param x 1 9 1")
>>> print(lt.text, end="")
t
V1 a 0 3 Rser=1
D1 a 0 dm 4 off=1
R1 a 0 1k
.model dm D
.step param x 1 9 1
.end
>>> lt.set_model("R1", "rm")
Traceback (most recent call last):
...
netlistmod.errors.EditError: `R1` takes no model: LTspice has no R, C or L model

```

`directives.set` upserts a `.step` by its swept quantity, so a nested `.step` of another quantity adds a line.
