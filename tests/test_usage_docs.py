"""Usage guides with doctest examples are executed (architecture §14)."""

from __future__ import annotations

import doctest
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest

from netlistmod import Dialect, Netlist
from tests.support.solvers import Solver

ROOT = Path(__file__).parents[1]
USAGE = ROOT / "docs" / "usage"
EXECUTED = [
    ROOT / "README.md",
    *(
        USAGE / name
        for name in (
            "structural-parse.md",
            "elements.md",
            "statements.md",
            "document.md",
            "editing.md",
            "errors.md",
        )
    ),
]


@pytest.mark.parametrize("path", EXECUTED, ids=lambda path: path.name)
def test_usage_guide_examples_run(path: Path) -> None:
    result = doctest.testfile(str(path), module_relative=False, encoding="utf-8")
    assert result.attempted > 0
    assert result.failed == 0


def test_read_only_demo_runs(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    demo = USAGE / "examples" / "read_only_demo.py"
    monkeypatch.setattr(sys, "argv", [str(demo)])
    runpy.run_path(str(demo), run_name="__main__")
    output = capsys.readouterr().out
    assert "dc_basic_r_divider.cir: 5 lines" in output
    assert "  /vin: V1, R1  spelled /vin" in output
    assert "  R1: 0->/vin, 1->/vout" in output
    assert "DIALECT_GATED_SYNTAX" in output


def _run_read_only_demo(monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
    demo = USAGE / "examples" / "read_only_demo.py"
    monkeypatch.setattr(sys, "argv", [str(demo), *args])
    runpy.run_path(str(demo), run_name="__main__")


def test_read_only_demo_help(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(SystemExit) as exit_:
        _run_read_only_demo(monkeypatch, "--help")
    assert exit_.value.code == 0
    assert "--dialect {ngspice,ltspice}" in capsys.readouterr().out


def test_read_only_demo_takes_a_dialect_and_a_path(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "lt.net"
    path.write_bytes(b"t\nV1 a 0 3\nR1 a 0 2k2\n.end\n")
    _run_read_only_demo(monkeypatch, str(path), "--dialect", "ltspice")
    assert "  R1 (Resistor) a 0 2k2" in capsys.readouterr().out


def test_read_only_demo_needs_rkm_for_an_rkm_path(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "rkm.cir"
    path.write_bytes(b"t\nV1 a 0 3\nR1 a 0 2k7\n.end\n")
    with pytest.raises(SystemExit) as exit_:
        _run_read_only_demo(monkeypatch, str(path))
    assert "`2k7` is RKM notation" in str(exit_.value.code)
    _run_read_only_demo(monkeypatch, str(path), "--rkm")
    assert "  R1 (Resistor) a 0 2k7" in capsys.readouterr().out


def test_read_only_demo_refuses_rkm_on_ltspice(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(SystemExit) as exit_:
        _run_read_only_demo(monkeypatch, "--dialect", "ltspice", "--rkm")
    assert exit_.value.code == 2
    assert "--rkm applies only to ngspice" in capsys.readouterr().err


def _demo() -> dict[str, Any]:
    return runpy.run_path(str(USAGE / "examples" / "edit_and_simulate.py"), run_name="demo")


@pytest.mark.parametrize("dialect", list(Dialect))
def test_edit_demo_saves_a_minimal_diff(dialect: Dialect, tmp_path: Path) -> None:
    demo = _demo()
    netlist = Netlist.from_text(demo["TEXT"], dialect=dialect)
    (_, before), (_, after) = demo["versions"](netlist, ("R2", "3k"))
    before.save(tmp_path / "before.cir")
    after.save(tmp_path / "after.cir")
    assert (tmp_path / "after.cir").read_bytes() == (tmp_path / "before.cir").read_bytes().replace(
        b"R2 out 0 1k", b"R2 out 0 3k"
    )


@pytest.mark.parametrize("dialect", list(Dialect))
def test_edit_demo_adds_op_only_if_missing(dialect: Dialect) -> None:
    with_op = _demo()["with_op"]
    bare = Netlist.from_text("t\nR1 a 0 1k\n.end\n", dialect=dialect)
    assert with_op(bare).text == "t\nR1 a 0 1k\n.op\n.end\n"
    written = Netlist.from_text("t\nR1 a 0 1k\n.OP\n.end\n", dialect=dialect)
    assert with_op(written).text == written.text


@pytest.mark.parametrize("dialect", list(Dialect))
@pytest.mark.parametrize(
    ("line", "found"),
    [
        (".tran 1u 1m", ".tran"),
        (".ac dec 10 1 1k", ".ac"),
        (".dc V1 0 1 1", ".dc"),
        (".NOISE v(a) V1 dec 10 1 1k", ".noise"),
        (".tf v(a) V1", ".tf"),
    ],
)
def test_edit_demo_refuses_another_analysis(
    dialect: Dialect, line: str, found: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "other.cir"
    path.write_bytes(f"t\nV1 a 0 1\nR1 a 0 1k\n{line}\n.end\n".encode())
    assert _demo()["main"](dialect, path, None, "a") == 1
    assert f"line 4: this script runs only .op, and found {found}" in capsys.readouterr().err


def test_edit_demo_refuses_a_step(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "step.net"
    path.write_bytes(b"t\nV1 a 0 1\nR1 a 0 1k\n.step param x 1 2 1\n.end\n")
    assert _demo()["main"](Dialect.LTSPICE, path, None, "a") == 1
    assert "found .step" in capsys.readouterr().err


def test_edit_demo_refuses_a_control_block(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "control.cir"
    path.write_bytes(b"t\nR1 a 0 1k\n.control\nrun\n.endc\n.end\n")
    assert _demo()["main"](Dialect.NGSPICE, path, None, "a") == 1
    assert "found .control block" in capsys.readouterr().err


def test_edit_demo_finds_a_net_in_any_spelling() -> None:
    demo = _demo()
    netlist = Netlist.from_text("t\nR1 /OUT_A GND 1k\n.end\n", dialect=Dialect.NGSPICE)
    assert demo["find_net"](netlist, "/out_a").name == "/out_a"
    assert demo["find_net"](netlist, "/OUT_A").name == "/out_a"
    assert demo["find_net"](netlist, "gnd").name == "0"
    with pytest.raises(demo["DemoError"], match=r"no net 'x' .*/OUT_A, GND"):
        demo["find_net"](netlist, "x")


def test_edit_demo_reports_a_library_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "t.cir"
    path.write_bytes(b"t\nR1 a 0 1k\n.end\n")
    assert _demo()["main"](Dialect.NGSPICE, path, ("R9", "3k"), "a") == 1
    assert "no element `R9`" in capsys.readouterr().err
    assert path.read_bytes() == b"t\nR1 a 0 1k\n.end\n"


def test_edit_demo_needs_a_probe_with_a_netlist(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _demo()["main"](Dialect.NGSPICE, tmp_path / "t.cir") == 1
    assert "needs --probe" in capsys.readouterr().err


def test_edit_demo_says_when_ngspice_may_misread_rkm(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "rkm.cir"
    path.write_bytes(b"t\nR1 a 0 2k7\n.end\n")
    # The unknown probe stops it before any solver runs.
    assert _demo()["main"](Dialect.NGSPICE, path, None, "x", rkm=True) == 1
    assert "`2k7` is RKM notation" in capsys.readouterr().err


@pytest.mark.parametrize(
    "dialect",
    [
        pytest.param(Dialect.NGSPICE, marks=pytest.mark.solver("ngspice")),
        pytest.param(Dialect.LTSPICE, marks=pytest.mark.solver("ltspice")),
    ],
)
def test_edit_demo_runs_the_solver(
    dialect: Dialect,
    solver: Solver,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(f"{solver.name.upper()}_EXE", str(solver.path))
    assert _demo()["main"](dialect) == 0
    output = capsys.readouterr().out
    assert "R2=1k: v(out) = 1.5000 V" in output
    assert "R2=3k: v(out) = 2.2500 V" in output


@pytest.mark.parametrize(
    "dialect",
    [
        pytest.param(Dialect.NGSPICE, marks=pytest.mark.solver("ngspice")),
        pytest.param(Dialect.LTSPICE, marks=pytest.mark.solver("ltspice")),
    ],
)
def test_edit_demo_runs_a_netlist_from_a_file(
    dialect: Dialect,
    solver: Solver,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(f"{solver.name.upper()}_EXE", str(solver.path))
    original = b"t\n.include lib/r.lib\nV1 in 0 DC 3\nX1 in Out rr\nR2 Out 0 1k\n.end\n"
    path = tmp_path / "divider.cir"
    path.write_bytes(original)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "r.lib").write_bytes(b".subckt rr a b\nR1 a b 1k\n.ends\n")
    assert _demo()["main"](dialect, path, ("R2", "3k"), "out") == 0
    output = capsys.readouterr().out
    assert "R2=1k: v(out) = 1.5000 V" in output
    assert "R2=3k: v(out) = 2.2500 V" in output
    assert path.read_bytes() == original
    assert sorted(item.name for item in tmp_path.iterdir()) == ["divider.cir", "lib"]


@pytest.mark.parametrize(
    "dialect",
    [
        pytest.param(Dialect.NGSPICE, marks=pytest.mark.solver("ngspice")),
        pytest.param(Dialect.LTSPICE, marks=pytest.mark.solver("ltspice")),
    ],
)
def test_edit_demo_reports_a_solver_failure(
    dialect: Dialect,
    solver: Solver,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(f"{solver.name.upper()}_EXE", str(solver.path))
    path = tmp_path / "missing.cir"
    path.write_bytes(b"t\n.include missing.lib\nV1 in 0 DC 3\nR2 in 0 1k\n.end\n")
    assert _demo()["main"](dialect, path, None, "in") == 1
    assert "the solver failed" in capsys.readouterr().err
    assert [item.name for item in tmp_path.iterdir()] == ["missing.cir"]
