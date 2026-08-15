"""Assessment PDF conversion implementation.

The layout record deliberately does not assume an assignment template: each page
keeps its text spans, embedded images, vector drawings, links, and annotations.
The ``assessment`` view is a best-effort convenience layer for common headings
such as ``Unit 1`` and ``Q1``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

import pymupdf
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


SECTION_RE = re.compile(r"^(?:unit|section|part|module)\s*([\w.-]+)?\s*[:.-]?\s*(.*)$", re.IGNORECASE)
QUESTION_RE = re.compile(r"^(?:question\s*)?q\s*(\d+)\s*[.:)\-]?\s*(.*)$", re.IGNORECASE)
MARKS_RE = re.compile(r"\s*[\[(]\s*(\d+(?:\.\d+)?)\s*marks?\s*(?:[,;|]\s*([A-Za-z]\d+))?\s*[\])]\s*$", re.IGNORECASE)


def _json_value(value: Any) -> Any:
    """Convert PyMuPDF geometry and drawing values to JSON-safe values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, pymupdf.Rect):
        return {"x0": value.x0, "y0": value.y0, "x1": value.x1, "y1": value.y1}
    if isinstance(value, pymupdf.Point):
        return {"x": value.x, "y": value.y}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return str(value)


def _span_record(span: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": span.get("text", ""),
        "bbox": _json_value(span.get("bbox")),
        "font": span.get("font"),
        "font_size": span.get("size"),
        "flags": span.get("flags"),
        "color": span.get("color"),
        "origin": _json_value(span.get("origin")),
    }


