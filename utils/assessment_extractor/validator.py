"""Validate compact assessment question records without adding diagnostic
fields to JSON. Unlike the MCQ validator, there are no options/answers to
check here — only content and asset presence."""

from __future__ import annotations

from pathlib import Path

from .models import AssessmentQuestion


def validate_question(question: AssessmentQuestion, output_parent: Path) -> list[str]:
    """Return validation messages for logging."""
    messages: list[str] = []
    if not question.content and not question.path:
        messages.append("Question has no text or image content.")
    for path in question.path:
        if not (output_parent / path).is_file():
            messages.append(f"Asset is missing: {path}")
    return list(dict.fromkeys(messages))


def confidence_score(question: AssessmentQuestion, validation_messages: list[str], used_ocr: bool) -> float:
    """Estimate structural extraction confidence with notification thresholds."""
    score = 1.0
    messages = " ".join(validation_messages).casefold()

    if "no text or image content" in messages:
        score = min(score, 0.40)

    score -= min(messages.count("asset is missing") * 0.20, 0.40)
    if used_ocr:
        score -= 0.05
    return round(max(0.0, min(1.0, score)), 2)
