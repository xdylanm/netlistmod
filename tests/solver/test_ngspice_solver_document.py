"""ngspice 47 probes for names, net identity and scoping (M5, T8 tier).

Each probe pairs what ngspice does with what the library reports; together they validate
``docs/grammars/ngspice/names.md`` and ``scoping.md``. Unless noted, the circuit is a divider,
``V1 in 0 DC 3`` with two 1k resistors, and the result is a voltage from the node table that
ngspice prints after ``.op`` in batch mode.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from netlistmod import (
    DiagnosticCode,
    Dialect,
    End,
    ModelStatement,
    Netlist,
    ParamAssignment,
    ParseError,
)
from tests.solver.test_ngspice_solver_elements import HARNESS
from tests.support.solvers import Solver, run_ngspice

pytestmark = pytest.mark.solver("ngspice")

CORPUS = Path(__file__).parents[1] / "corpus" / "ngspice"
C = DiagnosticCode

_DIV = ".subckt div a b\nR1 a b 1k\nR2 b 0 1k\n.ends\n"


def _run(solver: Solver, tmp_path: Path, text: str) -> tuple[int, str]:
    netlist = tmp_path / "probe.cir"
    netlist.write_bytes(text.encode("utf-8"))
    result = run_ngspice(solver, netlist)
    return result.returncode, (tmp_path / "ngspice.log").read_text(encoding="utf-8")


def _voltage(log: str, node: str) -> float:
    match = re.search(rf"(?m)^\s*{re.escape(node)}\s+([-+0-9.eE]+)\s*$", log)
    assert match is not None, log
    return float(match.group(1))


def _fails(code: int, log: str) -> bool:
    return code != 0 or "fatal error" in log.lower() or "Error" in log


def _netlist(text: str) -> Netlist:
    return Netlist.from_text(text, dialect=Dialect.NGSPICE)


def _codes(netlist: Netlist) -> list[DiagnosticCode]:
    return [diagnostic.code for diagnostic in netlist.diagnostics]


def test_node_names_are_case_insensitive(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nV1 IN 0 DC 3\nR1 in OUT 1k\nR2 out 0 1k\n.op\n.end\n"
    code, log = _run(solver, tmp_path, text)
    assert code == 0, log
    assert _voltage(log, "out") == pytest.approx(1.5)
    assert [net.name for net in _netlist(text).nets()] == ["in", "0", "out"]


def test_gnd_is_ground_and_00_is_a_separate_node(solver: Solver, tmp_path: Path) -> None:
    gnd = "probe\nV1 in GND DC 3\nR1 in out 1k\nR2 out gnd 1k\n.op\n.end\n"
    code, log = _run(solver, tmp_path, gnd)
    assert code == 0, log
    assert _voltage(log, "out") == pytest.approx(1.5)
    assert [net.name for net in _netlist(gnd).nets()] == ["in", "0", "out"]

    double_zero = "probe\nV1 in 0 DC 3\nR1 in out 1k\nR2 out 00 1k\nR3 00 0 1k\n.op\n.end\n"
    code, log = _run(solver, tmp_path, double_zero)
    assert code == 0, log
    assert _voltage(log, "out") == pytest.approx(2.0)
    assert [net.name for net in _netlist(double_zero).nets()] == ["in", "0", "out", "00"]


@pytest.mark.parametrize("second", ["R1 out 0 1k", "r1 out 0 1k"])
def test_duplicate_designators_fail(solver: Solver, tmp_path: Path, second: str) -> None:
    text = f"probe\nV1 in 0 DC 3\nR1 in out 1k\n{second}\n.op\n.end\n"
    assert _fails(*_run(solver, tmp_path, text))
    assert _codes(_netlist(text)) == [C.DUPLICATE_ELEMENT]


def test_model_and_subckt_names_are_case_insensitive_and_order_free(
    solver: Solver, tmp_path: Path
) -> None:
    text = (
        "probe\nV1 in 0 DC 3\nR1 in out 1k\nD1 out 0 DMOD\nX1 in out2 DIV\nR3 out2 0 1k\n"
        ".control\nop\nprint v(out2)\n.endc\n.model dmod d\n" + _DIV + ".op\n.end\n"
    )
    code, log = _run(solver, tmp_path, text)
    assert code == 0, log
    assert not _fails(code, log), log
    netlist = _netlist(text)
    assert [ref.target is not None for ref in netlist.references] == [True, True]
    assert _codes(netlist) == []


def test_subcircuit_port_count_mismatch_fails(solver: Solver, tmp_path: Path) -> None:
    text = "probe\nV1 in 0 DC 3\nX1 in out extra div\n" + _DIV + ".op\n.end\n"
    assert _fails(*_run(solver, tmp_path, text))
    assert _codes(_netlist(text)) == [C.SUBCKT_PORT_MISMATCH]


@pytest.mark.parametrize(
    ("params", "r2", "expected", "codes"),
    [
        (".param RX=1k\n", "{rx}", 1.5, []),
        ("", "{rx}\n.param rx=3k", 2.25, [C.PARAM_USED_BEFORE_DEFINITION]),
        (".param rx=1k\n.param rx=3k\n", "{rx}", 2.25, [C.DUPLICATE_DEFINITION]),
    ],
)
def test_parameter_case_order_and_redefinition(
    solver: Solver, tmp_path: Path, params: str, r2: str, expected: float, codes: list[C]
) -> None:
    text = f"probe\n{params}V1 in 0 DC 3\nR1 in out 1k\nR2 out 0 {r2}\n.op\n.end\n"
    code, log = _run(solver, tmp_path, text)
    assert code == 0, log
    assert _voltage(log, "out") == pytest.approx(expected)
    netlist = _netlist(text)
    assert _codes(netlist) == codes
    (reference,) = netlist.references
    assert reference.target is netlist.params["rx"][-1]


def test_local_parameters_mask_global_ones(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\n.param rx=3k\nV1 in 0 DC 3\nX1 in out div\n"
        ".subckt div a b\n.param rx=1k\nR1 a b {rx}\nR2 b 0 1k\n.ends\n.op\n.end\n"
    )
    code, log = _run(solver, tmp_path, text)
    assert code == 0, log
    assert _voltage(log, "out") == pytest.approx(1.5)
    (reference,) = _netlist(text).references_to_param("rx", ("div",))
    assert reference.scope == ("div",)


def test_models_are_local_to_their_definition(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nV1 in 0 DC 3\nR1 in out 1k\nD2 out 0 dm\n"
        ".subckt div a b\n.model dm d\nR1 a b 1k\n.ends\n.op\n.end\n"
    )
    assert _fails(*_run(solver, tmp_path, text))
    assert _codes(_netlist(text)) == [C.UNRESOLVED_MODEL]


def test_repeated_model_and_subckt_use_the_first_definition(solver: Solver, tmp_path: Path) -> None:
    subckt = (
        "probe\nV1 in 0 DC 3\nX1 in out div\n.subckt div a b\nR1 a b 1k\nR2 b 0 1k\n.ends\n"
        ".subckt div a b\nR1 a b 1k\nR2 b 0 3k\n.ends\n.op\n.end\n"
    )
    code, log = _run(solver, tmp_path, subckt)
    assert code == 0, log
    assert _voltage(log, "out") == pytest.approx(1.5)
    netlist = _netlist(subckt)
    assert netlist.references[0].target is netlist.subckts["div"][0]
    assert _codes(netlist) == [C.DUPLICATE_DEFINITION]

    model = (
        "probe\nV1 in 0 DC 3\nR1 in out 1k\nR2 out 0 rm l=1000 w=1\n"
        ".model rm R rsh=1\n.model rm R rsh=3\n.op\n.end\n"
    )
    code, log = _run(solver, tmp_path, model)
    assert code == 0, log
    assert _voltage(log, "out") == pytest.approx(1.5)
    netlist = _netlist(model)
    assert netlist.references[0].target is netlist.models["rm"][0]
    assert isinstance(netlist.references[0].target, ModelStatement)


def test_instance_parameters_are_case_insensitive_and_unknown_ones_are_ignored(
    solver: Solver, tmp_path: Path
) -> None:
    body = ".subckt div a b r2=1k\nR1 a b 1k\nR2 b 0 {r2}\n.ends\n.op\n.end\n"
    known = f"probe\nV1 in 0 DC 3\nX1 in out div R2=3k\n{body}"
    code, log = _run(solver, tmp_path, known)
    assert code == 0, log
    assert _voltage(log, "out") == pytest.approx(2.25)
    override = next(ref for ref in _netlist(known).references if ref.kind == "subckt_param")
    assert isinstance(override.target, ParamAssignment)

    unknown = f"probe\nV1 in 0 DC 3\nX1 in out div zz=3k\n{body}"
    code, log = _run(solver, tmp_path, unknown)
    assert code == 0, log
    assert _voltage(log, "out") == pytest.approx(1.5)
    netlist = _netlist(unknown)
    assert next(ref for ref in netlist.references if ref.kind == "subckt_param").target is None
    assert _codes(netlist) == []


def test_global_nodes_are_shared_and_other_nets_are_local(solver: Solver, tmp_path: Path) -> None:
    local = (
        "probe\nV1 in 0 DC 3\nX1 in out div\nR3 mid 0 1k\n"
        ".subckt div a b\nR1 a mid 1k\nR2 mid b 1k\n.ends\nR4 out 0 1k\n.op\n.end\n"
    )
    code, log = _run(solver, tmp_path, local)
    assert code == 0, log
    assert _voltage(log, "mid") == pytest.approx(0.0)
    assert _voltage(log, "x1.mid") == pytest.approx(2.0)
    netlist = _netlist(local)
    assert netlist.topology.net("mid") != netlist.topology.net("mid", ("div",))

    shared = (
        "probe\n.global vcc\nV1 vcc 0 DC 3\nX1 out div\nR2 out 0 1k\n"
        ".subckt div b\nR1 vcc b 1k\n.ends\n.op\n.end\n"
    )
    code, log = _run(solver, tmp_path, shared)
    assert code == 0, log
    assert _voltage(log, "out") == pytest.approx(1.5)
    netlist = _netlist(shared)
    assert netlist.topology.net("vcc") is netlist.topology.net("VCC", ("div",))

    unshared = shared.replace(".global vcc\n", "")
    code, log = _run(solver, tmp_path, unshared)
    assert code == 0, log
    assert _voltage(log, "out") == pytest.approx(0.0)


def test_global_inside_a_body_runs_but_the_library_rejects_it(
    solver: Solver, tmp_path: Path
) -> None:
    text = (
        "probe\nV1 vcc 0 DC 3\nX1 out div\nR2 out 0 1k\n"
        ".subckt div b\n.global vcc\nR1 vcc b 1k\n.ends\n.op\n.end\n"
    )
    code, log = _run(solver, tmp_path, text)
    assert code == 0, log
    assert _voltage(log, "out") == pytest.approx(1.5)
    with pytest.raises(ParseError, match="not allowed inside a subcircuit"):
        _netlist(text)


def test_inductor_references_are_case_insensitive(solver: Solver, tmp_path: Path) -> None:
    text = (
        "probe\nV1 in 0 DC 0 AC 1\nR1 in p 50\nL1 p 0 1m\nL2 s 0 1m\nk1 l1 L2 0.9\n"
        "R2 s 0 50\n.op\n.end\n"
    )
    code, log = _run(solver, tmp_path, text)
    assert not _fails(code, log), log
    netlist = _netlist(text)
    assert [ref.target is not None for ref in netlist.references] == [True, True]


@pytest.mark.parametrize(
    ("params", "value", "references"),
    [
        ("", "{pi}", [("pi", False)]),
        (".param a#b=3\n", "{a#b}", []),
        (".param a!b=3\n", "{a!b}", []),
        (".param a%b=3\n", "{a%b}", [("a", False), ("b", False)]),
        (".param a_b=3 c[1]=1\n", "{a_b*c[1]}", [("a_b", True), ("c[1]", True)]),
    ],
)
def test_formula_name_characters_and_constants(
    solver: Solver,
    tmp_path: Path,
    params: str,
    value: str,
    references: list[tuple[str, bool]],
) -> None:
    text = f"probe\n{params}V1 in 0 DC {value}\nR1 in out 1k\nR2 out 0 1k\n.op\n.end\n"
    code, log = _run(solver, tmp_path, text)
    if references and all(resolved for _, resolved in references):
        assert code == 0, log
        assert _voltage(log, "out") == pytest.approx(1.5)
    else:
        # ngspice 47 does not read pi as a constant, nor ! # % as name characters.
        assert _fails(code, log)
    found = [(ref.name, ref.target is not None) for ref in _netlist(text).references]
    assert found == references


_VECTOR = re.compile(r"(?m)^\s+(\S+)\s+: voltage,")
_NUMERIC = re.compile(r"^V\((.*)\)$")


def _ngspice_nodes(solver: Solver, tmp_path: Path, netlist: Netlist, harness: str = "") -> set[str]:
    """The top-level node names ngspice reports for a netlist (``display`` after ``op``).

    ``harness`` (models and subcircuits the file refers to) is inserted before ``.end``; it
    adds no top-level node.
    """
    end = netlist.lines.find(End)
    assert end is not None
    at = netlist.lines.insert_before(end).start
    control = ".control\nsave all\nop\ndisplay\n.endc\n"
    text = netlist.text[:at] + harness + control + netlist.text[at:]
    code, log = _run(solver, tmp_path, text)
    assert code == 0, log
    # Subcircuit-internal nodes are reported by instance path (x1.mid); ground is not listed;
    # a node whose name is a number is listed as V(13).
    names = (_NUMERIC.sub(r"\1", name) for name in _VECTOR.findall(log))
    return {name for name in names if "." not in name and "#" not in name}


@pytest.mark.parametrize(
    "path",
    sorted(
        [*(CORPUS / "statements_basic").glob("*.cir"), *(CORPUS / "elements_basic").glob("*.cir")]
    ),
    ids=lambda path: f"{path.parent.name}/{path.name}",
)
def test_library_nets_match_the_ngspice_node_list(
    solver: Solver, tmp_path: Path, path: Path
) -> None:
    netlist = Netlist.load(path, dialect=Dialect.NGSPICE)
    library = {net.name for net in netlist.nets() if net.name != "0"}
    harness = HARNESS if path.parent.name == "elements_basic" else ""
    assert _ngspice_nodes(solver, tmp_path, netlist, harness) == library


def test_document_basic_circuits_run(solver: Solver, tmp_path: Path) -> None:
    for path in sorted((CORPUS / "document_basic").glob("*.cir")):
        if path.name == "every_diagnostic.cir":
            continue  # deliberately broken: one of every diagnostic
        netlist = Netlist.load(path, dialect=Dialect.NGSPICE)
        assert all(ref.target is not None for ref in netlist.references), path.name
        library = {net.name for net in netlist.nets() if net.name != "0"}
        assert _ngspice_nodes(solver, tmp_path, netlist) == library, path.name
