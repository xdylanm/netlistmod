"""The edit layer on LTspice netlists (M8 T7; decisions 11 and 17), golden diffs included."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

import pytest

from netlistmod import (
    Dialect,
    EditError,
    Netlist,
    Placement,
    StepDirective,
    TopologyError,
    TopologyViolation,
)
from tests.edits.golden import apply_steps

pytestmark = pytest.mark.ltspice_only

CORPUS = Path(__file__).parents[1] / "corpus" / "ltspice"
GOLDEN = CORPUS / "edits_golden"
INPUTS = CORPUS / "contributed_examples"
CASES: dict[str, dict[str, Any]] = json.loads(
    (GOLDEN / "manifest.json").read_text(encoding="utf-8")
)["cases"]


def _netlist(body: str) -> Netlist:
    return Netlist.from_text(f"title\n{body}\n.end\n", dialect=Dialect.LTSPICE)


def _body(netlist: Netlist) -> str:
    return netlist.text.removeprefix("title\n").removesuffix("\n.end\n")


@pytest.mark.parametrize(
    ("before", "edit", "after"),
    [
        ("R1 a 0 1k", lambda n: n.set_value("R1", "2k2"), "R1 a 0 2k2"),
        ("R1 a 0 1k", lambda n: n.set_formula("R1", "x"), "R1 a 0 {x}"),
        ("R1 a 0 1k", lambda n: n.set_param("R1", "m", "2"), "R1 a 0 1k m=2"),
        ("R1 a 0 1k ; c", lambda n: n.set_param("R1", "temp", "30"), "R1 a 0 1k temp=30 ; c"),
        ("R1 a 0 1k tc=1m,1u", lambda n: n.set_param("r1", "TC", "2m,2u"), "R1 a 0 1k tc=2m,2u"),
        ("R1 a 0 1k", lambda n: n.set_param("R1", "tc", "1m,1u"), "R1 a 0 1k tc=1m,1u"),
        ("C1 a 0 1µ", lambda n: n.set_value("C1", "4u7"), "C1 a 0 4u7"),
        ("C1 a 0 1u Rser=1", lambda n: n.set_param("C1", "rser", "1k"), "C1 a 0 1u Rser=1k"),
        ("C1 a 0 1u", lambda n: n.set_param("C1", "Rser", "1k"), "C1 a 0 1u Rser=1k"),
        ("L1 a 0 1m\n+ Rser=1", lambda n: n.set_param("L1", "Rser", "2"), "L1 a 0 1m\n+ Rser=2"),
        ("V1 a 0 1", lambda n: n.set_param("V1", "Rser", "10m"), "V1 a 0 1 Rser=10m"),
        ("V1 a 0 1 AC 1", lambda n: n.set_param("V1", "Rser", "1"), "V1 a 0 1 AC 1 Rser=1"),
        ("V1 a 0 1 Rser=1", lambda n: n.set_dc("V1", "2k2"), "V1 a 0 2k2 Rser=1"),
        ("V1 a 0", lambda n: n.set_dc("V1", "3"), "V1 a 0 DC 3"),
        ("V1 a 0 1", lambda n: n.set_ac("V1", "1", "90"), "V1 a 0 1 AC 1 90"),
        ("V1 a 0 1 AC=1", lambda n: n.set_ac("V1", "2"), "V1 a 0 1 AC=2"),
        ("I1 a 0 R=1k", lambda n: n.set_param("I1", "R", "2k"), "I1 a 0 R=2k"),
        (
            "D1 a 0 dm 2\n.model dm D",
            lambda n: n.set_param("D1", "area", "3"),
            "D1 a 0 dm 3\n.model dm D",
        ),
        (
            "D1 a 0 dm\n.model dm D",
            lambda n: n.set_param("D1", "AREA", "3"),
            "D1 a 0 dm 3\n.model dm D",
        ),
        (
            "D1 a 0 dm off\n.model dm D",
            lambda n: n.set_param("D1", "m", "2"),
            "D1 a 0 dm off m=2\n.model dm D",
        ),
        (
            "D1 a 0 dm\n.model dm D\n.model em D",
            lambda n: n.set_model("D1", "em"),
            "D1 a 0 em\n.model dm D\n.model em D",
        ),
        (
            "X§U1 a b s r=1k ;§pnba p)q",
            lambda n: n.set_instance_param("X§U1", "r", "2k"),
            "X§U1 a b s r=2k ;§pnba p)q",
        ),
        ("K1 L1 L2 0.5", lambda n: n.set_coupling("K1", "0m9"), "K1 L1 L2 0m9"),
        (
            "R1 a 0 1k noiseless=1",
            lambda n: n.set_param("R1", "NOISELESS", "0"),
            "R1 a 0 1k noiseless=0",
        ),
        (
            "R1 a 0 1k noiseless",
            lambda n: n.set_param("R1", "noiseless", "0"),
            "R1 a 0 1k noiseless=0",
        ),
        ("R1 a 0 1k", lambda n: n.set_param("R1", "noiseless", "1"), "R1 a 0 1k noiseless=1"),
        ("I1 a 0 1m load", lambda n: n.set_param("I1", "load", "1"), "I1 a 0 1m load=1"),
        (
            "D1 a 0 dm off\n.model dm D",
            lambda n: n.set_param("D1", "off", "1"),
            "D1 a 0 dm off=1\n.model dm D",
        ),
        (
            "D1 a 0 dm\n.model dm D",
            lambda n: n.set_param("D1", "Rpar", "1k"),
            "D1 a 0 dm Rpar=1k\n.model dm D",
        ),
        ("R1 a 0 1k", lambda n: n.set_param("R1", "mfg", '"a b"'), 'R1 a 0 1k mfg="a b"'),
        ("R1 a 0 1k tol=1", lambda n: n.set_param("R1", "tol", "5"), "R1 a 0 1k tol=5"),
        (
            "R1 a 0 1k noiseless",
            lambda n: n.set_param("R1", "pwr", "1"),
            "R1 a 0 1k noiseless pwr=1",
        ),
        ("C1 a 0 1u V=6.3 Irms=1", lambda n: n.set_param("C1", "V", "10"), "C1 a 0 1u V=10 Irms=1"),
        (
            'L1 a 0 1m Ipk=5 mfg="Bourns, Inc."',
            lambda n: n.set_param("L1", "Ipk", "6"),
            'L1 a 0 1m Ipk=6 mfg="Bourns, Inc."',
        ),
        ('C1 a 0 1u mfg="a b"', lambda n: n.set_param("C1", "MFG", "word"), "C1 a 0 1u mfg=word"),
        ("C1 a 0 1u", lambda n: n.set_param("C1", "pn", '"p n"'), 'C1 a 0 1u pn="p n"'),
        (
            "D1 a 0 dm area=2\n.model dm D",
            lambda n: n.set_param("D1", "area", "3"),
            "D1 a 0 dm area=3\n.model dm D",
        ),
        (
            ".model d D(mfg=a Is=1n)",
            lambda n: n.set_model_param("d", "mfg", "b"),
            ".model d D(mfg=b Is=1n)",
        ),
        (
            ".model d D(mfg=a)",
            lambda n: n.set_model_param("d", "mfg", '"b c"'),
            '.model d D(mfg="b c")',
        ),
        (
            ".model d D(mfg=a)",
            lambda n: n.set_model_param("d", "Is", "1n"),
            ".model d D(mfg=a Is=1n)",
        ),
        (
            ".ic I(L1)=1\nL1 a 0 1m",
            lambda n: n.directives.replace(n.lines[1], ".ic I(L1)=2"),
            ".ic I(L1)=2\nL1 a 0 1m",
        ),
        (
            ".model dm D(Is=1n)",
            lambda n: n.set_model_param("dm", "N", "2"),
            ".model dm D(Is=1n N=2)",
        ),
        (".param x=1k", lambda n: n.params.set("x", "2k2"), ".param x=2k2"),
        (".param x 1k", lambda n: n.params.set("X", "2"), ".param x 2"),
        (".param x = a + b", lambda n: n.params.set("x", "c*2"), ".param x = c*2"),
        (
            "R1 ÄN 0 {Äx}\n.param äX=1k",
            lambda n: n.params.set("ÄX", "2k"),
            "R1 ÄN 0 {Äx}\n.param äX=2k",
        ),
    ],
)
def test_operations(before: str, edit: Any, after: str) -> None:
    assert _body(edit(_netlist(before))) == after


def test_names_address_elements_by_the_dialect_fold() -> None:
    netlist = _netlist("RÄ a 0 1k")
    assert _body(netlist.set_value("rä", "2k")) == "RÄ a 0 2k"
    assert _body(netlist.set_value("RÄ", "3k")) == "RÄ a 0 3k"


@pytest.mark.parametrize(
    ("before", "edit", "message"),
    [
        ("R1 a 0 1k", lambda n: n.set_param("R1", "foo", "1"), "does not parse"),
        ("R1 a 0 1k", lambda n: n.set_param("R1", "Rsr", "1"), "does not parse"),
        (".model d D(Is=1n)", lambda n: n.set_model_param("d", "Is", "x"), "does not parse"),
        (".model d D(Is=1n)", lambda n: n.set_model_param("d", "pn", "x"), "does not parse"),
        ("C1 a 0 1u V=6", lambda n: n.set_param("C1", "V", '"6.3"'), "does not parse"),
        ("I1 a 0 1m", lambda n: n.set_param("I1", "Rser", "1"), "does not parse"),
        ("R1 a 0 1k", lambda n: n.set_value("R1", "1k 2k"), "does not parse"),
        ("R1 a 0 1k", lambda n: n.set_value("R1", "R47"), "does not parse"),
        ("R1 a 0 1k\n.model rm R", lambda n: n.set_model("R1", "rm"), "LTspice has no R, C or L"),
        ("C1 a 0 1u", lambda n: n.set_model("C1", "nowhere"), "LTspice has no R, C or L"),
        ("L1 a 0 1m\n.model d D", lambda n: n.set_model("L1", "d"), "LTspice has no R, C or L"),
        ("R1 a 0 1k", lambda n: n.remove_value("R1"), "LTspice has no R, C or L"),
        ("D1 a 0 dm\n.model dm D", lambda n: n.remove_value("D1"), "only R, C and L"),
        ("X1 a s", lambda n: n.set_param("X1", "r", "1"), "set_instance_param"),
        ("K1 L1 L2 1", lambda n: n.set_param("K1", "m", "1"), "takes no parameters"),
    ],
)
def test_errors(before: str, edit: Any, message: str) -> None:
    with pytest.raises(EditError, match=message):
        edit(_netlist(before))


def test_add_and_replace_ltspice_directives() -> None:
    netlist = _netlist("R1 a 0 1k")
    assert _body(netlist.directives.set(".tran 1m startup")) == "R1 a 0 1k\n.tran 1m startup"
    assert _body(netlist.directives.add(".func f(x) {x}")) == "R1 a 0 1k\n.func f(x) {x}"
    assert _body(netlist.directives.add(".four 1k V(a)")) == "R1 a 0 1k\n.four 1k V(a)"
    assert _body(netlist.directives.add(".save V(a) Id(*)")) == "R1 a 0 1k\n.save V(a) Id(*)"
    tran = _netlist(".tran 1m").directives.set(".tran 1u 2m")
    assert _body(tran) == ".tran 1u 2m"
    temp = _netlist(".temp 27").directives.set(".temp 1 2 3")
    assert _body(temp) == ".temp 1 2 3"
    assert _body(netlist.add_include("h.inc")).startswith('.include "h.inc"\n')
    included = netlist.directives.add(".lib h.inc")
    assert _body(included).endswith(".lib h.inc")
    line = included.lines.find_all(type(included.lines[1].item))
    assert line


@pytest.mark.parametrize("text", [".control", ".foo", ".if (1)"])
def test_other_dialects_directives_do_not_parse(text: str) -> None:
    with pytest.raises(EditError, match="does not parse"):
        _netlist("R1 a 0 1k").directives.add(text)


@pytest.mark.parametrize(
    ("before", "text", "after"),
    [
        ("R1 a 0 {x}", ".step param x 1 2 1", "R1 a 0 {x}\n.step param x 1 2 1"),
        (".step param x 1 2 1", ".step param X list 1 2", ".step param X list 1 2"),
        (".step param x 1 2 1", ".step dec param x 1 100 5", ".step dec param x 1 100 5"),
        (".step param x 1 2 1", ".step param y 1 2 1", ".step param x 1 2 1\n.step param y 1 2 1"),
        (".step V1 1 2 1", ".step param V1 1 2 1", ".step V1 1 2 1\n.step param V1 1 2 1"),
        (".step temp 1 2 1", ".step TEMP list 0 27", ".step TEMP list 0 27"),
        (".step D dm(Is) 1 2 1", ".step d DM(IS) 3 4 1", ".step d DM(IS) 3 4 1"),
        (
            ".step D dm(Is) 1 2 1",
            ".step D dm(N) 3 4 1",
            ".step D dm(Is) 1 2 1\n.step D dm(N) 3 4 1",
        ),
    ],
)
def test_step_upsert(before: str, text: str, after: str) -> None:
    assert _body(_netlist(before).directives.set(text)) == after


def test_nested_steps_have_no_limit() -> None:
    netlist = _netlist("R1 a 0 1")
    for name in "abcde":
        netlist = netlist.directives.set(f".step param {name} 1 2 1")
    assert len(netlist.lines.find_all(StepDirective)) == 5


def test_two_lines_for_one_quantity_are_ambiguous() -> None:
    netlist = _netlist(".step param x 1 2 1\n.step param x 3 4 1")
    with pytest.raises(EditError, match="ambiguous"):
        netlist.directives.set(".step param x 5 6 1")
    replaced = netlist.directives.replace(netlist.lines[1], ".step param y 1 2 1")
    assert _body(replaced) == ".step param y 1 2 1\n.step param x 3 4 1"


def test_a_step_can_be_added_at_a_placement_and_removed() -> None:
    netlist = _netlist(".op")
    added = netlist.directives.add(".step temp 1 2 1", Placement.AFTER_TITLE)
    assert _body(added) == ".step temp 1 2 1\n.op"
    assert _body(added.directives.remove(added.lines[1])) == ".op"


def test_topology_is_still_protected() -> None:
    netlist = _netlist("R1 a 0 1k\n.include h.inc\n.op")
    with pytest.raises(TopologyError):
        netlist.directives.add("R2 a 0 1k")
    with pytest.raises(TopologyError):
        netlist.directives.remove(netlist.lines[1])
    from netlistmod import Edit, Span

    start = netlist.text.index("h.inc")
    with pytest.raises(TopologyViolation, match="opaque"):
        netlist.apply([Edit(Span(start, start + 5), "other.inc")])
    resistor = netlist.element("R1")
    with pytest.raises(TopologyViolation):
        netlist.apply([Edit(resistor.nodes[0].span, "A")])


def test_rkm_stays_off_on_the_result() -> None:
    edited = _netlist("R1 a 0 1k").set_value("R1", "2k2")
    assert not edited.rkm and edited.dialect is Dialect.LTSPICE
    assert not edited.diagnostics


def test_a_save_preserves_utf16(tmp_path: Path) -> None:
    netlist = Netlist.load(CORPUS / "encoding_samples" / "utf16le_bom.cir", dialect=Dialect.LTSPICE)
    assert netlist.source.bom
    path = tmp_path / "out.cir"
    netlist.set_value("R2", "3k3").save(path)
    assert path.read_bytes().startswith(b"\xff\xfe")
    assert "R2 out 0 3k3" in path.read_bytes().decode("utf-16-le")


def _diff(expected: bytes, actual: bytes) -> str:
    lines = difflib.unified_diff(
        expected.decode("utf-8").splitlines(keepends=True),
        actual.decode("utf-8").splitlines(keepends=True),
        "expected",
        "actual",
    )
    return "".join(repr(line) + "\n" for line in lines)


def _input(case: dict[str, Any]) -> Path:
    """A case's input: an authored file in the family, otherwise an export."""
    authored = GOLDEN / case["input"]
    return authored if authored.exists() else INPUTS / case["input"]


