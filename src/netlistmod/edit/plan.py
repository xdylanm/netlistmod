"""Edit plans: span replacements over the original text (architecture §7.5, decision 0007).

An :class:`Edit` replaces one span of the original text; a zero-width span is an insertion.
An :class:`EditPlan` is an ordered collection of edits, and :func:`apply_edits` splices it into
the text. Offsets always refer to the original text, which is never mutated.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from netlistmod.errors import EditError
from netlistmod.source import Span


@dataclass(frozen=True, slots=True)
class SlotCheck:
    """A part of an edit's text that must re-parse as a node of one of ``kinds``.

    ``start`` and ``end`` are offsets into :attr:`Edit.text` (``end=None`` for its end); the
    write-time check (decision 0007 item 8, step 5) looks for a node of one of ``kinds`` whose
    span is exactly that part of the new text. ``description`` names the slot in messages.
    """

    kinds: tuple[type, ...]
    description: str
    start: int = 0
    end: int | None = None


@dataclass(frozen=True, slots=True)
class Edit:
    """Replace ``span`` of the original text with ``text``; ``reason`` explains it in messages.

    ``slots`` lists the parts of ``text`` the write-time slot check verifies; a plan built by
    hand may leave it empty.
    """

    span: Span
    text: str
    reason: str = ""
    slots: tuple[SlotCheck, ...] = ()


@dataclass(frozen=True, slots=True, init=False)
class EditPlan:
    """An immutable collection of edits in submission order."""

    edits: tuple[Edit, ...]

    def __init__(self, edits: Iterable[Edit] = ()) -> None:
        """Collect ``edits``; they are ordered and checked when the plan is applied."""
        object.__setattr__(self, "edits", tuple(edits))

    def __iter__(self) -> Iterator[Edit]:
        """Iterate over the edits in submission order."""
        return iter(self.edits)

    def __len__(self) -> int:
        """Return the number of edits."""
        return len(self.edits)

    def __add__(self, other: EditPlan) -> EditPlan:
        """A plan with the edits of both, this plan's first."""
        return EditPlan((*self.edits, *other.edits))

    def ordered(self) -> tuple[Edit, ...]:
        """The edits in application order; ``EditError`` if two of them overlap.

        Edits are sorted by start offset; at one offset an insertion comes before a replacement,
        and insertions keep their submission order. Two edits overlap when they share a
        character or an insertion falls strictly inside a replacement (``Span.overlaps``), so
        two edits of the same non-empty span are an error, never last-wins.
        """
        ordered = sorted(
            enumerate(self.edits),
            key=lambda entry: (entry[1].span.start, not entry[1].span.is_empty, entry[0]),
        )
        edits = tuple(edit for _, edit in ordered)
        replacements = sorted(
            (edit for edit in edits if not edit.span.is_empty), key=lambda e: e.span.start
        )
        for before, after in zip(replacements, replacements[1:]):
            if before.span.overlaps(after.span):
                raise EditError(_overlap(before, after))
        insertions = [edit for edit in edits if edit.span.is_empty]
        for insertion in insertions:
            for replacement in replacements:
                if replacement.span.overlaps(insertion.span):
                    raise EditError(_overlap(replacement, insertion))
        return edits


def _overlap(first: Edit, second: Edit) -> str:
    return f"overlapping edits: {_describe(first)} and {_describe(second)}; make one edit per span"


def _describe(edit: Edit) -> str:
    where = f"[{edit.span.start}, {edit.span.end})"
    return f"{edit.reason or 'edit'} at {where}"


def apply_edits(text: str, plan: EditPlan | Iterable[Edit]) -> str:
    """Splice ``plan`` into ``text`` and return the new text; ``text`` is not changed.

    ``EditError`` if two edits overlap or a span lies outside the text.
    """
    edits = (plan if isinstance(plan, EditPlan) else EditPlan(plan)).ordered()
    parts: list[str] = []
    position = 0
    for edit in edits:
        if edit.span.end > len(text):
            raise EditError(f"{_describe(edit)} is outside the text (length {len(text)})")
        parts.append(text[position : edit.span.start])
        parts.append(edit.text)
        position = edit.span.end
    parts.append(text[position:])
    return "".join(parts)
