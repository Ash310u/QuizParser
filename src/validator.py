"""Validate compact question records without adding diagnostic fields to JSON."""

from __future__ import annotations

from pathlib import Path

from .models import Question


def validate_question(question: Question, output_parent: Path) -> list[str]:
    """Return validation messages for logging."""
    messages: list[str] = []
    if not question.content and not question.path:
        messages.append("Question has no text or image content.")
    if len(question.options) < 2:
        messages.append("Fewer than two options were detected.")
    labels = [option.label for option in question.options]
    if len(set(labels)) != len(labels):
        messages.append("Duplicate option labels were detected.")
    for option in question.options:
        if not option.content and not option.path:
            messages.append(f"Option {option.label} has no extractable content.")
    for path in [*question.path, *(path for option in question.options for path in option.path)]:
        if not (output_parent / path).is_file():
            messages.append(f"Asset is missing: {path}")
    return list(dict.fromkeys(messages))
