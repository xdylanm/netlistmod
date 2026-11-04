# 0013 — Stimulus specs

- **Status:** proposed
- **Date:** 2026-11-04
- **Context:** Phase 2 replaces the rejected source functions with a typed `SourceSpec` (§5.3, G2). The manual and the LTspice reference each show one order of fields and one form of each function, and both solvers accept more. Probes on ngspice 47 and LTspice 26.1.1 are in [m12-tasks.md](../design/m12-tasks.md) section 3. The maintainer decided these on 2026-11-04.
- **Decision:**
  1. **Field order.** A function may stand before or after the DC and AC parts, with at most one of each, since both solvers read those lines alike. A bare value after a function is refused, as are two functions: there ngspice runs and LTspice stops, and the ngspice readings surprise (the output becomes 0; the last function wins).
  2. **The manual and the reference decide the forms (decision 0002 stands).** Parentheses are required, although both solvers run `PULSE 0 1 1u`; a blank before them is allowed, since the manual writes `trrandom (2 10m 0 1)`. The forms that have no parentheses in the references stay: EXTERNAL, DISTOF1 and DISTOF2, and LTspice's `PWL FILE=` and `PWL REPEAT …`. LTspice's scale factors stand before the list, the file or the repeat (maintainer, 2026-11-04), since the reference lists them as options of all four PWL forms; after any of those they stop LTspice and are refused. On an I line, `load` stands after the value or the function and not before a function, and `tbl=` stands alone, as the reference writes them, although LTspice runs more. A bare parameter name, `PULSE(0 x)`, is refused: ngspice runs it and LTspice stops, it is not in the manual, and the library would not see the reference.
  3. **`SINE` on ngspice is the one exception.** ngspice 47 reads it as `SIN`, and its manual does not list it. A netlist can move between the dialects with it.
  4. **`set_stimulus` leaves DC and AC alone.** It changes only the function's text, and with no function it adds one after those parts. `.op` reads a DC value beside a function on both solvers, and `.ac` needs the AC part. `set_dc` and `set_ac` edit them separately.
  5. **The edit API.** `set_stimulus(designator, text)`, `set_stimulus_arg(designator, key, value)` and `remove_stimulus(designator)`. `key` is a 0-based position or a name the line writes as `name=value`. A position one past the end appends, and a further one is an `EditError`, because filling the gap would mean inventing defaults. No table names positional arguments: the manual and the reference name them differently. A `function=` argument addresses DISTOF1 or DISTOF2, and `DISTOF` text in `set_stimulus` sets that input.
  6. **Argument counts are not checked, except that an empty list is refused.** The library does not validate solver inputs. `PULSE()` is refused because both solvers refuse it and it has no slot to edit.
  7. **RF port parameters.** `portnum` and `z0` (manual §4.1.11) are V line parameters, written with a blank or `=`, and `set_param` edits them. They were recognised only to be rejected, and v1 leaves no manual form unsupported (§6.7).
  8. **Amendments to the architecture:** §5.3 (`SourceSpec`), §7.2 (the operations). `NG-UNS-001` and `LT-UNS-001` no longer cover source functions.
- **Consequences:**
  - An LTspice trigger's expression is kept as text. The nets it reads are hidden (§7.8), as a formula's are, and so are the parameters: `Trigger={x}` gives no `UNRESOLVED_PARAM`. M15's read-only query covers them. `Trigger=` with blanks in it is refused, because a blank ends the field, although LTspice runs it.
  - A trigger on an I line loads, because the reference says all time-dependent sources support one, and LTspice stops on it.
  - `set_stimulus` and `remove_stimulus` drop a comment inside the function's span, since the span is what they replace. A comment before or after it stays. `set_stimulus` text must be one line.
  - A `set_stimulus` on a PWL with `r=` and `td=` replaces them too, since they are the function's. LTspice's `Rser`, `Cpar` and trigger parameters are the line's and stay.
  - Removing the function of an LTspice I line with no other value is an `EditError`, because the grammar requires a value there.
  - No corpus signature changed. The tree snapshot lost the three rejected files and gained the new accept files.
  - This record stays `proposed` until the maintainer accepts it when M12 closes.
