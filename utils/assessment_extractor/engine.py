"""Batch assessment PDF to JSON conversion.

Reuses the question extractor's coordinate-aware text/asset pipeline (PDF
reading, OCR fallback, question-start detection, and asset cropping) since
locating "Q<n>" questions and their diagrams is identical work. Assessment
questions are typically free-response rather than multiple-choice, so this
module produces one JSON record per question with its marks and a Bloom's
Taxonomy cognitive level (bt_level) instead of options/answer. bt_level is
read directly from the source PDF when it labels a question (e.g.
"[2 Marks, L1]"); unlabelled questions fall back to the classifier.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from utils.question_extractor.asset_extractor import AssetRegion, find_asset_regions
from utils.question_extractor.content_builder import Section, build_section, render_and_assign_assets
from utils.question_extractor.folder_scanner import PdfJob, output_directory, scan_pdfs
from utils.question_extractor.ocr_processor import ocr_page
from utils.question_extractor.pdf_reader import TextLine, extract_page, has_usable_text, open_pdf
from utils.question_extractor.question_detector import split_question_lines
from utils.question_extractor.metadata_detector import extract_paper_code

from .bt_classifier import classify_bt_level
from .json_writer import write_paper
from .marks_detector import extract_marks
from .models import AssessmentPaper, AssessmentQuestion
from utils.question_extractor.models import PaperMetadata
from .validator import confidence_score, validate_question

LOG = logging.getLogger("assessment_converter")


def _question_text(question_lines: list[TextLine]) -> str:
    """Return selectable assessment text without suppressing it for visuals."""
    return re.sub(r"\s+", " ", " ".join(line.text for line in question_lines if line.text)).strip()


def _collect_lines_and_regions(
    pdf_path: Path,
) -> tuple[list[TextLine], list[AssetRegion], list[str], object, list[TextLine]]:
    document = open_pdf(pdf_path)
    lines: list[TextLine] = []
    metadata_lines: list[TextLine] = []
    regions: list[AssetRegion] = []
    warnings: list[str] = []
    for page_number, page in enumerate(document, start=1):
        data = extract_page(page, page_number)
        page_lines: list[TextLine]
        if not has_usable_text(data):
            try:
                ocr_lines = ocr_page(page, page_number)
            except RuntimeError as exc:
                warnings.append(f"Page {page_number}: {exc}")
                ocr_lines = []
            if ocr_lines:
                page_lines = ocr_lines
                warnings.append(f"Page {page_number}: used OCR because digital text was not usable.")
            else:
                page_lines = data.lines
        else:
            page_lines = data.lines
        metadata_lines.extend(page_lines)
        lines.extend(
            line for line in page_lines
            if line.rect.y0 >= data.height * 0.04 and line.rect.y1 <= data.height * 0.95
        )
        # Decorative headers and footers frequently contain lines, rectangles,
        # and logos that are not part of a question.
        regions.extend(
            region for region in find_asset_regions(page, page_number)
            if region.rect.y1 > data.height * 0.12 and region.rect.y0 < data.height * 0.95
        )
    return lines, regions, warnings, document, metadata_lines


def convert_assessment(job: PdfJob, output_root: Path) -> Path:
    destination_dir = output_directory(job, output_root)
    json_path = destination_dir / f"{job.pdf_path.stem}.json"
    assets_dir = destination_dir / f"{job.pdf_path.stem}_assets"
    assets_relative_dir = Path(f"{job.pdf_path.stem}_assets")
    # Each PDF owns an asset directory, even if every question is text-only.
    assets_dir.mkdir(parents=True, exist_ok=True)
    for stale_asset in assets_dir.glob("*.png"):
        stale_asset.unlink()
    lines, all_regions, paper_warnings, document, metadata_lines = _collect_lines_and_regions(job.pdf_path)
    try:
        questions: list[AssessmentQuestion] = []
        grouped = split_question_lines(lines)
        regions_by_question: dict[int, list[AssetRegion]] = defaultdict(list)
        for region in all_regions:
            candidates: list[tuple[float, int]] = []
            for index, (_, _, candidate_lines) in enumerate(grouped):
                page_lines = [line for line in candidate_lines if line.page_number == region.page_number]
                if not page_lines:
                    continue
                top = min(line.rect.y0 for line in page_lines)
                bottom = max(line.rect.y1 for line in page_lines)
                distance = 0.0 if top <= region.rect.y0 <= bottom else min(abs(region.rect.y0 - bottom), abs(top - region.rect.y1))
                candidates.append((distance, index))
            if candidates:
                _, owner = min(candidates)
                regions_by_question[owner].append(region)
            else:
                LOG.warning("%s: visual region on page %s could not be associated with a question", job.pdf_path, region.page_number)
        for index, (number, page_number, question_lines) in enumerate(grouped):
            content = _question_text(question_lines)
            paths: list[str] = []
            # Assessments are text-first. Only image-only questions need a
            # crop; otherwise a false drawing region can suppress valid text.
            if not content:
                stem = Section("question", None, question_lines)
                assignments = render_and_assign_assets(
                    document,
                    regions_by_question[index],
                    [stem],
                    assets_dir,
                    assets_relative_dir,
                    number,
                )
                _, paths = build_section(stem, assignments[id(stem)])
            content, marks, explicit_level = extract_marks(content)
            bt_level = explicit_level or classify_bt_level(content)
            question = AssessmentQuestion(
                number=number,
                page_number=page_number,
                content=content,
                path=paths,
                marks=marks,
                bt_level=bt_level,
            )
            validation_messages = validate_question(question, destination_dir)
            question.confidence_score = confidence_score(
                question,
                validation_messages,
                used_ocr=any("used OCR" in warning for warning in paper_warnings),
            )
            for warning in [*paper_warnings, *validation_messages]:
                LOG.warning("%s, question %s: %s", job.pdf_path.name, number, warning)
            questions.append(question)
        if not grouped:
            LOG.warning("%s: no question starts detected", job.pdf_path)
        paper = AssessmentPaper(
            subject=job.subject,
            semester=job.semester,
            source_pdf=job.pdf_path.name,
            metadata=PaperMetadata(paper_code=extract_paper_code(metadata_lines)),
            questions=questions,
        )
        write_paper(paper, json_path)
        return json_path
    finally:
        document.close()


def _resolve_pdf_path(directory: Path, filename: str) -> Path | None:
    """Return the existing PDF at ``directory/filename``, or ``None`` if unsafe/missing."""
    safe_name = secure_filename(filename or "")
    if not safe_name or Path(safe_name).suffix.lower() != ".pdf":
        return None
    candidate = (directory / safe_name).resolve()
    try:
        candidate.relative_to(directory.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def extract_assessments_from_directory(directory: Path, filenames: Iterable[str]) -> dict:
    """Extract PDFs already saved under ``directory``; assets are saved alongside them,
    but the generated JSON file itself is not kept on disk, only returned.

    Each result carries the same ``source_pdf``/``json_path``/``data`` shape as
    :func:`extract_assessments`, so callers get an identical response whether a
    PDF was uploaded directly or already sat in a directory."""
    results: list[dict] = []
    failures: list[dict] = []
    for filename in filenames:
        pdf_path = _resolve_pdf_path(directory, filename)
        if pdf_path is None:
            failures.append({"source_pdf": filename, "error": "File not found in directory"})
            continue
        job = PdfJob(pdf_path, "unspecified", "unspecified")
        try:
            json_path = convert_assessment(job, directory)
            data = json.loads(json_path.read_text(encoding="utf-8"))
            relative_json_path = json_path.relative_to(directory).as_posix()
            json_path.unlink(missing_ok=True)
            results.append({"source_pdf": job.pdf_path.name, "json_path": relative_json_path, "data": data})
        except Exception as exc:
            failures.append({"source_pdf": job.pdf_path.name, "error": str(exc)})
    return {"processed_pdfs": len(results), "failed_pdfs": len(failures), "results": results, "failures": failures}


def extract_assessments(input_directory: Path, output_directory: Path, uploaded_files: Iterable[FileStorage] | None = None) -> dict:
    """Save optional uploads and extract all available assessment PDFs."""
    input_directory.mkdir(parents=True, exist_ok=True)
    output_directory.mkdir(parents=True, exist_ok=True)

    jobs: list[PdfJob]
    if uploaded_files:
        jobs = []
        for uploaded_file in uploaded_files:
            filename = secure_filename(uploaded_file.filename or "")
            if not filename or Path(filename).suffix.lower() != ".pdf":
                continue
            destination = input_directory / filename
            uploaded_file.save(destination)
            jobs.append(PdfJob(destination, "unspecified", "unspecified"))
    else:
        jobs = scan_pdfs(input_directory)

    results: list[dict] = []
    failures: list[dict] = []
    for job in jobs:
        try:
            json_path = convert_assessment(job, output_directory)
            results.append(
                {
                    "source_pdf": job.pdf_path.name,
                    "json_path": json_path.relative_to(output_directory).as_posix(),
                    "data": json.loads(json_path.read_text(encoding="utf-8")),
                }
            )
        except Exception as exc:
            failures.append({"source_pdf": job.pdf_path.name, "error": str(exc)})

    return {"processed_pdfs": len(results), "failed_pdfs": len(failures), "results": results, "failures": failures}
