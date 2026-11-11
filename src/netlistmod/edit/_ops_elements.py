"""Element operations: values, parameters, models and couplings (architecture §7.2)."""

from __future__ import annotations

from collections.abc import Callable

from netlistmod.dialects import Dialect
from netlistmod.document import Netlist, ScopePath
from netlistmod.document.models import model_type_allowed, model_type_requirement
from netlistmod.edit import conventions
from netlistmod.edit._ops_common import (
    _MODEL,
    _NO_LTSPICE_MODEL,
    _PORT_PARAMS,
    _POSITIONAL_AREA,
    _SOURCES,
    _TRANSISTORS,
    _TWO_TERMINAL,
    _VALUE,
    _VALUE_KEYWORDS,
    _comment_inside,
    _element,
    _insert,
    _kind,
    _last_field_end,
    _refuse_impedance_flag,
    _refuse_over_comment,
)
from netlistmod.edit._ops_nonlinear import use_instead
from netlistmod.edit.plan import Edit, SlotCheck
from netlistmod.errors import EditError
from netlistmod.model.nodes import (
    BehavioralSource,
    BipolarTransistor,
    Cccs,
    CodeModelDevice,
    ControlledSource,
    Diode,
    FraProbe,
    FrequencyAnalyzer,
    Jfet,
    LosslessLine,
    LossyLine,
    Mesfet,
    MutualCoupling,
    OsdiDevice,
    SpecialFunction,
    SubcktInstance,
    Switch,
    TransmissionLine,
    Vccs,
    Vcvs,
    VoltageSource,
)
from netlistmod.model.values import (
    Flag,
    ModelReference,
    ParamAssignment,
    ValueList,
)

_LAPLACE_PARAMS = ("window", "nfft", "mtol")
# The two spellings of a T line's impedance, which name one parameter (decision 0019).
_IMPEDANCE = ("z0", "zo")


def set_value(
    netlist: Netlist,
    designator: str,
    value: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
    reason: str = "",
) -> list[Edit]:
    """Replace the value of an R, C or L line, or add one after the nodes; replace a source's
    DC value (never adding one or a ``DC`` keyword); or replace the gain of an E, F, G or H
    line (decision 0015 item 10)."""
    element = _element(netlist, designator, scope, in_definition)
    reason = reason or f"set_value {designator}"
    if isinstance(element, _TWO_TERMINAL):
        if element.value is not None:
            return [Edit(element.value.span, value, reason, (_VALUE,))]
        point = element.nodes[-1].span.end
        return [_insert(point, conventions.field(value), reason, _VALUE, 1)]
    if isinstance(element, _SOURCES):
        if element.dc is None:
            raise EditError(f"`{designator}` has no DC value to replace; use set_dc to add one")
        return [Edit(element.dc.span, value, reason, (_VALUE,))]
    if isinstance(element, ControlledSource):
        if element.value is None:
            if element.form in ("vol", "cur", "value"):
                raise EditError(
                    f"`{designator}` is written as an expression (`{element.form}`); "
                    "use set_expression"
                )
            raise EditError(
                f"`{designator}` is written as {element.form} and has no gain; "
                f"use {use_instead(element)}"
            )
        return [Edit(element.value.span, value, reason, (_VALUE,))]
    if isinstance(element, MutualCoupling):
        raise EditError(f"`{designator}` is a coupling; use set_coupling to set its value")
    if isinstance(element, LossyLine):
        raise EditError(
            f"`{designator}` is a {_kind(element)} and has no value slot; its values are in its "
            "LTRA model (use set_model_param)"
        )
    if isinstance(element, TransmissionLine | OsdiDevice | SpecialFunction | FrequencyAnalyzer):
        raise EditError(
            f"`{designator}` is a {_kind(element)} and has no value slot; use set_param to set "
            "its parameters"
        )
    if isinstance(element, CodeModelDevice):
        raise EditError(
            f"`{designator}` is a {_kind(element)} and has no value slot; its values are on its "
            "`.model` line (use set_model_param)"
        )
    raise EditError(f"`{designator}` is a {_kind(element)} line and has no value slot")


