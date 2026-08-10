from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf

from utils.assessment_extractor.engine import convert_assessment, extract_assessments, extract_assessments_from_directory
from utils.assessment_extractor.marks_detector import extract_marks
from utils.question_extractor.folder_scanner import PdfJob


class MarksDetectorTests(unittest.TestCase):
    def test_maps_explicit_level_code_to_bloom_name(self) -> None:
        content, marks, level = extract_marks("Define a data structure. [2 Marks, L1]")
        self.assertEqual(content, "Define a data structure.")
        self.assertEqual(marks, 2.0)
        self.assertEqual(level, "Remember")

    def test_l6_maps_to_create(self) -> None:
        _, _, level = extract_marks("Design a new data structure. [4 Marks, L6]")
        self.assertEqual(level, "Create")

    def test_no_level_code_returns_none(self) -> None:
        content, marks, level = extract_marks("Explain arrays. [3 Marks]")
        self.assertEqual(content, "Explain arrays.")
        self.assertEqual(marks, 3.0)
        self.assertIsNone(level)

    def test_no_annotation_defaults_marks_and_level(self) -> None:
        content, marks, level = extract_marks("Explain arrays.")
        self.assertEqual(content, "Explain arrays.")
        self.assertEqual(marks, 1.0)
        self.assertIsNone(level)


class AssessmentExtractorTests(unittest.TestCase):
    def setUp(self) -> None:
        classifier_patcher = patch(
            "utils.assessment_extractor.engine.classify_bt_level",
            return_value="Understand",
        )
        self.classify_mock = classifier_patcher.start()
        self.addCleanup(classifier_patcher.stop)

    def test_produces_question_extractor_shaped_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf_path = root / "assignment.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text((72, 72), "Q1. Define a data structure. [2 Marks]")
            page.insert_text((72, 96), "Q2. Explain arrays.")
            document.save(pdf_path)
            document.close()

            job = PdfJob(pdf_path, "unspecified", "unspecified")
            json_path = convert_assessment(job, root / "output")
            payload = json.loads(json_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["subject"], "unspecified")
            self.assertEqual(payload["semester"], "unspecified")
            self.assertEqual(payload["source_pdf"], "assignment.pdf")
            self.assertEqual(len(payload["questions"]), 2)

            first, second = payload["questions"]
            self.assertEqual(first["number"], 1)
            self.assertEqual(first["content"], "Define a data structure.")
            self.assertEqual(first["marks"], 2.0)
            self.assertEqual(first["bt_level"], "Understand")
            self.assertNotIn("options", first)
            self.assertNotIn("answer", first)

            # No explicit marks annotation defaults to one mark.
            self.assertEqual(second["marks"], 1.0)
            self.assertEqual(second["bt_level"], "Understand")

    def test_explicit_level_is_mapped_and_missing_level_is_classified(self) -> None:
        self.classify_mock.return_value = "Evaluate"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf_path = root / "assignment.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text((72, 72), "Q1. Define a data structure. [2 Marks, L1]")
            page.insert_text((72, 96), "Q2. Explain arrays.")
            document.save(pdf_path)
            document.close()

            job = PdfJob(pdf_path, "unspecified", "unspecified")
            json_path = convert_assessment(job, root / "output")
            payload = json.loads(json_path.read_text(encoding="utf-8"))

            labelled, unlabelled = payload["questions"]
            self.assertEqual(labelled["bt_level"], "Remember")
            self.assertEqual(unlabelled["bt_level"], "Evaluate")
            self.classify_mock.assert_called_once_with(unlabelled["content"])

    def test_trailing_end_of_assignment_is_excluded_from_last_question(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf_path = root / "assignment.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text((72, 72), "Q5. Evaluate whether Binary Search is suitable. [5 Marks, L5]")
            page.insert_text((72, 96), "--- End of Assignment ---")
            document.save(pdf_path)
            document.close()

            payload = json.loads(convert_assessment(PdfJob(pdf_path, "unspecified", "unspecified"), root / "output").read_text(encoding="utf-8"))

            self.assertEqual(payload["questions"][0]["content"], "Evaluate whether Binary Search is suitable.")

    def test_extracts_paper_code_into_assessment_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf_path = root / "assignment.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text((72, 72), "Paper Code: DS-ASSIGN-105")
            page.insert_text((72, 96), "Q1. Explain binary search. [5 Marks, L2]")
            document.save(pdf_path)
            document.close()

            payload = json.loads(convert_assessment(PdfJob(pdf_path, "unspecified", "unspecified"), root / "output").read_text(encoding="utf-8"))

            self.assertEqual(payload["metadata"]["paper_code"], "DS-ASSIGN-105")

    def test_selectable_text_is_preserved_without_a_diagram_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf_path = root / "diagram.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text((72, 72), "Q1. Evaluate the expression shown below.")
            page.draw_rect(pymupdf.Rect(72, 100, 300, 220), fill=(0, 0, 0))
            document.save(pdf_path)
            document.close()

            job = PdfJob(pdf_path, "unspecified", "unspecified")
            json_path = convert_assessment(job, root / "output")
            payload = json.loads(json_path.read_text(encoding="utf-8"))

            question = payload["questions"][0]
            self.assertEqual(question["content"], "Evaluate the expression shown below.")
            self.assertEqual(question["path"], [])

    def test_image_only_question_becomes_a_relative_asset_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf_path = root / "image_only.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text((72, 72), "Q1.")
            page.draw_rect(pymupdf.Rect(72, 100, 300, 220), fill=(0, 0, 0))
            document.save(pdf_path)
            document.close()

            job = PdfJob(pdf_path, "unspecified", "unspecified")
            json_path = convert_assessment(job, root / "output")
            payload = json.loads(json_path.read_text(encoding="utf-8"))

            question = payload["questions"][0]
            self.assertEqual(question["content"], "")
            self.assertTrue(question["path"])
            asset_path = Path(temp) / "output" / question["path"][0]
            self.assertTrue(asset_path.is_file())

    def test_from_directory_matches_direct_extraction_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()
            pdf_path = input_dir / "assignment.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text((72, 72), "Q1. Define a data structure.")
            document.save(pdf_path)
            document.close()

            direct_result = extract_assessments(input_dir, output_dir)
            directory_result = extract_assessments_from_directory(input_dir, ["assignment.pdf"])

            self.assertEqual(set(direct_result), set(directory_result))
            direct_entry, directory_entry = direct_result["results"][0], directory_result["results"][0]
            self.assertEqual(set(direct_entry), set(directory_entry))
            self.assertEqual(direct_entry["data"], directory_entry["data"])
            # The directory variant does not leave its transient JSON behind.
            self.assertFalse((input_dir / directory_entry["json_path"]).exists())
            self.assertTrue((output_dir / direct_entry["json_path"]).exists())


if __name__ == "__main__":
    unittest.main()
