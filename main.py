"""Command-line entry point for batch PDF MCQ conversion."""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path

from src.asset_extractor import AssetRegion, find_asset_regions
from src.content_builder import Section, build_content, render_and_assign_assets
from src.folder_scanner import PdfJob, output_directory, scan_pdfs
from src.models import Option, Paper, Question
from src.ocr_processor import ocr_page
from src.option_detector import split_options
from src.pdf_reader import TextLine, extract_page, has_usable_text, open_pdf
from src.question_detector import split_question_lines
from src.validator import validate_question
from src.json_writer import write_paper

LOG = logging.getLogger("pdf_mcq_converter")


def _collect_lines_and_regions(pdf_path: Path) -> tuple[list[TextLine], list[AssetRegion], list[str], object]:
    document = open_pdf(pdf_path)
    lines: list[TextLine] = []
    regions: list[AssetRegion] = []
    warnings: list[str] = []
    for page_number, page in enumerate(document, start=1):
        data = extract_page(page, page_number)
        if not has_usable_text(data):
            try:
                ocr_lines = ocr_page(page, page_number)
            except RuntimeError as exc:
                warnings.append(f"Page {page_number}: {exc}")
                ocr_lines = []
            if ocr_lines:
                lines.extend(ocr_lines)
                warnings.append(f"Page {page_number}: used OCR because digital text was not usable.")
            else:
                lines.extend(data.lines)
        else:
            lines.extend(data.lines)
        regions.extend(find_asset_regions(page, page_number))
    return lines, regions, warnings, document


def convert_pdf(job: PdfJob, output_root: Path) -> Path:
    destination_dir = output_directory(job, output_root)
    json_path = destination_dir / f"{job.pdf_path.stem}.json"
    assets_dir = destination_dir / f"{job.pdf_path.stem}_assets"
    assets_relative_dir = Path(f"{job.pdf_path.stem}_assets")
    # Each PDF owns an asset directory, even if every question is text-only.
    assets_dir.mkdir(parents=True, exist_ok=True)
    lines, all_regions, paper_warnings, document = _collect_lines_and_regions(job.pdf_path)
    try:
        questions: list[Question] = []
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
            stem_lines, option_groups = split_options(question_lines)
            stem = Section("question", None, stem_lines)
            option_sections = [Section("option", label, option_lines) for label, option_lines in option_groups]
            sections = [stem, *option_sections]
            question_regions = regions_by_question[index]
            assignments = render_and_assign_assets(document, question_regions, sections, assets_dir, assets_relative_dir, number)
            options = [
                Option(label=section.option_label or "?", content=build_content(section, assignments[id(section)]))
                for section in option_sections
            ]
            question = Question(number=number, page_number=page_number, content=build_content(stem, assignments[id(stem)]), options=options, warnings=list(paper_warnings))
            questions.append(validate_question(question, destination_dir))
        if not grouped:
            LOG.warning("%s: no question starts detected", job.pdf_path)
        paper = Paper(subject=job.subject, semester=job.semester, source_pdf=job.pdf_path.name, questions=questions)
        write_paper(paper, json_path)
        return json_path
    finally:
        document.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert PDFs in one input folder to JSON with PNG assets.")
    parser.add_argument("--input", type=Path, default=Path("input"), help="Directory containing PDF files (default: input)")
    parser.add_argument("--output", type=Path, default=Path("output"), help="Output root (default: output)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    jobs = scan_pdfs(args.input)
    if not jobs:
        LOG.warning("No PDFs found under %s", args.input)
        print("Summary: processed PDFs: 0 | failed PDFs: 0 | generated JSON files: 0")
        return 0
    completed: list[Path] = []
    failed = 0
    for job in jobs:
        try:
            completed.append(convert_pdf(job, args.output))
            LOG.info("Converted %s", job.pdf_path)
        except Exception:
            failed += 1
            LOG.exception("Failed to convert %s", job.pdf_path)
    print(f"Summary: processed PDFs: {len(completed)} | failed PDFs: {failed} | generated JSON files: {len(completed)}")
    for path in completed:
        print(f"  {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