def _run(case: dict[str, Any]) -> Netlist:
    netlist = Netlist.load(_input(case), dialect=Dialect.LTSPICE)
    return apply_steps(netlist, case["steps"])


@pytest.mark.parametrize("name", sorted(CASES))
def test_golden_case(name: str) -> None:
    expected = (GOLDEN / CASES[name]["expected"]).read_bytes()
    actual = _run(CASES[name]).to_bytes()
    assert actual == expected, f"golden case {name} differs:\n{_diff(expected, actual)}"


@pytest.mark.parametrize("name", sorted(CASES))
def test_golden_output_keeps_the_input_topology(name: str) -> None:
    case = CASES[name]
    original = Netlist.load(_input(case), dialect=Dialect.LTSPICE)
    edited = Netlist.load(GOLDEN / case["expected"], dialect=Dialect.LTSPICE)
    assert edited.signature() == original.signature()


def test_the_cases_cover_the_task_list() -> None:
    operations = {step[0] for case in CASES.values() for step in case["steps"]}
    assert operations >= {
        "set_value",
        "set_formula",
        "set_param",
        "set_instance_param",
        "set_model_param",
        "set_dc",
        "set_ac",
        "set_coupling",
        "params.set",
        "directives.set",
        "directives.add",
        "directives.replace",
        "directives.remove",
        "add_include",
    }
    steps = [step for case in CASES.values() for step in case["steps"]]
    assert any(step[0] == "set_param" and step[2] == "Rser" for step in steps)
    assert any(step[0] == "directives.set" and step[1].startswith(".step") for step in steps)
