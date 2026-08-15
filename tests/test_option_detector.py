"""Coverage for label-free option layouts using only the standard library."""

from __future__ import annotations

import unittest

import pymupdf as fitz

from utils.question_extractor.option_detector import split_options
from utils.question_extractor.pdf_reader import TextLine


def line(text: str, y: float, x: float = 50) -> TextLine:
    return TextLine(1, text, fitz.Rect(x, y, x + max(20, len(text) * 5), y + 10))


class OptionDetectorTests(unittest.TestCase):
    def assert_options(self, source: list[TextLine], labels: list[str], values: list[str]) -> None:
        stem, options = split_options(source)
        self.assertEqual([label for label, _ in options], labels)
        self.assertEqual([group[0].text for _, group in options], values)
        self.assertTrue(stem)

    def test_bullet_options_receive_numeric_labels(self) -> None:
        self.assert_options(
            [line("Choose a colour.", 20), line("• Red", 45), line("• Green", 65), line("• Blue", 85)],
            ["1", "2", "3"], ["Red", "Green", "Blue"],
        )

    def test_semicolon_options_receive_numeric_labels(self) -> None:
        self.assert_options(
            [line("Choose one.", 20), line("red; green; blue", 45)],
            ["1", "2", "3"], ["red", "green", "blue"],
        )

    def test_comma_options_receive_numeric_labels(self) -> None:
        self.assert_options(
            [line("Choose one.", 20), line("red, green, blue", 45)],
            ["1", "2", "3"], ["red", "green", "blue"],
        )

    def test_unlabelled_lines_receive_numeric_labels(self) -> None:
        self.assert_options(
            [line("Choose one.", 20), line("First", 45, 65), line("Second", 65, 65), line("Third", 85, 65)],
            ["1", "2", "3"], ["First", "Second", "Third"],
        )

    def test_horizontal_visual_row_receives_numeric_labels(self) -> None:
        self.assert_options(
            [line("Choose one.", 20), line("Analysis\tDesign\tTesting\tMaintenance", 45)],
            ["1", "2", "3", "4"], ["Analysis", "Design", "Testing", "Maintenance"],
        )

    def test_bullet_annotation_is_not_an_option(self) -> None:
        self.assert_options(
            [line("Choose one.", 20), line("• First", 45), line("• Second", 65), line("Options use bullets.", 85)],
            ["1", "2"], ["First", "Second"],
        )


if __name__ == "__main__":
    unittest.main()
