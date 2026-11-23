"""Rules for xyce's statements and element lines: `.SUBCKT` defaults, the includes and `.LIB`
(X-M1 B4; decision 0027 item 7), the R, C, L, V, I and D forms that differ from the other
dialects (X-M1 B5; decision 0027 items 5 and 6), the analyses and `.STEP` (X-M2 B2; decision
0028 items 3 and 4), the options, initial conditions, measurements and the `.DATA` block (X-M2
B3; decision 0028 items 5 to 8), the closed list's untyped dot-commands (X-M2 B4; decision
0028 item 1) and `.PRINT` (X-M2.1 C3; decision 0029 item 5)."""

from __future__ import annotations

import difflib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, NoReturn

from lark import Token

from netlistmod.dialects import _XYCE, Dialect, fold_name
from netlistmod.model._numbers import reads_as_number
from netlistmod.model._rules_statements import StatementsRules
from netlistmod.model._rules_xyce_sources import XyceSourcesRules
from netlistmod.model._tree import (
    _common,
    _dot,
    _Element,
    _Field,
    _field_token,
    _field_tokens,
    _Item,
    _ListKeyword,
    _Name,
    _span,
    _XRest,
)
from netlistmod.model.nodes import (
    AcDirective,
    Capacitor,
    DataTable,
    DcDirective,
    DcSweep,
    IcDirective,
    Inductor,
    LibCall,
    MeasureDirective,
    Node,
    NodeCondition,
    NodesetDirective,
    OpaqueBlock,
    OpaqueStatement,
    OptionItem,
    OptionsDirective,
    PrintDirective,
    Resistor,
    StepDirective,
    TranDirective,
    UnknownDirective,
)
from netlistmod.model.values import (
    Flag,
    Formula,
    Identifier,
    ModelReference,
    NumericValue,
    ParamAssignment,
    Value,
    ValueList,
)
from netlistmod.source import Span

# Whether R, C and L take xyce's forms (decision 0027 item 5): the model right after the nodes,
# then the value, which may also be written `R=`, `C=` or `L=` (and the charge `Q=` on C). The
# other dialects read their own forms in ElementsRules.
_MODEL_FIRST: dict[Dialect, bool] = {
    Dialect.NGSPICE: False,
    Dialect.LTSPICE: False,
    _XYCE: True,
}
# Whether an instance parameter written twice on an element line is refused (xyce: Xyce 7.10 runs
# `R1 a 0 1k L=1u L=2u` and `X1 a s PARAMS: r=1 r=2`, silently using one of the values; R1
# review). The other dialects read such a line as they always have.
_INSTANCE_REPEAT_REFUSED: dict[Dialect, bool] = {
    Dialect.NGSPICE: False,
    Dialect.LTSPICE: False,
    _XYCE: True,
}
# The long value keywords of ngspice, which Xyce stops on ("Unrecognized parameter").
_LONG_KEYWORDS = {"resistance": "R", "capacitance": "C", "inductance": "L"}
# Each letter's closed instance-parameter list, as the grammar's R_PARAM_KW, C_PARAM_KW,
# L_PARAM_KW and D_PARAM_KW hold it (xm1-tasks 5.1 point 29), for the message that refuses a name
# outside it: the device, the tables, and the names.
_PARAM_LISTS: dict[str, tuple[str, str, str]] = {
    "r": (
        "resistor",
        "Xyce reference manual §2.3.7 p203–205, Tables 2-42 and 2-44",
        "a, density, dtemp, heatcapacity, l, m, outputintvars, r, resistivity, tc (or tc1 and "
        "tc2), tce, temp, thermal_a, thermal_heatcapacity, thermal_l and w",
    ),
    "c": (
        "capacitor",
        "Xyce reference manual §2.3.4 p187, Table 2-37",
        "age, c, d, dtemp, ic, l, m, q, tc (or tc1 and tc2), temp and w",
    ),
    "l": (
        "inductor",
        "Xyce reference manual §2.3.5 p193, Table 2-39",
        "dtemp, ic, l, m, tc (or tc1 and tc2) and temp",
    ),
    "d": (
        "diode",
        "Xyce reference manual §2.3.8 p208–213, Tables 2-46, 2-48 and 2-51",
        "ab, area, dtemp, ic, lg, ls, m, mult, off, perim, pj and temp",
    ),
    "q": (
        "bipolar transistor",
        "Xyce reference manual §2.3.17 p247–279, Tables 2-67, 2-69, 2-71, 2-73, 2-75, 2-80 and "
        "2-83",
        "area, dt, dta, dtemp, ic (or ic1 and ic2), l, m, mult, n, off, sw_et, sw_noise, temp, "
        "trise and w",
    ),
    "m": (
        "MOSFET",
        "Xyce reference manual §2.3.20 p304–745, Tables 2-92, 2-94, 2-96, 2-98, 2-100, 2-102, "
        "2-104, 2-106, 2-108, 2-111, 2-114, 2-117, 2-120, 2-123, 2-126, 2-129, 2-132, 2-135, "
        "2-140, 2-143, 2-145 and 2-147",
        "abdrain, absource, acnqsmod, ad, adej, adeo, adrain, aebcp, agbcp, agbcp2, agbcpd, "
        "as, asej, aseo, asource, bjtoff, cdsp, cgdp, cgsp, covd, covs, cth0, d, dach1, "
        "dach2, dach3, dach4, dach5, dach6, debug, delvt0, delvto, delvtoedge, delvtrand, "
        "dta, dtemp, dws1, dws2, dws3, dws4, dws5, dws6, factuo, factuoedge, fpitch, frbody, "
        "geomod, hpff, ic (or ic1 to ic5), ids0mult, igb0mult, igc0mult, jw, l, lgdrain, "
        "lgsource, lrsd, lsdrain, lssource, m, min, minz, mobscmod, mult, nbc, nf, nfin, "
        "nfinnom, ngaa, ngcon, ngf, nqsmod, nrb, nrd, nrs, ns, nseg, off, pd, pdbcp, pdej, "
        "pdeo, pdrain, ps, psbcp, psej, pseo, psource, rbdb, rbodymod, rbpb, rbpd, rbps, "
        "rbsb, rgatemod, rgeomod, rth0, sa, sb, sc, sca, scb, scc, sd, shmod, soimod, "
        "subbandmod, temp, tfin, tgaa, tnodeout, trnqsmod, tsus, u0mult, vbsusr, vfbsdoff, "
        "vldebug, w, wgaa, xgw, xl and xw",
    ),
    "jz": (
        "JFET or MESFET",
        "Xyce reference manual §2.3.18 p287–288, Tables 2-86 and 2-88, and Xyce reference manual "
        "§2.3.19 p291, Table 2-90",
        "area, dtemp and temp",
    ),
}
# Why a number or expression after an M's model is refused (decision 0031 item 3; 5.1 point 5).
_NO_M_AREA = (
    "a Xyce MOSFET has no area, and Xyce stops on it (Xyce reference manual §2.3.20 p292); a "
    "number stands on an M line only as a node, before the model, or as a parameter's value"
)
# What a line of each letter needs when it has no value (decision 0027 item 5, as amended).
_VALUE_FORMS: dict[type, str] = {
    Resistor: "a value, positional or `R=`, or a model with `L=`",
    Capacitor: "a value, positional or `C=`, a charge `Q=`, or `L=`",
    Inductor: "a value, positional or `L=`",
}


