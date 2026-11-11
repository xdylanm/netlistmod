"""Edits on the special and mixed-signal devices and on a code model's values (M17 T8; decision
0020 item 9). The golden diffs are the ``special*`` cases of both ``edits_golden`` families."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from netlistmod import Dialect, EditError, Netlist
from tests.support.dialects import ltspice_only, ngspice_only

_NG = (
    "title\nV1 in 0 1\nVs in x 0\na1 in out amp\na2 %vnam Vs out2 amp\nN1 out 0 rmod w=1u\n"
    ".model amp gain(gain=5)\n.model sum summer(in_gain=[1 ; first\n+ 1])\n"
    ".model rmod r2_cmc(rsh=200)\n.model dm d\n.end\n"
)
_LT = (
    "title\nV1 in 0 1\nA1 in 0 0 0 0 nq q 0 BUF Vhigh=5\n"
    "@1 in q zm fstart=1k fend=10k flist=1k ; first\n+ 2k 5k\n&1 q 0 in 0\n.end\n"
)


def _ng() -> Netlist:
    return Netlist.from_text(_NG, dialect=Dialect.NGSPICE)


def _lt() -> Netlist:
    return Netlist.from_text(_LT, dialect=Dialect.LTSPICE)


@ngspice_only
@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda n: n.set_param("a1", "gain", "2"), "use set_model_param"),
        (lambda n: n.remove_param("a1", "gain"), "use remove_model_param"),
        (lambda n: n.set_value("a1", "2"), "use set_model_param"),
        (lambda n: n.set_value("N1", "2"), "use set_param"),
        (lambda n: n.set_model("a1", "dm"), "not a built-in SPICE type (a code model's type)"),
        (lambda n: n.set_model("N1", "dm"), "an OSDI module's type"),
        (lambda n: n.set_model("N1", "nowhere"), "is not defined"),
        (lambda n: n.remove_param("N1", "l"), "has no parameter `l`"),
        (lambda n: n.remove_model_param("sum", "in_gain"), "holds the comment `; first`"),
        (lambda n: n.set_model_param("sum", "in_gain", "[1 2 3]"), "has 2 values, not 3"),
        (lambda n: n.set_model_param("dm", "is", "[1 2]"), "a vector for `is=` on a `d` model"),
    ],
)
def test_ngspice_refusals(edit: Callable[[Netlist], object], message: str) -> None:
    with pytest.raises(EditError, match=message.replace("(", r"\(").replace(")", r"\)")):
        edit(_ng())


@ngspice_only
def test_a_code_model_or_osdi_model_may_be_set_to_another_open_type() -> None:
    edited = _ng().set_model("a1", "sum").set_model("N1", "rmod")
    assert edited.element("a1").model.model_name == "sum"  # type: ignore[attr-defined]


@ltspice_only
@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda n: n.set_param("&1", "x", "1"), "four nodes and no parameters"),
        (lambda n: n.remove_param("&1", "x"), "takes no parameters"),
        (lambda n: n.set_value("A1", "1"), "use set_param"),
        (lambda n: n.set_value("@1", "1"), "use set_param"),
        (lambda n: n.set_value("&1", "1"), "has no value slot"),
        (lambda n: n.set_model("A1", "OTA"), "is not a model and is not editable"),
        (lambda n: n.set_param("@1", "zm", "1"), "is a flag, which is not editable"),
        (lambda n: n.remove_param("@1", "zm"), "`zm` of `@1` is a flag, which is not editable"),
        (lambda n: n.remove_param("@1", "ZM"), "`zm` of `@1` is a flag, which is not editable"),
        (lambda n: n.set_param("@1", "flist", "1k"), "holds the comment `; first`"),
        (lambda n: n.remove_param("@1", "flist"), "holds the comment `; first`"),
        (lambda n: n.set_param("@1", "foo", "1"), "does not"),
        (lambda n: n.set_param("A1", "Vhigh", "x"), "does not"),
    ],
)
def test_ltspice_refusals(edit: Callable[[Netlist], object], message: str) -> None:
    with pytest.raises(EditError, match=message):
        edit(_lt())


@ltspice_only
def test_an_analyzer_net_and_list_are_set_whole() -> None:
    text = "title\nV1 in 0 1\n@1 in q flist=1k 2k refnode=in\n.end\n"
    edited = Netlist.from_text(text, dialect=Dialect.LTSPICE)
    edited = edited.set_param("@1", "flist", "1k 2k 5k").set_param("@1", "intnode", "q")
    assert "@1 in q flist=1k 2k 5k refnode=in intnode=q\n" in edited.source.text


_NG_EDITS: list[Callable[[Netlist, str], Netlist]] = [
    lambda n, v: n.set_param("N1", "l", v),
    lambda n, v: n.set_param("N1", "m", v),
    lambda n, v: n.set_model_param("amp", "gain", v),
    lambda n, v: n.set_model_param("sum", "in_gain", f"[{v} {v}]"),
]
_LT_EDITS: list[Callable[[Netlist, str], Netlist]] = [
    lambda n, v: n.set_param("A1", "Vhigh", v),
    lambda n, v: n.set_param("A1", "Td", v),
    lambda n, v: n.set_param("@1", "fend", v),
    lambda n, v: n.set_param("@1", "acmag", v),
]
_VALUES = st.sampled_from(["1", "2.5", "10k", "1e-3", "{p}", "-4m"])


@ngspice_only
@settings(max_examples=40, deadline=None)
@given(edit=st.sampled_from(_NG_EDITS), value=_VALUES)
def test_no_ngspice_edit_changes_the_signature(
    edit: Callable[[Netlist, str], Netlist], value: str
) -> None:
    netlist = _ng()
    assert edit(netlist, value).signature() == netlist.signature()


@ltspice_only
@settings(max_examples=40, deadline=None)
@given(edit=st.sampled_from(_LT_EDITS), value=_VALUES)
def test_no_ltspice_edit_changes_the_signature(
    edit: Callable[[Netlist, str], Netlist], value: str
) -> None:
    netlist = _lt()
    assert edit(netlist, value).signature() == netlist.signature()
