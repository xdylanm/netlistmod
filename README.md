# netlistmod

`netlistmod` is a source-preserving SPICE netlist editing library. Its goal is
to make permitted value and directive edits while preserving the original text
and circuit topology.

**Status:** M0–M4 are complete; M5 (the read-only document layer) is ready for
review. The strict
ngspice parser preserves titles, comments, unknown dot-commands, immediate
continuations and opaque blocks/statements, and parses the phase 1 element lines
(R, C, L, K, V, I, D, X) into typed nodes with exact source spans. RKM values
need `parse(..., rkm=True)`. `.param`, `.model`, `.subckt` … `.ends` (nested, with
its body) and the analysis, option and output directives (`.tran`, `.ac`, `.dc`,
`.op`, `.options`, `.temp`, `.ic`, `.nodeset`, `.save`, `.meas`) are typed nodes
too. `Netlist` answers read-only queries: lines, symbol tables, resolved
references, nets and connections, diagnostics and the topology signature; the
edit layer (M6) is next. See the [structural parse guide](docs/usage/structural-parse.md),
the [element guide](docs/usage/elements.md), the [statement guide](docs/usage/statements.md),
the [document guide](docs/usage/document.md),
[architecture](docs/architecture.md), and [Phase 1 plan](docs/design/phase-1-plan.md).
Local setup and checks are documented in [testing](docs/testing.md).
