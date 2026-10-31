# Editing a netlist

`netlistmod.Netlist` edits values, parameters and directives in place and writes the netlist
back with a minimal diff, without changing its topology (M6,
[decision 0007](../decisions/0007-edit-lifecycle-and-edit-semantics.md)). Every edit method
returns a **new** netlist that has been re-parsed and verified; the original is unchanged. The
operations, the slots they edit and their errors are listed in
[m6-edits.md](../design/m6-edits.md). The examples below are executed by the test suite.

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
netlistmod.errors.EditError: set_value R22: `1k 2k` does not re-parse as a value (decision 0007 item 8); the text would change more than the intended slot

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
adds one before `.end`. Repeatable directives (`.options`, `.save`, `.ic`, …) are added,
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
netlistmod.errors.EditError: scope ('amp',) edits the definition of subcircuit `amp`, which changes every instance of it; pass in_definition=True to confirm, or use set_instance_param on an X line to change one instance (architecture §7.4)
>>> print(amp.set_value("R1", "5k", scope=("amp",), in_definition=True).text.splitlines()[4])
R1 a b 5k
>>> print(amp.set_instance_param("X2", "g", "3").text.splitlines()[2])
X2 out o2 amp g=3

```

## What cannot be edited

Topology has no setter. Where an API could be misused it raises `TopologyError`, and a plan
that changes the topology anyway raises `TopologyViolation`; nothing is returned or written.

```python
>>> netlist.directives.add("R9 out 0 1k")
Traceback (most recent call last):
...
netlistmod.errors.TopologyError: directives.add: `R9 out 0 1k` is a resistor line (an element), which is topology or opaque; only directives can be added or replaced (architecture §7.3)
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
