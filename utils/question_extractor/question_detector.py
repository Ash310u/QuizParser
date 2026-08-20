"""Recognize question starts from coordinate-aware text lines."""

from __future__ import annotations

import re

from .pdf_reader import TextLine

EXPLICIT_QUESTION_START = re.compile(
    r"^\s*(?:Q\s*\.?\s*|QUESTION\s+)(\d{1,4})(?:\s*[.):\-])?\s*(.*)$",
    re.IGNORECASE,
)
NUMBERED_QUESTION_START = re.compile(r"^\s*(?:\(\s*)?(\d{1,4})(?:\s*\)|\s*[.:-])\s*(.*)$")
TERMINAL_DOCUMENT_MARKER = re.compile(
    r"^\s*(?:[-_=*#]\s*)*(?:end|the\s+end)\s+of\s+"
    r"(?:the\s+)?(?:quiz|questions?|paper|test|exam|document)\b.*$",
    re.IGNORECASE,
)


def is_terminal_document_line(text: str) -> bool:
    """Recognize common document-end labels that are not question content."""
    return TERMINAL_DOCUMENT_MARKER.match(text) is not None


def parse_question_start(text: str) -> tuple[int, str, bool] | None:
    """Return number, remainder, and whether an explicit Q/Question marker was used."""
    match = EXPLICIT_QUESTION_START.match(text)
    if match:
        return int(match.group(1)), match.group(2).strip(), True
    match = NUMBERED_QUESTION_START.match(text)
    if not match:
        return None
    return int(match.group(1)), match.group(2).strip(), False


def split_question_lines(lines: list[TextLine]) -> list[tuple[int, int, list[TextLine]]]:
    """Return (number, page, lines) groups. Header lines before Q1 are ignored."""
    groups: list[tuple[int, int, list[TextLine]]] = []
    current_number: int | None = None
    current_page: int | None = None
    current_question_x: float | None = None
    current_lines: list[TextLine] = []
    for line in lines:
        if current_number is not None and is_terminal_document_line(line.text):
            groups.append((current_number, current_page or line.page_number, current_lines))
            return groups
        start = parse_question_start(line.text)
        # Bare numeric labels such as `1)` can be answer options. Once a
        # question is open, promote those only when they continue numbering.
        is_new_question = start is not None and (
            current_number is None
            or start[2]
            or (start[0] == current_number + 1 and (current_question_x is None or line.rect.x0 <= current_question_x + 3))
        )
        if is_new_question and start:
            if current_number is not None:
                groups.append((current_number, current_page or line.page_number, current_lines))
            current_number, current_page = start[0], line.page_number
            current_question_x = line.rect.x0
            # Retain an empty marker line for its coordinates. A question can
            # begin with an image/equation immediately after `2.`.
            current_lines = [TextLine(line.page_number, start[1], line.rect, line.source)]
        elif current_number is not None:
            current_lines.append(line)
    if current_number is not None:
        groups.append((current_number, current_page or 1, current_lines))
    return groups
