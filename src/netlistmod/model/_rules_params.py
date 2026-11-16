"""Rules for xyce's parameters and functions: `.PARAM` with functions and commas, `.GLOBAL_PARAM`
and `.FUNC` (X-M1 B3; decision 0027 items 9 and 10)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NoReturn

from lark import Token

from netlistmod.model._rules_statements import StatementsRules
from netlistmod.model._tree import (
    _dot,
    _Element,
    _Field,
    _field_token,
    _Item,
    _span,
)
from netlistmod.model.nodes import FuncStatement, GlobalParamStatement
from netlistmod.model.values import Formula, FunctionDefinition, Identifier, ParamAssignment
from netlistmod.source import Span

_RESERVED = "time, freq, hertz, vt, temp, temper, gmin, pi and exp"
_BLANK_IN_VALUE = (
    "a blank inside a bare `.PARAM` value: the library reads a bare value only without blanks; "
    "write the expression in braces, `{1 + 2}`. Xyce deletes the blanks, which may join two "
    "values into one"
)


@dataclass(frozen=True, slots=True)
class _FuncArgs:
    """The arguments of a function and where its `)` ends."""

    args: tuple[Identifier, ...]
    end: int


class ParamRules(StatementsRules):
    """Rules for xyce's `.PARAM` functions, `.GLOBAL_PARAM` and `.FUNC`."""

    def param_next(self, children: list[Any]) -> _Field:
        # `, name=value`: the comma is a separator like a blank.
        return self.param_def(children)

    def reserved_def(self, children: list[Any]) -> NoReturn:
        name = _field_token(children)
        raise self._parse_error(
            name,
            f"`{name}` is a reserved word ({_RESERVED}) and cannot be defined as a parameter "
            "(Xyce reference manual §2.1.26 p121)",
        )

    def blank_tail(self, children: list[Any]) -> NoReturn:
        raise self._parse_error(children[0], _BLANK_IN_VALUE)

    def func_args(self, children: list[Token]) -> _FuncArgs:
        args: list[Identifier] = []
        for token in children:
            if token.type == "RESERVED_NAME":
                raise self._parse_error(
                    token,
                    f"`{token}` is a reserved word ({_RESERVED}) and cannot be a function argument "
                    "(Xyce reference manual §2.1.10 p42); Xyce ignores it as one",
                )
            if token.type == "PARAM_NAME":
                args.append(Identifier(str(token), _span(token)))
        return _FuncArgs(tuple(args), _span(children[-1]).end)

    def _function(self, opener: Token, args: _FuncArgs, body: Formula) -> FunctionDefinition:
        """A function from its `name(` token, its arguments and its body."""
        if opener.type == "BUILTIN_OPEN":
            name = str(opener)[:-1]
            raise self._parse_error(
                opener,
                f"`{name}` is a built-in function or a reserved word, and Xyce does not let a "
                "function of that name be defined (Xyce reference manual §2.1.10 p42); it "
                "ignores the definition",
            )
        span = _span(opener)
        # The token is the name and its `(`, a fixed delimiter.
        name_span = Span(span.start, span.end - 1)
        return FunctionDefinition(
            str(opener)[:-1], name_span, args.args, body, Span(span.start, body.span.end)
        )

    def func_def(self, children: list[Any]) -> _Field:
        def build(opener: Token) -> FunctionDefinition:
            args = next(child for child in children if isinstance(child, _FuncArgs))
            body = self._value(children[-1])
            assert isinstance(body, Formula)
            return self._function(opener, args, body)

        return self._field(children, build)

    func_next = func_def

    def func_name(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: token)

    def func_body(self, children: list[Any]) -> _Field:
        return self._field(children, self._value)

    def func_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        (opener,) = element.all(Token)
        args = next(child for child in children if isinstance(child, _FuncArgs))
        (body,) = element.all(Formula)
        function = self._function(opener, args, body)
        return _Item(
            element.end, lambda span: FuncStatement(**_dot(element, span), function=function)
        )

    def global_param_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        functions = element.all(FunctionDefinition)
        if functions:
            raise self._error_at(
                functions[0].name_span.start,
                "`.GLOBAL_PARAM` defines no function (Xyce reference manual §2.1.12 p45); write "
                "it on a `.PARAM` or `.FUNC` line",
            )
        assignments = element.all(ParamAssignment)
        return _Item(
            element.end,
            lambda span: GlobalParamStatement(**_dot(element, span), assignments=assignments),
        )
