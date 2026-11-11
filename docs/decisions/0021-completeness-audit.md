# 0021 — Completeness audit

- **Status:** proposed (M18; accepted when M18 closes)
- **Date:** 2026-11-11
- **Amends:** architecture §6.3 rules 13 and 14, §6.6, §6.7, §10.4 and §17; decision 0017 item 4's edits.
- **Context:** M18 audited the library against the phase 2 plan and the architecture before the v1 review package: value specifications (§6.4), the rejection paths and lookaround terminals, the corpus, the oracles and edit properties, and spec coverage. The findings and the maintainer's decisions are in sections 2 and 5.1 of [m18-tasks.md](../design/m18-tasks.md). Most findings were tests, records and wording. Two were defects: a number after a transistor's model could be read as the model, and a line after a nested `.if` block was refused. Four forms that LTspice stops on loaded. This record carries the normative changes. The probes are in `tests/solver/test_ngspice_value_probes.py`, `tests/solver/test_ltspice_value_probes.py` and the M18 LTspice probe tests, on ngspice 47 and LTspice 26.1.1.
- **Decision:**
  1. **A number is never the model** (amends §6.3 rule 14).
     - **The rule:** a field written as a number (a mantissa, an optional exponent, then letters) is never the model of a transistor, U, T, O, A or N line, whatever its letters are.
     - **LTspice:** the positional number takes any Unicode letter, as LTspice's `NUMBER` does. So after the model it is the area of Q, J or Z (`Q1 c b 0 qm 1μ`, area 1e-6 as LTspice reads it), and it is a POLY coefficient. Where only a name may follow the model (M), it is refused at its token, as a number in the model's place.
     - **ngspice:** the positional number takes ASCII letters and `µ` (U+00B5) only. A number with another letter (`1μ`, `2Ω`) is refused at its token: after a Q's model with the positional-area message (ngspice 47 runs it as an area and ignores the letter), and elsewhere as a number in the model's place.
     - **Before M18,** such lines loaded with the model taken as a node (`c b 0 qm`, model `1μ`), with no error.
  2. **Nested conditional blocks** (amends §6.6).
     - **The rule:** a `.if` block nested in another has its own rule, with the body of the top-level block and the same node class. So the parser states after an inner `.endif` do not merge with those where a statement may start, and any line may follow it (ngspice 47 runs these netlists).
     - **The check:** an architecture test checks that no contextual-lexer state offers a block line's terminal (`BLOCK_TEXT`, `BLOCK_DOT_NAME`) beside a statement's first terminal.
  3. **A lone CR before a CRLF is text** (amends §6.3 rule 13). A lone `\r` is ordinary text only inside free-text terminals, written `\r(?!\n)`: a CR not followed by LF. So a CR right before a CRLF is text, as decision 0001 reads that line. `\r?\n` is the only terminator. Anywhere else a lone `\r` is a syntax error. *Considered:* keeping `\r(?!\r?\n)` as a documented limit.
  4. **LTspice `.subckt` parameter commas** (`.subckt s p n r=1k, q=2`, also after `params:`) load, as they did through the X parameter rule: an observed form beside X's (`LT-SBD-001`). A comma right after `params:` (`params:, r=1k`) stops LTspice and is refused (item 5).
  5. **LTspice forms that load and that LTspice stops on.** A line shape the grammar can see is refused; a condition that spans lines gets a warning diagnostic. Neither misreads a line.
     - **Refused:**
       - a `+` line that holds only a comment as the last line of a statement, unless a later `+` line holds a field (blank `+` lines after it do not count). LTspice 26.1.1 stops on it on every statement probed, except at the end of a `.subckt` header with ports only, which it runs (a `discrepancies.md` row). The loader refuses it after the parse, from the source's physical lines, so no terminal gains a lookaround;
       - a special function's name (the 13 of decision 0020 item 3) or `DIGITAL` as a `.model` type: LTspice stops on the `.model` line itself, used or not;
       - a comma right after `params:` on X and `.subckt` (LTspice stops on both).
     - **Warnings** (§17 adds both codes):
       - `FRA_PROBE_IN_IMPEDANCE_MODE`, on an `&` whose resolved analyzer (decision 0020 item 8) has `zm`: LTspice stops under any analysis. It spans two lines, so it is not a grammar check;
       - `FRA_RANGE_MISSING`, on an `@` without `fstart=` and `fend=` when the top level has a `.fra` command; `flist=` does not replace them, and an `@` with `enabled=` is not checked, since the library does not read values.
     - **Edits:** a removal on LTspice that would leave such a `+` line moves its comment to the end of the last line that keeps a field (`V1 a 0 ; c ; d`).
     - **Left as rows:** an unknown LTspice `.model` type (`.model x FOO(a=1)`) loads and LTspice stops on it; a comma before `params:` runs in LTspice and is refused.

     *Considered:* `discrepancies.md` rows only.
  6. **A new parameter on an LTspice B line with `laplace=` goes before it** (amends decision 0017 item 4's edits). `set_param` adds it after the last field before `laplace=`, since the library reads only `window=`, `nfft=` and `mtol=` after `laplace=`; those three are still added after it. Before M18, the parameter was written after `laplace=`, the result did not parse, and the edit failed verification with nothing written. LTspice 26.1.1 runs both orders. E and G take only the three after `Laplace=`, so they are unchanged.
  7. **The lookaround terminals are reviewed** (closes phase 1 limit 3).
     - **The review:** the 21 terminals that Lark's strict mode cannot collision-check (10 ngspice, 11 LTspice) were reviewed by hand. For each, the review records the parser states where it is a candidate, the terminals it competes with there, and why they cannot match the same text. The tables are in each dialect's grammar README.
     - **The outcome:** the review found the nested `.if` defect of item 2 and no other. None of the terminals can lose its lookaround without changing behaviour.
     - **Kept:** `UNCHECKED_TERMINALS` stays as the guard against silent growth.
  8. **Spec coverage** (amends §10.4 and §11.2).
     - **Test references:** a test reference must name a `def` in its file.
     - **Accept tests:** every entry except a `disputed` one and the refusal entries (`NG-UNS-001`, `LT-UNS-001`, `LT-MCH-001`) cites an accept test outside `tests/solver/`, that is, one whose name does not say it refuses a form. A refusal entry is `validated` by probes of the forms it refuses.
     - **The coverage report:** each grammar README's "Validation status" table, generated by `tests/support/spec_coverage.py` and checked, gives every entry's status, test counts (non-solver and solver) and validation dates, with a totals line.
     - **Conventions:** an LTspice entry may hold observed parts in its notes (decision 0009), where ngspice splits them into an entry of their own. The checker does not prove that a solver test runs; solver tests skip in CI (decision 0011).
  9. **Options are not read.** The library does not interpret `.options`, so LTspice's `reject_number_tails`, which makes LTspice stop on `10V`, is a `discrepancies.md` row and a `numbers.md` note, not a diagnostic.
  10. **Own messages, no change in what loads.** These refusals each get their own message instead of the list of expected tokens:
      - ngspice: a POLY pair in parentheses; G's four-node TABLE and gate; `and (2)`; `m=` on Y and P; T's `IC=` with blanks; an odd count in a `%vd` vector;
      - LTspice: `window=` before `Laplace=`.

      The loader names the ngspice forms after the parser has stopped, as it names an unbalanced `(`, so no grammar rule or terminal is added.
  11. **The v1 exclusions are named** (amends §6.7 and §17). `UnsupportedConstruct` is raised in v1 only for the ngspice digital U and LTspice `.machine`, both out of scope for v1 (decision 0020 items 1 and 11). The `planned` status and its loader path stay for a later dialect.
- **Consequences:**
  - **Spec entries:**
    - `NG-XTR-001`, `LT-XTR-001`, `LT-PLY-001`, `NG-OPA-001`, `NG-TXT-001`, `LT-TXT-001`, `NG-NUM-001`, `LT-NUM-002` and `LT-SBD-001` change with items 1 to 4;
    - five entries whose `validated_on` predated rules added to them are revalidated;
    - `LT-FML-001` cites a solver test of `~`;
    - `LT-CNT-001`, `LT-SUB-001`, `LT-MOD-001`, `LT-FRA-001` and `LT-FRP-001` change with item 5;
    - `NG-COM-001` becomes `validated`: the manual documents both of its accepted forms (§2.4.3 and §2.1.1's leading blanks), and an ngspice 47 probe of an indented `*` line is cited.
  - **Records:** every form either solver runs that the library refuses has a `discrepancies.md` row, including the number forms of the M18 audit (`1d3`, `1meg5`, `1μ` on ngspice, `1_000`, `(1k)` and others) and the LTspice reference's conflict over `a`.
  - **Parses that change:** lines that were misread or wrongly refused (items 1 to 3), and item 5's refusals, each a form LTspice stops on. No corpus file changes its parse, and the signature snapshot is unchanged. The tree snapshot gains the M18 corpus files and loses the expected-token lists of the item 10 rejects.
  - **Tests:** two new test files cover every phase 2 letter and edit operation on both dialects: an independent oracle (`tests/grammar/test_device_oracle.py`) and edit properties (`tests/edits/test_device_edit_properties.py`). In the properties, idempotence for a removal means that repeating it raises `EditError` and writes nothing.
