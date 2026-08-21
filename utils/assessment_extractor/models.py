"""Models for compact assessment extraction output."""

from __future__ import annotations

from pydantic import BaseModel, Field

from utils.question_extractor.models import PathContainer


class AssessmentQuestion(PathContainer):
    """A non-MCQ question record without answer-related fields."""

    number: int = Field(ge=1)
    page_number: int = Field(ge=1)
    content: str = ""
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class AssessmentPaper(BaseModel):
    subject: str
    semester: str
    source_pdf: str
    questions: list[AssessmentQuestion] = Field(default_factory=list)
