"""XyceNF 7.10 probes of the xyce transistor models: the node counts of each LEVEL, the model
types, binned M models and `.PREPROCESS REMOVEUNUSED` (X-M4 B5; decision 0031 items 5 to 8 and
10; xm4-tasks 5.1 points 11 to 20, 25 and 26).

Each probe is a minimal netlist authored here and run with ``Xyce`` through
``tests/support/xyce.py``, in a temporary folder; nothing Xyce writes is committed. Each test
states the library's reading (and its `NODE_COUNT_MISMATCH`, `UNRESOLVED_MODEL` and
`MODEL_TYPE_MISMATCH` warnings) beside what Xyce does. A node Xyce drops is absent from its
names file; a device `REMOVEUNUSED` removes is absent from the log's device count.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from netlistmod import DiagnosticCode, Netlist, ParseError, UnknownDirective
from netlistmod.dialects import _XYCE
from netlistmod.model.xyce_levels import level_nodes
from tests.support.solvers import Solver
from tests.support.xyce import nodes, op, run

pytestmark = pytest.mark.solver("xyce")

_FIXED = {"BipolarTransistor": ("Q1", ["c", "b", "0"]), "Mosfet": ("M1", ["d", "g", "0"])}
_TYPES = {"BipolarTransistor": "npn", "Mosfet": "nmos"}
_MOST = {"BipolarTransistor": 5, "Mosfet": 7}


def _netlist(text: str) -> Netlist:
    return Netlist.from_text(text, dialect=_XYCE)


def _codes(text: str) -> set[DiagnosticCode]:
    return {item.code for item in _netlist(text).diagnostics}


def _line(kind: str, level: int, count: int, most: int, tail: str = "") -> str:
    """A line of ``count`` nodes on a model of ``level``: the fixed nodes, then nodes held at 0 V
    up to the level's ``most``, then floating nodes ``x<n>``, which Xyce drops or joins."""
    designator, fixed = _FIXED[kind]
    extra = [f"n{n}" if n <= most else f"x{n}" for n in range(4, count + 1)]
    sources = "".join(f"\nV{name} {name} 0 0" for name in extra if name.startswith("n"))
    model = f".model mx {_TYPES[kind]} level={level}"
    supply = "VC c 0 5\nVB b 0 0.7" if kind == "BipolarTransistor" else "VD d 0 1\nVG g 0 1"
    nodes_ = " ".join([*fixed, *extra])
    return f"lv\n{supply}\n{designator} {nodes_} mx{tail}{sources}\n{model}\n.op\n.end\n"


def _level_cases() -> list[object]:
    """For a level of each `extra` kind of `model/xyce-levels.json` (and the TNODEOUT levels),
    every count from one below its range to one above it that the letter's grammar reads."""
    chosen = {
        "BipolarTransistor": (1, 11, 12, 230, 504, 505),
        "Mosfet": (1, 10, 18, 70, 77, 1031, 2000),
    }
    cases: list[object] = []
    for kind, levels in chosen.items():
        for level in levels:
            entry = level_nodes(kind, level)
            assert entry is not None
            for tnodeout in (False, True) if entry.tnodeout else (False,):
                least, most = entry.range(tnodeout)
                for count in range(max(3, least - 1), min(_MOST[kind], most + 1) + 1):
                    if count > most and entry.extra is None:
                        continue
                    tag = "-tnodeout" if tnodeout else ""
                    cases.append(
                        pytest.param(
                            kind, level, count, tnodeout, id=f"{kind}-{level}-{count}{tag}"
                        )
                    )
    return cases


