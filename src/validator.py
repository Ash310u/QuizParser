"""Validation helpers that retain recoverable extraction problems as warnings."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from .models import Question


def validate_question(question: Question, output_parent: Path) -> Question:
    warnings = list(question.warnings)
    if question.number < 1:
        warnings.append("Question number is missing or invalid.")
    if len(question.options) < 2:
        warnings.append("Fewer than two options were detected.")
    labels = [option.label for option in question.options]
    if len(set(labels)) != len(labels):
        warnings.append("Duplicate option labels were detected.")
    for option in question.options:
        if not option.content:
            warnings.append(f"Option {option.label} has no extractable content.")
    for block in [*question.content, *(block for option in question.options for block in option.content)]:
        if block.type == "image" and not (output_parent / block.path).is_file():
            warnings.append(f"Asset is missing: {block.path}")
    question.warnings = list(dict.fromkeys(warnings))
    try:
        return Question.model_validate(question.model_dump())
    except ValidationError as exc:  # defensive: Pydantic model rules remain authoritative
        question.warnings.append(f"Schema validation warning: {exc.errors()[0]['msg']}")
        return question
