from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pymupdf

from assessment_extractors.service import convert_assessment


class AssessmentExtractorTests(unittest.TestCase):
    def test_preserves_layout_and_extracts_assessment_view(self) -> None:
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

            self.assertEqual(payload["assessment"]["title"], "Assignment Sample")
            self.assertEqual(payload["assessment"]["metadata"]["course"], "B.Tech")
            section = payload["assessment"]["sections"][0]
            self.assertEqual(section["identifier"], "1")
            self.assertEqual(section["questions"][0]["marks"], 2.0)
            self.assertEqual(section["questions"][1]["learning_level"], "L2")
            self.assertTrue(payload["pages"][0]["text_blocks"])
            self.assertTrue(payload["pages"][0]["drawings"])
            self.assertTrue((root / "output" / payload["pages"][0]["render_path"]).exists())
