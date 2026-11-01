# LTspice scoping

The scope model of the document layer for LTspice (architecture §8;
[decision 0009](../../decisions/0009-ltspice-dialect.md)). Rules S1–S11 of
[the ngspice document](../ngspice/scoping.md) were re-probed by hand on LTspice 26.1.1
(2026-11-01). The model is the same, and the rows that differ say so. The implementation is
`src/netlistmod/document/index.py`; it branches on the dialect only where a row says so. T12
(checkpoint B) adds the solver tests and the `Validated on:` line.

## Rules

| ID | Rule | Manual | Status | Tests |
|---|---|---|---|---|
| S1 | A top-level `.param` is global. | — (observed) | documented | validation_note: T12 adds the solver test (probed by hand); `tests/document/test_ltspice_document.py::test_scopes_mask_and_resolve_as_in_the_rule_table` |
| S2 | A definition's defaults and body `.param` lines are local and mask a global name. | [ltspice-ref] SIMULATION-COMMANDS-REFERENCE.md ".SUBCKT / .ENDS — Subcircuit Definition" | documented | validation_note: T12 adds the solver test (probed by hand); same test |
| S3 | A `.model` or `.subckt` is local to the definition that contains it and visible in nested definitions. | — (observed) | documented | validation_note: T12 adds the solver test (probed by hand); `tests/document/test_ltspice_document.py::test_models_and_subcircuits_are_local_to_their_definition` |
| S4 | A reference is looked up in its own scope, then each enclosing scope, independent of file order. | [ltspice-ref] SPICE-SYNTAX-REFERENCE.md "Netlist Structure" (line order is irrelevant) | documented | validation_note: T12 adds the solver test (probed by hand); same test |
| S5 | **Differs from ngspice.** A parameter used before its `.param` resolves with **no diagnostic**: the reference says line order is irrelevant. `PARAM_USED_BEFORE_DEFINITION` is not used. | same | documented | validation_note: T12 adds the solver test (probed by hand); `tests/document/test_ltspice_document.py::test_use_before_definition_is_not_diagnosed` |
| S6 | **Differs from ngspice.** A repeated `.param` in one scope stops LTspice ("already defined elsewhere"): `DUPLICATE_DEFINITION` is a warning, not info. The library's reference still resolves to the last. | — (observed) | documented | validation_note: T12 adds the solver test (probed by hand); `tests/document/test_ltspice_document.py::test_a_repeated_definition_stops_ltspice` |
| S7 | **Differs from ngspice.** A repeated `.model` or `.subckt` in one scope stops LTspice (ngspice ignores it): `DUPLICATE_DEFINITION`, warning. | — (observed) | documented | validation_note: T12 adds the solver test (probed by hand); same test |
| S8 | An `X` line's `name=value` refers to the definition's default; an unknown name is ignored by LTspice and not diagnosed. | [ltspice-ref] CIRCUIT-ELEMENTS-REFERENCE.md "X — Subcircuit" | documented | validation_note: T12 adds the solver test (probed by hand); `tests/grammar/ltspice/test_ltspice_elements.py::test_subcircuit_parameters` |
| S9 | A `K` line's inductors, a `.dc` or `.step` source and a `.save I(src)` are elements of the same scope; a pattern (`I(R?)`, `I(x1:R1)`) refers to no single element. `temp` is not a reference. | [ltspice-ref] SIMULATION-COMMANDS-REFERENCE.md ".SAVE — Limit Saved Data" | documented | validation_note: T12 adds the solver test (probed by hand); `tests/document/test_ltspice_document.py::test_saved_currents_reference_elements_unless_they_are_patterns` |
| S10 | The `X` line's node count must equal the definition's port count (`SUBCKT_PORT_MISMATCH`; LTspice stops). | — (observed) | documented | validation_note: T12 adds the solver test (probed by hand); `tests/document/test_ltspice_document.py::test_port_mismatch_and_undefined_subcircuit` |
| S11 | **Differs from ngspice.** Names in a formula: LTspice's reserved list holds its constants (`pi`, `BOLTZ`, ...) and functions, so `{pi}` is not a reference. A `.param pi=1` overrides the constant in LTspice; the library still reads `pi` as reserved. A bare `.param` expression is scanned like a formula. | [ltspice-ref] SIMULATION-COMMANDS-REFERENCE.md ".PARAM — User-Defined Parameters" | documented | validation_note: T12 adds the solver test (probed by hand); `tests/document/test_ltspice_document.py::test_formula_words_follow_the_dialect` |
| S12 | LTspice only. `.step param x` defines `x` at the top level: `{x}` resolves to the `StepDirective` with no `.param` line. Sweeping one quantity twice stops LTspice (`DUPLICATE_DEFINITION`, warning). | [ltspice-ref] SIMULATION-COMMANDS-REFERENCE.md ".STEP — Parameter Sweeps" | documented | validation_note: T12 adds the solver test (probed by hand); `tests/document/test_ltspice_document.py::test_a_stepped_parameter_is_defined_by_its_step`; `test_sweeping_a_quantity_twice_is_diagnosed` |

## Includes

As for ngspice, the library never reads `.include`/`.lib` files (§7.8). An `UNRESOLVED_*` diagnostic
whose searched scopes contain one is **info**. LTspice's bundled device libraries are not visible
either: a diode naming a bundled model with no `.lib` line gets `UNRESOLVED_MODEL` (warning).
