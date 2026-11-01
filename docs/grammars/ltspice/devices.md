# LTspice device-letter matrix

The letters of `[ltspice-ref] SPICE-SYNTAX-REFERENCE.md "Line Types by Leading Character"`. Since M8
the phase 1 letters R, C, L, K, V, I, D and X are parsed into typed element nodes (spec entries
`LT-RES-001` to `LT-SUB-001`). Every other letter of the table raises `UnsupportedConstruct` until
phase 2. The table is checked against
[`ltspice-devices.json`](../../../src/netlistmod/grammar/ltspice-devices.json).

| Letter | Status | Phase | Milestone |
|---|---|---:|---|
| A | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| B | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| C | supported | 1 | M8 |
| D | supported | 1 | M8 |
| E | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| F | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| G | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| H | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| I | supported | 1 | M8 |
| J | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| K | supported | 1 | M8 |
| L | supported | 1 | M8 |
| M | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| O | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| Q | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| R | supported | 1 | M8 |
| S | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| T | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| U | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| V | supported | 1 | M8 |
| W | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| X | supported | 1 | M8 |
| Z | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| & | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| @ | planned | 2 | Post-review phase 2 (milestone sequence TBD) |

`@` is the frequency response analyzer and `&` its probe. N, P and Y are not LTspice letters, so a
line starting with one is a `ParseError`. The architecture's `Ö` is not in the reference (decision
0009 corrects §6.7).
