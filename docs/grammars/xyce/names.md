# Xyce names and net identity

How the document layer compares names and decides which node names are the same net, for Xyce
(architecture §8; [decision 0026](../../decisions/0026-the-xyce-dialect.md),
[decision 0027](../../decisions/0027-xyce-structure-names-and-values.md) items 3 and 4). The
functions are in `src/netlistmod/dialects.py` and `src/netlistmod/document/names.py`; the grammar
side of a name is `XY-NAM-001`. Status words have the meanings of
[decision 0008](../../decisions/0008-validation-status-and-solver-harnesses.md); `validated` and
`observed` rows cite a solver test, run on the version below (`-v` prints `XyceNF Release 7.10.0`).

Validated on: xyce 7.10.0 (2026-11-15)

| ID | Rule | Manual | Status | Tests |
|---|---|---|---|---|
| N1 | `0` is the one ground net, canonical name `"0"`, shared by every scope. Without `.PREPROCESS REPLACEGROUND TRUE`, `GND` and the other synonyms of N2 are ordinary nets, and `00` is a distinct net. | [xyce-ref] §2.3.1.1 p182 "Global nodes"; [xyce-ug] §4.1.3 p42 "Elements" | validated | `tests/architecture/test_hidden_dialects.py::test_only_zero_is_ground_on_xyce`; `tests/document/test_xyce_names.py::test_only_zero_is_ground_without_replaceground`; `tests/solver/test_xyce_structure_probes.py::test_gnd_is_not_ground_without_replaceground`; `tests/solver/test_xyce_structure_probes.py::test_double_zero_is_not_ground` |
| N2 | With `.PREPROCESS REPLACEGROUND TRUE`, `GND`, `GND!` and `GROUND` in any case are ground, `"0"`, in every scope; `GROUND!` is not. The flag is netlist-wide: the statement may stand in a subcircuit body and acts on the whole netlist (`Scope.replace_ground` is the same everywhere). `FALSE` leaves them ordinary nets. A second statement is a `ParseError` (`XY-PRE-001`). The value is part of the topology signature. | [xyce-ref] §2.1.28 p125 ".PREPROCESS REPLACEGROUND (Ground Synonym)" | validated | `tests/document/test_xyce_names.py::test_replaceground_makes_the_ground_synonyms_ground`; `tests/document/test_xyce_names.py::test_other_names_stay_nets_under_replaceground`; `tests/document/test_xyce_names.py::test_replaceground_sets_the_netlist_wide_flag`; `tests/document/test_xyce_names.py::test_the_signature_records_replaceground`; `tests/solver/test_xyce_names_probes.py::test_replaceground_makes_the_synonyms_ground`; `tests/solver/test_xyce_names_probes.py::test_ground_with_a_bang_is_not_a_synonym`; `tests/solver/test_xyce_names_probes.py::test_replaceground_false_keeps_gnd_a_node`; `tests/solver/test_xyce_names_probes.py::test_replaceground_in_a_body_acts_on_the_whole_netlist` |
| N3 | A node whose name begins `$G`, in any case, is global (decision X-D3): one net in every scope, `Net.global_`, named by its folded name (`is_automatic_global`). `$` alone does not make a node global. | [xyce-ref] §2.3.1.1 p182 "Global nodes"; [xyce-ug] §4.1.2.1 p41 "Global Nodes" | validated | `tests/document/test_xyce_names.py::test_a_dollar_g_node_is_global`; `tests/document/test_xyce_names.py::test_other_dollar_names_are_not_global`; `tests/document/test_xyce_names.py::test_a_dollar_g_net_is_global`; `tests/solver/test_xyce_names_probes.py::test_a_dollar_g_node_is_global`; `tests/solver/test_xyce_names_probes.py::test_a_dollar_name_without_g_is_local` |
| N4 | `.GLOBAL` makes its names global nodes, as on ngspice: top level only, at least one name, no commas (`XY-GLB-001`). | [xyce-ref] §2.1.11 p44 ".GLOBAL (Global Node)" | validated | `tests/document/test_xyce_names.py::test_replaceground_sets_the_netlist_wide_flag`; `tests/solver/test_xyce_names_probes.py::test_global_makes_nodes_global` |
| N5 | Designators, model, subcircuit, parameter, function and node names compare by ASCII lower case: `AB` and `ab` are one name, `Ä` and `ä` two. The manual says only that Xyce ignores case; the ASCII fold is the binary's. | [xyce-ug] §4.1.3 p41 "Elements" | observed | `tests/document/test_xyce_names.py::test_names_fold_by_ascii_case_only`; `tests/solver/test_xyce_names_probes.py::test_case_folds_in_ascii_only` |
| N6 | A name is printable ASCII except blanks and `( ) { } , : ; " ' =`; `[` and `]` are name characters, so `[s]` is a node literally named `[s]`. Non-ASCII and `"` are refused, although Xyce takes them (discrepancies.md). | [xyce-ref] §2.3.2 p184 "Legal Characters in Node and Device Names" | validated | `tests/grammar/xyce/test_xyce_names_numbers.py::test_a_global_node_takes_the_name_class`; `tests/solver/test_xyce_names_probes.py::test_name_characters_of_the_class`; `tests/solver/test_xyce_structure_probes.py::test_a_bracketed_node_is_a_literal_node_name` |
| N7 | `:` is a name character only in a node field of an element line: `X1:m` (or `X1:X2:m`) names a node of an instance, relative to the scope it is written in (decision X-D2). The library keeps it as a net of its own, and reports it with `NODE_INTO_INSTANCE` when it names an internal node of the instance's definition (architecture §7.8); X-M1 B5 and B6 read and report it. | [xyce-ref] §2.3.1.2 p182–183 "Subcircuit Nodes" | documented | validation_note: the grammar's node-field terminal is defined (`NODE_WORD`, `tests/grammar/xyce/test_xyce_names_numbers.py::test_the_node_field_terminal_also_takes_a_colon`), but no element line is read until X-M1 B5, which adds the solver evidence. |

## The flag and the signature

`Index.replace_ground` (and `Scope.replace_ground`) is `True` when the netlist holds
`.PREPROCESS REPLACEGROUND TRUE`, anywhere. `is_ground`, `net_name` and the topology view take it,
so a node named `GND` is the net `"0"` in every scope. The signature gains the entry
`("replaceground", (<value as written>,))` when the netlist has the statement, so an edit that
changes or removes it is a `TopologyViolation` at save (P4); a netlist without it, and every
ngspice and LTspice netlist, has no such entry.

## Names in expressions

Parameter and function names follow `scoping.md`; a node read in an expression (`V(X1:A)`) goes
through N7's reading (X-M1 B6).
