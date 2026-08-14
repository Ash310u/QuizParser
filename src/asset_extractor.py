"""Find visual PDF regions and render them as relative PNG assets."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import fitz
from PIL import Image


@dataclass(frozen=True)
class AssetRegion:
    page_number: int
    rect: fitz.Rect
    kind: str


def _dedupe(regions: list[AssetRegion]) -> list[AssetRegion]:
    kept: list[AssetRegion] = []
    for region in sorted(regions, key=lambda r: (r.page_number, r.rect.y0, r.rect.x0)):
        if region.rect.width < 8 or region.rect.height < 8:
            continue
        if any(region.page_number == prior.page_number and (region.rect & prior.rect).get_area() / min(region.rect.get_area(), prior.rect.get_area()) > .8 for prior in kept):
            continue
        kept.append(region)
    return kept


def find_asset_regions(page: fitz.Page, page_number: int) -> list[AssetRegion]:
    """Locate embedded bitmaps and large vector-drawing bounds.

    OpenCV helps reject tiny page-rendering noise; vector drawings cover common
    diagrams and equations that are not exposed as embedded bitmap images.
    """
    regions: list[AssetRegion] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") == 1:
            regions.append(AssetRegion(page_number, fitz.Rect(block["bbox"]), "image"))
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect and rect.get_area() >= 900:
            regions.append(AssetRegion(page_number, fitz.Rect(rect), "diagram"))

    # Detect only substantial isolated ink components in a low-resolution raster.
    # Embedded images and vector drawings remain available if OpenCV was omitted
    # from a development install; `requirements.txt` installs it for full support.
    try:
        import cv2
        import numpy as np
    except ImportError:
        cv2 = None
    if cv2 is not None:
        pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), colorspace=fitz.csGRAY, alpha=False)
        bitmap = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
        binary = cv2.threshold(bitmap, 220, 255, cv2.THRESH_BINARY_INV)[1]
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            if width * height >= 5000 and width >= 80 and height >= 50:
                rect = fitz.Rect(x, y, x + width, y + height)
                regions.append(AssetRegion(page_number, rect, "graphic"))
    return _dedupe(regions)


def save_crop(page: fitz.Page, rect: fitz.Rect, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clipped = rect & page.rect
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clipped, alpha=False)
    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
    image.save(output_path, format="PNG")
