"""Documentation checks: relative links resolve, and the error reference is complete (M9)."""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

import netlistmod
from netlistmod import DiagnosticCode, SpiceNetlistError

ROOT = Path(__file__).parents[1]
DOCUMENTS = sorted(
    path
    for path in [*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md")]
    if "prototype" not in path.parts
)
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
ERRORS = (ROOT / "docs" / "usage" / "errors.md").read_text(encoding="utf-8")
EXCEPTIONS = [
    name
    for name in netlistmod.__all__
    if inspect.isclass(getattr(netlistmod, name))
    and issubclass(getattr(netlistmod, name), SpiceNetlistError)
]


@pytest.mark.parametrize("document", DOCUMENTS, ids=lambda path: path.relative_to(ROOT).as_posix())
def test_relative_links_resolve(document: Path) -> None:
    text = FENCE.sub("", document.read_text(encoding="utf-8"))
    missing = [
        target
        for target in LINK.findall(text)
        if not re.match(r"[a-z]+:|#", target)
        and not (document.parent / target.split("#")[0]).exists()
    ]
    assert not missing


@pytest.mark.parametrize("name", [*EXCEPTIONS, *(code.name for code in DiagnosticCode)])
def test_error_reference_has_an_entry(name: str) -> None:
    assert f"### `{name}`" in ERRORS