@pytest.mark.parametrize(("kind", "level", "count", "tnodeout"), _level_cases())
def test_each_level_takes_the_counts_of_the_level_table(
    solver: Solver, tmp_path: Path, kind: str, level: int, count: int, tnodeout: bool
) -> None:
    """The level table (5.1 point 11): Xyce runs a count in the level's range and stops on fewer;
    on more it stops, drops the extra nodes (absent from its circuit) or joins them to internal
    nodes (present, a different circuit), as `extra` says. The library reads every count the
    letter allows and warns (`NODE_COUNT_MISMATCH`) exactly outside the range (decision 0031
    item 5), which `reads/stops`, `reads/ignores` and `reads/runs` rows record."""
    entry = level_nodes(kind, level)
    assert entry is not None
    least, most = entry.range(tnodeout)
    text = _line(kind, level, count, most, " tnodeout=1" if tnodeout else "")
    warned = DiagnosticCode.NODE_COUNT_MISMATCH in _codes(text)
    assert warned is not (least <= count <= most)
    result = run(solver, tmp_path / "run", text)
    if count < least or (count > most and entry.extra == "stops"):
        assert not result.ok
        return
    assert result.ok, result.log
    floating = {f"x{n}" for n in range(most + 1, count + 1)}
    found = nodes(solver, tmp_path / "names", text)
    if entry.extra == "dropped":
        assert not floating & found
    elif count > most:
        assert entry.extra == "joined"
        assert floating <= found


def test_fbh_level_23_drops_a_fifth_node(solver: Solver, tmp_path: Path) -> None:
    """FBH (level 23) takes four nodes, the 4th its thermal node. Xyce runs five, dropping the
    5th (absent from its circuit), as `model/xyce-levels.json` records (`extra` `dropped`,
    corrected in X-M4 B5 from Stage 1's `stops`). The library warns on the count
    (`reads/ignores`, `library-limit`)."""
    text = _line("BipolarTransistor", 23, 5, 4)
    entry = level_nodes("BipolarTransistor", 23)
    assert entry is not None and entry.nodes == (4, 4) and entry.extra == "dropped"
    assert DiagnosticCode.NODE_COUNT_MISMATCH in _codes(text)
    assert run(solver, tmp_path / "run", text).ok
    assert "x5" not in nodes(solver, tmp_path / "names", text)
    assert not run(solver, tmp_path / "three", _line("BipolarTransistor", 23, 3, 4)).ok


@pytest.mark.parametrize(
    ("kind", "letter", "level", "ok"),
    [("njf", "J", 1, True), ("njf", "J", 2, True), ("nmf", "Z", 1, True), ("nmf", "Z", 2, False)],
)
def test_j_and_z_take_three_nodes_on_their_levels(
    solver: Solver, tmp_path: Path, kind: str, letter: str, level: int, ok: bool
) -> None:
    """J has levels 1 and 2 and Z level 1, each of three nodes; a Z of level 2 stops Xyce (no
    valid model card), on which the library, knowing no such level, is silent."""
    text = (
        f"jz\nVD d 0 5\nVG g 0 0\n{letter}1 d g 0 mx\n.model mx {kind} level={level}\n.op\n.end\n"
    )
    assert DiagnosticCode.NODE_COUNT_MISMATCH not in _codes(text)
    assert run(solver, tmp_path, text).ok is ok


@pytest.mark.parametrize(
    ("level", "count"),
    [("{lv}", 3), ("10.4", 5), ("'10'", 5)],
    ids=["braced", "fractional", "quoted"],
)
def test_a_level_that_is_not_a_plain_integer_leaves_the_check_silent(
    solver: Solver, tmp_path: Path, level: str, count: int
) -> None:
    """The library checks only a plain integer LEVEL (decision 0031 item 5). Xyce stops on a
    braced LEVEL (5.1 point 11: "LEVEL must be a literal") and reads the others in its own way;
    the library is silent on each."""
    text = (
        "lv\nVD d 0 1\nVG g 0 1\n.param lv=1\nV5 n5 0 0\n"
        f"M1 d g 0 {' '.join(['0', 'n5'][: count - 3])} nm\n"
        f".model nm nmos level={level}\n.op\n.end\n"
    )
    assert DiagnosticCode.NODE_COUNT_MISMATCH not in _codes(text)
    if level == "{lv}":
        assert not run(solver, tmp_path, text).ok


