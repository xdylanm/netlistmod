"""Edit invariants on generated phase 2 element lines, on both dialects (M18 D3, T5 tier).

The lines come from the oracle's generator (``tests/grammar/test_device_oracle.py``), so they hold
every form, blank, tab, ``+`` continuation, comment and keyword case it writes, some of them in a
``.subckt``. Each case draws a sequence of operations allowed on its lines, from a table per form
(A3's matrix), and checks every step:

(a) the signature is unchanged;
(b) the operation is idempotent: applied again it gives the same bytes, and a removal applied
    again raises ``EditError`` and writes nothing;
(c) the text changed lies inside the target element's item span, or inside its ``.model``'s.

Every drawn operation must apply: the table offers a removal only while what it removes is there,
and a count change of a table or of POLY coefficients only where the edit layer takes one (decision
0017 item 6). The cases run once per dialect (``tests/edits/conftest.py``), and each group's forms
are those of the running dialect, so nothing is skipped silently.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from netlistmod import Dialect, EditError, Netlist
from tests.grammar.test_device_oracle import (
    FORMS,
    Line,
    positional_area,
    transistor_params,
    write_netlist,
)
from tests.support.dialects import current_dialect

Operation = Callable[[Netlist], Netlist]
_T = TypeVar("_T")


@dataclass(frozen=True)
class _Op:
    """One allowed operation: what it does, and the item whose span must hold the change."""

    description: str
    run: Operation
    target: tuple[str, str]  # ("element", designator) or ("model", name)
    removal: bool = False


GROUPS: dict[str, tuple[str, ...]] = {
    "sources": ("V-stimulus", "I-stimulus"),
    "transistors": ("Q-transistor", "M-transistor", "J-transistor", "Z-transistor"),
    "controlled": ("E-linear", "G-linear", "F-linear", "H-linear", "S-switch", "W-switch"),
    "behavioral": (
        "B-behavioral",
        "C-charge",
        "L-flux",
        "E-vol",
        "G-cur",
        "E-value",
        "G-value",
        "F-value",
        "H-value",
    ),
    "nonlinear": (
        "E-table",
        "G-table",
        "E-table4",
        "E-freq",
        "E-gate",
        "E-poly",
        "G-poly",
        "F-poly",
        "H-poly",
        "E-laplace",
        "G-laplace",
    ),
    "lines": ("T-lossless", "O-lossy", "U-rc", "Y-txl", "P-cpl"),
    "special": ("A-code-model", "N-osdi", "A-special", "@-analyzer", "&-probe"),
}


def test_the_groups_hold_every_form() -> None:
    dialect = current_dialect()
    grouped = [form for forms in GROUPS.values() for form in forms if form in FORMS[dialect]]
    assert sorted(grouped) == sorted(FORMS[dialect])


def _bind(value: _T, run: Callable[[Netlist, _T], Netlist]) -> Operation:
    """``run`` with its second argument bound to ``value`` (a loop variable)."""
    return lambda netlist: run(netlist, value)


def _names(netlist: Netlist, designator: str, scope: tuple[str, ...]) -> list[str]:
    return [param.name for param in netlist.element(designator, scope).params]


def _model_names(netlist: Netlist, model: str) -> list[str]:
    return [param.name.lower() for param in netlist.models[model][0].params]


def _points(rows: int, width: int, seed: int) -> list[tuple[str, ...]]:
    pool = ("0", "1", "3", "-2", "5m")
    rng = random.Random(seed)
    if width == 3:
        frequencies = ("1", "1e3", "1e6", "1e9")
        return [(frequencies[i], rng.choice(pool), rng.choice(pool)) for i in range(rows)]
    return [(rng.choice(pool), rng.choice(pool)) for _ in range(rows)]


def _operations(netlist: Netlist, line: Line, scope: tuple[str, ...]) -> list[_Op]:
    """The operations the edit layer takes on ``line`` now, from the form's table."""
    dialect = netlist.dialect
    ng = dialect is Dialect.NGSPICE
    d = line.designator
    inside = bool(scope)
    element = ("element", d)
    ops: list[_Op] = []
    letter, form = line.form.split("-", 1)

    def add(description: str, run: Operation, target: tuple[str, str] = element) -> None:
        ops.append(_Op(f"{description} {d}", run, target))

    def setter(name: str, value: str) -> None:
        add(
            f"set_param {name}={value}",
            lambda n: n.set_param(d, name, value, scope=scope, in_definition=inside),
        )

    def removals(names: tuple[str, ...] | None = None) -> None:
        for name in _names(netlist, d, scope):
            if names is None or name.lower() in names:
                ops.append(
                    _Op(
                        f"remove_param {name} {d}",
                        _bind(
                            name,
                            lambda n, p: n.remove_param(d, p, scope=scope, in_definition=inside),
                        ),
                        element,
                        removal=True,
                    )
                )

    def models(family: str) -> None:
        for model in (f"{family}1", f"{family}2"):
            add(
                f"set_model {model}",
                _bind(model, lambda n, m: n.set_model(d, m, scope=scope, in_definition=inside)),
            )

    def model_param(family: str, name: str, value: str, remove: str | None = None) -> None:
        for model in line.models[:1]:
            ops.append(
                _Op(
                    f"set_model_param {model} {name}",
                    _bind(model, lambda n, m: n.set_model_param(m, name, value)),
                    ("model", model),
                )
            )
            if remove is not None and remove.lower() in _model_names(netlist, model):
                ops.append(
                    _Op(
                        f"remove_model_param {model} {remove}",
                        _bind(model, lambda n, m: n.remove_model_param(m, remove)),
                        ("model", model),
                        removal=True,
                    )
                )

    item = netlist.element(d, scope)
    if form == "stimulus":
        for text in ("SIN(0 2 1k)", "PULSE(0 1 2n)"):
            add(
                f"set_stimulus {text}",
                _bind(text, lambda n, t: n.set_stimulus(d, t, scope=scope, in_definition=inside)),
            )
        stimulus = getattr(item, "stimulus", None)
        if stimulus is not None:
            add(
                "set_stimulus_arg 0",
                lambda n: n.set_stimulus_arg(d, 0, "3", scope=scope, in_definition=inside),
            )
            add(
                "set_stimulus_arg 1",
                lambda n: n.set_stimulus_arg(d, 1, "{k}", scope=scope, in_definition=inside),
            )
        # An LTspice I line needs a value, so its function goes only beside a DC part (the edit
        # layer refuses otherwise, naming set_dc).
        if stimulus is not None and (ng or letter == "V" or getattr(item, "dc", None)):
            ops.append(
                _Op(
                    f"remove_stimulus {d}",
                    lambda n: n.remove_stimulus(d, scope=scope, in_definition=inside),
                    element,
                    removal=True,
                )
            )
        for spec in getattr(item, "distortion", ()):
            ops.append(
                _Op(
                    f"remove_stimulus {spec.name} {d}",
                    _bind(
                        spec.name,
                        lambda n, f: n.remove_stimulus(
                            d, function=f, scope=scope, in_definition=inside
                        ),
                    ),
                    element,
                    removal=True,
                )
            )
        if ng:
            add(
                "set_stimulus DISTOF2",
                lambda n: n.set_stimulus(d, "DISTOF2 1 90", scope=scope, in_definition=inside),
            )
        if letter == "V" and not ng:
            setter("Rser", "2")
            removals()
    elif form == "transistor":
        models(letter.lower() + "n")
        for name in transistor_params(letter, dialect):
            setter(name, "3")
        if positional_area(letter, dialect):
            setter("area", "2")
        removals()
        model_param(letter.lower() + "n", "kp", "2")
    elif form == "linear":
        add("set_value", lambda n: n.set_value(d, "5", scope=scope, in_definition=inside))
        add("set_formula", lambda n: n.set_formula(d, "k*3", scope=scope, in_definition=inside))
        if ng and letter in "FG":
            setter("m", "3")
            removals()
    elif form == "switch":
        models("sm" if letter == "S" else "cm")
        for state in ("on", "off", None):
            add(
                f"set_switch_state {state}",
                _bind(
                    state, lambda n, s: n.set_switch_state(d, s, scope=scope, in_definition=inside)
                ),
            )
    elif form in ("behavioral", "charge", "flux", "vol", "cur", "value"):
        reads = {"F": "I(Vs)", "H": "I(Vs)"}.get(letter, "v(vs)" if ng else "V(vs)")
        if form == "charge":
            reads = "v(a)" if ng else "x"
        elif form == "flux":
            reads = "x"
        text = f"3*{reads}"
        add(
            f"set_expression {text}",
            lambda n: n.set_expression(d, text, scope=scope, in_definition=inside),
        )
        if form == "behavioral":
            quantity = str(line.struct["quantity"])
            name = "tc1" if ng else {"v": "ic", "i": "Rpar", "r": "Rpar", "p": "vprx"}[quantity]
            # On LTspice a new parameter goes before `laplace=` (D3-1, fixed by M18 D7).
            setter(name, "1")
            removals()
        elif form == "charge":
            setter("tc1" if ng else "ic", "1")
            removals()
    elif form in ("table", "table4", "freq", "gate"):
        width = 3 if form == "freq" else 2
        count = int(str(line.struct["points"]))
        counts = [count]
        if form != "gate" and line.one_line_points:
            low = 2 if (form in ("table4", "table") and not ng) or form == "table4" else 1
            counts += [c for c in (low, count + 1) if c != count]
        for rows in counts:
            points = _points(rows, width, rows)
            add(
                f"set_table {rows} points",
                _bind(points, lambda n, p: n.set_table(d, p, scope=scope, in_definition=inside)),
            )
        if line.struct.get("expression") is not None and form != "gate":
            add(
                "set_expression",
                lambda n: n.set_expression(d, "v(vs)*2", scope=scope, in_definition=inside),
            )
        if ng and letter == "G":
            setter("m", "3")
            removals()
    elif form == "poly":
        count = int(str(line.struct["coefficients"]))
        counts = [count]
        if not line.coefficient_comments:
            counts += [c for c in (2 if ng else 1, count + 1) if c != count]
        for size in counts:
            values = [str(v) for v in range(size)]
            add(
                f"set_poly_coefficients {size}",
                _bind(
                    values,
                    lambda n, v: n.set_poly_coefficients(d, v, scope=scope, in_definition=inside),
                ),
            )
        if ng and letter in "FG":
            setter("m", "3")
            removals()
    elif form == "laplace":
        add(
            "set_expression",
            lambda n: n.set_expression(d, "3/(1+s/2k)", scope=scope, in_definition=inside),
        )
        for name, value in (("window", "2m"), ("nfft", "1024"), ("mtol", "2")):
            setter(name, value)
        removals()
    elif form == "lossless":
        setter("z0", "75")
        written = {name.lower() for name in line.params}
        if "td" in written:
            setter("td", "2n")
        else:
            setter("f", "100meg")
            setter("nl", "0.5")
        if ng:
            setter("ic", "1,0,1,0")
        removals(("ic", "nl"))
    elif form == "lossy":
        models("lm")
        model_param("lm", "R", "3", remove="R")
    elif form == "rc":
        models("um")
        setter("l", "7")
        setter("n", "3")
        removals(("n",))
        model_param("um", "Rperl", "20", remove="Cperl")
    elif form in ("txl", "cpl"):
        models("ym" if form == "txl" else "pm")
        setter("len", "2")
        removals()
        if form == "cpl":
            model_param("pm", "R", "2 0 2")
    elif form == "code-model":
        models("am")
        model_param("am", "gain", "3")
    elif form == "osdi":
        models("nm")
        setter("l", "1u")
        setter("w", "2u")
        removals()
    elif form == "special":
        setter("Vhigh", "5")
        setter("Rout", "1k")
        removals()
    elif form == "analyzer":
        setter("fend", "2k")
        setter("refnode", "out")
        setter("flist", "1k 2k")
        removals()
    return ops


