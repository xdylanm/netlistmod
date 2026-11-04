"""The phase 2 compatibility rule: a netlist that parses keeps its topology signature and digest.

``signature_snapshot.json`` was generated at the start of M11, before any phase 2 grammar. It holds
the digest of every corpus netlist that parsed then, so saved digests stay valid. A new corpus file
needs no entry. Changing an entry is a deliberate act that needs a decision record:
``python -m tests.document.test_signature_snapshot``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from netlistmod import Dialect, Netlist, ParseError, UnsupportedConstruct

CORPUS = Path(__file__).parents[1] / "corpus"
SNAPSHOT = Path(__file__).with_name("signature_snapshot.json")
NETLIST_SUFFIXES = {".cir", ".net", ".sp"}
# ngspice has the RKM option; LTspice reads RKM values without one and refuses the option.
_MODES = {Dialect.NGSPICE: (False, True), Dialect.LTSPICE: (False,)}


def _digest(path: Path, dialect: Dialect, *, rkm: bool) -> str | None:
    try:
        return Netlist.load(path, dialect=dialect, rkm=rkm).signature().digest()
    except (ParseError, UnsupportedConstruct):
        return None


def _key(path: Path, rkm: bool) -> str:
    return f"{path.relative_to(CORPUS).as_posix()}{' rkm' if rkm else ''}"


def _snapshot() -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for dialect, modes in _MODES.items():
        for path in sorted((CORPUS / dialect.value).rglob("*")):
            if path.suffix.lower() in NETLIST_SUFFIXES and "solver_stubs" not in path.parts:
                for rkm in modes:
                    digest = _digest(path, dialect, rkm=rkm)
                    if digest is not None:
                        snapshot[_key(path, rkm)] = digest
    return snapshot


RECORDED: dict[str, str] = json.loads(SNAPSHOT.read_text(encoding="utf-8"))


@pytest.mark.parametrize("key", sorted(RECORDED))
def test_a_recorded_netlist_keeps_its_digest(key: str) -> None:
    name, _, mode = key.partition(" ")
    path = CORPUS / name
    dialect = Dialect(Path(name).parts[0])
    assert _digest(path, dialect, rkm=mode == "rkm") == RECORDED[key]


if __name__ == "__main__":
    SNAPSHOT.write_text(json.dumps(_snapshot(), indent=1, sort_keys=True) + "\n", encoding="utf-8")