def set_param(
    netlist: Netlist,
    designator: str,
    name: str,
    value: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Set or add an instance parameter of an R, C, L, D, Q, M, J or Z line, ``m=`` of an
    ngspice F or G line (decision 0015 item 7), a parameter of an LTspice V or I line, or one of
    a T, U, Y or P line (decision 0019; a T keeps its spelling of ``Z0=`` or ``Zo=``), or one of an
    ngspice N, an LTspice A or an ``@`` line (decision 0020 item 9).
    ``area`` goes in the positional slot where the dialect writes one (decision 0014 item 5),
    unless the line already writes ``area=``."""
    element = _element(netlist, designator, scope, in_definition)
    reason = f"set_param {designator} {name}"
    found_fold = netlist.scope(scope).fold
    folded = found_fold(name)
    ltspice = netlist.dialect is Dialect.LTSPICE
    if isinstance(element, SubcktInstance):
        raise EditError(f"`{designator}` is a subcircuit call; use set_instance_param")
    if isinstance(element, ControlledSource | Switch):
        # An ngspice F or G takes m= (decision 0015 item 7), and an LTspice E or G with Laplace=
        # takes window=, nfft= and mtol= (decision 0017).
        laplace = (
            ltspice
            and isinstance(element, Vcvs | Vccs)
            and element.form == "laplace"
            and folded in {found_fold(word) for word in _LAPLACE_PARAMS}
        )
        meter = not ltspice and isinstance(element, Cccs | Vccs) and folded == found_fold("m")
        if not (laplace or meter):
            if ltspice:
                named = folded in {found_fold(word) for word in _LAPLACE_PARAMS}
                only = "; only a line with `Laplace=` takes it" if named else ""
            else:
                only = "; on ngspice only F and G take `m=`"
            raise EditError(f"`{designator}` takes no parameter `{name}`{only}")
        return _assign(element.params, element, name, value, reason, folded=found_fold)
    if isinstance(element, LossyLine):
        raise EditError(
            f"`{designator}` is a {_kind(element)} and takes no parameter; its values are in its "
            "LTRA model (use set_model_param)"
        )
    if isinstance(element, CodeModelDevice):
        raise EditError(
            f"`{designator}` is a {_kind(element)} and takes no parameter on its line; a code "
            "model's parameters are on its `.model` line (use set_model_param)"
        )
    if isinstance(element, FraProbe):
        raise EditError(
            f"`{designator}` is a {_kind(element)}: four nodes and no parameters; its analyzer's "
            "parameters are on the `@` line"
        )
    if isinstance(element, FrequencyAnalyzer):
        return _analyzer_param(netlist, element, name, value, reason, found_fold)
    if isinstance(element, OsdiDevice | SpecialFunction):
        return _assign(element.params, element, name, value, reason, folded=found_fold)
    if isinstance(element, TransmissionLine):
        if isinstance(element, LosslessLine) and folded in _IMPEDANCE:
            # Z0= and Zo= are one parameter: the line keeps the spelling it writes.
            written = [param for param in element.params if found_fold(param.name) in _IMPEDANCE]
            if len(written) == 1:
                return [Edit(written[0].value.span, value, reason, (_VALUE,))]
        return _assign(element.params, element, name, value, reason, folded=found_fold)
    takes_params = (*_TWO_TERMINAL, Diode, *_TRANSISTORS, *_SOURCES, BehavioralSource)
    port = isinstance(element, VoltageSource) and folded in _PORT_PARAMS
    if not isinstance(element, takes_params) or (
        not ltspice and isinstance(element, _SOURCES) and not port
    ):
        raise EditError(f"`{designator}` is a {_kind(element)} line and takes no parameters")
    if (
        isinstance(element, _TWO_TERMINAL)
        and not ltspice
        and folded in _VALUE_KEYWORDS[type(element)]
    ):
        if element.value_keyword is None or element.value is None:
            raise EditError(
                f"`{name}` names the value of `{designator}`, which is not written as "
                f"`{name}=…`; use set_value"
            )
        return [Edit(element.value.span, value, reason, (_VALUE,))]
    for flag in getattr(element, "flags", ()):
        # A flag takes its value in place: `noiseless=1` -> `noiseless=0`, `off` -> `off=1`.
        if found_fold(flag.name) == folded:
            if flag.value is not None:
                return [Edit(flag.value.span, value, reason, (_VALUE,))]
            text = f"={value}"
            return [_insert(flag.span.end, text, reason, _VALUE, 1)]
    # The area is positional, right after the model, unless it is written `area=`: LTspice's D
    # and Q, and J and Z on both dialects. An ngspice D and Q write `area=` only.
    if (
        isinstance(element, Diode | BipolarTransistor | Jfet | Mesfet)
        and folded == _POSITIONAL_AREA
        and (ltspice or isinstance(element, Jfet | Mesfet))
    ):
        if any(found_fold(param.name) == folded for param in element.params):
            return _assign(element.params, element, name, value, reason, folded=found_fold)
        if element.area is not None:
            return [Edit(element.area.span, value, reason, (_VALUE,))]
        return [_insert(element.model.span.end, conventions.field(value), reason, _VALUE, 1)]
    return _assign(element.params, element, name, value, reason, folded=found_fold)


def _analyzer_param(
    netlist: Netlist,
    element: FrequencyAnalyzer,
    name: str,
    value: str,
    reason: str,
    folded: Callable[[str], str],
) -> list[Edit]:
    """A parameter of an ``@`` line: a list is replaced whole, unless a comment lies inside it;
    ``refnode=`` and ``intnode=`` take a net name; ``zm`` is not editable (decision 0020
    item 9)."""
    designator = element.designator
    _refuse_impedance_flag(element, name)
    matches = [param for param in element.params if folded(param.name) == folded(name)]
    if len(matches) == 1 and isinstance(matches[0].value, ValueList):
        comment = _comment_inside(element, matches[0].value.span)
        if comment is not None:
            raise _refuse_over_comment(
                netlist, comment, f"the list `{matches[0].name}=` of `{designator}`"
            )
    return _assign(element.params, element, name, value, reason, folded=folded)


def set_instance_param(
    netlist: Netlist,
    designator: str,
    name: str,
    value: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Set or add a parameter override on an X line (the per-instance edit of §7.4)."""
    element = _element(netlist, designator, scope, in_definition)
    if not isinstance(element, SubcktInstance):
        raise EditError(f"`{designator}` is not a subcircuit call; use set_param")
    reason = f"set_instance_param {designator} {name}"
    return _assign(element.params, element, name, value, reason, folded=netlist.scope(scope).fold)


def _assign(
    params: tuple[ParamAssignment, ...],
    owner: object,
    name: str,
    value: str,
    reason: str,
    after: int | None = None,
    *,
    folded: Callable[[str], str],
) -> list[Edit]:
    """Replace the value of parameter ``name`` or add ``name=value`` after the last field
    (or after offset ``after``); ``folded`` is the dialect's name comparison."""
    matches = [param for param in params if folded(param.name) == folded(name)]
    if len(matches) > 1:
        raise EditError(f"{reason}: parameter `{name}` is repeated; the edit has no single target")
    if matches:
        return [Edit(matches[0].value.span, value, reason, (_VALUE,))]
    point = _last_field_end(owner) if after is None else after
    text = conventions.field(conventions.assignment(name, value))
    # A flag's keyword may be written with a value too (LTspice), which parses as a Flag.
    return [_insert(point, text, reason, SlotCheck((ParamAssignment, Flag), "a parameter"), 1)]


def set_model(
    netlist: Netlist,
    designator: str,
    model: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
    allow_external: bool = False,
) -> list[Edit]:
    """Replace the model name of an R, C, L, D, Q, M, J, Z, S, W, O, U, Y, P, ngspice A or N line,
    or add one after the value of an R, C or L line that has none (decision 0007 item 3; review
    round 1; decisions 0014 and 0015: S takes an SW model and W a CSW model; decision 0019: O takes
    LTRA, U URC, Y TXL and P CPL; decision 0020: A and N take any type that is not built in)."""
    element = _element(netlist, designator, scope, in_definition)
    if isinstance(element, LosslessLine):
        raise EditError(f"`{designator}` is a {_kind(element)} and has no model")
    if isinstance(element, SpecialFunction):
        raise EditError(
            f"`{designator}` is a {_kind(element)}: its function `{element.function.name}` is not "
            "a model and is not editable, because it changes what the device is; edit the line "
            "by hand"
        )
    if not isinstance(
        element,
        (
            *_TWO_TERMINAL,
            Diode,
            *_TRANSISTORS,
            Switch,
            TransmissionLine,
            CodeModelDevice,
            OsdiDevice,
        ),
    ):
        raise EditError(f"`{designator}` is a {_kind(element)} line and has no model")
    if netlist.dialect is Dialect.LTSPICE and isinstance(element, _TWO_TERMINAL):
        raise EditError(f"`{designator}` takes no model: {_NO_LTSPICE_MODEL}")
    if (
        isinstance(element, _TWO_TERMINAL)
        and element.model is None
        and element.value_keyword is not None
    ):
        raise EditError(
            f"`{designator}` writes its value as `{element.value_keyword}=…`, a form that takes "
            "no model; use set_value to write a positional value first"
        )
    chain = tuple(netlist.scope(scope).chain())
    key = chain[0].fold(model)
    definition = next((found.models[key][0] for found in chain if key in found.models), None)
    if definition is not None:
        if not model_type_allowed(element, definition.model_type, netlist.dialect):
            raise EditError(
                f"model `{model}` has type `{definition.model_type}`, but `{designator}` "
                f"takes {model_type_requirement(element, netlist.dialect)}"
            )
    else:
        searched = ", ".join(found.describe() for found in chain)
        include = any(found.may_define_elsewhere for found in chain)
        if not include:
            raise EditError(f"model `{model}` is not defined (searched: {searched})")
        if not allow_external:
            raise EditError(
                f"model `{model}` is not defined (searched: {searched}); it may be defined in "
                "an `.include` or `.lib` file or an opaque block, which is not read: pass "
                "allow_external=True to "
                "set it without a type check"
            )
    reason = f"set_model {designator}"
    current = getattr(element, "model", None)
    if isinstance(current, ModelReference):
        return [Edit(current.span, model, reason, (_MODEL,))]
    # Without a model the grammar requires a value; the model goes right after it.
    assert isinstance(element, _TWO_TERMINAL) and element.value is not None
    return [_insert(element.value.span.end, conventions.field(model), reason, _MODEL, 1)]


def remove_value(
    netlist: Netlist,
    designator: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Remove the value of an R, C or L line that also names a model, so the model's geometry
    applies (review round 1). The separator before the value stays."""
    element = _element(netlist, designator, scope, in_definition)
    if not isinstance(element, _TWO_TERMINAL):
        raise EditError(f"`{designator}` is a {_kind(element)} line; only R, C and L have a value")
    if netlist.dialect is Dialect.LTSPICE:
        raise EditError(f"`{designator}` needs its value: {_NO_LTSPICE_MODEL}")
    if element.value is None:
        raise EditError(f"`{designator}` has no value to remove")
    if element.model is None:
        raise EditError(
            f"`{designator}` has no model, so it needs its value; add a model with set_model first"
        )
    return [Edit(element.value.span, "", f"remove_value {designator}")]


def set_coupling(
    netlist: Netlist,
    designator: str,
    value: str,
    *,
    scope: ScopePath = (),
    in_definition: bool = False,
) -> list[Edit]:
    """Replace the coupling value of a ``K`` line."""
    element = _element(netlist, designator, scope, in_definition)
    if not isinstance(element, MutualCoupling):
        raise EditError(f"`{designator}` is a {_kind(element)} line, not a coupling")
    return [Edit(element.value.span, value, f"set_coupling {designator}", (_VALUE,))]
