"""Tests for MCQ paper-level metadata."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pymupdf

from utils.question_extractor.engine import convert_pdf
from utils.question_extractor.folder_scanner import PdfJob


class McqMetadataTests(unittest.TestCase):
    def test_writes_total_time_minutes_to_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf_path = root / "mcq.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text((72, 72), "Paper Code: DS-MCQ-101")
            page.insert_text((72, 96), "Total Time: 45 Minutes")
            page.insert_text((72, 120), "Q1. Select the correct answer.")
            page.insert_text((72, 144), "A) One")
            page.insert_text((72, 168), "B) Two")
            document.save(pdf_path)
            document.close()

            payload = json.loads(convert_pdf(PdfJob(pdf_path, "unspecified", "unspecified"), root / "output").read_text(encoding="utf-8"))

            self.assertEqual(payload["metadata"], {"paper_code": "DS-MCQ-101", "total_time_minutes": 45.0})


if __name__ == "__main__":
    unittest.main()
