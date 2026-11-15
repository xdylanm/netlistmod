# Usage guides

The examples in these guides are executed by the test suite. Each guide says which dialect it covers.

Import every name from `netlistmod` (`from netlistmod import Dialect, Netlist`): `netlistmod.__all__` is
the public API, and its submodules (`netlistmod.document`, `netlistmod.edit`, `netlistmod.model`, …) are
internal.

| Guide | Covers |
|---|---|
| [Parsing structural source](./structural-parse.md) | Titles, comments, continuations and opaque items |
| [Parsing element lines](./elements.md) | Every device letter of both dialects: R, C, L, K, V, I, D and X; the transistors Q, M, J and Z; the dependent sources and switches E, F, G, H, S and W; B; the transmission lines T, O, U, Y and P; and A, N, `@` and `&` |
| [Parsing statements and directives](./statements.md) | `.param`, `.model`, `.subckt` and the directives |
| [Reading a netlist](./document.md) | Lines, references, nets and diagnostics |
| [Editing a netlist](./editing.md) | Every edit, verification and `save()` |
| [Errors and diagnostics](./errors.md) | Each exception and diagnostic code, and what to do |
| [Exporting from LTspice](./ltspice-export.md) | From an `.asc` schematic to a netlist, and batch runs |

Examples you can run:

- [read_only_demo.py](./examples/read_only_demo.py): load a netlist and print its elements, nets, connections, references, diagnostics and topology signature. Without a path it loads a KiCad export from a clone of the repository. It takes `--dialect` and `--rkm`, and `--help` describes them.
- [edit_and_simulate.py](./examples/edit_and_simulate.py): load, edit, save and run `.op` in a solver, on a built-in divider or your own netlist, and print a net's voltage. It takes `--dialect`, `--edit-value`, `--probe` and `--rkm`.

See [the architecture](../architecture.md) for the design and its constraints.

## Related tools

netlistmod edits a netlist in its own dialect and does not translate between dialects. These third-party tools may help with tasks outside its scope. They are listed for reference only: netlistmod does not use or test them, so check each tool's documentation and licence yourself.

| Tool | What it does |
|---|---|
| [XDM](https://github.com/Xyce/XDM) (Sandia) | Converts PSpice and HSPICE netlists into Xyce's format |