def _page_text(page: pymupdf.Page) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return simple reading lines plus full text block/span layout."""
    blocks: list[dict[str, Any]] = []
    lines: list[dict[str, Any]] = []
    for block in page.get_text("dict", sort=True).get("blocks", []):
        if block.get("type") != 0:
            continue
        line_records = []
        for line in block.get("lines", []):
            spans = [_span_record(span) for span in line.get("spans", [])]
            text = "".join(span["text"] for span in spans).strip()
            line_record = {"text": text, "bbox": _json_value(line.get("bbox")), "spans": spans}
            line_records.append(line_record)
            if text:
                lines.append(line_record)
        blocks.append({"type": "text", "bbox": _json_value(block.get("bbox")), "lines": line_records})
    return lines, blocks


def _save_images(page: pymupdf.Page, assets_dir: Path, asset_prefix: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_xrefs: set[int] = set()
    for image_index, image in enumerate(page.get_images(full=True), start=1):
        xref = image[0]
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)
        extracted = page.parent.extract_image(xref)
        extension = extracted.get("ext", "png")
        filename = f"{asset_prefix}_image_{image_index}.{extension}"
        (assets_dir / filename).write_bytes(extracted["image"])
        records.append(
            {
                "xref": xref,
                "path": filename,
                "width": extracted.get("width"),
                "height": extracted.get("height"),
                "colorspace": extracted.get("colorspace"),
                "bits_per_component": extracted.get("bpc"),
            }
        )
    return records


def _parse_metadata(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for part in re.split(r"\s*[|]\s*", text):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        key, value = key.strip(), value.strip()
        if key and value:
            metadata[key.lower().replace(" ", "_")] = value
    return metadata


def _assessment_view(page_lines: list[tuple[int, dict[str, Any]]]) -> dict[str, Any]:
    """Build a conservative section/question view without discarding raw layout."""
    all_text = [line["text"] for _, line in page_lines if line["text"]]
    title = all_text[0] if all_text else ""
    metadata = _parse_metadata(all_text[1]) if len(all_text) > 1 else {}
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    active_question: dict[str, Any] | None = None

    def ensure_section(page_number: int) -> dict[str, Any]:
        nonlocal current
        if current is None:
            current = {"title": "Unsectioned content", "identifier": None, "page_number": page_number, "metadata": {}, "questions": []}
            sections.append(current)
        return current

    # The document title and its conventional metadata line describe the whole
    # assessment; they must not become an ``Unsectioned content`` section.
    first_content_lines = 2 if metadata else 1
    for line_index, (page_number, line) in enumerate(page_lines):
        if line_index < first_content_lines:
            continue
        text = line["text"]
        section_match = SECTION_RE.match(text)
        if section_match and not QUESTION_RE.match(text):
            current = {"title": (section_match.group(2) or text).strip(), "identifier": section_match.group(1), "page_number": page_number, "metadata": {}, "questions": []}
            sections.append(current)
            active_question = None
            continue
        section = ensure_section(page_number)
        if text.lower().startswith(("topics:", "total marks:", "total time:")):
            key, _, value = text.partition(":")
            section["metadata"][key.lower().replace(" ", "_")] = value.strip()
            continue
        question_match = QUESTION_RE.match(text)
        if question_match:
            content = question_match.group(2).strip()
            marks_match = MARKS_RE.search(content)
            marks = float(marks_match.group(1)) if marks_match else None
            level = marks_match.group(2) if marks_match else None
            if marks_match:
                content = content[: marks_match.start()].rstrip()
            active_question = {
                "number": int(question_match.group(1)),
                "page_number": page_number,
                "content": content,
                "marks": marks,
                "learning_level": level,
                "bbox": line["bbox"],
                "source_lines": [text],
            }
            section["questions"].append(active_question)
        elif active_question is not None:
            active_question["content"] = f"{active_question['content']} {text}".strip()
            active_question["source_lines"].append(text)

    return {"title": title, "metadata": metadata, "sections": sections}


def convert_assessment(pdf_path: Path, output_directory: Path) -> Path:
    """Extract one PDF to a standalone JSON file plus relative image assets."""
    output_directory.mkdir(parents=True, exist_ok=True)
    assets_dir = output_directory / f"{pdf_path.stem}_assessment_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open(pdf_path)
    document_metadata = {key: value for key, value in document.metadata.items() if value not in (None, "")}
    table_of_contents = _json_value(document.get_toc(simple=False))
    pages: list[dict[str, Any]] = []
    all_lines: list[tuple[int, dict[str, Any]]] = []
    try:
        for index, page in enumerate(document, start=1):
            lines, text_blocks = _page_text(page)
            all_lines.extend((index, line) for line in lines)
            render_name = f"page_{index}.png"
            page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False).save(assets_dir / render_name)
            drawings = [_json_value(drawing) for drawing in page.get_drawings()]
            annotations = [_json_value(annotation.info) for annotation in (page.annots() or [])]
            pages.append(
                {
                    "page_number": index,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "rotation": page.rotation,
                    "render_path": (assets_dir.name + "/" + render_name),
                    "text_blocks": text_blocks,
                    "images": [
                        {**record, "path": (assets_dir.name + "/" + record["path"])}
                        for record in _save_images(page, assets_dir, f"page_{index}")
                    ],
                    "drawings": drawings,
                    "links": [_json_value(link) for link in page.get_links()],
                    "annotations": annotations,
                }
            )
    finally:
        document.close()
    payload = {
        "schema_version": "1.0",
        "source_pdf": pdf_path.name,
        "document_metadata": document_metadata,
        "table_of_contents": table_of_contents,
        "assessment": _assessment_view(all_lines),
        "pages": pages,
    }
    json_path = output_directory / f"{pdf_path.stem}_assessment.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


def extract_assessments(input_directory: Path, output_directory: Path, uploaded_files: Iterable[FileStorage] | None = None) -> dict[str, Any]:
    """Save optional uploads and extract all available assessment PDFs."""
    input_directory.mkdir(parents=True, exist_ok=True)
    output_directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    if uploaded_files:
        for upload in uploaded_files:
            filename = secure_filename(upload.filename or "")
            if filename and Path(filename).suffix.lower() == ".pdf":
                path = input_directory / filename
                upload.save(path)
                paths.append(path)
    else:
        paths = sorted(path for path in input_directory.iterdir() if path.is_file() and path.suffix.lower() == ".pdf")

    results, failures = [], []
    for path in paths:
        try:
            json_path = convert_assessment(path, output_directory)
            results.append({"source_pdf": path.name, "json_path": json_path.name, "data": json.loads(json_path.read_text(encoding="utf-8"))})
        except Exception as exc:
            failures.append({"source_pdf": path.name, "error": str(exc)})
    return {"processed_pdfs": len(results), "failed_pdfs": len(failures), "results": results, "failures": failures}