def _changed(old: str, new: str) -> tuple[int, int]:
    """The region of ``old`` that differs from ``new``: what is left after the common prefix and
    suffix."""
    if old == new:
        return 0, 0  # nothing changed (the value was already the one set)
    shortest = min(len(old), len(new))
    start = 0
    while start < shortest and old[start] == new[start]:
        start += 1
    end = 0
    while end < shortest - start and old[-1 - end] == new[-1 - end]:
        end += 1
    return start, len(old) - end


def _span(netlist: Netlist, target: tuple[str, str], scope: tuple[str, ...]) -> tuple[int, int]:
    kind, name = target
    if kind == "model":
        span = netlist.models[name][0].span
    else:
        span = netlist.element(name, scope).span
    return span.start, span.end


def _step(netlist: Netlist, op: _Op, scope: tuple[str, ...], baseline: object) -> Netlist:
    """Apply ``op`` and check (a), (b) and (c); return the edited netlist."""
    before = netlist.text
    edited = op.run(netlist)
    # (a) the signature is the baseline's.
    assert edited.signature() == baseline, op.description
    # (b) idempotence; a removal applied again raises and writes nothing.
    if op.removal:
        written = edited.to_bytes()
        with pytest.raises(EditError):
            op.run(edited)
        assert edited.to_bytes() == written, op.description
    else:
        assert op.run(edited).to_bytes() == edited.to_bytes(), f"{op.description} twice"
    # (c) the change lies inside the target's item span; the text around it is unchanged.
    low, high = _span(netlist, op.target, scope)
    if before != edited.text:
        start, end = _changed(before, edited.text)
        assert low <= start and end <= high, (op.description, (start, end), (low, high))
    assert edited.text[:low] == before[:low], op.description
    assert edited.text[len(edited.text) - (len(before) - high) :] == before[high:], op.description
    return edited


