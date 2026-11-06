"""Netlist, Line and Lines (M5 T3): constructors, logical lines, search and insertion points."""

from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import (
    BlankLine,
    CommentLine,
    Dialect,
    End,
    Line,
    Lines,
    Netlist,
    ParseError,
    Resistor,
    SourceText,
    Span,
    SubcktDefinition,
    Title,
)
from netlistmod.document import fold, is_ground, net_name
from tests.support.corpus import accept_files
from tests.support.dialects import current_dialect

CORPUS = Path(__file__).parents[1] / "corpus" / "ngspice"
ACCEPT_FILES = accept_files(CORPUS)

TEXT = (
    "divider\n"
    "* a comment\n"
    "R1 in out 1k ; first\n"
    "+ m=1\n"
    "\n"
    ".subckt div a b\n"
    "R1 a b 1k\n"
    "R2 b 0 1k\n"
    ".ends div\n"
    "X1 in out div\n"
    ".end\n"
)


def _netlist(text: str = TEXT, **options: bool) -> Netlist:
    return Netlist.from_text(text, dialect=current_dialect(), **options)


def test_constructors_take_an_explicit_dialect(tmp_path: Path) -> None:
    path = tmp_path / "x.cir"
    path.write_bytes(TEXT.replace("\n", "\r\n").encode("utf-8"))
    loaded = Netlist.load(path, dialect=current_dialect())
    assert loaded.to_bytes() == path.read_bytes()
    assert loaded.dialect is current_dialect()
    from_source = Netlist.from_source(SourceText(TEXT), dialect=current_dialect())
    assert from_source.text == TEXT
    assert not from_source.rkm
    with pytest.raises(TypeError):
        Netlist.from_text(TEXT)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        Netlist.from_text(TEXT, dialect="ngspice")  # type: ignore[arg-type]
    with pytest.raises(ParseError):
        _netlist("title\nR1 a b\n.end\n")


def test_load_uses_the_fallback_encodings(tmp_path: Path) -> None:
    path = tmp_path / "micro.cir"
    path.write_bytes("t\nC1 a 0 1\xb5\n.end\n".encode("cp1252"))
    netlist = Netlist.load(path, dialect=current_dialect(), fallback_encodings=("cp1252",))
    assert netlist.source.encoding == "cp1252"
    assert netlist.to_bytes() == path.read_bytes()


@pytest.mark.ngspice_only
@pytest.mark.parametrize("path", ACCEPT_FILES, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_to_bytes_round_trips_every_accept_corpus_file(path: Path) -> None:
    netlist = Netlist.load(path, dialect=current_dialect(), rkm=True)
    assert netlist.to_bytes() == path.read_bytes()
    _assert_tiles(netlist.lines, 0, len(netlist.text))
    for line in netlist.lines.walk():
        assert line.first_line <= line.last_line
        if line.body is not None:
            assert isinstance(line.item, SubcktDefinition)
            _assert_tiles(line.body, line.item.header_span.end, line.item.ends.span.start)


def _assert_tiles(lines: Lines, start: int, end: int) -> None:
    offset = start
    for line in lines:
        assert line.span == line.item.span
        assert line.span.start == offset
        offset = line.span.end
    assert offset == end


def test_a_line_is_a_logical_item_with_physical_line_numbers() -> None:
    netlist = _netlist()
    kinds = [type(line.item) for line in netlist.lines]
    assert kinds[:4] == [Title, CommentLine, Resistor, BlankLine]
    resistor = netlist.lines[2]
    assert (resistor.first_line, resistor.last_line) == (3, 4)
    assert netlist.slice(resistor.span) == "R1 in out 1k ; first\n+ m=1\n"
    definition = netlist.lines.find(SubcktDefinition)
    assert definition is not None
    assert (definition.first_line, definition.last_line) == (6, 9)
    assert definition.scope == ()
    assert definition.body is not None
    assert [line.scope for line in definition.body] == [("div",), ("div",)]
    assert [line.first_line for line in definition.body] == [7, 8]


def test_find_find_all_and_index_of() -> None:
    netlist = _netlist()
    lines = netlist.lines
    assert [line.item.designator for line in lines.find_all(Resistor)] == ["R1"]  # type: ignore[union-attr]
    nested = lines.find_all(Resistor, recursive=True)
    assert [(line.scope, line.item.designator) for line in nested] == [  # type: ignore[union-attr]
        ((), "R1"),
        (("div",), "R1"),
        (("div",), "R2"),
    ]
    assert lines.find(End) is lines[-1]
    assert lines.find(CommentLine, recursive=True) is lines[1]
    assert lines.find(type(None)) is None
    assert lines.index_of(lines[2]) == 2
    assert lines.index_of(lines[2].item) == 2
    with pytest.raises(ValueError):
        lines.index_of(nested[1])
    body = lines[4].body
    assert body is not None
    assert body.index_of(nested[2]) == 1
    assert isinstance(lines[1:3], Lines)
    assert len(lines[1:3]) == 2
    assert "Resistor" in repr(lines)


def test_lines_compare_by_identity() -> None:
    first, second = _netlist(), _netlist()
    assert first.lines[2] != second.lines[2]
    assert first.lines[2] == first.lines[2]


def test_insertion_points_are_physical_line_boundaries() -> None:
    netlist = _netlist()
    lines = netlist.lines
    text = netlist.text
    first_item = lines[1]
    assert lines.insert_before(first_item) == Span(8, 8)
    assert text[:8] == "divider\n"
    end = lines[-1]
    before_end = lines.insert_before(end)
    assert text[before_end.start :] == ".end\n"
    assert lines.insert_after(lines[-2]) == before_end
    body = lines[4].body
    assert body is not None
    inside = body.insert_after(body[-1])
    assert text[inside.start :].startswith(".ends div\n")
    assert lines.insert_before(body[0]) == Span(body[0].span.start, body[0].span.start)
    stranger = Line(end.item, end.span, 1, 1, ())
    with pytest.raises(ValueError):
        lines.insert_after(stranger)


def test_insertion_after_a_last_line_without_final_newline() -> None:
    netlist = _netlist("title\nR1 a 0 1\n.end")
    last = netlist.lines[-1]
    assert netlist.lines.insert_after(last) == Span(len(netlist.text), len(netlist.text))
    assert netlist.lines.insert_before(last) == Span(15, 15)
    assert (last.first_line, last.last_line) == (3, 3)


def test_names_fold_ascii_and_ground_aliases() -> None:
    assert fold("R1_ÄB", Dialect.NGSPICE) == "r1_Äb"
    assert [is_ground(name, Dialect.NGSPICE) for name in ("0", "GND", "gNd", "00", "gnd1")] == [
        True,
        True,
        True,
        False,
        False,
    ]
    assert net_name("GND", Dialect.NGSPICE) == "0"
    assert net_name("/Vout", Dialect.NGSPICE) == "/vout"


def test_repr_and_parse_result() -> None:
    netlist = _netlist()
    assert repr(netlist) == f"Netlist({current_dialect().value}, 7 lines)"
    assert netlist.parse_result.items[0] is netlist.lines[0].item
