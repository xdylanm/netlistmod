# netlistmod

`netlistmod` is a source-preserving SPICE netlist editing library. Its goal is
to make permitted value and directive edits while preserving the original text
and circuit topology.

**Status:** The strict M2 ngspice structural parser is under review and is not
yet accepted; element parsing and the document/edit layers remain in progress.
It preserves titles, comments, unknown dot-commands, immediate continuations,
and opaque blocks/statements with exact source spans. See the [structural parse guide](docs/usage/structural-parse.md),
[architecture](docs/architecture.md), and [Phase 1 plan](docs/design/phase-1-plan.md).
Local setup and checks are documented in [testing](docs/testing.md).
