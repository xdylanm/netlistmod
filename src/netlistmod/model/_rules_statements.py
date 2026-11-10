"""Rules for typed statements and dot-commands (decision 0005)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, NoReturn

from lark import Token, v_args
from lark.tree import Meta

from netlistmod.dialects import Dialect
from netlistmod.model._rules_elements import ElementsRules
from netlistmod.model._tree import (
    _BARE_EXPRESSION,
    _RESERVED_PARAMS,
    _STEP_VARIATIONS,
    _Bare,
    _comment_spans,
    _dot,
    _Element,
    _Ends,
    _Field,
    _field_tokens,
    _FileArgument,
    _Header,
    _Item,
    _ListKeyword,
    _MeasBody,
    _ModelParams,
    _Rest,
    _RParen,
    _span,
    _statement_end,
    _StepItem,
    _StepModelRef,
    _StepSweep,
    _Tail,
)
from netlistmod.model.nodes import (
    AcDirective,
    BodyItem,
    DcDirective,
    DcSweep,
    End,
    EndsLine,
    GlobalDirective,
    IcDirective,
    MeasureDirective,
    ModelStatement,
    Node,
    NodeCondition,
    NodesetDirective,
    OpDirective,
    OptionItem,
    OptionsDirective,
    OutputVector,
    ParamStatement,
    SaveDirective,
    StepDirective,
    SubcktDefinition,
    TempDirective,
    Title,
    TitleDirective,
    TranDirective,
)
from netlistmod.model.values import (
    ElementReference,
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

_CPL_MATRICES = frozenset({"r", "l", "g", "c"})
_LTRA_FLAGS = frozenset(
    {"nosteplimit", "steplimit", "nocontrol", "lininterp", "mixedinterp", "truncnr", "truncdontcut"}
)
_LTRA_FLAG_TERMINALS = frozenset(f"{flag.upper()}_KW" for flag in _LTRA_FLAGS)


@dataclass(frozen=True, slots=True)
class _ModelValue:
    """A value after a ``.model`` parameter's value: the next value of a CPL matrix."""

    value: Value


