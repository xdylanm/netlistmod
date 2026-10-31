from __future__ import annotations

import importlib
import pkgutil
from importlib.metadata import version

import netlistmod


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
        "Diode",
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
        "SubcktInstance",
        "SubcktReference",
        "Value",
        "VoltageSource",
        "__version__",
        "parse",
    }
    assert set(netlistmod.__all__) == expected
    assert netlistmod.__version__ == version("netlistmod")
    assert all(hasattr(netlistmod, name) for name in expected)