# Model types (decision 0031 item 6; 5.1 points 13 and 14).


@pytest.mark.parametrize(
    ("line", "model", "ok"),
    [
        ("Q1 d g 0 mx", "npn", True),
        ("Q1 d g 0 mx", "pnp", True),
        ("Q1 d g 0 mx", "nmos", False),
        ("M1 d g 0 0 mx", "nmos", True),
        ("M1 d g 0 0 mx", "pmos", True),
        ("M1 d g 0 0 mx", "nmos level=18", True),
        ("M1 d g 0 0 mx", "vdmos", False),
        ("M1 d g 0 0 mx", "npn", False),
        ("J1 d g 0 mx", "njf", True),
        ("J1 d g 0 mx", "pjf", True),
        ("J1 d g 0 mx", "nmf", False),
        ("Z1 d g 0 mx", "nmf", True),
        ("Z1 d g 0 mx", "pmf", True),
        ("Z1 d g 0 mx", "njf", False),
    ],
)
def test_each_letter_takes_its_model_types(
    solver: Solver, tmp_path: Path, line: str, model: str, ok: bool
) -> None:
    """A type the letter takes runs; another stops Xyce ("no valid model card found"), and the
    library warns (`MODEL_TYPE_MISMATCH`, saying Xyce stops). VDMOS is no type: it is NMOS or PMOS
    at `LEVEL=18`."""
    text = f"types\nVD d 0 1\nVG g 0 1\n{line}\n.model mx {model}\n.op\n.end\n"
    assert (DiagnosticCode.MODEL_TYPE_MISMATCH not in _codes(text)) is ok
    assert run(solver, tmp_path, text).ok is ok


# Binned M models (decision 0031 items 7 and 8; 5.1 points 15 to 18).

_BIN1 = ".model nch.1 nmos level=1 vto=0.3 lmin=0.1u lmax=20u wmin=0.1u wmax=10u"
_BIN2 = ".model nch.2 nmos level=1 vto=0.9 lmin=0.1u lmax=20u wmin=10u wmax=100u"
_BINS = f"{_BIN1}\n{_BIN2}"


def _bin(lines: str, models: str = _BINS, extra: str = "") -> str:
    return f"bins\nVD d 0 1\nVG g 0 1.2\n{lines}\n{models}\n{extra}\n.op\n.end\n"


def _drain(solver: Solver, folder: Path, text: str) -> float:
    return -op(solver, folder, text)["vd#branch"]


def _vto(solver: Solver, folder: Path, vto: float, size: str = "L=1u W=5u") -> float:
    """The drain current of the same line on one model of ``vto``, with no bounds."""
    text = _bin(f"M1 d g 0 0 mx {size}", f".model mx nmos level=1 vto={vto}")
    return _drain(solver, folder, text)


@pytest.mark.parametrize(
    ("size", "vto"),
    [("L=1u W=5u", 0.3), ("L=1u W=50u", 0.9), ("L=1u W=10u", 0.9)],
    ids=["first-bin", "second-bin", "lower-bound-inclusive"],
)
def test_a_set_of_bins_is_resolved_and_xyce_selects_by_l_and_w(
    solver: Solver, tmp_path: Path, size: str, vto: float
) -> None:
    """`nch` names the set `nch.1`, `nch.2`: the library resolves it (no `UNRESOLVED_MODEL`, the
    reference on the first bin) and Xyce selects the bin whose bounds hold L and W, half-open
    (`W=10u` is the second bin's), as the current shows."""
    text = _bin(f"M1 d g 0 0 nch {size}")
    assert DiagnosticCode.UNRESOLVED_MODEL not in _codes(text)
    current = _drain(solver, tmp_path / "bins", text)
    assert current == pytest.approx(_vto(solver, tmp_path / "one", vto, size))


