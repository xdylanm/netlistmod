"""Read-only use of netlistmod: load a netlist and print what it holds.

Run it from the root of a clone, or give it a netlist::

    uv run --env-file .env python docs/usage/examples/read_only_demo.py
    uv run --env-file .env python docs/usage/examples/read_only_demo.py my.net --dialect ltspice

Without a netlist it loads the clone's KiCad export
``tests/corpus/ngspice/kicad_basic/dc_basic_r_divider.cir``. Its values use RKM notation
(``1k0``), so on ngspice it is loaded with ``rkm=True``.

``--rkm`` accepts ngspice values such as ``2k7`` in your own netlist. LTspice reads them without
an option, so ``--rkm`` is refused with ``--dialect ltspice``. A netlist the library refuses
prints the error, and the script exits with status 1.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from netlistmod import Dialect, Netlist, SpiceNetlistError

CORPUS = Path(__file__).parents[3] / "tests" / "corpus" / "ngspice"
DEFAULT = CORPUS / "kicad_basic" / "dc_basic_r_divider.cir"


def main(path: Path, dialect: Dialect = Dialect.NGSPICE, *, rkm: bool = False) -> None:
    """Print the elements, nets, connections, references and diagnostics of ``path``."""
    netlist = Netlist.load(path, dialect=dialect, rkm=rkm)
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
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("netlist", nargs="?", type=Path, help="default: the clone's KiCad export")
    parser.add_argument(
        "--dialect", choices=[d.value for d in Dialect], default=Dialect.NGSPICE.value
    )
    parser.add_argument("--rkm", action="store_true", help="accept ngspice RKM values such as 2k7")
    args = parser.parse_args()
    dialect = Dialect(args.dialect)
    if args.rkm and dialect is not Dialect.NGSPICE:
        parser.error("--rkm applies only to ngspice: LTspice reads RKM values without it")
    path = args.netlist
    rkm = args.rkm
    if path is None:
        if not DEFAULT.exists():
            parser.error(f"{DEFAULT} is not here: run from a clone, or give a netlist")
        path = DEFAULT
        rkm = dialect is Dialect.NGSPICE
    try:
        main(path, dialect, rkm=rkm)
    except SpiceNetlistError as error:
        sys.exit(f"{path}: {error}")
