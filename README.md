# netlistmod

`netlistmod` is a source-preserving SPICE netlist editing library. Its goal is
to make permitted value and directive edits while preserving the original text
and circuit topology.

## Supported dialects

The caller always selects the dialect; there is no default and no detection.

| Dialect | `Dialect` | Input | Elements | Reference | Validated on |
|---|---|---|---|---|---|
| ngspice | `NGSPICE` | `.cir`, `.sp`, `.net`, KiCad exports | R, C, L, K, V, I, D, X; Q, M, J, Z (M13) | [ngspice manual](docs/references.md) | ngspice 47 |
| LTspice | `LTSPICE` | `.net`, `.cir` (an `.asc` schematic is [exported first](docs/usage/ltspice-export.md)) | R, C, L, K, V, I, D, X; Q, M, J, Z (M13) | [ltspice-reference](docs/references.md) | LTspice 26.1.1, Windows |

Where a solver and the library differ, the file is `docs/grammars/<dialect>/discrepancies.md`. Other
device letters raise `UnsupportedConstruct` until their phase 2 milestone.

## Quick start

```bash
uv sync
```

```python
>>> from pathlib import Path
>>> from tempfile import TemporaryDirectory
>>> from netlistmod import Dialect, Netlist
>>> folder = TemporaryDirectory()
>>> path = Path(folder.name) / "divider.cir"
>>> _ = path.write_bytes(b"divider\nV1 in 0 DC 3\nR1 in out 1k ; top\nR2 out 0 1k\n.op\n.end\n")

>>> netlist = Netlist.load(path, dialect=Dialect.NGSPICE)
>>> edited = netlist.set_value("R2", "3k").directives.set(".tran 1u 5u")
>>> edited.save()
>>> print(path.read_text(), end="")
divider
V1 in 0 DC 3
R1 in out 1k ; top
R2 out 0 3k
.op
.tran 1u 5u
.end
>>> folder.cleanup()

```

Every edit returns a new netlist that has been re-parsed and checked against the topology of the original. `save()` changes only the edited text: comments, spacing, line endings and encoding stay as they were. For the whole cycle with a solver, see [edit_and_simulate.py](docs/usage/examples/edit_and_simulate.py).

## What it does and does not do

- **Reads** titles, comments, the phase 1 elements, `.param`, `.model`, `.subckt`, the analysis, option and output directives, and LTspice's `.step`, into typed nodes with exact source spans. It answers queries about lines, references, nets and connections.
- **Edits** values, formulas, instance and model parameters, source DC and AC values and functions, `.param` lines and directives, and adds an `.include`.
- **Preserves** other dot-commands verbatim. `.control`, `.if`, `.include` and `.lib` are opaque: their contents are not read.
- **Never** changes topology (elements, nodes, subcircuit ports), evaluates a value, or launches a solver.
- **Refuses loudly.** A line outside the grammar is an error, not a guess. Netlists with Q or M devices are rejected until phase 2.

## Status

Phase 1 is complete, with both dialects validated on their solvers ([M9](docs/design/archive/phase-1/m9-tasks.md)), and phase 2 is next. There is no release yet.

Supported platforms are Linux and Windows, with Python 3.13 or newer. LTspice validation runs on Windows. macOS is not tested.

- **Guides:** [usage](docs/usage/README.md), including the [error reference](docs/usage/errors.md).
- **Design:** [architecture](docs/architecture.md), [phase 2 plan](docs/design/phase-2-plan.md), [phase 1 plan](docs/design/archive/phase-1/phase-1-plan.md).
- **Development:** [testing](docs/testing.md), [changelog](CHANGELOG.md).