@pytest.mark.parametrize(
    "model",
    [
        ".model nch.a nmos level=1 vto=0.9 lmin=0.1u lmax=20u wmin=10u wmax=100u",
        ".model nch.x.2 nmos level=1 vto=0.9 lmin=0.1u lmax=20u wmin=10u wmax=100u",
        ".model NCH.2 nmos level=1 vto=0.9 lmin=0.1u lmax=20u wmin=10u wmax=100u",
    ],
    ids=["letter-suffix", "dotted-suffix", "case"],
)
def test_any_non_empty_suffix_is_a_bin(solver: Solver, tmp_path: Path, model: str) -> None:
    """The manual says "bin number"; Xyce takes any suffix, folded, and so does the library (G1
    point 15 (a); the row `reads/runs`, `imprecise`)."""
    text = _bin("M1 d g 0 0 nch L=1u W=50u", model)
    assert DiagnosticCode.UNRESOLVED_MODEL not in _codes(text)
    current = _drain(solver, tmp_path / "bins", text)
    assert current == pytest.approx(_vto(solver, tmp_path / "one", 0.9, "L=1u W=50u"))


def test_a_bin_named_directly_is_an_ordinary_model(solver: Solver, tmp_path: Path) -> None:
    """`nch.2` names that model, its bounds not checked: Xyce runs it at `W=5u`."""
    text = _bin("M1 d g 0 0 nch.2 L=1u W=5u")
    assert not _codes(text) & {DiagnosticCode.UNRESOLVED_MODEL}
    assert _drain(solver, tmp_path / "bin", text) == pytest.approx(_vto(solver, tmp_path, 0.9))


def test_an_exact_name_wins_over_a_set(solver: Solver, tmp_path: Path) -> None:
    text = _bin("M1 d g 0 0 nch L=1u W=50u", f"{_BINS}\n.model nch nmos level=1 vto=0")
    assert _drain(solver, tmp_path / "exact", text) == pytest.approx(
        _vto(solver, tmp_path / "one", 0.0, "L=1u W=50u")
    )


def test_a_set_is_gathered_across_the_scope_chain(solver: Solver, tmp_path: Path) -> None:
    """A bin at the top level and one in the body form one set inside the body; a set in a body is
    not visible at the top level. The library resolves the first and reports the second, as Xyce
    runs and stops."""
    split = _bin(
        "X1 d g sub",
        _BIN1,
        f".subckt sub a b\nM1 a b 0 0 nch L=1u W=50u\n{_BIN2}\n.ends",
    )
    assert DiagnosticCode.UNRESOLVED_MODEL not in _codes(split)
    assert _drain(solver, tmp_path / "split", split) == pytest.approx(
        _vto(solver, tmp_path / "one", 0.9, "L=1u W=50u")
    )
    hidden = _bin(
        "M1 d g 0 0 nch L=1u W=5u\nX1 d g sub", "", f".subckt sub a b\n{_BIN1}\nR1 a b 1k\n.ends"
    )
    assert DiagnosticCode.UNRESOLVED_MODEL in _codes(hidden)
    assert not run(solver, tmp_path / "hidden", hidden).ok


def test_binning_off_leaves_the_name_unresolved(solver: Solver, tmp_path: Path) -> None:
    text = _bin("M1 d g 0 0 nch L=1u W=50u", extra=".options parser model_binning=false")
    assert DiagnosticCode.UNRESOLVED_MODEL in _codes(text)
    assert not run(solver, tmp_path, text).ok


@pytest.mark.parametrize(
    ("line", "models"),
    [
        ("Q1 d g 0 qn", ".model qn.1 npn"),
        ("J1 d g 0 jn", ".model jn.1 njf"),
    ],
    ids=["q", "j"],
)
def test_only_m_bins(solver: Solver, tmp_path: Path, line: str, models: str) -> None:
    """A set name on Q or J is unresolved, for the library and for Xyce."""
    text = _bin(line, models)
    assert DiagnosticCode.UNRESOLVED_MODEL in _codes(text)
    assert not run(solver, tmp_path, text).ok