class StatementsRules(ElementsRules):
    """Rules for typed statements and dot-commands (decision 0005)."""

    def param_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        assignments = element.all(ParamAssignment)
        bare = element.optional(_Bare)
        if bare is not None:
            raise self._error_at(assignments[-1].value.span.start, _BARE_EXPRESSION)
        return _Item(
            element.end,
            lambda span: ParamStatement(**_dot(element, span), assignments=assignments),
        )

    def param_def(self, children: list[Any]) -> _Field:
        def build(name: Token) -> ParamAssignment:
            if name.type in _RESERVED_PARAMS:
                raise self._parse_error(
                    name,
                    f"`{name}` is a reserved name (time, temper, hertz) and cannot be a parameter",
                )
            value = children[-1]
            if isinstance(value, _Bare):
                raise self._error_at(value.span.start, _BARE_EXPRESSION)
            built = self._value(value)
            name_span = _span(name)
            return ParamAssignment(
                str(name), built, Span(name_span.start, built.span.end), name_span
            )

        return self._field(children, build)

    def bare_value(self, children: list[Token]) -> _Bare:
        return _Bare(Span(_span(children[0]).start, _span(children[-1]).end))

    def bare_tail(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _Bare(_span(token)))

    def model_ako(self, children: list[Any]) -> _Field:
        def build(token: Token) -> ModelReference:
            # AKO_REF is "ako:" and the base model name, one token.
            prefix = len("ako:")
            start = _span(token).start + prefix
            return ModelReference(str(token)[prefix:], Span(start, _span(token).end))

        return self._field(children, build)

    def model_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        name, model_type = element.all(Token)[:2]
        ako = element.optional(ModelReference)
        paren = element.optional(_ModelParams)
        fields = paren.fields if paren is not None else tuple(element.fields)
        params, flags = self._model_fields(str(model_type), fields)
        return _Item(
            element.end,
            lambda span: ModelStatement(
                **_dot(element, span),
                name=str(name),
                name_span=_span(name),
                model_type=str(model_type),
                model_type_span=_span(model_type),
                params=params,
                parenthesized=paren is not None,
                open_paren_span=paren.open_span if paren is not None else None,
                close_paren_span=paren.close_span if paren is not None else None,
                ako=ako,
                flags=flags,
            ),
        )

    def _model_fields(
        self, model_type: str, fields: tuple[object, ...]
    ) -> tuple[tuple[ParamAssignment, ...], tuple[Flag, ...]]:
        """The parameters and flags of a ``.model`` line, in order. The values after a CPL
        matrix's first one join it in a :class:`ValueList`, and LTRA's flags stay on an LTRA
        model (decision 0019)."""
        kind = model_type.lower()
        params: list[ParamAssignment] = []
        flags: list[Flag] = []
        extra: list[Value] = []
        previous: object = None
        for node in (*fields, None):
            if isinstance(node, _ModelValue):
                last = previous if isinstance(previous, ParamAssignment) else None
                if last is None:
                    raise self._error_at(
                        node.value.span.start,
                        "a value without a name: a `.model` value follows `name=`",
                    )
                if kind != "cpl" or last.name.lower() not in _CPL_MATRICES:
                    raise self._error_at(
                        node.value.span.start,
                        f"a second value for `{last.name}=`: only the R, L, G and C matrices of a "
                        "CPL model take a list of values (ngspice reads the first and ignores "
                        "the rest)",
                    )
                extra.append(node.value)
                continue
            previous = node
            if extra:
                last = params[-1]
                assert not isinstance(last.value, ValueList | Identifier)
                values = (last.value, *extra)
                span = Span(values[0].span.start, values[-1].span.end)
                params[-1] = ParamAssignment(
                    last.name,
                    ValueList(self._source.text[span.start : span.end], values, span),
                    Span(last.span.start, span.end),
                    last.name_span,
                )
                extra = []
            if isinstance(node, ParamAssignment):
                params.append(node)
            elif isinstance(node, Flag):
                if node.name.lower() in _LTRA_FLAGS and kind != "ltra":
                    raise self._error_at(
                        node.span.start,
                        f"`{node.name}` is a flag of an LTRA model (ngspice manual §6.2.1); "
                        f"ngspice ignores it on a `{model_type}` model",
                    )
                flags.append(node)
        return tuple(params), tuple(flags)

    def model_paren(self, children: list[Any]) -> _Field:
        fields = [child for child in children if isinstance(child, _Field)]
        comments = (*_comment_spans(children), *(c for f in fields for c in f.comments))
        inner = fields[-1].node
        if isinstance(inner, _ModelParams):
            # A gap before the parenthesis: the list is the nested field.
            return _Field(inner, comments)
        nodes = tuple(f.node for f in fields if not isinstance(f.node, _RParen))
        assert isinstance(inner, _RParen)  # the grammar ends the list with rparen
        open_paren = next(c for c in children if isinstance(c, Token) and c.type == "LPAR")
        return _Field(_ModelParams(nodes, _span(open_paren), inner.span), comments)

    def model_flag(self, children: list[Any]) -> _Field:
        def build(token: Token) -> Flag:
            if token.type in _LTRA_FLAG_TERMINALS and self._dialect is Dialect.LTSPICE:
                raise self._parse_error(
                    token,
                    f"`{token}` is an ngspice LTRA flag: the LTspice reference lists only R, L, "
                    "G, C and Len for LTRA",
                )
            return Flag(str(token), _span(token))

        return self._field(children, build)

    model_flag_first = model_flag

    def model_more(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _ModelValue(self._value(token)))

    def model_text(self, children: list[Any]) -> _Field:
        return self.param(children)

    def rparen(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _RParen(_span(token)))

    def subckt_def(self, children: list[Any]) -> _Item:
        header: _Header = children[0]
        items: list[_Item] = children[1:-1]
        ends: _Ends = children[-1]
        element = header.element
        name = element.all(Token)[0]

        def build(span: Span) -> SubcktDefinition:
            body: list[BodyItem] = []
            cursor = element.end
            for item in items:
                built = item.build(Span(cursor, item.end))
                assert not isinstance(built, Title | TitleDirective | End)
                body.append(built)  # type: ignore[arg-type]
                cursor = item.end
            ends_name = ends.name
            return SubcktDefinition(
                **_dot(element, span),
                name=str(name),
                name_span=_span(name),
                ports=element.all(Node),
                params=element.all(ParamAssignment),
                body=tuple(body),
                ends=EndsLine(
                    str(ends_name) if ends_name is not None else None,
                    _span(ends_name) if ends_name is not None else None,
                    Span(cursor, ends.end),
                    ends.comments,
                ),
                header_span=Span(span.start, element.end),
            )

        return _Item(ends.end, build)

    def subckt_header(self, children: list[Any]) -> _Header:
        return _Header(_Element(children))

    def subckt_port(self, children: list[Any]) -> _Field:
        def build(token: Token) -> Node:
            if token.type == "ZERO_PORT":
                raise self._parse_error(
                    token, "a subcircuit port cannot be `0` (ground); ports are external nodes"
                )
            return Node(str(token), _span(token))

        return self._field(children, build)

    @v_args(meta=True)
    def not_in_subckt(self, meta: Meta, children: list[Any]) -> NoReturn:
        keyword = str(children[0]) if isinstance(children[0], Token) else ".control"
        raise self._error_at(
            meta.start_pos,
            f"`{keyword}` is not allowed inside a subcircuit definition (`.subckt` ... `.ends`)",
        )

    def ends_line(self, children: list[Any]) -> _Ends:
        element = _Element(children)
        return _Ends(element.optional(Token), element.comments, element.end)

    def tran_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        values = element.values()
        # LTspice's `.tran 1m` holds only tstop; the grammar requires both otherwise.
        tstep, tstop = (None, values[0]) if len(values) == 1 else (values[0], values[1])
        return _Item(
            element.end,
            lambda span: TranDirective(
                **_dot(element, span),
                tstep=tstep,
                tstop=tstop,
                tstart=values[2] if len(values) > 2 else None,
                tmax=values[3] if len(values) > 3 else None,
                uic=element.optional(Flag),
                modifiers=element.all(OptionItem),
            ),
        )

    def tran_modifier(self, children: list[Any]) -> _Field:
        def build(name: Token) -> OptionItem:
            tokens = _field_tokens(children)
            value = self._value(tokens[-1]) if len(tokens) > 1 else None
            name_span = _span(name)
            end = value.span.end if value is not None else name_span.end
            return OptionItem(str(name), name_span, value, Span(name_span.start, end))

        return self._field(children, build)

    def ac_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        file = element.optional(_FileArgument)
        listed = element.optional(_ListKeyword)
        values = element.values()
        if file is not None:
            variation_span = _span(file.keyword)
        elif listed is not None:
            variation_span = listed.span
        else:
            variation_span = _span(element.all(Token)[0])
        variation = self._source.text[variation_span.start : variation_span.end]
        ranged = file is None and listed is None
        return _Item(
            element.end,
            lambda span: AcDirective(
                **_dot(element, span),
                variation=variation,
                variation_span=variation_span,
                points=values[0] if ranged else None,
                fstart=values[1] if ranged else None,
                fstop=values[2] if ranged else None,
                frequencies=values if listed is not None else (),
                file=file.name if file is not None else None,
            ),
        )

    def ac_variation(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: token)

    def list_keyword(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _ListKeyword(_span(token)))

    def file_argument(self, children: list[Any]) -> _Field:
        def build(keyword: Token) -> _FileArgument:
            name: Token = children[-1]
            return _FileArgument(keyword, Identifier(str(name), _span(name)))

        return self._field(children, build)

    meas_analysis = ac_variation

    def dc_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        sweeps = element.all(DcSweep)
        return _Item(element.end, lambda span: DcDirective(**_dot(element, span), sweeps=sweeps))

    def dc_sweep(self, children: list[_Field]) -> _Field:
        tokens = [child.node for child in children if isinstance(child.node, Token)]
        variation = tokens[0] if len(tokens) == 2 else None
        source = tokens[-1]
        assert isinstance(source, Token)
        values = tuple(
            child.node for child in children if isinstance(child.node, NumericValue | Formula)
        )
        listed = any(isinstance(child.node, _ListKeyword) for child in children)
        file = next((c.node.name for c in children if isinstance(c.node, _FileArgument)), None)
        ranged = not listed and file is None
        last = file if file is not None else values[-1]
        sweep = DcSweep(
            str(source),
            _span(source),
            values[0] if ranged else None,
            values[1] if ranged else None,
            values[2] if ranged else None,
            Span(_span(source).start, last.span.end),
            str(variation) if variation is not None else None,
            values if listed else (),
            file,
        )
        return _Field(sweep, tuple(c for child in children for c in child.comments))

    def dc_list_sweep(self, children: list[Any]) -> _Tail:
        # The statement's end is part of this rule: a value list is not delimited (LALR).
        return _Tail(self.dc_sweep(children[:-1]), *_statement_end(children[-1]))

    def op_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        return _Item(element.end, lambda span: OpDirective(**_dot(element, span)))

    def options_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        options = element.all(OptionItem)
        return _Item(
            element.end, lambda span: OptionsDirective(**_dot(element, span), options=options)
        )

    def option_item(self, children: list[Any]) -> _Field:
        def build(name: Token) -> OptionItem:
            tokens = _field_tokens(children)
            value: Value | Identifier | None = None
            if len(tokens) > 1:
                token = tokens[-1]
                value = (
                    Identifier(str(token), _span(token))
                    if token.type == "WORD"
                    else self._value(token)
                )
            name_span = _span(name)
            end = value.span.end if value is not None else name_span.end
            return OptionItem(str(name), name_span, value, Span(name_span.start, end))

        return self._field(children, build)

    def temp_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        values = element.values()
        return _Item(
            element.end,
            lambda span: TempDirective(**_dot(element, span), value=values[0], others=values[1:]),
        )

    def ic_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        conditions = element.all(NodeCondition)
        return _Item(
            element.end, lambda span: IcDirective(**_dot(element, span), conditions=conditions)
        )

    def nodeset_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        conditions = element.all(NodeCondition)
        return _Item(
            element.end,
            lambda span: NodesetDirective(**_dot(element, span), conditions=conditions),
        )

    def node_condition(self, children: list[Any]) -> _Field:
        def build(opener: Token) -> NodeCondition:
            # v( node ) = value: the node is the second field token, the value the last.
            tokens = _field_tokens(children)
            value = self._value(tokens[-1])
            node = Node(str(tokens[1]), _span(tokens[1])) if opener.type == "V_OPEN" else None
            return NodeCondition(node, value, Span(_span(opener).start, value.span.end))

        return self._field(children, build)

    nodeset_all = node_condition

    def current_condition(self, children: list[Any]) -> _Field:
        def build(opener: Token) -> NodeCondition:
            # i( L_REF ) = value: the inductor is the second field token, the value the last.
            tokens = _field_tokens(children)
            value = self._value(tokens[-1])
            current = ElementReference(str(tokens[1]), _span(tokens[1]))
            span = Span(_span(opener).start, value.span.end)
            return NodeCondition(None, value, span, current)

        return self._field(children, build)

    def save_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        vectors = element.all(OutputVector)
        return _Item(
            element.end, lambda span: SaveDirective(**_dot(element, span), vectors=vectors)
        )

    def output_vector(self, children: list[Any]) -> _Field:
        inner = children[-1]
        if isinstance(inner, OutputVector):
            # [gap] voltage_vector or current_vector: one separator, no comments.
            return _Field(inner, ())
        return self._field(children, lambda token: OutputVector(str(token), _span(token)))

    def voltage_vector(self, children: list[Token]) -> OutputVector:
        opener, *names = _field_tokens(children)[:-1]
        span = Span(_span(opener).start, _span(children[-1]).end)
        return OutputVector(
            self._source.text[span.start : span.end],
            span,
            function=str(opener)[:-1],
            nodes=tuple(Node(str(name), _span(name)) for name in names),
        )

    def current_vector(self, children: list[Token]) -> OutputVector:
        opener, *names = _field_tokens(children)[:-1]
        function = str(opener)[:-1]
        if names[0].type == "SAVE_PATTERN":
            # A wildcard or hierarchical name (LTspice) refers to no single element.
            span = Span(_span(opener).start, _span(children[-1]).end)
            return OutputVector(self._source.text[span.start : span.end], span, function=function)
        if opener.type == "CURRENT_VARIANT_OPEN":
            raise self._parse_error(
                opener,
                f"`{function}(...)` is not implemented in ngspice (ngspice manual §11.6.2); "
                "save `i(...)` instead",
            )
        if len(names) > 1:
            raise self._parse_error(names[1], "`i(...)` takes one source name")
        span = Span(_span(opener).start, _span(children[-1]).end)
        return OutputVector(
            self._source.text[span.start : span.end],
            span,
            function=function,
            source=ElementReference(str(names[0]), _span(names[0])),
        )

    def meas_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        tokens = element.all(Token)
        analysis, result = (None, tokens[0]) if len(tokens) == 1 else tokens[:2]
        body = element.all(_MeasBody)[0]
        return _Item(
            element.end,
            lambda span: MeasureDirective(
                **_dot(element, span),
                analysis=str(analysis) if analysis is not None else None,
                analysis_span=_span(analysis) if analysis is not None else None,
                result=str(result),
                result_span=_span(result),
                body_text=body.text,
                body_span=body.span,
            ),
        )

    def meas_body(self, children: list[Any]) -> _Field:
        inner = children[-1]
        comments = _comment_spans(children)
        if isinstance(inner, _Field):
            return _Field(inner.node, (*comments, *inner.comments))
        # [gap] first text token, then the statement text.
        first: Token = children[-2]
        rest: _Rest = inner
        span = Span(_span(first).start, rest.text_end or _span(first).end)
        body = _MeasBody(self._source.text[span.start : span.end], span)
        return _Field(body, (*comments, *rest.comments))

    def global_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        nodes = element.all(Node)
        return _Item(element.end, lambda span: GlobalDirective(**_dot(element, span), nodes=nodes))

    def step_stmt(self, children: list[Any]) -> _Item:
        element = _Element(children)
        tokens = element.all(Token)
        variation = next((t for t in tokens if t.type in _STEP_VARIATIONS), None)
        item = element.optional(_StepItem)
        source = next((t for t in tokens if t.type not in _STEP_VARIATIONS), None)
        model_ref = element.optional(_StepModelRef)
        sweep = element.all(_StepSweep)[0]
        if sweep.listed and variation is not None:
            raise self._parse_error(
                variation, f"`{variation}` cannot be combined with `list` in `.step` (reference)"
            )
        name = item.token if item is not None else source
        assert name is not None
        kind: Literal["param", "source", "temp", "model"]
        if item is not None:
            kind = item.kind
        else:
            kind = "model" if model_ref is not None else "source"
        ranged = not sweep.listed and sweep.file is None
        return _Item(
            element.end,
            lambda span: StepDirective(
                **_dot(element, span),
                kind=kind,
                name=str(model_ref.name) if model_ref is not None else str(name),
                name_span=model_ref.span if model_ref is not None else _span(name),
                model_type=(Identifier(str(name), _span(name)) if model_ref is not None else None),
                model=model_ref.model if model_ref is not None else None,
                variation=str(variation) if variation is not None else None,
                variation_span=_span(variation) if variation is not None else None,
                start=sweep.values[0] if ranged else None,
                stop=sweep.values[1] if ranged else None,
                increment=sweep.values[2] if ranged else None,
                values=sweep.values if sweep.listed else (),
                file=sweep.file,
            ),
        )

    def step_param(self, children: list[Any]) -> _Field:
        comments = _comment_spans(children)
        inner: _Field = children[-1]
        if isinstance(inner.node, _StepItem):
            return _Field(inner.node, (*comments, *inner.comments))
        assert isinstance(inner.node, Token)
        return _Field(_StepItem("param", inner.node), (*comments, *inner.comments))

    def step_temp(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _StepItem("temp", token))

    def step_model_ref(self, children: list[Any]) -> _Field:
        def build(token: Token) -> _StepModelRef:
            # STEP_MODEL_REF is name(parameter), one token, so the model name is its head.
            span = _span(token)
            head = str(token).partition("(")[0]
            model = ModelReference(head, Span(span.start, span.start + len(head)))
            return _StepModelRef(str(token), span, model)

        return self._field(children, build)

    def step_sweep(self, children: list[Any]) -> _Tail:
        # The statement's end is part of this rule: a value list is not delimited (LALR).
        fields: list[_Field] = children[:-1]
        values = tuple(c.node for c in fields if isinstance(c.node, NumericValue | Formula))
        listed = any(isinstance(c.node, _ListKeyword) for c in fields)
        file = next((c.node.name for c in fields if isinstance(c.node, _FileArgument)), None)
        comments = tuple(comment for child in fields for comment in child.comments)
        sweep = _Field(_StepSweep(values, listed, file), comments)
        return _Tail(sweep, *_statement_end(children[-1]))
