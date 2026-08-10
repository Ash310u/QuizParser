"""Pydantic models for the compact assessment JSON, matching the question
extractor's shape minus MCQ-only fields, plus marks and a Bloom's Taxonomy
cognitive level."""

from __future__ import annotations

from pydantic import BaseModel, Field

from utils.question_extractor.models import PaperMetadata, PathContainer


class AssessmentQuestion(PathContainer):
    number: int = Field(ge=1)
    page_number: int = Field(ge=1)
    content: str = ""
    marks: float = Field(default=1.0, ge=0.0)
    bt_level: str = "Understand"
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class AssessmentPaper(BaseModel):
    subject: str
    semester: str
    source_pdf: str
    metadata: PaperMetadata = Field(default_factory=PaperMetadata)
    questions: list[AssessmentQuestion] = Field(default_factory=list)