@pytest.mark.parametrize(
    "line",
    ["M1 d g 0 0 nch", "M1 d g 0 0 nch W=50u", "M1 d g 0 0 nch L=1u W=500u"],
    ids=["no-l-or-w", "no-l", "in-no-bin"],
)
def test_a_set_no_bin_takes_is_read_and_xyce_stops(
    solver: Solver, tmp_path: Path, line: str
) -> None:
    """The library does not select a bin (decision 0031 item 7): it reads a set named without
    both `L=` and `W=`, or with a size no bin holds, as resolved; Xyce finds no model card and
    stops (the row `reads/stops`, `library-limit`)."""
    text = _bin(line)
    assert DiagnosticCode.UNRESOLVED_MODEL not in _codes(text)
    assert not run(solver, tmp_path, text).ok


def test_a_bin_missing_a_bound_is_never_selected(solver: Solver, tmp_path: Path) -> None:
    """A bin without WMIN and WMAX: Xyce never selects it, while the other bin still works (the
    row `reads/runs`, `imprecise`)."""
    models = ".model nch.1 nmos level=1 vto=0.3 lmin=0.1u lmax=20u\n" + _BIN2
    assert not run(solver, tmp_path / "first", _bin("M1 d g 0 0 nch L=1u W=5u", models)).ok
    second = _bin("M1 d g 0 0 nch L=1u W=50u", models)
    assert DiagnosticCode.UNRESOLVED_MODEL not in _codes(second)
    assert _drain(solver, tmp_path / "second", second) == pytest.approx(
        _vto(solver, tmp_path / "one", 0.9, "L=1u W=50u")
    )


def test_bins_may_differ_in_level_or_type(solver: Solver, tmp_path: Path) -> None:
    """The selected bin rules, its node count too: a 5-node line on a set of a level 10 bin and a
    level 1 bin runs on either, and a PMOS bin beside an NMOS one runs. The library checks each
    bin's level (`NODE_COUNT_MISMATCH` names the level 1 bin) and takes NMOS and PMOS alike (the
    row `reads/runs`, `imprecise`)."""
    soi = ".model nch.1 nmos level=10 lmin=0.1u lmax=20u wmin=0.1u wmax=10u\n" + _BIN2
    for size in ("W=5u", "W=50u"):
        text = _bin(f"M1 d g 0 0 n5 nch L=1u {size}\nV5 n5 0 0", soi)
        messages = [item.message for item in _netlist(text).diagnostics]
        assert any("bin `nch.2`" in message for message in messages)
        assert run(solver, tmp_path / size, text).ok
    mixed = _BIN1 + "\n.model nch.2 pmos level=1 lmin=0.1u lmax=20u wmin=10u wmax=100u"
    text = _bin("M1 d g 0 0 nch L=1u W=50u", mixed)
    assert DiagnosticCode.MODEL_TYPE_MISMATCH not in _codes(text)
    assert run(solver, tmp_path / "pmos", text).ok


def test_under_step_the_bin_is_chosen_once(solver: Solver, tmp_path: Path) -> None:
    """`.STEP` over W: Xyce keeps the bin of the first step (the row `reads/runs`,
    `imprecise`)."""
    text = _bin("M1 d g 0 0 nch L=1u W={ww}", extra=".param ww=5u\n.step ww list 5u 50u").replace(
        ".op", ".dc VD 1 1 1"
    )
    result = run(solver, tmp_path / "step", text)
    assert result.ok, result.log
    currents = [-float(v.real) for plot in result.plots for v in plot.column("vd#branch")]
    first = _vto(solver, tmp_path / "w5", 0.3)
    assert currents[0] == pytest.approx(first)
    assert currents[-1] == pytest.approx(10 * first)


