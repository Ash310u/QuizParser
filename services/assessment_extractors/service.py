"""Public service interface for assessment PDF extraction."""

from utils.assessment_extractor.engine import extract_assessments, extract_assessments_from_directory

__all__ = ["extract_assessments", "extract_assessments_from_directory"]
