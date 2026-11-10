# ngspice device-letter matrix

Since M3 the phase 1 letters R, C, L, K, V, I, D and X are parsed into typed
element nodes (spec entries `NG-RES-001` to `NG-SUB-001`); phase 2 added the
others, the last of them A (`NG-COD-001`) and N (`NG-OSD-001`) in M17, so no letter
is planned. The table is checked against
[`ngspice-devices.json`](../../../src/netlistmod/grammar/ngspice-devices.json).

| Letter | Status | Phase | Milestone |
|---|---|---:|---|
| A | supported | 2 | M17 |
| B | supported | 2 | M15 |
| C | supported | 1 | M3 |
| D | supported | 1 | M3 |
| E | supported | 2 | M14, M15 |
| F | supported | 2 | M14, M15 |
| G | supported | 2 | M14, M15 |
| H | supported | 2 | M14, M15 |
| I | supported | 1 | M3 |
| J | supported | 2 | M13 |
| K | supported | 1 | M3 |
| L | supported | 1 | M3 |
| M | supported | 2 | M13 |
| N | supported | 2 | M17 |
| O | supported | 2 | M16 |
| P | supported | 2 | M16 |
| Q | supported | 2 | M13 |
| R | supported | 1 | M3 |
| S | supported | 2 | M14 |
| T | supported | 2 | M16 |
| U | supported | 2 | M16 |
| V | supported | 1 | M3 |
| W | supported | 2 | M14 |
| X | supported | 1 | M3 |
| Y | supported | 2 | M16 |
| Z | supported | 2 | M13 |

The milestones are those of the [phase 2 plan](../../design/phase-2-plan.md). E, F, G and H have
linear forms in M14 and nonlinear forms in M15. U is a URC line since M16 (`[ngspice-manual] §10.1.3 "URC transmission
line versus U devices"`). Every other U line is the ngspice digital U, a named v1 exclusion
(decision 0020 item 1): it raises `UnsupportedConstruct` ("ngspice digital U device, out of scope
for v1"). No device letter is
unassigned.
