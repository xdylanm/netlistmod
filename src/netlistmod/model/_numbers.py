"""Whether a field's text reads as a number: the shared test of decision 0024 item 7, used by the
element rules (a number is never a model), the document layer (an xyce `.model` named as a number)
and the edit layer. Internal to the package."""

from __future__ import annotations

_DIGITS = frozenset("0123456789")
_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZµ")


def _is_letter(char: str) -> bool:
    """Whether ``char`` is a letter of LTspice's NUMBER and FIELD_NUMBER (``[^\\W\\d_]``)."""
    return char.isalnum() and not char.isdecimal()


def reads_as_number(text: str, *, any_letter: bool = False) -> bool:
    """Whether ``text`` is core.lark's FIELD_NUMBER: a number, then letters only (``2``, ``1k``).

    With ``any_letter``, the letters are any Unicode letter, as in LTspice's NUMBER (``1μ``,
    ``2Ω``): a field written so is a number in the model's place on either dialect, never a
    model name (M18 A1-4).
    """
    i = 1 if text[:1] in ("+", "-") else 0
    start = i
    while i < len(text) and text[i] in _DIGITS:
        i += 1
    digits = i - start
    if i < len(text) and text[i] == ".":
        i += 1
        while i < len(text) and text[i] in _DIGITS:
            i += 1
            digits += 1
    if digits == 0:
        return False
    if i < len(text) and text[i] in "eE":
        j = i + 1 + (text[i + 1 : i + 2] in ("+", "-"))
        if j < len(text) and text[j] in _DIGITS:
            i = j
            while i < len(text) and text[i] in _DIGITS:
                i += 1
    return all(char in _LETTERS or (any_letter and _is_letter(char)) for char in text[i:])
