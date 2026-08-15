"""Run the existing PDF-to-question JSON converter for Flask requests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from utils.question_extractor.engine import convert_pdf
from utils.question_extractor.folder_scanner import PdfJob, scan_pdfs


def extract_questions(
    input_directory: Path,
    output_directory: Path,
    uploaded_files: Iterable[FileStorage] | None = None,
) -> dict:
    """Save optional uploads, process PDFs, and return their generated JSON."""
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
            json_path = convert_pdf(job, output_directory)
            results.append(
                {
                    "source_pdf": job.pdf_path.name,
                    "json_path": json_path.relative_to(output_directory).as_posix(),
                    "data": json.loads(json_path.read_text(encoding="utf-8")),
                }
            )
        except Exception as exc:  # keep the batch behavior of the CLI endpoint
            failures.append({"source_pdf": job.pdf_path.name, "error": str(exc)})

    return {
        "processed_pdfs": len(results),
        "failed_pdfs": len(failures),
        "results": results,
        "failures": failures,
    }
