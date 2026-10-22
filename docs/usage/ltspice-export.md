# LTspice netlist export and batch simulation

The command-line behavior below was verified on Windows with LTspice 26.1.1
(file/product version 26.1.1.0) on 2026-10-20. The smoke circuit is authored
in this repository; no schematic or code from another project is used.

## Export a netlist from a schematic

```powershell
& $env:LTSPICE_EXE -netlist .\circuit.asc
```

LTspice can export without opening the GUI. It returns exit code 0 for a valid
schematic and writes `circuit.net` beside `circuit.asc`.

The M0 candidate schematic and normalized netlist are in
[`tests/corpus/ltspice/m0_export_candidate/`](../../tests/corpus/ltspice/m0_export_candidate/).
The first comment emitted by LTspice contains the absolute source path; the
candidate replaces that machine-specific path with the relative filename
`export_smoke.asc`. No other exported netlist content was changed.

## Encoding observations

The M1 samples in
[`tests/corpus/ltspice/encoding_samples/`](../../tests/corpus/ltspice/encoding_samples/)
were exported with LTspice 26.1.1.0. A CP1252 schematic containing `µ` and `°`
exports as UTF-8 without a BOM, preserving those characters. A separate UTF-8
schematic is needed to supply `Ω`, which CP1252 cannot encode; LTspice reads
its non-ASCII UTF-8 bytes as Windows-1252 and the resulting netlist contains
mojibake. This supports CP1252 for LTspice schematic input and UTF-8 for its
exported netlists: the decoder's UTF-8-first order handles LTspice exports, and
the CP1252 fallback mainly serves hand-made or older netlists. These are
observations for the tested version, not a cross-version guarantee.

## Run a netlist in batch mode

```powershell
& $env:LTSPICE_EXE -b .\circuit.net
```

Batch mode is headless. In the local spike it returned exit code 0 and wrote
`circuit.log` and `circuit.raw` beside the input netlist. This output location
was verified with a working directory different from the input file's
directory.

These switches and output behaviors are local findings, not a promise that all
LTspice versions behave identically. Re-run the smoke tests after upgrading
LTspice and re-check the encoding observations above, since they are specific
to the tested version.
