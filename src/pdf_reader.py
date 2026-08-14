"""PyMuPDF page extraction with coordinates in natural reading order."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass(frozen=True)
class TextLine:
    page_number: int
    text: str
    rect: fitz.Rect
    source: str = "pdf"


@dataclass
class PageData:
    number: int
    page: fitz.Page
    lines: list[TextLine]
    width: float
    height: float


def extract_page(page: fitz.Page, page_number: int) -> PageData:
    """Extract words, grouping them into ordered visual lines."""
    words = page.get_text("words", sort=True)
    grouped: dict[tuple[int, int], list[tuple]] = {}
    for word in words:
        grouped.setdefault((int(word[5]), int(word[6])), []).append(word)
    lines: list[TextLine] = []
    for _, line_words in sorted(grouped.items(), key=lambda item: (min(w[1] for w in item[1]), min(w[0] for w in item[1]))):
        line_words.sort(key=lambda word: word[0])
        rect = fitz.Rect(
            min(word[0] for word in line_words), min(word[1] for word in line_words),
            max(word[2] for word in line_words), max(word[3] for word in line_words),
        )
        text_parts: list[str] = []
        previous = None
        for word in line_words:
            if previous is not None:
                gap = word[0] - previous[2]
                # Retain deliberately wide visual gaps as tabs. They often
                # indicate unlabeled choices placed in one horizontal row.
                if gap >= max(12, (previous[2] - previous[0]) / max(len(str(previous[4])), 1) * 2.3):
                    text_parts.append("\t")
                else:
                    text_parts.append(" ")
            text_parts.append(str(word[4]))
            previous = word
        text = "".join(text_parts).strip()
        if text:
            lines.append(TextLine(page_number, text, rect))
    return PageData(page_number, page, lines, page.rect.width, page.rect.height)


def has_usable_text(page_data: PageData) -> bool:
    """Reject sparse/garbled extraction; this is deliberately conservative for OCR."""
    text = " ".join(line.text for line in page_data.lines)
    alnum = sum(character.isalnum() for character in text)
    return len(page_data.lines) >= 2 and alnum >= 20


def open_pdf(path: Path) -> fitz.Document:
    return fitz.open(path)
