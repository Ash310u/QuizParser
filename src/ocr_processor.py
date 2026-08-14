"""OCR fallback, used only when a page lacks usable digital text."""

from __future__ import annotations

import io

import fitz
from PIL import Image

from .pdf_reader import TextLine


def ocr_page(page: fitz.Page, page_number: int, scale: float = 2.5) -> list[TextLine]:
    try:
        import pytesseract
    except ImportError as exc:  # pragma: no cover - depends on installation
        raise RuntimeError("pytesseract is not installed; install requirements.txt") from exc

    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
    try:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config="--psm 6")
    except pytesseract.TesseractNotFoundError as exc:  # pragma: no cover - system dependency
        raise RuntimeError("Tesseract was required for a scanned page but was not found on PATH") from exc

    groups: dict[tuple[int, int, int], list[int]] = {}
    for index, value in enumerate(data["text"]):
        if value.strip():
            key = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
            groups.setdefault(key, []).append(index)
    lines: list[TextLine] = []
    for indexes in groups.values():
        words = [data["text"][index].strip() for index in indexes]
        x0 = min(data["left"][index] for index in indexes) / scale
        y0 = min(data["top"][index] for index in indexes) / scale
        x1 = max(data["left"][index] + data["width"][index] for index in indexes) / scale
        y1 = max(data["top"][index] + data["height"][index] for index in indexes) / scale
        lines.append(TextLine(page_number, " ".join(words), fitz.Rect(x0, y0, x1, y1), "ocr"))
    return sorted(lines, key=lambda line: (line.rect.y0, line.rect.x0))
