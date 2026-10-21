from __future__ import annotations

import importlib
import pkgutil

import netlistmod


def test_package_and_subpackages_import() -> None:
    names = [
        module.name for module in pkgutil.walk_packages(netlistmod.__path__, prefix="netlistmod.")
    ]
    assert "netlistmod.source" in names

    for name in names:
        importlib.import_module(name)
