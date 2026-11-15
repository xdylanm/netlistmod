"""Netlist document and read-only indexes.

Internal: ``__all__`` lists only what :mod:`netlistmod` exports from here. The read-only base
class is ``netlistmod.document.document.Netlist``; callers use the editable ``netlistmod.Netlist``.
"""

from netlistmod.document.diagnostics import Diagnostic, DiagnosticCode, Severity
from netlistmod.document.index import Reference, ReferenceKind, Scope
from netlistmod.document.lines import Line, Lines, ScopePath
from netlistmod.document.topology import (
    Connection,
    ExpressionRead,
    Net,
    TopologySignature,
    TopologyView,
)

__all__ = [
    "Connection",
    "Diagnostic",
    "DiagnosticCode",
    "ExpressionRead",
    "Line",
    "Lines",
    "Net",
    "Reference",
    "ReferenceKind",
    "Scope",
    "ScopePath",
    "Severity",
    "TopologySignature",
    "TopologyView",
]
