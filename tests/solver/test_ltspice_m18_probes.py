"""LTspice 26.1.1 probes for the forms that loaded while LTspice stopped on them (M18 D2, decision 5
of the M18 task list): a `+` line that holds only a comment (which the library loads; review R1),
a special function as a `.model` type, a comma right after `params:`, and the analyzer's `zm`
probe and `.fra` range.

Each probe pairs what LTspice does with what the library reads: `refused` (a `ParseError`),
`loads`, or the diagnostic code it reports. Only syntax facts come out of these runs; nothing
LTspice writes is committed (decision 0009 item 2).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import DiagnosticCode, Dialect, Netlist, ParseError
from tests.support import ngspice
from tests.support.ltspice import run
from tests.support.solvers import Solver

pytestmark = pytest.mark.solver("ltspice")

_FRA_CODES = (DiagnosticCode.FRA_PROBE_IN_IMPEDANCE_MODE, DiagnosticCode.FRA_RANGE_MISSING)


def _reading(text: str, dialect: Dialect = Dialect.LTSPICE) -> str:
    try:
        netlist = Netlist.from_text(text, dialect=dialect)
    except ParseError:
        return "refused"
    codes = [d.code.value for d in netlist.diagnostics if d.code in _FRA_CODES]
    return " ".join(codes) or "loads"


_CONTINUED = "probe\nV1 a 0 1\nR9 a 0 1k\n{body}\n.op\n.end\n"

# (body, LTspice runs it, the library's reading)
_COMMENT_LINES: dict[str, tuple[str, bool, str]] = {
    # LTspice stops on a statement whose last "+" line holds only a comment unless a later "+" line
    # holds a field; the library loads it, the grammar's reading (P13; M18 review R1).
    "end-semicolon": ("R2 a 0 1k\n+ ; note", False, "loads"),
    "end-semicolon-no-blank": ("R2 a 0 1k\n+;note", False, "loads"),
    "end-tab": ("R2 a 0 1k\n+\t;note", False, "loads"),
    "end-dollar": ("R2 a 0 1k\n+ $ note", False, "loads"),
    "end-indented": ("R2 a 0 1k\n  + ; note", False, "loads"),
    "end-then-blank-plus": ("R2 a 0 1k\n+ ; c\n+", False, "loads"),
    "end-two-comments": ("R2 a 0 1k\n+ ; c1\n+ ; c2", False, "loads"),
    "end-after-value-line": ("R2 a 0\n+ 1k\n+ ; note", False, "loads"),
    "end-param": (".param p=1\n+ ; c", False, "loads"),
    "end-model": (".model dd D(Is=1e-14)\n+ ; c\nD1 a 0 dd", False, "loads"),
    "end-untyped": (".backanno\n+ ; c", False, "loads"),
    "end-global": (".global g\n+ ; c", False, "loads"),
    "end-x": ("X1 a s\n+ ; c\n.subckt s p\nR1 p 0 1k\n.ends", False, "loads"),
    "end-b": ("B1 b 0 V=V(a)*2\n+ ; c\nR2 b 0 1k", False, "loads"),
    "end-ends": ("X1 a s\n.subckt s p\nR1 p 0 1k\n.ends\n+ ; c", False, "loads"),
    "end-subckt-params": (
        "X1 a s\n.subckt s p params: r=1k\n+ ; c\nR1 p 0 {r}\n.ends",
        False,
        "loads",
    ),
    # The one form of a comment-only last "+" line that LTspice runs.
    "end-subckt-ports": ("X1 a s\n.subckt s p\n+ ; c\nR1 p 0 1k\n.ends", True, "loads"),
    "mid-before-value": ("R2 a 0\n+ ; note\n+ 1k", True, "loads"),
    "mid-before-param": ("R2 a 0 1k\n+ ; note\n+ tc=0", True, "loads"),
    "mid-two-comments": ("R2 a 0\n+ ; c1\n+ ; c2\n+ 1k", True, "loads"),
    "mid-dollar": ("R2 a 0 1k\n+ $ note\n+ tc=0", True, "loads"),
    "mid-param": (".param p=1\n+ ; c\n+ q=2", True, "loads"),
    "mid-model-paren": (".model dd D(Is=1e-14\n+ ; c\n+ )\nD1 a 0 dd", True, "loads"),
    "end-plus-alone": ("R2 a 0 1k\n+", True, "loads"),
    "end-plus-blanks": ("R2 a 0 1k\n+   ", True, "loads"),
    "same-line": ("R2 a 0 1k ; c", True, "loads"),
}


@pytest.mark.parametrize("case", sorted(_COMMENT_LINES))
def test_comment_only_plus_line_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    body, ltspice_runs, reading = _COMMENT_LINES[case]
    text = _CONTINUED.format(body=body)
    assert run(solver, tmp_path, text).ok is ltspice_runs
    assert _reading(text) == reading


@pytest.mark.solver("ngspice")
@pytest.mark.parametrize(
    "case", ["end-semicolon", "end-dollar", "end-param", "end-model", "end-x", "end-subckt-ports"]
)
def test_ngspice_runs_and_loads_a_comment_only_plus_line(
    solver: Solver, tmp_path: Path, case: str
) -> None:
    text = _CONTINUED.format(body=_COMMENT_LINES[case][0])
    assert ngspice.run(solver, tmp_path, text).ok
    assert _reading(text, Dialect.NGSPICE) == "loads"


_SPECIAL = "probe\nV1 in 0 1\nRin in 0 1k\nRq q 0 1k\n{body}\n.op\n.end\n"
_NODES = "in 0 0 0 0 nq q 0"

_MODELS: dict[str, tuple[str, bool, str]] = {
    **{
        f"alone-{name.lower()}": (f".model x {name}(Vhigh=5)", False, "refused")
        for name in ("BUF", "AND", "OTA", "SCHMITT", "VARISTOR", "DIGITAL")
    },
    "alone-buf-no-parameters": (".model x BUF", False, "refused"),
    "used-buf": (f".model x BUF(Vhigh=5)\nA1 {_NODES} x", False, "refused"),
    "used-lower-case": (f".model x buf(Vhigh=5)\nA1 {_NODES} x", False, "refused"),
    "model-named-buf": (f".model buf D\nA1 {_NODES} buf", True, "loads"),
    # Not a special function: LTspice stops on any type it does not know (a finding of D2).
    "alone-unknown-type": (".model x FOO(a=1)", False, "loads"),
}


@pytest.mark.parametrize("case", sorted(_MODELS))
def test_special_function_model_type_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    body, ltspice_runs, reading = _MODELS[case]
    text = _SPECIAL.format(body=body)
    assert run(solver, tmp_path, text).ok is ltspice_runs
    assert _reading(text) == reading


_SUBCKT = "probe\nV1 a 0 1\n{call}\n.subckt s p n {header}\nR1 p n {{r}}\n.ends\n.op\n.end\n"

_PARAMS: dict[str, tuple[str, str, bool, str]] = {
    "subckt-comma": ("X1 a 0 s", "params:, r=1k", False, "refused"),
    "subckt-comma-no-blank": ("X1 a 0 s", "params:,r=1k", False, "refused"),
    "subckt-blank-comma": ("X1 a 0 s", "params: , r=1k", False, "refused"),
    "subckt-plus-comma": ("X1 a 0 s", "params:\n+ , r=1k", False, "refused"),
    "x-comma": ("X1 a 0 s params:, r=2k", "r=1k", False, "refused"),
    "x-comma-no-blank": ("X1 a 0 s params:,r=2k", "r=1k", False, "refused"),
    "x-blank-comma": ("X1 a 0 s params: , r=2k", "r=1k", False, "refused"),
    "subckt-params": ("X1 a 0 s", "params: r=1k", True, "loads"),
    "subckt-params-comma-later": ("X1 a 0 s", "params: r=1k, q=2", True, "loads"),
    "x-params": ("X1 a 0 s params: r=2k", "r=1k", True, "loads"),
    # A comma before params: runs, and the library refuses it (discrepancies.md; review R2 of D2).
    "subckt-comma-before-params": ("X1 a 0 s", ", params: r=1k", True, "refused"),
}


@pytest.mark.parametrize("case", sorted(_PARAMS))
def test_comma_after_params_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    call, header, ltspice_runs, reading = _PARAMS[case]
    text = _SUBCKT.format(call=call, header=header)
    assert run(solver, tmp_path, text).ok is ltspice_runs
    assert _reading(text) == reading


_LOOP = (
    "probe\nV1 a 0 0 AC 1\nR1 a b 1k\nE1 c 0 b 0 -10\nR2 c d 10k\n{analyzer}\n&1 d 0 b 0\n"
    "C1 b d 1n\n{analysis}\n.end\n"
)
_TIMING = " oct=1 tavgmin=0.5m tsettle=0.2m"

_RANGES: dict[str, tuple[str, str, bool, str]] = {
    "fra-none": (f"@1 d b{_TIMING}", ".fra", False, "FRA_RANGE_MISSING"),
    "fra-fstart": (f"@1 d b fstart=1k{_TIMING}", ".fra", False, "FRA_RANGE_MISSING"),
    "fra-fend": (f"@1 d b fend=4k{_TIMING}", ".fra", False, "FRA_RANGE_MISSING"),
    "fra-flist": (f"@1 d b flist=1k 2k{_TIMING}", ".fra", False, "FRA_RANGE_MISSING"),
    "fra-flist-fstart": (
        f"@1 d b flist=1k 2k fstart=1k{_TIMING}",
        ".fra",
        False,
        "FRA_RANGE_MISSING",
    ),
    "fra-range": (f"@1 d b fstart=1k fend=4k{_TIMING}", ".fra", True, "loads"),
    "fra-flist-range": (f"@1 d b flist=1k 2k fstart=1k fend=4k{_TIMING}", ".fra", True, "loads"),
    "fra-second-without-range": (
        f"@1 d b fstart=1k fend=4k{_TIMING}\n@2 d b{_TIMING}",
        ".fra",
        False,
        "FRA_RANGE_MISSING",
    ),
    "fra-second-disabled": (
        f"@1 d b fstart=1k fend=4k{_TIMING}\n@2 d b enabled=0{_TIMING}",
        ".fra",
        True,
        "loads",
    ),
    "op-none": (f"@1 d b{_TIMING}", ".op", True, "loads"),
    "op-flist": (f"@1 d b flist=1k 2k{_TIMING}", ".op", True, "loads"),
}


@pytest.mark.parametrize("case", sorted(_RANGES))
def test_fra_range_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    analyzer, analysis, ltspice_runs, reading = _RANGES[case]
    text = _LOOP.format(analyzer=analyzer, analysis=analysis)
    assert run(solver, tmp_path, text).ok is ltspice_runs
    assert _reading(text) == reading


_ZM = "probe\nV1 a 0 0 AC 1\nR1 a b 1k\nR2 b 0 1k\n{body}\n.op\n.end\n"

_PROBES: dict[str, tuple[str, bool, str]] = {
    "zm-probe": ("@1 a b zm fstart=1k fend=4k\n&1 b 0 a 0", False, "FRA_PROBE_IN_IMPEDANCE_MODE"),
    "zm-probe-only-analyzer": (
        "@1 a b zm fstart=1k fend=4k\n&2 b 0 a 0",
        False,
        "FRA_PROBE_IN_IMPEDANCE_MODE",
    ),
    "zm-probe-by-suffix": (
        "@1 a b zm fstart=1k fend=4k\n@2 a b\n&1 b 0 a 0",
        False,
        "FRA_PROBE_IN_IMPEDANCE_MODE",
    ),
    "plain-probe-by-suffix": ("@1 a b zm fstart=1k fend=4k\n@2 a b\n&2 b 0 a 0", True, "loads"),
    "zm-without-probe": ("@1 a b zm fstart=1k fend=4k", True, "loads"),
}


@pytest.mark.parametrize("case", sorted(_PROBES))
def test_zm_probe_probes(solver: Solver, tmp_path: Path, case: str) -> None:
    body, ltspice_runs, reading = _PROBES[case]
    text = _ZM.format(body=body)
    result = run(solver, tmp_path, text)
    assert result.ok is ltspice_runs
    if not ltspice_runs:
        assert "FRA Probe not supported" in result.log
    assert _reading(text) == reading
