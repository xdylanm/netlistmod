# LTspice netlist export and batch simulation

The command-line behavior below was verified on Windows with LTspice 26.1.1
(file/product version 26.1.1.0) on 2026-10-20. The smoke circuit is authored
in this repository; no schematic or code from another project is used.

## Export a netlist from a schematic

```powershell
& $env:LTSPICE_EXE -netlist .\circuit.asc
```

LTspice can export without opening the GUI. It returns exit code 0 for a valid
schematic and writes `circuit.net` beside `circuit.asc`. The exported file has
no BOM; the M0 smoke output was ASCII-only, so the encoding of non-ASCII output
has not yet been established.

The M0 candidate schematic and normalized netlist are in
[`tests/corpus/ltspice/m0_export_candidate/`](../../tests/corpus/ltspice/m0_export_candidate/).
The first comment emitted by LTspice contains the absolute source path; the
candidate replaces that machine-specific path with the relative filename
`export_smoke.asc`. No other exported netlist content was changed.

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
LTspice; encoding for non-ASCII exported content remains an open risk.
