# Xyce names and net identity

How the document layer compares names and decides which node names are the same net, for Xyce
(architecture §8; [decision 0026](../../decisions/0026-the-xyce-dialect.md)). The functions are in
`src/netlistmod/dialects.py` and `src/netlistmod/document/names.py`. Status words have the meanings
of [decision 0008](../../decisions/0008-validation-status-and-solver-harnesses.md); `validated` rows
cite a solver test, run on the version below (`-v` prints `XyceNF Release 7.10.0`).

Validated on: xyce 7.10.0 (2026-11-15)

X-M0 reads no node, so only the ground rule is implemented, for the dialect tables to be complete;
the rest of this document is written in X-M1, with decision X-D3 (`$G` globals) and X-D2
(`X1:node` on device lines).

| ID | Rule | Manual | Status | Tests |
|---|---|---|---|---|
| N1 | `0` is the one ground net, canonical name `"0"`, shared by every scope. `GND` and the other names `.PREPROCESS REPLACEGROUND` makes synonyms of `0` are ordinary nets without that command, and `00` is a distinct net. | [xyce-ref] §2.3.1.1 p182 "Global nodes"; [xyce-ref] §2.1.28 p125 ".PREPROCESS REPLACEGROUND (Ground Synonym)"; [xyce-ug] §4.1.3 p42 "Elements" | validated | `tests/architecture/test_hidden_dialects.py::test_only_zero_is_ground_on_xyce`; `tests/solver/test_xyce_structure_probes.py::test_gnd_is_not_ground_without_replaceground`; `tests/solver/test_xyce_structure_probes.py::test_double_zero_is_not_ground` |

## Provisional

- **Case.** Xyce ignores case in a netlist, except in file names (`[xyce-ug] §4.1.3 p41`).
  `fold_name` folds Xyce names by ASCII lower case, as on ngspice, so that the tables of
  `dialects.py` are complete; whether Unicode letters fold as well is decided in X-M1, with a
  probe. `-namesfile` lists the circuit's nodes in lower case (xm0-tasks 5.1 point 5).

## Planned

- **`$G` globals (X-M1, decision X-D3).** A node whose name starts with `$G` is global, available
  in every subcircuit (`[xyce-ref] §2.3.1.1 p182`, `[xyce-ug] §4.1.2.1 p41`); `.GLOBAL` makes other
  names global. `is_automatic_global` knows only LTspice's `$G_*` until then.
- **`X1:node` (X-M1, decision X-D2).** Xyce reaches a node inside a subcircuit instance with a
  fully resolved name, on device lines as well as in expressions (`[xyce-ug] §4.1.2 p40`;
  `[xyce-ref] §2.3.1.2 p182`).
- **Legal characters (X-M1).** `[xyce-ref] §2.3.2 p184`.
- **A bracketed node (X-M4).** Xyce 7.10 reads `[s]` as a node literally named `[s]`
  ([discrepancies](./discrepancies.md)).
