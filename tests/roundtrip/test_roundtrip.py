from __future__ import annotations

from pathlib import Path

import pytest

from netlistmod import SourceText

ROOT = Path(__file__).parents[2]
CORPUS = ROOT / "tests" / "corpus"


BYTE_CASES = [
    pytest.param(b"one\ntwo\n", id="lf"),
    pytest.param(b"one\r\ntwo\r\n", id="crlf"),
    pytest.param(b"one\r\ntwo\nthree\r\n", id="mixed-endings"),
    pytest.param(b"one\rtwo", id="lone-cr"),
    pytest.param(b"no-final-newline", id="no-final-newline"),
    pytest.param(b"\n\r\n\n", id="only-newlines"),
    pytest.param(b"", id="empty"),
    pytest.param(b"\tleading\ttrailing\t", id="tabs"),
    pytest.param(b"trailing whitespace  \t\r\n", id="trailing-whitespace"),
    pytest.param(b"first\n\nthird\n", id="blank-lines"),
    pytest.param(b"x" * 16_384, id="long-line"),
    pytest.param(b"\x00embedded\x00nul", id="nul-bytes"),
    pytest.param("UTF-8 µ".encode("utf-8"), id="utf8"),
    pytest.param(b"\xef\xbb\xbf" + "UTF-8 µ".encode("utf-8"), id="utf8-bom"),
    pytest.param(b"\xff\xfe" + "UTF-16 µ".encode("utf-16-le"), id="utf16-le-bom"),
    pytest.param(b"\xfe\xff" + "UTF-16 µ".encode("utf-16-be"), id="utf16-be-bom"),
    pytest.param(b"cp1252 \xb5", id="cp1252-micro"),
    pytest.param(b"undefined cp1252 byte \x81", id="latin1-fallback"),
]


@pytest.mark.parametrize("data", BYTE_CASES)
def test_source_bytes_round_trip(data: bytes, tmp_path: Path) -> None:
    source = SourceText.from_bytes(data)
    assert source.to_bytes() == data

    path = tmp_path / "roundtrip.net"
    source.write(path)
    assert path.read_bytes() == data
    assert SourceText.read(path).to_bytes() == data
    assert list(tmp_path.iterdir()) == [path]


def test_byte_round_trip_preserves_crlf_that_text_mode_would_translate(
    tmp_path: Path,
) -> None:
    path = tmp_path / "newlines.net"
    path.write_bytes(b"first\r\nsecond\r\n")

    # Default text-mode reads translate CRLF to LF; SourceText must not.
    with path.open("r", newline=None) as text_file:
        assert text_file.read() == "first\nsecond\n"
    assert SourceText.read(path).text == "first\r\nsecond\r\n"

    path.write_bytes(b"\xef\xbb\xbfcontent")
    # utf-8-sig text mode strips the BOM; SourceText records and restores it.
    with path.open("r", encoding="utf-8-sig") as text_file:
        assert text_file.read() == "content"
    source = SourceText.read(path)
    assert source.bom
    assert source.to_bytes() == b"\xef\xbb\xbfcontent"


def test_every_corpus_file_round_trips_byte_exactly() -> None:
    files = [path for path in CORPUS.rglob("*") if path.is_file()]
    assert files
    for path in files:
        original = path.read_bytes()
        assert SourceText.from_bytes(original).to_bytes() == original, str(path)
