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

    ``notation`` is ``"rkm"`` for an RKM value (in ngspice, accepted only with
    ``parse(..., rkm=True)``) or an LTspice embedded decimal, which is LTspice's own reading.
    ``solver_mismatch`` marks an RKM value that ngspice reads differently from IEC 60062
    (resistor ``1M0`` and capacitor ``4F7``); it is always ``False`` for standard notation and for
    LTspice.
    """

    text: str
    span: Span
    notation: Literal["standard", "rkm"] = "standard"
    solver_mismatch: bool = False


@dataclass(frozen=True, slots=True)
class Formula:
    """A brace or quoted expression, or a double-quoted string parameter value.

    ``text`` excludes the delimiters; ``span`` includes them. The contents are not parsed. The
    delimiter is empty for a bare ``.param`` expression, which only LTspice accepts.
    """

    text: str
    delimiter: Literal["{", "'", '"', ""]
    span: Span


Value: TypeAlias = NumericValue | Formula


@dataclass(frozen=True, slots=True)
class ValueList:
    """The comma-separated values of an LTspice ``tc=a,b``; ``span`` runs from first to last.

    ``text`` is the source slice of ``span``, so every parameter value has a ``text``.
    """

    text: str
    values: tuple[Value, ...]
    span: Span


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
    """A ``name=value`` parameter; ``span`` runs from the name to the end of the value.

    Used for instance parameters, ``.param`` assignments, ``.model`` parameters and ``.subckt``
    default values. The value is a :class:`ValueList` only for an LTspice ``tc=``, and an
    :class:`Identifier` only for an LTspice bare word in ``mfg``, ``pn`` or ``type``, which is kept
    verbatim.
    """

    name: str
    value: Value | ValueList | Identifier
    span: Span
    name_span: Span


@dataclass(frozen=True, slots=True)
class Identifier:
    """A bare name used as a value, such as the ``gear`` of ``.options method=gear``."""

    name: str
    span: Span

    @property
    def text(self) -> str:
        """The name, so that every parameter value has a ``text``."""
        return self.name


@dataclass(frozen=True, slots=True)
class Flag:
    """A keyword flag, such as a diode's ``off`` or the ``uic`` of ``.tran``.

    In LTspice a flag may take a value (``noiseless=0``): ``value`` holds its text, and ``span``
    then runs to the end of the value. The threshold is not interpreted (non-goal 6).
    """

    name: str
    span: Span
    value: Value | None = None


@dataclass(frozen=True, slots=True)
class AcSpec:
    """The ``AC`` part of a source; ``span`` runs from the keyword to the last value."""

    magnitude: Value
    phase: Value | None
    span: Span
