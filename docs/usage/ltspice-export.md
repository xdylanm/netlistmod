# LTspice netlist export and batch simulation

The command-line behavior below was verified on Windows with LTspice 26.1.1 (file/product version
26.1.1.0), on 2026-10-20 and again on 2026-11-01. The schematics are authored in this
repository; no schematic or code from another project is used. These are local findings, not a
promise that all LTspice versions behave identically. Linux and macOS (wine) are not verified.

## Export a netlist from a schematic

```powershell
& $env:LTSPICE_EXE -netlist .\circuit.asc
```

LTspice exports without opening the GUI. It returns exit code 0 for a valid schematic and writes
`circuit.net` beside `circuit.asc`.

### Settings that change the export

**Default Devices** and **Default Libraries** (`DefaultDeviceModels` and `DefaultDeviceLibraries` in
`%APPDATA%\LTspice.ini`) must be off. With them on, every diode adds `.model D D` and a `.lib` line
naming the bundled `lib\cmp\standard.dio` by absolute path.

A running LTspice writes the setting to the file only when it exits, so a command-line export started
while the GUI is open still uses the old value. Close LTspice after changing the setting.

### The path comment

The first line of an export is a comment that holds the absolute schematic path, such as
`* C:\any\folder\r_divider.asc`. The library reads the first line as the title.

### What an export looks like

The schematics named below are the repository's examples ([for contributors](#for-contributors)).

- A subcircuit instance placed from a block symbol is `X§U1 ... ;§pnba r1)r2`: LTspice inserts `§`
  after the prefix and adds the pin names as a comment. Both parse as they are.
- `-netlist` does **not** netlist a hierarchical block's sheet (no `.subckt`), so such an export does
  not run. `r_divider_subckt.asc` holds the definition in a directive instead.
- `SYMATTR Value ""` on a block drops the subcircuit name from the X line.
- A schematic comment becomes a `*` line, and `.backanno` is added before `.end`.
- Parts from LTspice's component database carry their data on the line
  (`C1 ... V=10 Irms=2.44949 mfg="KEMET" pn="A700V226M010ATE045" type="Al electrolytic"`), as in
  `LC_filter_mfg_components.asc`. These parse, and `set_param` edits the numeric ones.
- A source function (`half_rectifier.asc`: `SINE(0 1 60k) Rser=1`) loads as `stimulus`, and
  `set_stimulus_arg` edits it. `Rser` stays a parameter of the line.

## Encoding

Every export (the eight `contributed_examples`, whether the schematic is UTF-16 or 8-bit, and the
samples in [`encoding_samples`](../../tests/corpus/ltspice/encoding_samples/)) is **UTF-8 without a
BOM**, which is the reference's statement about the netlister. The source layer's order (BOM, then
UTF-8, then `cp1252`, then Latin-1; [decision 0001](../decisions/0001-source-text-policy.md)) reads
them, and they round-trip byte for byte.

- The micro sign in an export is `µ` (U+00B5) or `μ` (U+03BC), as the schematic has it. Both are
  micro in LTspice and in the grammar.
- A CP1252 schematic containing `µ` and `°` exports them correctly. A UTF-8 schematic is read as
  Windows-1252, so its non-ASCII characters become mojibake in the netlist: draw schematics in
  LTspice, or keep them in CP1252.
- LTspice runs a hand-made UTF-16LE file with or without a BOM, and Latin-1. The library detects a
  UTF-16 BOM (`encoding_samples/utf16le_bom.cir`). It does not detect BOM-less UTF-16LE: decode the
  file and pass `SourceText(text, encoding="utf-16-le")`. It tries `cp1252` before Latin-1; the two
  differ on bytes 0x80–0x9F. See [discrepancies.md](../grammars/ltspice/discrepancies.md).

## Run a netlist in batch mode

```powershell
& $env:LTSPICE_EXE -b -ascii .\circuit.net
```

Batch mode is headless. It returns exit code 0 and writes `circuit.log` and `circuit.raw` beside the
input netlist, also when the working directory is another folder.

- `-ascii` writes an 8-bit text raw file with CRLF line endings and full precision. Without it, the
  raw file is binary with a UTF-16LE header, and it stores the variables after the first as float32.
- An AC analysis also writes its bias point to `circuit.op.raw`.
- A failed run exits non-zero, and the log usually has a `file(line): message` line. A run with no
  analysis line exits 1 with "No analysis specified." in the log, and an over-defined circuit (a loop
  of inductors and a source) exits 1 with a message that has no `file(line):`.
- A warning can take the same form: `V1 a 0` (no value) runs, with exit code 0 and a
  `file(line): Missing value, assuming 0V` line.

## For contributors

The example exports are in
[`tests/corpus/ltspice/contributed_examples/`](../../tests/corpus/ltspice/contributed_examples/).
They replace the path comment with the file name and change nothing else:

```text
* C:\any\folder\r_divider.asc   ->   * r_divider.asc
```

`tests/test_ltspice_export.py` re-exports each schematic, applies the same normalisation and
compares the result with the committed netlist, so it verifies the export on every run and shows
LTspice version drift. It fails with an explanation if an export has a `.lib` line into
LTspice's `lib\cmp\` folder (Default Libraries is on). After an LTspice upgrade, run it first:

```bash
uv run --env-file .env python -m pytest tests/test_ltspice_export.py --require-solver ltspice --no-cov
```

LTspice raw files, logs and timing are never committed
([decision 0009](../decisions/0009-ltspice-dialect.md) item 2).
