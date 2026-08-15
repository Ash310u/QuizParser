"""Pydantic models for the compact JSON written by the converter."""

from __future__ import annotations

from pathlib import PurePosixPath

from pydantic import BaseModel, Field, field_validator


class PathContainer(BaseModel):
    """Common relative asset-path validation for questions and options."""

    path: list[str] = Field(default_factory=list)

    @field_validator("path")
    @classmethod
    def relative_png_paths(cls, values: list[str]) -> list[str]:
        for value in values:
            path = PurePosixPath(value)
            if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".png":
                raise ValueError("image paths must be relative PNG paths")
        return values


class Option(PathContainer):
    label: str = Field(min_length=1, max_length=12)
    content: str = ""

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return value.strip().upper()


class Question(PathContainer):
    number: int = Field(ge=1)
    page_number: int = Field(ge=1)
    content: str = ""
    options: list[Option] = Field(default_factory=list)
    # Always an array: [] means no answer key was detected, while one or more
    # values contain the selected option labels.
    answer: list[str] = Field(default_factory=list)


class Paper(BaseModel):
    subject: str
    semester: str
    source_pdf: str
    questions: list[Question] = Field(default_factory=list)
