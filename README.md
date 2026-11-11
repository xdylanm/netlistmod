# netlistmod

`netlistmod` is a source-preserving SPICE netlist editing library. Its goal is
to make permitted value and directive edits while preserving the original text
and circuit topology.

## Supported dialects

The caller always selects the dialect; there is no default and no detection.

| Dialect | `Dialect` | Input | Elements | Reference | Validated on |
|---|---|---|---|---|---|
| ngspice | `NGSPICE` | `.cir`, `.sp`, `.net`, KiCad exports | R, C, L, K, V, I, D, X, Q, M, J, Z, E, F, G, H, S, W, B, T, O, U (URC), Y, P, A (code models) and N (OSDI), with the expression, TABLE, POLY, FREQ and gate forms | [ngspice manual](docs/references.md) | ngspice 47 |
| LTspice | `LTSPICE` | `.net`, `.cir` (an `.asc` schematic is [exported first](docs/usage/ltspice-export.md)) | R, C, L, K, V, I, D, X, Q, M, J, Z, E, F, G, H, S, W, B, T, O, U, A (special functions), `@` and `&`, with the expression, `table=`, POLY and `Laplace=` forms | [ltspice-reference](docs/references.md) | LTspice 26.1.1, Windows |

Where a solver and the library differ, the file is `docs/grammars/<dialect>/discrepancies.md`. Every
device letter is supported. Two constructs are out of scope for v1 and raise `UnsupportedConstruct`:
the ngspice digital U (a U line that is not a URC line), whose libraries need PSpice compatibility
mode, and LTspice's `.machine` ([decision 0020](docs/decisions/0020-special-and-mixed-signal-devices.md)).

## Quick start

```bash
pip install netlistmod
```

To work on the library itself, clone it and run `uv sync`.

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

- **Reads** titles, comments, every device letter of both dialects, `.param`, `.model`, `.subckt`, `.global`, the analysis, option and output directives, and LTspice's `.step`, into typed nodes with exact source spans. It answers queries about lines, references, nets and connections.
- **Edits** values, formulas and behavioural expressions (`set_value`, `set_formula`, `set_expression`, `remove_value`); instance and model parameters (`set_param`, `set_instance_param`, `set_model_param`, `remove_param`, `remove_model_param`); an element's model (`set_model`); a source's DC and AC values and its function (`set_dc`, `set_ac`, `set_stimulus`, `set_stimulus_arg`, `remove_stimulus`); a coupling (`set_coupling`), a table (`set_table`), POLY coefficients (`set_poly_coefficients`) and a switch's state (`set_switch_state`); `.param` lines (`params`) and directives (`directives`); and adds an `.include` (`add_include`).
- **Preserves** other ngspice dot-commands verbatim. On ngspice, `.control`, `.if`, `.include` and `.lib` are opaque: their contents are not read. On LTspice, `.include` and `.lib` are opaque, and the dot-commands are a closed list: any other, `.control` and `.if` among them, is a `ParseError`.
- **Never** changes topology (elements, nodes, subcircuit ports), evaluates a value, or launches a solver.
- **Refuses loudly.** A line outside the grammar is an error, not a guess. A construct outside v1 (the ngspice digital U, LTspice `.machine`) raises `UnsupportedConstruct`.

## Status

The library is feature complete for v1: every device letter of both dialects is supported, and both dialects are validated on their solvers. The current release is the `0.5.0` alpha: the public API may still change before 1.0.

Supported platforms are Linux and Windows, with Python 3.13 or newer. LTspice validation runs on Windows. macOS is not tested.

- **Guides:** [usage](docs/usage/README.md), including the [error reference](docs/usage/errors.md).
- **Design:** [architecture](docs/architecture.md) and the [decision records](docs/decisions/README.md).
- **Development:** [testing](docs/testing.md), [changelog](CHANGELOG.md).
