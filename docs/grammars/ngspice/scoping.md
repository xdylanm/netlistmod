# ngspice scoping

The simple scope model the document layer uses (architecture §8, decision 12;
[decision 0006](../../decisions/0006-document-layer-names-scope-and-diagnostics.md) items 4–5),
validated against ngspice 47 (2026-10-31). The implementation is
`src/netlistmod/document/index.py`; probes are in `tests/solver/test_ngspice_solver_document.py`
and, for S9, `tests/solver/test_ngspice_validation.py` (M7). The status words have the meanings of
[decision 0008](../../decisions/0008-validation-status-and-solver-harnesses.md); a rule ngspice
also tolerates in a form the library rejects keeps its status and has a row in
[discrepancies.md](./discrepancies.md).

Validated on: ngspice 47 (2026-10-31)

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
| S5 | A parameter used before its `.param` still resolves, with `PARAM_USED_BEFORE_DEFINITION` (warning), but only when the reference and the definition it resolves to are in the **same scope** and the reference comes before that scope's first definition of the name. A reference that resolves to an enclosing scope's parameter is never warned: §2.11.1 orders assignments "through the expanded circuit", and a body is expanded where it is called, not where it is defined (M5 review R1, 2026-10-31). | [ngspice-manual] §2.11.1 ".param line" (strict reading) | validated | `test_parameter_case_order_and_redefinition`; `tests/document/test_diagnostics.py::test_used_before_definition_is_judged_within_one_scope`; `document_basic/library_first.cir` |
| S6 | A repeated `.param` in one scope resolves to the **last** assignment (`DUPLICATE_DEFINITION`, info). | — (observed) | observed | same |
| S7 | A repeated `.model` or `.subckt` in one scope resolves to the **first** definition; ngspice 47 warns "redefinition of .subckt …, ignored" (`DUPLICATE_DEFINITION`, warning). | — (observed) | observed | `test_repeated_model_and_subckt_use_the_first_definition` |
| S8 | An `X` line's `name=value` refers to the definition's default of that name (case-insensitive); an unknown name is ignored by ngspice 47 and not diagnosed (`Reference` of kind `subckt_param` with `target=None`). | [ngspice-manual] §2.11.3 "Subcircuit parameters" | validated | `test_instance_parameters_are_case_insensitive_and_unknown_ones_are_ignored`; `test_instances_resolve_their_subcircuit_and_its_defaults` |
| S9 | A `K` line's inductors, a `.dc` source and a `.save i(src)` are elements of the same scope (directives are top level only). `.dc TEMP` is not a reference. ngspice 47 stops when a top-level `K`, `.dc` or `.save i()` names an element inside an instance ("coupling to non-existent inductor", "not in the circuit", "no data saved"); the library reports `UNRESOLVED_ELEMENT` (warning). | [ngspice-manual] §11.3.2 ".DC: DC Transfer Function" | validated | `test_top_level_references_do_not_reach_into_an_instance`; `test_coupling_references_inductors_in_the_same_scope`; `test_dc_sources_and_saved_currents_reference_elements` |
| S10 | The X line's node count must equal the definition's port count (`SUBCKT_PORT_MISMATCH`; ngspice 47 stops with an error). | [ngspice-manual] §2.6.3 "Subcircuit Calls" | validated | `test_subcircuit_port_count_mismatch_fails` |
| S11 | Names in a formula: an identifier followed by `(` is a call; `v(…)`, `i(…)` take node and source names; reserved words are not parameters; `pi` is not a constant; `!`, `#`, `%` are not name characters in an expression (`NG-FML-001`). | [ngspice-manual] §2.11.5 "Syntax of expressions", §2.11.6 "Reserved words" | validated | `test_formula_name_characters_and_constants`; `tests/grammar/ngspice/test_formula.py` |

## The §2.11.4 / §2.6.1 conflict

§2.11.4 says all subcircuit and model names "are considered global and must be unique".
§2.6.1 says models and subcircuit definitions inside a definition "are strictly local". ngspice
47 follows §2.6.1: a `.model dm d` inside `div` used by a top-level `D2 out 0 dm` fails with
"can't find model". The library follows the validated reading (S3) and reports
`UNRESOLVED_MODEL`; it does not require global uniqueness.

## Includes and conditional blocks

The library never reads `.include`/`.lib` files, `.if` blocks or `.lib` blocks (§7.8). An
`UNRESOLVED_*` diagnostic whose searched scopes contain any of these is **info** and says the name
may be defined there (decision 0006 item 8, decision 0012). A `.control` block does not count.
