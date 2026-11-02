# Usage guides

The examples in these guides are executed by the test suite. Each guide says which dialect it covers.

| Guide | Covers |
|---|---|
| [Parsing structural source](./structural-parse.md) | Titles, comments, continuations and opaque items |
| [Parsing element lines](./elements.md) | R, C, L, K, V, I, D and X |
| [Parsing statements and directives](./statements.md) | `.param`, `.model`, `.subckt` and the directives |
| [Reading a netlist](./document.md) | Lines, references, nets and diagnostics |
| [Editing a netlist](./editing.md) | Every edit, verification and `save()` |
| [Errors and diagnostics](./errors.md) | Each exception and diagnostic code, and what to do |
| [Exporting from LTspice](./ltspice-export.md) | From an `.asc` schematic to a netlist, and batch runs |

Examples you can run:

- [read_only_demo.py](./examples/read_only_demo.py): what the library sees in a KiCad export.
- [edit_and_simulate.py](./examples/edit_and_simulate.py): load, edit, save and run a solver, with `--dialect ngspice` or `ltspice`.

See [the architecture](../architecture.md) for the design and its constraints.
