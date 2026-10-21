from __future__ import annotations

import pytest

from netlistmod import Dialect


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("ngspice", Dialect.NGSPICE),
        ("NGSPICE", Dialect.NGSPICE),
        ("NgSpIcE", Dialect.NGSPICE),
        ("ltspice", Dialect.LTSPICE),
        ("LTSPICE", Dialect.LTSPICE),
        ("LTspice", Dialect.LTSPICE),
    ],
)
def test_dialect_from_name(name: str, expected: Dialect) -> None:
    assert Dialect.from_name(name) is expected


def test_dialect_display_names() -> None:
    assert Dialect.NGSPICE.display_name == "ngspice"
    assert Dialect.LTSPICE.display_name == "LTspice"


def test_unknown_dialect_lists_valid_names() -> None:
    with pytest.raises(ValueError, match=r"valid names are: ngspice, ltspice"):
        Dialect.from_name("unknown")
