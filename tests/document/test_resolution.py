"""Scopes, symbol tables and reference resolution (M5 T4; scoping.md, decision 0006)."""

from __future__ import annotations

import pytest

from netlistmod import (
    Diode,
    Inductor,
    ModelStatement,
    MutualCoupling,
    Netlist,
    ParamAssignment,
    Reference,
    Resistor,
    SubcktDefinition,
    VoltageSource,
)
from tests.support.dialects import current_dialect


def _netlist(body: str, **options: bool) -> Netlist:
    return Netlist.from_text(f"title\n{body}\n.end\n", dialect=current_dialect(), **options)


def _refs(netlist: Netlist, kind: str | None = None) -> list[Reference]:
    return [ref for ref in netlist.references if kind is None or ref.kind == kind]


def _spelled(netlist: Netlist, ref: Reference) -> str:
    return netlist.slice(ref.span)


def test_scopes_are_definition_paths() -> None:
    netlist = _netlist(
        ".subckt amp a b\n.subckt inner x y\nR1 x y 1\n.ends\nR1 a b 1\n.ends\n"
        ".subckt AMP2 p q\nR1 p q 1\n.ends"
    )
    assert [scope.path for scope in netlist.scopes] == [(), ("amp",), ("amp", "inner"), ("amp2",)]
    inner = netlist.scope(("AMP", "Inner"))
    assert inner.display == ("amp", "inner")
    assert inner.parent is netlist.scope(("amp",))
    assert [scope.path for scope in inner.chain()] == [("amp", "inner"), ("amp",), ()]
    assert netlist.scope(("amp2",)).display == ("AMP2",)
    assert netlist.scope(("amp2",)).describe() == "subcircuit `AMP2`"
    assert netlist.scope().describe() == "top level"
    assert repr(inner) == "Scope(('amp', 'inner'))"
    assert isinstance(inner.definition, SubcktDefinition)
    with pytest.raises(KeyError, match="no subcircuit definition scope"):
        netlist.scope(("nope",))


def test_element_lookup_is_per_scope_and_case_insensitive() -> None:
    netlist = _netlist("R1 a b 1\n.subckt div a b\nr1 a b 2\nR2 b 0 1\n.ends")
    top = netlist.element("r1")
    local = netlist.element("R1", scope=("DIV",))
    assert isinstance(top, Resistor) and top.designator == "R1"
    assert local.designator == "r1"
    assert [element.designator for element in netlist.elements()] == ["R1"]
    assert [e.designator for e in netlist.elements(recursive=True)] == ["R1", "r1", "R2"]
    assert [e.designator for e in netlist.elements(("div",))] == ["r1", "R2"]
    with pytest.raises(KeyError, match="no element 'R2' in top level"):
        netlist.element("R2")


def test_symbol_tables_hold_every_definition_in_source_order() -> None:
    netlist = _netlist(
        ".param rx=1k RX=2k\n.model DM d\n.subckt div a b r2=1k\n.param q=1\nR1 a b 1\n.ends"
    )
    assert [a.value.text for a in netlist.params["rx"]] == ["1k", "2k"]
    assert isinstance(netlist.models["dm"][0], ModelStatement)
    assert list(netlist.subckts) == ["div"]
    div = netlist.scope(("div",))
    assert list(div.params) == ["r2", "q"]
    assert all(isinstance(a, ParamAssignment) for a in div.params["r2"])
    assert not div.models and not div.subckts
    assert list(div.elements) == ["r1"]


@pytest.mark.ngspice_only
def test_element_models_resolve_through_enclosing_scopes_in_any_order() -> None:
    netlist = _netlist(
        "D1 a 0 DMOD\nR1 a b rmod l=1u\n.subckt outer p q\n.subckt inner x y\nD2 x y dloc\n"
        "D3 x y dmod\n.ends\n.model DLOC d\n.ends\n.model dmod d\n.model rmod r"
    )
    models = _refs(netlist, "model")
    assert [(ref.name, ref.scope) for ref in models] == [
        ("DMOD", ()),
        ("rmod", ()),
        ("dloc", ("outer", "inner")),
        ("dmod", ("outer", "inner")),
    ]
    assert all(isinstance(ref.target, ModelStatement) for ref in models)
    assert models[2].target is netlist.scope(("outer",)).models["dloc"][0]
    assert isinstance(models[0].owner, Diode)
    assert [_spelled(netlist, ref) for ref in models] == ["DMOD", "rmod", "dloc", "dmod"]


def test_models_are_local_to_their_definition() -> None:
    netlist = _netlist(".subckt div a b\n.model dm d\nD1 a b dm\n.ends\nD2 out 0 dm")
    inside, outside = _refs(netlist, "model")
    assert inside.target is not None
    assert outside.target is None


def test_repeated_model_or_subckt_resolves_to_the_first() -> None:
    netlist = _netlist(
        "D1 a 0 dm\nX1 a b s\n.model dm d is=1\n.model dm d is=2\n"
        ".subckt s a b\nR1 a b 1\n.ends\n.subckt S a b\nR1 a b 2\n.ends"
    )
    model, subckt = _refs(netlist, "model")[0], _refs(netlist, "subckt")[0]
    assert model.target is netlist.models["dm"][0]
    assert subckt.target is netlist.subckts["s"][0]


def test_instances_resolve_their_subcircuit_and_its_defaults() -> None:
    netlist = _netlist(
        "X1 in out DIV r2=3k zz=1\n.subckt div a b r2=1k\nR1 a b 1k\nR2 b 0 {r2}\n.ends\n"
        "X2 in out nope r=1"
    )
    subckt, r2, zz, missing, r = [ref for ref in netlist.references if ref.kind != "param"]
    assert subckt.target is netlist.subckts["div"][0]
    assert r2.kind == "subckt_param" and r2.target is netlist.subckts["div"][0].params[0]
    assert _spelled(netlist, r2) == "r2"
    assert zz.kind == "subckt_param" and zz.target is None
    assert missing.kind == "subckt" and missing.target is None
    assert r.kind == "subckt_param" and r.target is None


