# ngspice names and net identity

How the document layer compares names and decides which node names are the same net
(architecture §8, decision 16; [decision 0006](../../decisions/0006-document-layer-names-scope-and-diagnostics.md)).
The functions are in `src/netlistmod/document/names.py`. Status follows the spec entries
(§11.2, with the meanings of
[decision 0008](../../decisions/0008-validation-status-and-solver-harnesses.md)): `validated`
(the manual describes it and ngspice reads every accepted form as modelled), `observed` (the
manual is silent; the rule rests on ngspice), `disputed`, or `documented` (no solver evidence,
with a validation note). Probes ran on ngspice 47 (2026-10-31) in batch mode; they are in
`tests/solver/test_ngspice_solver_document.py`.

Validated on: ngspice 47 (2026-10-31)

| ID | Rule | Manual | Status | Tests |
|---|---|---|---|---|
| N1 | Node names compare case-insensitively, by ASCII lower-casing. The canonical net name is the folded name. | [ngspice-manual] §2.1.3.4 "Node names" (case insensitive in batch mode) | validated | `test_node_names_are_case_insensitive`; `tests/document/test_topology.py::test_nets_fold_case_and_merge_ground_aliases` |
| N2 | `0` and `gnd` (any case) are the one ground net, canonical name `"0"`; it is shared by every scope. | [ngspice-manual] §2.1.3.5 "Ground node" | validated | `test_gnd_is_ground_and_00_is_a_separate_node`; `test_nets_fold_case_and_merge_ground_aliases` |
| N3 | `00` (and any other spelling of zero) is a distinct net: node names are strings, not numbers. | [ngspice-manual] §2.1.3.5 "Ground node" | validated | same |
| N4 | Designators compare case-insensitively; a repeated designator in one scope is `DUPLICATE_ELEMENT` (ngspice 47 stops with an error). | — (observed) | observed | `test_duplicate_designators_fail`; `tests/document/test_diagnostics.py::test_behaviour_table` |
| N5 | Model, subcircuit and parameter names compare case-insensitively. | — (observed) | observed | `test_model_and_subckt_names_are_case_insensitive_and_order_free`; `test_parameter_case_order_and_redefinition`; `test_instance_parameters_are_case_insensitive_and_unknown_ones_are_ignored` |
| N6 | `K` inductor references compare case-insensitively (`k1 l1 L2`). | — (observed) | observed | `test_inductor_references_are_case_insensitive` |
| N7 | A net used inside a subcircuit definition is local to it (`mid` inside `div` is `x1.mid` in ngspice, not the top-level `mid`), except ground, the definition's ports and `.global` nodes. | [ngspice-manual] §2.6.1 ".SUBCKT Line" | validated | `test_global_nodes_are_shared_and_other_nets_are_local`; `tests/document/test_topology.py::test_local_nets_ports_and_global_nodes` |
| N8 | A definition's ports are nets of its own scope; an instance binds them to its nodes by position. | [ngspice-manual] §2.6.1 ".SUBCKT Line", §2.6.3 "Subcircuit Calls" | validated | `test_local_nets_ports_and_global_nodes`; `test_subcircuit_port_count_mismatch_fails` |
| N9 | `.global` nodes are one net in every scope. `.global` is top level only (decision 0006; ngspice 47 also accepts it in a body: `discrepancies.md`). | [ngspice-manual] §2.7 ".GLOBAL" | validated | `test_global_nodes_are_shared_and_other_nets_are_local`; `test_global_inside_a_body_runs_but_the_library_rejects_it`; `tests/document/test_topology.py::test_global_nodes_are_shared_across_scopes` |
| N10 | The top-level nets the library reports are ngspice's node list (`display` after `op`, [ngspice-manual] §13.5.25 "Display: List known vectors and types") for every `statements_basic`, `elements_basic` and `document_basic` file. | — | validated | `test_library_nets_match_the_ngspice_node_list`; `test_document_basic_circuits_run` |

## What the signature uses instead

The topology signature does **not** fold names: it holds the exact text of each designator, node,
port, subcircuit name and `.global` node (decision 0006 item 6). `GND` → `gnd` leaves every query
unchanged but changes the signature, so M6's write-time check catches a splice that only changes
case.

## Settings the library cannot see

ngspice reads `set no_auto_gnd` (§2.1.3.5: `gnd` is then not ground) and `set ngbehavior`
(compatibility modes, §12.11) from `spinit` or `.spiceinit`, outside the netlist. The library
ignores both and always applies the rules above; with `no_auto_gnd` set, ngspice would treat
`gnd` as an ordinary node.

## Not seen

Nodes of elements inside opaque `.if` blocks, inside `.include`/`.lib` files and in `.control`
scripts are not nets of the library (§7.8). Nets named only in behavioral expressions
(`{V(n1)}`) are not nets either (§7.8, "Expressions can hide connectivity"). `.ic v(node)` and
`.nodeset v(node)` naming a net that no element uses are not reported (M5 T4, settled: the
diagnostic would be about a directive's argument, not topology).
