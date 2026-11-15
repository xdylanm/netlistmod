# qspice dialect plan (draft)

> **Status:** DRAFT. Written in [M21](./m21-tasks.md) (P2) from reviews Q1b and Q2b and the G1 decisions; for the maintainer's review. It plans work after 1.0 and changes nothing in the library.
> **Governed by:** [architecture.md](../architecture.md) §2, §6, §9.3, §10, §11 and §12; [decision 0024](../decisions/0024-the-1-0-public-api.md), the 1.0 contract; [decision 0025](../decisions/0025-qspice-help-as-reference.md), QSPICE's help as the reference.

## 1. Summary

A qspice dialect is feasible. About 80% of its analog lines and dot-commands overlap LTspice and SPICE, mostly reusing existing nodes with differences. No covered name, signature or exception class has to change (M21 section 5.1, items 6 to 8).

What is new or hard:
1. **Bare expressions in every value slot.** The help says expressions need no braces or quotes (`R1 A B 3*x`). Inside number lists the parser uses spacing as a hint. This conflicts with §6.3 rule 10 and is the main grammar problem.
2. **R takes an optional model before its value.** `R1 a b x` could then be a model or an expression.
3. **Six mixed-mode devices** with extended-character prefixes: ¥, Ã, €, £, × and Ø. They have fixed pin counts (16, 32 or 64) with a `¥` no-connect placeholder, or `«…»` pin groups. They need new node classes and topology rules.
4. **`.end` is optional,** which bears on `BEFORE_END` (decided in QS0, m21 5.1 item 7).
5. **Encoding.** The help says only that the netlist compiler is "8-bit clean". The bytes of a real export are probed, as M8 did for LTspice.

Solver tests are possible. Batch simulation, netlist export from a schematic and data export are documented command-line uses. QSPICE runs on Windows only, and CI stays solver-free (decision 0011).

## 2. Sources

- **[qspice-help]:** QSPICE's built-in help (`QSPICE.chm`), the build of 2026-11-05, read on 2026-11-15. Cited by topic and paraphrased under decision 0025. The help and extracts from it are never committed.
- **The installed `RevisionHistory.txt`:** release notes. They are used only as leads for probes, never as the basis of a grammar rule.
- No forums, third-party guides or source code were used. In particular, `KSKelvin-Github/Qspice` is unofficial and GPL-3.0 (m21 5.1 item 5). QSPICE's example schematics and models are not used either (decision 0025 item 3).

## 3. Devices

Kinds: **reuse** (an existing node as it is), **reuse with differences**, **new node**, **exclusion candidate**. "LT" is the LTspice overlay.

