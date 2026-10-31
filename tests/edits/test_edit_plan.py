"""Edit plans and the splice (M6 T1, architecture §7.5; T1 tier)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from netlistmod import Edit, EditError, EditPlan, Span, apply_edits


def test_replacements_and_insertions_use_original_offsets() -> None:
    text = "R1 a b 1k\n"
    plan = EditPlan(
        [
            Edit(Span(7, 9), "2.2k", "value"),
            Edit(Span(9, 9), " tc1=1m", "param"),
            Edit(Span(0, 0), "* new\n", "comment"),
        ]
    )
    assert apply_edits(text, plan) == "* new\nR1 a b 2.2k tc1=1m\n"
    assert text == "R1 a b 1k\n"


def test_insertions_at_one_point_keep_submission_order() -> None:
    plan = EditPlan([Edit(Span(1, 1), "x"), Edit(Span(1, 1), "y"), Edit(Span(1, 1), "z")])
    assert apply_edits("ab", plan) == "axyzb"


def test_an_insertion_at_a_replacement_start_comes_first() -> None:
    plan = EditPlan([Edit(Span(1, 2), "R"), Edit(Span(1, 1), "I"), Edit(Span(2, 2), "E")])
    assert apply_edits("abc", plan) == "aIREc"


def test_adjacent_replacements_do_not_overlap() -> None:
    assert apply_edits("abcd", [Edit(Span(0, 2), "X"), Edit(Span(2, 4), "Y")]) == "XY"


@pytest.mark.parametrize(
    "edits",
    [
        [Edit(Span(0, 2), "x"), Edit(Span(0, 2), "y")],
        [Edit(Span(0, 3), "x"), Edit(Span(2, 4), "y")],
        [Edit(Span(0, 3), "x"), Edit(Span(1, 1), "y")],
    ],
)
def test_overlapping_edits_are_an_error(edits: list[Edit]) -> None:
    with pytest.raises(EditError, match="overlapping edits"):
        apply_edits("abcd", edits)


def test_a_span_outside_the_text_is_an_error() -> None:
    with pytest.raises(EditError, match="outside the text"):
        apply_edits("ab", [Edit(Span(1, 5), "x")])


def test_plan_is_an_immutable_sequence() -> None:
    first = EditPlan([Edit(Span(0, 0), "a")])
    second = EditPlan([Edit(Span(1, 1), "b")])
    combined = first + second
    assert len(combined) == 2
    assert list(combined) == [*first, *second]
    assert apply_edits("x", EditPlan()) == "x"
    with pytest.raises(AttributeError):
        combined.edits = ()  # type: ignore[misc]


def _reference_splice(text: str, edits: list[tuple[int, int, str]]) -> str:
    """Apply edits one at a time from the end, the simplest correct splice."""
    result = text
    ordered = sorted(
        enumerate(edits), key=lambda entry: (entry[1][0], entry[1][0] != entry[1][1], entry[0])
    )
    for _, (start, end, replacement) in reversed(ordered):
        result = result[:start] + replacement + result[end:]
    return result


@st.composite
def _plans(draw: st.DrawFn) -> tuple[str, list[tuple[int, int, str]]]:
    text = draw(st.text(alphabet="ab \n", max_size=30))
    cuts = sorted(draw(st.lists(st.integers(0, len(text)), max_size=8)))
    edits: list[tuple[int, int, str]] = []
    # Pair consecutive cut points into disjoint spans; a pair of equal points is an insertion.
    for start, end in zip(cuts[::2], cuts[1::2]):
        edits.append((start, end, draw(st.text(alphabet="XY\r\n", max_size=4))))
        if draw(st.booleans()):
            edits.append((start, start, draw(st.text(alphabet="Z", max_size=2))))
    return text, draw(st.permutations(edits))


@given(_plans())
def test_random_non_overlapping_plans_match_a_reference_splice(
    case: tuple[str, list[tuple[int, int, str]]],
) -> None:
    text, edits = case
    plan = EditPlan(Edit(Span(start, end), replacement) for start, end, replacement in edits)
    assert apply_edits(text, plan) == _reference_splice(text, edits)
