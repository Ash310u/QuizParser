"""Extract answer-key lines and resolve them to option labels."""

from __future__ import annotations

import re

from .models import Option
from .pdf_reader import TextLine

ANSWER_LINE = re.compile(r"^\s*(?:correct\s+answers?|answers?)\s*[:\-]\s*(.+?)\s*$", re.IGNORECASE)
ANSWER_NOTE = re.compile(r"^\s*(?:correct\s+answers?|answers?)\s+(?:are|shown|appear)\b", re.IGNORECASE)


def is_answer_line(text: str) -> bool:
    return ANSWER_LINE.match(text) is not None


def split_answer_lines(lines: list[TextLine]) -> tuple[list[TextLine], str | None]:
    """Remove answer-key lines from question content and return their value."""
    content_lines: list[TextLine] = []
    answers: list[str] = []
    for line in lines:
        match = ANSWER_LINE.match(line.text)
        if match:
            answers.append(match.group(1))
        elif ANSWER_NOTE.match(line.text):
            # Informational page text such as "Answers are shown after the
            # options" is neither question content nor an answer key value.
            continue
        else:
            content_lines.append(line)
    return content_lines, " ".join(answers) if answers else None


def resolve_answer_labels(
    answer_text: str | None,
    options: list[Option],
    source_labels: list[str] | None = None,
) -> list[str]:
    """Resolve printed answers such as ``B. Newton`` or ``I and II``.

    If a paper prints an answer's wording rather than its label, match it to an
    option's text. The returned list preserves the order of the options.
    """
    if not answer_text:
        return []
    normalized = re.sub(r"\s+", " ", answer_text).strip()
    selected: list[str] = []
    for index, option in enumerate(options):
        source_label = source_labels[index] if source_labels and index < len(source_labels) else option.label
        label = re.escape(source_label)
        if re.search(rf"(?<![A-Za-z0-9])\(?{label}\)?(?=$|[^A-Za-z0-9])", normalized, re.IGNORECASE):
            selected.append(option.label)
            continue
        content = re.sub(r"\s+", " ", option.content).strip()
        if content and content.casefold() in normalized.casefold():
            selected.append(option.label)
    return selected
