"""Normalize every output option label to a stable alphabetic sequence."""

from __future__ import annotations


def alphabetic_label(index: int) -> str:
    """Return A, B, ..., Z, AA, AB, ... for a zero-based option index."""
    if index < 0:
        raise ValueError("option index cannot be negative")
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result
