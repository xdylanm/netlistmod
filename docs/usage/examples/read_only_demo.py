"""Read-only use of netlistmod (M5 checkpoint): load a KiCad export and print what it holds.

Run from the repository root::

    uv run --env-file .env python docs/usage/examples/read_only_demo.py [netlist.cir]

Without an argument it loads ``tests/corpus/ngspice/kicad_basic/dc_basic_r_divider.cir``,
whose values use RKM notation (``1k0``), so it is parsed with ``rkm=True``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from netlistmod import Dialect, Netlist

CORPUS = Path(__file__).parents[3] / "tests" / "corpus" / "ngspice"
DEFAULT = CORPUS / "kicad_basic" / "dc_basic_r_divider.cir"


def main(path: Path) -> None:
    """Print the elements, nets, connections, references and diagnostics of ``path``."""
    netlist = Netlist.load(path, dialect=Dialect.NGSPICE, rkm=True)
    print(f"{path.name}: {len(netlist.lines)} lines")
    for scope in netlist.scopes:
        print(f"\n[{scope.describe()}]")
        print("elements:")
        for element in netlist.elements(scope.path):
            value = getattr(element, "value", None) or getattr(element, "dc", None)
            text = f" {value.text}" if value is not None else ""
            nodes = " ".join(node.name for node in element.nodes)
            print(f"  {element.designator} ({type(element).__name__}) {nodes}{text}")
        print("nets:")
        for net in netlist.nets(scope.path):
            on = ", ".join(e.designator for e in netlist.elements_on_net(net, scope.path))
            shared = " (shared)" if net.global_ else ""
            print(f"  {net.name}{shared}: {on}  spelled {', '.join(net.spellings)}")
        print("connections:")
        for element in netlist.elements(scope.path):
            terminals = ", ".join(
                f"{c.terminal}->{c.net.name}"
                for c in netlist.connections(element.designator, scope.path)
            )
            print(f"  {element.designator}: {terminals}")
    print("\nreferences:")
    for reference in netlist.references:
        target = type(reference.target).__name__ if reference.target is not None else "UNRESOLVED"
        print(f"  {reference.kind} {reference.name!r} in {reference.scope} -> {target}")
    print("\ndiagnostics:")
    for diagnostic in netlist.diagnostics:
        print(
            f"  {diagnostic.line}:{diagnostic.column} {diagnostic.severity} "
            f"{diagnostic.code.value}: {diagnostic.message}"
        )
    print(f"\nsignature {netlist.signature().digest()[:16]}...")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT)
