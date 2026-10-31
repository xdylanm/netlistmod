# ngspice device-letter matrix

Since M3 the phase 1 letters R, C, L, K, V, I, D and X are parsed into typed
element nodes (spec entries `NG-RES-001` to `NG-SUB-001`). Every other
alphabetic designator is a known device letter and raises `UnsupportedConstruct`
until its scheduled grammar milestone. The table is checked against
[`ngspice-devices.json`](../../../src/netlistmod/grammar/ngspice-devices.json).

| Letter | Status | Phase | Milestone |
|---|---|---:|---|
| A | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| B | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| C | supported | 1 | M3 |
| D | supported | 1 | M3 |
| E | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| F | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| G | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| H | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| I | supported | 1 | M3 |
| J | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| K | supported | 1 | M3 |
| L | supported | 1 | M3 |
| M | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| N | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| O | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| P | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| Q | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| R | supported | 1 | M3 |
| S | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| T | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| U | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| V | supported | 1 | M3 |
| W | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| X | supported | 1 | M3 |
| Y | planned | 2 | Post-review phase 2 (milestone sequence TBD) |
| Z | planned | 2 | Post-review phase 2 (milestone sequence TBD) |

The post-review phase 2 work is required by architecture decision 6, but the
phase-2 milestone sequence has not yet been added to the phase plan. No device
letter is unassigned.
