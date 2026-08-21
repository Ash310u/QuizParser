"""Convert assessment PDFs to the compact question-extractor JSON shape."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Iterable

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from utils.question_extractor.content_builder import Section, build_section, render_and_assign_assets
from utils.question_extractor.engine import _collect_lines_and_regions
from utils.question_extractor.question_detector import split_question_lines

from .models import AssessmentPaper, AssessmentQuestion

LOG = logging.getLogger("pdf_assessment_converter")


def _question_text(question_lines: list[Any]) -> str:
    """Return selectable assessment text without suppressing it for visuals."""
    return re.sub(r"\s+", " ", " ".join(line.text for line in question_lines if line.text)).strip()


def convert_assessment(pdf_path: Path, output_directory: Path) -> Path:
    """Extract one assessment PDF to compact question JSON and cropped assets."""
    output_directory.mkdir(parents=True, exist_ok=True)
    assets_dir = output_directory / f"{pdf_path.stem}_assessment_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for stale_asset in assets_dir.glob("*.png"):
        stale_asset.unlink()

    lines, all_regions, warnings, document = _collect_lines_and_regions(pdf_path)
    try:
        grouped = split_question_lines(lines)
        regions_by_question: dict[int, list[Any]] = {index: [] for index in range(len(grouped))}
        for region in all_regions:
            candidates: list[tuple[float, int]] = []
            for index, (_, _, question_lines) in enumerate(grouped):
                page_lines = [line for line in question_lines if line.page_number == region.page_number]
                if not page_lines:
                    continue
                top = min(line.rect.y0 for line in page_lines)
                bottom = max(line.rect.y1 for line in page_lines)
                distance = 0.0 if top <= region.rect.y0 <= bottom else min(
                    abs(region.rect.y0 - bottom), abs(top - region.rect.y1)
                )
                candidates.append((distance, index))
            if candidates:
                _, owner = min(candidates)
                regions_by_question[owner].append(region)
            else:
                LOG.warning("%s: visual region on page %s could not be associated with a question", pdf_path, region.page_number)

        questions: list[AssessmentQuestion] = []
        assets_relative_dir = Path(f"{pdf_path.stem}_assessment_assets")
        for index, (number, page_number, question_lines) in enumerate(grouped):
            content = _question_text(question_lines)
            paths: list[str] = []
            # Assessments are text-first. A visual asset is useful only when
            # the question has no selectable text at all; otherwise a PDF
            # layout drawing can never replace the question's text.
            if not content:
                section = Section("question", None, question_lines)
                assignments = render_and_assign_assets(
                    document, regions_by_question[index], [section], assets_dir, assets_relative_dir, number
                )
                _, paths = build_section(section, assignments[id(section)])
            questions.append(AssessmentQuestion(
                number=number,
                page_number=page_number,
                content=content,
                path=paths,
                confidence_score=1.0 if content or paths else 0.2,
            ))

        for warning in warnings:
            LOG.warning("%s: %s", pdf_path.name, warning)
        paper = AssessmentPaper(subject="unspecified", semester="unspecified", source_pdf=pdf_path.name, questions=questions)
        json_path = output_directory / f"{pdf_path.stem}_assessment.json"
        json_path.write_text(json.dumps(paper.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return json_path
    finally:
        document.close()


def extract_assessments(
    input_directory: Path,
    output_directory: Path,
    uploaded_files: Iterable[FileStorage] | None = None,
) -> dict[str, Any]:
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
