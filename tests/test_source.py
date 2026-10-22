from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from netlistmod import EncodingError, SourceText, Span


def test_span_boundaries_and_hull() -> None:
    span = Span(2, 5)
    assert span.length == 3
    assert not span.is_empty
    assert span.contains(2)
    assert span.contains(4)
    assert not span.contains(5)
    assert span.hull(Span(5, 8)) == Span(2, 8)
    assert Span(2, 5).overlaps(Span(2, 5))
    assert not Span(2, 5).overlaps(Span(5, 8))
    assert not Span(2, 5).overlaps(Span(1, 2))
    assert Span(2, 5).overlaps(Span(3, 3))
    assert not Span(2, 5).overlaps(Span(2, 2))
    assert not Span(2, 5).overlaps(Span(5, 5))
    assert not Span(3, 3).overlaps(Span(3, 3))
    assert Span(3, 3).is_empty


@given(
    st.integers(min_value=0, max_value=100),
    st.integers(min_value=0, max_value=100),
    st.integers(min_value=0, max_value=100),
    st.integers(min_value=0, max_value=100),
)
def test_span_overlap_is_symmetric(a: int, b: int, c: int, d: int) -> None:
    first = Span(min(a, b), max(a, b))
    second = Span(min(c, d), max(c, d))
    assert first.overlaps(second) == second.overlaps(first)


@pytest.mark.parametrize(("start", "end"), [(-1, 0), (1, 0)])
def test_span_rejects_invalid_offsets(start: int, end: int) -> None:
    with pytest.raises(ValueError):
        Span(start, end)


def test_span_rejects_non_integer_offsets() -> None:
    with pytest.raises(ValueError):
        Span(0, 1.5)  # type: ignore[arg-type]


def test_source_bytes_detection_and_fallback_order() -> None:
    utf8 = SourceText.from_bytes("micro µ".encode("utf-8"))
    assert (utf8.text, utf8.encoding, utf8.bom) == ("micro µ", "utf-8", False)
    assert SourceText.from_bytes(codecs_bom_utf8() + b"text") == SourceText("text", "utf-8", True)
    cp1252 = SourceText.from_bytes(b"\xb5")
    assert cp1252.encoding == "cp1252"
    assert cp1252.text == "µ"
    assert SourceText("a", "windows-1252").encoding == "cp1252"
    assert SourceText("a", "ISO-8859-1").encoding == "latin-1"
    assert SourceText.from_bytes(b"\x81").encoding == "latin-1"
    assert SourceText.from_bytes(b"\x81").to_bytes() == b"\x81"
    assert SourceText.from_bytes(b"\xff", fallback_encodings=("ascii", "latin-1")).text == "ÿ"
    assert SourceText.from_bytes(b"A\x00").encoding == "utf-8"


def codecs_bom_utf8() -> bytes:
    """Return the UTF-8 BOM without relying on text-mode encoders."""
    return b"\xef\xbb\xbf"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"\xff\xfe" + "LT".encode("utf-16-le"), ("LT", "utf-16-le", True)),
        (b"\xfe\xff" + "LT".encode("utf-16-be"), ("LT", "utf-16-be", True)),
    ],
)
def test_source_utf16_boms(data: bytes, expected: tuple[str, str, bool]) -> None:
    source = SourceText.from_bytes(data)
    assert (source.text, source.encoding, source.bom) == expected
    assert source.to_bytes() == data


def test_empty_bom_and_encoding_failures() -> None:
    assert SourceText.from_bytes(b"") == SourceText("", "utf-8", False)
    assert SourceText.from_bytes(codecs_bom_utf8()) == SourceText("", "utf-8", True)
    assert SourceText.from_bytes(b"\xff\xfe") == SourceText("", "utf-16-le", True)
    with pytest.raises(EncodingError, match="UTF-32"):
        SourceText.from_bytes(b"\xff\xfe\x00\x00")
    with pytest.raises(EncodingError, match="UTF-32"):
        SourceText.from_bytes(b"\x00\x00\xfe\xff")
    with pytest.raises(EncodingError, match="BOM"):
        SourceText.from_bytes(codecs_bom_utf8() + b"\xff")
    with pytest.raises(EncodingError, match="BOM"):
        SourceText.from_bytes(b"\xff\xfe\x00")
    with pytest.raises(EncodingError, match="no fallback encodings"):
        SourceText.from_bytes(b"\xff", fallback_encodings=())
    with pytest.raises(EncodingError, match="Unknown encoding"):
        SourceText.from_bytes(b"\xff", fallback_encodings=("not-a-codec",))
    with pytest.raises(EncodingError, match="No BOM"):
        SourceText("text", "cp1252", True).to_bytes()


def test_with_text_and_unencodable_text() -> None:
    original = SourceText.from_bytes(b"caf\xe9")
    changed = original.with_text("tea")
    assert changed == SourceText("tea", "cp1252", False)
    assert original.text == "café"
    with pytest.raises(EncodingError, match="cannot be encoded"):
        original.with_text("λ").to_bytes()


