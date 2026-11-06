# ngspice device-letter matrix

Since M3 the phase 1 letters R, C, L, K, V, I, D and X are parsed into typed
element nodes (spec entries `NG-RES-001` to `NG-SUB-001`). Every other
alphabetic designator is a known device letter and raises `UnsupportedConstruct`
until its scheduled grammar milestone. The table is checked against
[`ngspice-devices.json`](../../../src/netlistmod/grammar/ngspice-devices.json).

| Letter | Status | Phase | Milestone |
|---|---|---:|---|
| A | planned | 2 | M17 |
| B | planned | 2 | M15 |
| C | supported | 1 | M3 |
| D | supported | 1 | M3 |
| E | planned | 2 | M14, M15 |
| F | planned | 2 | M14, M15 |
| G | planned | 2 | M14, M15 |
| H | planned | 2 | M14, M15 |
| I | supported | 1 | M3 |
| J | supported | 2 | M13 |
| K | supported | 1 | M3 |
| L | supported | 1 | M3 |
| M | supported | 2 | M13 |
| N | planned | 2 | M17 |
| O | planned | 2 | M16 |
| P | planned | 2 | M16 |
| Q | supported | 2 | M13 |
| R | supported | 1 | M3 |
| S | planned | 2 | M14 |
| T | planned | 2 | M16 |
| U | planned | 2 | M16, M17 |
| V | supported | 1 | M3 |
| W | planned | 2 | M14 |
| X | supported | 1 | M3 |
| Y | planned | 2 | M16 |
| Z | supported | 2 | M13 |

The milestones are those of the [phase 2 plan](../../design/phase-2-plan.md). E, F, G and H have
linear forms in M14 and nonlinear forms in M15. U is a URC line in M16 and a digital primitive in
M17 (`[ngspice-manual] §10.1.3 "URC transmission line versus U devices"`). No device letter is
unassigned.
