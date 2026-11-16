# 0028 — xyce directives and the closed list of dot-commands

- **Status:** accepted (2026-11-16, maintainer; X-M2 gate G1)
- **Date:** 2026-11-16
- **Amends:** architecture §6.5 (directives top-level only; the unknown dot-command), for the hidden xyce dialect only; [decision 0027](0027-xyce-structure-names-and-values.md) item 7 and xm1-tasks 5.1 point 16 (directives in a body), whose record of Xyce's behaviour was wrong.
- **Context:** X-M2 ([xm2-tasks.md](../design/xm2-tasks.md)) makes the hidden xyce dialect read its analysis, option, initial-condition, sweep and measurement directives and the `.DATA` block, and decides the rest of the dot-commands. Its stage 1 compared the Xyce 7.10 manuals with the XyceNF 7.10.0 binary (section 5.1, points 1 to 30). The grammar follows the manual (decision 0026 item 5), and every refusal of a form the binary runs is a row in `docs/grammars/xyce/discrepancies.md` (decision 0027 item 12). The maintainer decided every point at G1.
- **Decision:** Item numbers below refer to xm2-tasks.md section 5.1, which holds the evidence and the details.
  1. **A closed list of dot-commands** (points 1 to 4).
     - The typed directives of this decision, the statements of decision 0027, and these untyped ones, read as `UnknownDirective`, top level only and continuable: `.PRINT`, `.FOUR`, `.FFT`, `.RESULT`, `.SAVE`, `.SENS`, `.NOISE`, `.HB`, `.LIN`, `.SAMPLING`, `.EMBEDDEDSAMPLING`, `.PCE`, and `.PREPROCESS ADDRESISTORS`.
     - xyce's `.SAVE` never builds `SaveDirective`: it writes an operating point and has no vectors.
     - `.PREPROCESS ADDRESISTORS` is allowed in a body, as `.PREPROCESS` is; a second of the same kind is a `ParseError`. `.PREPROCESS REMOVEUNUSED`, which deletes devices, stays an `UnsupportedConstruct` (P4) until X-M4.
     - Any other dot-command is a `ParseError`, with hints for `.TEMP`, `.PROBE`, `.title`, `.opt` and `.step param`. Xyce ignores them with a warning, and reads the lines of an unknown block as circuit lines.
  2. **Directives in a body** (point 5). Xyce silently ignores the analyses, `.OPTIONS`, `.STEP`, `.MEAS`, `.DATA` and the outputs in a subcircuit body; they are a `ParseError` there, as §6.5 says for the other dialects. `.IC`, `.DCVOLT` and `.NODESET` are allowed in a body, read per definition (Xyce applies them to every instance); a `$G` node in a body condition draws a warning, since Xyce ignores it.
  3. **Analyses** (points 7 to 13).
     - `.TRAN tstep tstop [tstart [tmax]] [NOOP] [UIC] [{schedule(…)}]`, as the manual writes it. `NOOP` and `UIC` are synonyms, each at most once, after the numbers. The schedule is a field of its own, with its own terminal; it may stand with tstart and tmax, although Xyce 7.10 stops on a schedule after tstart (a row; taken as a solver bug).
     - `.AC` takes `LIN|OCT|DEC points fstart fstop` or `DATA=table`.
     - `.DC` takes any number of sweeps, each with its own `LIN|DEC|OCT` or `LIST`, or `DATA=table` alone. A sweep target may hold `:`.
     - `LIST` takes at least two values, on `.DC` and `.STEP`.
     - `.OP` takes no fields.
     - Unbraced fields use the device-field number reader (decision 0027 item 8); braces and quotes are read on `.TRAN`, `.AC` and `.DC`, not on `.STEP`.
  4. **`.STEP`** (points 14 and 16). One sweep per line, no `param` keyword; `[LIN|DEC|OCT] target start stop step`, `target LIST v…` or `DATA=table`. `StepDirective.kind` gains `name`, `qualified` and `data`, with fields `parameter` and `data`; the document layer resolves a target as Xyce does, a parameter first. The quantity key folds a device's primary parameter (`R2` is `R2:R`).
  5. **Options** (points 18 to 23). `.OPTIONS` and `.OPTION` take a package from the manual's 21, case-folded; any other or none is a `ParseError`, except `.OPTION SCALE=v`. Item names are open. Items are `name=value`, a value a number, a word or a comma list; braces only in `SAMPLES` and `EMBEDDEDSAMPLES`; `OUTPUT` and `RESTART` take `INITIAL_INTERVAL` pairs. A repeated item: Xyce uses the first value.
  6. **Initial conditions** (points 24 and 25). `.IC`, `.DCVOLT` (building `IcDirective`) and `.NODESET` take `V(node)=value` or `node value` pairs, one form per statement; nodes may be `:` paths, resolved as decision 0027 item 4. A repeated node: Xyce uses the last value. `.IC` with `.NODESET` in one netlist draws a warning, since Xyce aborts.
  7. **`.MEAS`** (point 26) keeps the shallow typing, with a closed, required list of modes (TRAN, DC, AC, NOISE, FFT and the four `_CONT` forms).
  8. **`.DATA … .ENDDATA`** (point 27) is a new opaque block with a required name, its columns, plain numbers in a multiple of the columns, and a bare `.ENDDATA`, top level only. `DATA=` fields are references of a new kind `data`, in a namespace of their own.
  9. **Diagnostics** (points 10, 15, 16, 21, 24, 26 and 27), each a warning keyed per dialect: an analysis Xyce will not run (only the last of `.TRAN`, `.AC` and `.DC` runs; `.OP` gives way; two `.DC` lines join), a stepped parameter in an analysis field, a repeated `.STEP` quantity, `DATA=` beside other steps, several steps with `.OP`, `.IC` with `.NODESET`, a `.MEAS` mode with no matching analysis, an unresolved `DATA=` name, and `DUPLICATE_DEFINITION` for repeated options, conditions, results and tables, each message saying which one Xyce uses.
  10. **New names** (point 28) are best-effort additions under decision 0024 item 11, kept for the X-M8 release notes (xyce-plan.md section 8.2).
- **Consequences:**
  - `xyce.lark` replaces its `unsupported_directive` rule with the closed list and the typed directives; `XY-UNS-001` keeps only the planned letters and `REMOVEUNUSED`.
  - New fields on `TranDirective`, `AcDirective`, `DcDirective`, `StepDirective`, `OptionsDirective`, `OptionItem` and `NodeCondition`; a `.DATA` node; new `DiagnosticCode` members; a `data` reference kind.
  - The xyce plan's section 4 is corrected (UIC is a synonym of `NOOP`), and the X-M1 discrepancy row for a directive in a body is rewritten.
  - `docs/grammars/xyce/` gains its directive spec entries, a statements page and the discrepancy rows; the corpus and the solver tests cover each directive.
