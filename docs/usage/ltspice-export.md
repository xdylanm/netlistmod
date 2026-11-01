# LTspice netlist export and batch simulation

The command-line behavior below was verified on Windows with LTspice 26.1.1 (file/product version
26.1.1.0), on 2026-10-20 and again in M8 on 2026-11-01. The schematics are authored in this
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
`tests/test_ltspice_export.py` fails with this explanation if an export has a `.lib` line into
LTspice's `lib\cmp\` folder.

### The path comment

The first comment of an export holds the absolute schematic path. The fixtures replace it with the
file name and change nothing else:

```text
* C:\any\folder\r_divider.asc   ->   * r_divider.asc
```

The re-export test applies the same normalisation before comparing with the committed netlist, so it
verifies the switch on every run and shows LTspice version drift. After an LTspice upgrade, run it
first:

```bash
uv run --env-file .env python -m pytest tests/test_ltspice_export.py --require-solver ltspice --no-cov
```

### What an export looks like

The fixtures are in
[`tests/corpus/ltspice/contributed_examples/`](../../tests/corpus/ltspice/contributed_examples/).

- A subcircuit instance placed from a block symbol is `X§U1 ... ;§pnba r1)r2`: LTspice inserts `§`
  after the prefix and adds the pin names as a comment. Both parse as they are.
- `-netlist` does **not** netlist a hierarchical block's sheet (no `.subckt`), so such an export does
  not run. `r_divider_subckt.asc` holds the definition in a directive instead.
- `SYMATTR Value ""` on a block drops the subcircuit name from the X line.
- A schematic comment becomes a `*` line, and `.backanno` is added before `.end`.
- Parts from LTspice's component database carry their data on the line
  (`C1 ... V=10 Irms=2.44949 mfg="KEMET" pn="A700V226M010ATE045" type="Al electrolytic"`), as in
  `LC_filter_mfg_components.asc`. These parse, and `set_param` edits the numeric ones.
- A source function (`half_rectifier.asc`: `SINE`) exports and runs, but the library reports
  `UnsupportedConstruct` until phase 2.

## Encoding

Every export (the eight `contributed_examples`, whether the schematic is UTF-16 or 8-bit, and the M1
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
- A failed run exits non-zero, and the log has a `file(line): message` line; a run with no analysis
  line exits 1 with no message.

LTspice raw files, logs and timing are never committed (decision 0009 item 2).