@pytest.mark.parametrize(
    ("lines", "body"),
    [
        ("M1 d g 0 0 nch L=1u W=50u\nM2 d g 0 0 nch L=1u W=60u", ""),
        ("X1 d g sub\nX2 d g sub", "M4 a b 0 0 nch L=1u W=50u"),
        ("M1 d g 0 0 nch L=1u W=50u\nX1 d g sub", "M4 a b 0 0 nch L=1u W=50u"),
        ("X1 d g sub", "M4 a b 0 0 nch L=1u W=50u\nM5 a b 0 0 nch L=1u W=60u"),
        ("M1 d g 0 0 nch.2 L=1u W=50u\nX1 d g sub", "M4 a b 0 0 nch L=1u W=50u"),
    ],
    ids=["two-top-lines", "two-instances", "top-then-body", "two-body-lines", "direct-then-set"],
)
def test_a_bin_is_selected_by_one_line_only(
    solver: Solver, tmp_path: Path, lines: str, body: str
) -> None:
    """Undocumented: Xyce stops ("no valid model card") on the second M line, or instance, that
    selects a bin through its set when another line has used that bin, by the set or (before it)
    by its own name: two lines of one scope, an M in a body called twice, the top level and a
    body. The library resolves every such line (the row `reads/stops`, `manual`). Bins that
    differ, or a bin named directly after its selection, run."""
    text = _bin(lines, extra=f".subckt sub a b\n{body}\n.ends" if body else "")
    assert DiagnosticCode.UNRESOLVED_MODEL not in _codes(text)
    assert not run(solver, tmp_path / "twice", text).ok
    differ = _bin("M1 d g 0 0 nch L=1u W=5u\nM2 d g 0 0 nch L=1u W=50u\nM3 d g 0 0 nch.2 L=1u W=5u")
    assert run(solver, tmp_path / "differ", differ).ok


def test_a_set_name_is_no_model_parameter_target(solver: Solver, tmp_path: Path) -> None:
    """`nch:vto` names no model for Xyce, which stops; the library looks the head up by its exact
    name (scoping.md S13)."""
    text = _bin("M1 d g 0 0 nch L=1u W=5u", extra=".print dc nch:vto")
    assert not run(solver, tmp_path, text).ok


# `.PREPROCESS REMOVEUNUSED` (decision 0031 item 10; 5.1 points 25 and 26).


def _ru(device: str, preprocess: str, extra: str = "") -> str:
    models = ".model nm nmos level=1\n.model qn npn"
    return f"ru\nVD d 0 1\nR1 d 0 1k\n{device}\n{preprocess}\n{models}\n{extra}\n.op\n.end\n"


def _devices(log: str, letter: str) -> int:
    """How many devices of ``letter`` the log's "Device Count Summary" counts."""
    return sum(int(count) for count in re.findall(rf"^\s+{letter} level .*?(\d+)$", log, re.M))


@pytest.mark.parametrize(
    "preprocess",
    [
        ".PREPROCESS REMOVEUNUSED V",
        ".preprocess removeunused r,v",
        ".PREPROCESS REMOVEUNUSED R, V",
        ".PREPROCESS REMOVEUNUSED V,V",
        ".PREPROCESS REMOVEUNUSED R,\n+ V",
    ],
    ids=["one", "lower-case-list", "blank-after-comma", "repeated", "continued"],
)
def test_removeunused_removes_a_listed_device_on_one_node(
    solver: Solver, tmp_path: Path, preprocess: str
) -> None:
    """`V2 d d 1` across VD's node makes the matrix singular; listed, Xyce removes it and runs.
    The library reads the line as an `UnknownDirective` and keeps V2 (P4)."""
    text = _ru("V2 d d 1", preprocess)
    netlist = _netlist(text)
    assert any(isinstance(item, UnknownDirective) for item in netlist.parse_result.items)
    assert netlist.element("V2") is not None
    assert not run(solver, tmp_path / "kept", _ru("V2 d d 1", "")).ok
    assert run(solver, tmp_path / "removed", text).ok


