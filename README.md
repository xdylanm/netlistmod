# netlistmod

`netlistmod` is a source-preserving SPICE netlist editing library. Its goal is
to make permitted value and directive edits while preserving the original text
and circuit topology.

## Supported dialects

The caller always selects the dialect; there is no default and no detection.

| Dialect | `Dialect` | Input | Phase 1 elements | Reference | Validated on |
|---|---|---|---|---|---|
| ngspice | `NGSPICE` | `.cir`, `.sp`, `.net`, KiCad exports | R, C, L, K, V, I, D, X | [ngspice manual](docs/references.md) | ngspice 47 |
| LTspice | `LTSPICE` | `.net`, `.cir` (an `.asc` schematic is [exported first](docs/usage/ltspice-export.md)) | R, C, L, K, V, I, D, X | [ltspice-reference](docs/references.md) | LTspice 26.1.1, Windows |

Where a solver and the library differ, the file is `docs/grammars/<dialect>/discrepancies.md`. Other
device letters raise `UnsupportedConstruct` until phase 2.

## Status

**Status:** M0–M8 are complete, including the edit layer, local ngspice validation and the
LTspice dialect with the same guarantees, validated on LTspice 26.1.1. The strict
parser preserves titles, comments, unknown dot-commands, immediate
continuations and opaque blocks/statements, and parses the phase 1 element lines
(R, C, L, K, V, I, D, X) into typed nodes with exact source spans. RKM values
need `parse(..., rkm=True)`. `.param`, `.model`, `.subckt` … `.ends` (nested, with
its body) and the analysis, option and output directives (`.tran`, `.ac`, `.dc`,
`.op`, `.options`, `.temp`, `.ic`, `.nodeset`, `.save`, `.meas`) are typed nodes
too. `Netlist` answers read-only queries: lines, symbol tables, resolved
references, nets and connections, diagnostics and the topology signature. Its edit
methods set values, formulas, instance and model parameters, source DC/AC values,
`.param` lines and directives, add a harness `.include`, and return a new netlist
that has been re-parsed and checked against the topology signature of the load;
`save()` writes it back with a minimal diff. See the [structural parse guide](docs/usage/structural-parse.md),
the [element guide](docs/usage/elements.md), the [statement guide](docs/usage/statements.md),
the [document guide](docs/usage/document.md), the [editing guide](docs/usage/editing.md),
[architecture](docs/architecture.md), and [Phase 1 plan](docs/design/phase-1-plan.md).
Local setup and checks are documented in [testing](docs/testing.md).
