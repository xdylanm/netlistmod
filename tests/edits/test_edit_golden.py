"""Golden-diff edit tests (M6 T8, T4 tier): input + operations → expected bytes."""

from __future__ import annotations

import difflib
from typing import Any

import pytest

from netlistmod import Dialect, Netlist
from tests.edits.golden import FAMILY, manifest, run_case

CASES: dict[str, dict[str, Any]] = manifest()["cases"]


def _diff(expected: bytes, actual: bytes) -> str:
    lines = difflib.unified_diff(
        expected.decode("utf-8").splitlines(keepends=True),
        actual.decode("utf-8").splitlines(keepends=True),
        "expected",
        "actual",
    )
    return "".join(repr(line) + "\n" for line in lines)


@pytest.mark.parametrize("name", sorted(CASES))
def test_golden_case(name: str) -> None:
    case = CASES[name]
    expected = (FAMILY / case["expected"]).read_bytes()
    actual = run_case(case).to_bytes()
    assert actual == expected, f"golden case {name} differs:\n{_diff(expected, actual)}"


@pytest.mark.parametrize("name", sorted(CASES))
def test_golden_output_keeps_the_input_topology(name: str) -> None:
    case = CASES[name]
    original = Netlist.load(FAMILY / case["input"], dialect=Dialect.NGSPICE)
    expected = Netlist.load(FAMILY / case["expected"], dialect=Dialect.NGSPICE)
    assert expected.signature() == original.signature()


def test_every_input_is_used_and_round_trips() -> None:
    inputs = {case["input"] for case in CASES.values()}
    expected = {case["expected"] for case in CASES.values()}
    files = {path.name for path in FAMILY.glob("*.cir")}
    assert inputs | expected == files
    for name in inputs:
        assert (
            Netlist.load(FAMILY / name, dialect=Dialect.NGSPICE).to_bytes()
            == (FAMILY / name).read_bytes()
        )


def test_the_cases_cover_every_operation() -> None:
    operations: set[str] = set()
    for case in CASES.values():
        for step in case["steps"]:
            steps = step[1] if step[0] == "batch" else [step]
            operations.update(inner[0] for inner in steps)
    assert operations >= {
        "set_value",
        "set_formula",
        "set_param",
        "set_model",
        "set_dc",
        "set_ac",
        "set_coupling",
        "set_instance_param",
        "set_model_param",
        "params.set",
        "directives.add",
        "directives.replace",
        "directives.remove",
        "directives.set",
        "add_include",
    }