| Prefix | Device and form (paraphrased) | Help topic | Kind and notes |
|---|---|---|---|
| R | `R n1 n2 [model] value [params]`; an optional bracketed third node is a thermal node; `AC re im` gives a complex value; model type RES | "R. Resistor" | Reuse with differences: model before value, the thermal node, the RES model (LT's R has no model) |
| C, L | value, or the expression forms `C=`, `Q=`, `L=`, `FLUX=`; model type CAP; geometry parameters on L | "C. Capacitor", "L. Inductor" | Reuse with differences |
| K | `K L1 L2 [L3 …] coeff` | "K. Mutual Inductance" | Reuse |
| V, I | value plus named parameters (`AC`, `DC`, `RSER`, `TD`, triggers, scale factors); functions PULSE, SINE/SIN, EXP, SFFM, GAUSS, IGAUSS, CHIRP, PWL (points, `FILE`, a sound or waveform track, `REPEAT FOR n`/`FOREVER … ENDREPEAT`); written without parentheses | "V. Voltage Source", "I.  Current Source" | Reuse with differences: GAUSS, IGAUSS and CHIRP are new |
| D, J, O, S, T, U, W, X | as on LTspice; U is the uniform RC line; `params:` on X is optional; E has `RSER`, G `Rpar`, S instance parameters, W `ttol` | the device topics | Reuse, or reuse with differences for the parameters |
| E, G | gain, or gain with `LAPLACE=expr`; no `value=`, `table=` or POLY in the help (the release notes mention TABLE and POLY: probe) | "E. …", "G. …", "Laplace s-Domain Support" | Reuse with differences |
| F, H | `F/H n+ n- Vname gain`; the sense device may be E, H, L, V or a B voltage source | "F. …", "H. …" | Reuse |
| B | `V=`, `I=`, `R=` or `P=` with `LAPLACE`, `FREQ`, Thévenin and Norton forms | "B. Behavioral Sources" | Reuse with differences |
| M | always four nodes; VDMOS is a model flag, not a type | "M. MOSFET" | Reuse with differences (LT's VDMOS takes three nodes) |
| Q | the Q page writes the substrate as required, while the quick reference shows it optional | "Q. Bipolar Transistor", "Device Reference" | Reuse with differences; probe the three-node form |
| Z | MESFET only (no IGBT form) | "Z. MESFET" | Reuse with differences |
| Y | a piezoelectric crystal: a positional frequency, `dF=`, `Ctot=` | "Y. Piezoelectric Crystal" | New node; the letter collides with ngspice's TXL |
| A, N, P, `@`, `&` | not documented | "Device Reference" | `ParseError` |
| ¥ | gates, flip-flops and others: 16 pins, a type keyword, parameters; unused pins written `¥` | "¥-Device" | New node; `¥` is both a prefix and a no-connect token |
| Ã | transconductance blocks: 16 pins, a type, parameters | "Ã-Device" | New node |
| € | a 12-bit DAC: 32 pins | "€-Device" | New node |
| £ | 64 pins, then a type such as a comparator, multiplexer or gate driver | "£-Device" | New node |
| × | a saturating transformer: `«…»` winding groups, `TURNS=` | "×-Device: Saturating Transformer" | New node |
| Ø | a C++ or Verilog block: `«inputs» «outputs» «[common]»`, a module (DLL) name, typed parameters | "Ø-Device" | New node for the line; building the DLL stays outside the library (an exclusion candidate for anything beyond reading the line) |

Model types: CAP, CSW, D, LTRA, NJF, NMF, NMOS, NPN, PJF, PMF, PMOS, PNP, RES, SW, URC (`"Define Model(.model)"`). The Latin-1 accented case pairs count as the same letter (`"General Conventions"` note 1), so `ø1` is presumably an Ø device; probe it.

## 4. Statements

| Command | Notes | Help topic | Kind |
|---|---|---|---|
| `.op`, `.temp`, `.global`, `.ic`, `.nodeset` (alias `.ns`), `.option` | as on LTspice | the command topics | Reuse |
| `.tran` | `TSTOP [UIC]`, or the Berkeley form; `SKIPBP` | "Non-Linear Transient Analysis(.tran)" | Reuse with differences |
| `.ac` | linear by default; `list` | "AC Analysis(.ac)" | Reuse with differences |
| `.dc` | up to six sweep dimensions | "DC Sweep(.dc)" | Reuse with differences |
| `.step` | several dimensions on one line | "Step User-Defined Parameter(.step)" | Reuse with differences |
| `.param` | several pairs; four scopes (global, body, instance, definition) | "User-Defined Parameter(.param)" | Reuse with differences (bare expressions) |
| `.func` | `name(args) { expr }` | "User-Defined Function(.func)" | New node, or unknown directive first |
| `.model`, `.subckt`/`.ends` | the model-type list above; hierarchical schematics are netlisted as `.subckt` | "Define Model(.model)", "Subcircuit Definition(.subckt)" | Reuse with differences |
| `.inc`, `.lib`, `.endl`, `.libpath` | the path single-quoted, double-quoted or bare; `.lib` blocks; `.include` not documented (probe) | "Include File(.inc)", "Include Library(.lib)", "Library Search Path(.libpath)" | Opaque statements and blocks; `add_include` writes `.inc` on qspice |
| `.save`, `.meas` | wildcards; new `.meas` forms (`four`, `fra`, `plot`) | "Limit Saved Data Traces(.save)", "Measure(.meas)" | Reuse with differences |
| `.noise`, `.four`, `.bode`, `.net`, `.plot`/`.print`/`.probe`, `.abscissa`, `.display`, `.system` | analyses, outputs and actions; `.net` differs from LT's | the command topics | Unknown directive (typed later where needed) |
| `.prot` … `.unprot` | an encrypted section | "Protect with Encryption(.prot)" | New opaque block |
| `.if`, `.else`, `.endif` | mentioned only in passing | "Display on the Console(.display)" | Probe; opaque block, as on ngspice, if accepted |
| `.end` | optional; reading stops there | "End Netlist(.end)" | Decided in QS0 (m21 5.1 item 7) |

The help does not say whether an unknown dot-command stops QSPICE. QS0 probes it, to decide between a closed list (as LTspice's, decision 0009) and an open one.

## 5. Names, numbers, scoping and structure

- **Case:** case-insensitive, plus the listed Latin-1 accented pairs (`"General Conventions"` note 1). That is narrower than LTspice's full Unicode fold, so qspice gets its own fold rule.
- **Characters and encoding:** the compiler is "8-bit clean" (`"General Conventions"` item 2). The device prefixes include €, which among the 8-bit Western code pages only cp1252 holds. Decision 0001 (BOM, then UTF-8, then cp1252) probably decodes real exports. QS0 checks the bytes of an export with Ø, µ, € and Ω, and UTF-16 files, which the release notes say are read.
- **Ground and globals:** `0`, with `GND`, `CHASSIS` and `EARTH` as synonyms; `.global` nets and any `$G_` name (`"Global Net(.global)"`).
- **Hierarchy separator:** not named in the help (a probe).
- **Numbers:** the suffixes f, p, n, u/μ, mil, m, K, Meg, G and T, with no `a`; a capital Greek Mu reads as milli; hex `0x` and binary `0b` integers (`"General Conventions"` item 5). RKM is not mentioned: probe, then `rkm=True` is a `ValueError` or allowed.
- **Expressions:** braces and quotes are optional (`"General Conventions"` item 1), the main grammar problem (section 1). `^^` is XOR, and `&`/`|` act as `&&`/`||`. The function list is long, so the expression scan needs a qspice set of built-in names.
- **Comments and continuation:**
  - `*` or `#` starts a comment line; `;`, `//` or `$` starts an end-of-line comment, except the `$` of a `$G_` name (`"General Conventions"` item 4).
  - `+` continues a line, and so does a trailing `\`. The help documents `\` for `.system`; the release notes say it works on every line (probe).
- **Title and `.end`:** the first line is a title or comment. That is implied by the help rather than stated for a simulation deck (`"Include File(.inc)"`, `"Post Processor"`), so probe it. `.end` is optional (section 4).
- **Scoping:** four parameter scopes. A right-hand side refers to the next outer scope, and an instance value takes precedence (`"User-Defined Parameter(.param)"`). Use before definition and duplicates are probed.

## 6. Decisions the work needs

- **Q-D0 (QS0) — The dialect.** The overlay, and whether LTspice's rules are shared or copied. §6.1 allows only core plus one overlay, so sharing needs a decision. Also: the closed or open dot-command list, and the evidence policy (decision 0025 item 3 keeps raw files and logs out).
- **Q-D1 (QS0) — `.end`:** required as an exception, or optional with `BEFORE_END` at the end of the text (m21 5.1 item 7).
- **Q-D2 (QS1) — Bare expressions in value slots,** an exception to §6.3 rule 10, and how the end of a value is found without breaking P13.
- **Q-D3 (QS1) — R's model before its value:** how `R1 a b x` and `R1 a b x 1k` are read.
- **Q-D4 (QS1) — The qspice fold:** the Latin-1 pairs, capital Mu as milli, and extended-character prefixes.
- **Q-D5 (QS3) — Mixed-mode devices:** how `¥` placeholders and `«…»` groups enter `nodes`, `nets()` and the topology signature (m21 5.1 item 8); what Ø supports beyond reading its line.

## 7. Solver evidence

- **Platform:** 64-bit Windows 10 or 11 (`"Recommended Machine"`). QSPICE is free.
- **Batch run:** `QSPICE64.exe` (or `QSPICE80.exe`) on a netlist.
  - Options: `-ASCII` or `-binary` (the `.qraw` format), `-r <file>` (the `.qraw` name) and `-o <file>` (console output) (`"Simulator"`, `"Appendix I.  Inter-Process Communication"`).
  - `QPOST.exe <netlist>` evaluates `.meas` and `.four` from the matching `.qraw` (`"Post Processor"`).
- **Netlist export:** `QUX.exe -Netlist <file.qsch> [-stdout]` writes a `.cir` named after the schematic. The switch is case-sensitive. The `.cir` is a stable file the library can read, as LTspice's `-netlist` export is (`"Waveform Viewer"`, `"Schematic Capture"`).
- **Data export:** `QUX.exe -Export <file.qraw> exprs [N|all] [CSV|…]` (`"Waveform Viewer"`). CSV avoids writing a `.qraw` reader.
- **Version:** `QUX.exe -buildtimestamp` and `QPOST.exe -b`. QSPICE ships frequent builds, so `validated_on` records the build date.
- **Not documented:** exit codes, the default `.qraw` format, whether a run writes a log. QS0 probes them.
- **Licence:** running QSPICE to observe behaviour is use of the software (decision 0025 item 3).

## 8. Milestones

| Milestone | Content | Size |
|---|---|---|
| **QS0 — Probes and set-up** | The probe list (section 9) with circuits authored here; `docs/usage/qspice-export.md`; the harness (`tests/support/qspice.py`, CSV or a reader); `Dialect.QSPICE` with an empty overlay; the `docs/grammars/qspice/` skeleton; decisions Q-D0 and Q-D1 | S |
| **QS1 — Overlay skeleton** | Structure, comments and both continuations, names and the fold, numbers (hex and binary), `.param`/`.func`, `.model`, `.subckt`/X, includes and `.lib`, `.prot`, possibly `.if`; R, C, L, K, V, I, D; the directive list; names.md, scoping.md, numbers.md, devices.md; decisions Q-D2 to Q-D4 | M–L |
| **QS2 — Analog devices** | The stimulus functions; Q, M, J, Z; E, F, G, H, S, W; B; T, O, U; the Y crystal; LAPLACE forms | M |
| **QS3 — Mixed-mode devices** | ¥, Ã, €, £, ×, Ø: fixed pins, the `¥` placeholder, `«…»` groups, type keywords, Ø's module and typed parameters, ×'s TURNS; decision Q-D5 | L |
| **QS4 — Completeness audit and review** | As M18 and M19: the value-spec audit, the corpus, property tests, a solver run from a clean clone | M |

## 9. Probe list (QS0)

From Q1b and Q2b, where the help is unclear or silent:
1. **What `QUX -Netlist` writes:** the first line, whether it writes `.end`, line endings, any BOM, the bytes for Ø, µ, € and Ω, node-list comments.
2. **`.end`:** a netlist with no `.end`, and text after it.
3. **Unknown dot-commands** (error or ignored); whether `.include`, `.measure` and `.opt` are accepted.
4. **Name matching:** two elements differing only by prefix or by a case pair (`Ø1`, `ø1`); the hierarchy separator; whether a name can reach into an instance.
5. **The `¥` pin:** a no-connect, or one shared net. Whether empty and bus `«»` groups are allowed.
6. **Switch states** (bare `on`/`off`, or `off=1`).
7. **Values:** RKM (`2k7`), `{…}` in a value, letters after numbers (`10V`, `1kΩ`), Greek μ against the micro sign µ.
8. **Continuation:** `\` on every line; `+` after a comment or blank line.
9. **R:** how `R1 a b x` and `R1 a b x 1k` are read.
10. **Transistors:** a three-node Q; M with three nodes.
11. **E and G:** TABLE, POLY and `value=` (release notes only); `.if`/`.else`/`.endif`; AKO models.
12. **Parameters:** precedence, use before definition, duplicates; nested `.subckt`.
13. **Encoding and comments:** the bytes inside `.prot` sections; UTF-16 without a BOM; a `$` comment next to a `$G_` name.
14. **Running:** exit codes; the default `.qraw` format; whether a run writes a log.

## 10. Risks

1. **Bare-expression value slots** (decision Q-D2).
2. **Encoding of real exports.**
3. **Extended-character prefixes and case pairs.**
4. **Placeholder and grouped pins** in the topology signature.
5. **Frequent builds.** The release notes show syntax changes month by month, so the help edition and `validated_on` must name the build.
6. **Forms found only in the release notes** (TABLE, POLY, AKO, `.if`). They become `observed` entries when a probe confirms them (§11.3).
7. **A Windows-only solver.**
