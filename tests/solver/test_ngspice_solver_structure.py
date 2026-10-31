from __future__ import annotations

import re
from pathlib import Path

import pytest

from netlistmod import (
    Dialect,
    ParamStatement,
    ParseError,
    SourceText,
    Span,
    Title,
    UnsupportedConstruct,
    parse,
)
from tests.support.solvers import Solver, run_ngspice

pytestmark = pytest.mark.solver("ngspice")

_CIRCUIT = "probe circuit\nV1 in 0 DC 2\nR1 in 0 1k\n.op\n.print op v(in)\n.end\n"


def _run(solver: Solver, tmp_path: Path, text: str) -> tuple[int, str]:
    netlist = tmp_path / "probe.cir"
    netlist.write_bytes(text.encode("utf-8"))
    result = run_ngspice(solver, netlist)
    return result.returncode, (tmp_path / "ngspice.log").read_text(encoding="utf-8")


def _assert_parser_rejects(text: str) -> None:
    with pytest.raises((ParseError, UnsupportedConstruct)):
        parse(SourceText(text), Dialect.NGSPICE)


def _voltage(log: str) -> str:
    match = re.search(r"(?m)^\s*in\s+([-+0-9.eE]+)\s*$", log)
    assert match is not None, log
    return match.group(1)


def test_missing_end_is_solver_leniency_rejected_by_parser(solver: Solver, tmp_path: Path) -> None:
    text = _CIRCUIT.removesuffix(".end\n")
    code, _ = _run(solver, tmp_path, text)
    assert code == 0
    _assert_parser_rejects(text)


def test_element_after_end_is_ignored_by_solver_rejected_by_parser(
    solver: Solver, tmp_path: Path
) -> None:
    text = _CIRCUIT + "R2 in 0 2k\n"
    code, log = _run(solver, tmp_path, text)
    assert code == 0
    assert "Circuit: probe circuit" in log
    _assert_parser_rejects(text)


def test_control_block_after_end_runs_but_parser_rejects(solver: Solver, tmp_path: Path) -> None:
    text = _CIRCUIT + ".control\nop\n.endc\n"
    code, log = _run(solver, tmp_path, text)
    assert code == 0
    assert "Circuit: probe circuit" in log
    _assert_parser_rejects(text)


def test_continuation_across_comment_and_blank_is_solver_leniency(
    solver: Solver, tmp_path: Path
) -> None:
    ordinary = _CIRCUIT
    split = _CIRCUIT.replace(
        "V1 in 0 DC 2",
        "V1 in 0\n* continuation comment\n\n+ DC 2",
    )
    ordinary_code, ordinary_log = _run(solver, tmp_path, ordinary)
    split_code, split_log = _run(solver, tmp_path, split)
    assert ordinary_code == split_code == 0
    assert float(_voltage(ordinary_log)) == pytest.approx(2.0)
    assert float(_voltage(split_log)) == pytest.approx(2.0)
    _assert_parser_rejects(split)


@pytest.mark.parametrize(
    ("statement", "files"),
    [
        (".include sub/v.inc\n+ sub/w.inc", ("v.inc", "w.inc")),
        (".lib sub/l.lib\n+ sec", ("l.lib",)),
    ],
)
def test_include_and_lib_continuation_fails_in_both(
    solver: Solver, tmp_path: Path, statement: str, files: tuple[str, ...]
) -> None:
    contents = {
        "v.inc": "V1 in 0 DC 2\n",
        "w.inc": "R7 in 0 1k\n",
        "l.lib": ".lib sec\nV1 in 0 DC 2\n.endl\n",
    }
    (tmp_path / "sub").mkdir()
    for name in files:
        (tmp_path / "sub" / name).write_text(contents[name], encoding="utf-8")
    body = _CIRCUIT.split("\n", 1)[1].replace("V1 in 0 DC 2\n", "")
    code, log = _run(solver, tmp_path, f"probe circuit\n{statement}\n{body}")
    assert code != 0, log
    assert "Error on line" in log
    _assert_parser_rejects(f"probe circuit\n{statement}\n.end\n")


