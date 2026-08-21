from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pymupdf

from utils.assessment_extractor.engine import convert_assessment


class AssessmentExtractorTests(unittest.TestCase):
    def test_writes_assessment_questions_without_options_answers_or_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf_path = root / "assignment.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text((72, 72), "Assignment Sample")
            page.insert_text((72, 96), "Course: B.Tech | Subject: Data Structures | Sem: X")
            page.insert_text((72, 132), "Unit 1")
            page.insert_text((72, 156), "Topics: Arrays | Total Marks: 20")
            page.insert_text((72, 192), "Q1. Define a data structure. [2 Marks, L1]")
            page.insert_text((72, 216), "Q2. Explain arrays. [3 Marks, L2]")
            page.draw_line((72, 240), (300, 240))
            document.save(pdf_path)
            document.close()

            json_path = convert_assessment(pdf_path, root / "output")
            payload = json.loads(json_path.read_text(encoding="utf-8"))

            self.assertEqual(set(payload), {"subject", "semester", "source_pdf", "questions"})
            self.assertEqual(len(payload["questions"]), 2)
            question = payload["questions"][0]
            self.assertEqual(question["content"], "Define a data structure. [2 Marks, L1]")
            self.assertEqual(question["path"], [])
            self.assertNotIn("options", question)
            self.assertNotIn("answer", question)
            self.assertNotIn("bbox", question)
            self.assertTrue((root / "output" / "assignment_assessment_assets").is_dir())