def test_write_is_byte_exact_and_encoding_failure_does_not_touch_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "source.cir"
    target.write_bytes(b"original\r\n")
    source = SourceText("λ", "cp1252")
    with pytest.raises(EncodingError):
        source.write(target)
    assert target.read_bytes() == b"original\r\n"
    assert list(tmp_path.iterdir()) == [target]

    expected = b"R1 a b 1k\r\nR2 a b 2k"
    SourceText.from_bytes(expected).write(target)
    assert target.read_bytes() == expected
    assert SourceText.read(target).to_bytes() == expected
    assert list(tmp_path.iterdir()) == [target]


def test_write_cleans_temporary_file_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "source.cir"
    target.write_bytes(b"original")

    def fail_replace(_source: str | bytes, _target: str | bytes) -> None:
        raise OSError("replacement failed")

    monkeypatch.setattr("netlistmod.source.os.replace", fail_replace)
    with pytest.raises(OSError, match="replacement failed"):
        SourceText("replacement").write(target)
    assert target.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [target]


def test_source_positions_mixed_endings_and_lone_cr() -> None:
    source = SourceText("one\r\n two\nthree\rfour")
    assert source.line_count == 3
    assert source.line_span(1) == Span(0, 5)
    assert source.line_span(2) == Span(5, 10)
    assert source.line_span(3) == Span(10, len(source.text))
    assert source.position(0) == (1, 1)
    assert source.position(5) == (2, 1)
    assert source.position(10) == (3, 1)
    assert source.position(len(source.text)) == (3, 11)
    assert source.offset(2, 1) == 5
    assert source.excerpt(1) == "one\n ^"
    assert source.excerpt(11) == "three\rfour\n ^"


def test_source_position_empty_no_final_newline_and_trailing_newline() -> None:
    assert SourceText("").line_count == 1
    assert SourceText("").line_span(1) == Span(0, 0)

    no_final_newline = SourceText("a\nb")
    assert no_final_newline.line_count == 2
    assert no_final_newline.line_span(2) == Span(2, 3)
    assert no_final_newline.position(3) == (2, 2)

    trailing_newline = SourceText("a\n")
    assert trailing_newline.line_count == 1
    assert trailing_newline.line_span(1) == Span(0, 2)
    assert trailing_newline.position(2) == (1, 3)
    assert trailing_newline.excerpt(2) == "a\n ^"


def test_source_position_rejects_out_of_range_values() -> None:
    source = SourceText("abc")
    for offset in (-1, 4):
        with pytest.raises(ValueError):
            source.position(offset)
    for line, column in ((0, 1), (2, 1), (1, 0), (1, 5)):
        with pytest.raises(ValueError):
            source.offset(line, column)


def test_offset_rejects_columns_beyond_the_line_terminator() -> None:
    lf = SourceText("a\nb")
    assert lf.offset(1, 2) == 1
    with pytest.raises(ValueError):
        lf.offset(1, 3)
    assert lf.offset(2, 2) == 3

    crlf = SourceText("one\r\ntwo")
    assert crlf.offset(1, 4) == 3
    with pytest.raises(ValueError):
        crlf.offset(1, 5)


@given(st.text(alphabet=st.sampled_from(["a", " ", "\n", "\r"])))
def test_valid_offsets_round_trip_through_position(text: str) -> None:
    source = SourceText(text)
    for line in range(1, source.line_count + 1):
        span = source.line_span(line)
        for column in range(1, span.length + 3):
            try:
                offset = source.offset(line, column)
            except ValueError:
                continue
            assert source.position(offset) == (line, column)


@given(st.text())
def test_utf8_round_trip_property(text: str) -> None:
    encoded = text.encode("utf-8")
    assert SourceText.from_bytes(encoded).to_bytes() == encoded
    with_bom = codecs_bom_utf8() + encoded
    assert SourceText.from_bytes(with_bom).to_bytes() == with_bom


@given(st.text())
def test_utf16_round_trip_property(text: str) -> None:
    for encoding, bom in (
        ("utf-16-le", b"\xff\xfe"),
        ("utf-16-be", b"\xfe\xff"),
    ):
        # A UTF-16 LE BOM followed by U+0000 is byte-identical to a UTF-32 LE BOM
        # and is rejected by design; see test_utf16_le_leading_nul_is_ambiguous.
        encoded = bom + ("x" + text).encode(encoding)
        assert SourceText.from_bytes(encoded).to_bytes() == encoded
        without_bom = ("x" + text).encode(encoding)
        assert SourceText.from_bytes(without_bom).to_bytes() == without_bom


def test_utf16_le_leading_nul_is_ambiguous_with_a_utf32_bom() -> None:
    with pytest.raises(EncodingError, match="UTF-32"):
        SourceText.from_bytes(b"\xff\xfe" + "\x00".encode("utf-16-le"))


@given(st.text(alphabet=st.characters(min_codepoint=0, max_codepoint=255)))
def test_latin1_round_trip_property(text: str) -> None:
    encoded = text.encode("latin-1")
    assert SourceText.from_bytes(encoded).to_bytes() == encoded


@given(st.text(alphabet=st.sampled_from(["\x00", "a", "µ", "°", "€", "ÿ"])))
def test_cp1252_round_trip_property(text: str) -> None:
    encoded = text.encode("cp1252")
    assert SourceText.from_bytes(encoded).to_bytes() == encoded


@given(st.binary())
def test_non_utf8_byte_strings_round_trip_with_default_fallbacks(suffix: bytes) -> None:
    encoded = b"\x81" + suffix
    assert SourceText.from_bytes(encoded).to_bytes() == encoded