@dataclass(frozen=True, slots=True)
class _Schedule:
    """The `{schedule(...)}` field of an xyce `.TRAN`, kept apart from the positional values."""

    formula: Formula


@dataclass(frozen=True, slots=True)
class _DataRef:
    """`DATA=table` on an xyce `.AC`, `.DC` or `.STEP`: the keyword and the table's name."""

    keyword: Token
    table: Identifier


@dataclass(frozen=True, slots=True)
class _SweepTarget:
    """The target of an xyce `.DC` sweep or `.STEP`, a name that may hold `:`."""

    token: Token


@dataclass
class _OpenSweep:
    """A `.DC` sweep while its fields are gathered."""

    target: Token
    variation: Token | None
    listed: bool = False
    values: list[Value] = field(default_factory=list)


# The `.OPTIONS` packages of [xyce-ref] §2.1.25 p96, folded (decision 0028 item 5), those that
# take braces and quotes in a value, and those that take the INITIAL_INTERVAL pairs.
_OPTION_PACKAGES = (
    "device",
    "diagnostic",
    "timeint",
    "nonlin",
    "nonlin-tran",
    "nonlin-hb",
    "loca",
    "linsol",
    "linsol-hb",
    "linsol-ac",
    "output",
    "restart",
    "samples",
    "embeddedsamples",
    "pces",
    "sensitivity",
    "hbint",
    "dist",
    "fft",
    "measure",
    "parser",
)
_DELIMITED_PACKAGES = frozenset({"samples", "embeddedsamples"})
_INTERVAL_PACKAGES = frozenset({"output", "restart"})
_PACKAGE_LIST = ", ".join(name.upper() for name in _OPTION_PACKAGES)


@dataclass(frozen=True, slots=True)
class _OptPackage:
    """The package word of an xyce `.OPTIONS` line, read or recognised to be refused."""

    token: Token


@dataclass(frozen=True, slots=True)
class _OptItem:
    """An xyce option item's name and its value or comma list, before its pairs are known."""

    name: Token
    values: tuple[Value | Identifier, ...]


@dataclass(frozen=True, slots=True)
class _OptExtra:
    """A field after an option item that is not `name=value`."""

    value: Value | Identifier


@dataclass(frozen=True, slots=True)
class _MeasText:
    """One field of an xyce `.MEASURE` body."""

    token: Token


@dataclass(frozen=True, slots=True)
class _PrintText:
    """One field of an xyce `.PRINT` line after its print type."""

    token: Token


# The print types of the manual's closed list ([xyce-ref] §2.1.31 p128, §2.1.31.6 and §2.1.31.7;
# decision 0029 item 5), as the refusal of another word names them: the grammar's PRINT_TYPE_KW
# list, which a test ties to this text and to the document layer's `_XYCE_PRINT_RULES`.
_PRINT_TYPES = (
    "AC, AC_IC, DC, ES, HB, HB_FD, HB_IC, HB_STARTUP, HB_TD, NOISE, PCE, TRAN, HOMOTOPY, SENS and "
    "TRANADJOINT"
)


@dataclass(frozen=True, slots=True)
class _IcRefused:
    """A refused `.IC`, `.DCVOLT` or `.NODESET` field (`I(...)`, `all=`, `V(a,b)`), refused by the
    statement, whose keyword decides what Xyce does with it."""

    opener: Token


@dataclass(frozen=True, slots=True)
class _ValueKeyword:
    """An xyce R, C or L value written as its parameter (`R=`, `C=`, `L=`), or a C's charge
    `Q=` (``charge``): the whole assignment, which keeps the keyword's span for the edits."""

    assignment: ParamAssignment
    charge: bool


