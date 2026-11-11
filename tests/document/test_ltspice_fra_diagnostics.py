"""The LTspice frequency response analyzer diagnostics (M18 D2, decision 5 of the M18 task list):
a probe for an analyzer in `zm` mode, and an analyzer with no frequency range under `.fra`.

LTspice 26.1.1 stops on both; the solver probes are in tests/solver/test_ltspice_m18_probes.py.
"""

from __future__ import annotations

import pytest

from netlistmod import Diagnostic, DiagnosticCode, Dialect, Netlist

_BASE = "t\nV1 a 0 0 AC 1\nR1 a b 1k\nR2 b 0 1k\n{body}\n.end\n"
_ZM = DiagnosticCode.FRA_PROBE_IN_IMPEDANCE_MODE
_RANGE = DiagnosticCode.FRA_RANGE_MISSING


def _found(body: str, code: DiagnosticCode, dialect: Dialect = Dialect.LTSPICE) -> list[Diagnostic]:
    netlist = Netlist.from_text(_BASE.format(body=body), dialect=dialect)
    return [d for d in netlist.diagnostics if d.code is code]


# (body, the line of the probe the warning is on, or None when it does not fire)
_PROBES: dict[str, tuple[str, int | None]] = {
    "zm": ("@1 a b zm\n&1 b 0 a 0", 6),
    "zm-upper-with-range": ("@1 a b fstart=1k fend=4k ZM\n&1 b 0 a 0", 6),
    "only-analyzer": ("@1 a b zm\n&2 b 0 a 0", 6),
    "two-matching-zm": ("@1 a b zm\n@2 a b\n&1 b 0 a 0", 7),
    "two-matching-plain": ("@1 a b zm\n@2 a b\n&2 b 0 a 0", None),
    "two-no-match": ("@1 a b zm\n@2 a b\n&3 b 0 a 0", None),
    "plain": ("@1 a b\n&1 b 0 a 0", None),
    "zm-without-probe": ("@1 a b zm", None),
    "probe-in-other-scope": ("@1 a b zm\nX1 a b s\n.subckt s p q\n&1 p 0 q 0\n.ends", None),
    "both-in-subckt": ("X1 a b s\n.subckt s p q\n@1 p q zm\n&1 q 0 p 0\n.ends", 8),
}


@pytest.mark.parametrize("case", sorted(_PROBES))
def test_a_probe_for_an_analyzer_in_zm_mode_is_a_warning(case: str) -> None:
    body, line = _PROBES[case]
    found = _found(body, _ZM)
    if line is None:
        assert found == []
        return
    (diagnostic,) = found
    assert (diagnostic.severity, diagnostic.line, diagnostic.column) == ("warning", line, 1)
    assert "stops on a probe in that mode" in diagnostic.message
    assert diagnostic.message.startswith("`&")


# (body, the missing parameters named, or None when it does not fire)
_RANGES: dict[str, tuple[str, str | None]] = {
    "none": ("@1 a b\n.fra", "`fstart=` and no `fend=`"),
    "fstart-only": ("@1 a b fstart=1k\n.fra", "`fend=`;"),
    "fend-only": ("@1 a b fend=4k\n.fra", "`fstart=`;"),
    "flist": ("@1 a b flist=1k 2k\n.fra", "`fstart=` and no `fend=`"),
    "flist-fstart": ("@1 a b flist=1k 2k fstart=1k\n.fra", "`fend=`;"),
    "upper-case-command": ("@1 a b\n.FRA", "`fstart=` and no `fend=`"),
    "in-a-subcircuit": ("X1 a b s\n.subckt s p q\n@1 p q\n.ends\n.fra", "`fstart=`"),
    "range": ("@1 a b fstart=1k fend=4k\n.fra", None),
    "range-upper-names": ("@1 a b FSTART=1k Fend=4k\n.fra", None),
    "flist-and-range": ("@1 a b flist=1k 2k fstart=1k fend=4k\n.fra", None),
    "enabled-given": ("@1 a b enabled=0\n.fra", None),
    "no-fra": ("@1 a b\n.op", None),
}


@pytest.mark.parametrize("case", sorted(_RANGES))
def test_an_analyzer_with_no_range_under_fra_is_a_warning(case: str) -> None:
    body, missing = _RANGES[case]
    found = _found(body, _RANGE)
    if missing is None:
        assert found == []
        return
    (diagnostic,) = found
    assert diagnostic.severity == "warning"
    assert diagnostic.column == 1
    assert diagnostic.message.startswith("`@1` has no ")
    assert missing in diagnostic.message
    assert '("Missing parameter")' in diagnostic.message


def test_each_analyzer_gets_its_own_range_warning() -> None:
    found = _found("@1 a b fstart=1k fend=4k\n@2 a b\n@3 a b fend=1k\n.fra", _RANGE)
    assert [d.message.split("`")[1] for d in found] == ["@2", "@3"]
    assert [d.line for d in found] == [6, 7]


def test_the_two_warnings_together_are_in_source_order() -> None:
    netlist = Netlist.from_text(
        _BASE.format(body="@1 a b zm\n&1 b 0 a 0\n.fra"), dialect=Dialect.LTSPICE
    )
    fra = [d.code for d in netlist.diagnostics if d.code in (_ZM, _RANGE)]
    assert fra == [_RANGE, _ZM]
