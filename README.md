# netlistmod

`netlistmod` is a source-preserving SPICE netlist editing library. Its goal is
to make permitted value and directive edits while preserving the original text
and circuit topology.

**Status:** M3 (ngspice elements and values) is ready for review. The strict
ngspice parser preserves titles, comments, unknown dot-commands, immediate
continuations and opaque blocks/statements, and parses the phase 1 element lines
(R, C, L, K, V, I, D, X) into typed nodes with exact source spans. RKM values
need `parse(..., rkm=True)`. Statements such as `.param` and `.model` (M4) and the
document/edit layers remain in progress. See the [structural parse guide](docs/usage/structural-parse.md),
the [element guide](docs/usage/elements.md),
[architecture](docs/architecture.md), and [Phase 1 plan](docs/design/phase-1-plan.md).
Local setup and checks are documented in [testing](docs/testing.md).
