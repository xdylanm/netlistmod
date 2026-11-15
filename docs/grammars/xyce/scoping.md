# Xyce scoping

The scope model of the document layer for Xyce (architecture §8;
[decision 0026](../../decisions/0026-the-xyce-dialect.md)). X-M0 reads no definition, parameter
or reference: a netlist has only its top-level scope, which holds no names. The rules are written
in X-M1, which reads `.param`, `.global_param`, `.func`, `.model`, `.subckt`, `.include`, `.lib`
and `.global`, and re-probes rules S1–S11 of [the ngspice document](../ngspice/scoping.md) on
Xyce, as [the LTspice document](../ltspice/scoping.md) did on LTspice.

## Planned (X-M1)

- Whether a parameter may be used before its `.param`, and what a repeated `.param`, `.model` or
  `.subckt` in one scope does. The diagnostics look up these rules per dialect, and have no Xyce
  entry until then (`_REPEAT_STOPS`, `_ENDS_NAME_RULE` in `src/netlistmod/document/diagnostics.py`).
- `.global_param` and the bare expressions of decision X-D5.
- Model binning: `.model` names with `.` and an instance's selection among them
  (`[xyce-ref] §2.1.21 p89–90`).

## Includes

As for ngspice, the library will never read `.include`/`.lib` files or `.lib` blocks (§7.8).
