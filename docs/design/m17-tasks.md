# M17 task list — Special and mixed-signal devices (ngspice A and N; LTspice A, `@` and `&`)

> **Status:** READY — approved by the maintainer on 2026-11-10, with section 2 decided and the provenance of the base files (section 3.2) confirmed
> **Part of:** [phase-2-plan.md](./phase-2-plan.md) (milestone M17). Governed by [architecture.md](../architecture.md) (§2, §5.3, §6.3, §7.2, §7.7, §7.8, §10). Follows [M16](./archive/phase-2/m16-tasks.md), [decision 0014](../decisions/0014-transistors.md) (the node and model boundary) and [decision 0015](../decisions/0015-controlled-sources.md) (controlling references).

## 1. Scope

M17 adds the last planned letters. The probes of section 3.1 found that they differ a lot in size:

- LTspice `&` and N are small.
- LTspice A and `@` are about the size of an M16 letter.
- ngspice A has its own port syntax. Its `.model` cards also take values the library refuses today: vectors, `TRUE`/`FALSE` and quoted strings.
- **The ngspice digital U is out of v1** (decision 1, maintainer, 2026-11-10). It is bigger than the plan assumed:
  - Real digital libraries are written for PSpice compatibility mode, where `$` is part of a name (`$G_DPWR`, `$D_HI`). The ngspice grammar reads `$` as a comment.
  - ngspice also runs a line without its I/O model, so the line's shape alone does not tell where the nodes end.

  Section 3.1 keeps its probes as the record behind the exclusion.