@pytest.mark.parametrize(
    ("device", "letter", "removed"),
    [
        ("M2 d d d 0 nm", "M", True),
        ("Q2 d d d 0 qn", "Q", True),
        ("Q2 d d 0 d qn", "Q", False),
    ],
    ids=["m-first-three", "q-first-three", "q-two-nodes"],
)
def test_removeunused_looks_at_the_first_three_nodes_of_m_and_q(
    solver: Solver, tmp_path: Path, device: str, letter: str, removed: bool
) -> None:
    text = _ru(device, f".PREPROCESS REMOVEUNUSED {letter}")
    _netlist(text)
    result = run(solver, tmp_path, text)
    assert result.ok, result.log
    assert _devices(result.log, letter) == (0 if removed else 1)


@pytest.mark.parametrize(
    ("preprocess", "ok"),
    [
        (".PREPROCESS REMOVEUNUSED R V", True),
        (".PREPROCESS REMOVEUNUSED V,", True),
        (".PREPROCESS REMOVEUNUSED", False),
        (".PREPROCESS REMOVEUNUSED J", False),
        (".PREPROCESS REMOVEUNUSED {V}", False),
        (".PREPROCESS REMOVEUNUSED V\n.PREPROCESS REMOVEUNUSED R", False),
    ],
    ids=["blank-separated", "trailing-comma", "empty", "another-letter", "braces", "two-lines"],
)
def test_removeunused_forms_the_library_refuses(
    solver: Solver, tmp_path: Path, preprocess: str, ok: bool
) -> None:
    """Blank separators and a trailing comma run, removing V2 (the rows `refuses/runs`,
    `manual`); an empty list, another letter, braces and a second line stop Xyce."""
    text = _ru("V2 d d 1", preprocess)
    with pytest.raises(ParseError, match="REMOVEUNUSED|letter|comma|blank"):
        _netlist(text)
    assert run(solver, tmp_path, text).ok is ok


def test_removeunused_follows_how_an_instance_connects(solver: Solver, tmp_path: Path) -> None:
    """In a body, per instance: a V between two ports is removed where the instance ties both
    ports to one node, and kept where it does not; a ground synonym counts only under
    `REPLACEGROUND`. The library keeps every device and has no diagnostic (the row `reads/runs`,
    `library-limit`)."""
    body = ".subckt sub2 a b\nV9 a b 1\n.ends"
    tied = _ru("X1 d d sub2", ".PREPROCESS REMOVEUNUSED V", body)
    apart = _ru("X1 d 0 sub2", ".PREPROCESS REMOVEUNUSED V", body)
    for text in (tied, apart):
        assert DiagnosticCode.UNTYPED_DIRECTIVE_PRESERVED in _codes(text)
    assert run(solver, tmp_path / "tied", tied).ok
    assert not run(solver, tmp_path / "apart", apart).ok
    ground = _ru("V2 0 gnd 1", ".PREPROCESS REMOVEUNUSED V")
    assert "v2_branch" in {name for name in _names(solver, tmp_path / "ground", ground)}
    replaced = _ru("V2 0 gnd 1", ".PREPROCESS REMOVEUNUSED V\n.PREPROCESS REPLACEGROUND TRUE")
    _netlist(replaced)
    assert "v2_branch" not in _names(solver, tmp_path / "replaced", replaced)


def test_removeunused_stands_in_a_body(solver: Solver, tmp_path: Path) -> None:
    text = _ru(
        "X1 d sub", "", ".subckt sub a\n.PREPROCESS REMOVEUNUSED V\nV9 a a 1\nR8 a 0 1k\n.ends"
    )
    _netlist(text)
    assert run(solver, tmp_path, text).ok


def _names(solver: Solver, folder: Path, text: str) -> frozenset[str]:
    result = run(solver, folder, text, mode="namesfile")
    assert result.ok, result.log
    return result.names