@pytest.mark.parametrize(
    "continued",
    [
        "in 0 \\\\\nDC 2",
        "in 0 DC\\\\\n 2",
        "in 0 \\\\\n    DC 2",
        "in 0 \\\\\r\nDC 2",
        "in 0\n+ DC \\\\\n2",
    ],
)
def test_backslash_continuation_agrees_with_solver(
    solver: Solver, tmp_path: Path, continued: str
) -> None:
    code, log = _run(solver, tmp_path, _CIRCUIT.replace("V1 in 0 DC 2", f"V1 {continued}"))
    assert code == 0, log
    assert float(_voltage(log)) == pytest.approx(2.0)
    result = parse(SourceText(f"probe circuit\n.foo {continued}\n.end\n"), Dialect.NGSPICE)
    assert getattr(result.items[1], "raw", None) == f".foo {continued}"


@pytest.mark.parametrize(
    "continued",
    [
        "in 0 \\\\  \nDC 2",
        "in 0 ; comment \\\\\nDC 2",
    ],
)
def test_backslash_after_trailing_space_or_in_comment_is_solver_leniency(
    solver: Solver, tmp_path: Path, continued: str
) -> None:
    code, log = _run(solver, tmp_path, _CIRCUIT.replace("V1 in 0 DC 2", f"V1 {continued}"))
    assert code == 0, log
    assert float(_voltage(log)) == pytest.approx(2.0)
    # The parser ends the statement on line 2, so line 3 is a new D line missing its second node.
    with pytest.raises(ParseError) as captured:
        parse(SourceText(f"probe circuit\n.foo {continued}\n.end\n"), Dialect.NGSPICE)
    assert (captured.value.line, captured.value.column) == (3, 5)


@pytest.mark.parametrize(
    "lines",
    [
        "V1 in 0 DC 2 \\\\\n\n",
        "V1 in 0 DC 2 \\\\\n* comment\n",
        "V1 in 0 \\\\\n+ DC 2\n",
        "V1 in 0 DC 2\n\\\\\n",
    ],
)
def test_backslash_before_a_line_that_cannot_continue_fails_in_both(
    solver: Solver, tmp_path: Path, lines: str
) -> None:
    code, log = _run(solver, tmp_path, _CIRCUIT.replace("V1 in 0 DC 2\n", lines))
    assert code != 0, log
    _assert_parser_rejects(f"probe circuit\n{lines.replace('V1', '.foo')}.end\n")


def test_backslash_after_include_path_fails_in_both(solver: Solver, tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "v.inc").write_text("V1 in 0 DC 2\n", encoding="utf-8")
    body = _CIRCUIT.split("\n", 1)[1].replace("V1 in 0 DC 2\n", "")
    code, log = _run(solver, tmp_path, "probe circuit\n.include sub/v.inc\\\\\n" + body)
    assert code != 0
    assert "Could not find include file sub/v.inc\\\\" in log
    _assert_parser_rejects("probe circuit\n.include sub/v.inc\\\\\n.end\n")


def test_comments_on_continued_lines_agree_with_solver(solver: Solver, tmp_path: Path) -> None:
    continued = "in 0 ; one\n+ DC // two\n+ 2 $ three"
    code, log = _run(solver, tmp_path, _CIRCUIT.replace("V1 in 0 DC 2", f"V1 {continued}"))
    assert code == 0, log
    assert float(_voltage(log)) == pytest.approx(2.0)
    result = parse(SourceText(f"probe circuit\n.foo {continued}\n.end\n"), Dialect.NGSPICE)
    assert len(getattr(result.items[1], "trailing_comments", ())) == 3


def test_plus_after_end_is_ignored_by_solver_rejected_by_parser(
    solver: Solver, tmp_path: Path
) -> None:
    text = _CIRCUIT + "+ ignored after end\n"
    code, log = _run(solver, tmp_path, text)
    assert code == 0
    assert "Circuit: probe circuit" in log
    _assert_parser_rejects(text)


@pytest.mark.parametrize("comment", ["; c", "$ c", "// c"])
def test_trailing_comment_on_end_is_solver_leniency_rejected_by_parser(
    solver: Solver, tmp_path: Path, comment: str
) -> None:
    text = _CIRCUIT.replace(".end\n", f".end {comment}\n")
    code, log = _run(solver, tmp_path, text)
    assert code == 0, log
    assert float(_voltage(log)) == pytest.approx(2.0)
    _assert_parser_rejects(text)


def test_unknown_dot_command_after_end_fails_in_both(solver: Solver, tmp_path: Path) -> None:
    text = _CIRCUIT + ".unknown after end\n"
    code, log = _run(solver, tmp_path, text)
    assert code != 0
    assert "Error on line" in log
    _assert_parser_rejects(text)


