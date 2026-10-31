# ngspice scoping

The simple scope model the document layer uses (architecture §8, decision 12;
[decision 0006](../../decisions/0006-document-layer-names-scope-and-diagnostics.md) items 4–5),
validated against ngspice 47 (2026-10-31). The implementation is
`src/netlistmod/document/index.py`; probes are in `tests/solver/test_ngspice_solver_document.py`.

## Scopes

A scope is the top level or one subcircuit **definition**, addressed by the tuple of folded
subcircuit names from the top level: `()`, `("amp",)`, `("amp", "inner")`. A definition is not an
instance: the `R1` of `("amp",)` is shared by every `X` line that calls `amp`. There is no
instance-expanded view (ngspice's `x1.r1`) in M5.

## Rules

| ID | Rule | Manual | Status | Tests |
|---|---|---|---|---|
| S1 | A top-level `.param` is global. | [ngspice-manual] §2.11.4 "Symbol scope" | validated | `test_local_parameters_mask_global_ones`; `tests/document/test_resolution.py::test_parameters_mask_globals_and_the_last_assignment_wins` |
| S2 | A definition's defaults (`.subckt div a b r2=1k`) and its body `.param` lines are local and mask a global name. | [ngspice-manual] §2.11.4 "Symbol scope", §2.11.3 "Subcircuit parameters" | validated | same; `test_references_to_param_follow_masking` |
| S3 | A `.model` or `.subckt` is local to the definition that contains it and visible in its nested definitions; one defined inside `div` is not found at the top level. | [ngspice-manual] §2.6.1 ".SUBCKT Line" (conflict: §2.11.4) | validated | `test_models_are_local_to_their_definition` (both); `tests/document/test_resolution.py::test_models_are_local_to_their_definition`, `test_local_subckt_masks_a_global_one` |
| S4 | A model, subcircuit or parameter reference is looked up in its own scope, then each enclosing scope, up to the top level, independent of file order. | — (observed) | observed | `test_model_and_subckt_names_are_case_insensitive_and_order_free`; `test_element_models_resolve_through_enclosing_scopes_in_any_order` |
| S5 | A parameter used before its `.param` still resolves, with `PARAM_USED_BEFORE_DEFINITION` (warning). | [ngspice-manual] §2.11.1 ".param line" (strict reading) | validated (discrepancy) | `test_parameter_case_order_and_redefinition` |
| S6 | A repeated `.param` in one scope resolves to the **last** assignment (`DUPLICATE_DEFINITION`, info). | — (observed) | observed | same |
| S7 | A repeated `.model` or `.subckt` in one scope resolves to the **first** definition; ngspice 47 warns "redefinition of .subckt …, ignored" (`DUPLICATE_DEFINITION`, warning). | — (observed) | observed | `test_repeated_model_and_subckt_use_the_first_definition` |
| S8 | An `X` line's `name=value` refers to the definition's default of that name (case-insensitive); an unknown name is ignored by ngspice 47 and not diagnosed (`Reference` of kind `subckt_param` with `target=None`). | [ngspice-manual] §2.11.3 "Subcircuit parameters" | validated | `test_instance_parameters_are_case_insensitive_and_unknown_ones_are_ignored`; `test_instances_resolve_their_subcircuit_and_its_defaults` |
| S9 | A `K` line's inductors, a `.dc` source and a `.save i(src)` are elements of the same scope (directives are top level only). `.dc TEMP` is not a reference. | [ngspice-manual] §11.3.2 ".DC: DC Transfer Function" | documented | `test_coupling_references_inductors_in_the_same_scope`; `test_dc_sources_and_saved_currents_reference_elements` |
| S10 | The X line's node count must equal the definition's port count (`SUBCKT_PORT_MISMATCH`; ngspice 47 stops with an error). | [ngspice-manual] §2.6.3 "Subcircuit Calls" | validated | `test_subcircuit_port_count_mismatch_fails` |
| S11 | Names in a formula: an identifier followed by `(` is a call; `v(…)`, `i(…)` take node and source names; reserved words are not parameters; `pi` is not a constant; `!`, `#`, `%` are not name characters in an expression (`NG-FML-001`). | [ngspice-manual] §2.11.5 "Syntax of expressions", §2.11.6 "Reserved words" | validated | `test_formula_name_characters_and_constants`; `tests/grammar/ngspice/test_formula.py` |

## The §2.11.4 / §2.6.1 conflict

§2.11.4 says all subcircuit and model names "are considered global and must be unique".
§2.6.1 says models and subcircuit definitions inside a definition "are strictly local". ngspice
47 follows §2.6.1: a `.model dm d` inside `div` used by a top-level `D2 out 0 dm` fails with
"can't find model". The library follows the validated reading (S3) and reports
`UNRESOLVED_MODEL`; it does not require global uniqueness.

## Includes and conditional blocks

The library never reads `.include`/`.lib` files or `.if` blocks (§7.8). An `UNRESOLVED_*`
diagnostic whose searched scopes contain an `.include` or `.lib` is **info** and says the name
may be defined there (decision 0006 item 8). An `.if` block does not soften a diagnostic (a
limitation: a model defined only in a conditional block is reported as a warning).
