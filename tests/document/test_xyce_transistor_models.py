"""The document layer on xyce transistors (X-M4 B4; decision 0031 items 5 to 8; xm4-tasks 5.1
points 4, 11 to 20): the model types of Q, M, J and Z, binned model names on M, and the node
count against the model's LEVEL (`NODE_COUNT_MISMATCH`, from `model/xyce-levels.json`)."""

from __future__ import annotations

from typing import Any

import pytest

from netlistmod import DiagnosticCode, Dialect, ModelStatement, Netlist
from netlistmod.dialects import _XYCE
from netlistmod.document.index import Index, Reference, _model_level, model_binning
from netlistmod.model.xyce_levels import LevelNodes, _read, default_level, level_nodes


def _netlist(body: str, dialect: Dialect = _XYCE) -> Netlist:
    return Netlist.from_text(f"t\n{body}.end\n", dialect=dialect)


def _bins(body: str) -> tuple[Index, Reference]:
    """The index of an xyce netlist, which holds `model_bins`, and its one model reference."""
    netlist = _netlist(body)
    index = Index(netlist.parse_result.items, netlist.source, _XYCE)
    (reference,) = [r for r in index.references if r.kind == "model"]
    return index, reference


def _findings(netlist: Netlist, code: DiagnosticCode) -> list[tuple[int, str]]:
    return [(d.line, d.message) for d in netlist.diagnostics if d.code is code]


def _codes(netlist: Netlist) -> list[tuple[int, DiagnosticCode]]:
    return [(d.line, d.code) for d in netlist.diagnostics]


# Model types (decision 0031 item 6; 5.1 points 13 and 14).


@pytest.mark.parametrize(
    ("line", "model"),
    [
        ("Q1 c b 0 qm", ".model qm NPN"),
        ("Q1 c b 0 qm", ".model qm pnp"),
        ("M1 d g 0 0 mm", ".model mm NMOS"),
        ("M1 d g 0 0 mm", ".model mm pmos level=18"),
        ("J1 d g 0 jm", ".model jm NJF"),
        ("J1 d g 0 jm", ".model jm pjf"),
        ("Z1 d g 0 zm", ".model zm NMF"),
        ("Z1 d g 0 zm", ".model zm pmf"),
    ],
)
def test_each_transistor_takes_its_xyce_types(line: str, model: str) -> None:
    assert _netlist(f"{line}\n{model}\n").diagnostics == ()


@pytest.mark.parametrize(
    ("line", "model", "takes"),
    [
        ("Q1 c b 0 qm", ".model qm nmos", "`NPN`, `PNP`"),
        ("J1 d g 0 jm", ".model jm nmf", "`NJF`, `PJF`"),
        ("Z1 d g 0 zm", ".model zm njf", "`NMF`, `PMF`"),
        ("M1 d g 0 0 mm", ".model mm npn", "`NMOS`, `PMOS`"),
    ],
)
def test_a_wrong_type_says_xyce_stops(line: str, model: str, takes: str) -> None:
    ((number, message),) = _findings(
        _netlist(f"{line}\n{model}\n"), DiagnosticCode.MODEL_TYPE_MISMATCH
    )
    assert number == 2
    assert f"takes a model of type {takes}" in message
    assert "Xyce 7.10 stops on the line (it finds no valid model card)" in message
    assert ("a VDMOS is an `NMOS` or `PMOS` model with `LEVEL=18`" in message) == line.startswith(
        "M"
    )


def test_vdmos_is_not_an_xyce_type() -> None:
    # Xyce's VDMOS is NMOS or PMOS at LEVEL=18 (Table 2-36 p180); `vdmos` stops on M.
    ((_, message),) = _findings(
        _netlist("M1 d g 0 0 vm\n.model vm vdmos\n"), DiagnosticCode.MODEL_TYPE_MISMATCH
    )
    assert "of type `vdmos`" in message and "`LEVEL=18`" in message