@pytest.mark.parametrize("group", list(GROUPS))
@settings(max_examples=25, print_blob=True, deadline=None)
@given(seed=st.integers(), data=st.data())
def test_no_sequence_of_device_edits_changes_the_signature(
    group: str, seed: int, data: st.DataObject
) -> None:
    dialect = current_dialect()
    forms = [form for form in GROUPS[group] if form in FORMS[dialect]]
    written = write_netlist(dialect, forms, random.Random(seed))
    netlist = Netlist.from_text(written.text, dialect=dialect)
    baseline = netlist.signature()
    targets = [(line, scope) for line, scope, _ in written.elements]
    for _ in range(data.draw(st.integers(1, 5), label="steps")):
        line, scope = data.draw(st.sampled_from(targets), label="line")
        ops = _operations(netlist, line, scope)
        if not ops:
            assert line.form == "&-probe"  # the probe takes no edit (decision 0020 item 8)
            continue
        op = data.draw(st.sampled_from(ops), label="operation")
        netlist = _step(netlist, op, scope, baseline)


def _every_operation(form: str, seed: int) -> None:
    dialect = current_dialect()
    written = write_netlist(dialect, [form], random.Random(seed))
    netlist = Netlist.from_text(written.text, dialect=dialect)
    line, scope, _ = written.elements[0]
    ops = _operations(netlist, line, scope)
    assert ops or form == "&-probe"
    for op in ops:
        _step(netlist, op, scope, netlist.signature())


# The matrix itself: each operation of each form's table, once, from fixed lines, so that no
# operation is left to the draws of the property above. Each dialect runs only its own forms.


@pytest.mark.ngspice_only
@pytest.mark.parametrize("form", list(FORMS[Dialect.NGSPICE]))
@pytest.mark.parametrize("seed", range(3))
def test_every_ngspice_operation_holds(form: str, seed: int) -> None:
    _every_operation(form, seed)


@pytest.mark.ltspice_only
@pytest.mark.parametrize("form", list(FORMS[Dialect.LTSPICE]))
@pytest.mark.parametrize("seed", range(3))
def test_every_ltspice_operation_holds(form: str, seed: int) -> None:
    _every_operation(form, seed)
