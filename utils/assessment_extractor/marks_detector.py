"""Detect and strip a trailing marks (and optional explicit Bloom's level)
annotation from question content, e.g. ``[2 Marks, L1]``."""

from __future__ import annotations

import re

MARKS_RE = re.compile(
    r"[\[(]\s*(?P<marks>\d+(?:\.\d+)?)\s*marks?\b"
    r"(?:\s*[,;|]\s*(?P<level>L[1-6]))?"
    r"[^\])]*[\])]\s*$",
    re.IGNORECASE,
)
DEFAULT_MARKS = 1.0
LEVEL_CODES = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]


def extract_marks(content: str) -> tuple[str, float, str | None]:
    """Return ``(content without the trailing annotation, marks, explicit bt_level)``.

    Questions without an explicit ``[N Marks]``-style annotation default to
    one mark, matching the common one-mark-per-question quiz format. When the
    annotation also carries an ``L1``-``L6`` code (e.g. ``[2 Marks, L1]``),
    it is mapped to its Bloom's Taxonomy name. ``None`` is returned when the
    source PDF does not label it, allowing the caller to infer a level.
    """
    match = MARKS_RE.search(content)
    if not match:
        return content, DEFAULT_MARKS, None
    clean_content = content[: match.start()].rstrip()
    marks = float(match.group("marks"))
    level_code = match.group("level")
    level = LEVEL_CODES[int(level_code[1:]) - 1] if level_code else None
    return clean_content, marks, level