def test_ngspice_and_ltspice_keep_their_messages() -> None:
    for dialect in (Dialect.NGSPICE, Dialect.LTSPICE):
        ((_, message),) = _findings(
            _netlist("Q1 c b 0 qm\n.model qm nmos\n", dialect), DiagnosticCode.MODEL_TYPE_MISMATCH
        )
        assert "Xyce" not in message and "VDMOS" not in message


# Binning (decision 0031 items 7 and 8; 5.1 points 15 to 18).

_BINS = ".model nch.1 nmos lmin=1u lmax=2u\n.model nch.2 nmos lmin=2u lmax=4u\n"


def test_a_set_of_bins_resolves_to_its_first_bin() -> None:
    body = f"M1 d g 0 0 nch L=1u W=5u\n{_BINS}"
    netlist = _netlist(body)
    assert netlist.diagnostics == ()
    (reference,) = [r for r in netlist.references if r.kind == "model"]
    assert netlist.resolve(reference) is netlist.lines[2].item
    index, reference = _bins(body)
    assert reference.target is index.lines[2].item
    assert index.model_bins[reference] == (index.lines[2].item, index.lines[3].item)


@pytest.mark.parametrize("suffix", ["5", "a", "x.2", "BIN"])
def test_any_non_empty_suffix_is_a_bin(suffix: str) -> None:
    # G1 point 15 (a): Xyce reads any suffix, not only a number; names are folded.
    netlist = _netlist(f"M1 d g 0 0 NCH\n.model nch.{suffix} nmos\n")
    assert netlist.diagnostics == ()


def test_an_empty_suffix_or_another_prefix_is_no_bin() -> None:
    netlist = _netlist("M1 d g 0 0 nch\n.model nch. nmos\n.model nchx.1 nmos\n")
    assert _codes(netlist) == [(2, DiagnosticCode.UNRESOLVED_MODEL)]


def test_an_exact_name_anywhere_in_the_chain_wins_over_a_set() -> None:
    text = f".subckt s d g\nM1 d g 0 0 nch\n{_BINS}.ends\nX1 a b s\n.model nch pmos\n"
    index, reference = _bins(text)
    assert isinstance(reference.target, ModelStatement)
    assert reference.target.name == "nch"
    assert reference not in index.model_bins


def test_a_set_is_gathered_across_the_scope_chain() -> None:
    text = (
        ".subckt s d g\nM1 d g 0 0 nch\n.model nch.2 nmos\n.ends\nX1 a b s\n"
        ".model nch.1 nmos\n.model nch.2 pmos\n"
    )
    index, reference = _bins(text)
    bins = index.model_bins[reference]
    # The body's bin first, then the top level's other bin; the shadowed `nch.2` is left out.
    assert [(m.name, m.model_type) for m in bins] == [("nch.2", "nmos"), ("nch.1", "nmos")]


def test_a_body_set_is_not_visible_from_the_top_level() -> None:
    text = ".subckt s d g\n.model nch.1 nmos\n.ends\nM1 d g 0 0 nch\n"
    assert _codes(_netlist(text)) == [(5, DiagnosticCode.UNRESOLVED_MODEL)]


@pytest.mark.parametrize("letter", ["Q1 c b 0", "J1 d g 0", "Z1 d g 0"])
def test_only_m_bins(letter: str) -> None:
    # A binned name on Q, J or Z stops Xyce as a missing model (5.1 point 15).
    netlist = _netlist(f"{letter} nch\n.model nch.1 npn\n")
    assert _codes(netlist) == [(2, DiagnosticCode.UNRESOLVED_MODEL)]


def test_ngspice_does_not_bin_by_name() -> None:
    netlist = _netlist("M1 d g 0 0 nch\n.model nch.1 nmos\n", Dialect.NGSPICE)
    assert _codes(netlist) == [(2, DiagnosticCode.UNRESOLVED_MODEL)]


