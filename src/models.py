"""Pydantic models for the JSON written by the converter."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    value: str = Field(min_length=1)


class ImageBlock(BaseModel):
    type: Literal["image"] = "image"
    path: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def relative_png_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".png":
            raise ValueError("image paths must be relative PNG paths")
        return value


ContentBlock = TextBlock | ImageBlock


class Option(BaseModel):
    label: str = Field(min_length=1, max_length=12)
    content: list[ContentBlock] = Field(default_factory=list)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return value.strip().upper()


class Question(BaseModel):
    number: int = Field(ge=1)
    page_number: int = Field(ge=1)
    content: list[ContentBlock] = Field(default_factory=list)
    options: list[Option] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Paper(BaseModel):
    subject: str
    semester: str
    source_pdf: str
    questions: list[Question] = Field(default_factory=list)
