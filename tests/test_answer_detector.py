"""Tests for single- and multiple-answer key extraction."""

from __future__ import annotations

import unittest

import pymupdf as fitz

from utils.question_extractor.answer_detector import resolve_answer_labels, split_answer_lines
from utils.question_extractor.label_normalizer import alphabetic_label
from utils.question_extractor.option_detector import parse_option_start
from utils.question_extractor.models import Option
from utils.question_extractor.models import Question
from utils.question_extractor.pdf_reader import TextLine
from utils.question_extractor.validator import confidence_score


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

    def test_removes_text_after_answer_key(self) -> None:
        content, answer = split_answer_lines([
            line("4) Four", 20),
            line("Correct Answer: A", 40),
            line("--- End of Quiz ---", 60),
        ])
        self.assertEqual([item.text for item in content], ["4) Four"])
        self.assertEqual(answer, "A")

    def test_resolves_single_and_multiple_labels(self) -> None:
        options = [Option(label=label, content=value) for label, value in [("A", "One"), ("B", "Two"), ("C", "Three")]]
        self.assertEqual(resolve_answer_labels("B. Two", options), ["B"])
        self.assertEqual(resolve_answer_labels("Correct answer: (a), (c)", options), ["A", "C"])

    def test_resolves_answer_text_when_no_label_is_printed(self) -> None:
        options = [Option(label="1", content="Waterfall"), Option(label="2", content="Both statements")]
        self.assertEqual(resolve_answer_labels("Both statements", options), ["2"])

    def test_checkbox_prefixed_label_is_recognized(self) -> None:
        self.assertEqual(parse_option_start("[ ] B. Velocity"), ("B", "Velocity"))

    def test_answer_labels_remap_from_source_to_standard_labels(self) -> None:
        options = [Option(label="A", content="Ten"), Option(label="B", content="Eleven"), Option(label="C", content="Twelve")]
        self.assertEqual(resolve_answer_labels("3) Twelve", options, ["1", "2", "3"]), ["C"])
        self.assertEqual(resolve_answer_labels("I and II", options[:2], ["I", "II"]), ["A", "B"])

    def test_alphabetic_labels_continue_after_z(self) -> None:
        self.assertEqual([alphabetic_label(index) for index in (0, 3, 25, 26)], ["A", "D", "Z", "AA"])

    def test_confidence_score_penalizes_unstructured_question(self) -> None:
        question = Question(number=1, page_number=1, content="", options=[])
        self.assertEqual(
            confidence_score(question, ["Question has no text or image content.", "Fewer than two options were detected."], False, False),
            0.20,
        )

    def test_confidence_thresholds_for_option_problems(self) -> None:
        three = Question(number=1, page_number=1, content="Prompt", options=[Option(label=label, content=label) for label in "ABC"])
        five = Question(number=1, page_number=1, content="Prompt", options=[Option(label=label, content=label) for label in "ABCDE"])
        one_duplicate = Question(number=1, page_number=1, content="Prompt", options=[Option(label=label, content=label) for label in ["A", "A", "C", "D"]])
        two_duplicates = Question(number=1, page_number=1, content="Prompt", options=[Option(label=label, content=label) for label in ["A", "A", "B", "B"]])
        one_empty = Question(number=1, page_number=1, content="Prompt", options=[Option(label="A", content=""), *[Option(label=label, content=label) for label in "BCD"]])
        self.assertLess(confidence_score(three, [], False, False), 0.50)
        self.assertEqual(confidence_score(five, [], False, False), 0.90)
        self.assertLess(confidence_score(one_duplicate, [], False, False), 0.75)
        self.assertLess(confidence_score(two_duplicates, [], False, False), 0.50)
        self.assertLess(confidence_score(one_empty, [], False, False), 0.75)
        standard_labels = Question(number=1, page_number=1, content="Prompt", options=[Option(label=label, content=label) for label in "ABCD"])
        self.assertLess(confidence_score(standard_labels, [], False, False, source_duplicate_count=1), 0.75)
        self.assertLess(confidence_score(standard_labels, [], False, False, source_duplicate_count=2), 0.50)


if __name__ == "__main__":
    unittest.main()
