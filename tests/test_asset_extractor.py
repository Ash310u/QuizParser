"""Regression tests for vector figures in otherwise styled PDF pages."""

from __future__ import annotations

import unittest

import pymupdf as fitz

from utils.question_extractor.asset_extractor import find_asset_regions


class AssetExtractorTests(unittest.TestCase):
    def test_keeps_nested_vector_figure_when_page_has_background_and_card(self) -> None:
        document = fitz.open()
        page = document.new_page(width=600, height=800)
        page.draw_rect(page.rect, fill=(1, 1, 1), color=None)
        page.draw_rect(fitz.Rect(50, 100, 550, 650), fill=(0.988, 0.988, 0.988), color=None)
        figure = fitz.Rect(70, 180, 530, 360)
        page.draw_rect(figure, fill=(1, 1, 1), color=(0.8, 0.8, 0.8))
        page.draw_rect(fitz.Rect(240, 220, 360, 290), color=(0, 0, 0))

        regions = find_asset_regions(page, 1)

        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0].kind, "diagram")
        self.assertEqual(regions[0].rect, figure)
        document.close()


if __name__ == "__main__":
    unittest.main()
