# 0012 — Carried limits from phase 1

- **Status:** proposed
- **Date:** 2026-11-03
- **Context:** The phase 1 review left limits for phase 2 to settle ([phase-1-review.md](../design/archive/phase-1/phase-1-review.md) section 6), and H5–H8 of the M9 review. Probes on ngspice 47 and LTspice 26.1.1 are in [m11-tasks.md](../design/m11-tasks.md) section 3. The maintainer decided these on 2026-11-03.
- **Decision:**
  1. **`.lib name` … `.endl` is an opaque block on both dialects (limit 6; amends decision 0002 and decision 0009 item 5).** Its text is preserved and not read, its body is not topology, and it is added, replaced or removed whole. Both solvers stop on such a block in a netlist and read it only in a library file, but the library does not validate whether a netlist can run. A `.lib` line opens a block only when it has one field and an `.endl` line follows before the next one-field `.lib` line or `.end`; a two-field `.lib` line may stand in the body, as vendor libraries write it. Any other `.lib` line stays an opaque statement, which is LTspice's file form. A stray `.endl` is unchanged.
  2. **`directives.add` writes the line it is given (limit 9).** A second line of one kind can be meant: ngspice runs two `.ac` or `.dc` lines and gives a plot for each. `directives.set` remains the upsert. LTspice stops on a second analysis, which is its behaviour to report. This limit closes as documented behaviour, and the phase 2 plan's refusal is dropped.
  3. **LTspice `.end` stays required (limit 2).** This closes what decision 0009 item 4 left to revisit. Edit placement and the round-trip tests depend on it.
  4. **`UNKNOWN_DIRECTIVE_PRESERVED` becomes `UNTYPED_DIRECTIVE_PRESERVED` (H6; amends §17).** The commands that get it are often documented ones, such as ngspice `.print` and LTspice `.backanno`, so "unknown" is wrong on both dialects. The `UnknownDirective` node keeps its name.
  5. **A name may be defined in an opaque block (H8; amends §7.8 and §17).** An opaque `.if` or `.lib` block counts as an `.include` does: an `UNRESOLVED_*` diagnostic in that scope is info and says so, and `set_model` accepts such a name with `allow_external=True`. A `.control` block does not count.
  6. **Library files are a later candidate, not in v1.** Whether a file is a netlist or a library cannot be told from the file: the extension is not binding, a section file can have an `.end`, and blocks look the same in both. The caller would choose, as with a dialect (P7). This needs an explicit way to open a library file with no title or `.end`, and typed section contents. It is added to §21 and decided after using the beta.
- **Consequences:**
  - The one exception to the phase 2 plan's compatibility rule: an ngspice netlist with such a block keeps parsing, but its topology signature changes, because the body leaves it. No solver ran such a netlist, and no corpus file had one.
  - An LTspice netlist with such a block goes from `ParseError` to loading, and LTspice stops when it runs.
  - One more terminal, `LIB_BLOCK_KW`, has a lookaround that strict mode cannot check (decision 0003).
  - Callers filtering on the old diagnostic code must change it, which §18 allows before 1.0.
  - This record stays `proposed` until the maintainer accepts it when M11 closes.
