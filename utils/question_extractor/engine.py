"""Core batch PDF MCQ conversion workflow."""

from __future__ import annotations

import argparse
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

from .answer_detector import is_answer_line, resolve_answer_labels, split_answer_lines
from .asset_extractor import AssetRegion, find_asset_regions
from .content_builder import Section, build_section, render_and_assign_assets
from .folder_scanner import PdfJob, output_directory, scan_pdfs
from .json_writer import write_paper
from .label_normalizer import alphabetic_label
from .models import Option, Paper, Question
from .ocr_processor import ocr_page
from .option_detector import split_options
from .pdf_reader import TextLine, extract_page, has_usable_text, open_pdf
from .question_detector import split_question_lines
from .validator import confidence_score, validate_question

LOG = logging.getLogger("pdf_mcq_converter")
IMAGE_CHOICE_PROMPT = re.compile(
    r"\b(?:which|choose|select|identify|pick)\b.*\b(?:image|diagram|figure|symbol|shape|option)\b",
    re.IGNORECASE,
)


def _collect_lines_and_regions(pdf_path: Path) -> tuple[list[TextLine], list[AssetRegion], list[str], object]:
    document = open_pdf(pdf_path)
    lines: list[TextLine] = []
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
    return lines, regions, warnings, document


def convert_pdf(job: PdfJob, output_root: Path) -> Path:
    destination_dir = output_directory(job, output_root)
    json_path = destination_dir / f"{job.pdf_path.stem}.json"
    assets_dir = destination_dir / f"{job.pdf_path.stem}_assets"
    assets_relative_dir = Path(f"{job.pdf_path.stem}_assets")
    # Each PDF owns an asset directory, even if every question is text-only.
    assets_dir.mkdir(parents=True, exist_ok=True)
    for stale_asset in assets_dir.glob("*.png"):
        stale_asset.unlink()
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
            answer_line_rects = [line.rect for line in question_lines if is_answer_line(line.text)]
            question_lines, answer_text = split_answer_lines(question_lines)
            stem_lines, option_groups = split_options(question_lines)
            # Answer banners are page decorations for the key, not question or
            # option imagery. Do not save them as assets.
            question_regions = [
                region for region in regions_by_question[index]
                if not any(region.rect.contains(answer_rect) for answer_rect in answer_line_rects)
            ]
            # When no textual labels or choices exist, a prompt that explicitly
            # asks the reader to choose a visual item can still be represented
            # as numbered options. Each detected visual region becomes one
            # choice; ordinary question diagrams are not guessed as options.
            prompt = " ".join(line.text for line in stem_lines)
            if not option_groups and len(question_regions) >= 2 and IMAGE_CHOICE_PROMPT.search(prompt):
                option_groups = [
                    (str(position), [TextLine(region.page_number, "", region.rect, "asset")])
                    for position, region in enumerate(sorted(question_regions, key=lambda item: (item.page_number, item.rect.y0, item.rect.x0)), start=1)
                ]
            stem = Section("question", None, stem_lines)
            option_sections = [Section("option", label, option_lines) for label, option_lines in option_groups]
            sections = [stem, *option_sections]
            assignments = render_and_assign_assets(document, question_regions, sections, assets_dir, assets_relative_dir, number)
            options = []
            source_labels = [section.option_label or "?" for section in option_sections]
            source_duplicate_count = len(source_labels) - len({label.casefold() for label in source_labels})
            for option_index, section in enumerate(option_sections):
                content, paths = build_section(section, assignments[id(section)])
                options.append(Option(label=alphabetic_label(option_index), content=content, path=paths))
            content, paths = build_section(stem, assignments[id(stem)])
            answer_labels = resolve_answer_labels(answer_text, options, source_labels)
            question = Question(
                number=number,
                page_number=page_number,
                content=content,
                path=paths,
                options=options,
                answer=answer_labels,
            )
            validation_messages = validate_question(question, destination_dir)
            question.confidence_score = confidence_score(
                question,
                validation_messages,
                answer_key_was_present=answer_text is not None,
                used_ocr=any("used OCR" in warning for warning in paper_warnings),
                source_duplicate_count=source_duplicate_count,
            )
            for warning in [*paper_warnings, *validation_messages]:
                LOG.warning("%s, question %s: %s", job.pdf_path.name, number, warning)
            questions.append(question)
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
