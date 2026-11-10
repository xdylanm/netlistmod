"""The ``.model`` types of the built-in SPICE devices, and the elements that take any other type.

The table is data (``model-types.json``; decision 0007 item 3): an element class name maps to the
types it may refer to, compared case-insensitively, with a dialect's own types added (decision
0014: LTspice's Z also takes an IGBT; decision 0019: only ngspice has Y and P). The types it
lists are the built-in ones. ``not_builtin`` names the elements whose model may be any type that is
not built in: ngspice's code models and OSDI devices (decision 0020 items 5 and 6). The parser
uses the built-in set to keep a code model's values off a built-in model, and the document
layer's model-type check reads the same table (``netlistmod.document.models``).
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

from netlistmod.dialects import Dialect

_MODEL_TYPES = "model-types.json"


@lru_cache(maxsize=1)
def _parsed() -> dict[str, Any]:
    resource = files("netlistmod.model") / _MODEL_TYPES
    parsed = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict) or not isinstance(parsed.get("elements"), dict):
        raise ValueError("model-types.json must map element class names to model types")
    return parsed


@lru_cache(maxsize=None)
def model_type_table(dialect: Dialect) -> dict[str, frozenset[str]]:
    """Each element class name, mapped to the folded model types it takes in ``dialect``."""
    parsed = _parsed()
    elements: dict[str, list[str]] = parsed["elements"]
    extra: dict[str, list[str]] = parsed.get(dialect.value, {})
    names = (*elements, *(name for name in extra if name not in elements))
    return {
        str(name): frozenset(
            str(kind).lower() for kind in (*elements.get(name, ()), *extra.get(name, ()))
        )
        for name in names
    }


@lru_cache(maxsize=None)
def builtin_model_types(dialect: Dialect) -> frozenset[str]:
    """The folded model types that are built-in SPICE types in ``dialect``."""
    return frozenset(kind for kinds in model_type_table(dialect).values() for kind in kinds)


def takes_any_other_type(class_name: str) -> bool:
    """Whether elements of ``class_name`` take any model type that is not built in."""
    return class_name in _parsed().get("not_builtin", ())