@pytest.mark.parametrize(
    ("options", "bins"),
    [
        (".options parser model_binning=false\n", False),
        (".OPTIONS PARSER MODEL_BINNING=0\n", False),
        (".OPTIONS PARSER MODEL_BINNING=0.0\n", False),
        (".options parser model_binning=true\n", True),
        (".options parser model_binning=1\n", True),
        (".options parser model_binning=true\n.options parser model_binning=false\n", True),
        (".options device temp=27\n", True),
        ("", True),
    ],
)
def test_a_literal_false_turns_binning_off(options: str, bins: bool) -> None:
    # Xyce uses the first value of a repeated option (an expression is refused in this package).
    netlist = _netlist(f"{options}M1 d g 0 0 nch\n.model nch.1 nmos\n")
    assert model_binning(netlist.scope()) is bins
    unresolved = [d for d in netlist.diagnostics if d.code is DiagnosticCode.UNRESOLVED_MODEL]
    assert bool(unresolved) is not bins


def test_a_model_parameter_target_is_looked_up_by_its_exact_name() -> None:
    # `nch:vto` stops Xyce (5.1 point 16): a `head:param` target never names a set.
    netlist = _netlist(f"M1 d g 0 0 nch\n{_BINS}.step nch:vto 0 1 0.5\n.op\n")
    assert _codes(netlist) == [(5, DiagnosticCode.UNRESOLVED_ELEMENT)]


def test_a_wrong_type_is_reported_for_each_bin() -> None:
    text = "M1 d g 0 0 nch\n.model nch.1 nmos\n.model nch.2 npn\n.model nch.3 njf\n"
    found = _findings(_netlist(text), DiagnosticCode.MODEL_TYPE_MISMATCH)
    assert [message.split(",")[0] for _, message in found] == [
        "`M1` refers to model set `nch`",
        "`M1` refers to model set `nch`",
    ]
    assert "whose bin `nch.2` has type `npn`" in found[0][1]
    assert "whose bin `nch.3` has type `njf`" in found[1][1]


def test_a_repeated_bin_is_a_duplicate_definition() -> None:
    text = "M1 d g 0 0 nch\n.model nch.1 nmos\n.model NCH.1 nmos\n"
    assert _codes(_netlist(text)) == [(4, DiagnosticCode.DUPLICATE_DEFINITION)]


# The level table (decision 0031 item 5; 5.1 points 11 and 20).


def test_the_level_table_holds_the_observed_counts() -> None:
    assert default_level() == 1
    assert level_nodes("BipolarTransistor", 1) == LevelNodes((3, 4), None, "stops")
    assert level_nodes("BipolarTransistor", 504) == LevelNodes((4, 4), None, None)
    assert level_nodes("Mosfet", 10) == LevelNodes((4, 6), (5, 7), "stops")
    assert level_nodes("Mosfet", 70).range(True) == (7, 7)  # type: ignore[union-attr]
    assert level_nodes("Mosfet", 1).range(True) == (4, 4)  # type: ignore[union-attr]
    assert level_nodes("Mosfet", 2000) == LevelNodes((3, 3), None, "dropped")
    assert level_nodes("Jfet", 2) == LevelNodes((3, 3), None, None)
    assert level_nodes("Mosfet", 5) is None
    assert level_nodes("Resistor", 1) is None


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({}, "must give a `default_level`"),
        ({"default_level": 1, "Mosfet": []}, "must map levels"),
        ({"default_level": 1, "Mosfet": {"1": {}}}, "must give its `nodes`"),
        ({"default_level": 1, "Mosfet": {"1": {"nodes": [4]}}}, "is [least, most]"),
        ({"default_level": 1, "Mosfet": {"1": {"nodes": [5, 4]}}}, "is [least, most]"),
        ({"default_level": 1, "Mosfet": {"1": {"nodes": [4, 4], "extra": "x"}}}, "`extra`"),
    ],
)
def test_a_malformed_level_table_is_refused(data: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message.replace("[", r"\[").replace("]", r"\]")):
        _read(data)


