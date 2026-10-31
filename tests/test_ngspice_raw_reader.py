"""The raw-file reader of ``tests/support/ngspice.py`` on files written by ngspice 47 (M7 T1).

The samples in ``tests/corpus/ngspice/solver_stubs/raw/`` were produced from the netlists next
to them; the expected values are their closed forms. No solver is needed.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from netlistmod import Dialect, Netlist
from tests.support.ngspice import RawFileError, ensure_runs, read_raw, with_stubs, without_date

RAW = Path(__file__).parent / "corpus" / "ngspice" / "solver_stubs" / "raw"


def test_operating_point_plot() -> None:
    (plot,) = read_raw((RAW / "op.raw").read_bytes())
    assert (plot.title, plot.name, plot.flags) == ("op probe", "Operating Point", ("real",))
    assert plot.variables == ("v(in)", "v(out)", "i(v1)")
    assert plot.kinds == ("voltage", "voltage", "current")
    assert plot.real("V(OUT)") == (2.0,)  # names compare case-insensitively
    assert plot.real("i(v1)") == (-1e-3,)


def test_ac_plot_has_complex_values() -> None:
    (plot,) = read_raw((RAW / "ac.raw").read_bytes())
    assert plot.name == "AC Analysis" and "complex" in plot.flags
    frequencies = [value.real for value in plot.column("frequency")]
    assert frequencies == [100.0, 200.0, 300.0]
    for frequency, value in zip(frequencies, plot.column("v(out)"), strict=True):
        expected = 1 / complex(1, 2 * math.pi * frequency * 1e3 * 1e-6)
        assert value == pytest.approx(expected, rel=1e-12)
    with pytest.raises(RawFileError, match="complex"):
        plot.real("v(out)")


def test_transient_plot_follows_the_rc_charge() -> None:
    (plot,) = read_raw((RAW / "tran.raw").read_bytes())
    assert plot.name == "Transient Analysis" and len(plot.rows) == 61
    time, out = plot.real("time"), plot.real("v(out)")
    assert time[-1] == pytest.approx(2e-3)
    assert out[-1] == pytest.approx(1 - math.exp(-2), rel=1e-3)


def test_two_analyses_give_two_plots_in_file_order() -> None:
    plots = read_raw((RAW / "two.raw").read_bytes())
    assert [plot.name for plot in plots] == ["AC Analysis", "Operating Point"]
    assert plots[1].real("v(out)") == (2.0,)
    assert plots[0].column("v(out)") == (complex(2 / 3, 0),)


def test_line_endings_do_not_matter() -> None:
    data = (RAW / "op.raw").read_bytes()
    assert b"\r\n" in data  # ngspice 47 writes CRLF
    assert read_raw(data.replace(b"\r\n", b"\n")) == read_raw(data)


def test_without_date_drops_only_the_date_line() -> None:
    data = (RAW / "op.raw").read_bytes()
    stripped = without_date(data)
    assert b"Date:" not in stripped
    assert len(data.splitlines()) - len(stripped.splitlines()) == 1


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda text: text.replace("Values:", "Binary:"), "binary raw file"),
        (lambda text: text.replace("Values:", "Data:"), "expected `Values:`"),
        (lambda text: text.replace("No. Points: 1 ", "No. Points: 2 "), "ends inside a plot"),
        (lambda text: text.replace("\t1\tv(out)", "\t7\tv(out)"), "expected variable 1"),
        (lambda text: text.replace("Plotname: Operating Point\r\n", ""), "without `Plotname:`"),
        (lambda text: text.replace("0\t\t3.0", "5\t\t3.0"), "expected point 0"),
        (lambda text: text.replace("0\t\t3.0", "0\t\t1 2 3 3.0"), "4 values for 3"),
        (lambda text: text.split("\r\nVariables:")[0], "ends inside a plot header"),
        (lambda text: text.replace("Flags: real", "Flags: complex"), "without `,`"),
        (lambda text: text.replace("Flags: real", "Flags real"), "expected `Key: value`"),
    ],
)
def test_malformed_raw_files_fail_loudly(change: object, message: str) -> None:
    text = (RAW / "op.raw").read_bytes().decode("ascii")
    assert callable(change)
    with pytest.raises(RawFileError, match=message):
        read_raw(change(text))


def test_ensure_runs_adds_an_op_line_only_without_an_analysis() -> None:
    bare = Netlist.from_text("t\nV1 a 0 1\nR1 a 0 1k\n.end\n", dialect=Dialect.NGSPICE)
    assert ensure_runs(bare).text == "t\nV1 a 0 1\nR1 a 0 1k\n.op\n.end\n"
    tran = Netlist.from_text("t\nV1 a 0 1\nR1 a 0 1k\n.tran 1u 2u\n.end\n", dialect=Dialect.NGSPICE)
    assert ensure_runs(tran) is tran


def test_stubs_replace_include_and_lib_lines(tmp_path: Path) -> None:
    stub = tmp_path / "stubs" / "vendor_stub.lib"
    stub.parent.mkdir()
    stub.write_text(".lib tt\n.endl tt\n", encoding="utf-8")
    other = tmp_path / "stubs" / "models_stub.inc"
    other.write_text("* models\n", encoding="utf-8")
    netlist = Netlist.from_text(
        't\n.include "~/x/models.lib"\n.lib vendor.lib tt\n.include old_models.lib\n.end\n',
        dialect=Dialect.NGSPICE,
    )
    folder = tmp_path / "run"
    folder.mkdir()
    stubbed = with_stubs(netlist, folder, {"~/x/models.lib": other, "vendor.lib": stub})
    assert stubbed.text == (
        't\n.include "models_stub.inc"\n.lib vendor_stub.lib tt\n.include old_models.lib\n.end\n'
    )
    assert sorted(path.name for path in folder.iterdir()) == ["models_stub.inc", "vendor_stub.lib"]
    with pytest.raises(ValueError, match="no .include or .lib line names 'models.lib'"):
        with_stubs(netlist, folder, {"models.lib": other})
