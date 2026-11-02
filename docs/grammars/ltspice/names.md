# LTspice names and net identity

How the document layer compares names and decides which node names are the same net, for LTspice
(architecture §8; [decision 0009](../../decisions/0009-ltspice-dialect.md) item 8). The functions
are in `src/netlistmod/document/names.py`. Status words have the meanings of
[decision 0008](../../decisions/0008-validation-status-and-solver-harnesses.md). The probes are in
`tests/solver/test_ltspice_solver_document.py`.

Validated on: ltspice 26.1.1 (2026-11-01)

| ID | Rule | Manual | Status | Tests |
|---|---|---|---|---|
| N1 | Names compare by Unicode case folding after NFC normalisation: `ÄIN` is `äin`, `Ä` is `A` + U+0308, `STRASSE` is `straße`. | [ltspice-ref] SPICE-SYNTAX-REFERENCE.md "Text Encoding", "Node Naming" | validated | `tests/solver/test_ltspice_solver_document.py::test_names_fold_by_unicode_case_folding_after_nfc`; `tests/solver/test_ltspice_solver_document.py::test_different_letters_are_different_nets`; `tests/document/test_ltspice_document.py::test_names_fold_by_unicode_case_folding_after_nfc` |
| N2 | `0` and `GND` in any case are the one ground net, canonical name `"0"`, shared by every scope. | [ltspice-ref] SPICE-SYNTAX-REFERENCE.md "Node Naming" | validated | `tests/solver/test_ltspice_solver_document.py::test_ground_aliases`; `tests/document/test_ltspice_document.py::test_ground_aliases` |
| N3 | `00` is a distinct net: names are strings, not numbers. | same | validated | `tests/solver/test_ltspice_solver_document.py::test_a_name_like_zero_is_not_ground`; `tests/solver/test_ltspice_solver_document.py::test_numeric_names_are_strings`; `tests/document/test_ltspice_document.py::test_ground_aliases` |
| N4 | Designators compare by the same fold; a repeated designator in one scope is `DUPLICATE_ELEMENT` (LTspice stops: "Instance with that name already defined"). | — (observed) | observed | `tests/solver/test_ltspice_solver_document.py::test_a_repeated_designator_stops_ltspice`; `tests/document/test_ltspice_document.py::test_a_repeated_designator_names_ltspice` |
| N5 | Model, subcircuit and parameter names compare by the same fold. | — (observed) | observed | `tests/solver/test_ltspice_solver_document.py::test_other_names_fold_alike`; `tests/edits/test_ltspice_edits.py::test_names_address_elements_by_the_dialect_fold` |
| N6 | `K` inductor references compare by the same fold. | — (observed) | observed | `tests/solver/test_ltspice_solver_document.py::test_coupling_references_fold_alike`; `tests/grammar/ltspice/test_ltspice_elements.py::test_couplings_take_two_or_more_inductors` |
| N7 | A net used inside a subcircuit definition is local to it, except ground, the definition's ports, `.global` nodes and `$G_*` nodes. | [ltspice-ref] SIMULATION-COMMANDS-REFERENCE.md ".GLOBAL — Global Nodes" | validated | `tests/solver/test_ltspice_solver_document.py::test_a_net_in_a_definition_is_local`; `tests/document/test_ltspice_document.py::test_global_and_local_nets` |
| N8 | A definition's ports are nets of its own scope; an instance binds them by position. | [ltspice-ref] CIRCUIT-ELEMENTS-REFERENCE.md "X — Subcircuit" | validated | `tests/solver/test_ltspice_solver_document.py::test_ports_bind_by_position`; `tests/document/test_ltspice_document.py::test_port_mismatch_and_undefined_subcircuit` |
| N9 | `.global` nodes and nodes matching `$G_*` (by the same fold) are one net in every scope. `.global` is top level only. | [ltspice-ref] SIMULATION-COMMANDS-REFERENCE.md ".GLOBAL — Global Nodes" | validated | `tests/solver/test_ltspice_solver_document.py::test_global_nodes_join_every_scope`; `tests/document/test_ltspice_document.py::test_dollar_g_nodes_are_global_by_name` |
| N10 | Bus names such as `d[0]` are ordinary node names; a bus tap has no meaning in a netlist. | — (observed, L20) | observed | `tests/solver/test_ltspice_solver_document.py::test_bus_names_are_nets`; `tests/document/test_ltspice_document.py::test_bus_names_are_nets` |
| N11 | **Known limit.** A node named `<instance>:<node>` is joined by LTspice to that node inside an instance of the same scope, and the library keeps it as a net of its own. `X1` is written `x1`, `X§U1` is written `u1`, and `XY§U1` is written `xy§u1`; `x1:x2:n` follows each level. A name that no instance holds (`x1:zz`, `x7:n`, `a:b`) is an ordinary node. `NODE_INTO_INSTANCE` flags it: a warning, info when the definition is in an include, and a warning when the last part is a global node or empty, which stops LTspice. | — (observed) | observed | `tests/solver/test_ltspice_solver_document.py::test_a_node_into_an_instance_is_joined_and_flagged`; `tests/solver/test_ltspice_solver_document.py::test_other_names_with_a_colon_are_ordinary_nodes`; `tests/solver/test_ltspice_solver_document.py::test_a_node_in_a_body_reaches_an_instance_of_that_body`; `tests/document/test_ltspice_document.py::test_a_node_into_an_instance_is_a_warning` |

## What the signature uses instead

As for ngspice, the topology signature holds the exact text of each token and does not fold it
(decision 0006 item 6).

## Not seen

Nodes inside `.include`/`.lib` files are not nets of the library (§7.8). A `.step` over a node name
does not exist. An expression as a node name (`I1 {CONNECT} 0 2m`) is a documented LTspice form that
the library rejects, since it would hide topology (discrepancies.md).