@pytest.mark.parametrize(
    ("params", "level"),
    [
        ("", 1),
        ("level=10", 10),
        ("LEVEL=10.0", 10),
        ("level=1e1", 10),
        ("level={10}", None),
        ("level='10'", None),
        ("level=10.5", None),
        ("level=10k", None),
        ("LEVEL=10", 10),
    ],
)
def test_a_models_level_is_its_last_plain_integer(params: str, level: int | None) -> None:
    netlist = _netlist(f".model mm nmos {params}\n")
    (model,) = netlist.models["mm"]
    assert _model_level(model, 1, _XYCE) == level


# NODE_COUNT_MISMATCH (decision 0031 item 5; 5.1 points 4, 11, 12 and 20).


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            "M1 d g 0 mm\n.model mm nmos\n",
            "`M1` connects 3 nodes, but model `mm` is level 1, which takes 4 nodes; Xyce 7.10 "
            "stops on the line",
        ),
        (
            "M1 d g 0 0 n5 n6 mm\n.model mm nmos level=3\n",
            "`M1` connects 6 nodes, but model `mm` is level 3, which takes 4 nodes; Xyce 7.10 "
            "silently drops nodes 5 to 6 (`n5`, `n6`)",
        ),
        (
            "M1 d g 0 0 mm\n.model mm nmos level=2000\n",
            "`M1` connects 4 nodes, but model `mm` is level 2000, which takes 3 nodes; Xyce 7.10 "
            "silently drops node 4 (`0`)",
        ),
        (
            "Q1 c b 0 s t qm\n.model qm npn level=11\n",
            "`Q1` connects 5 nodes, but model `qm` is level 11, which takes 3 to 4 nodes; Xyce "
            "7.10 joins node 5 (`t`) to internal nodes of the device, which makes a different "
            "circuit",
        ),
        (
            "Q1 c b 0 s t qm\n.model qm npn\n",
            "`Q1` connects 5 nodes, but model `qm` is level 1, which takes 3 to 4 nodes; Xyce "
            "7.10 stops on the line",
        ),
        (
            "Q1 c b 0 s t qm\n.model qm npn level=504\n",
            "`Q1` connects 5 nodes, but model `qm` is level 504, which takes 4 nodes; what Xyce "
            "7.10 does with node 5 (`t`) was not observed",
        ),
        (
            "M1 d g 0 0 n5 mm TNODEOUT=1\n.model mm nmos level=70\n",
            "`M1` connects 5 nodes, but model `mm` is level 70, which takes 7 nodes with "
            "`TNODEOUT=`; Xyce 7.10 stops on the line",
        ),
        (
            "M1 d g 0 0 n5 n6 n7 mm\n.model mm nmos level=10\n",
            "`M1` connects 7 nodes, but model `mm` is level 10, which takes 4 to 6 nodes; Xyce "
            "7.10 stops on the line",
        ),
    ],
)
def test_a_count_outside_the_level_is_a_warning(body: str, expected: str) -> None:
    netlist = _netlist(body)
    (finding,) = netlist.diagnostics
    assert (finding.code, finding.severity, finding.message) == (
        DiagnosticCode.NODE_COUNT_MISMATCH,
        "warning",
        expected,
    )


def test_the_warning_covers_the_extra_nodes() -> None:
    (finding,) = _netlist("M1 d g 0 0 n5 n6 mm\n.model mm nmos\n").diagnostics
    assert (finding.line, finding.column) == (2, 12)
    assert finding.span.end - finding.span.start == len("n5 n6")