- **In:**
  - **ngspice A** (code models, manual §8.1, §22.2.1). The port syntax:
    - the port types of Table 8.1, with or without parentheses;
    - vectors in `[ ]`, `~` inversion and `null`;
    - `%vnam`, which names a source.

    A takes no instance parameters, and its model must be the last name on the line.
  - **The `.model` values code models need:**
    - vectors in `[ ]`;
    - `TRUE` and `FALSE`;
    - quoted strings (`file="…"`).

    These are allowed only on a model type that is not a built-in SPICE type (decision 5).
  - **ngspice N** (OSDI devices, manual §9.3.1.6):
    - nodes, then the model by the boundary rule, then named parameters;
    - validated on the OSDI models that the Windows build of ngspice 47 ships (section 3.1).
  - **LTspice A** (special functions; [ltspice-ref] CIRCUIT-ELEMENTS-REFERENCE.md "A — Special Functions"): eight nodes, a function name and named parameters.
  - **LTspice `@`** (the frequency response analyzer; the reference's "@ — Frequency Response Analyzer"): two nodes, an optional `zm`, and named parameters, some of them lists.
  - **LTspice `&`** (the FRA probe; the reference's "& — Frequency Response Analysis Probe"): four nodes and nothing else.
  - **Edits** on the new lines and models (decision 9).
  - **LTspice `.machine` and the ngspice digital U** are recorded as named v1 exclusions (plan section 8, point 4; decision 1).
  - **The planned-letter tests** move to a mocked matrix, because no letter is planned after M17 (decision 10).
- **Not in M17:**
  - the ngspice digital U, which stays `UnsupportedConstruct` in v1 (decision 1);
  - checking an instance against what its model defines:
    - a code model's port count and types;
    - an OSDI module's node count;
    - parameter names on a code-model or OSDI `.model`;
  - editing nodes or ports (§7.3), an LTspice A's function, and the `zm` flag;
  - LTspice `.model` lines of a special-function type (`.model x BUF(…)`): the library loads them and LTspice stops on them. M18's audit takes this;
  - a release. M17 ends at its own merged pull request (decision 0018).

**Exit (plan):** no letter in either matrix is `planned`. Also:
- The signature snapshot is unchanged, and the compatibility test still passes.
- A negative test shows that changing any node, port or controlling source of each new letter is a `TopologyViolation`.
- Every M17 accept file loads, round-trips byte-exact and runs in its solver sweep.
- Every edit has golden diffs. Solver tests show that each of these moves the result:
  - an edited code-model parameter, including a vector;
  - an OSDI instance parameter;
  - an LTspice A parameter;
  - an `@` parameter.

## 2. Decisions (maintainer, 2026-11-10)

The maintainer took decision 1 as "drop the digital U from v1", decision 3 as option A, and agreed decisions 4, 7 and 8 explicitly. The rest were accepted as recommended. Decision 12's KiCad files were replaced by netlists written here (section 3.2). "*Considered:*" marks an option weighed and not chosen. As in M13 to M16, a form that the manual or the reference does not show is refused even when the solver runs it. Each such refusal gets a row in that dialect's `discrepancies.md`, with its probe. Decision 3 proposes one deliberate exception.

1. **The ngspice digital U is a named v1 exclusion.** **Decided (maintainer, 2026-11-10).** Three findings make it too large for v1 (section 3.1):
   - **`$` names.** The manual's own example and every ngspice digital example use `$G_DPWR`, `$G_DGND`, `$D_HI` and `$D_NC`. In PS mode `$` is an ordinary character (§2.4.4), and the digital U runs only in PS mode. The library reads `$` as a comment, so such a line would lose nodes silently, or fail to load. Reading them would need a PS reading mode, and plan section 8, point 2 rules out a parser option.
   - **Where the nodes end.** ngspice runs `U1 inv vp vg a y d0` without its I/O model. To know where the models start, the library would have to know each basic type's node count: about forty types of §10.1.2, with their `(n)` and `(n,m)` forms. The manual gives none of these counts.
   - **LOGICEXP and PINDLY** have keyword sections that the manual does not describe.

   **What changes:**
   - Every U line that is not a URC line keeps raising `UnsupportedConstruct` ("ngspice digital U device"), with M16's shape rule (decision 0019 item 7) unchanged. Its message says the device is out of scope for v1, as `.machine`'s does (decision 11).
   - The ngspice device matrix keeps U `supported`, with milestone `M16` and a note naming the exclusion.
   - Decision 0020 records it, and it amends plan section 8, point 2.
   - The plan's v1 scope (section 1, "Not in v1"), M17 entry and section 5 say so.
   - NG-UNS-001's note, `docs/usage/errors.md` and the README's limits name it.

   *Considered:* splitting it into an M17b before M18 (proposed in the draft).
2. **Node classes and fields.** **Decided:**

   | Letter | Dialect | Class | Fields beyond `Component` |
   |---|---|---|---|
   | A | ngspice | `CodeModelDevice` | `model`; `ports` (decision 4) |
   | N | ngspice | `OsdiDevice` | `model`; instance parameters are `params` |
   | A | LTspice | `SpecialFunction` | `function` (an `Identifier`, as written); parameters are `params` |
   | @ | LTspice | `FrequencyAnalyzer` | `impedance` (the `zm` flag, or `None`); parameters are `params`; `reference_net` and `intermediate_net` (decision 7) |
   | & | LTspice | `FraProbe` | `analyzer` (an `ElementReference`, decision 8) |

   - Properties:
     - `SpecialFunction.inputs` (nodes 1 to 5), `outputs` (6 and 7) and `common` (8), as the reference names them;
     - `FraProbe.output_pair` and `input_pair`.
   - No shared base class: A means a different device in each dialect, so it gets a class per dialect, as T to P did.
   - *Considered:* `XspiceDevice` (XSPICE is the framework; the manual calls these lines "code model instance cards"); one `SpecialDevice` class with optional fields.
3. **LTspice A's function names.** **Decided (maintainer, 2026-11-10): option A**, the 13 names LTspice uses, as an exception to the reference. The reference lists symbols (INV, BUF, AND, OR, XOR, SCHMITT, SCHMTBUF, SCHMTINV, DFLOP, VARISTOR, MODULATE, and the OTAs OTA, OTA2, MOTA, MOTA2, MOTA3 and MOTA8). These are not the names in a netlist:
   - LTspice stops on `INV`, `SCHMTBUF`, `SCHMTINV` and `MODULATE` ("Expected valid special function name").
   - LTspice 26.1.1's symbol library (`lib/sym/Digital` and `lib/sym/SpecialFunctions`) has 26 symbols with prefix A. Their `SpiceModel` attributes write 13 function names. Each symbol uses a subset of the eight terminals, and the reference says that an unused one is tied to terminal 8 (`com`).
   - Each of the 13 runs in a probe, some only with the parameters they need (`COUNTER` `cycles=`, `MODULATOR` `mark=`).

   | Function name in the netlist | Reference symbols | Other LTspice symbols | Terminals the symbols use (position: pin) | Parameters in the reference | Probe (`A1 in 0 0 0 0 out 0 0 <name>`) |
   |---|---|---|---|---|---|
   | `BUF` | BUF, INV | buf1 | buf: 1 in, 6 `_Q`, 7 Q, 8 com. inv: 1 in, 6 `_Q`, 8 com. buf1: 1 in, 7 Q, 8 com | gate | Runs; `Vhigh=5` gives 4.995 |
   | `AND` | AND | — | 1–5 a–e, 6 `_Q`, 7 Q, 8 com | gate | Runs |
   | `OR` | OR | — | 1–5 a–e, 6 `_Q`, 7 Q, 8 com | gate | Runs |
   | `XOR` | XOR | — | 1–5 a–e, 6 `_Q`, 7 Q, 8 com | gate | Runs |
   | `SCHMITT` | SCHMITT, SCHMTBUF, SCHMTINV | diffschmitt, diffschmtbuf, diffschmtinv | schmitt: 1 in, 6 `_Q`, 7 Q, 8 com; schmtbuf drops 6, schmtinv drops 7; the diff variants add 2 in− | gate, `Vt`, `Vh` | Runs, also with `Vt=0.5 Vh=0.1` |
   | `DFLOP` | DFLOP | — | 1 D, 3 CLK, 4 PRE, 5 CLR, 6 `_Q`, 7 Q, 8 com | gate | Runs |
   | `SRFLOP` | — | srflop | 1 S, 2 R, 6 `_Q`, 7 Q, 8 com | none (gate parameters assumed) | Runs |
   | `VARISTOR` | VARISTOR | — | 1 invin, 2 noninvin, 7 out, 8 com | none | Runs; `Rclamp=2` runs (the maintainer's schematic); `Rclamp=1 Vrating=5` stops: "Unknown parameter" (`Vrating` is not a name) |
   | `MODULATOR` | MODULATE | modulate2 | modulate: 1 FM, 2 AM, 7 Q, 8 com. modulate2 adds 6 COS, and 7 is SIN | `mark`, `space` | Runs with `mark=`; without it stops: "Missing mark frequency" |
   | `OTA` | OTA, OTA2, MOTA, MOTA2, MOTA3, MOTA8 | — | ota, ota2: 1 invin, 2 noninvin, 7 out, 8 com. mota, mota2 add 3 mult. mota3: 3 mult+, 4 mult−. mota8 also adds 5 −V, 6 +V | `G`, `Vhigh`, `Vlow`, `Iout`, `Isink`, `Rout`, `Cout` | Runs, also with `G=1m Iout=1m Isink=-1m` and `Rout=1k` |
   | `PHASEDET` | — | phidet | 1 a, 2 b, 7 Q, 8 com | none | Runs; `PHIDET` (the symbol's file name) stops |
   | `COUNTER` | — | counter | 1 CLK, 6 Phi2, 7 Phi1, 8 com | none | Runs with `cycles=4`; without it stops: "Missing value of cycles" |
   | `SAMPLEHOLD` | — | sample | 1 in+, 2 in−, 3 CLK, 4 S/H, 7 out, 8 com | none | Stops with only terminal 1 connected ("Either the S/H or CLK input must be connected"); T1 writes a valid one |
   | — | INV, SCHMTBUF, SCHMTINV, MODULATE as names | — | — | — | Stop: "Expected valid special function name" (also `FOO`) |

   "gate" is the reference's gate parameters: `Vhigh`, `Vlow`, `Trise`, `Tfall`, `Td`, `Rout`, `Cout` and `Ref`. The six OTA symbols differ only in which terminals they use: the multiplier input of the MOTAs, and the supply pins of MOTA8. They all write `OTA`, so the library sees one function. Which OTA parameters apply to which terminals is not documented, and the library does not check it (decision 7: open parameter names).

   **Option A (decided): the 13 names, case-insensitive, as a closed list.** Any other name is a `ParseError` at the name. This is an exception to "the reference shows it", like M16's decision 3: the reference's names do not load at all, and the 13 are what LTspice's own schematics export. The discrepancies row records the mapping from each symbol to its name.
   - *Option B:* only the nine names behind the reference's symbols: `BUF`, `AND`, `OR`, `XOR`, `SCHMITT`, `DFLOP`, `VARISTOR`, `MODULATOR` and `OTA`. A schematic with a counter, phase detector, sample-and-hold or SR flip-flop would then not load.
   - *Considered:* any name. LTspice stops on an unknown one, so this would not misread a line, but it would load a netlist that does not run.
4. **ngspice A's ports, and how they reach `nodes` and the signature.** This is the plan's open question (section 3, point 4). **Decided (maintainer, 2026-11-10):**
   - **The grammar** reads A in its own rules, so the node class that every other element uses does not widen (§6.3 rule 9). After the designator comes a list of ports, then the model, which is the last name on the line.
     - A port is a connection or a vector `[ … ]`.
     - A connection is:
       - an optional port type from Table 8.1, case-insensitive (`%v`, `%i`, `%g`, `%h`, `%d`, `%vd`, `%id`, `%gd`, `%hd`);
       - then one node (two for a differential type), with or without parentheses;
       - or `null`;
       - or `%vnam` and a source name.
     - A digital node may carry a `~` with no blank after it.
     - A port type may stand before a vector (`%v[…]`, `%v […]`), and applies to each connection inside it that has no type of its own.
   - **`ports`** is a tuple of `CodeModelPort`. Each holds:
     - `vector` (true for `[ … ]`) and its span;
     - its connections. Each connection has its `port_type` as written (or `None`), its nodes, `inverted`, `null`, and `source` (an `ElementReference` for `%vnam`).
   - **`nodes`** is every node in order, without `null` and without `%vnam` sources. So `nets()`, `connections()` and `elements_on_net()` work unchanged.
   - **A `%vnam` source is a controlling reference,** like F's and H's (decision 0015 item 3):
     - it is resolved, with `UNRESOLVED_ELEMENT` when the source is missing (ngspice stops: "unknown controlling source");
     - it is in the signature as a `control` entry;
     - it is not a net.
   - **The signature entry of an A line records the port structure:**
     - each port's position, and whether it is a vector;
     - each connection's port type as written, its nodes, and `null`.

     Without this, `[a null] b` and `[null a] b`, or `[a b] c` and `[a] b c`, would have the same signature. Yet each connects a node to a different pin, and `%v` against `%i` connects it differently. `~` is not in the signature: it inverts a logic value, not a connection.
   - **Not checked:** the number of ports, their types against the model, and where `null` is allowed. The library cannot see a code model's interface, which can be user-defined (chapter 24). ngspice stops on each mismatch probed (too many ports, a vector where a scalar is expected, `null` where it is not allowed, `~` on an analog port), so none of these misreads a line.
   - **Refused,** each with a discrepancies row where ngspice runs it:
     - a comma inside a vector (ngspice runs `[in, in]`; the manual shows blanks);
     - `~` followed by a blank (ngspice runs `~ d`);
     - a name=value on the instance line (ngspice stops);
     - a number as the model (ngspice stops).
   - *Considered:* `nodes` only, a flat list (it loses the pin structure in the signature); a `ports` field without a signature entry.
5. **`.model` values for code models.** **Decided:**
   - **Where they are allowed.** A `.model` whose type is not a built-in SPICE type of `model-types.json` may give a parameter:
     - **a vector:** `[`, values separated by blanks, `]`. It may continue over a `+` line. It is held as a `ValueList` whose span includes the brackets, as M16's CPL list is held without them;
     - **`TRUE` or `FALSE`** (any case): an `Identifier`;
     - **a quoted string** (`file="in.txt"`): a string value that holds the text as written and is never scanned as a formula.

     Every probe of these runs in ngspice (`in_gain=[2.0 1.0]`, over a `+` line, braced, `fraction=FALSE`, `false`). A built-in type keeps today's rules, so a vector or string on `.model d …` is still a `ParseError`.
   - **Refused,** each with a row:
     - a comma between vector values (ngspice runs `[2.0, 1.0]`);
     - a vector on a built-in type.
   - **Parameter names are not checked** (ngspice ignores `foo=1` on `gain`). This matches section 1, and the spec note says so.
   - **Which value is which** is decided per parameter, with no knowledge of the code model: for example, a vector of one value against a scalar.
   - *Considered:* only the types that §8.2 to §8.5 list (user-defined code models would not load); quoted strings as formulas (the formula scan would read `in.txt` as an expression).
6. **ngspice N (§9.3.1.6).** **Decided:**
   - **Shape:** nodes, then the model, the last name before the first `name=value` or the end of the line (decision 0014 item 1), then named parameters in ngspice's value slot.
     - At least one node is needed. The count is not checked, because the module defines it: ngspice runs a two-terminal `r2_cmc` with one node, and stops on three.
     - A number as the model is refused.
   - **Refused (ngspice stops):** a positional value after the model, and a flag (`off`). `m=` is an ordinary parameter (ngspice runs it, and halves the resistance).
   - **Parameter names are not checked:** ngspice stops on an unknown one, and only the module knows its names.
   - **Model types:** N's model must be a `.model` whose type is not a built-in SPICE type. A built-in one is `MODEL_TYPE_MISMATCH` (ngspice stops on a D model). A and N share this rule, and `set_model` checks it.
   - **Validation:**
     - The Windows build of ngspice 47 ships compiled models in `lib/ngspice/` (`r2_cmc.osdi`, `psp103.osdi` and others).
     - A netlist loads one with `pre_osdi <path>` in a `.control` block, which the library keeps as an opaque block.
     - The solver tests find `r2_cmc.osdi` beside the ngspice in `.env`, and skip with a reason when it is missing (a Linux package may not ship it). So NG-OSD-001 can be `validated`, where the plan expected `documented`.
   - *Considered:* `documented` only.
7. **LTspice A and `@` parameters.** **Decided (maintainer, 2026-11-10, including `refnode=` and `intnode=` as references):**
   - **LTspice A:**
     - exactly eight nodes (LTspice stops on seven and on nine), then the function (decision 3), then named parameters;
     - the names are not a closed list, because the reference lists only some of them, by symbol family. LTspice stops on an unknown name ("foo=5"), so an open list does not misread a line;
     - values are in LTspice's value slot. A bare name (`Vhigh=x`), which LTspice runs, is refused with M16's R2 message suggesting `{x}`;
     - a positional value and a flag are refused (LTspice stops);
     - a comma between parameters is accepted, as on T (LTspice runs it).
   - **`@`:**
     - two nodes, then fields in any order: the `zm` flag (any case; a second `zm` is refused), and named parameters from the reference's table. That table is complete, so the list is closed: `delay`, `fstart`, `fend`, `oct`, `fcoarse`, `flist`, `nmax`, `pp0`, `pp1`, `f0`, `f1`, `pp`, `tavgmin`, `tsettle`, `rpar`, `acmag`, `acphase`, `ac`, `enabled`, `refnode` and `intnode`. LTspice stops on any other name, on one node and on three;
     - `flist=` (values), `pp=` (frequency and amplitude pairs), `nmax=` (a value or pairs) and `ac=` (magnitude and phase, comma-separated) are `ValueList`s. Each form was probed;
     - none is required: LTspice runs `@1 in out` in `.op`.
   - **`refnode=` and `intnode=` name nets** (decision 2's `reference_net` and `intermediate_net`). They are node references, as `.ic V(n)` is:
     - resolved, with `UNRESOLVED_NODE` (LTspice stops on a missing net);
     - not terminals and not in the signature, because the analyzer measures them and connects nothing to them (plan section 8, point 1);
     - editable with `set_param`.
   - *Considered:* `refnode=` and `intnode=` as connections in the signature.
8. **`&` and its analyzer.** LTspice pairs `&N` with `@N` by the name after the letter, in any case (`&a` with `@A`).
   - With exactly one `@` in the circuit, an unmatched `&` runs.
   - With none, or with two and no match, LTspice stops ("No FRA device associated with this probe").
   - An `&` in a subcircuit with its `@` at the top level stops too.

   **Decided (maintainer, 2026-11-10):** `FraProbe.analyzer` is an `ElementReference` to `@` plus the probe's suffix, resolved in its scope. An unresolved one is `UNRESOLVED_ELEMENT`, except when its scope has exactly one `@`, which LTspice then uses. It is not topology: the probe connects nothing, and its four nodes are its connections. Four nodes and nothing after them; LTspice stops on three, five, or a parameter. *Considered:* no reference.
9. **Edits.** **Decided:**
   - **`set_model`** on ngspice A and N, with decision 6's type check.
   - **`set_param` and `remove_param`:**
     - on N, LTspice A and `@`;
     - `refnode=` and `intnode=` take a node name;
     - an `@` list as a whole list.
   - **`set_model_param` and `remove_model_param`** on code-model and OSDI models:
     - a vector is replaced as a whole (`"[2 1]"`);
     - a boolean takes `TRUE` or `FALSE`;
     - a string takes a quoted value;
     - a comment inside a vector over `+` lines follows M16's R3 rule.
   - **`EditError`s naming the right operation:**
     - `set_param` on ngspice A (its parameters are on the `.model`) and on `&`;
     - `set_value` on any new line;
     - the LTspice A function and the `zm` flag ("not editable"; hand-edit the line).
   - **Nodes, ports and the `%vnam` source** are not editable (§7.3).
   - *Considered:* `set_function` on LTspice A. A function changes what the device is, and its parameters with it.
10. **The planned-letter tests.** **Decided:** move them to a mocked matrix, as `test_structure.py` already does for `"error"`:
    - `test_parse_messages.py`'s two planned-letter tests and `test_structure.py::test_continued_element_line_is_reported_at_its_first_line` patch the device matrix so that a letter is `planned`, and keep checking the message and position;
    - the `phase_2_letter.cir` rejects of both dialects go, with their manifest entries. The LTspice entry in `test_ltspice_discrepancies.py` changes to an accept test of the `A` line, which now loads;
    - an architecture test checks that no matrix entry is `planned`, which is M17's exit and M18's audit item.

    *Considered:* dropping the tests (the planned-letter path stays in the loader until M18, so it keeps a test).
11. **LTspice `.machine`.** **Decided:**
    - It stays `UnsupportedConstruct` (LT-MCH-001) and becomes a **named v1 exclusion** in decision 0020, the LTspice device matrix's note, `docs/usage/errors.md` and the README's limits;
    - its message says it is out of scope for v1, rather than not yet supported. The digital U's message does the same (decision 1).
12. **Corpus.** **Decided:**
    - Variants written here, each changing one form, under new families: `ngspice/code_models`, `ngspice/osdi_devices` and `ltspice/special_functions`.
    - **Base files** (2026-11-10, section 3.2):
      - the LTspice schematics are the maintainer's, following the checklist;
      - the ngspice netlists are written here, and the maintainer confirmed their provenance (2026-11-10).

      Both are credited as in M16 (xdylanm, MIT), kept byte for byte, and the manifests record their hashes.
    - The ngspice distribution's examples are not copied (plan risk "mixed licences").
13. **One decision record, 0020, and where the code goes.** **Decided:**
    - **0020 records this section.** It amends:
      - §5.3: the new nodes, `CodeModelPort` and the code-model `.model` values;
      - §6.3 rule 14: N uses the boundary rule;
      - §7.2: the model-type rule for A and N;
      - decision 0015 item 3: `%vnam` is a controlling reference.

      It also records decision 3 as an exception to decision 0002, and the two v1 exclusions: `.machine` and the digital U, which amends plan section 8, point 2.
    - **The rules** go in a new `model/_rules_special.py` (P12). The edits need no new module.
    - **The A port terminals:** if any needs lookaround, it is added to the reviewed list (limit 3), and the architecture test is updated in the same change.

## 3. Starting point (2026-11-10, `13ebefb`, `main`)

M16's pull request (#15) was merged as `3a72861` on 2026-11-10; `main` adds a Dependabot `uv.lock` update. The probes of section 3.1 ran on 2026-11-09 and 2026-11-10 against M16's final code (`b048501`, the same tree as `3a72861`). M17 works on the branch `m17-special-devices`.

### 3.1 Probes

The probes ran on ngspice 47 and LTspice 26.1.1, from scratch scripts outside the repository. Each ngspice circuit has `V1 in 0 1`, `Rin in 0 1k` and a 1 kΩ load `Rl out 0 1k`; a `gain` with `gain=5` gives `v(out)` = 5. Digital probes run `.tran 1n 200n` through an `adc_bridge` and a `dac_bridge` (out 0 or 1). The library's reading today is `UnsupportedConstruct` for every A, N, `@` and `&` line, because the letters are planned.

**ngspice 47 — A:**

| Line | Result |
|---|---|
| `a1 in out amp`; `%v(in) %v(out)`; `%v in %v out`; `%v (in)`; `%V`; `%vd(in 0)`; `%vd in 0` | Run, 5 |
| `.model amp gain gain=5` (no parentheses); `gain={g}`; `gain=5 foo=1` | Run, 5: ngspice ignores `foo` |
| `a1 in out amp gain=2`; no model; an undefined model; an unknown type; `a1 in out out amp`; `a1 [in] out amp`; model named `5` | Stop |
| summer `[in in]`; `[ in in ]`; `%v[in in]`; `%v [in in]`; `[in %vd(in 0)]`; `[in %vd in 0]`; `[in, in]` | Run, 2 |
| summer `in_gain=[2.0 1.0]`; `[2.0, 1.0]`; without parentheses; over a `+` line; `[{g} 1.0]` | Run, 3 |
| summer `in_gain=2.0` (scalar for a vector); `[in]`; `in` without brackets; `[in null]`; gain `null out` | Stop |
| `%vnam V1 out`; `%vnam(V1) out` | Run, −0.005 (the current through V1, times 5) |
| `%vnam Vnone out` | Stops ("unknown controlling source") |
| `in %i(out)` | Runs, −5000 |
| limit `fraction=FALSE`; `false`; `0` | Run, 3 |
| A in a subcircuit | Runs, 5 |
| digital: `d_inverter`; `d_buffer`; `~d`; `~` on the output; `~ d`; `[~d d]` into `d_nand`; `%d d %d dn`; `d_dff` with `null` set and reset | Run, with the expected logic (0 or 1) |
| `~in` on an analog `gain` | Stops |
| `filesource(file="nofile.txt")` | Stops on the missing file; the line itself is read |

**ngspice 47 — N** (`.control` with `pre_osdi` and the shipped `r2_cmc.osdi`, `.model rmod r2_cmc(rsh=200)`):

| Line | Result |
|---|---|
| `N1 out in rmod w=1u l=20u`; braced `l={20u}`; in a subcircuit | Run, 0.3333 (a 2 kΩ resistor) |
| `l=40u` | Runs, 0.2: the parameter moves the result |
| no parameters | Runs, 0.9091 |
| `m=2` | Runs, 0.5 |
| one node (`N1 out rmod …`) | Runs, 0: ngspice leaves the second terminal unconnected |
| without `pre_osdi` | Stops |
| three nodes; `foo=1`; positional `5`; `off`; a D model | Stop |

**ngspice 47 — digital U (the record behind decision 1):**

| Line | Result |
|---|---|
| any digital U without PS mode; at the top level with `ngbehavior=psa` | Stop |
| in a subcircuit with `ngbehavior=psa`, the models in the subcircuit: `inv`, `buf`, `and(2)`, `AND(2)` | Run, through automatic bridges |
| the same with the models outside the subcircuit | Stops: the translator looks for them inside |
| `and (2)` (a blank before the parenthesis) | Stops ("U* device syntax error") |
| `and(2)` with one input too few or too many | Stop: ngspice counts the nodes |
| `$D_HI` as an input; `$G_DPWR $G_DGND` as the power nodes | Run |
| without the I/O model (`U1 inv vp vg a y d0`) | Runs |
| `MNTYMXDLY=2 IO_LEVEL=0`; `foo=1` | Run: ngspice ignores `foo` |
| an unknown basic type (`frob`) | Stops |
| a URC line in a subcircuit with `psa`, including one whose first node is `inv` | Runs as URC |
| `Rx in out 1k $ comment` with `psa` | Stops: `$` is not a comment in PS mode |

**LTspice 26.1.1 — A** (`A1 in 0 0 0 0 out 0 0 <function>`):

| Line | Result |
|---|---|
| `BUF`, `buf`, `AND`, `OR`, `XOR`, `SCHMITT`, `DFLOP`, `SRFLOP`, `VARISTOR`, `OTA`, `PHASEDET` | Run |
| `COUNTER cycles=4`; `MODULATOR mark=2k space=1k` | Run (each stops without its parameter: "Missing value of cycles", "Missing mark frequency") |
| `SAMPLEHOLD` with only an input on terminal 1 | Stops ("Either the S/H or CLK input must be connected"): T1 writes a valid one |
| `INV`, `SCHMTBUF`, `SCHMTINV`, `MODULATE`, `PHIDET`, `FOO` | Stop ("Expected valid special function name") |
| `Vhigh=5`; `Vhigh={5}`; bare `Vhigh=x`; the gate parameters together; `Vhigh=5, Vlow=0`; common at 0.5 V | Run (out 4.995 with `Vhigh=5`) |
| `foo=5`; `off`; positional `5`; seven nodes; nine nodes | Stop |
| a `.model mybuf BUF(…)` or `DIGITAL(…)` used as the function | Stops ("Expected model definition") |
| in a subcircuit | Runs |

**LTspice 26.1.1 — `@` and `&`:**

| Line | Result |
|---|---|
| `@1 in out fstart=1k fend=10k` in `.op` (a short in DC); in `.fra`; in `.ac` with `acmag=1`; in a subcircuit | Run |
| `zm`, `ZM`, after the parameters, twice | Run |
| no parameters; no `fstart` | Run |
| one node; three nodes; `foo=1`; `refnode=` a missing net | Stop |
| `refnode=r`; `intnode=out`; `flist=1k 2k 5k`; `flist=1k,2k,5k`; `pp=1k 10m 10k 1m`; `nmax=1k 2 10k 1`; `ac=1,0`; `ac=1 0`; `enabled=0`; braced; bare `fstart=f1`; `pp0 pp1 f0 f1`; the timing parameters; over a `+` line | Run |
| two `@1` lines | Stops ("Instance with that name already defined") |
| `&1 out 0 in 0` with `@1`; `&a` with `@A`; `&2` with only `@1` | Run |
| `&1` without any `@`; `&2` with `@1` and `@3`; `&1` in a subcircuit with `@1` at the top level | Stop ("No FRA device associated with this probe") |
| `&` with three or five nodes, or a parameter | Stop |
| `.machine` … `.endmachine` | The library: `UnsupportedConstruct` (unchanged) |

**Found with the maintainer's schematics (2026-11-10):** a `.fra` run writes `<name>.fra_<instance>.raw`, which `tests/support/raw.py` reads as a "Frequency Response Analysis" plot with `frequency`, `gain_<n>`, `V(stimulus_<n>)` and `probe_<n>`. So an edited `fend=` can be shown to move its frequency points. During `.fra`, an independent source's `AC` value does not apply, so a probe whose input pair sits on such a source's node reads ±inf.

**For T1:**
- a valid `SAMPLEHOLD`;
- ngspice A with a model of a built-in type (`.model dm d`);
- a differential `%vd` with a blank before its parenthesis;
- `%vnam` inside a vector;
- the probes above as tests, each with the library's reading.

### 3.2 Corpus

- **Today:** no accept file has an A, N, `@` or `&` line. `elements_rejects/phase_2_letter.cir` holds an A line in both dialects (decision 10).
- **The maintainer's base files** (decision 12): see the checklist below.
- **Variants (T2),** each one change from a base file:
  - **ngspice accept:**
    - code models: `gain` with and without port types; a `summer` with a vector port and a vector parameter; `%vd`; `%vnam`; a digital chain with bridges, `~` and `null`; `limit` with `fraction=FALSE`; a `filesource` with a quoted path (a stub file);
    - OSDI: `r2_cmc` with `pre_osdi` (a relative path, written for the solver sweep), and with `m=`.
  - **ngspice rejects:** `a_param_on_instance`, `a_vector_comma`, `a_tilde_blank`, `a_model_number`, `model_vector_on_builtin`, `model_vector_comma`, `n_positional`, `n_flag`, `n_model_number`.
  - **LTspice accept:** each of the 13 functions with the parameters it needs; `@` with each list form and `zm`; `&` paired by name.
  - **LTspice rejects:** `a_inv_name` (LTspice stops, so it is not in `LTSPICE_RUNS`), `a_bare_param` (runs), `a_seven_nodes`, `fra_unknown_param`, `fra_zm_twice` (runs), `probe_param`.

#### Checklist for the maintainer's files

**For every file:**
- [ ] Draw it yourself, using only the tool's own built-in parts. Use no third-party model, `.lib` or `.include`, so that provenance stays xdylanm, MIT.
- [ ] Give it an analysis directive, and check that it simulates in the tool before you save it. If one is meant to fail, say so.
- [ ] Name it `test_<tool>_<topic>`, as in M16 (`test_ltspice_gates.asc`, `test_kicad_xspice_digital.cir`).
- [ ] Put it in the folder named below. Leave the manifest, the path-comment normalisation and the hashes to T2. Don't edit an export by hand.
- [ ] Note the tool's version (LTspice 26.1.1 was used for M16; the KiCad version for the KiCad files).

**LTspice** (`tests/corpus/ltspice/special_functions/`, each `.asc` with its `.net` export):
- [ ] **Before exporting:** close LTspice with **Default Devices** and **Default Libraries** off (`docs/usage/ltspice-export.md`). Export with `-netlist`, or in the GUI (View → SPICE Netlist, then save). Either way the first comment keeps the absolute path, and T2 replaces it.
- [ ] **`test_ltspice_gates.asc`** (`.tran`, a `PULSE` source as input or clock):
  - the `buf`, `inv` and `buf1` symbols;
  - `and`, `or` and `xor` with two or three inputs used;
  - `dflop` clocked by the pulse;
  - `srflop`;
  - at least one gate with `Vhigh=`, `Trise=` and `Td=` set in its line.

  This covers `BUF`, written three ways, and `AND`, `OR`, `XOR`, `DFLOP` and `SRFLOP`.
- [ ] **`test_ltspice_schmitt.asc`:** `schmitt`, `schmtbuf`, `schmtinv` and one `diff…` variant, with `Vt=` and `Vh=` set on one of them. All four write `SCHMITT`.
- [ ] **`test_ltspice_ota.asc`:** `ota`, `mota` (with its multiplier input driven) and `mota8` (with its supply pins), with `G=`, `Iout=` and `Rout=` set on one. All three write `OTA`, with different terminals used.
- [ ] **`test_ltspice_functions.asc`:**
  - `counter` with `cycles=`;
  - `phidet` with two pulse inputs;
  - `modulate` and `modulate2` with `mark=` and `space=`;
  - `sample`, with CLK or S/H connected;
  - `varistor`.

  This covers `COUNTER`, `PHASEDET`, `MODULATOR`, `SAMPLEHOLD` and `VARISTOR`. If you know `VARISTOR`'s parameter names, set one: the probe's guesses (`Rclamp`, `Vrating`) stopped LTspice.
- [ ] **`test_ltspice_fra.asc`:** a small closed loop (for example an op-amp or a behavioural source with feedback), with:
  - the `fra` symbol (`@`) inserted in the loop;
  - one `fraprobe` (`&`) with the same instance number;
  - a `.fra` directive;
  - on the analyzer, `fstart`, `fend`, `oct`, `delay` and either `pp0`/`pp1`/`f0`/`f1` or `pp=`, as the reference's procedure suggests.

  Keep the run short (a narrow sweep, `oct=1`), so that the solver sweep stays fast.
- [ ] **`test_ltspice_fra_zm.asc`** (optional): an impedance measurement (`zm`), and `refnode=` or `intnode=` on an analyzer.

**The LTspice set (received 2026-11-10):** `test_ltspice_gates`, `_schmitt`, `_ota`, `_functions` and `_fra` (the optional `_fra_zm` was left out). Each exports and runs in LTspice 26.1.1.
- The FRA schematic was revised after review: a 1 kHz to 100 kHz sweep with `oct=1`, which runs in 2.9 s; the analyzer facing the op-amp output; the probe's input pair on the inverting input.
- Its `gain_1` is 1.75e3 at 92.7° at 1 kHz, and its `probe_1` is 3.49e3 at 90.9°.
- LTspice leaves its Bode plot blank, because neither analyzer terminal is grounded and the circuit has a probe (the reference's "Results and Bode Plot"). The results are in the `.fra_1.raw` file.

**ngspice: written here; provenance confirmed by the maintainer (2026-11-10).** KiCad's standard library has no parts with XSPICE models, so a KiCad export would be a hand-written netlist anyway (maintainer). Instead, these base netlists are written here. Each was run in ngspice 47, and the variants of section 3.2 are derived from them once the maintainer confirms the set:

| File | What it covers | ngspice 47 result |
|---|---|---|
| `code_models/test_xspice_gain.cir` | `gain` with no port types, `%v(…)` and `%vd(… …)` | `.op`: 5, 5, 2.5 |
| `code_models/test_xspice_summer.cir` | `summer` with a vector port, a vector port with a type and a `%vd` connection inside it, vector parameters with a brace, over a `+` line | `.op`: 4, 2 |
| `code_models/test_xspice_control.cir` | `%vnam`, a `%i(…)` output, `limit` with `fraction=FALSE` | `.op`: 1, −1, 3 |
| `code_models/test_xspice_digital.cir` | `adc_bridge` and `dac_bridge` with vector ports, `d_inverter`, `d_nand` with `~`, `d_dff` with `null` set and reset | `.tran`: the outputs follow the input pulse |
| `osdi_devices/test_osdi_r2_cmc.cir` | N with `r2_cmc`, one with `m=2`; `pre_osdi r2_cmc.osdi` in a `.control` block | `.op`: 0.2 |

- The OSDI file names `r2_cmc.osdi` without a path. ngspice finds it when `NGSPICE_OSDI_DIR` names ngspice's `lib/ngspice` folder, or when a copy sits beside the netlist (both probed). T2 sets the variable in the ngspice sweep's environment, from the solver's install folder, and skips with a reason when the file is missing.
- A quoted-string parameter (`filesource`'s `file="…"`) needs a data file beside the netlist. It is a variant in T2, with a small data file written here.

**Next (T2):** add the manifests, recording each file's SHA-256 and the provenance (xdylanm, MIT, confirmed by the maintainer on 2026-11-10), then derive the variants.

### 3.3 In the repository

- **Grammar and loader:**
  - A and N (ngspice), and A, `@` and `&` (LTspice), are `planned`, and the loader turns their lines into `UnsupportedConstruct` (`grammar/loader.py`).
  - The ngspice U rule already recognises every non-URC shape (`rc_line` with `u_word+`) and raises "ngspice digital U device".
- **`.model` today:** `param | model_flag | model_text`, plus M16's CPL lists and LTRA flags. A `[`, `TRUE`/`FALSE` or a quoted value in a `.model` is a `ParseError` (`gain` loads; `summer(in_offset=[…])`, `limit(fraction=FALSE)` and `filesource(file="…")` do not).
- **Reusable pieces:**
  - the boundary rule (`t_name`, `t_number`), for N;
  - `ElementReference` and the `control` signature entry, for `%vnam` and `&`;
  - node references with `UNRESOLVED_NODE`, for `refnode=` and `intnode=`;
  - `ValueList`, for vectors and `@` lists;
  - `Identifier`, for booleans and the LTspice function.
- **The signature:** new letters add entries only for new lines, so no saved digest changes.
- **`.control` blocks** are opaque and load, so a netlist with `pre_osdi` loads today apart from its N line.

## 4. Tasks

[ ] **T1 — Probes and decision record 0020.**
- Run the open probes of section 3.1, and add them to the tables.
- Write the probe tests first, in `tests/solver/test_ngspice_special_probes.py` and `test_ltspice_special_probes.py`, with M16's shape: the line, whether the solver runs it, and the library's reading. They fail until the forms are in.
- Add a test helper that finds the shipped `r2_cmc.osdi` beside the ngspice in `.env`, and skips with a reason when it is missing.
- Write 0020 from section 2, with status `proposed` until M17 closes, and add it to the decisions index.

[ ] **T2 — Corpus first.**
- The three new families of section 3.2, with manifests (author, licence and origin as decision 12), in both solver sweeps' `FAMILIES`, each accept file `pending: M17`.
- The maintainer's files (section 3.2 checklist) are kept byte for byte, and their hashes go in the manifests.
  - The maintainer commits only the `.asc` schematics (2026-11-10).
  - T2 exports each one with `-netlist`, replaces the path comment with the file name, and commits the `.net` beside it, because the round-trip and solver tests read committed files.
  - The LTspice re-export test keeps each `.net` in step with its `.asc`.
  - `jellybean.lib` is not copied into the family: as in `ltspice_transistors`, the manifest maps it to `OPENJELLYBEAN_LIB`.
- Cover any LTspice schematics with the re-export test.

[ ] **T3 — Nodes, model types and the planned-letter tests (decisions 2, 6 and 10).**
- The five classes and `CodeModelPort` in `model/nodes.py`, exported from the package, with docstrings and properties.
- The "not a built-in type" rule for A and N in `model-types.json` and `MODEL_TYPE_MISMATCH`.
- The planned-letter tests move to a mocked matrix; the `phase_2_letter.cir` rejects go.

[ ] **T4 — ngspice A (decision 4).**
- The port grammar in its own rules in `model/_rules_special.py`, with the refusals of decision 4.
- `ports`, `nodes`, the `%vnam` reference and the signature entry.
- **Topology tests:** every node is in `nodes`, `nets()` and the signature. Moving a node between ports, swapping a node and `null`, and changing a port type or the `%vnam` source are each a `TopologyViolation`.
- **Spec entry:** `NG-COD-001`.

[ ] **T5 — Code-model `.model` values (decision 5).**
- Vectors, booleans and strings on types that are not built-in, refused on built-in types.
- Extend NG-MOD-001 and the `.model` section of `statements.md`.

[ ] **T6 — ngspice N (decision 6).**
- Shape, refusals and the model-type rule.
- **Spec entry:** `NG-OSD-001`, `validated` with the shipped `r2_cmc.osdi`.

[ ] **T7 — LTspice A, `@` and `&` (decisions 3, 7 and 8).**
- The function list, the eight nodes and the parameters.
- `@`'s fields and lists, and `refnode=`/`intnode=` as node references.
- `&` and its analyzer reference, with decision 8's exception.
- **Spec entries:** `LT-SPF-001`, `LT-FRA-001` and `LT-FRP-001`. `LT-UNS-001` and `LT-MCH-001` change (decision 11).

[ ] **T8 — Edits (decision 9).**
- The operations of decision 9 and their `EditError`s.
- **Golden diffs:** for each, on its dialect, including a vector, a boolean, a string and an `@` list.
- **Property tests:** no edit here changes the signature.
- **Solver tests that each edit moves the result:**
  - a code-model parameter, and a vector (`.op`);
  - an OSDI `l=` (`.op`);
  - an LTspice A `Vhigh=` (`.op`);
  - an `@` `fend=` (`.fra`, as T1 found).

[ ] **T9 — Corpus and snapshots.**
- The `pending` marks go, and every M17 accept file loads, round-trips and runs in its sweep.
- The tree snapshot gains the new files and loses `phase_2_letter.cir`, and its docstring says so.
- No signature snapshot entry changes.

[ ] **T10 — Documentation.**
- **Both device matrices and their JSON files:** A, N, `@` and `&` become `supported`. ngspice U's milestone becomes `M16`, with a note naming the digital U as a v1 exclusion (decision 1).
- **Design and usage docs:**
  - `docs/design/elements.md` and `statements.md`;
  - `docs/usage/elements.md`, `editing.md` (a code-model vector and an `@` example) and `errors.md`, with the `.machine` exclusion.
- **Both `discrepancies.md`,** with a row for each refusal a solver runs, and decision 3's names.
- **The plan:** checked against decision 1. Its v1 scope, M17 entry, section 5 and section 8, point 2 are already updated with this list.
- **Also:** README, CHANGELOG ("Unreleased") and the architecture amendments.

[ ] **T11 — Final evidence and handover.**
- Open the pull request.
- Run the full local check set with `--require-solver ngspice --require-solver ltspice`, and record it and the CI run in section 5.
- List the design points worth reviewing, and set the status to `READY FOR REVIEW`.

### After the maintainer's approval

[ ] **T12 — Close M17.** Archive this list, accept decision 0020, and update the plan and index.

## 5. Results

To be written in T11.
