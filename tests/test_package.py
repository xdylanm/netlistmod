from __future__ import annotations

import importlib
import pkgutil
from importlib.metadata import version

import netlistmod
import netlistmod.document.document
import netlistmod.grammar


def test_package_and_subpackages_import() -> None:
    names = [
        module.name for module in pkgutil.walk_packages(netlistmod.__path__, prefix="netlistmod.")
    ]
    assert "netlistmod.source" in names

    for name in names:
        importlib.import_module(name)


def test_public_exports_and_version() -> None:
    expected = {
        "BlankLine",
        "CommentLine",
        "Dialect",
        "EditError",
        "EncodingError",
        "End",
        "OpaqueBlock",
        "OpaqueStatement",
        "ParseError",
        "ParseResult",
        "SourceText",
        "Span",
        "SpiceNetlistError",
        "TopologyError",
        "TopologyViolation",
        "Title",
        "TitleDirective",
        "UnsupportedConstruct",
        "UnknownDirective",
        "AcSpec",
        "Capacitor",
        "Component",
        "CurrentSource",
        "BehavioralSource",
        "BipolarTransistor",
        "Diode",
        "Jfet",
        "Mesfet",
        "Mosfet",
        "ElementReference",
        "Flag",
        "Formula",
        "Inductor",
        "ModelReference",
        "MutualCoupling",
        "Node",
        "NumericValue",
        "ParamAssignment",
        "Resistor",
        "SourceSpec",
        "SubcktInstance",
        "Transistor",
        "TransmissionLine",
        "LosslessLine",
        "LossyLine",
        "RcLine",
        "TxlLine",
        "CoupledLine",
        "CodeModelConnection",
        "CodeModelDevice",
        "CodeModelPort",
        "FraProbe",
        "FrequencyAnalyzer",
        "OsdiDevice",
        "SpecialFunction",
        "Cccs",
        "ControlledSource",
        "Ccvs",
        "CurrentSwitch",
        "Switch",
        "Table",
        "TablePoint",
        "Vccs",
        "Vcvs",
        "VoltageSwitch",
        "SubcktReference",
        "Value",
        "VoltageSource",
        "AcDirective",
        "Connection",
        "ExpressionRead",
        "Diagnostic",
        "DiagnosticCode",
        "GlobalDirective",
        "Line",
        "Lines",
        "Net",
        "Netlist",
        "Reference",
        "ReferenceKind",
        "ScopePath",
        "Severity",
        "BodyItem",
        "TopLevelItem",
        "Scope",
        "TopologySignature",
        "TopologyView",
        "DcDirective",
        "DcSweep",
        "Directive",
        "EndsLine",
        "IcDirective",
        "Identifier",
        "MeasureDirective",
        "ModelStatement",
        "NodeCondition",
        "NodesetDirective",
        "OpDirective",
        "OptionItem",
        "OptionsDirective",
        "OutputVector",
        "ParamStatement",
        "SaveDirective",
        "StepDirective",
        "ValueList",
        "SubcktDefinition",
        "TempDirective",
        "TranDirective",
        "Batch",
        "DirectiveEditor",
        "Edit",
        "EditPlan",
        "ParamTable",
        "Placement",
        "SlotCheck",
        "__version__",
        "parse",
    }
    assert set(netlistmod.__all__) == expected
    assert netlistmod.__all__ == sorted(netlistmod.__all__)
    assert len(netlistmod.__all__) == len(expected)
    assert netlistmod.__version__ == version("netlistmod")
    assert all(hasattr(netlistmod, name) for name in expected)
    assert netlistmod.Netlist is netlistmod.edit.Netlist
    assert issubclass(netlistmod.Netlist, netlistmod.document.document.Netlist)


def test_internal_names_do_not_leak() -> None:
    assert not hasattr(netlistmod, "version")
    assert not hasattr(netlistmod, "apply_edits")
    assert not hasattr(netlistmod.document, "Netlist")
    for package in (netlistmod.document, netlistmod.edit, netlistmod.model):
        assert set(package.__all__) <= set(netlistmod.__all__)
    assert netlistmod.grammar.__all__ == []
