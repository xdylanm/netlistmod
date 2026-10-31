"""Netlist document and read-only indexes."""

from netlistmod.document.diagnostics import Diagnostic, DiagnosticCode, Severity
from netlistmod.document.document import Netlist
from netlistmod.document.index import Reference, ReferenceKind, Scope
from netlistmod.document.lines import Line, Lines, ScopePath
from netlistmod.document.names import GROUND, fold, is_ground, net_name
from netlistmod.document.topology import Connection, Net, TopologySignature, TopologyView

__all__ = [
    "GROUND",
    "Connection",
    "Diagnostic",
    "DiagnosticCode",
    "Line",
    "Lines",
    "Net",
    "Netlist",
    "Reference",
    "ReferenceKind",
    "Scope",
    "ScopePath",
    "Severity",
    "TopologySignature",
    "TopologyView",
    "fold",
    "is_ground",
    "net_name",
]
