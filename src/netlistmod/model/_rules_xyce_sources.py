"""Rules for xyce's transient source functions (X-M3 B2; decision 0030 items 1 to 5).

The grammar lays a function's fields flat in the source line's rule (xyce.lark, XY-SRC-002 to
XY-SRC-004): its name, the `(` if any, each argument, a `)`, and `TD=`, `R=` or `FILE` after the
list. ``_xyce_function`` gathers them into one :class:`SourceSpec` and checks what the grammar
does not count: each function's arguments, PAT's bit string in the seventh place, PWL's pairs, and
that `TD=` and `R=` stand once. It runs through the ``_source_fields`` hook, on xyce only. The P
line's rule (``port_source``) is here too, so the shared ``SourcesRules`` holds no xyce code; the
mixin is a base of ``XyceRules``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NoReturn

from lark import Token

from netlistmod.dialects import _XYCE
from netlistmod.model._rules_elements import ElementsRules
from netlistmod.model._tree import (
    _comment_spans,
    _Element,
    _Field,
    _field_token,
    _field_tokens,
    _Item,
    _RParen,
    _span,
)
from netlistmod.model.nodes import CurrentSource, PortSource, SourceSpec, VoltageSource
from netlistmod.model.values import Formula, Identifier, NumericValue, ParamAssignment, Value
from netlistmod.source import Span


@dataclass(frozen=True, slots=True)
class _XFnHead:
    """The name of an xyce transient function: PULSE, SIN, EXP, SFFM, PAT or PWL."""

    token: Token


@dataclass(frozen=True, slots=True)
class _XFnOpen:
    """The `(` of an xyce function's argument list."""

    span: Span


@dataclass(frozen=True, slots=True)
class _XFnArg:
    """A positional argument of an xyce function; PAT's bit string is an Identifier."""

    value: Value | Identifier


@dataclass(frozen=True, slots=True)
class _XFnKey:
    """A `name=` argument of an xyce function, which the library refuses (decision 0030 item 3)."""

    param: ParamAssignment


@dataclass(frozen=True, slots=True)
class _XFnParam:
    """PWL's `TD=`, `R=` or `FILE name`, or PAT's `R=`, after the argument list."""

    param: ParamAssignment


# The manual's sections, by the letter of the line: V's functions, I's, and P's, which are V's
# ([xyce-ref] §2.3.11 p231).
_SECTIONS = {
    "v": "Xyce reference manual §2.3.10 p226–230",
    "i": "Xyce reference manual §2.3.9 p221–225",
    "p": "Xyce reference manual §2.3.10 p226–230",
}
# Each function's argument count, least and most, and the arguments' names in the manual's order
# (decision 0030 item 2). PAT's eighth field, R, is written `R=` (item 4); PWL takes pairs.
_COUNTS: dict[str, tuple[int, int, str]] = {
    "pulse": (1, 7, "V1 V2 TD TR TF PW PER"),
    "sin": (3, 6, "V0 VA FREQ TD THETA PHASE"),
    "exp": (2, 6, "V1 V2 TD1 TAU1 TD2 TAU2"),
    "sffm": (2, 5, "V0 VA FC MDI FS"),
    "pat": (7, 7, "VHI VLO TD TR TF TSAMPLE DATA"),
}
_PORT_CITE = "Xyce reference manual §2.3.11 p231"
# PAT's DATA, the seventh argument.
_PAT_DATA = 6
# The `name=` fields each function takes after its list.
_AFTER_LIST: dict[str, tuple[str, ...]] = {"pwl": ("td", "r"), "pat": ("r",)}


def _whole_decimal(text: str) -> bool:
    """`1.0`, `1.` or `-2.00`: a decimal point and only zeros after it, no exponent or letter."""
    whole, point, fraction = text.lstrip("+-").partition(".")
    return bool(point) and whole.isdigit() and set(fraction) <= {"0"}


