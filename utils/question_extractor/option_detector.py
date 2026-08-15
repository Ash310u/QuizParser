"""Split MCQ options using labels first, then conservative layout fallbacks."""

from __future__ import annotations

import re
from statistics import median

from .pdf_reader import TextLine

OPTION_START = re.compile(
    r"^\s*(?:\(\s*([A-Ha-h]|[ivxlcdmIVXLCDM]+|\d{1,2})\s*\)|"
    r"([A-Ha-h]|[ivxlcdmIVXLCDM]+|\d{1,2})\s*[.):\-])\s*(.*)$"
)
CHECKBOX_PREFIX = re.compile(r"^\s*(?:\[\s*[xX]?\s*\]|\(\s*[xX]\s*\))\s*")
BULLET_START = re.compile(r"^\s*(?:[•●▪◦*]|[-–—])\s+(.*)$")
OPTIONS_PREFIX = re.compile(r"^\s*(?:options?|choices?|answers?)\s*[:\-]\s*(.*)$", re.IGNORECASE)
ANNOTATION = re.compile(r"^\s*(?:options?|choices?|answers?)\s+(?:are|use|appear|shown|separated)\b", re.IGNORECASE)


def normalize_option_label(label: str) -> str:
    label = label.strip()
    return label if label.isdigit() else label.upper()


def parse_option_start(text: str) -> tuple[str, str] | None:
    match = OPTION_START.match(CHECKBOX_PREFIX.sub("", text))
    if not match:
        return None
    return normalize_option_label(match.group(1) or match.group(2)), match.group(3).strip()


def _line_with_text(line: TextLine, text: str) -> TextLine:
    return TextLine(line.page_number, text, line.rect, line.source)


def _split_explicit_labels(lines: list[TextLine]) -> tuple[list[TextLine], list[tuple[str, list[TextLine]]]]:
    stem: list[TextLine] = []
    options: list[tuple[str, list[TextLine]]] = []
    active: list[TextLine] | None = None
    for line in lines:
        match = parse_option_start(line.text)
        if match:
            # Retain empty markers so image-only choices retain their location.
            active = [_line_with_text(line, match[1])]
            options.append((match[0], active))
        elif active is None:
            stem.append(line)
        else:
            # Labels in a horizontal row are read left-to-right. Route later
            # text to the closest same-row label, instead of always to the
            # last (rightmost) label.
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


def _split_bullets(lines: list[TextLine]) -> tuple[list[TextLine], list[tuple[str, list[TextLine]]]] | None:
    stem: list[TextLine] = []
    options: list[tuple[str, list[TextLine]]] = []
    active: list[TextLine] | None = None
    for line in lines:
        match = BULLET_START.match(line.text)
        if match:
            active = [_line_with_text(line, match.group(1).strip())]
            options.append((str(len(options) + 1), active))
        elif active is None:
            stem.append(line)
        elif ANNOTATION.match(line.text):
            # Explanatory notes beneath a list are not a fifth answer choice.
            continue
        else:
            active.append(line)
    return (stem, options) if len(options) >= 2 else None


def _delimited_parts(text: str) -> list[str]:
    # Semicolon-separated choices are unambiguous. Commas require at least
    # three values unless an explicit "Options:" prefix was supplied.
    delimiter = ";" if ";" in text else "," if "," in text else None
    if delimiter is None:
        return []
    return [part.strip() for part in text.split(delimiter) if part.strip()]


def _split_delimited(lines: list[TextLine]) -> tuple[list[TextLine], list[tuple[str, list[TextLine]]]] | None:
    for index, line in enumerate(lines):
        prefix = OPTIONS_PREFIX.match(line.text)
        payload = prefix.group(1) if prefix else line.text
        parts = _delimited_parts(payload)
        explicit_options = prefix is not None
        delimiter = ";" if ";" in payload else "," if "," in payload else None
        minimum = 2 if explicit_options or delimiter == ";" else 3
        # An unlabeled delimited row must follow the question text. This avoids
        # splitting a natural-language question that merely contains commas.
        if index == 0 and not explicit_options:
            continue
        if len(parts) < minimum or any(len(part) > 140 for part in parts):
            continue
        options = [(str(number), [_line_with_text(line, value)]) for number, value in enumerate(parts, start=1)]
        return lines[:index], options
    return None


def _split_horizontal_row(lines: list[TextLine]) -> tuple[list[TextLine], list[tuple[str, list[TextLine]]]] | None:
    """Split a tab-marked row of visually separated, unlabeled choices."""
    for index, line in enumerate(lines):
        parts = [part.strip() for part in line.text.split("\t") if part.strip()]
        if index == 0 or len(parts) < 2 or any(len(part) > 140 for part in parts):
            continue
        options = [(str(number), [_line_with_text(line, value)]) for number, value in enumerate(parts, start=1)]
        return lines[:index], options
    return None


def _split_visual_lines(lines: list[TextLine]) -> tuple[list[TextLine], list[tuple[str, list[TextLine]]]] | None:
    """Infer line-separated unlabeled choices from a clear layout transition."""
    if len(lines) < 3:
        return None
    heights = [line.rect.height for line in lines if line.rect.height > 0]
    normal_height = median(heights) if heights else 10
    for index in range(1, len(lines) - 1):
        previous, current = lines[index - 1], lines[index]
        if previous.page_number != current.page_number:
            continue
        gap = current.rect.y0 - previous.rect.y1
        indented = current.rect.x0 >= previous.rect.x0 + 4
        if gap >= max(6, normal_height * 0.65) or indented:
            option_lines = [line for line in lines[index:] if not ANNOTATION.match(line.text)]
            # Each separately positioned line is a choice. This handles a
            # vertical list as well as one row of unlabelled choices.
            options = [(str(number), [line]) for number, line in enumerate(option_lines, start=1)]
            return lines[:index], options
    return None


def split_options(lines: list[TextLine]) -> tuple[list[TextLine], list[tuple[str, list[TextLine]]]]:
    """Return stem and options, supporting labels and common unlabeled layouts.

    Inferred labels are numeric strings (``"1"``, ``"2"``, ...), preserving a
    compact uniform JSON schema even when the source has no visible labels.
    """
    stem, options = _split_explicit_labels(lines)
    if options:
        return stem, options
    for strategy in (_split_bullets, _split_delimited, _split_horizontal_row, _split_visual_lines):
        result = strategy(lines)
        if result is not None:
            return result
    return lines, []
