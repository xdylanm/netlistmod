# 0004 — Element and value grammar

- **Status:** proposed
- **Date:** 2026-10-30
- **Context:** M3 parses the phase 1 element lines (R, C, L, K, V, I, D, X) and their values
  into typed nodes ([m3-tasks.md](../design/m3-tasks.md), section 2 records the maintainer's
  decisions). Architecture §21 left open how the RKM mode option interacts with the grammar
  and diagnostics. §5.3 described source value slots only as `value`, and §6.4 had an
  incomplete scale-factor set and placed RKM in the grammar without an option. The lexing
  risks were numeric node names, digit-leading model names, a value next to a model name, and
  parameter names that are known only by the `=` after them. All of these had to be solved
  under `strict=True`, preferably without new lookaround terminals.
- **Decision:**
  1. **RKM option.** `parse(source, dialect, *, rkm=False)`. The grammar has dedicated RKM
     terminals in both modes, and the transformer rejects them when the option is off, with a
     `ParseError` at the value that names the option (P13 (c)). With `rkm=True`, RKM values
     are accepted for R and C values only and get `NumericValue.notation == "rkm"`. Standard
     notation parses the same in both modes. One parser is cached per dialect; the option
     does not change the grammar. `DIALECT_GATED_SYNTAX` is emitted once the diagnostics API
     exists (M5). This resolves the §21 item "Interaction of the RKM mode option".
  2. **RKM letters follow IEC 60062** (IEC 60062:2016, *Marking codes for resistors and
     capacitors*). R: `L R K G T` (case-insensitive) and uppercase `M` (mega), plus a leading
     `R` or `L` (`R47`). C: `p n u µ m M F` (case-insensitive; `M` is milli). `E` is not a code
     letter (`4E7` is an exponent). A letter with no digit after it is standard notation.
     A lowercase `m` inside a resistor value is a `ParseError` in both modes, with a hint to
     use `L`. ngspice 47 reads R `1M0`/`4M7` as milli and C `4F7` as femto in both modes.
     Those values have their own terminals (`RKM_R_MEGA`, `RKM_C_FARAD`), and the node records
     `solver_mismatch=True`, so M5 can emit the new diagnostic **`RKM_SOLVER_MISMATCH`**
     without re-reading the text.
  3. **Scale factors** are the manual's set `t g meg k mil m u n p f a` (case-insensitive),
     plus `µ` as an `observed` entry. **Letters after a number** are part of the value token
     (§2.1.3.3), which is not the bare-formula catch-all §6.3 rule 10 forbids.
  4. **Separators are tokens.** `SEP` (blanks, or a `+` continuation line) is at priority 10,
     above the ignored `WS` (9) and `CONT` (7). `CSEP` (one comma) and `EQ` (`=` with blanks)
     are at 11. A field rule starts with its separator, `node: SEP WORD | …`, and a longer gap
     nests (`node: SEP node`, right-recursive), so the field token is lexed in the state
     reached by shifting its own separator. The contextual lexer therefore offers only the
     terminals valid at that place: a node `1` is a name, not a number. Two fields written
     without a separator are a syntax error (`1k5x`). A comma may only be the last separator
     before a field. A parenthesis outside a formula is a `ParseError` (phase 1).
     - Spike S1 findings: a separate gap rule ending right before a field merges its LALR
       lookaheads across all elements, and the field token is lexed with the union. A
       left-to-right gap list cannot tell its last separator from a middle one with one token
       of lookahead. Lark inlines a sub-terminal containing `|` without a group; such
       sub-terminals are written with an explicit group.
  5. **Priorities.** RKM terminals (4) > `NUMBER` (3) > `WORD` (2): in a value position a
     digit-leading field is a value, and an RKM form is tried before the standard number that
     would match only its prefix. Where no value can stand (a diode model, after a value), a
     digit-leading field is a model name (`1n4148`). Keywords (`dc`, `ac`, `off`, `r`,
     `resistance`, `q`, `params:`, …) are string terminals at `WORD`'s priority, so Lark
     re-types an exact `WORD` match only in states where the keyword is valid. Designators
     are one terminal per letter (`R_NAME`, …) at priority 4. **No new lookaround terminal**
     was needed; the pinned list in `tests/architecture/test_contracts.py` is unchanged.
  6. **Parameters and the X line.** `=` is its own token and absorbs the blanks around it, so
     `WORD EQ` is decided with one token of lookahead. The X name list is right-recursive
     (`x_node`/`x_last`), so a name is classified as a node or the subcircuit only after the
     parser has seen what follows it.
  7. **Expression forms** of R, C, L (`{expr}`, `'expr'`, and the keywords `r=`/`resistance=`,
     `c=`/`capacitance=`, `l=`/`inductance=`) fill the value slot, and the keyword is recorded
     as `value_keyword`. A keyword value is recognised only directly after the nodes.
     Formulas are not parsed.
  8. **Source value slots** (extends §5.3): `dc: Value | None`, `dc_keyword: bool`,
     `ac: AcSpec | None` with `AcSpec(magnitude, phase | None, span)`. The DC part comes before
     the AC part, as in the §4.1 general form. `DC` needs a value and `AC` needs its magnitude.
  9. **Unsupported forms** (stimulus functions, `DISTOF1/2`, `q=`) are grammar rules
     (`stimulus`, `charge`) whose arguments are statement text up to the line end, and their
     transformer method raises `UnsupportedConstruct` at the keyword. `params:` on an X line
     is recognised the same way and raises `ParseError`. Phase 2 letters still fail in the
     lexer and are classified by the loader (only `planned` letters are
     `UnsupportedConstruct`; a `supported` letter in a bad place is a `ParseError`).
  10. **Tree-less transformer** (amends §6.2 for the typed parse). `parse()` runs the
      transformer inside the LALR parser (`Lark(..., transformer=...)`). No tree is built and
      no second pass is needed, which keeps 20,000 element lines under 2 s. That mode passes
      no `meta`, so each item ends at its last token; every top-level rule ends with one. The
      per-parse source and options are kept in a `ContextVar`. This parser skips
      `propagate_positions`, because it builds no tree and token positions are always kept.
      `parse_tree()` still returns a positioned tree from the parser without a transformer.
      Because transformer errors are raised during the parse, the leftmost problem is reported
      first.
  11. **Corpus provenance:** `elements_basic` and `elements_rejects` are authored in this
      repository by `xdylanm`, MIT.
- **Consequences:**
  - Architecture §5.3, §6.2, §6.4, §17 and §21 are amended to match. The new diagnostic code
    `RKM_SOLVER_MISMATCH` is listed in §17.
  - Known limits:
    - a letter-leading expression written without blanks (`Rx+1000`) is a valid name and so
      reads as a model name (M5 reports it as unresolved);
    - a model named `r`/`resistance` (or `c`, `l`, `q` …) cannot stand directly after the
      nodes;
    - an RKM-shaped field such as `R2D2` in an R value position is rejected;
    - a name cannot end in `/`.
  - The element grammar is about 10 tokens per line. Lark's per-token cost sets a floor of
    roughly 1.5–1.9 s per 20,000 lines on the maintainer's machine, so the performance test
    has little margin there.
  - M6 edits replace the sub-spans recorded here (designator, nodes, values, model, parameter
    names and values); each slices back to exactly its text
    ([m3-elements.md](../design/m3-elements.md)).
