# 0024 — The 1.0 public API

- **Status:** accepted (2026-11-14, maintainer; M20 gate G1)
- **Date:** 2026-11-14
- **Amends:** decision 0004 item 5, decision 0006 item 2, decision 0007 items 10 and 11, decision 0021 item 1; architecture §4, §5.4, §6.3 rule 14, §18, §19 decision 21 and §21.
- **Context:** Decisions 0018 and 0023 left one question for after practical use of the beta: what 1.0 commits to in the public API (§18). The maintainer reported on 2026-11-14 that the `0.9.0` beta works as expected. M20 ([m20-tasks.md](../design/archive/v1.0/m20-tasks.md)) reviewed the public surface, the contract and the open behaviour items. The maintainer decided each point at gate G1 (m20 section 5.1). This record holds the outcome. Breaking changes are made directly before 1.0, with no deprecation shim (m20 decision 6).
- **Decision:**
  1. **What is public.** The public API is the names in `netlistmod.__all__`, with the documented attributes, methods and parameters of those objects. Submodules and subpackages are internal, even where a name in them has no underscore, and so are their `__all__` lists. Callers import from `netlistmod`.
  2. **What SemVer covers from 1.0.0.** This is a narrower contract.
     - **Covered:** public names, and the signatures of public functions, classes and methods (parameter names, which are keyword-only, defaults). Also covered are the exception classes, their hierarchy, and the class raised for a documented condition.
     - **Best-effort (not covered):**
       - dataclass fields and their types;
       - diagnostics (the `DiagnosticCode` members, severities, and when a code is reported);
       - the topology signature's entries and `digest()`;
       - the exact text an edit inserts;
       - type annotations;
       - message text, `repr` and `str`.

       A change to any of these is listed in the CHANGELOG, but needs no major version.
  3. **Grammar changes.** The grammar follows the reference editions in `docs/references.md` (P5).
     - **Minor:** accepting a new form, or reading one that raised `UnsupportedConstruct`. Refusing a form the reference does not allow is a correction; it is shipped in a minor release, never in a patch, and listed as "Refused".
     - **Major:**
       - refusing a form the reference allows;
       - changing the node type of a form that was read correctly;
       - removing an exception of §19 decision 21.
     - **Fixing a misread** is minor and listed.
  4. **Deprecation.** A public name or behaviour to be removed raises a `DeprecationWarning` for at least one minor release, with its replacement in the CHANGELOG. It is removed only in the next major. The project's own tests treat warnings as errors.
  5. **Python and solvers.**
     - **Python:** every CPython release from 3.13 that is in bugfix or security support. A new version is added in a minor release once CI passes on it. A version is dropped only after its end of life, in a minor release, with `requires-python` raised.
     - **Solvers:** a spec entry's `validated_on` records where a behaviour was checked (ngspice 47 and LTspice 26.1.1 at 1.0). It is evidence, not a support promise. A new solver version is re-validated by appending to `validated_on`. A difference becomes a `discrepancies.md` row, and changes the grammar only under item 3.
  6. **Changes to the public API in M20.** Each is listed in the CHANGELOG with its replacement.
     - **The boundary:**
       - `netlistmod.__all__` is sorted.
       - `ScopePath`, `Severity`, `ReferenceKind`, `BodyItem` and `TopLevelItem` are exported.
       - `netlistmod.version` (a stray import) and `netlistmod.document.Netlist` (the read-only base) are no longer reachable as public names.
       - The subpackage `__all__` lists hold only what `netlistmod` imports.
     - **`apply_edits` is internal** (amends decision 0007 item 10). `Edit` and `EditPlan` stay public, and a plan reaches a netlist only through `Netlist.apply`, which verifies.
     - **The read-only base** is `netlistmod.document.document.Netlist`, which is internal (amends decision 0007 item 11).
     - **Signatures:**
       - `Dialect` is a `StrEnum`.
       - `placement` and `scope` are keyword-only on every method that takes them. The exception is `Netlist.scope(path)`, whose argument is the scope being asked for.
       - `set_formula`'s second parameter is `text`.
       - `set_switch_state` takes `Literal["on", "off"] | None`.
       - `ControlledSource.form` and `BehavioralSource.quantity` are `Literal` types.
     - **`Lines.point_before`/`point_after`** replace `insert_before`/`insert_after`, which return a zero-width span and insert nothing (amends decision 0006 item 2).
     - **Defects fixed:**
       - `Scope`'s attributes are read-only.
       - `Placement` validates its kind and anchor (`ValueError`).
       - `in_definition=True` at the top level is an `EditError`.
       - A `Scope` passed as `scope=` raises a `TypeError` naming `Scope.path`.
       - On LTspice, `set_param` and `remove_param` on an E or G `Laplace` point to `set_expression`.
  7. **A number is never a model name, on every letter** (amends decision 0004 item 5 and decision 0021 item 1). A field written as a number (a mantissa, an optional exponent, then letters only, as decision 0021 item 1 has it) is never the model of any element line.
     - **What it adds:** decision 0021 item 1's letters gain D, S and W on both dialects, and the model after an ngspice R, C or L value.
     - **How it is refused:** where only a name may follow, the lexer reads such a field as a name, so the transformer refuses it at its token. There is no grammar change, as decision 0014 item 1 does for Q.
     - **Unaffected:** a name with letters before further digits (`1n4148`, `2N2222`, `1N4148_OJ`, `CD4093`, `4N25`) stays a model. A subcircuit name is not checked.
     - **Probes:**
       - ngspice 47 stops on a pure number as a D, S or W model. It reads a number after an R or C value as the value, which the library had misread as the model. It runs `4093B` and `1kohm` as model names, which the library refuses.
       - LTspice 26.1.1 runs a number as a D, S, W or Q model, and its reference allows any string without blanks. On LTspice this is therefore an exception to the reference (§19 decision 21).
     - **Not checked:**
       - a `.model` named with a number still loads, though no element can now use it;
       - model references outside element lines (`.step` model sweeps, `ako:` bases).

     Evidence: `tests/grammar/test_number_model_names.py` and `tests/solver/test_{ngspice,ltspice}_number_model_probes.py`.
  8. **`|` in ngspice names** is kept. The reference's excluded list does not hold it, and ngspice 47 runs it in a node and a model name (NG-NOD-001).
  9. **Kept as they are, and documented:**
     - `set_value`'s meanings;
     - `KeyError` on a read of a missing name beside `EditError` on an edit;
     - `Netlist.text` beside `source.text`;
     - no `.param` removal and no `.model` addition or removal;
     - a quoted LTspice string as a `Formula`;
     - scopes as tuples in `scope=`;
     - `in_definition=True`;
     - `ModelReference.model_name`, `Vcvs`, `Vccs`, `Cccs`, `Ccvs`, `BehavioralSource` and `Net.global_`;
     - LTspice B's `laplace=` parameter beside the E and G `Laplace=` form.

     **The rule for vocabularies:** an open, growing set (`DiagnosticCode`) is an enum; a small closed vocabulary is a `Literal` string.
  10. **Library files** stay a candidate after 1.0. They need their own entry point and result type, so a minor release can add them without changing 1.0 behaviour.
- **Consequences:**
  - §18 states items 1 to 5, and the README and the usage guides say to import from `netlistmod`. This closes the question left open by decisions 0018 and 0023.
  - **0.9.0 callers must update** for the removed names, the keyword-only arguments, `set_formula(text=…)`, `point_before`/`point_after`, and the refused number model names.
  - The contract takes effect at `1.0.0`. The next release is `0.10.0`, a second beta that ships these changes. `1.0.0` waits for a read-only audit of the planned xyce and qspice dialects (§9.2) against this contract, so that adding either does not need a 2.0 (maintainer, 2026-11-14; amends m20 decision 5).