class XyceSourcesRules(ElementsRules):
    """The field rules of xyce's transient functions, their gathering into a SourceSpec, and the
    P line."""

    if TYPE_CHECKING:
        # SourcesRules builds every source line; the transformer has both mixins.
        def _source_item(
            self, kind: type[VoltageSource | CurrentSource | PortSource], element: _Element
        ) -> _Item: ...

    def _source_fields(self, element: _Element) -> _Element:
        if self._dialect is not _XYCE:
            return element
        return self._xyce_function(element)

    def port_source(self, children: list[Any]) -> _Item:
        element = _Element(children)
        self._xyce_port(element.designator, element.all(ParamAssignment))
        return self._source_item(PortSource, element)

    def xfn_name(self, children: list[Any]) -> _Field:
        return self._field(children, _XFnHead)

    pat_name = xfn_name

    pwl_name = xfn_name

    def xfn_open(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _XFnOpen(_span(token)))

    def xfn_arg(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _XFnArg(self._xfn_value(token)))

    xfn_first = xfn_arg

    pat_arg = xfn_arg

    pat_first = xfn_arg

    def _xfn_value(self, token: Token) -> Value | Identifier:
        if token.type in ("PAT_BITS", "PWL_PATH"):
            return Identifier(str(token), _span(token))
        return self._value(token)

    def _xfn_written(self, value: Value | Identifier) -> str:
        return self._source.text[value.span.start : value.span.end]

    def xfn_comma(self, children: list[Any]) -> NoReturn:
        separator: Token = children[0]
        comma = _span(separator).start + str(separator).index(",")
        raise self._error_at(
            comma,
            "a comma between the arguments of a source function: Xyce stops on every comma "
            "there, so separate the arguments with blanks (`PULSE(0 1 1n)`)",
        )

    def xfn_key(self, children: list[Any]) -> _Field:
        def build(name: Token) -> _XFnKey:
            value = self._xfn_value(_field_tokens(children)[-1])
            span = Span(_span(name).start, value.span.end)
            return _XFnKey(ParamAssignment(str(name), value, span, _span(name)))

        return self._field(children, build)

    xfn_key_first = xfn_key

    def xfn_td(self, children: list[Any]) -> _Field:
        field = self.param(children)
        if isinstance(field.node, _XFnParam):
            return field  # the gap before a field on a `+` line, around the inner field
        assert isinstance(field.node, ParamAssignment)
        return _Field(_XFnParam(field.node), field.comments)

    xfn_r = xfn_td

    def xpwl_path(self, children: list[Any]) -> _Field:
        def build(token: Token) -> Value | Identifier:
            if token.type == "QUOTE_FORMULA":
                raise self._parse_error(
                    token,
                    f'`{token}`: write the path in double quotes, `"{str(token)[1:-1]}"`, or with '
                    "none; Xyce reads single quotes as part of the file's name and stops",
                )
            return self._xfn_value(token)

        return self._field(children, build)

    def xpwl_file(self, children: list[Any]) -> _Field:
        inner = children[-1]
        assert isinstance(inner, _Field)
        comments = (*_comment_spans(children), *inner.comments)
        if isinstance(inner.node, _XFnParam):
            return _Field(inner.node, comments)  # the gap before the keyword on a `+` line
        keyword = _field_token(children)
        path = inner.node
        assert isinstance(path, Formula | Identifier)
        span = Span(_span(keyword).start, path.span.end)
        return _Field(
            _XFnParam(ParamAssignment(str(keyword), path, span, _span(keyword))), comments
        )

    def p_port(self, children: list[Any]) -> _Field:
        return self.param(children)

    p_z0 = p_port

    def _xyce_port(self, designator: Token, params: tuple[ParamAssignment, ...]) -> None:
        """A P line takes `port=` once and `Z0=` at most once, and its port number is an integer
        literal of 1 or more, or an expression in braces or quotes (decision 0030 item 6)."""
        for name in ("port", "z0"):
            written = [param for param in params if param.name.lower() == name]
            if len(written) > 1:
                raise self._error_at(
                    written[1].name_span.start,
                    f"`{written[1].name}=` is written twice on `{designator}`; write it once "
                    "(Xyce stops on a second one)",
                )
        ports = [param for param in params if param.name.lower() == "port"]
        if not ports:
            raise self._parse_error(
                designator,
                f"`{designator}` has no `port=`: a P line needs its port number, `port=1`, after "
                f"the DC value ({_PORT_CITE}); Xyce runs a P line without it as a plain voltage "
                "source, which is not a port",
            )
        port = ports[0]
        value = port.value
        if isinstance(value, Formula):
            return
        assert isinstance(value, NumericValue)  # the grammar's NUMBER
        text = self._xfn_written(value)
        if text.isdigit() and int(text) >= 1:
            return
        whole = text.lstrip("+-").partition(".")[0]
        below_one = text.startswith("-") or (whole.isdigit() and int(whole) == 0)
        if (text.lstrip("+-").isdigit() or _whole_decimal(text)) and below_one:
            outcome = "Xyce runs it outside `.LIN`, but a port is numbered from 1"
        elif text.startswith("+") and text[1:].isdigit():
            outcome = f"Xyce runs it as `{text[1:]}`, but the port number is unsigned"
        elif _whole_decimal(text):
            outcome = f"Xyce runs `{text}` as an integer, but the manual takes an integer literal"
        else:
            outcome = "Xyce stops on it"
        raise self._error_at(
            value.span.start,
            f"`{port.name}={text}`: the port number is an integer of 1 or more, `port=1` "
            f"({_PORT_CITE}), or an expression in braces or quotes; {outcome}",
        )

    def _xyce_function(self, element: _Element) -> _Element:
        """Gather an xyce function's fields, the last of the line, into one SourceSpec."""
        start = next(
            (index for index, node in enumerate(element.fields) if isinstance(node, _XFnHead)),
            None,
        )
        if start is None:
            return element
        head = element.fields[start]
        assert isinstance(head, _XFnHead)
        letter = str(element.designator)[0].lower()
        element.fields[start:] = [self._xfn_spec(head.token, element.fields[start + 1 :], letter)]
        return element

    def _xfn_spec(self, name: Token, parts: list[object], letter: str) -> SourceSpec:
        function = str(name).lower()
        section = _SECTIONS[letter]
        args: list[Value | Identifier] = []
        params: list[ParamAssignment] = []
        end = _span(name).end
        inside = False
        for part in parts:
            if isinstance(part, _XFnOpen):
                inside = True
            elif isinstance(part, _RParen):
                inside = False
                end = part.span.end
            elif isinstance(part, _XFnArg):
                if params:
                    # Without parentheses, `TD=` or `R=` before an argument (the grammar's bare
                    # forms take one, so that the refusal names the keyword).
                    self._xfn_refuse_key(name, params[-1], True, section)
                args.append(part.value)
                end = part.value.span.end
            elif isinstance(part, _XFnKey):
                self._xfn_refuse_key(name, part.param, inside, section)
            else:
                assert isinstance(part, _XFnParam)
                self._xfn_refuse_repeat(name, part.param, params)
                params.append(part.param)
                end = part.param.span.end
        if function == "pwl":
            self._xfn_check_pairs(name, args, params, section)
        else:
            self._xfn_check_count(name, args, section)
        return SourceSpec(
            str(name), _span(name), tuple(args), tuple(params), Span(_span(name).start, end)
        )

    def _xfn_refuse_key(
        self, name: Token, key: ParamAssignment, inside: bool, section: str
    ) -> NoReturn:
        function = str(name).lower()
        folded = key.name.lower()
        at = key.name_span.start
        if function == "pwl" and folded == "file":
            raise self._error_at(
                at,
                f'`{key.name}=`: write `{key.name} "name"`, the keyword and the path with a '
                f'blank between them and no `=` (`PWL FILE "wave.csv"`; {section}); Xyce reads '
                "the `=` as the file's name",
            )
        allowed = _AFTER_LIST.get(function, ())
        if folded in allowed and inside:
            raise self._error_at(
                at,
                f"`{key.name}=` inside the list of `{name}`: it stands after the list, outside "
                f"the parentheses (`{name}(...) {key.name}=...`)",
            )
        if allowed:
            takes = " and ".join(f"`{word.upper()}=`" for word in allowed)
            raise self._error_at(
                at,
                f"`{key.name}=` on `{name}`, which takes its arguments by position and only "
                f"{takes} after its list ({section})",
            )
        raise self._error_at(
            at,
            f"`{key.name}=` on `{name}`: the manual gives its arguments by position only "
            f"({_COUNTS[function][2]}; {section}), so write the values in that order; Xyce reads "
            "a `name=` argument, but undocumented",
        )

    def _xfn_refuse_repeat(
        self, name: Token, param: ParamAssignment, before: list[ParamAssignment]
    ) -> None:
        folded = param.name.lower()
        if any(earlier.name.lower() == folded for earlier in before):
            raise self._error_at(
                param.name_span.start,
                f"`{param.name}=` is written twice on `{name}`: Xyce runs it with the last "
                "value, so write it once",
            )

    def _xfn_check_count(self, name: Token, args: list[Value | Identifier], section: str) -> None:
        function = str(name).lower()
        least, most, names = _COUNTS[function]
        takes = f"{least}" if least == most else f"{least} to {most}"
        if function == "pat":
            self._xfn_check_pattern(name, args, section)
        if len(args) < least:
            raise self._parse_error(
                name,
                f"`{name}` takes {takes} arguments ({names}; {section}) and has {len(args)}: "
                "Xyce stops on fewer",
            )
        if len(args) > most:
            extra = args[most]
            written = self._xfn_written(extra)
            if function == "pat" and len(args) == most + 1:
                raise self._error_at(
                    extra.span.start,
                    f"`{written}` after PAT's DATA: write the repeat count as `R={written}`"
                    f" after the list (`PAT(...) R={written}`); Xyce ignores a positional "
                    "eighth argument, which the manual documents",
                )
            raise self._error_at(
                extra.span.start,
                f"`{name}` takes {takes} arguments ({names}; {section}) and has {len(args)}: "
                "Xyce ignores those after the last, so remove them",
            )

    def _xfn_check_pattern(self, name: Token, args: list[Value | Identifier], section: str) -> None:
        for index, arg in enumerate(args):
            bits = isinstance(arg, Identifier)
            if bits and index != _PAT_DATA:
                raise self._error_at(
                    arg.span.start,
                    f"`{self._xfn_written(arg)}` is a bit string, which only PAT's DATA, its "
                    f"seventh argument, takes ({_COUNTS['pat'][2]}; {section})",
                )
            if index == _PAT_DATA and not bits:
                raise self._error_at(
                    arg.span.start,
                    f"PAT's seventh argument is its DATA, `b` and a string of 0s and 1s "
                    f"(`b0101`; {section}); Xyce stops on anything else",
                )

    def _xfn_check_pairs(
        self,
        name: Token,
        args: list[Value | Identifier],
        params: list[ParamAssignment],
        section: str,
    ) -> None:
        if any(param.name.lower() == "file" for param in params):
            return
        if not args:
            raise self._parse_error(
                name,
                f"`{name}` without its points: write time-value pairs, `{name} 0 0 1n 1`, or "
                f'`{name} FILE "name"` ({section}); Xyce stops on it',
            )
        if len(args) % 2:
            last = args[-1]
            raise self._error_at(
                last.span.start,
                f"`{self._xfn_written(last)}` has no partner: `{name}` takes time-value pairs, "
                f"an even number of values ({section}); Xyce runs an odd count with a waveform "
                "it does not document",
            )
