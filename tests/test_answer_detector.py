"""Tests for single- and multiple-answer key extraction."""

from __future__ import annotations

import unittest

import pymupdf as fitz

from src.answer_detector import resolve_answer_labels, split_answer_lines
from src.option_detector import parse_option_start
from src.models import Option
from src.pdf_reader import TextLine


def line(text: str, y: float) -> TextLine:
    return TextLine(1, text, fitz.Rect(50, y, 400, y + 10))


class AnswerDetectorTests(unittest.TestCase):
    def test_removes_answer_line_from_question_content(self) -> None:
        content, answer = split_answer_lines([line("A. One", 20), line("Correct answers: A and C", 40)])
        self.assertEqual([item.text for item in content], ["A. One"])
        self.assertEqual(answer, "A and C")

    def test_removes_answer_explanation_note(self) -> None:
        content, answer = split_answer_lines([line("4) Four", 20), line("Answers are shown after the options.", 40)])
        self.assertEqual([item.text for item in content], ["4) Four"])
        self.assertIsNone(answer)

    def test_resolves_single_and_multiple_labels(self) -> None:
        options = [Option(label=label, content=value) for label, value in [("A", "One"), ("B", "Two"), ("C", "Three")]]
        self.assertEqual(resolve_answer_labels("B. Two", options), ["B"])
        self.assertEqual(resolve_answer_labels("Correct answer: (a), (c)", options), ["A", "C"])

    def test_resolves_answer_text_when_no_label_is_printed(self) -> None:
        options = [Option(label="1", content="Waterfall"), Option(label="2", content="Both statements")]
        self.assertEqual(resolve_answer_labels("Both statements", options), ["2"])

    def test_checkbox_prefixed_label_is_recognized(self) -> None:
        self.assertEqual(parse_option_start("[ ] B. Velocity"), ("B", "Velocity"))


if __name__ == "__main__":
    unittest.main()
