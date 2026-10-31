"""Immutable value slots of element lines: numbers, formulas, references and parameters.

Values are stored as source text with spans; the library never evaluates them (non-goal 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from netlistmod.source import Span


@dataclass(frozen=True, slots=True)
class NumericValue:
    """A number exactly as written, such as ``1k``, ``10kOhm``, ``1e-6`` or ``2k7``.

    ``notation`` is ``"rkm"`` for an RKM value (accepted only with ``parse(..., rkm=True)``).
    ``solver_mismatch`` marks an RKM value that ngspice reads differently from IEC 60062
    (resistor ``1M0`` and capacitor ``4F7``); it is always ``False`` for standard notation.
    """

    text: str
    span: Span
    notation: Literal["standard", "rkm"] = "standard"
    solver_mismatch: bool = False


@dataclass(frozen=True, slots=True)
class Formula:
    """A brace or quoted expression, or a double-quoted string parameter value.

    ``text`` excludes the delimiters; ``span`` includes them. The contents are not parsed.
    """

    text: str
    delimiter: Literal["{", "'", '"']
    span: Span


Value: TypeAlias = NumericValue | Formula


@dataclass(frozen=True, slots=True)
class ModelReference:
    """The name of a ``.model`` an element refers to."""

    model_name: str
    span: Span


@dataclass(frozen=True, slots=True)
class SubcktReference:
    """The subcircuit name of an ``X`` line."""

    name: str
    span: Span


@dataclass(frozen=True, slots=True)
class ElementReference:
    """A reference to another element by designator (the inductors of a ``K`` line)."""

    designator: str
    span: Span


@dataclass(frozen=True, slots=True)
class ParamAssignment:
    """An instance parameter ``name=value``; ``span`` runs from the name to the end of the value."""

    name: str
    value: Value
    span: Span
    name_span: Span


@dataclass(frozen=True, slots=True)
class Flag:
    """A keyword flag on an element line, such as a diode's ``off``."""

    name: str
    span: Span


@dataclass(frozen=True, slots=True)
class AcSpec:
    """The ``AC`` part of a source; ``span`` runs from the keyword to the last value."""

    magnitude: Value
    phase: Value | None
    span: Span
