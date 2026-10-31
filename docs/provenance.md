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
| `ltspice/encoding_samples`, `ltspice/m0_export_candidate` | LTspice exports of circuits authored here | xdylanm | MIT |
