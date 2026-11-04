"""Write-time verification (architecture §7.6, decision 0007 item 8).

Every plan is applied and verified in five steps, and a failure raises before anything is
returned or written:

1. the splice (§7.5 rules, :func:`~netlistmod.edit.plan.apply_edits`), and a check that no
   edit cuts into an opaque item of the original (``.control`` and ``.if`` blocks,
   ``.include`` and ``.lib`` statements): such an item is added, removed or replaced whole,
   never edited (§7.3; ``TopologyViolation``). The signature does not cover opaque content, so
   without this a plan could edit inside a block unnoticed. It runs before the re-parse, so a
   cut block is reported as such even when the remains do not parse;
2. a re-parse with the same dialect and ``rkm`` (a failure is an ``EditError`` carrying the
   ``ParseError``);
3. the topology signature compared with the one taken when the original file was loaded
   (``TopologyViolation``, naming the first differing entry);
4. a check that every character outside the edited spans is unchanged (always on);
5. the slot check: each :class:`~netlistmod.edit.plan.SlotCheck` of an edit names a part of
   its text that must re-parse as a node of the expected kind with exactly that span.

The re-parse makes the verifier independent of the splice logic (§3).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import fields, is_dataclass
from typing import TypeVar

from netlistmod.dialects import Dialect
from netlistmod.document import Netlist, TopologySignature
from netlistmod.edit.plan import Edit, EditPlan, apply_edits
from netlistmod.errors import EditError, ParseError, TopologyViolation, UnsupportedConstruct
from netlistmod.model.nodes import OpaqueBlock, OpaqueStatement, ParseResult
from netlistmod.model.transform import parse
from netlistmod.source import SourceText, Span

_N = TypeVar("_N", bound=Netlist)


def apply_plan(
    source: SourceText,
    original: ParseResult,
    plan: EditPlan,
    *,
    dialect: Dialect,
    rkm: bool,
    baseline: TopologySignature,
    build: Callable[[SourceText, ParseResult], _N],
) -> _N:
    """Apply ``plan`` to ``source`` (whose parse is ``original``), verify the result and return
    it built by ``build``."""
    text = apply_edits(source.text, plan)
    check_opaque(source.text, original, plan)
    edited = source.with_text(text)
    try:
        result = parse(edited, dialect, rkm=rkm)
    except (ParseError, UnsupportedConstruct) as error:
        reasons = "; ".join(sorted({edit.reason for edit in plan if edit.reason}))
        context = f" ({reasons})" if reasons else ""
        raise EditError(f"the edited netlist does not parse{context}: {error}") from error
    netlist = build(edited, result)
    check_signature(baseline, netlist.signature())
    check_outside(source.text, text, plan)
    check_slots(text, result, plan)
    return netlist


def check_signature(baseline: TopologySignature, signature: TopologySignature) -> None:
    """``TopologyViolation`` unless ``signature`` equals the load ``baseline`` (§7.7)."""
    if signature == baseline:
        return
    for position, (expected, found) in enumerate(zip(baseline.entries, signature.entries)):
        if expected != found:
            raise TopologyViolation(
                f"the edit changes the topology at signature entry {position}: expected "
                f"{expected!r}, found {found!r}; nothing was written"
            )
    count, new_count = len(baseline.entries), len(signature.entries)
    extra = signature.entries[count] if new_count > count else baseline.entries[new_count]
    change = "adds" if new_count > count else "removes"
    raise TopologyViolation(
        f"the edit {change} topology: signature entry {min(count, new_count)} {extra!r}; "
        "nothing was written"
    )


def check_opaque(original_text: str, original: ParseResult, plan: EditPlan) -> None:
    """``TopologyViolation`` if an edit cuts into an opaque item of the original text.

    A ``.control``, ``.if`` or ``.lib`` block or an ``.include``/``.lib`` statement is a black box
    (architecture §6.6, §7.3): an edit may leave it alone, remove or replace it whole, or insert
    next to it, but may not touch part of it (review round 1).
    """
    for node, span in _spanned(original.items):
        if not isinstance(node, OpaqueBlock | OpaqueStatement):
            continue
        for edit in plan:
            whole = edit.span.start <= span.start and span.end <= edit.span.end
            if edit.span.overlaps(span) and not whole:
                text = original_text[span.start : span.end].strip().splitlines()[0]
                raise TopologyViolation(
                    f"{edit.reason or 'an edit'} changes part of the opaque `.{node.kind}` item "
                    f"{text!r}; opaque items are added or removed whole, never edited "
                    "; nothing was written"
                )


def check_outside(original: str, text: str, plan: EditPlan) -> None:
    """``TopologyViolation`` unless every character outside the edited spans is unchanged.

    The positions are recomputed from the plan, independently of the splice.
    """
    shift = 0
    previous = 0
    for edit in plan.ordered():
        _same(original, text, previous, edit.span.start, shift)
        shift += len(edit.text) - edit.span.length
        previous = edit.span.end
    _same(original, text, previous, len(original), shift)
    if len(text) != len(original) + shift:
        raise TopologyViolation("the edited text has an unexpected length; nothing was written")


def _same(original: str, text: str, start: int, end: int, shift: int) -> None:
    if original[start:end] != text[start + shift : end + shift]:
        raise TopologyViolation(
            f"text outside the edited spans changed in [{start}, {end}) of the original; "
            "nothing was written"
        )


def check_slots(text: str, result: ParseResult, plan: EditPlan) -> None:
    """``EditError`` unless each slot of each edit re-parses as a node of its kind."""
    nodes: dict[Span, list[object]] = {}
    for node, span in _spanned(result.items):
        nodes.setdefault(span, []).append(node)
    shift = 0
    for edit in plan.ordered():
        start = edit.span.start + shift
        for slot in edit.slots:
            end = len(edit.text) if slot.end is None else slot.end
            span = Span(start + slot.start, start + end)
            if not any(isinstance(node, slot.kinds) for node in nodes.get(span, ())):
                raise EditError(_slot_message(edit, text[span.start : span.end], slot.description))
        shift += len(edit.text) - edit.span.length


def _slot_message(edit: Edit, written: str, description: str) -> str:
    reason = f"{edit.reason}: " if edit.reason else ""
    return (
        f"{reason}`{written}` does not re-parse as {description}; the text would change more "
        "than the intended slot"
    )


def _spanned(node: object) -> Iterator[tuple[object, Span]]:
    """Every node with a ``span`` field inside ``node``, depth first."""
    if isinstance(node, tuple):
        for element in node:
            yield from _spanned(element)
    elif is_dataclass(node) and not isinstance(node, type | Span):
        span = getattr(node, "span", None)
        if isinstance(span, Span):
            yield node, span
        for field in fields(node):
            yield from _spanned(getattr(node, field.name))
