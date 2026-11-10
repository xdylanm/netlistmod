"""The model types each element accepts (decision 0007 item 3).

The table is data (``model-types.json``): an element class name maps to the ``.model`` types
it may refer to, compared case-insensitively. It backs the ``MODEL_TYPE_MISMATCH`` diagnostic
and the type check of ``set_model``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files

from netlistmod.dialects import Dialect
from netlistmod.model.nodes import Component

_MODEL_TYPES = "model-types.json"


@lru_cache(maxsize=None)
def _table(dialect: Dialect) -> dict[str, frozenset[str]]:
    """The types of both dialects (``elements``), with a dialect's own types added (decision
    0014: LTspice's Z also takes an IGBT; decision 0019: only ngspice has Y and P)."""
    resource = files("netlistmod.document") / _MODEL_TYPES
    parsed = json.loads(resource.read_text(encoding="utf-8"))
    elements = parsed.get("elements") if isinstance(parsed, dict) else None
    if not isinstance(elements, dict):
        raise ValueError("model-types.json must map element class names to model types")
    extra = parsed.get(dialect.value, {})
    names = (*elements, *(name for name in extra if name not in elements))
    return {
        str(name): frozenset(
            str(kind).lower() for kind in (*elements.get(name, ()), *extra.get(name, ()))
        )
        for name in names
    }


def allowed_model_types(element: Component, dialect: Dialect) -> frozenset[str]:
    """The folded model types ``element`` may refer to in ``dialect``; empty if it takes none."""
    return _table(dialect).get(type(element).__name__, frozenset())


def model_type_allowed(element: Component, model_type: str, dialect: Dialect) -> bool:
    """Whether a model of ``model_type`` (as written) fits ``element`` in ``dialect``."""
    return model_type.lower() in allowed_model_types(element, dialect)
