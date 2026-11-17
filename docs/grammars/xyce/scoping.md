# Xyce scoping

The scope model of the document layer for Xyce (architecture §8;
[decision 0026](../../decisions/0026-the-xyce-dialect.md),
[decision 0027](../../decisions/0027-xyce-structure-names-and-values.md) items 9 and 10;
xm1-tasks 5.1 points 20 to 25). The code is `src/netlistmod/document/index.py` and
`src/netlistmod/document/diagnostics.py`, with the per-dialect tables `_ORDER_MATTERS`,
`_FIRST_PARAM_WINS`, `_USER_FUNCTIONS`, `_REPEAT_STOPS` and `_PARAM_REPEATS`. Status words have
the meanings of [decision 0008](../../decisions/0008-validation-status-and-solver-harnesses.md);
`validated` rows cite a solver test, run on the version below.

Validated on: xyce 7.10.0 (2026-11-15)

Scopes are definition scopes, as on ngspice (`()` for the top level, a tuple of folded
subcircuit names for a body). Subcircuits, `.MODEL` and their scoping are X-M1 B4's; the rows
below that need a body (S1, S6) are implemented and validated on the solver, and their library
tests come with B4, which reads `.SUBCKT`.

| ID | Rule | Manual | Status | Tests |
|---|---|---|---|---|
| S1 | A top-level `.PARAM` is global; a body `.PARAM` is local to its definition and visible in nested definitions. A reference is resolved in its own scope, then each enclosing scope. | [xyce-ref] §2.1.26 p121 ".PARAM (Parameter)" | validated | `tests/document/test_xyce_scoping.py::test_a_global_param_is_a_top_level_parameter`; `tests/solver/test_xyce_param_probes.py::test_param_forms` |
| S2 | `.GLOBAL_PARAM` is a top-level `.PARAM` (a `GlobalParamStatement`): it may stand only at the top level and defines no function. | [xyce-ref] §2.1.12 p45–46 ".GLOBAL_PARAM (Global parameter)" | validated | `tests/document/test_xyce_scoping.py::test_a_global_param_is_a_top_level_parameter`; `tests/solver/test_xyce_param_probes.py::test_global_param_is_top_level_only` |
| S3 | A repeated parameter in one scope resolves to its **first** definition, as Xyce 7.10 does by default (its own warning says so; `-redefined_params` changes it), with a `DUPLICATE_DEFINITION` warning. The manual says the last is used (discrepancies.md). | [xyce-ref] §2.1.26 p120 ".PARAM (Parameter)" | validated | `tests/document/test_xyce_scoping.py::test_a_repeated_param_resolves_to_the_first_definition`; `tests/solver/test_xyce_param_probes.py::test_the_first_definition_wins_and_param_beats_global_param` |
| S4 | Order does not matter: a parameter or a function may be used before its definition, so there is no `PARAM_USED_BEFORE_DEFINITION` on xyce, although the manual's `.FUNC` wording says a function is used after it. | [xyce-ref] §2.1.10 p42 ".FUNC (Function)" | validated | `tests/document/test_xyce_scoping.py::test_order_does_not_matter`; `tests/solver/test_xyce_param_probes.py::test_functions` |
| S5 | A `.PARAM` and a `.GLOBAL_PARAM` of the same name: the `.PARAM` wins, in either order. The scope's table lists the `.GLOBAL_PARAM` assignments after the `.PARAM` ones, and the `.GLOBAL_PARAM` gets a `DUPLICATE_DEFINITION` warning. | [xyce-ref] §2.1.12 p45 ".GLOBAL_PARAM (Global parameter)" | validated | `tests/document/test_xyce_scoping.py::test_param_beats_global_param_whatever_the_order`; `tests/solver/test_xyce_param_probes.py::test_the_first_definition_wins_and_param_beats_global_param` |
| S6 | A body `.PARAM` that repeats a `PARAMS:` name is shadowed by the default or the instance's value: a `DUPLICATE_DEFINITION` warning that says so (the defaults come first in the table, so S3 resolves to them). | [xyce-ref] §2.1.37 p159 ".SUBCKT (Subcircuit)" | validated | `tests/grammar/xyce/test_xyce_statements.py::test_a_body_param_shadowed_by_a_params_default_is_reported`; `tests/solver/test_xyce_param_probes.py::test_a_body_param_is_shadowed_by_a_params_default` |
| S7 | The reserved words time, freq, hertz, vt, temp, temper, gmin, pi and exp are never parameter references, and a definition never masks them: defining one as a parameter, a `PARAMS:` default or a function argument is a `ParseError`, and so is a default whose name is not a parameter name (`PARAMS: 1x=1`). As a `.PARAM`, Xyce stops on five of them and ignores `hertz`, `temper`, `pi` and `exp`; as a `PARAMS:` default it stops on `time`, `vt`, `temp` and `gmin` and ignores the other five; it stops on `1x` (discrepancies.md). | [xyce-ref] §2.1.26 p121 ".PARAM (Parameter)"; [xyce-ref] §2.1.10 p42 ".FUNC (Function)"; [xyce-ref] §2.1.37 p159 ".SUBCKT (Subcircuit)" | validated | `tests/document/test_xyce_scoping.py::test_reserved_words_are_never_references`; `tests/grammar/xyce/test_xyce_statements.py::test_a_reserved_word_is_rejected_as_a_default`; `tests/grammar/xyce/test_xyce_statements.py::test_a_default_takes_a_parameter_name`; `tests/solver/test_xyce_param_probes.py::test_a_reserved_word_parameter_stops_xyce`; `tests/solver/test_xyce_param_probes.py::test_some_reserved_words_are_ignored`; `tests/solver/test_xyce_statement_probes.py::test_a_reserved_default_stops_xyce`; `tests/solver/test_xyce_statement_probes.py::test_some_reserved_defaults_are_ignored`; `tests/solver/test_xyce_statement_probes.py::test_a_default_name_outside_the_parameter_class_stops_xyce` |
| S8 | A `.FUNC`, or a function on a `.PARAM` line, is scoped like a model: local to its scope and visible in nested definitions (the scope's internal function table until X-M8, `Scope._functions`). A call to a name that is not a built-in function is a `function` reference, resolved to the `FunctionDefinition`; a built-in call is not a reference. The arguments are local to the body, where they mask parameters. A repeated function is a `DUPLICATE_DEFINITION` warning, since Xyce stops. A call that resolves to no function is an `UNRESOLVED_PARAM` (a warning, or info with an include in scope), as an unresolved parameter is; Xyce stops on it. | [xyce-ref] §2.1.10 p42–43 ".FUNC (Function)" | validated | `tests/document/test_xyce_scoping.py::test_function_calls_are_function_references`; `tests/document/test_xyce_scoping.py::test_a_function_argument_shadows_a_parameter_in_its_body`; `tests/document/test_xyce_scoping.py::test_a_repeated_function_is_a_warning`; `tests/document/test_xyce_document.py::test_an_unresolved_function_is_reported_as_a_parameter_is`; `tests/document/test_xyce_document.py::test_an_unresolved_function_with_an_include_is_info`; `tests/solver/test_xyce_param_probes.py::test_functions`; `tests/solver/test_xyce_param_probes.py::test_xyce_stops_on`; `tests/solver/test_xyce_param_probes.py::test_an_undefined_function_stops_xyce` |
| S9 | A bare `.PARAM` value (decision X-D5) is scanned like a braced one, from the start of its text. | [xyce-ref] §2.2 p164 "Expressions" | validated | `tests/document/test_xyce_scoping.py::test_a_bare_value_is_scanned_from_its_start`; `tests/solver/test_xyce_param_probes.py::test_param_forms` |

## Not yet

- `.MODEL` and `.SUBCKT` scoping, repeated models and subcircuits (Xyce stops on both;
  `_REPEAT_STOPS` already says so) and model binning are X-M1 B4's.
- The X-M2 rows, written at X-M2 B6 with their solver tests: `.DC` and `.STEP` targets resolved
  a parameter first, then an element or (for `head:param`) a model; the `.DATA` namespace
  (top level only, the last of a repeated name); condition nodes resolved in their line's scope
  (decision 0028 items 4, 6 and 8; implemented at X-M2 B5, `document-layer.md` section 9).

## Includes

As for ngspice, the library will never read `.include`/`.lib` files or `.lib` blocks (§7.8).