class XyceRules(StatementsRules, XyceSourcesRules):
    """Rules for xyce's statements that the other dialects spell differently."""

    def subckt_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    def reserved_default(self, children: list[Any]) -> NoReturn:
        name = _field_token(children)
        raise self._parse_error(
            name,
            f"`{name}` is a reserved word (time, freq, hertz, vt, temp, temper, gmin, pi and exp) "
            "and cannot be a subcircuit parameter (Xyce reference manual §2.1.26 p121); Xyce "
            "stops on time, vt, temp and gmin, and ignores the others",
        )

    def path_field(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: Identifier(str(token), _span(token)))

    def _opaque_raw(self, element: _Element) -> str:
        """The text from the keyword to the end of the last field, across `+` lines."""
        last = element.all(Identifier)[-1]
        return self._source.text[_span(element.designator).start : last.span.end]

    def include_line(self, children: list[Any]) -> _Item:
        element = _Element(children)
        raw = self._opaque_raw(element)
        comments = element.comments
        return _Item(element.end, lambda span: OpaqueStatement("include", raw, span, comments))

    def lib_call(self, children: list[Any]) -> _Item:
        element = _Element(children)
        raw = self._opaque_raw(element)
        comments = element.comments
        entries = element.all(Identifier)[1:]
        return _Item(element.end, lambda span: LibCall("lib", raw, span, comments, entries))

    def lib_open(self, children: list[Any]) -> Identifier:
        field: _Field = children[1]
        assert isinstance(field.node, Identifier)
        return field.node

    def lib_open_end(self, children: list[Any]) -> None:
        return None

    def lib_text(self, children: list[Any]) -> None:
        return None

    def lib_close(self, children: list[Any]) -> tuple[Token, Identifier | None, int]:
        element = _Element(children)
        return element.designator, element.optional(Identifier), element.end

    def lib_section(self, children: list[Any]) -> _Item:
        name: Identifier = children[0]
        keyword, closing, end = children[-1]
        if closing is None:
            raise self._parse_error(
                keyword,
                f"`{keyword}` without a name: it must name the library entry it closes, "
                f"`{keyword} {name.name}` (Xyce reference manual §2.1.16.2 p51); Xyce stops on it",
            )
        if fold_name(closing.name, self._dialect) != fold_name(name.name, self._dialect):
            raise self._error_at(
                closing.span.start,
                f"`{keyword} {closing.name}` closes the library entry `{name.name}`: the names "
                "must match (Xyce reference manual §2.1.16.2 p51); Xyce stops on it",
            )
        return _Item(end, lambda span: OpaqueBlock("lib", span))

    # Element lines (X-M1 B5).

    def inst_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    def r_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    def r_keyword(self, children: list[Any]) -> _Field:
        return self._value_keyword(children, charge=False)

    c_keyword = r_keyword

    l_keyword = r_keyword

    def q_charge(self, children: list[Any]) -> _Field:
        return self._value_keyword(children, charge=True)

    def _value_keyword(self, children: list[Any], *, charge: bool) -> _Field:
        field = self.param(children)
        if isinstance(field.node, _ValueKeyword):
            return field  # the gap before a field on a `+` line, around the inner field
        assert isinstance(field.node, ParamAssignment)
        return _Field(_ValueKeyword(field.node, charge=charge), field.comments)

    def c_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    def l_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    def d_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    def r_unlisted(self, children: list[Any]) -> NoReturn:
        self._unlisted("r", children)

    def c_unlisted(self, children: list[Any]) -> NoReturn:
        self._unlisted("c", children)

    def l_unlisted(self, children: list[Any]) -> NoReturn:
        self._unlisted("l", children)

    def d_unlisted(self, children: list[Any]) -> NoReturn:
        self._unlisted("d", children)

    def _unlisted(self, letter: str, children: list[Any]) -> NoReturn:
        """Refuse a parameter name outside the letter's closed list (xm1-tasks 5.1 point 29)."""
        name = _field_token(children)
        folded = fold_name(str(name), self._dialect)
        if folded in _LONG_KEYWORDS:
            raise self._parse_error(
                name,
                f"`{name}=` is not a Xyce parameter, and Xyce stops on it; write the value "
                f"positionally or as `{_LONG_KEYWORDS[folded]}=`",
            )
        device, tables, names = _PARAM_LISTS[letter]
        raise self._parse_error(
            name,
            f"`{name}=` is not a parameter of a Xyce {device}, and Xyce stops on it "
            f'("Unrecognized parameter"). The reference guide lists {names} ({tables})',
        )

    def xy_tc_param(self, children: list[Any]) -> _Field:
        # `TC=a,b` is a list of two; `TC=a` alone is an ordinary value.
        if any(isinstance(c, Token) and c.type == "CSEP" for c in children):
            return self.tc_param(children)
        return self.param(children)

    def d_flag(self, children: list[Any]) -> _Field:
        return self.flag(children)

    # Transistors (X-M4 B2; decision 0031 items 1 to 4). Only xyce.lark produces these rules.

    def xt_name(self, children: list[Any]) -> _Field:
        return self.t_name(children)

    xt_number = xt_name

    def xt_area(self, children: list[Any]) -> _Field:
        return self.t_area(children)

    def q_param(self, children: list[Any]) -> _Field:
        return self.param(children)

    jz_param = q_param

    def q_flag(self, children: list[Any]) -> _Field:
        return self.flag(children)

    def q_ic_param(self, children: list[Any]) -> _Field:
        return self._ic_list(
            children,
            2,
            "on a Q takes at most two values, Vbe and Vce (Xyce reference manual §2.3.17, Table "
            "2-67 p247)",
        )

    def _ic_list(self, children: list[Any], most: int, refusal: str) -> _Field:
        """An `IC=` comma list of at most ``most`` values (5.1 point 9)."""
        field = self.tc_param(children)
        param = field.node
        assert isinstance(param, ParamAssignment)
        if isinstance(param.value, ValueList) and len(param.value.values) > most:
            raise self._error_at(param.value.values[most].span.start, f"`{param.name}=` {refusal}")
        return field

    def q_unlisted(self, children: list[Any]) -> NoReturn:
        self._unlisted("q", children)

    # M (X-M4 B3; decision 0031 items 1 to 4).

    m_param = q_param
    m_flag = q_flag

    def m_ic_param(self, children: list[Any]) -> _Field:
        return self._ic_list(
            children,
            5,
            "on an M takes at most five values, BSIM-SOI's Vds, Vgs, Vbs, Ves and Vps (Xyce "
            "reference manual §2.3.20 p293–294)",
        )

    def m_unlisted(self, children: list[Any]) -> NoReturn:
        name = _field_token(children)
        if fold_name(str(name), self._dialect) == "area":
            raise self._parse_error(
                name,
                f"`{name}=`: a Xyce MOSFET has no area, and Xyce stops on it (Xyce reference "
                "manual §2.3.20 p292); write the geometry as `L=`, `W=`, `AD=` and `AS=`",
            )
        self._unlisted("m", children)

    def m_keyword(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        if keyword.type == "TNODEOUT_KW":
            # 5.1 point 7: the manual writes it bare (§2.3.20 p292), and Xyce stops on that.
            raise self._parse_error(
                keyword,
                f"`{keyword}` without a value: Xyce stops on it, although the reference guide "
                "writes it bare (Xyce reference manual §2.3.20 p292); write `TNODEOUT=1`",
            )
        raise self._parse_error(
            keyword,
            f"`{keyword}` is ngspice's VDMOS flag, not a flag of a Xyce MOSFET, whose flag is "
            "`OFF`; a Xyce VDMOS is an NMOS or PMOS model at `LEVEL=18` (Xyce reference manual "
            "§2.3.20 p292–296)",
        )

    def m_late_value(self, children: list[Any]) -> NoReturn:
        value = _field_token(children)
        raise self._parse_error(value, f"`{value}` after a flag or parameter: {_NO_M_AREA}")

    def mosfet(self, children: list[Any]) -> _Item:
        # A number or expression after the model stands in the area's place (decision 0031
        # item 3): the grammar reads it there only so that it is refused here.
        element = _Element(children)
        names = element.all(_Name)
        late = next((value.span for value in element.values()), None)
        if late is None and len(names) > 1 and names[-1].token.type == "NUMBER":
            late = _span(names[-1].token)
        if late is not None:
            written = self._source.text[late.start : late.end]
            raise self._error_at(late.start, f"`{written}` after the model: {_NO_M_AREA}")
        return self._xyce_transistor(children, super().mosfet)

    def jz_unlisted(self, children: list[Any]) -> NoReturn:
        self._unlisted("jz", children)

    def jz_off(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        raise self._parse_error(
            keyword,
            f"`{keyword}` is not a flag of a Xyce J or Z line, and Xyce stops on it; the "
            "reference guide lists area, dtemp and temp (Xyce reference manual §2.3.18 p287–288 "
            "and Xyce reference manual §2.3.19 p291)",
        )

    def xt_late_area(self, children: list[Any]) -> NoReturn:
        value = _field_token(children)
        raise self._parse_error(
            value,
            f"`{value}` after a flag or parameter: a positional area stands right after the "
            f"model (`<model> {value} ...`), or write it as `area={value}`",
        )

    def bjt(self, children: list[Any]) -> _Item:
        return self._xyce_transistor(children, super().bjt)

    def jfet(self, children: list[Any]) -> _Item:
        return self._xyce_transistor(children, super().jfet)

    def mesfet(self, children: list[Any]) -> _Item:
        return self._xyce_transistor(children, super().mesfet)

    def _xyce_transistor(self, children: list[Any], read: Callable[[list[Any]], _Item]) -> _Item:
        """Refuse a repeated parameter and an area written both ways on xyce, then read the line
        as every dialect does (decision 0031 items 3 and 4)."""
        item = read(children)
        if _INSTANCE_REPEAT_REFUSED[self._dialect]:
            element = _Element(children)
            params = element.all(ParamAssignment)
            self._refuse_repeats(params)
            flags = element.all(Flag)
            if len(flags) > 1:
                # Q's `OFF` or `OFF=`, in any combination: Xyce runs it (5.1 point 8).
                second = flags[1]
                written = f"{second.name}=" if second.value is not None else second.name
                raise self._error_at(
                    second.span.start,
                    f"`{written}` is written twice on this line (as `OFF` or `OFF=`); "
                    f"{self._dialect.display_name} silently uses one of them, so write it once",
                )
            names = element.all(_Name)
            positional = bool(element.values()) or (
                len(names) > 1 and names[-1].token.type == "NUMBER"
            )
            named = [p for p in params if fold_name(p.name, self._dialect) == "area"]
            if named and positional:
                raise self._error_at(
                    named[0].name_span.start,
                    f"the area is given twice, positionally and as `{named[0].name}=`; Xyce "
                    "stops on it, so write only one",
                )
        return item

    def x_name_node(self, children: list[Any]) -> _Field:
        return self.x_name(children)

    def x_last(self, children: list[Any]) -> _XRest:
        rest = super().x_last(children)
        if _INSTANCE_REPEAT_REFUSED[self._dialect]:
            self._refuse_repeats(rest.params)
        return rest

    def diode(self, children: list[Any]) -> _Item:
        if _INSTANCE_REPEAT_REFUSED[self._dialect]:
            self._refuse_repeats(_Element(children).all(ParamAssignment))
        return super().diode(children)

    def _refuse_repeats(self, params: tuple[ParamAssignment, ...]) -> None:
        """Refuse an instance parameter written twice: Xyce 7.10 runs the line and silently uses
        one of the values (the last on R, the first on X; R1 review)."""
        seen: set[str] = set()
        for param in params:
            folded = fold_name(param.name, self._dialect)
            if folded in seen:
                raise self._error_at(
                    param.name_span.start,
                    f"`{param.name}=` is written twice on this line; "
                    f"{self._dialect.display_name} silently uses one of the values, so write it "
                    "once",
                )
            seen.add(folded)

    def late_model(self, children: list[Any]) -> NoReturn:
        name = _field_token(children)
        if reads_as_number(str(name)):
            raise self._parse_error(name, f"`{name}` is a second value; the line takes one")
        raise self._parse_error(
            name,
            f"`{name}` after the value: Xyce writes the model before the value, right after "
            f"the nodes (`... {name} <value>`; Xyce reference manual §2.3.7 p201)",
        )

    def ac_bare(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        raise self._parse_error(
            keyword,
            f"`{keyword}` without a magnitude: write `{keyword} 0`; the library reads an AC part "
            "only with its magnitude, which the Xyce manual makes optional",
        )

    def resistor(self, children: list[Any]) -> _Item:
        if not _MODEL_FIRST[self._dialect]:
            return super().resistor(children)
        return self._model_first(Resistor, _Element(children))

    def capacitor(self, children: list[Any]) -> _Item:
        if not _MODEL_FIRST[self._dialect]:
            return super().capacitor(children)
        return self._model_first(Capacitor, _Element(children))

    def inductor(self, children: list[Any]) -> _Item:
        if not _MODEL_FIRST[self._dialect]:
            return super().inductor(children)
        return self._model_first(Inductor, _Element(children))

    def _model_first(self, kind: type[Resistor | Capacitor | Inductor], element: _Element) -> _Item:
        """An xyce R, C or L: the model if any, then the value, positional or as its keyword."""
        params = element.all(ParamAssignment)
        written = element.all(_ValueKeyword)
        keywords = tuple(field.assignment for field in written if not field.charge)
        charges = tuple(field.assignment for field in written if field.charge)
        # Xyce 7.10 runs a parameter or a keyword written twice and silently uses one of them.
        self._refuse_repeats((*params, *keywords, *charges))
        keyword = keywords[0] if keywords else None
        charge = charges[0] if charges else None
        names = {fold_name(param.name, self._dialect) for param in params}
        positional = next(iter(element.values()), None)
        if positional is not None and keyword is not None:
            raise self._error_at(
                keyword.name_span.start,
                f"the value is given twice, positionally and as `{keyword.name}=`; Xyce "
                "silently uses one of them, so write only one",
            )
        value: Value | None = positional
        if keyword is not None:
            assert isinstance(keyword.value, NumericValue | Formula)
            value = keyword.value
        model = element.optional(ModelReference)
        if model is not None:
            model = self._model_not_number(model, "the name after the nodes")
        formula: Formula | None = None
        if charge is not None:
            if value is not None:
                raise self._error_at(
                    charge.name_span.start,
                    f"a capacitance and a charge `{charge.name}=` on one line; Xyce silently uses "
                    "one of them, so write only one",
                )
            if not isinstance(charge.value, Formula):
                raise self._error_at(
                    charge.value.span.start,
                    f"`{charge.name}=` takes the charge as an expression, in braces or quotes "
                    f"(`{charge.name}={{...}}`)",
                )
            formula = charge.value
        if value is None and formula is None:
            self._require_value(kind, model, names, element)
        extra: dict[str, Any] = {"charge": formula} if kind is Capacitor else {}
        return _Item(
            element.end,
            lambda span: kind(
                **_common(element, span, params=params),
                value=value,
                value_keyword=keyword.name if keyword is not None else None,
                value_keyword_span=keyword.name_span if keyword is not None else None,
                model=model,
                flags=element.all(Flag),
                **extra,
            ),
        )

    def _require_value(
        self,
        kind: type[Resistor | Capacitor | Inductor],
        model: ModelReference | None,
        names: set[str],
        element: _Element,
    ) -> None:
        """Refuse an R, C or L line without its value, except the geometry forms: an R with a
        model and `L=` (Xyce takes RSH x L / W from the model, and the model's DEFW for a missing
        `W=`; [xyce-ref] §2.3.7 p203), and a C with `L=` (decision 0027 item 5, as amended and
        corrected at R1)."""
        if kind is Resistor and model is not None and "l" in names:
            return
        if kind is Capacitor and "l" in names:
            return
        letter = str(element.designator)[0].upper()
        hint = ""
        if model is not None:
            hint = (
                f"; `{model.model_name}` is read as the model, since a name right after the "
                f"nodes is one: write `{{{model.model_name}}}` for a parameter"
            )
        raise self._error_at(
            _span(element.designator).start,
            f"this {letter} line has no value: it needs {_VALUE_FORMS[kind]}{hint}",
        )

    # Analyses and `.STEP` (X-M2 B2; decision 0028 items 3 and 4). In a subcircuit body they are
    # refused by not_in_subckt (StatementsRules), whose message says Xyce ignores them there.

    def xy_tran_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        values = element.values()
        flags: dict[str, Flag] = {}
        for flag in element.all(Flag):
            folded = fold_name(flag.name, self._dialect)
            if folded in flags:
                raise self._error_at(
                    flag.span.start,
                    f"`{flag.name}` is written twice on this `.TRAN` line; write it once (NOOP "
                    "and UIC are synonyms, each at most once; Xyce reference manual §2.1.38 p161)",
                )
            flags[folded] = flag
        schedule = element.optional(_Schedule)
        return _Item(
            element.end,
            lambda span: TranDirective(
                **_dot(element, span),
                tstep=values[0],
                tstop=values[1],
                tstart=values[2] if len(values) > 2 else None,
                tmax=values[3] if len(values) > 3 else None,
                uic=flags.get("uic"),
                noop=flags.get("noop"),
                schedule=schedule.formula if schedule is not None else None,
            ),
        )

    def tran_flag(self, children: list[Any]) -> _Field:
        return self.flag(children)

    def tran_schedule(self, children: list[Any]) -> _Field:
        def build(token: Token) -> _Schedule:
            # SCHEDULE_FORMULA has one delimiter character at each end, braces or quotes.
            span = _span(token)
            text = self._source.text[span.start + 1 : span.end - 1]
            delimiter: Literal["{", "'"] = "{" if str(token).startswith("{") else "'"
            return _Schedule(Formula(text, delimiter, span))

        return self._field(children, build)

    def data_ref(self, children: list[Any]) -> _Field:
        def build(keyword: Token) -> _DataRef:
            table: Token = children[-1]
            return _DataRef(keyword, Identifier(str(table), _span(table)))

        return self._field(children, build)

    def xy_ac_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        data = element.optional(_DataRef)
        values = element.values()
        keyword = data.keyword if data is not None else element.all(Token)[0]
        ranged = data is None
        return _Item(
            element.end,
            lambda span: AcDirective(
                **_dot(element, span),
                variation=str(keyword),
                variation_span=_span(keyword),
                points=values[0] if ranged else None,
                fstart=values[1] if ranged else None,
                fstop=values[2] if ranged else None,
                data=data.table if data is not None else None,
            ),
        )

    def sweep_target(self, children: list[Any]) -> _Field:
        def build(token: Token) -> _SweepTarget:
            text = str(token)
            if reads_as_number(text):
                raise self._parse_error(
                    token, f"`{text}` stands where a sweep target is, and a target is a name"
                )
            if "" in text.split(":"):
                raise self._parse_error(
                    token,
                    f"`{text}` has an empty part around a `:`; a target is a name, "
                    "`device:parameter`, `model:parameter` or a path such as `X1:R5:R`",
                )
            return _SweepTarget(token)

        return self._field(children, build)

    def xy_dc_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        data = element.optional(_DataRef)
        sweeps: list[DcSweep] = []
        variation: Token | None = None
        current: _OpenSweep | None = None
        for node in element.fields:
            if isinstance(node, Token):  # LIN, DEC or OCT, before the next target
                variation = node
            elif isinstance(node, _SweepTarget):
                if current is not None:
                    sweeps.append(self._dc_sweep(current))
                current = _OpenSweep(node.token, variation)
                variation = None
            elif isinstance(node, _ListKeyword):
                assert current is not None
                current.listed = True
            elif isinstance(node, NumericValue | Formula):
                assert current is not None
                current.values.append(node)
        if current is not None:
            sweeps.append(self._dc_sweep(current))
        found = tuple(sweeps)
        return _Item(
            element.end,
            lambda span: DcDirective(
                **_dot(element, span),
                sweeps=found,
                data=data.table if data is not None else None,
            ),
        )

    def _dc_sweep(self, sweep: _OpenSweep) -> DcSweep:
        values = tuple(sweep.values)
        ranged = not sweep.listed
        target = _span(sweep.target)
        return DcSweep(
            str(sweep.target),
            target,
            values[0] if ranged else None,
            values[1] if ranged else None,
            values[2] if ranged else None,
            Span(target.start, values[-1].span.end),
            str(sweep.variation) if sweep.variation is not None else None,
            values if sweep.listed else (),
        )

    def xy_step_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        data = element.optional(_DataRef)
        target = element.optional(_SweepTarget)
        variation = next(iter(element.all(Token)), None)
        values = element.values()
        listed = element.optional(_ListKeyword) is not None
        kind: Literal["temp", "name", "qualified", "data"]
        parameter: str | None = None
        if data is not None:
            kind, name, name_span = "data", data.table.name, data.table.span
        else:
            assert target is not None
            name, name_span = str(target.token), _span(target.token)
            if ":" in name:
                kind, parameter = "qualified", name.rpartition(":")[2]
            elif fold_name(name, self._dialect) == "temp":
                kind = "temp"
            else:
                kind = "name"
        ranged = data is None and not listed
        return _Item(
            element.end,
            lambda span: StepDirective(
                **_dot(element, span),
                kind=kind,
                name=name,
                name_span=name_span,
                model_type=None,
                model=None,
                variation=str(variation) if variation is not None else None,
                variation_span=_span(variation) if variation is not None else None,
                start=values[0] if ranged else None,
                stop=values[1] if ranged else None,
                increment=values[2] if ranged else None,
                values=values if listed else (),
                file=None,
                parameter=parameter,
                data=data.table if data is not None else None,
            ),
        )

    def tran_early_schedule(self, children: list[Any]) -> NoReturn:
        schedule = _field_token(children)
        raise self._error_at(
            _span(schedule).start,
            "a schedule stands after the numbers and the NOOP and UIC flags, as the last field "
            "(`.TRAN tstep tstop [tstart [tmax]] [NOOP] [UIC] [{schedule(...)}]`; Xyce reference "
            "manual §2.1.38 p161)",
        )

    def step_second(self, children: list[Any]) -> NoReturn:
        target = _field_token(children)
        raise self._parse_error(
            target,
            f"a second sweep (`{target}`) on one `.STEP` line: Xyce silently runs only the last "
            "one, so write one `.STEP` line per sweep (they nest, the first innermost; Xyce "
            "reference manual §2.1.36 p155)",
        )

    def xy_step_param(self, children: list[Any]) -> NoReturn:
        keyword = _field_token(children)
        raise self._parse_error(
            keyword,
            f"`.STEP` takes no `{keyword}` keyword on Xyce, which stops on it: name the "
            "parameter directly, `.STEP name start stop step` (Xyce reference manual §2.1.36 "
            "p155)",
        )

    # Options, initial conditions, measurements and `.DATA` (X-M2 B3; decision 0028 items 5 to
    # 8). `.OPTIONS`, `.MEAS` and `.DATA` are refused in a body by not_in_subckt.

    def opt_package(self, children: list[Any]) -> _Field:
        return self._field(children, _OptPackage)

    def _opt_value(self, token: Token) -> Value | Identifier:
        if token.type != "WORD":
            return self._value(token)
        if reads_as_number(str(token)):
            raise self._parse_error(
                token,
                f"`{token}` is not a number Xyce reads: a number takes a scale factor and a unit "
                "of the device-field lists (Xyce users' manual Table 4-1 p42)",
            )
        return Identifier(str(token), _span(token))

    def opt_item(self, children: list[Any]) -> _Field:
        def build(name: Token) -> _OptItem:
            values = tuple(self._opt_value(token) for token in _field_tokens(children)[1:])
            return _OptItem(name, values)

        return self._field(children, build)

    def opt_extra(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _OptExtra(self._opt_value(token)))

    def xy_options_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        keyword = element.designator
        found = element.optional(_OptPackage)
        package = Identifier(str(found.token), _span(found.token)) if found is not None else None
        folded = fold_name(package.name, self._dialect) if package is not None else None
        if package is not None and folded not in _OPTION_PACKAGES:
            close = difflib.get_close_matches(folded or "", _OPTION_PACKAGES, n=1)
            hint = f" (did you mean `{close[0].upper()}`?)" if close else ""
            raise self._error_at(
                package.span.start,
                f"`{package.name}` is not an `.OPTIONS` package{hint}: the packages are "
                f"{_PACKAGE_LIST} (Xyce reference manual §2.1.25 p96); Xyce ignores a line with "
                "another package, with a warning",
            )
        groups: list[tuple[_OptItem, list[Value | Identifier]]] = []
        for node in element.fields:
            if isinstance(node, _OptItem):
                groups.append((node, []))
            elif isinstance(node, _OptExtra):
                if not groups:
                    self._refuse_bare(node.value)
                groups[-1][1].append(node.value)
        if not groups:
            where = package.span.start if package is not None else _span(keyword).start
            what = f"`{keyword} {package.name}`" if package is not None else f"`{keyword}`"
            raise self._error_at(
                where,
                f"{what} has no item: an `.OPTIONS` line takes a package and one or more "
                "`name=value` items (`.OPTIONS TIMEINT RELTOL=1e-3`; Xyce reference manual "
                "§2.1.25 p96)",
            )
        if package is None:
            self._check_packageless(keyword, groups)
        options = tuple(self._option_item(folded, item, extras) for item, extras in groups)
        return _Item(
            element.end,
            lambda span: OptionsDirective(**_dot(element, span), options=options, package=package),
        )

    def _check_packageless(
        self, keyword: Token, groups: list[tuple[_OptItem, list[Value | Identifier]]]
    ) -> None:
        """Only `.OPTION SCALE=v`, singular with one item, stands without a package."""
        first = groups[0][0].name
        scale = fold_name(str(first), self._dialect) == "scale"
        if scale and len(groups) == 1 and fold_name(str(keyword), self._dialect) == ".option":
            return
        if scale and len(groups) == 1:
            raise self._parse_error(
                first,
                f"`{keyword} {first}=` has no package: only the singular `.OPTION {first}=` "
                f"stands without one; write that, or `.OPTIONS PARSER {first}=` (Xyce reference "
                "manual §2.1.25.21 p119)",
            )
        folded = fold_name(str(first), self._dialect)
        if folded in ("temp", "tnom") and len(groups) == 1:
            # Observed (X-M2 B6): Xyce 7.10 applies `TEMP=` or `TNOM=` alone on a package-less
            # line, silently; any other package-less line it ignores, with a warning.
            raise self._parse_error(
                first,
                f"`{keyword}` needs a package before its items: write `.OPTIONS DEVICE "
                f"{folded.upper()}=` (Xyce reference manual §2.1.25.1 p98); Xyce applies a "
                f"package-less line whose only item is `{first}=`, silently, but the manual "
                "gives every item a package",
            )
        raise self._parse_error(
            first,
            f"`{keyword}` needs a package before its items, `{keyword} <package> {first}=...`, "
            f"the package one of {_PACKAGE_LIST} (Xyce reference manual §2.1.25 p96); Xyce "
            "ignores a line without one, with a warning",
        )

    def _refuse_bare(self, value: Value | Identifier) -> NoReturn:
        raise self._error_at(
            value.span.start,
            f"`{self._source.text[value.span.start : value.span.end]}` is not a `name=value` "
            "item: an `.OPTIONS` item is `name=value`, a list of values takes commas "
            "(`name=a,b`), and only OUTPUT's and RESTART's INITIAL_INTERVAL takes pairs of values "
            "after it (Xyce reference manual §2.1.25.9 p110); Xyce drops a bare field after an "
            "item silently, or stops on it",
        )

    def _option_item(
        self, package: str | None, item: _OptItem, extras: list[Value | Identifier]
    ) -> OptionItem:
        for value in item.values:
            if isinstance(value, Formula) and package not in _DELIMITED_PACKAGES:
                raise self._error_at(
                    value.span.start,
                    "an expression in braces or quotes is an option value only in the SAMPLES "
                    "and EMBEDDEDSAMPLES packages (Xyce reference manual §2.1.25.13 p113); write "
                    "a number or a word, as Xyce stops on it",
                )
        name_span = _span(item.name)
        pairs: tuple[tuple[Value, Value], ...] = ()
        if extras:
            interval = (
                package in _INTERVAL_PACKAGES
                and fold_name(str(item.name), self._dialect) == "initial_interval"
                and len(item.values) == 1
            )
            numbers = [value for value in extras if isinstance(value, NumericValue)]
            if not interval or len(numbers) != len(extras):
                self._refuse_bare(next(v for v in extras if not interval or v not in numbers))
            if len(numbers) % 2:
                raise self._error_at(
                    numbers[-1].span.start,
                    f"`{item.name}=` takes pairs `t i` after the interval, and "
                    f"`{numbers[-1].text}` has no partner: write an even number of values (Xyce "
                    "reference manual §2.1.25.9 p110)",
                )
            pairs = tuple(zip(numbers[::2], numbers[1::2], strict=True))
        last = pairs[-1][1] if pairs else item.values[-1]
        listed = len(item.values) > 1
        return OptionItem(
            str(item.name),
            name_span,
            None if listed else item.values[0],
            Span(name_span.start, last.span.end),
            values=item.values if listed else (),
            pairs=pairs,
        )

    def ic_voltage(self, children: list[Any]) -> _Field:
        def build(opener: Token) -> NodeCondition:
            # v( node ) = value: the node is the second field token, the value the last.
            tokens = _field_tokens(children)
            value = self._value(tokens[-1])
            node = Node(str(tokens[1]), _span(tokens[1]))
            return NodeCondition(node, value, Span(_span(opener).start, value.span.end))

        return self._field(children, build)

    def ic_refused(self, children: list[Any]) -> _Field:
        # Refused by `_conditions`, which knows the statement's keyword.
        if isinstance(children[-1], _Field):
            return children[-1]
        return _Field(_IcRefused(_field_token(children)), ())

    def _condition_outcome(self, keyword: Token, what: str) -> str:
        """What Xyce 7.10 does with a condition field it cannot read (X-M2 B6 probes): `.IC` and
        `.DCVOLT` warn and ignore it, `.NODESET` stops."""
        if fold_name(str(keyword), self._dialect) == ".nodeset":
            return f"Xyce stops on {what} on `.NODESET`"
        return f"Xyce ignores {what} on `{keyword}`, with a warning"

    def _refuse_condition(self, keyword: Token, opener: Token) -> NoReturn:
        nodeset = fold_name(str(keyword), self._dialect) == ".nodeset"
        if opener.type == "IC_CURRENT_OPEN":
            reason = (
                f"`{opener}...)`: an initial condition sets a node voltage only, `V(node)=value` "
                "or `node value` (Xyce reference manual §2.1.14 p48); "
                + self._condition_outcome(keyword, "a current")
            )
        elif opener.type == "ALL_KW":
            section = (
                "Xyce reference manual §2.1.22 p92"
                if nodeset
                else "Xyce reference manual §2.1.14 p48"
            )
            reason = (
                f"`{opener}=` is not a Xyce initial condition: name each node, `V(node)=value` "
                f"or `node value` ({section}); " + self._condition_outcome(keyword, "it")
            )
        else:
            reason = (
                "`V(a,b)`: an initial condition takes one node, `V(node)=value` (Xyce reference "
                "manual §2.1.14 p48); " + self._condition_outcome(keyword, "a difference")
            )
        raise self._parse_error(opener, reason)

    def _conditions(self, element: _Element) -> tuple[NodeCondition, ...]:
        conditions: list[NodeCondition] = []
        pending: Node | None = None
        refused = element.optional(_IcRefused)
        if refused is not None:
            self._refuse_condition(element.designator, refused.opener)
        for node in element.fields:
            if isinstance(node, NodeCondition):
                conditions.append(node)
            elif isinstance(node, Node):
                pending = node
            elif isinstance(node, NumericValue | Formula):
                assert pending is not None
                span = Span(pending.span.start, node.span.end)
                conditions.append(NodeCondition(pending, node, span, form="pair"))
                pending = None
        keyword = element.designator
        if pending is not None:
            raise self._error_at(
                pending.span.start,
                f"`{pending.name}` has no value: `{keyword}` takes `node value` pairs (Xyce "
                "reference manual §2.1.14 p48), and Xyce hangs on an odd number of fields",
            )
        if not conditions:
            raise self._parse_error(
                keyword,
                f"`{keyword}` has no condition: write `V(node)=value` or `node value` (Xyce "
                "reference manual §2.1.14 p48)",
            )
        first = conditions[0].form
        for condition in conditions:
            if condition.form != first:
                raise self._error_at(
                    condition.span.start,
                    f"this `{keyword}` line mixes `V(node)=value` and `node value`: write one "
                    "form per line (Xyce reference manual §2.1.14 p48); "
                    + self._condition_outcome(keyword, "the other form"),
                )
        return tuple(conditions)

    def xy_ic_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        conditions = self._conditions(element)
        return _Item(
            element.end, lambda span: IcDirective(**_dot(element, span), conditions=conditions)
        )

    def xy_nodeset_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        conditions = self._conditions(element)
        return _Item(
            element.end,
            lambda span: NodesetDirective(**_dot(element, span), conditions=conditions),
        )

    def meas_mode(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: token)

    def meas_field(self, children: list[Any]) -> _Field:
        return self._field(children, _MeasText)

    def meas_bad_mode(self, children: list[Any]) -> NoReturn:
        word = _field_token(children)
        hint = " (write `TRAN`)" if fold_name(str(word), self._dialect) == "tr" else ""
        raise self._parse_error(
            word,
            f"`{word}` is not a `.MEASURE` mode{hint}: the mode is required, one of TRAN, DC, "
            "AC, NOISE, FFT, TRAN_CONT, DC_CONT, AC_CONT and NOISE_CONT, before the result name "
            "(Xyce reference manual §2.1.18 p54, and the sections after it to p84)",
        )

    def xy_meas_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        mode, result = element.all(Token)
        body = element.all(_MeasText)
        start, end = _span(body[0].token).start, _span(body[-1].token).end
        text = self._source.text[start:end]
        return _Item(
            element.end,
            lambda span: MeasureDirective(
                **_dot(element, span),
                analysis=str(mode),
                analysis_span=_span(mode),
                result=str(result),
                result_span=_span(result),
                body_text=text,
                body_span=Span(start, end),
            ),
        )

    # .PRINT (X-M2.1 C3; decision 0029 item 5): the print type, then the rest kept as text.
    def print_type(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: token)

    def print_field(self, children: list[Any]) -> _Field:
        return self._field(children, _PrintText)

    def print_bad_type(self, children: list[Any]) -> NoReturn:
        word = _field_token(children)
        hint = " (write `TRAN`)" if fold_name(str(word), self._dialect) == "tr" else ""
        raise self._parse_error(
            word,
            f"`{word}` is not a `.PRINT` type{hint}: the print type is required, before the "
            f"other fields, one of {_PRINT_TYPES} (Xyce reference manual §2.1.31 p128)",
        )

    def print_no_type(self, children: list[Any]) -> NoReturn:
        keyword = children[0]
        raise self._parse_error(
            keyword,
            f"`{keyword}` has no print type: write one of {_PRINT_TYPES}, then the output "
            "variables (Xyce reference manual §2.1.31 p128)",
        )

    def print_no_field(self, children: list[Any]) -> NoReturn:
        element = _Element(children)
        (kind,) = element.all(Token)
        raise self._parse_error(
            kind,
            f"`{element.designator} {kind}` has no field after the print type: write the output "
            "variables after it (Xyce reference manual §2.1.31 p128)",
        )

    def xy_print_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        (kind,) = element.all(Token)
        body = element.all(_PrintText)
        start, end = _span(body[0].token).start, _span(body[-1].token).end
        text = self._source.text[start:end]
        return _Item(
            element.end,
            lambda span: PrintDirective(
                **_dot(element, span),
                print_type=str(kind),
                print_type_span=_span(kind),
                body_text=text,
                body_span=Span(start, end),
            ),
        )

    def data_field(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: token)

    def data_open_end(self, children: list[Any]) -> None:
        return None

    def data_close_name(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: token)

    def data_close(self, children: list[Any]) -> tuple[Token, int]:
        element = _Element(children)
        named = element.all(Token)
        if named:
            raise self._parse_error(
                named[0],
                f"`{element.designator} {named[0]}`: `.ENDDATA` takes no name (Xyce reference "
                "manual §2.1.2 p26)",
            )
        return element.designator, element.end

    def data_block(self, children: list[Any]) -> _Item:
        keyword: Token = children[0]
        fields = [
            child.node
            for child in children[1:]
            if isinstance(child, _Field) and isinstance(child.node, Token)
        ]
        closing, end = children[-1]
        name = fields[0]
        if name.type != "NODE_WORD" or ":" in str(name) or reads_as_number(str(name)):
            raise self._parse_error(
                name,
                f"`{name}` stands where the table's name is: `.DATA` takes a name, then its "
                "column names, then the values (Xyce reference manual §2.1.2 p26)",
            )
        columns: list[Token] = []
        values: list[Token] = []
        for token in fields[1:]:
            if token.type in ("BRACE_FORMULA", "QUOTE_FORMULA"):
                raise self._parse_error(
                    token,
                    "a `.DATA` value is a plain number (Xyce reference manual §2.1.2 p26); "
                    "Xyce stops on an expression",
                )
            if token.type == "NUMBER":
                values.append(token)
            elif values or reads_as_number(str(token)):
                raise self._parse_error(
                    token,
                    f"`{token}` is not a number Xyce reads, and the column names stand before "
                    "the values (Xyce reference manual §2.1.2 p26)",
                )
            elif "" in str(token).split(":"):
                raise self._parse_error(
                    token,
                    f"`{token}` has an empty part around a `:`; a column is a parameter, a "
                    "device, `device:parameter` or `model:parameter`",
                )
            else:
                columns.append(token)
        if not columns:
            raise self._parse_error(
                fields[1] if len(fields) > 1 else name,
                f"the table `{name}` has no column names: write them after the name, then the "
                "values (Xyce reference manual §2.1.2 p26)",
            )
        if not values or len(values) % len(columns):
            at = values[-1] if values else columns[-1]
            raise self._parse_error(
                at,
                f"the table `{name}` has {len(values)} values for {len(columns)} columns: the "
                "count must be a non-zero multiple of the columns, one row per sweep point, and "
                "Xyce stops on any other",
            )
        body = Span(_span(columns[0]).start, _span(values[-1]).end)
        table = Identifier(str(name), _span(name))
        names = tuple(Identifier(str(token), _span(token)) for token in columns)
        rows = len(values) // len(columns)
        text = self._source.text[body.start : body.end]
        return _Item(
            end,
            lambda span: DataTable(
                "data",
                span,
                keyword=str(keyword),
                keyword_span=_span(keyword),
                name=table,
                columns=names,
                rows=rows,
                body_text=text,
                body_span=body,
                end_span=_span(closing),
            ),
        )

    # The closed list's untyped dot-commands (X-M2 B4; decision 0028 item 1), kept whole as
    # UnknownDirective; in a body not_in_subckt refuses them.
    def unknown_field(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: token)

    def xy_unknown_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        name = element.designator
        fields = element.all(Token)
        end = _span(fields[-1]).end if fields else _span(name).end
        raw = self._source.text[_span(name).start : end]
        comments = element.comments
        return _Item(
            element.end,
            lambda span: UnknownDirective(str(name), raw, span, comments, _span(name)),
        )

    def stray_enddata(self, children: list[Any]) -> NoReturn:
        raise self._parse_error(
            children[0],
            f"`{children[0]}` closes no `.DATA` table: it ends the block that a `.DATA` "
            "statement opens (Xyce reference manual §2.1.2 p26)",
        )
