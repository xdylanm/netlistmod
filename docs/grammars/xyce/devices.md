# Xyce device-letter matrix

The letters of `[xyce-ref] §2.3 p177 "Devices"` (Table 2-35, p177–178). X-M0 reads no element
([decision 0026](../../decisions/0026-the-xyce-dialect.md)): every letter is `planned`, and a line
that starts with one raises `UnsupportedConstruct` ("not yet supported on Xyce", with the
milestone). The Milestone column is the milestone of the [xyce plan](../../design/xyce-plan.md)
section 8 that adds the letter; Phase is 1 for the X-M1 letters and 2 for the rest. The table is
checked against [`xyce-devices.json`](../../../src/netlistmod/grammar/xyce-devices.json).

| Letter | Status | Phase | Milestone |
|---|---|---:|---|
| B | planned | 2 | X-M5 |
| C | planned | 1 | X-M1 |
| D | planned | 1 | X-M1 |
| E | planned | 2 | X-M5 |
| F | planned | 2 | X-M5 |
| G | planned | 2 | X-M5 |
| H | planned | 2 | X-M5 |
| I | planned | 1 | X-M1 |
| J | planned | 2 | X-M4 |
| K | planned | 1 | X-M1 |
| L | planned | 1 | X-M1 |
| M | planned | 2 | X-M4 |
| O | planned | 2 | X-M6 |
| P | planned | 2 | X-M3 |
| Q | planned | 2 | X-M4 |
| R | planned | 1 | X-M1 |
| S | planned | 2 | X-M5 |
| T | planned | 2 | X-M6 |
| U | planned | 2 | X-M7 |
| V | planned | 1 | X-M1 |
| W | planned | 2 | X-M5 |
| X | planned | 1 | X-M1 |
| Y | planned | 2 | X-M6 |
| Z | planned | 2 | X-M4 |

A and N are not Xyce letters (Table 2-35), so a line starting with one is a `ParseError`, as a
letter outside a dialect's matrix is on ngspice and LTspice. Several letters collide with the other
dialects and mean something else on Xyce: P is a port device for `.LIN` (ngspice: a coupled line),
U a digital gate (ngspice: a URC line) and Y a family of devices named by a type and a name,
`Y<type> <name>` (ngspice: a TXL line; decision X-D4 in X-M6). The plan's section 3 lists the form
of each letter and its source in the manual.
