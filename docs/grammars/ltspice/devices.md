# LTspice device-letter matrix

The letters of `[ltspice-ref] SPICE-SYNTAX-REFERENCE.md "Line Types by Leading Character"`. Since M8
the phase 1 letters R, C, L, K, V, I, D and X are parsed into typed element nodes (spec entries
`LT-RES-001` to `LT-SUB-001`). Every other letter of the table raises `UnsupportedConstruct` until
phase 2. The table is checked against
[`ltspice-devices.json`](../../../src/netlistmod/grammar/ltspice-devices.json).

| Letter | Status | Phase | Milestone |
|---|---|---:|---|
| A | planned | 2 | M17 |
| B | planned | 2 | M15 |
| C | supported | 1 | M8 |
| D | supported | 1 | M8 |
| E | planned | 2 | M14, M15 |
| F | planned | 2 | M14, M15 |
| G | planned | 2 | M14, M15 |
| H | planned | 2 | M14, M15 |
| I | supported | 1 | M8 |
| J | planned | 2 | M13 |
| K | supported | 1 | M8 |
| L | supported | 1 | M8 |
| M | planned | 2 | M13 |
| O | planned | 2 | M16 |
| Q | planned | 2 | M13 |
| R | supported | 1 | M8 |
| S | planned | 2 | M14 |
| T | planned | 2 | M16 |
| U | planned | 2 | M16 |
| V | supported | 1 | M8 |
| W | planned | 2 | M14 |
| X | supported | 1 | M8 |
| Z | planned | 2 | M13 |
| & | planned | 2 | M17 |
| @ | planned | 2 | M17 |

`@` is the frequency response analyzer and `&` its probe. N, P and Y are not LTspice letters, so a
line starting with one is a `ParseError`. The architecture's `Ö` is not in the reference (decision
0009 corrects §6.7). The milestones are those of the [phase 2 plan](../../design/phase-2-plan.md). E, F, G
and H have linear forms in M14 and nonlinear forms in M15.