def test_local_subckt_masks_a_global_one() -> None:
    netlist = _netlist(
        ".subckt outer a b\nX2 a b div\n.subckt div a b\nR1 a b 3k\n.ends\n.ends\n"
        ".subckt div a b\nR1 a b 1k\n.ends\nX1 in out div"
    )
    local, top = _refs(netlist, "subckt")
    assert local.target is netlist.scope(("outer",)).subckts["div"][0]
    assert top.target is netlist.subckts["div"][0]
    assert local.target is not top.target


def test_coupling_references_inductors_in_the_same_scope() -> None:
    netlist = _netlist(
        "L1 a 0 1u\nl2 b 0 1u\nk1 l1 L2 0.9\n.subckt t a b\nK1 L1 L3 0.5\nL3 a b 1\n.ends"
    )
    top = [ref for ref in _refs(netlist, "element") if ref.scope == ()]
    assert [ref.name for ref in top] == ["l1", "L2"]
    assert all(isinstance(ref.target, Inductor) for ref in top)
    assert isinstance(top[0].owner, MutualCoupling)
    local = [ref for ref in _refs(netlist, "element") if ref.scope == ("t",)]
    assert [ref.target is None for ref in local] == [True, False]


@pytest.mark.ngspice_only
def test_dc_sources_and_saved_currents_reference_elements() -> None:
    netlist = _netlist(
        "VIN in 0 1\nR1 in 0 1\n.dc vin 0 5 0.1 TEMP -15 75 5\n.dc r1 1 2 1\n"
        ".save i(VIN) i(vx) v(in) in vin#branch"
    )
    elements = _refs(netlist, "element")
    assert [(ref.name, ref.target is not None) for ref in elements] == [
        ("vin", True),
        ("r1", True),
        ("VIN", True),
        ("vx", False),
    ]
    assert isinstance(elements[0].target, VoltageSource)


@pytest.mark.ngspice_only
def test_formula_identifiers_resolve_to_parameters() -> None:
    netlist = _netlist(
        ".param gain=2 rx={gain*1k}\n"
        "R1 a b {V(a)*2+gain}\n"
        "V1 a 0 DC {rx} AC {gain} {time}\n"
        ".model dm d is={rx}\n"
        "D1 a 0 dm area='gain'\n"
        ".tran {rx} 1u\n"
        '.subckt div a b r2={rx} s="text"\n'
        "R2 b 0 {r2+sqrt(gain)}\n"
        ".ends\n"
        "X1 a b div r2={2*rx}\n"
        ".options reltol={gain}\n"
        ".temp {gain}\n"
        ".ic v(a)={rx}"
    )
    params = _refs(netlist, "param")
    assert [ref.name for ref in params] == [
        "gain",
        "gain",
        "rx",
        "gain",
        "rx",
        "gain",
        "rx",
        "rx",
        "r2",
        "gain",
        "rx",
        "gain",
        "gain",
        "rx",
    ]
    assert [_spelled(netlist, ref) for ref in params] == [ref.name for ref in params]
    assert all(ref.target is not None for ref in params)
    r2 = next(ref for ref in params if ref.name == "r2")
    assert r2.scope == ("div",)
    assert r2.target is netlist.subckts["div"][0].params[0]


def test_parameters_mask_globals_and_the_last_assignment_wins() -> None:
    netlist = _netlist(
        ".param rx=1k\n.param rx=3k\nR1 a b {rx}\n.subckt div a b\n.param rx=1k\nR1 a b {rx}\n"
        "R2 a b {RX}\n.ends\n.subckt other a b\nR1 a b {rx}\n.ends"
    )
    top, local, upper, other = _refs(netlist, "param")
    assert top.target is netlist.params["rx"][1]
    assert local.target is netlist.scope(("div",)).params["rx"][0]
    assert upper.target is local.target
    assert other.target is netlist.params["rx"][1]


def test_references_to_param_follow_masking() -> None:
    netlist = _netlist(
        ".param rx=1k\nR1 a b {rx}\n.subckt div a b\n.param rx=1k\nR1 a b {rx}\n.ends\n"
        ".subckt other a b\nR1 a b {rx*2}\n.ends"
    )
    top = netlist.references_to_param("RX")
    assert [ref.scope for ref in top] == [(), ("other",)]
    assert [ref.scope for ref in netlist.references_to_param("rx", ("div",))] == [("div",)]
    assert netlist.references_to_param("nope") == ()


@pytest.mark.ngspice_only
def test_unresolved_and_unparsed_formulas() -> None:
    netlist = _netlist("R1 a b {missing}\nR2 a b {a#b}\nR3 a b {2*pi}")
    params = _refs(netlist, "param")
    assert [(ref.name, ref.target) for ref in params] == [("missing", None), ("pi", None)]


def test_resolve_returns_the_target_of_this_netlists_references() -> None:
    netlist = _netlist("D1 a 0 dm\n.model dm d")
    (reference,) = netlist.references
    assert netlist.resolve(reference) is netlist.models["dm"][0]
    stranger = _netlist("D1 a 0 dm\n.model dm d").references[0]
    with pytest.raises(ValueError):
        netlist.resolve(stranger)


@pytest.mark.ngspice_only
def test_items_in_opaque_blocks_are_not_seen() -> None:
    netlist = _netlist(".if (1)\n.model dm d\nR9 a b 1\n.endif\nD1 a 0 dm")
    assert netlist.references[0].target is None
    assert "r9" not in netlist.scope().elements
