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
            # Retain empty label markers: their coordinates let image-only
            # choices be associated with A/B/C/D rather than the question.
            active = [TextLine(line.page_number, match[1], line.rect, line.source)]
            options.append((match[0], active))
        elif active is None:
            stem.append(line)
        else:
            # Labels arranged in a horizontal row are read left-to-right, so
            # `active` would otherwise always be D. Route later text to the
            # closest label on that row (e.g. "Yes / No?" inside option C).
            same_page = [entry for entry in options if entry[1] and entry[1][0].page_number == line.page_number]
            if len(same_page) >= 2:
                label_ys = [entry[1][0].rect.y0 for entry in same_page]
                if max(label_ys) - min(label_ys) <= 24:
                    line_center = (line.rect.x0 + line.rect.x1) / 2
                    _, active = min(
                        same_page,
                        key=lambda entry: abs(((entry[1][0].rect.x0 + entry[1][0].rect.x1) / 2) - line_center),
                    )
            active.append(line)
    return stem, options
