from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from utils.summarizer.output_writer import save_summary_output


class SummaryOutputTests(unittest.TestCase):
    def test_writes_a_summary_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = save_summary_output({"unit_1": "Short summary"}, Path(temporary_directory))
            self.assertTrue(output_path.exists())
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), {"summaries": {"unit_1": "Short summary"}})
