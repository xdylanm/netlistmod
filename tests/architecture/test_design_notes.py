"""The living design notes name every public name, so they cannot drift silently (decision 0010)."""

from __future__ import annotations

import dataclasses
import inspect
import re
from pathlib import Path

import pytest

import netlistmod
from netlistmod import DiagnosticCode

DESIGN = Path(__file__).parents[2] / "docs" / "design"
NOTES = ["elements.md", "statements.md", "document-layer.md", "edit-layer.md"]
PUBLIC = [name for name in netlistmod.__all__ if name != "__version__"]


def _words() -> set[str]:
    text = "\n".join((DESIGN / name).read_text(encoding="utf-8") for name in NOTES)
    return set(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", text))


WORDS = _words()


@pytest.mark.parametrize("name", PUBLIC)
def test_public_name_is_in_a_note(name: str) -> None:
    assert name in WORDS


@pytest.mark.parametrize(
    ("owner", "field"),
    [
        (name, field.name)
        for name in PUBLIC
        if inspect.isclass(getattr(netlistmod, name))
        and dataclasses.is_dataclass(getattr(netlistmod, name))
        for field in dataclasses.fields(getattr(netlistmod, name))
    ],
)
def test_public_field_is_in_a_note(owner: str, field: str) -> None:
    assert field in WORDS, f"{owner}.{field}"


@pytest.mark.parametrize("code", [code.name for code in DiagnosticCode])
def test_diagnostic_code_is_in_a_note(code: str) -> None:
    assert code in WORDS
