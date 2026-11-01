"""Run the golden-diff cases of ``tests/corpus/ngspice/edits_golden`` (M6 T8, T4 tier).

A case names an input fixture, a list of steps and an expected fixture. A step is
``[operation, *arguments]`` with an optional trailing object of keyword arguments, applied to
the netlist the previous step returned; ``["batch", [steps…]]`` applies its steps as one batch.
An operation is a ``Netlist`` method name or ``params.set`` / ``directives.<name>``. In keyword
arguments, ``placement`` is a ``Placement`` constant name or ``before:<Type>`` /
``after:<Type>`` (the first top-level line of that node type) and ``scope`` a list.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import netlistmod
from netlistmod import Batch, Dialect, Netlist, Placement

FAMILY = Path(__file__).parents[1] / "corpus" / "ngspice" / "edits_golden"
Step = Sequence[Any]


def manifest() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FAMILY / "manifest.json").read_text(encoding="utf-8"))
    return data


def run_case(case: dict[str, Any]) -> Netlist:
    return apply_steps(Netlist.load(FAMILY / case["input"], dialect=Dialect.NGSPICE), case["steps"])


def apply_steps(netlist: Netlist, steps: Sequence[Step]) -> Netlist:
    """Apply a case's steps in order (the LTspice cases use this too)."""
    for step in steps:
        netlist = _step(netlist, step)
    return netlist


def _step(netlist: Netlist, step: Step) -> Netlist:
    if step[0] == "batch":
        with netlist.batch() as batch:
            for inner in step[1]:
                _call(batch, netlist, inner)
        return batch.result
    result = _call(netlist, netlist, step)
    assert isinstance(result, Netlist)
    return result


def _call(target: Netlist | Batch, netlist: Netlist, step: Step) -> object:
    name, *arguments = step
    keywords: dict[str, Any] = {}
    if arguments and isinstance(arguments[-1], dict):
        keywords = dict(arguments.pop())
    if "placement" in keywords:
        keywords["placement"] = _placement(netlist, keywords["placement"])
    if "scope" in keywords:
        keywords["scope"] = tuple(keywords["scope"])
    owner: object = target
    for part in name.split(".")[:-1]:
        owner = getattr(owner, part)
    method = getattr(owner, name.split(".")[-1])
    if name.startswith("directives.") and name != "directives.add" and name != "directives.set":
        arguments[0] = _line(netlist, arguments[0])
    return method(*arguments, **keywords)


def _placement(netlist: Netlist, spec: str) -> Placement:
    if ":" not in spec:
        placement: Placement = getattr(Placement, spec)
        return placement
    side, kind = spec.split(":")
    line = _line(netlist, kind)
    return Placement.before(line) if side == "before" else Placement.after(line)


def _line(netlist: Netlist, kind: str) -> netlistmod.Line:
    line = netlist.lines.find(getattr(netlistmod, kind))
    assert line is not None, kind
    return line
