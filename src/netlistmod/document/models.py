"""The model types each element accepts (decision 0007 item 3).

The table is data (``model-types.json``): an element class name maps to the ``.model`` types
it may refer to, compared case-insensitively. It backs the ``MODEL_TYPE_MISMATCH`` diagnostic
and the type check of ``set_model``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files

from netlistmod.document.names import fold
from netlistmod.model.nodes import Component

_MODEL_TYPES = "model-types.json"


@lru_cache(maxsize=1)
def _table() -> dict[str, frozenset[str]]:
    resource = files("netlistmod.document") / _MODEL_TYPES
    parsed = json.loads(resource.read_text(encoding="utf-8"))
    elements = parsed.get("elements") if isinstance(parsed, dict) else None
    if not isinstance(elements, dict):
        raise ValueError("model-types.json must map element class names to model types")
    return {
        str(name): frozenset(fold(str(kind)) for kind in kinds) for name, kinds in elements.items()
    }


def allowed_model_types(element: Component) -> frozenset[str]:
    """The folded model types ``element`` may refer to; empty if it takes no model."""
    return _table().get(type(element).__name__, frozenset())


def model_type_allowed(element: Component, model_type: str) -> bool:
    """Whether a model of ``model_type`` (as written) fits ``element``."""
    return fold(model_type) in allowed_model_types(element)
