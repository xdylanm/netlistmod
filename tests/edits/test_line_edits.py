"""Edits of the transmission lines, and remove_param and remove_model_param on every family
(M16 T8 and T8b, decision 0019). Golden diffs are in ``tests/corpus/*/edits_golden`` (the
``lines_*`` cases)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from netlistmod import EditError, Netlist
from tests.support.dialects import current_dialect, is_ltspice, ltspice_only, ngspice_only

Operation = Callable[[Netlist], Netlist]

_LINES = (
    "title\nV1 in 0 1\nR1 in a 50\nT1 a 0 b 0 Z0=50 TD=1n\nR2 b 0 50\nO1 a 0 c 0 lmod\n"
    "U1 a d 0 umod L=5 N=6\n.model lmod LTRA(R=1 L=50n C=20p len=1)\n"
    ".model lmod2 LTRA(R=2 L=50n C=20p len=1)\n.model umod URC(Rperl=10 Cperl=1p)\n"
    ".model umod2 URC(Rperl=20 Cperl=1p)\n.model dm D\n.end\n"
)


def _netlist(text: str = _LINES) -> Netlist:
    return Netlist.from_text(text, dialect=current_dialect())


def _line(netlist: Netlist, designator: str) -> str:
    span = netlist.element(designator).span
    return netlist.source.text[span.start : span.end].rstrip("\r\n")


@pytest.mark.parametrize(
    ("edit", "designator", "after"),
    [
        (lambda n: n.set_param("T1", "z0", "75"), "T1", "T1 a 0 b 0 Z0=75 TD=1n"),
        (lambda n: n.set_param("T1", "Zo", "75"), "T1", "T1 a 0 b 0 Z0=75 TD=1n"),
        (lambda n: n.set_param("T1", "td", "2n"), "T1", "T1 a 0 b 0 Z0=50 TD=2n"),
        (lambda n: n.set_param("U1", "l", "10"), "U1", "U1 a d 0 umod L=10 N=6"),
        (lambda n: n.set_param("U1", "n", "{k}"), "U1", "U1 a d 0 umod L=5 N={k}"),
        (lambda n: n.set_model("O1", "lmod2"), "O1", "O1 a 0 c 0 lmod2"),
        (lambda n: n.set_model("U1", "umod2"), "U1", "U1 a d 0 umod2 L=5 N=6"),
        (lambda n: n.remove_param("U1", "n"), "U1", "U1 a d 0 umod L=5"),
    ],
)
def test_line_edits(edit: Operation, designator: str, after: str) -> None:
    netlist = _netlist()
    edited = edit(netlist)
    assert _line(edited, designator) == after
    assert edited.signature() == netlist.signature()


def test_the_written_spelling_of_the_impedance_is_kept() -> None:
    netlist = _netlist(_LINES.replace("Z0=50", "Zo=50"))
    assert _line(netlist.set_param("T1", "z0", "75"), "T1") == "T1 a 0 b 0 Zo=75 TD=1n"
    assert _line(netlist.set_param("T1", "ZO", "75"), "T1") == "T1 a 0 b 0 Zo=75 TD=1n"


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda n: n.set_param("O1", "len", "2"), "takes no parameter"),
        (lambda n: n.remove_param("O1", "len"), "takes no parameter"),
        (lambda n: n.set_value("O1", "2"), "use set_model_param"),
        (lambda n: n.set_value("T1", "2"), "use set_param"),
        (lambda n: n.set_value("U1", "2"), "use set_param"),
        (lambda n: n.set_model("T1", "lmod"), "lossless transmission line and has no model"),
        (lambda n: n.set_model("O1", "umod"), "takes a model of type `LTRA`"),
        (lambda n: n.set_model("U1", "dm"), "takes a model of type `URC`"),
        (lambda n: n.set_model("U1", "nomod"), "is not defined"),
        (lambda n: n.set_param("T1", "nl", "0.1"), "does not parse"),
        (lambda n: n.remove_param("T1", "z0"), "must be given"),
        (lambda n: n.remove_param("T1", "td"), "length must be given"),
        (lambda n: n.remove_param("U1", "l"), "`l=` must be given"),
        (lambda n: n.remove_param("U1", "m"), "has no parameter `m`"),
        (lambda n: n.remove_model_param("lmod", "x"), "has no parameter `x`"),
        (lambda n: n.remove_model_param("nomod", "x"), "no model `nomod`"),
    ],
)
def test_line_edit_errors(edit: Operation, message: str) -> None:
    with pytest.raises(EditError, match=message.replace("(", r"\(").replace("`", "`")):
        edit(_netlist())


@ngspice_only
def test_td_beside_f_is_refused_by_verification() -> None:
    netlist = _netlist(_LINES.replace("TD=1n", "F=100meg"))
    with pytest.raises(EditError, match="as `TD=` and as `F=`"):
        netlist.set_param("T1", "td", "1n")


@ngspice_only
def test_a_batch_switches_the_length_form() -> None:
    netlist = _netlist()
    with netlist.batch() as batch:
        batch.set_param("T1", "f", "100meg")
        batch.set_param("T1", "nl", "0.1")
        batch.remove_param("T1", "td")
    assert _line(batch.result, "T1") == "T1 a 0 b 0 Z0=50 f=100meg nl=0.1"
    with netlist.batch() as batch:
        batch.remove_param("T1", "td")
        batch.set_param("T1", "f", "100meg")
    assert _line(batch.result, "T1") == "T1 a 0 b 0 Z0=50 f=100meg"


@ngspice_only
def test_ic_is_set_and_removed_whole() -> None:
    netlist = _netlist(_LINES.replace("TD=1n", "TD=1n IC=0,0,0,0"))
    assert _line(netlist.set_param("T1", "ic", "1, 0, 1, 0"), "T1") == (
        "T1 a 0 b 0 Z0=50 TD=1n IC=1, 0, 1, 0"
    )
    assert _line(netlist.remove_param("T1", "ic"), "T1") == "T1 a 0 b 0 Z0=50 TD=1n"
    with pytest.raises(EditError, match="holds 2 values"):
        netlist.set_param("T1", "ic", "0,0")


_NG_YP = (
    "title\nV1 in 0 1\nR1 in a 50\nY1 a 0 b 0 ymod len=1\nP1 a 0 c 0 pmod\n"
    ".model ymod TXL R=1 L=50n G=0 C=20p length=1\n.model ymod2 TXL R=2 L=50n G=0 C=20p length=1\n"
    ".model pmod CPL length=1\n+R=1\n+L=50n\n+G=0\n+C=20p\n.model dm D\n.end\n"
)


@ngspice_only
@pytest.mark.parametrize(
    ("edit", "designator", "after"),
    [
        (lambda n: n.set_param("Y1", "len", "2"), "Y1", "Y1 a 0 b 0 ymod len=2"),
        (lambda n: n.remove_param("Y1", "len"), "Y1", "Y1 a 0 b 0 ymod"),
        (lambda n: n.set_param("P1", "len", "2"), "P1", "P1 a 0 c 0 pmod len=2"),
        (lambda n: n.set_model("Y1", "ymod2"), "Y1", "Y1 a 0 b 0 ymod2 len=1"),
    ],
)
def test_y_and_p_edits(edit: Operation, designator: str, after: str) -> None:
    netlist = _netlist(_NG_YP)
    assert _line(edit(netlist), designator) == after


@ngspice_only
def test_y_and_p_refusals() -> None:
    netlist = _netlist(_NG_YP)
    with pytest.raises(EditError, match="does not parse"):
        netlist.set_param("Y1", "m", "2")
    with pytest.raises(EditError, match="takes a model of type `CPL`"):
        netlist.set_model("P1", "ymod")


@ngspice_only
def test_a_cpl_matrix_is_set_and_removed_whole() -> None:
    text = _NG_YP.replace("+R=1\n", "+R=1 0 1\n").replace("P1 a 0 c 0", "P1 a e 0 c f 0")
    netlist = _netlist(text)
    edited = netlist.set_model_param("pmod", "R", "2 0.1 2")
    assert "+R=2 0.1 2\n" in edited.source.text
    model = edited.models["pmod"][0]
    assert [value.text for value in model.params[1].value.values] == ["2", "0.1", "2"]
    removed = netlist.remove_model_param("pmod", "R")
    assert "+R=" not in removed.source.text and "+L=50n\n" in removed.source.text


@ngspice_only
def test_ltra_flags_stay_as_written() -> None:
    text = _LINES.replace("len=1)\n.model lmod2", "len=1 nosteplimit)\n.model lmod2")
    netlist = _netlist(text)
    edited = netlist.set_model_param("lmod", "G", "0")
    assert ".model lmod LTRA(R=1 L=50n C=20p len=1 G=0 nosteplimit)" in edited.source.text
    with pytest.raises(EditError, match="flags are not removable"):
        netlist.remove_model_param("lmod", "nosteplimit")


@pytest.mark.parametrize(
    ("before", "edit", "after"),
    [
        (".model lm LTRA(R=10 len=1)", ("lm", "R"), ".model lm LTRA(len=1)"),
        (".model lm LTRA(R=10 len=1)", ("lm", "len"), ".model lm LTRA(R=10)"),
        (".model dm D(Is=1e-14)", ("dm", "is"), ".model dm D()"),
        (".model dm D Is=1e-14 N=2", ("dm", "Is"), ".model dm D N=2"),
        (".model dm D(Is=1e-14\n+ N=2)", ("dm", "N"), ".model dm D(Is=1e-14\n+ )"),
        (".model dm D(Is=1e-14 ; sat\n+ N=2)", ("dm", "N"), ".model dm D(Is=1e-14 ; sat\n+ )"),
        (
            ".model dm D Is=1e-14\n+ Rs=10 ; series\n+ N=1",
            ("dm", "Rs"),
            ".model dm D Is=1e-14 ; series\n+ N=1",
        ),
        (".model dm D(Is=1e-14\n+ N=2 Rs=1)", ("dm", "N"), ".model dm D(Is=1e-14\n+ Rs=1)"),
    ],
)
def test_remove_model_param(before: str, edit: tuple[str, str], after: str) -> None:
    netlist = _netlist(f"title\nR1 a 0 1\n{before}\n.end\n")
    edited = netlist.remove_model_param(*edit)
    assert edited.source.text == f"title\nR1 a 0 1\n{after}\n.end\n"


def test_remove_model_param_keeps_a_comment_beside_the_field() -> None:
    # Review R1: a comment only ends a physical line, so the removal never holds one.
    netlist = _netlist("title\nR1 a 0 1\n.model dm D Is=1e-14 ; c\n+ N=2\n.end\n")
    edited = netlist.remove_model_param("dm", "N")
    assert edited.source.text == "title\nR1 a 0 1\n.model dm D Is=1e-14 ; c\n.end\n"
    edited = netlist.remove_model_param("dm", "Is")
    assert edited.source.text == "title\nR1 a 0 1\n.model dm D ; c\n+ N=2\n.end\n"


# remove_param on every family that takes a named parameter (decision 0019 item 11).
_BOTH_REMOVALS = [
    ("R1 a 0 1k tc1=1m", "tc1", "R1 a 0 1k"),
    ("R1 a 0 1k m=2 temp=30", "m", "R1 a 0 1k temp=30"),
    ("C1 a 0 1p m=2", "m", "C1 a 0 1p"),
    ("L1 a 0 1u m=2", "m", "L1 a 0 1u"),
    ("D1 a 0 dm m=2 temp=30", "temp", "D1 a 0 dm m=2"),
    ("Q1 c b e qn temp=30", "temp", "Q1 c b e qn"),
    ("M1 d g s s nm m=2 l=1u", "m", "M1 d g s s nm l=1u"),
    ("J1 d g s jn temp=30", "temp", "J1 d g s jn"),
    ("R1 a 0 1k m=2\n+ temp=30", "temp", "R1 a 0 1k m=2"),
    ("R1 a 0 1k\n+ m=2 temp=30", "m", "R1 a 0 1k\n+ temp=30"),
    ("R1 a 0 1k m=2 ; note", "m", "R1 a 0 1k ; note"),
    # Review R1: the removed span follows where the field sits on its physical line, and a
    # comment after a field that is alone on its line moves to the end of the line before.
    ("R1 a 0 1k m=2 tc1=0 ; note", "m", "R1 a 0 1k tc1=0 ; note"),
    ("R1 a 0 1k ; note\n+ m=2", "m", "R1 a 0 1k ; note"),
    ("R1 a 0 1k ; note\r\n+ m=2", "m", "R1 a 0 1k ; note"),
    ("R1 a 0 1k\n+ m=2 tc1=0 ; note", "m", "R1 a 0 1k\n+ tc1=0 ; note"),
    ("R1 a 0 1k\n+ tc1=0 m=2 ; note", "m", "R1 a 0 1k\n+ tc1=0 ; note"),
    ("R1 a 0 1k\n+ m=2 ; note\n+ tc1=0", "m", "R1 a 0 1k ; note\n+ tc1=0"),
    ("R1 a 0 1k\r\n+ m=2 ; note\r\n+ tc1=0", "m", "R1 a 0 1k ; note\r\n+ tc1=0"),
    ("R1 a 0 1k ; first\n+ m=2 ; note\n+ tc1=0", "m", "R1 a 0 1k ; first ; note\n+ tc1=0"),
    ("R1 a 0 1k m=2 ; c\n+ temp=1", "m", "R1 a 0 1k ; c\n+ temp=1"),
    ("R1 a 0 1k\n+ m=2", "m", "R1 a 0 1k"),
]
_NG_REMOVALS = [
    ("R1 a 0 1k tc1=1m, tc2=0", "tc2", "R1 a 0 1k tc1=1m"),
    ("Z1 d g s zn temp=30", "temp", "Z1 d g s zn"),
    ("G1 0 a b 0 2m m=2", "m", "G1 0 a b 0 2m"),
    ("F1 0 a Vs 2 m=2", "m", "F1 0 a Vs 2"),
    ("B1 a 0 v={1} tc1=1m", "tc1", "B1 a 0 v={1}"),
    ("Q1 c b e qn area=2", "area", "Q1 c b e qn"),
    ("V9 a 0 1 portnum=1 z0=50", "z0", "V9 a 0 1 portnum=1"),
    ("R1 a 0 1k m=2 \\\\\ntemp=30", "temp", "R1 a 0 1k m=2"),
    ("R1 a 0 1k \\\\\nm=2 ; note", "m", "R1 a 0 1k ; note"),
    ("R1 a 0 1k \\\\\r\nm=2 ; note\r\n+ tc1=0", "m", "R1 a 0 1k ; note\r\n+ tc1=0"),
    ("T1 a 0 b 0 Z0=50 F=1g\n+ NL=0.1 ; frac", "nl", "T1 a 0 b 0 Z0=50 F=1g ; frac"),
]
_LT_REMOVALS = [
    ("V9 a 0 1 Rser=1", "rser", "V9 a 0 1"),
    ("B1 a 0 V=1 ic=0", "ic", "B1 a 0 V=1"),
    ("Z1 d g s zn m=2", "m", "Z1 d g s zn"),
]
_MODELS = ".model dm D\n.model qn NPN\n.model nm NMOS\n.model jn NJF\n.model zn NMF\nVs s 0 0\n"


def _removal(line: str, name: str, after: str) -> None:
    netlist = _netlist(f"title\n{line}\n{_MODELS}.end\n")
    edited = netlist.remove_param(line.split()[0], name)
    assert edited.source.text == f"title\n{after}\n{_MODELS}.end\n"
    assert edited.signature() == netlist.signature()


@pytest.mark.parametrize(("line", "name", "after"), _BOTH_REMOVALS)
def test_remove_param_on_every_family(line: str, name: str, after: str) -> None:
    _removal(line, name, after)


@ngspice_only
@pytest.mark.parametrize(("line", "name", "after"), _NG_REMOVALS)
def test_remove_param_on_ngspice_lines(line: str, name: str, after: str) -> None:
    _removal(line, name, after)


@ltspice_only
@pytest.mark.parametrize(("line", "name", "after"), _LT_REMOVALS)
def test_remove_param_on_ltspice_lines(line: str, name: str, after: str) -> None:
    _removal(line, name, after)


@pytest.mark.parametrize(
    ("line", "name", "message"),
    [
        ("D1 a 0 dm off", "off", "is a flag"),
        ("R1 a 0 1k", "m", "has no parameter `m`"),
        ("X1 a 0 sub k=1", "k", "subcircuit call"),
        ("K1 L1 L2 0.5", "x", "takes no parameters"),
        ("T1 a 0 b 0 Z0=50\n+ TD=1n ; delay", "td", "length must be given"),
    ],
)
def test_remove_param_refusals(line: str, name: str, message: str) -> None:
    text = f"title\n{line}\nL1 a 0 1u\nL2 a 0 1u\n.subckt sub p q\n.ends\n{_MODELS}.end\n"
    with pytest.raises(EditError, match=message):
        _netlist(text).remove_param(line.split()[0], name)


@ngspice_only
def test_remove_param_names_remove_value_for_a_value_keyword() -> None:
    with pytest.raises(EditError, match="use remove_value"):
        _netlist("title\nR1 a 0 r=1k m=2\n.end\n").remove_param("R1", "r")


def test_remove_param_refuses_a_positional_area() -> None:
    with pytest.raises(EditError, match="positional"):
        _netlist(f"title\nJ1 d g s jn 2\n{_MODELS}.end\n").remove_param("J1", "area")


_PARAMS = ("m", "temp", "tc1", "tc2")


@st.composite
def _commented_lines(draw: st.DrawFn) -> tuple[str, str]:
    """An R line whose parameters are spread over ``+`` lines, with comments at line ends, and
    the name of one of its parameters."""
    names = draw(st.lists(st.sampled_from(_PARAMS), min_size=1, max_size=4, unique=True))
    eol = draw(st.sampled_from(["\n", "\r\n"]))
    text = "R1 a 0 1k"
    for index, name in enumerate(names):
        if draw(st.booleans()):
            text += f" ; c{index}" if draw(st.booleans()) else ""
            text += f"{eol}+"
        text += f" {name}=1"
    if draw(st.booleans()):
        text += " ; last"
    return text + eol, draw(st.sampled_from(names))


def _comments(netlist: Netlist) -> list[str]:
    item = netlist.element("R1")
    return [netlist.source.text[s.start : s.end] for s in item.trailing_comments]


@settings(max_examples=60, deadline=None)
@given(case=_commented_lines())
def test_a_removal_keeps_every_comment_byte_for_byte(case: tuple[str, str]) -> None:
    line, name = case
    netlist = _netlist(f"title\n{line}.end\n")
    edited = netlist.remove_param("R1", name)
    # Every comment's text is in the result, in order and unchanged; two may share a line.
    joined = " ".join(_comments(edited))
    position = 0
    for comment in _comments(netlist):
        position = joined.index(comment, position) + len(comment)
    assert "".join(_comments(edited)).replace(" ", "") == "".join(_comments(netlist)).replace(
        " ", ""
    )
    assert name not in [param.name for param in edited.element("R1").params]
    assert edited.signature() == netlist.signature()


# The exit: no sequence of these edits changes the signature.
def _operations() -> list[Operation]:
    operations: list[Operation] = [
        lambda n: n.set_param("T1", "z0", "75"),
        lambda n: n.set_param("T1", "td", "2n"),
        lambda n: n.set_param("U1", "l", "7"),
        lambda n: n.set_param("U1", "n", "3"),
        lambda n: n.remove_param("U1", "n"),
        lambda n: n.set_model("O1", "lmod2"),
        lambda n: n.set_model("O1", "lmod"),
        lambda n: n.set_model("U1", "umod2"),
        lambda n: n.set_model_param("lmod", "R", "3"),
        lambda n: n.remove_model_param("lmod2", "R"),
        lambda n: n.remove_model_param("umod", "Cperl"),
    ]
    if not is_ltspice():
        operations.append(lambda n: n.set_param("T1", "ic", "0,0,0,0"))
        operations.append(lambda n: n.remove_param("T1", "ic"))
    return operations


@settings(max_examples=40, deadline=None)
@given(choices=st.lists(st.integers(min_value=0, max_value=12), max_size=8))
def test_no_sequence_of_line_edits_changes_the_signature(choices: list[int]) -> None:
    netlist = _netlist()
    baseline = netlist.signature()
    operations = _operations()
    for choice in choices:
        try:
            netlist = operations[choice % len(operations)](netlist)
        except EditError:
            continue
        assert netlist.signature() == baseline
