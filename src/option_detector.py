"""Split a question into stem and labelled options without comma-based splitting."""

from __future__ import annotations

import re

from .pdf_reader import TextLine

OPTION_START = re.compile(
    r"^\s*(?:\(\s*([A-Ha-h]|[ivxlcdmIVXLCDM]+|\d{1,2})\s*\)|"
    r"([A-Ha-h]|[ivxlcdmIVXLCDM]+|\d{1,2})\s*[.):\-])\s*(.*)$"
)


def normalize_option_label(label: str) -> str:
    label = label.strip()
    if label.isdigit():
        return label
    return label.upper()


def parse_option_start(text: str) -> tuple[str, str] | None:
    match = OPTION_START.match(text)
    if not match:
        return None
    return normalize_option_label(match.group(1) or match.group(2)), match.group(3).strip()


def split_options(lines: list[TextLine]) -> tuple[list[TextLine], list[tuple[str, list[TextLine]]]]:
    stem: list[TextLine] = []
    options: list[tuple[str, list[TextLine]]] = []
    active: list[TextLine] | None = None
    for line in lines:
        match = parse_option_start(line.text)
        if match:
            active = [TextLine(line.page_number, match[1], line.rect, line.source)] if match[1] else []
            options.append((match[0], active))
        elif active is None:
            stem.append(line)
        else:
            active.append(line)
    return stem, options
