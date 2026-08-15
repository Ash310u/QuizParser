"""Basic Flask route tests without loading the heavyweight summary model."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app import create_app


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = create_app().test_client()

    @patch("app.save_summary_output", return_value=__import__("pathlib").Path("output/summarizer/summary.json"))
    @patch("app.summarize_units", return_value={"1": "Short summary"})
    def test_summarize_endpoint(self, summarize_mock, save_mock) -> None:
        response = self.client.post("/summarize", json={"units": {"1": ["A short source text."]}, "word_limit": 20})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"summaries": {"1": "Short summary"}, "output_path": "output/summarizer/summary.json"})
        summarize_mock.assert_called_once_with({"1": ["A short source text."]}, 20)
        save_mock.assert_called_once()

    def test_summarize_requires_units_object(self) -> None:
        response = self.client.post("/summarize", json={"units": ["not an object"]})
        self.assertEqual(response.status_code, 400)

    @patch("app.extract_questions", return_value={"processed_pdfs": 1, "failed_pdfs": 0, "results": [], "failures": []})
    def test_question_extractor_endpoint(self, extract_mock) -> None:
        response = self.client.post("/question-extractor")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["processed_pdfs"], 1)
        extract_mock.assert_called_once()

    @patch("app.extract_assessments", return_value={"processed_pdfs": 1, "failed_pdfs": 0, "results": [], "failures": []})
    def test_assessment_extractor_endpoint(self, extract_mock) -> None:
        response = self.client.post("/assessment-extractor")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["processed_pdfs"], 1)
        extract_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