@pytest.mark.parametrize(
    "body",
    [
        "M1 d g 0 0 mm\n.model mm nmos\n",
        "M1 d g 0 0 n5 n6 mm\n.model mm nmos level=10\n",
        "M1 d g 0 0 n5 n6 n7 mm TNODEOUT=1\n.model mm nmos level=10\n",
        "M1 d g 0 0 n5 n6 n7 mm tnodeout=0\n.model mm nmos level=70450\n",
        "M1 d g 0 mm\n.model mm nmos level=2001\n",
        "Q1 c b 0 qm\n.model qm npn\n",
        "Q1 c b 0 s t qm\n.model qm npn level=234\n",
        "J1 d g 0 jm\n.model jm njf level=2\n",
        # Unknown level, or unresolved model: silent.
        "M1 d g 0 mm\n.model mm nmos level={lv}\n.param lv=1\n",
        "M1 d g 0 mm\n.model mm nmos level=5\n",
        "M1 d g 0 mm\n.include 'models.lib'\n",
    ],
)
def test_a_count_the_level_takes_or_an_unknown_level_is_silent(body: str) -> None:
    netlist = _netlist(body)
    assert DiagnosticCode.NODE_COUNT_MISMATCH not in [d.code for d in netlist.diagnostics]


def test_each_bin_with_a_known_level_is_checked_by_name() -> None:
    text = (
        "M1 d g 0 0 n5 nch\n.model nch.1 nmos level=10\n.model nch.2 nmos\n"
        ".model nch.3 nmos level={x}\n.param x=1\n"
    )
    found = _findings(_netlist(text), DiagnosticCode.NODE_COUNT_MISMATCH)
    assert found == [
        (
            2,
            "`M1` connects 5 nodes, but bin `nch.2` of model set `nch` is level 1, which takes 4 "
            "nodes; Xyce 7.10 silently drops node 5 (`n5`)",
        )
    ]


@pytest.mark.parametrize(
    ("body", "node"),
    [
        ("Q1 c b 0 s qn\n.model qn npn\n.model s npn\n", "s"),
        ("Q1 c b 0 s qn\n.model qn npn\n.model S pnp\n", "s"),
        ("M1 d g 0 0 b nm\n.model nm nmos level=10\n.model b nmos\n", "b"),
        ("M1 d g 0 0 b nm\n.model nm nmos level=10\n.model b.1 nmos\n", "b"),
    ],
)
def test_a_node_naming_a_model_that_takes_the_count_so_far_is_a_warning(
    body: str, node: str
) -> None:
    # Xyce ends the nodes at the first name that is a model whose level takes the count so far
    # (5.1 point 4), so it takes the node as the model; the line's own model is not checked.
    (finding,) = _netlist(body).diagnostics
    assert finding.code is DiagnosticCode.NODE_COUNT_MISMATCH
    assert finding.message.startswith(f"node `{node}` of `")
    assert f"takes `{node}` as the model" in finding.message
    assert finding.span.end - finding.span.start == 1


@pytest.mark.parametrize(
    "body",
    [
        # Level 1 M takes 4 nodes, so a model at the fourth place is not taken there.
        "M1 d g 0 b nm\n.model nm nmos\n.model b nmos\n",
        # The model's level is unknown.
        "Q1 c b 0 s qn\n.model qn npn\n.model s npn level={1}\n",
        # A model of a type the letter does not take: Xyce runs the line (X-M4 R1).
        "Q1 c b 0 rx qn\n.model qn npn\n.model rx r\n",
        "M1 d g 0 0 dx nm\n.model nm nmos level=10\n.model dx d\n",
    ],
)
def test_a_node_naming_a_model_of_another_count_is_silent(body: str) -> None:
    netlist = _netlist(body)
    assert DiagnosticCode.NODE_COUNT_MISMATCH not in [d.code for d in netlist.diagnostics]


def test_the_topology_stays_the_nodes_written() -> None:
    # P4: the warning changes nothing that the topology reads.
    netlist = _netlist("M1 d g 0 0 n5 n6 mm\n.model mm nmos\n")
    assert [node.name for node in netlist.element("M1").nodes] == ["d", "g", "0", "0", "n5", "n6"]
    assert {net.name for net in netlist.nets()} >= {"n5", "n6"}


def test_ngspice_counts_by_letter_only() -> None:
    netlist = _netlist("M1 d g 0 0 mm\n.model mm nmos level=2000\n", Dialect.NGSPICE)
    assert netlist.diagnostics == ()
