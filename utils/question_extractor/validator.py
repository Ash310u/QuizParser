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


def confidence_score(
    question: Question,
    validation_messages: list[str],
    answer_key_was_present: bool,
    used_ocr: bool,
    source_duplicate_count: int = 0,
) -> float:
    """Estimate structural extraction confidence with notification thresholds.

    The rules deliberately place incomplete or ambiguous MCQs below 0.50, so
    callers can notify users without needing to interpret free-form warnings.
    A missing answer key is acceptable; an answer key that cannot be resolved
    is not.
    """
    score = 1.0
    messages = " ".join(validation_messages).casefold()
    option_count = len(question.options)
    duplicate_count = max(option_count - len({option.label for option in question.options}), source_duplicate_count)
    empty_count = sum(not option.content and not option.path for option in question.options)

    if "no text or image content" in messages:
        score = min(score, 0.40)

    # Standard MCQs contain four choices. Any smaller set is deliberately
    # below the notification threshold; no options is substantially lower.
    if option_count == 0:
        score = min(score, 0.20)
    elif option_count < 4:
        score = min(score, 0.49)
    elif option_count > 4:
        score -= min((option_count - 4) * 0.10, 0.30)

    # One duplicate/empty option is a review-worthy issue (<75%). Multiple
    # such issues are severe enough to trigger the <50% notification.
    if duplicate_count == 1:
        score = min(score, 0.74)
    elif duplicate_count >= 2:
        score = min(score, 0.49)
    if empty_count == 1:
        score = min(score, 0.74)
    elif empty_count >= 2:
        score = min(score, 0.49)

    score -= min(messages.count("asset is missing") * 0.20, 0.40)
    if answer_key_was_present and not question.answer:
        score = min(score, 0.74)
    if used_ocr:
        score -= 0.05
    return round(max(0.0, min(1.0, score)), 2)
