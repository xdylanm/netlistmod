"""The model types each element accepts (decision 0007 item 3).

The table is data (``model/model-types.json``, read by :mod:`netlistmod.model.model_types`): an
element class name maps to the ``.model`` types it may refer to, compared case-insensitively.
ngspice's code models and OSDI devices take any type that is not a built-in one (decision 0020
items 5 and 6). It backs the ``MODEL_TYPE_MISMATCH`` diagnostic and the type check of
``set_model``.
"""

from __future__ import annotations

from netlistmod.dialects import Dialect
from netlistmod.model.model_types import (
    builtin_model_types,
    model_type_table,
    takes_any_other_type,
)
from netlistmod.model.nodes import Component


def allowed_model_types(element: Component, dialect: Dialect) -> frozenset[str]:
    """The folded model types ``element`` may refer to in ``dialect``; empty if it takes none or
    takes any type that is not built in (see :func:`model_type_requirement`)."""
    return model_type_table(dialect).get(type(element).__name__, frozenset())


def model_type_allowed(element: Component, model_type: str, dialect: Dialect) -> bool:
    """Whether a model of ``model_type`` (as written) fits ``element`` in ``dialect``."""
    if takes_any_other_type(type(element).__name__):
        return model_type.lower() not in builtin_model_types(dialect)
    return model_type.lower() in allowed_model_types(element, dialect)


def model_type_requirement(element: Component, dialect: Dialect) -> str:
    """What a message says ``element`` takes: ``a model of type `NPN`, `PNP```, or, for a code
    model or an OSDI device, a model whose type is not a built-in one."""
    name = type(element).__name__
    if takes_any_other_type(name):
        what = (
            "an OSDI module's type, from a module loaded with `pre_osdi`"
            if name == "OsdiDevice"
            else "a code model's type"
        )
        return f"a model whose type is not a built-in SPICE type ({what})"
    allowed = ", ".join(
        f"`{kind.upper()}`" for kind in sorted(allowed_model_types(element, dialect))
    )
    return f"a model of type {allowed}"
