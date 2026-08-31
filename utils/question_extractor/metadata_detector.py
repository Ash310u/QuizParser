"""Extract paper-level metadata from MCQ PDF text."""

from __future__ import annotations

import re

from .pdf_reader import TextLine


# Require a label so question wording (for example, "time complexity") cannot
# be mistaken for an assessment duration.
TIME_LABEL = re.compile(
    r"\b(?:total\s+time|time\s+allowed|time\s+limit|duration|time)\b\s*(?:[:\-–—]|is)?\s*"
    r"(?P<value>\d+(?:\.\d+)?\s*(?:hours?|hrs?|hr|minutes?|mins?|min)"
    r"(?:\s*\d+(?:\.\d+)?\s*(?:minutes?|mins?|min))?|\d{1,2}:\d{2})\b",
    re.IGNORECASE,
)
HOURS = re.compile(r"(?P<amount>\d+(?:\.\d+)?)\s*(?:hours?|hrs?|hr)\b", re.IGNORECASE)
MINUTES = re.compile(r"(?P<amount>\d+(?:\.\d+)?)\s*(?:minutes?|mins?|min)\b", re.IGNORECASE)
CLOCK_DURATION = re.compile(r"^(?P<hours>\d{1,2}):(?P<minutes>\d{2})$")
PAPER_CODE_LABEL = re.compile(
    r"\bpaper\s*(?:code|no\.?|number)\s*[:#\-]\s*(?P<value>[A-Za-z0-9][A-Za-z0-9._/-]*)\b",
    re.IGNORECASE,
)


def extract_paper_code(lines: list[TextLine]) -> str | None:
    """Return the first explicitly labelled paper code, if present."""
    for line in lines:
        match = PAPER_CODE_LABEL.search(line.text)
        if match:
            return match.group("value")
    return None


def extract_total_time_minutes(lines: list[TextLine]) -> float | None:
    """Return the first labelled assessment duration in minutes, if present."""
    for line in lines:
        match = TIME_LABEL.search(line.text)
        if not match:
            continue
        value = match.group("value").strip()
        clock = CLOCK_DURATION.fullmatch(value)
        if clock:
            return float(int(clock.group("hours")) * 60 + int(clock.group("minutes")))
        hours = sum(float(item.group("amount")) for item in HOURS.finditer(value))
        minutes = sum(float(item.group("amount")) for item in MINUTES.finditer(value))
        total = hours * 60 + minutes
        if total > 0:
            return total
    return None
