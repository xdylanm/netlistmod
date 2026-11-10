# M16 task list — Transmission lines (T, O, U as URC, Y, P)

> **Status:** ACTIVE — review round 1 (section 6) requires R1 and R2; implemented 2026-11-09 (section 5); section 2 decided by the maintainer on 2026-11-09
> **Part of:** [phase-2-plan.md](./phase-2-plan.md) (milestone M16). Governed by [architecture.md](../architecture.md) (§2, §5.3, §6.3, §7.2, §7.7, §7.8, §10). Follows [M15b](./archive/phase-2/m15b-tasks.md) and [decision 0014](../decisions/0014-transistors.md) (the node and model boundary).

## 1. Scope

M16 adds the transmission-line letters. Each is a fixed set of nodes, with a model on all but T, and a few named parameters, so the grammar is simpler than M13 to M15b's. The risk is in three places where a solver reads a line differently from what it says:

- ngspice ignores the reference nodes of Y and P;
- both solvers ignore some parameters, or fill in values the manual says must be given;
- ngspice ignores unknown bare words in a `.model` line, which matters for LTRA's flags.

Section 3.1 has the probes behind every point below.

- **In:**
  - **T** (lossless line), on both dialects: four nodes, `Z0=` (or `Zo=`), then `TD=`, or `F=` with an optional `NL=`, and ngspice's `IC=` (manual §6.1; [ltspice-ref] CIRCUIT-ELEMENTS-REFERENCE.md "T — Lossless Transmission Line").
  - **O** (lossy line), on both: four nodes and an LTRA model (§6.2; the reference's "O — Lossy Transmission Line").
  - **U** as a URC line, on both: three nodes, a URC model, `l=` and an optional `n=` (§6.3; the reference's "U — Uniform RC-Line").
  - **Y** (TXL), ngspice only: four nodes with ground references, a TXL model and an optional `len=` (§6.4.1).
  - **P** (CPL), ngspice only: 2X+2 nodes for X coupled lines, with ground references, a CPL model and an optional `len=` (§6.4.2).
  - **`.model` forms the new models need:**
    - LTRA's bare flags (`nosteplimit` and the others of §6.2.1), on ngspice;
    - CPL's matrix values (`R=1 0 1`, §6.4.2).
  - **Model types** LTRA, URC, TXL and CPL, with `MODEL_TYPE_MISMATCH`.
  - **Edits:**
    - `set_param`, `set_model` and `set_model_param` on the new lines and models;
    - two new operations, `remove_param` and `remove_model_param`, for every line and model that takes named parameters (decision 11).
  - **The ngspice digital U** is recognised by its shape, and raises `UnsupportedConstruct` until M17 (plan section 8, point 2).
- **Not in M16:**
  - the ngspice digital U, and A, N, `@` and `&` (all M17);
  - checking a model against its instance, such as a CPL matrix whose size does not match the line count, or an LTRA model without `len=`;
  - `remove_instance_param` on X lines;
  - adding or removing `.model` flags;
  - a release. M16 ends at its own merged pull request (decision 0018).

**Exit (plan):** each letter is `supported`, with spec entries validated wherever the solver can run the form. Also:
- The signature snapshot is unchanged, and the compatibility test still passes.
- A negative test shows that changing any node of each new letter is a `TopologyViolation`.
- Every M16 accept file loads, round-trips byte-exact and runs in its solver sweep.
- Every edit has golden diffs. Solver tests show that an edited `TD=`, `l=`, `len=`, model name and model parameter move the result, and so does a removed parameter.

## 2. Decisions (maintainer, 2026-11-09)

The maintainer decided the points one at a time on 2026-11-09:
- decision 3 as option B (both spellings);
- decision 5 as option A (ground only);
- decision 11 with `remove_param` and `remove_model_param` added;
- decision 13 with the maintainer's exports.

The rest were accepted as recommended. "Considered" marks an option weighed and not chosen. As in M13 to M15b, a form that the manual or the reference does not show is refused even when the solver runs it, and each such refusal gets a row in that dialect's `discrepancies.md` with its probe. Decision 3 is the one deliberate exception.

1. **Node classes and fields.** **Decided:**
   - A public base `TransmissionLine(Component)`, for `isinstance`, as `Transistor` and `Switch` are, and one class per letter:

     | Letter | Class | Fields beyond `Component` |
     |---|---|---|
     | T | `LosslessLine` | none: `Z0=`, `TD=`, `F=`, `NL=` and `IC=` are `params` |
     | O | `LossyLine` | `model` |
     | U | `RcLine` | `model`; `l=` and `n=` are `params` |
     | Y | `TxlLine` | `model`; `len=` is a parameter |
     | P | `CoupledLine` | `model`; `len=` is a parameter |

   - **Properties:**
     - `port1` and `port2` on T, O, Y and P give each port's nodes; on P, a port is its X nodes and then its reference node;
     - `conductors` on P gives X;
     - U has three `nodes` and no ports.
   - `IC=` holds a `ValueList`, as a transistor's `ic=` does.
   - *Considered:* `UniformRcLine` (longer, and the manual's own short name is "URC"); one class for all five (it would leave `model` optional and the ports undefined for U).
2. **T's parameters.** **Decided:** the parameter names are a closed list, as for LTspice's transistors (decision 0014 item 6).
   - **ngspice** takes `Z0=`, `TD=`, `F=`, `NL=` and `IC=` (and `Zo=`, decision 3), in any order, with a blank, a comma or a `+` line between them. `rel=` and `abs=` run, but the manual does not show them, so they are refused. ngspice stops on an unknown name, `m=`, a positional value and `off`.
   - **LTspice** takes `Zo=` and `Td=`, the only names in the reference (and `Z0=`, decision 3). `F=`, `NL=`, `IC=`, `rel=` and `abs=` run there, and are refused for the same reason.
   - **`Z0=` must be given.** Both solvers stop without it ("transmission line z0 must be given").
   - **Exactly one length form must be given:** `TD=`, or `F=` with or without `NL=`. The manual says one of the two is needed, and shows them as alternatives. Each case below is refused, with a discrepancies row:
     - no length at all: both solvers run it with a default delay (−9° at 100 MHz);
     - `TD=` together with `F=`: both run it, and `TD=` wins silently;
     - `NL=` without `F=`: ngspice runs it.
   - **ngspice's `IC=`** is exactly four values (V1, I1, V2, I2), comma-separated, with or without a blank after each comma. That is the transistors' `ic_param`. ngspice runs one to four values, and four separated by blanks, but stops on five. Other counts, and blanks, are refused.
   - A parameter written twice follows the library's existing rule for repeated parameters.
3. **`Z0` or `Zo`.** **Decided (option B): both spellings, on both dialects.**
   - The manual writes `Z0=` (zero) and the reference writes `Zo=` (letter O), and both solvers run both with the same meaning. The two characters are easy to confuse, and a line copied between the dialects should keep loading.
   - **The two spellings are one parameter.** A line that writes both (`Z0=50 Zo=75`) is treated as a repeated parameter, so an ambiguous impedance never loads silently.
   - **`set_param` and `remove_param` follow the line's spelling:** `set_param("T1", "z0", "75")` on a line written `Zo=50` writes `Zo=75`.
   - Each `discrepancies.md` records the other dialect's spelling as accepted. 0019 records this as a deliberate exception to decision 0002, not a general relaxation.
   - *Considered:* option A, each dialect taking only its own spelling.
4. **Instance fields of O, U, Y and P.** **Decided:**
   - **O** takes nothing after the model. Both solvers stop on `len=` or `m=` there.
   - **U** takes `l=`, which must be given, and an optional `n=`, in either order (manual §6.3; the reference's `L=` and `N=`).
     - Without `l=`, LTspice stops ("Length must be positive definite"), but ngspice runs the line with a near-zero length (0.4995 V where `l=5` gives 0.3333 V). This is refused, with a row.
     - A positional length (`U1 a b 0 umod 5`) is refused: ngspice runs it and ignores the value, and LTspice stops.
     - Both solvers stop on any other name, and on `off`.
   - **Y and P** take an optional `len=`, which overrides the model's `length=` (§6.4).
     - ngspice runs `m=2` on both and ignores it. It is refused, with a row, as is any other name.
     - A positional length is refused: ngspice ignores it on Y and stops on P.
   - **`l=`, `n=` and `len=` are values** in each dialect's value slot: a number, or a formula in braces or quotes. *(Corrected by review R2: a bare parameter such as `L=len`, which LTspice runs, is refused on LTspice U and T, as on every other LTspice element.)* Whether `n=` is a whole number is not checked.
5. **The reference nodes of Y and P must be ground.** **Decided (option A).**
   - The manual writes Y as `YXXXXXXX N1 0 N2 0 mname` and P's references as `GND1` and `GND2`. ngspice ignores those nodes: the same circuit with a port's reference held at 0.2 V gives the same result to four digits in `.op` and `.tran`, on Y and on P. T uses every node (0.4 against 0.5).
   - Accepting another name would put a connection into the signature that the solver does not make. So Y's second or fourth node, or one of P's two reference nodes, must be ground (`0` or `gnd`, any case, names.md N2). Anything else is a `ParseError` at the node, whose message says that ngspice ignores it and to write `0`. It gets a discrepancies row.
   - The rule is the same inside a subcircuit: a port name in a reference position is refused.
   - *Considered:* option B, accept the line as written and record a known limit (§7.8). Not chosen: §7.8 is for what the library cannot see.
6. **P's nodes and model (decision 0014 item 1).** **Decided:**
   - The model is the last name before `len=` or the end of the line, as on X and the transistors. A number there is refused as the model.
   - The names before the model must be an even number, at least 4 (one line) and at most 18 (eight lines, the manual's limit). Otherwise the line is a `ParseError` at its end. ngspice stops on an odd count.
   - `port1` is the first half of the nodes, and `port2` the second.
   - **T1 confirms the eight-line limit** with a valid nine-line matrix. The planning probes for eight and nine lines both stopped on the matrix ("not positive definite"). If ngspice runs nine lines, the limit stays as the manual says, and gets a discrepancies row.
7. **ngspice U: URC in M16, digital in M17.** **Decided:**
   - A U line is URC when exactly four names come before its first `name=value`, or before the end of the line: three nodes, then the model.
   - Every other U line is recognised by the grammar and raises `UnsupportedConstruct` ("ngspice digital U device"). This covers five or more names, and a type with parentheses such as `and(2)`, and NG-UNS-001 lists it. A URC line with four nodes before its model also lands here in M16; M17 decides its message.
   - A URC line whose first node is `inv` stays URC. Both solvers run it as one (plan section 8, point 2).
   - On LTspice, U is only URC, and any other shape is a `ParseError`.
   - ngspice's U becomes `supported` with milestone `M16, M17`, as E was `M14, M15`.
8. **LTRA's flags in `.model`.** **Decided:**
   - §6.2.1 lists six flags: `NOSTEPLIMIT`, `NO CONTROL`, `LININTERP`, `MIXEDINTERP`, `TRUNCNR` and `TRUNCDONTCUT`. The manual's example also writes `steplimit`. ngspice ignores any unknown bare word in a `.model` (`foobar` runs on LTRA and on D), so a run does not show that a flag is read.
   - **ngspice:**
     - An LTRA model accepts these flags in `ModelStatement.flags`, as `pchan`, with or without parentheses.
     - Each is one word: `nocontrol`, not the table's two words, which would be two unknown words.
     - `steplimit` is accepted because the manual's example writes it.
   - **On any other model type, these flags are a `ParseError`**, because ngspice would ignore them there.
   - **T1 checks which flags ngspice reads,** by a result each one changes (for example, a `.tran` step count). A flag no probe can confirm still loads, and its spec note says the solver cannot decide.
   - **On LTspice the flags are refused:** the reference lists only R, L, G, C and Len for LTRA. They get a discrepancies row naming the three that LTspice runs (`steplimit`, `nosteplimit`, `lininterp`).
   - *Considered:* accept the flags on any model type; accept them on LTspice too; accept any bare word.
9. **CPL's matrices in `.model`.** **Decided:**
   - A list of values after `R=`, `L=`, `G=` or `C=` in a `.model … CPL` (any case). The values are separated by blanks or commas, and may continue over a `+` line. Each value is a number, or a formula in braces or quotes.
   - The list is held as a `ValueList`. Its `text` and `span` run from the first value to the last, and its docstring widens from "comma-separated" to "a list of values".
   - A list on another parameter (`length=1 2`) or another model type (`is=1e-14 1e-15`, which ngspice runs, ignoring the second value) is a `ParseError` at the second value.
   - The number of values is not checked, because it depends on the line count of the instances (section 1, not in M16).
   - `set_model_param("pmod", "L", "50n 10n 50n")` replaces the whole list.
   - *Considered:* one parameter per value, which would lose the list as a unit.
10. **Model types.** **Decided:**
    - `model-types.json` gains `LossyLine: [LTRA]`, `RcLine: [URC]`, `TxlLine: [TXL]` and `CoupledLine: [CPL]`. TXL and CPL are ngspice only, because LTspice has no Y or P.
    - A model of another type is `MODEL_TYPE_MISMATCH`, and an undefined one is `UNRESOLVED_MODEL`, as for a diode. Both solvers stop on each, so no discrepancies rows are needed.
    - `set_model` checks the same table.
11. **Edits.** **Decided:**
    - **`set_param`** sets or adds T's, U's, Y's and P's parameters, including `IC=` as a whole list. A result that breaks decisions 2 to 4 (adding `TD=` beside `F=`, `m=` on Y) is refused by verification with the parse message. An O takes no parameter, which is an `EditError`.
    - **`set_model`** works on O, U, Y and P, with decision 10's check.
    - **`set_model_param`** covers the new models, including CPL's lists, and leaves an LTRA's flags as written.
    - **`set_value`** on any of the new lines is an `EditError` that names `set_param`.
    - Nodes, including P's line count, are not editable (§7.3).
    - **New: `remove_param(designator, name, *, scope=(), in_definition=False)`.**
      - **Coverage:** every line on which `set_param` can set a named parameter:
        - R, C, L, D, Q, M, J and Z;
        - `m=` on ngspice F and G;
        - B's parameters, and LTspice V and I parameters;
        - T, U, Y and P.
      - **Required parameters need no list of their own.** Verification re-parses the result, so removing `Z0=` from a T, `l=` from a U, or T's only length form is refused with the parse message.
      - **Refused with an `EditError` that names the right operation:**
        - a value keyword (`R1 a b r=1k`; use `remove_value`);
        - a positional area;
        - a flag (`off`, `pchan`, the LTRA flags);
        - a parameter the line does not have;
        - an X line's instance parameters.
      - **What is removed:**
        - the field, with the separator before it; `IC=` goes as a whole list;
        - a `+` line holding only that field goes whole;
        - if a comment sits between the field and the rest of the line, or shares the field's `+` line, the edit is refused (the rule of M15b's R3).
      - **A T's length form is switched in one `Netlist.batch()`,** which is verified once, against the final text:
        ```python
        with nl.batch() as b:
            b.set_param("T1", "f", "100meg")
            b.set_param("T1", "nl", "0.1")
            b.remove_param("T1", "td")
        ```
        A batch rejects two edits of the same span. If the two additions conflict there, T8b makes this batch work, or documents an order that does. It is tested either way.
    - **New: `remove_model_param(model, name, *, scope=(), in_definition=False)`,** for the `.model` defined in `scope`.
      - The field goes with the separator before it. As the first parameter inside parentheses, it goes with the separator after it instead (`ltra(r=10 len=1)` → `ltra(len=1)`).
      - Removing the last parameter keeps the parentheses (`d(is=1e-14)` → `d()`, which already parses).
      - A CPL list goes whole. Flags are not removable.
      - The `remove_param` rules for a missing parameter, comments and `+` lines apply.
      - Model contents are not checked (section 1). A model inside an opaque `.lib` block is not editable (M11 decision 1).
    - *Considered:* no removal operation, which would leave switching a T's length form as a hand edit.
12. **Tests that use T as the planned letter.** **Decided:** once T is supported, they use A, which stays planned on both dialects until M17:
    - the `phase_2_letter.cir` rejects of both dialects (new hashes; the LTspice entry in `test_ltspice_discrepancies.py` stays);
    - `test_parse_messages.py`'s two planned-letter tests;
    - `test_structure.py::test_continued_element_line_is_reported_at_its_first_line`, whose construct becomes `"ngspice A device"`.

    After M17 no letter is planned. The plan's M17 entry says that M17 drops these tests or moves them to a mocked matrix, as `test_structure.py` already does for `"error"`.
13. **Corpus.** **Decided:**
    - **The maintainer's base files** are in the repository. Their provenance is recorded as xdylanm, MIT (maintainer, 2026-11-09). Keep them byte for byte; T2's manifests must give these hashes:

      | File | SHA-256 |
      |---|---|
      | `ngspice/transmission_lines/test_kicad_tline.cir` | `e66ce416b8b38251386e8917ed2722dfa32ea1890dbc0e715c8835313b20ef96` |
      | `ltspice/transmission_lines/test_ltspice_tline_T.asc` | `3cc10406d3d3849e3781cda98b40acfdf85ca8fa47276f7695ec08455fea477a` |
      | `ltspice/transmission_lines/test_ltspice_tline_O.asc` | `00d4030e7df684561a6e6898112873df82f5f00a37935c7d9150cfdf19190352` |
      | `ltspice/transmission_lines/test_ltspice_tline_O_reject.asc` | `9b21590d0cf4093074c9b66b204d082bc23495b5343ffdd170029840b4e536b3` |
      | `ltspice/transmission_lines/test_ltspice_tline_U.asc` | `67b555e3ef85f8121ec29cc5094e273a9348d5c28935c190587c99f681cbe6e7` |

      The maintainer also exported each schematic to `.net` (2026-11-09). Re-exporting all four on LTspice 26.1.1 gives the same netlists (`_O` after it was saved again). `test_ltspice_tline_O.net` (`O1 N001 0 N002 0 myline`, with `.ac`) and `_U.net` run in LTspice, and `_O_reject.net` stops. Each export's first comment, the absolute path, was replaced with the file name (the export workflow) before the manifests took their hashes.

      - `test_kicad_tline.cir` is KiCad's TLINE exported for ngspice. **KiCad writes it as an O line with an LTRA model**, not a T (`OT1 … __T1` with `.model __T1 LTRA( r=0 l=5e-07 g=0 c=2e-10 len=1 )`).
      - **The LTspice `.net` files are the maintainer's exports,** with the export workflow's one normalisation applied (`docs/usage/ltspice-export.md`: the path in the first comment becomes the file name) and nothing else changed. `tests/test_ltspice_export.py` re-exports and compares `contributed_examples` today, and T2 extends it to this family.
      - `_T.net` has no analysis line, so it runs through the sweep's usual `.op` (`ensure_runs`), as other exports do.
    - T2 writes the manifests (family `transmission_lines`, author xdylanm, licence MIT, origin "schematics by the maintainer, and variants made for M16, each changing one form").
    - Everything else is written as variants that change one form each, and credited as variants:
      - the ngspice T, which KiCad doesn't export, and the ngspice U, Y and P;
      - the rejects of section 3.2.
    - **Three findings from the schematics** (exported to a scratch folder on LTspice 26.1.1, 2026-11-09):
      - **LTspice's own `tline` symbol writes `Z0=`** (`T1 N001 0 N002 0 Td=50n Z0=50`), not the reference's `Zo=`. Decision 3 lets that export load.
      - **The `ltline` symbol with its model in `SpiceModel` writes two names after the nodes**, `O1 N001 0 N002 0 myline LTRA`, because the symbol's `Value` still holds `LTRA`. LTspice stops on its own export ("Unknown parameter"). The library refuses it too: O takes nothing after its model (decision 4). The maintainer kept that schematic as `test_ltspice_tline_O_reject` (its export a reject; `LTSPICE_RUNS` does not list it, because LTspice stops), and changed `test_ltspice_tline_O` so that it exports `O1 N001 0 N002 0 myline`, which LTspice runs.
      - The `urc` symbol writes `U1 IN1 IN2 0 myRC L=1e-3 N=20`, which LTspice runs, with `.model myRC URC(… K=2. …)`.
14. **One decision record, 0019, and where the code goes.** **Decided:**
    - 0019 records this section. It amends:
      - §5.3: the new nodes, the `ValueList` in `.model`, and the LTRA flags in `ModelStatement.flags`;
      - §6.3 rule 14: P uses the boundary rule;
      - §7.2: the model types, `remove_param` and `remove_model_param`;
      - decision 0014 item 7: flags beyond `pchan` and `nchan`, and the removal operations.
    - It also records decision 3 as an exception to decision 0002.
    - **The rules** go in a new family module, `model/_rules_lines.py` (P12).
    - **The edits:**
      - the new lines need no new module: `set_param` and `set_model` are in `edit/_ops_elements.py`;
      - `remove_param` and `remove_model_param` go in a new `edit/_ops_remove.py`, since they cover every family.
    - **The ground check of decision 5** needs `0` and `gnd` in the model layer. If the import contracts keep `document/names.py` out of it, the ground names move down to a module both layers may use, with no change in behaviour.
    - *Considered:* the rules in `_rules_elements.py` (412 lines today); the removals in `_ops_common.py`, which holds shared helpers rather than operations.

## 3. Starting point (2026-11-09, `d2a7776`, `main`)

### 3.1 Probes

The probes ran on ngspice 47 and LTspice 26.1.1, from a scratch script outside the repository. Each circuit has `V1 in 0 dc 1 ac 1`, `R1 in a 50`, the line from `a` to `b` with ground references, a 50 Ω load `R2 b 0 50`, and `.param z=50 td=1n len=1`.

- A matched lossless line gives `v(b)` = 0.5 in `.op`. In `.ac` at 100 MHz its phase is −360·f·TD, so −36° for 1 ns.
- A line with 10 Ω of series resistance gives 0.4545 in `.op`.
- A URC line of 50 Ω (`rperl=10`, `l=5`) gives 0.3333.

**ngspice 47:**

| Line | Result |
|---|---|
| T `Z0=50 TD=1n`; `TD=1NS`; `ZO=50`; `TD=` before `Z0=`; braced; bare `Z0=z`; blanks around `=`; a comma between parameters; over a `+` line | Run, −36° |
| T `Z0=50 F=100meg NL=0.1`; `NL=` before `F=` | Run, −36° |
| T `F=100meg` without `NL=` | Runs, −90° (NL = 0.25, as the manual says) |
| T `Z0=50` alone (no length); `NL=0.1` without `F=` | Run, −9° / −3.6° |
| T `TD=1n F=100meg NL=0.2` (both forms, either order) | Runs, −36°: `TD=` wins |
| T `TD=1n` without `Z0=`; three nodes | Stop ("z0 must be given") |
| T `IC=0, 0, 0, 0`; `IC=0,0,0,0`; `IC=0,0`; `IC=1`; `IC=0 0 0 0` | Run |
| T `IC=` with five values | Stops |
| T `rel=1 abs=1` | Runs |
| T `foo=1`; `m=2`; positional `50 1n`; `off` | Stop |
| T `Z0=` twice | Runs, the last wins |
| T with port 1's reference at 0.2 V | Runs, 0.4: the reference is used |
| O LTRA `l=50n c=20p len=1`; `r=10`; the model in parentheses | Run, −36° / 0.4545 |
| O LTRA model without `len=` | Stops ("lossy line length must be given") |
| O `len=2` or `m=2` on the instance; three nodes; no model; a D or TXL model; an undefined model | Stop |
| LTRA flags `nosteplimit`; all six; `steplimit`; `no control`; in or out of parentheses, or first in them; `nosteplimit=1` | Run |
| LTRA, or D, with `foobar` | Runs: ngspice ignores the word |
| D `.model dmod d is=1e-14 1e-15` | Runs: ngspice ignores the second value |
| U `l=5`; `L=5`; `n=6`, before or after `l=`; `n=6.5`; `l={len*5}`; `l = 5`; inside a subcircuit; with `ngbehavior=psa` | Run, 0.3333 |
| U `l=` twice | Runs, the last wins |
| U without `l=`; `n=6` alone; positional `5` | Run, 0.4995: a near-zero length |
| U `m=2`; `off`; two or four nodes; a D or LTRA model; a model named `5` | Stop |
| U with its first node named `inv` | Runs as URC |
| U digital `U1 inv p n a b d0 dmio` at the top level | Stops (no PS flag) |
| Y `len=1` or `LEN=1`; without `len=` (the model's `length=`); braced | Run: 0.4545 in `.op`, 0.4013 at 5 ns in `.tran` |
| Y in `.ac` | Runs, but reads 0.2273 at 0°: TXL is for transient (§6.4.1) |
| Y `len=2` | Runs, 0.4167 |
| Y `m=2`; positional `2` | Run, ignored (as `len=1`) |
| Y without any length; three or five nodes; an LTRA model | Stop |
| Y with a reference node held at 0.2 V (port 1, port 2, or both) | Runs, the same result as grounded: ngspice ignores it |
| P one line `R=10 L=50n G=0 C=20p`, in `.op` and `.tran`; without `len=`; `len=2` | Run (0.4545 / 0.3394; 0.4167) |
| P two lines, matrices with blanks, commas, braces, in parentheses, over a `+` line inside a list | Run |
| P `m=2` | Stops (corrected by T1; the planning probe had it run, ignored) |
| P with a reference node held at 0.2 V; references named `gnd` | Run, the same result as grounded |
| P odd node count; positional `2`; a TXL model; matrices too short for the line count | Stop |
| P with eight or nine lines | Both stopped on the matrix written, so this is open (T1) |

**LTspice 26.1.1:**

| Line | Result |
|---|---|
| T `Zo=50 Td=1n`; `Z0=50`; `ZO=50 TD=1n`; braced; bare `Zo=z`; `Td=` first; a comma between; over a `+` line | Run, −36° |
| T `F=100meg NL=0.1`; without `NL=`; `Zo=50` alone | Run, −36° / −90° / −9° |
| T `Td=1n F=100meg NL=0.2` | Runs, −36°: `Td=` wins |
| T `IC=0,0,0,0`; `IC=0,0`; `IC=0 0 0 0`; `rel=1 abs=1` | Run |
| T `Td=1n` alone | Stops ("Z0 must be given") |
| T `foo=1`; `m=2`; positional; three nodes | Stop ("Unknown parameter") |
| T with port 1's reference at 0.2 V | Runs, 0.4 |
| O LTRA as on ngspice; without `len=` | Run (0.4545 both: LTspice does not require `len=`) |
| LTRA `nosteplimit lininterp`; the manual's example with `steplimit` | Run |
| LTRA with `foobar` | Stops ("Syntax error") |
| O `len=2` or `m=2` on the instance; three nodes; a D model | Stop |
| U `L=5`; `l=5`; `N=6`; braced; bare `L=len`; a model with every URC parameter | Run |
| U without `L=`; `N=6` alone | Stop ("Length must be positive definite") |
| U positional `5`; `m=2`; four nodes; a D or LTRA model | Stop |
| U with its first node named `inv` | Runs as URC |
| Y and P lines | Stop: not LTspice letters (the library already refuses them) |

**For T1:**
- P's line limit (decision 6);
- which LTRA flags ngspice reads (decision 8);
- a `.tran` for T and Y showing that `TD=` and `len=` move the waveform;
- the probes of decisions 2 to 9 as tests, each with the library's reading.

**T1 results (2026-11-09, ngspice 47 and LTspice 26.1.1):**

| Probe | Result |
|---|---|
| P with eight coupled lines, a valid diagonally dominant matrix (off-diagonal L 5n, C −1p) | Runs |
| P with nine lines, the same matrix | ngspice crashes (exit code 0xC0000409): the manual's limit of eight stands |
| P with diagonal-only matrices of two or more lines | Stops ("Forbidden combination of model parameters"): coupling is required |
| LTRA flags in a `.tran` (a 10-length line into 1k) | `lininterp` and `mixedinterp` change the waveform; `nosteplimit`, `steplimit`, `nocontrol`, `truncnr`, `truncdontcut` and `foobar` give the same one |
| T `TD=1n` against `TD=2n`, and Y `len=1` against `len=2`, in `.tran` | The first rise moves with `TD=` (1.05 ns to 2.05 ns) and with `len=` |
| P `m=2` (the planning table had it run) | Stops |
| U with two nodes (`U1 a b umod l=5`) | Stops; the library reads three names as the digital U (unsupported) |
| A CPL model without one of its matrices, or without `length=` when the instance writes `len=`; a TXL model without `g=` | Stops ("lossy line parallel conductance not given", "lossy line length must be given") |
| LTspice `A1 a 0 0 0 0 b 0 0 BUF`, the new planned-letter reject | Runs |

Each is a test: `tests/solver/test_ngspice_line_probes.py` and `test_ltspice_line_probes.py`.

### 3.2 Corpus

- **Today:** no accept file has a transmission line. `elements_rejects/phase_2_letter.cir` holds a T line in both dialects (decision 12).
- **The maintainer's base files** (decision 13), in the two new `transmission_lines` folders:
  - KiCad's TLINE for ngspice (an O with LTRA);
  - LTspice T, O, O reject and U schematics, each with its `.net` export.
- **Variants (T2),** each one change from an export or another variant:
  - **ngspice accept:** T with `TD=` (from the KiCad file, the O line replaced); T with `F=` and `NL=`; T with `IC=`; T with `Zo=`; O with an LTRA model that has flags; U with and without `n=`; Y with and without `len=`; P with one line, and with two lines and matrices.
  - **ngspice rejects:**
    - T: `t_no_length`, `t_td_and_f`, `t_nl_without_f`, `t_rel`, `t_ic_count`, `t_z0_and_zo`;
    - O and U: `o_param`, `u_no_length`, `u_positional`;
    - Y and P: `y_reference_node`, `y_param`, `p_reference_node`, `p_odd_nodes`, `p_param`;
    - models: `ltra_flag_on_diode`, `cpl_list_on_diode`.
  - **LTspice accept:** T with `Zo=` (the export writes `Z0=`).
  - **LTspice rejects:** `t_f_nl`, `t_ic`, `t_no_length`, `u_no_length`, `ltra_flags`. The ones LTspice runs are listed in `LTSPICE_RUNS`.

### 3.3 In the repository

- **Grammar:** T, O, U, Y and P are `planned` in both device matrices (Y and P on ngspice only). A line fails in the grammar, and the loader turns that into `UnsupportedConstruct` (`grammar/loader.py`).
- **Reusable pieces:**
  - the transistors' `t_name` and `t_number` and the boundary rule, for P;
  - `ic_param` and `IC_COMMA`, for T's `IC=`;
  - `ValueList`, for `IC=` and CPL's lists;
  - `model_flag` and `ModelStatement.flags`, for LTRA's flags.
- **`.model` today:** `param | model_flag | model_text`, where a flag is only `pchan` or `nchan`. A bare LTRA flag, or a second value after `R=`, is a `ParseError` ("this line ends too early").
- **Edits:** `Netlist.batch()` collects operations into one plan with one verification, and refuses two edits of the same span (`edit/api.py`, `Batch`). There is no removal of a named parameter today. `remove_value` and `remove_stimulus` are the nearest operations.
- **The signature:** new letters add entries only for new lines, so no saved digest changes. The tree snapshot will list the five letters among the expected terminals of the rejected files, as M13 and M14 did.

## 4. Tasks

[x] **T1 — Probes and decision record 0019.**
- Run the open probes of section 3.1, and add them to the tables.
- Write the probe tests first, in `tests/solver/test_ngspice_line_probes.py` and `test_ltspice_line_probes.py`, with M15b's shape: the line, whether the solver runs it, and the library's reading. They fail until the forms are in.
- Write 0019 from section 2, with status `proposed` until M16 closes, and add it to the decisions index.

[x] **T2 — Corpus first.**
- **Done with the task list (2026-11-09):**
  - the maintainer's `.net` exports have their first comment normalised (decision 13);
  - both `transmission_lines` manifests list the maintainer's files, each `pending: M16` with a `solver.skip`;
  - the family is in both solver sweeps' `FAMILIES`;
  - the tree snapshot has the KiCad file as a rejected file.

  The `.asc` hashes are those of decision 13. The `.net` hashes are those after normalisation.
- Add the variants of section 3.2. Move `test_ltspice_tline_O_reject.net` to a reject entry, with its line, column and error.
- Cover the family with the LTspice re-export test. A reject's manifest gives its line, column and error, and the rejects LTspice runs go in `LTSPICE_RUNS`.
- Mark each accept file `pending: M16`, so that the sweeps skip it until T9.

[x] **T3 — Nodes, model types and the planned letter (decisions 1, 10 and 12).**
- `TransmissionLine` and its five classes in `model/nodes.py`, exported from the package, with docstrings and properties.
- `model-types.json` and `MODEL_TYPE_MISMATCH`.
- The planned-letter tests and fixtures move to A. Add M17's note to the plan.

[x] **T4 — T (decisions 2 and 3).** On both dialects, in `model/_rules_lines.py`:
- the closed parameter lists with both spellings of `Z0`/`Zo`, the required `Z0=`, the one length form and ngspice's `IC=`;
- **negative tests:** each refusal of decisions 2 and 3, at its column, including `Z0=` with `Zo=`;
- **spec entries:** `NG-TLL-001` and `LT-TLL-001`.

[x] **T5 — O and U (decisions 4 and 7).**
- O with its model, on both dialects.
- U as URC on both, with the required `l=` and the shape rule. The ngspice digital U becomes `UnsupportedConstruct`, and NG-UNS-001 lists it.
- **Spec entries:** `NG-LTR-001`, `LT-LTR-001`, `NG-URC-001` and `LT-URC-001`.

[x] **T6 — Y and P (decisions 4, 5 and 6).**
- Y's four nodes and P's 2X+2, with the ground references, P's count and the boundary rule. The ground check sits where the import contracts allow (decision 14).
- **Topology tests:** every node is in `nodes`, `nets()` and the signature. Changing any node of each new letter is a `TopologyViolation`.
- **Spec entries:** `NG-TXL-001` and `NG-CPL-001`.

[x] **T7 — `.model` (decisions 8 and 9).**
- LTRA's flags on ngspice, refused on other types and on LTspice.
- CPL's lists, refused on other parameters and types.
- Extend NG-MOD-001 and LT-MOD-001, and the `.model` sections of `statements.md`.

[x] **T8 — Edits on the new lines (decision 11).**
- `set_param` (following the written `Z0`/`Zo`), `set_model`, `set_model_param`, and `set_value`'s message.
- **Golden diffs** for each, on both dialects, including a CPL list and an `IC=` list.
- **Property tests** that no edit here changes the signature.
- **Solver tests** that an edited `TD=`, `l=`, `len=`, model name and model parameter move the result. Use `.ac` or `.op` for T, O and U, and `.op` or `.tran` for Y and P.

[x] **T8b — `remove_param` and `remove_model_param` (decision 11).**
- Both operations, in `edit/_ops_remove.py` and `edit/api.py` (on `Netlist` and `Batch`), with docstrings.
- **Golden diffs** on both dialects:
  - a field mid-line and at the end;
  - an `IC=` list, and a CPL list;
  - a `+` line holding only the field;
  - the first and the last parameter inside `.model` parentheses.
- **Refusals:**
  - each `EditError` of decision 11;
  - a comment beside the field;
  - a required parameter, refused through verification.
- **The batch of decision 11** that switches a T from `TD=` to `F=`/`NL=`, tested to work. If two additions at one point conflict in a plan, fix that, or document the order that works and test that order.
- **Property tests** that neither operation changes the signature; a **solver test** that removing `len=` from a Y moves the result back to the model's length.
- `edit-layer.md`, `docs/usage/editing.md` and the CHANGELOG.

[x] **T9 — Corpus and snapshots.**
- The `pending` marks go, and every M16 accept file loads, round-trips and runs in its sweep.
- The tree snapshot gains the new files and the expected-terminal changes, and its docstring says so.
- No signature snapshot entry changes.

[x] **T10 — Documentation.**
- Both device matrices and their JSON files: T, O, U, Y and P become `supported`, with ngspice U at `M16, M17`.
- `docs/design/elements.md` and `statements.md`; `docs/usage/elements.md`, `editing.md` (a T and a CPL example) and `errors.md`.
- Both `discrepancies.md`, with a row for each refusal a solver runs, and decision 3's accepted spelling.
- README, CHANGELOG ("Unreleased") and the architecture amendments.

[x] **T11 — Final evidence and handover.**
- Open the pull request.
- Run the full local check set with `--require-solver ngspice --require-solver ltspice`, and record it and the CI run in section 5.
- List the design points worth reviewing, and set the status to `READY FOR REVIEW`.

### After the maintainer's approval

[ ] **T12 — Close M16.** Archive this list, accept decision 0019, and update the plan and index.

## 5. Results

### 5.1 Evidence

- **Full local check set** (2026-11-09): `pytest --require-solver ngspice --require-solver ltspice` on ngspice 47 and LTspice 26.1.1: **8,824 passed, 2 skipped**, 1,072 deselected (the other dialect's `ngspice_only` and `ltspice_only` runs), coverage **98.52%** (floor 90%), in 21 min 24 s. The two skips are the ones every run has.
- `ruff check`, `ruff format --check`, `mypy` (strict), `lint-imports` and `pre-commit run --all-files` pass.
- **Exit criteria:**
  - every letter is `supported` in both device matrices (ngspice U at `M16, M17`), with spec entries validated on its solver (NG-TLL-001, NG-LTR-001, NG-URC-001, NG-TXL-001, NG-CPL-001, LT-TLL-001, LT-LTR-001, LT-URC-001; NG-MOD-001 and LT-MOD-001 extended);
  - the signature snapshot is unchanged and its compatibility test passes;
  - changing any node of each new letter, and P's line count, is a `TopologyViolation` (`tests/document/test_line_topology.py`);
  - every M16 accept file of both `transmission_lines` families loads, round-trips byte-exact and runs in its solver sweep, and the maintainer's four LTspice schematics re-export to the committed `.net` files;
  - every edit has golden diffs (the `lines*` cases of both `edits_golden` families), and solver tests show that an edited `TD=`, `l=`, `len=`, model name and model parameter, a removed `len=` and a removed model parameter move the result (`test_an_edit_moves_the_result` on both solvers).
- The tree snapshot changed as its docstring says: the KiCad file parses, 35 files are new, and 17 rejected files list the five new letters among their expected terminals; `phase_2_letter.cir` and `structure_rejects/element_line.cir` now hold an A line, with the same entries.
- **CI:** see the pull request.

### 5.2 Design points worth reviewing

1. **A repeated impedance is refused, other repeats load.** Decision 3 makes `Z0=` with `Zo=` a "repeated parameter" that never loads, and decision 2 says repeats follow the library's existing rule, under which a repeated parameter loads and edits refuse it. I refuse any repeat of the impedance (`Z0=` twice too) at parse time and leave other repeats (`TD=` twice, `l=` twice) to the existing rule. Say if every repeat on a line should be refused.
2. **Three findings the task list did not have** (T1, section 3.1): ngspice 47 stops on `m=2` on P (the planning table had it run, ignored); a CPL model needs every matrix and `length=` even when the instance writes `len=`, and a TXL model needs `g=`; ngspice crashes rather than stops on nine coupled lines. The CPL-removal golden (`lines_cpl_remove.expected.cir`) therefore has a `solver.skip`, since model contents are not checked.
3. **A second T-based planned-letter fixture**, `structure_rejects/element_line.cir`, was not in decision 12's list; it now holds an A line too.
4. **Five names on an ngspice U whose last is a number or `off`** are a `ParseError` (positional length, flag) rather than the digital U, so that `u_positional.cir` is refused as decision 4 says. Any other five-name line is the digital U, as decision 7 says. A three-name line (`U1 a b umod l=5`) is the digital U too.
5. **The comment rule of `remove_param`.** A comment after the field on its line refuses the edit only when more fields follow or the field is on a `+` line; a comment after a line's last field stays put (`R1 a 0 1k m=2 ; note` loses `m=2`). This reads decision 11's "between the field and the rest of the line" literally.
6. **Removal of a field that starts a `+` line holding more fields** takes the separator after it, so the other fields stay on their line; a `+` line holding only the field goes whole.
7. **`remove_param` coverage** includes everything `set_param` sets, and also an LTspice E or G's `window=`/`nfft=`/`mtol=` and ngspice V's port parameters, which decision 11's list does not name; say if they should be refused.
8. **LTspice T refuses a comma between parameters** (`Zo=50, Td=1n`, which LTspice runs), as LTspice element lines take no comma; it has a discrepancies row.
9. **Refusal messages:** `rel=`/`abs=`, LTspice `F=`/`NL=`/`IC=`, a field after an O's model, and LTRA flags on LTspice each have their own message; `m=` on Y and P and unknown names are generic syntax errors at the field.
10. The new decision record is `proposed`; T12 accepts it.

## 6. Review round 1 (2026-11-09, `a9d386b`, #15)

### 6.1 Outcome

M16 goes back for R1 and R2. The letters, the `.model` forms, the topology and the edits other than removal match section 2, and they held up when I checked them by hand on both dialects. R1 widens the removal rule, as section 5.2 point 5 asks. R2 corrects a sentence of decision 4 that I wrote wrongly in planning.

- **Checks:**
  - pytest with ngspice 47 and LTspice 26.1.1 from `.env` (`--require-solver ngspice --require-solver ltspice`): 8,824 passed, 2 skipped, 1,072 deselected, coverage 98.52%, in 21 min 8 s. This matches section 5.1.
  - CI on #15 at `a9d386b` is green on all five jobs.
- **By hand, both dialects (a scratch script outside the repository):**
  - **T:**
    - `Z0=`, `Zo=` and `ZO=` load on both. `Z0=` with `Zo=`, or `Z0=` twice, is refused at the second, with its own message.
    - No length, `TD=` with `F=`, `NL=` without `F=`, no `Z0=`, `rel=`, and an `IC=` of two values are each refused at the right column, with their own messages.
    - LTspice's `F=` and `IC=` are refused with the reference named. LTspice's export (`Td=50n Z0=50`) loads.
  - **O:**
    - It takes nothing after its model. LTspice's `myline LTRA` export is refused, with the cause in the message.
    - A D model gives `MODEL_TYPE_MISMATCH`.
  - **U:**
    - A missing `l=` and a positional `5` are refused with the ngspice behaviour in the message.
    - `U1 inv b 0 umod l=5` is an `RcLine`. The digital line and the four-node line are `UnsupportedConstruct`. On LTspice, the digital line is a `ParseError`.
  - **Y and P:**
    - A non-ground reference is refused at the node; `gnd` and `GND` load.
    - P's `port1`, `port2` and `conductors` are right for one and two lines.
    - An odd count, 20 names and a model named `5` are refused.
  - **`.model`:**
    - LTRA's flags load on ngspice, inside parentheses too, and `nocontrol` and `steplimit` load. `no control` is refused.
    - The flags are refused on a D model, with their own message, and on LTspice.
    - CPL lists load with blanks, commas, braces and over `+` lines. A list on `is=` or `length=` is refused.
  - **Edits:**
    - `set_param` follows the written spelling: `Zo=50` becomes `Zo=75`, and LTspice's `Z0=50` becomes `Z0=75`.
    - Adding `TD=` beside `F=`, and removing `Z0=` or `l=`, are refused through verification.
    - `set_value`, `set_param` on O, and `set_model` to a D model name the right operation.
    - The batch that switches a T to `F=`/`NL=` gives `T1 a 0 b 0 Z0=50 f=100meg nl=0.1`.
    - `remove_param` refuses a value keyword, a positional area, a flag and an X line, each with its message.
- **Section 5.2:**
  - Points 1 to 4 and 6 to 10 are accepted. Point 5 is R1.
  - The P `m=2` correction in point 2 is noted, and section 3.1 should say so. It is part of R1's documentation pass.

### 6.2 Required changes

[ ] **R1 — `remove_param` and `remove_model_param` refuse safe edits.**

The rule in decision 11 refuses whenever a comment sits near the field. But a comment can only end a physical line, so most of these removals can never touch one. The rule should look at the text the edit removes, not at where the comments are. Results at `a9d386b`, by hand on both dialects:

| Line (removing `m=2`, `rs=10` or `TD=1n`) | At `a9d386b` | Safe result |
|---|---|---|
| `R1 a 0 1k m=2 tc1=0 ; note` | refused | `R1 a 0 1k tc1=0 ; note` |
| `R1 a 0 1k ; note` / `+ m=2` (also with CRLF; also LTspice) | refused | `R1 a 0 1k ; note` |
| `R1 a 0 1k` / `+ m=2 tc1=0 ; note` | refused | `R1 a 0 1k` / `+ tc1=0 ; note` |
| `R1 a 0 1k` / `+ tc1=0 m=2 ; note` | refused | `R1 a 0 1k` / `+ tc1=0 ; note` |
| `.model dm d(is=1e-14 ; sat` / `+ rs=10)` | refused | `.model dm d(is=1e-14 ; sat` / `+ )` |
| `R1 a 0 1k m=2 ; note`; `+ m=2` alone; `\` continuations; `d(is=1e-14` / `+ rs=10)` | right | unchanged |
| `T1 a 0 b 0 Z0=50` / `+ TD=1n ; delay` | refused | `T1 a 0 b 0 Z0=50 ; delay` |
| `.model dm d is=1e-14` / `+ rs=10 ; series` / `+ n=1` | refused | `.model dm d is=1e-14 ; series` / `+ n=1` |

Probed on ngspice 47 and LTspice 26.1.1:
- `+ )` on its own line runs on both, and loads.
- A `*` comment line inside a continued statement does not load, as before M16, so the removed text can never include one.

**Change:** remove the comment refusals. Choose the removed span from where the field sits on its physical line:

1. **The field follows another field of the statement on the same physical line:** remove the separator before it and the field. Comments only end a line, so this span never holds one.
2. **The field is the first one on its physical line, and a later field or the closing `)` is on the same line:** remove the field and the separator after it, up to that field or `)`. A comment later on the line stays.
3. **The field is the only one on its physical line** (a `+` line, or the line after a `\`): remove from the line break that ends the line before (`\r\n` or `\n`, with a `\` continuation's backslash and the blank before it) up to the end of the field. What followed the field on its line is kept as written, so a comment there moves back to the end of the line before (maintainer, 2026-11-09):

   ```
   R1 a 0 1k              R1 a 0 1k ; note
   + m=2 ; note     →     + tc1=0
   + tc1=0
   ```

   - With no comment, the line goes whole, as at `a9d386b`.
   - If the line before already ends with a comment, the two join on that line (`R1 a 0 1k ; first` and `+ m=2 ; note` give `R1 a 0 1k ; first ; note`). The text of both is kept byte for byte, and both solvers read the result as one comment.
   - Keeping `+ ; note` instead would not work: LTspice stops on a `+` line that holds only a comment ("Syntax error"), although ngspice runs it.

**Tests:**
- A golden diff for each row above, on both dialects, including CRLF, a `\` continuation and the two comments that join.
- A property test that a removal leaves the text of every comment byte for byte in the result.
- A solver test, on both dialects, that the results with a moved comment run.
- `test_remove_model_param_refuses_a_comment_beside_the_field` and its `remove_param` twin become tests of the new results.

**Docs:**
- Decision 0019 item 11, `edit-layer.md` (both rows) and `docs/usage/editing.md` get the new rule.
- In section 3.1's ngspice table, the P `m=2` row becomes "stops" (section 5.2 point 2).

[ ] **R2 — A bare parameter name on LTspice U (`L=len`).**

Decision 4 says that U's `l=`, `n=` and `len=` follow each dialect's value slot, "and on LTspice a bare parameter (`L=len`, which LTspice runs)". The second half is my error from planning: the library's LTspice value slot refuses bare names on every element, with a discrepancies row (LTspice `discrepancies.md`, the row for `R=x*2` and `m=x`). The implementation follows the sentence as written:
- U takes `L=len` (`U_BARE` in `ltspice.lark`);
- T, whose decision says nothing about it, refuses `Zo=z` with a generic message, although LTspice runs it (−36°, section 3.1).

So the two letters disagree.

- **Decided (maintainer, 2026-11-09):** refuse the bare name on U too, as on every other LTspice element:
  - drop `U_BARE`;
  - give U and T one message suggesting `{len}`;
  - add both to that discrepancies row;
  - correct decision 0019 item 4, and decision 4 of section 2.

  No corpus file writes `L=len`. The tests that accept it become refusals: `test_ltspice_lines.py`, and the probe rows, which keep "LTspice runs it". `LT-URC-001` and `elements.md` change with them.
- *Considered:* accept bare names on both U and T, as a second exception to the LTspice value rule.

### 6.3 Noted, no change required

- **The `.net` exports disappeared from the working tree after the commit.** At 18:31, the four `transmission_lines/*.net` files were missing from the working tree of `m16-lines`, although `a9d386b` has them. Nothing in the tests deletes them: the harness removes only `.raw` and `.log` files, in temporary folders. I restored them from the commit, and they re-export identically. If you open these schematics in the LTspice GUI, check afterwards that the exports are still there.
- **LTspice and a `+` line that holds only a comment.** The library loads such a line on LTspice, but LTspice stops on it. This was here before M16; it belongs with M18's audit of value and line forms.
- **Messages that are still the generic list of expected tokens**, for M18 with M15b's (plan M18):
  - `m=` on Y and P (section 5.2 point 9);
  - `IC=0 0 0 0`;
  - LTspice's `Zo=z` gets its own message in R2, so it leaves this list.

### 6.4 Exit for this round

1. Make R1 and R2 as decided.
2. Run the full check set with `--require-solver ngspice --require-solver ltspice`, read CI once after the push, and add a short report as 6.5.
3. Set the status to `READY FOR REVIEW`. **Do not archive** (T12 follows approval).