def test_valid_if_form_is_accepted_by_solver_and_parser(solver: Solver, tmp_path: Path) -> None:
    text = _CIRCUIT.replace(".op\n", ".if (1)\nR2 x 0 1k\n.endif\n.op\n")
    code, log = _run(solver, tmp_path, text)
    assert code == 0, log
    assert "Circuit: probe circuit" in log
    result = parse(
        SourceText("probe circuit\n.if (1)\nR2 x 0 1k\n.endif\n.end\n"),
        Dialect.NGSPICE,
    )
    assert any(getattr(item, "kind", None) == "if" for item in result.items)


def test_double_slash_comment_probe(solver: Solver, tmp_path: Path) -> None:
    text = _CIRCUIT.replace("R1 in 0 1k\n", "// slash comment\nR1 in 0 1k\n")
    code, _ = _run(solver, tmp_path, text)
    assert code == 0
    _assert_parser_rejects(text)


@pytest.mark.parametrize(
    "source_line", ["V1 in 0 DC 2 // 3", "V1 in 0 DC 2// 3", "V1 in 0 DC 2//3"]
)
def test_double_slash_comment_needs_no_preceding_space(
    solver: Solver, tmp_path: Path, source_line: str
) -> None:
    code, log = _run(solver, tmp_path, _CIRCUIT.replace("V1 in 0 DC 2", source_line))
    assert code == 0, log
    assert float(_voltage(log)) == pytest.approx(2.0)
    directive = source_line.replace("V1 in 0 DC ", ".param v=")
    text = f"probe circuit\n{directive}\n.end\n"
    statement = parse(SourceText(text), Dialect.NGSPICE).items[1]
    assert isinstance(statement, ParamStatement)
    assert statement.assignments[0].value.text == "2"
    marker = text.index("//")
    assert statement.trailing_comments == (Span(marker, text.index("\n", marker)),)


def test_include_path_is_cut_at_double_slash_unless_quoted(solver: Solver, tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "v.inc").write_text("V1 in 0 DC 2\n", encoding="utf-8")
    body = _CIRCUIT.split("\n", 1)[1].replace("V1 in 0 DC 2\n", "")
    code, log = _run(solver, tmp_path, "probe circuit\n.include sub//v.inc\n" + body)
    assert code != 0
    assert "Could not open file" in log
    code, log = _run(solver, tmp_path, 'probe circuit\n.include "sub//v.inc"\n' + body)
    assert code == 0, log
    assert float(_voltage(log)) == pytest.approx(2.0)
    parsed = parse(
        SourceText('probe circuit\n.include sub//v.inc\n.include "sub//v.inc"\n.end\n'),
        Dialect.NGSPICE,
    )
    assert [getattr(item, "raw", None) for item in parsed.items[1:3]] == [
        ".include sub",
        '.include "sub//v.inc"',
    ]


def test_quoted_and_braced_include_paths_probe_free_text(solver: Solver, tmp_path: Path) -> None:
    (tmp_path / "quoted;$.inc").write_text("* quoted\n", encoding="utf-8")
    (tmp_path / "{braced;$.inc}").write_text("* braced\n", encoding="utf-8")
    quoted_text = 'probe circuit\n.include "quoted;$.inc"\n' + _CIRCUIT.split("\n", 1)[1]
    code, log = _run(solver, tmp_path, quoted_text)
    assert code == 0, log
    braced_text = "probe circuit\n.include {braced;$.inc}\n" + _CIRCUIT.split("\n", 1)[1]
    code, log = _run(solver, tmp_path, braced_text)
    assert code != 0
    assert "Could not find include file {braced" in log
    parsed = parse(
        SourceText('probe circuit\n.include "quoted;$.inc"\n.include {braced;$.inc}\n.end\n'),
        Dialect.NGSPICE,
    )
    assert [item.raw for item in parsed.items if hasattr(item, "raw")] == [
        '.include "quoted;$.inc"',
        ".include {braced",
    ]


def test_title_is_first_line_and_later_title_replaces_it(solver: Solver, tmp_path: Path) -> None:
    text = (
        "initial title ; still title\n"
        ".title replacement ; still title\n" + _CIRCUIT.split("\n", 1)[1]
    )
    code, log = _run(solver, tmp_path, text)
    assert code == 0
    assert "Circuit: replacement ; still title" in log
    result = parse(
        SourceText("initial title ; still title\n.title replacement ; still title\n.end\n"),
        Dialect.NGSPICE,
    )
    assert isinstance(result.items[0], Title)
    assert result.items[0].text == "initial title ; still title"
