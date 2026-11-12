# LTspice device-letter matrix

The letters of `[ltspice-ref] SPICE-SYNTAX-REFERENCE.md "Line Types by Leading Character"`. Every
letter is parsed into a typed element node; each has its spec entries. The Phase and Milestone
columns record when a letter was added. The table is checked against
[`ltspice-devices.json`](../../../src/netlistmod/grammar/ltspice-devices.json).

| Letter | Status | Phase | Milestone |
|---|---|---:|---|
| A | supported | 2 | M17 |
| B | supported | 2 | M15 |
| C | supported | 1 | M8 |
| D | supported | 1 | M8 |
| E | supported | 2 | M14, M15 |
| F | supported | 2 | M14, M15 |
| G | supported | 2 | M14, M15 |
| H | supported | 2 | M14, M15 |
| I | supported | 1 | M8 |
| J | supported | 2 | M13 |
| K | supported | 1 | M8 |
| L | supported | 1 | M8 |
| M | supported | 2 | M13 |
| O | supported | 2 | M16 |
| Q | supported | 2 | M13 |
| R | supported | 1 | M8 |
| S | supported | 2 | M14 |
| T | supported | 2 | M16 |
| U | supported | 2 | M16 |
| V | supported | 1 | M8 |
| W | supported | 2 | M14 |
| X | supported | 1 | M8 |
| Z | supported | 2 | M13 |
| & | supported | 2 | M17 |
| @ | supported | 2 | M17 |

A is a special function, `@` the frequency response analyzer and `&` its probe. `.machine` is
not a letter but a block, and stays `UnsupportedConstruct`: a named v1 exclusion (decision 0020
item 11). N, P and Y are not LTspice letters, so a
line starting with one is a `ParseError`. The architecture's `Ö` is not in the reference (decision
0009 corrects §6.7). The milestones are those of the [phase 2 plan](../../design/archive/phase-2/phase-2-plan.md). E, F, G
and H have linear forms in M14 and nonlinear forms in M15.
