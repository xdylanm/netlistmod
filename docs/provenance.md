# Provenance and licensing

The library is licensed under the MIT License. Runtime dependencies must not
introduce GPL-licensed code.

All implementation and tests are clean-room work. Do not copy or derive code,
tests, or other material from GPL-licensed projects, including spicelib.

Corpus fixtures must be independently authored or exported from projects owned
by the maintainer. Each fixture family has a manifest recording its origin,
license, author, date, and relevant notes. Preserve corpus files byte-for-byte;
do not normalize line endings or whitespace.

## Corpus families

| Family | Origin | Author | License |
|---|---|---|---|
| `ngspice/kicad_basic` | Export of a KiCad project owned by the maintainer | xdylanm | MIT |
| `ngspice/kicad_extended` | Export of a KiCad project owned by the maintainer | xdylanm | MIT |
| `ngspice/structure_basic`, `ngspice/structure_rejects` | Authored in this repository (M2) | xdylanm | MIT |
| `ngspice/elements_basic`, `ngspice/elements_rejects` | Authored in this repository (M3); manual examples paraphrased | xdylanm | MIT |
| `ngspice/statements_basic`, `ngspice/statements_rejects` | Authored in this repository (M4); manual examples paraphrased | xdylanm | MIT |
| `ngspice/document_basic` | Authored in this repository (M5); expected query results in the manifest | xdylanm | MIT |
| `ngspice/edits_golden` | Authored in this repository (M6); golden edit inputs and expected outputs, reviewed by hand | xdylanm | MIT |
| `ngspice/solver_stubs` (with `raw/`) | Authored in this repository (M7); stand-ins for include files, and raw-file samples written by ngspice 47 for netlists authored here | xdylanm | MIT |
| `ltspice/encoding_samples`, `ltspice/m0_export_candidate` | LTspice exports of circuits authored here | xdylanm | MIT |
| `ltspice/contributed_examples` | LTspice schematics (`.asc`, `.asy`) drawn by the maintainer in LTspice 26.1.1 for M8 (2026-11-01), with their `-netlist` exports (path comment normalised). LTspice run output is never committed (`.gitignore`; decision 0009 item 2). | xdylanm | MIT |
| `ltspice/elements_basic`, `ltspice/statements_basic`, `ltspice/names_basic`, and their `_rejects` families | Authored in this repository (M8) | xdylanm | MIT |
| `ltspice/edits_golden` | Authored in this repository (M8); expected outputs of golden edits on `contributed_examples`, reviewed by hand | xdylanm | MIT |

## LTspice evidence policy

Decision 0009 item 2. The LTspice licence restricts publishing benchmark or comparison results and
treats its documentation as confidential. The repository therefore records only syntax facts: what
LTspice accepts or rejects, and how it reads a value. LTspice raw files, logs, and timing or
performance numbers are never committed; probes run locally, and the LTspice reader tests use
synthetic files written here. `analogdevicesinc/ltspice-reference` (Apache-2.0) is the cited manual,
paraphrased; the built-in LTspice Help is not cited or copied. This policy is the maintainer's call
and is not legal advice.
