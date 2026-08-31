"""Find visual PDF regions and render them as relative PNG assets."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import pymupdf as fitz
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


def _is_page_background(rect: fitz.Rect, page: fitz.Page) -> bool:
    """Return whether a drawing is the page-sized fill, not page content."""
    return rect.get_area() >= page.rect.get_area() * 0.95


def _is_question_card(drawing: dict, rect: fitz.Rect, page: fitz.Page) -> bool:
    """Ignore the pale rounded rectangles used to lay out question cards.

    WeasyPrint emits each card as a drawing. Treating those containers as
    diagrams produces page-sized crops and can hide the smaller white figure
    panels nested inside them.
    """
    fill = drawing.get("fill")
    if fill is None or rect.width < page.rect.width * 0.7:
        return False
    return all(0.96 <= component < 1.0 for component in fill)


def _same_bounds(left: fitz.Rect, right: fitz.Rect) -> bool:
    return all(abs(a - b) < 0.1 for a, b in zip(left, right))


def _is_layout_divider(rect: fitz.Rect, page: fitz.Page) -> bool:
    """Exclude full-width rules used to separate a question from its answer."""
    return rect.width >= page.rect.width * 0.7 and rect.height <= page.rect.height * 0.03


def _is_decorative_header(drawing: dict, rect: fitz.Rect, page: fitz.Page) -> bool:
    """Exclude a wide, coloured banner at the top of the page."""
    fill = drawing.get("fill")
    return (
        fill is not None
        and rect.width >= page.rect.width * 0.7
        and rect.y0 <= page.rect.height * 0.12
        and rect.height <= page.rect.height * 0.12
        and max(fill) - min(fill) >= 0.15
    )


def find_asset_regions(page: fitz.Page, page_number: int) -> list[AssetRegion]:
    """Locate embedded bitmaps and large vector-drawing bounds.

    OpenCV helps reject tiny page-rendering noise; vector drawings cover common
    diagrams and equations that are not exposed as embedded bitmap images.
    """
    regions: list[AssetRegion] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") == 1:
            regions.append(AssetRegion(page_number, fitz.Rect(block["bbox"]), "image"))
    drawings = page.get_drawings()
    # A card is often emitted twice: a pale filled rectangle and a separate
    # rounded border. Remember the filled rectangle so its border is excluded
    # as well.
    card_bounds = [
        drawing["rect"]
        for drawing in drawings
        if drawing.get("rect") and _is_question_card(drawing, drawing["rect"], page)
    ]
    for drawing in drawings:
        rect = drawing.get("rect")
        if (
            rect
            and rect.get_area() >= 900
            and not _is_page_background(rect, page)
            and not _is_question_card(drawing, rect, page)
            and not any(_same_bounds(rect, card) for card in card_bounds)
            and not _is_layout_divider(rect, page)
            and not _is_decorative_header(drawing, rect, page)
        ):
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