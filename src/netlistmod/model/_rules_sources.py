"""Rules for independent sources and their functions (decision 0013)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from lark import Token

from netlistmod.dialects import Dialect
from netlistmod.model._rules_elements import ElementsRules
from netlistmod.model._tree import (
    _FN_PARAM_OWNERS,
    _AcMagnitude,
    _comment_spans,
    _common,
    _Dc,
    _DcKeyword,
    _DistortionHead,
    _Element,
    _Field,
    _field_token,
    _field_tokens,
    _FnList,
    _Forever,
    _Item,
    _RParen,
    _span,
    _SpecParam,
)
from netlistmod.model.nodes import (
    CurrentSource,
    SourceSpec,
    VoltageSource,
)
from netlistmod.model.values import (
    AcSpec,
    Flag,
    Formula,
    NumericValue,
    ParamAssignment,
    Value,
)
from netlistmod.source import Span


class SourcesRules(ElementsRules):
    """Rules for independent sources and their functions (decision 0013)."""

    def dc_keyword(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _DcKeyword())

    def dc_spec(self, children: list[Any]) -> _Field:
        keyword = children[0] if len(children) == 2 else None
        value: _Field = children[-1]
        assert isinstance(value.node, NumericValue | Formula)
        comments = (*(keyword.comments if keyword else ()), *value.comments)
        return _Field(_Dc(value.node, keyword is not None), comments)

    def ac_spec(self, children: list[Any]) -> _Field:
        # [gap] AC_KW value, or a gap token and a nested ac_spec; both end in a _Field. LTspice
        # also has [gap] AC_KW EQ value, which ends in the value's token.
        if isinstance(children[-1], Token):
            magnitude = self._value(children[-1])
            start = _span(_field_token(children)).start
            return _Field(_AcMagnitude(magnitude, start), _comment_spans(children))
        inner: _Field = children[-1]
        comments = (*_comment_spans(children), *inner.comments)
        if isinstance(inner.node, _AcMagnitude):
            return _Field(inner.node, comments)
        assert isinstance(inner.node, NumericValue | Formula)
        keyword = _field_token(children)
        return _Field(_AcMagnitude(inner.node, _span(keyword).start), comments)

    dc_after = dc_spec

    def stimulus(self, children: list[Any]) -> _Field:
        inner = children[-1]
        if isinstance(inner, _Field) and isinstance(inner.node, SourceSpec):
            return _Field(inner.node, (*_comment_spans(children), *inner.comments))
        name = _field_token(children)
        args: tuple[Value, ...] = ()
        params: list[ParamAssignment] = []
        comments = list(_comment_spans(children))
        end = _span(name).end
        forever = False
        for child in children:
            if isinstance(child, _FnList):
                args, end = child.args, child.end
                comments.extend(child.comments)
            elif isinstance(child, _Field):
                comments.extend(child.comments)
                if isinstance(child.node, ParamAssignment):
                    params.append(child.node)
                    end = child.node.span.end
                elif isinstance(child.node, _Forever):
                    forever = True
                    end = child.node.span.end
                elif isinstance(child.node, _RParen):
                    end = child.node.span.end
        return _Field(
            SourceSpec(
                str(name), _span(name), args, tuple(params), Span(_span(name).start, end), forever
            ),
            tuple(comments),
        )

    pwl_stimulus = stimulus

    table_stimulus = stimulus

    step_stimulus = stimulus

    def wave_stimulus(self, children: list[Any]) -> _Field:
        inner = children[-1]
        if isinstance(inner, _Field):
            return _Field(inner.node, (*_comment_spans(children), *inner.comments))
        name, path = _field_tokens(children)
        value = self._param_value(path)
        span = Span(_span(name).start, value.span.end)
        assignment = ParamAssignment(str(name), value, span, _span(name))
        return _Field(
            SourceSpec(str(name), _span(name), (), (assignment,), span), _comment_spans(children)
        )

    def fn_list(self, children: list[Any]) -> _FnList:
        inner = children[-1]
        if isinstance(inner, _FnList):
            return _FnList(
                inner.args, inner.end, (*_comment_spans(children), *inner.comments), inner.start
            )
        fields = [child for child in children if isinstance(child, _Field)]
        close = fields[-1].node
        assert isinstance(close, _RParen)
        comments = tuple(comment for field in fields for comment in field.comments)
        args = tuple(field.node for field in fields[:-1])
        opener = next(
            child for child in children if isinstance(child, Token) and child.type == "LPAR"
        )
        return _FnList(args, close.span.end, comments, _span(opener).start)  # type: ignore[arg-type]

    def fn_first(self, children: list[Any]) -> _Field:
        return self._field(children, self._value)

    fn_arg = fn_first

    def pwl_factor(self, children: list[Any]) -> _Field:
        return self.param(children)

    pwl_file = pwl_factor

    def pwl_repeat(self, children: list[Any]) -> _Field:
        inner = children[-1]
        if isinstance(inner, _Field):
            return _Field(inner.node, (*_comment_spans(children), *inner.comments))
        tokens = _field_tokens(children)
        if tokens[-1].type == "FOREVER_KW":
            return _Field(_Forever(_span(tokens[-1])), _comment_spans(children))
        keyword, value_token = tokens[-2:]
        value = self._value(value_token)
        span = Span(_span(keyword).start, value.span.end)
        return _Field(
            ParamAssignment(str(keyword), value, span, _span(keyword)), _comment_spans(children)
        )

    def pwl_endrepeat(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _RParen(_span(token)))

    def fn_param(self, children: list[Any]) -> _Field:
        inner = children[-1]
        if isinstance(inner, _Field):
            return _Field(inner.node, (*_comment_spans(children), *inner.comments))
        field = self.param(children)
        assert isinstance(field.node, ParamAssignment)
        return _Field(_SpecParam(field.node), field.comments)

    def external_kw(self, children: list[Any]) -> _Field:
        return self._field(
            children,
            lambda token: SourceSpec(str(token), _span(token), (), (), _span(token)),
        )

    def distof1_kw(self, children: list[Any]) -> _Field:
        return self._field(children, lambda token: _DistortionHead(token))

    distof2_kw = distof1_kw

    def voltage_source(self, children: list[Any]) -> _Item:
        return self._source_item(VoltageSource, _Element(children))

    def current_source(self, children: list[Any]) -> _Item:
        return self._source_item(CurrentSource, _Element(children))

    def _source_item(self, kind: type[VoltageSource | CurrentSource], element: _Element) -> _Item:
        dc = element.optional(_Dc)
        ac, stimulus, distortion = self._source_parts(element, kind)
        return _Item(
            element.end,
            lambda span: kind(
                **_common(element, span),
                dc=dc.value if dc is not None else None,
                dc_keyword=dc.keyword if dc is not None else False,
                ac=ac,
                flags=element.all(Flag),
                stimulus=stimulus,
                distortion=distortion,
            ),
        )

    def _source_parts(
        self, element: _Element, kind: type[VoltageSource | CurrentSource]
    ) -> tuple[AcSpec | None, SourceSpec | None, tuple[SourceSpec, ...]]:
        """A source line's AC part, function and distortion inputs. A plain value belongs to the
        AC magnitude or distortion keyword before it. A function's named parameter must follow it
        directly and be one that function takes, and RF port parameters are for V only: fn_param
        and port_param are one rule wherever a line allows them, so these are checked here."""
        magnitude: _AcMagnitude | None = None
        phase: Value | None = None
        stimulus: SourceSpec | None = None
        distortion: list[SourceSpec] = []
        in_ac = False
        previous: object = None
        for node in element.fields:
            if isinstance(node, _AcMagnitude):
                magnitude, in_ac = node, True
            elif isinstance(node, _DistortionHead):
                token = node.token
                distortion.append(SourceSpec(str(token), _span(token), (), (), _span(token)))
                in_ac = False
            elif isinstance(node, NumericValue | Formula):
                if in_ac:
                    phase = node
                else:
                    last = distortion[-1]
                    span = Span(last.span.start, node.span.end)
                    distortion[-1] = replace(last, args=(*last.args, node), span=span)
            elif isinstance(node, SourceSpec):
                stimulus, in_ac = node, False
            elif isinstance(node, _SpecParam):
                stimulus = self._with_param(stimulus, node.param, previous)
                in_ac = False
            elif isinstance(node, ParamAssignment):
                in_ac = False
                if self._dialect is Dialect.NGSPICE and kind is CurrentSource:
                    raise self._error_at(
                        node.name_span.start, f"`{node.name}` is for a V line (RF port parameters)"
                    )
            else:
                in_ac = False
            previous = node
        ac = None
        if magnitude is not None:
            end = (phase or magnitude.value).span.end
            ac = AcSpec(magnitude.value, phase, Span(magnitude.start, end))
        return ac, stimulus, tuple(distortion)

    def _with_param(
        self, stimulus: SourceSpec | None, param: ParamAssignment, previous: object
    ) -> SourceSpec:
        name = param.name.lower()
        function = stimulus.name.lower() if stimulus is not None else ""
        owner = _FN_PARAM_OWNERS[name]
        if stimulus is None or function != owner:
            raise self._error_at(
                param.name_span.start, f"`{param.name}=` applies only to `{owner.upper()}`"
            )
        if not isinstance(previous, SourceSpec | _SpecParam):
            raise self._error_at(
                param.name_span.start,
                f"`{param.name}=` must follow `{stimulus.name}` directly",
            )
        span = Span(stimulus.span.start, param.span.end)
        return replace(stimulus, params=(*stimulus.params, param), span=span)
