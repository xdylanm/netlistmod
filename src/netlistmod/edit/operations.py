"""Plan builders for the restricted edit operations (architecture §7.2, decision 0007).

Each function looks up its target in a netlist and returns the edits that make the change,
with the slot checks that verify where they land; it never applies them. Spans come from the
typed nodes and text is composed by :mod:`netlistmod.edit.conventions`; nothing scans source
text for syntax (P13). :mod:`netlistmod.edit.api` exposes these as methods.

The operations live in modules by family (``_ops_*.py``); this module is the one place callers
import them from."""

from __future__ import annotations

from netlistmod.edit._ops_behavioral import set_expression
from netlistmod.edit._ops_common import (
    DirectiveText,
    UpsertTarget,
    include_target,
    upsert_target,
)
from netlistmod.edit._ops_controlled import set_switch_state
from netlistmod.edit._ops_directives import (
    add_directive,
    add_include,
    directive_target,
    remove_directive,
    replace_directive,
    set_directive,
)
from netlistmod.edit._ops_elements import (
    remove_value,
    set_coupling,
    set_instance_param,
    set_model,
    set_param,
    set_value,
)
from netlistmod.edit._ops_nonlinear import set_poly_coefficients, set_table
from netlistmod.edit._ops_sources import (
    remove_stimulus,
    set_ac,
    set_dc,
    set_stimulus,
    set_stimulus_arg,
    stimulus_target,
)
from netlistmod.edit._ops_statements import (
    set_model_param,
    set_param_statement,
)

__all__ = [
    "DirectiveText",
    "UpsertTarget",
    "add_directive",
    "add_include",
    "directive_target",
    "include_target",
    "remove_directive",
    "remove_stimulus",
    "remove_value",
    "replace_directive",
    "set_ac",
    "set_coupling",
    "set_dc",
    "set_directive",
    "set_expression",
    "set_instance_param",
    "set_model",
    "set_model_param",
    "set_param",
    "set_poly_coefficients",
    "set_param_statement",
    "set_stimulus",
    "set_stimulus_arg",
    "set_table",
    "set_switch_state",
    "set_value",
    "stimulus_target",
    "upsert_target",
]
