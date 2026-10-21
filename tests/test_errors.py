from __future__ import annotations

import ast
from pathlib import Path

import netlistmod.errors as errors


def test_error_hierarchy_and_parse_error_format() -> None:
    assert issubclass(errors.ParseError, errors.SpiceNetlistError)
    assert issubclass(errors.UnsupportedConstruct, errors.SpiceNetlistError)
    assert issubclass(errors.EditError, errors.SpiceNetlistError)
    assert issubclass(errors.TopologyError, errors.SpiceNetlistError)
    assert issubclass(errors.TopologyViolation, errors.SpiceNetlistError)
    assert issubclass(errors.EncodingError, errors.SpiceNetlistError)

    error = errors.ParseError(2, 4, "R1 in out 1k\n   ^")
    assert error.line == 2
    assert error.column == 4
    assert error.excerpt == "R1 in out 1k\n   ^"
    assert str(error) == "Parse error at line 2, column 4:\nR1 in out 1k\n   ^"


def test_errors_module_has_no_package_imports() -> None:
    path = Path(errors.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(not alias.name.startswith("netlistmod") for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("netlistmod")
