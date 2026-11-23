"""The node counts that each LEVEL of an xyce transistor model takes (decision 0031 item 5).

The table is data (``xyce-levels.json``; xm4-tasks 5.1 point 11, observed on XyceNF 7.10.0): an
element class name (``BipolarTransistor``, ``Mosfet``, ``Jfet``, ``Mesfet``), then a LEVEL, maps
to the range of node counts Xyce takes, the range when the line sets ``TNODEOUT=``, and what
Xyce does with more nodes than that. A model without LEVEL is ``default_level``. The document
layer's ``NODE_COUNT_MISMATCH`` reads it; the grammar counts nodes by letter only. Internal to
the package until X-M8 (xyce-plan.md section 8.2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any, Literal

_LEVELS = "xyce-levels.json"
_EXTRA = ("dropped", "joined", "stops")

Extra = Literal["dropped", "joined", "stops"]


@dataclass(frozen=True, slots=True)
class LevelNodes:
    """The node counts of one LEVEL: ``nodes`` (least, most), ``tnodeout`` the same when the line
    sets ``TNODEOUT=`` (``None``: as ``nodes``), and ``extra``, what Xyce does with more nodes
    than the range (``None`` where it was not observed). Fewer nodes always stop Xyce."""

    nodes: tuple[int, int]
    tnodeout: tuple[int, int] | None
    extra: Extra | None

    def range(self, tnodeout: bool) -> tuple[int, int]:
        """The range that applies to a line, which sets ``TNODEOUT=`` or not."""
        return self.tnodeout if tnodeout and self.tnodeout is not None else self.nodes


def _pair(value: object) -> tuple[int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(count, int) for count in value)
        or value[0] > value[1]
    ):
        raise ValueError(f"{_LEVELS}: a node range is [least, most], not {value!r}")
    return value[0], value[1]


@lru_cache(maxsize=1)
def _table() -> tuple[int, dict[str, dict[int, LevelNodes]]]:
    resource = files("netlistmod.model") / _LEVELS
    return _read(json.loads(resource.read_text(encoding="utf-8")))


def _read(parsed: dict[str, Any]) -> tuple[int, dict[str, dict[int, LevelNodes]]]:
    """The default level and the table of a parsed ``xyce-levels.json``; ``ValueError`` if it
    does not have the shape the module docstring gives."""
    default = parsed.get("default_level")
    if not isinstance(default, int):
        raise ValueError(f"{_LEVELS} must give a `default_level`")
    table: dict[str, dict[int, LevelNodes]] = {}
    for name, levels in parsed.items():
        if name in ("source", "default_level"):
            continue
        if not isinstance(levels, dict):
            raise ValueError(f"{_LEVELS}: `{name}` must map levels to node counts")
        table[name] = {}
        for level, entry in levels.items():
            if not isinstance(entry, dict) or "nodes" not in entry:
                raise ValueError(f"{_LEVELS}: `{name}` level {level} must give its `nodes`")
            extra = entry.get("extra")
            if extra is not None and extra not in _EXTRA:
                raise ValueError(f"{_LEVELS}: `{name}` level {level}: `extra` is one of {_EXTRA}")
            tnodeout = entry.get("tnodeout")
            table[name][int(level)] = LevelNodes(
                _pair(entry["nodes"]), None if tnodeout is None else _pair(tnodeout), extra
            )
    return default, table


def default_level() -> int:
    """The LEVEL of a model that writes none."""
    return _table()[0]


def level_nodes(class_name: str, level: int) -> LevelNodes | None:
    """The node counts of ``level`` for elements of ``class_name``; ``None`` if the table has no
    such level (an unknown level, which the check passes over)."""
    return _table()[1].get(class_name, {}).get(level)
