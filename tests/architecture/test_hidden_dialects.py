"""The hidden xyce dialect (decision 0026; xm0-tasks G1 point 1): a ``Dialect`` instance that is
not a member, reachable only through ``netlistmod.dialects._XYCE`` until X-M8.

It relies on undocumented ``Enum`` internals, so these checks run on every supported Python.
"""

from __future__ import annotations

import copy
import importlib
import pickle
import pkgutil

import pytest

import netlistmod
from netlistmod import Dialect, Netlist, SourceText, UnsupportedConstruct
from netlistmod.dialects import _XYCE, fold_name, is_ground_name
from netlistmod.document.names import is_ground, net_name


def _modules() -> list[object]:
    names = [
        module.name for module in pkgutil.walk_packages(netlistmod.__path__, prefix="netlistmod.")
    ]
    return [netlistmod, *(importlib.import_module(name) for name in names)]


def test_xyce_is_not_a_member() -> None:
    assert _XYCE not in list(Dialect)
    assert "XYCE" not in Dialect.__members__
    assert all(member is not _XYCE for member in Dialect.__members__.values())
    assert "xyce" not in [member.value for member in Dialect]
    assert "xyce" not in Dialect._value2member_map_
    assert len(Dialect) == 2
    assert "XYCE" not in vars(Dialect)
    assert not hasattr(Dialect, "XYCE")
    # `EnumType.__contains__` accepts any instance of the enum, so the pseudo-member is `in
    # Dialect` while it is hidden (decision 0026 item 4); its value is not.
    assert _XYCE in Dialect
    assert "xyce" not in Dialect


@pytest.mark.parametrize("name", ["xyce", "XYCE", "Xyce"])
def test_xyce_is_not_found_by_name_or_value(name: str) -> None:
    with pytest.raises(ValueError, match="valid names are: ngspice, ltspice$"):
        Dialect.from_name(name)
    with pytest.raises(ValueError):
        Dialect(name)
    with pytest.raises(KeyError):
        Dialect[name]


def test_no_public_name_is_bound_to_xyce() -> None:
    # Every non-underscore name in every module, whether listed in `__all__` or not.
    for module in _modules():
        bound = [
            name
            for name, value in vars(module).items()
            if not name.startswith("_") and value is _XYCE
        ]
        assert bound == [], module
    # The class attributes of the public top-level objects.
    for public_name in netlistmod.__all__:
        obj = getattr(netlistmod, public_name)
        if not isinstance(obj, type):
            continue
        for klass in obj.__mro__:
            bound = [
                name
                for name, value in vars(klass).items()
                if not name.startswith("_") and value is _XYCE
            ]
            assert bound == [], (public_name, klass)
    assert "_XYCE" not in netlistmod.__all__
    assert not hasattr(netlistmod, "_XYCE")


def test_xyce_behaves_as_a_dialect() -> None:
    assert isinstance(_XYCE, Dialect)
    assert isinstance(_XYCE, str)
    assert str(_XYCE) == "xyce"
    assert f"{_XYCE}" == "xyce"
    assert _XYCE == "xyce"
    assert _XYCE.value == "xyce"
    assert _XYCE.name == "XYCE"
    assert repr(_XYCE) == "<Dialect.XYCE: 'xyce'>"
    assert _XYCE.display_name == "Xyce"
    assert _XYCE is not Dialect.NGSPICE
    assert _XYCE != Dialect.NGSPICE
    assert _XYCE != Dialect.LTSPICE
    # Identity survives the constructor and copies, and a dict keyed by dialects finds it.
    assert Dialect(_XYCE) is _XYCE
    assert copy.copy(_XYCE) is _XYCE
    assert copy.deepcopy(_XYCE) is _XYCE
    assert {_XYCE: 1, Dialect.NGSPICE: 2}[_XYCE] == 1


def test_xyce_cannot_be_pickled_into_a_member() -> None:
    # Unpickling looks the value up, which no member has: a documented limit of the mechanism.
    with pytest.raises((ValueError, pickle.PicklingError)):
        pickle.loads(pickle.dumps(_XYCE))


def test_the_public_loaders_read_a_structure_only_netlist() -> None:
    text = "Xyce structure\n* a comment\n\n.END\n"
    for netlist in (
        Netlist.from_text(text, dialect=_XYCE),
        Netlist.from_source(SourceText(text), dialect=_XYCE),
    ):
        assert netlist.dialect is _XYCE
        assert [type(line.item).__name__ for line in netlist.lines] == [
            "Title",
            "CommentLine",
            "BlankLine",
            "End",
        ]
        assert netlist.diagnostics == ()
        assert "xyce" in repr(netlist)


def test_the_public_loaders_refuse_an_element_line() -> None:
    with pytest.raises(UnsupportedConstruct, match="not yet supported on Xyce"):
        Netlist.from_text("t\nQ1 c b e qmod\n.END\n", dialect=_XYCE)


def test_rkm_is_refused_on_xyce() -> None:
    with pytest.raises(ValueError, match="applies only to ngspice"):
        Netlist.from_text("t\n.END\n", dialect=_XYCE, rkm=True)


def test_only_zero_is_ground_on_xyce() -> None:
    # [xyce-ref] §2.3.1.1 p182; `GND` is a ground only after `.PREPROCESS REPLACEGROUND`
    # (§2.1.28 p125), which X-M1 reads.
    assert is_ground_name("0", _XYCE)
    assert is_ground("0", _XYCE)
    assert net_name("0", _XYCE) == "0"
    for name in ("gnd", "GND", "00", "ground", "gnd!"):
        assert not is_ground_name(name, _XYCE)
    assert net_name("GND", _XYCE) == "gnd"
    # The other dialects keep `gnd`.
    assert is_ground_name("GND", Dialect.NGSPICE)
    assert is_ground_name("GND", Dialect.LTSPICE)


def test_xyce_names_fold_case() -> None:
    # Xyce ignores case ([xyce-ug] §4.1.3 p41); the fold is provisional until X-M1's names.md.
    assert fold_name("RaResistor", _XYCE) == "raresistor"


def test_xyce_has_its_own_formula_grammar() -> None:
    # X-M1 B3 (decision 0027 item 11): formula_xyce.lark and its reserved words, not another
    # dialect's rules; the other dialects list no built-in functions, so the lookup fails loudly.
    from netlistmod.grammar.formula import (
        build_formula_parser,
        builtin_functions,
        parse_formula,
        reserved_words,
    )

    assert build_formula_parser(_XYCE) is not build_formula_parser(Dialect.NGSPICE)
    assert "freq" in reserved_words(_XYCE)
    assert "sin" in builtin_functions(_XYCE)
    assert parse_formula("x1:a+1", Dialect.LTSPICE) is None
    assert [token.text for token in parse_formula("x1:a+1", _XYCE) or ()] == ["x1:a"]
    with pytest.raises(ValueError, match="No built-in functions are listed for ngspice"):
        builtin_functions(Dialect.NGSPICE)
