"""Find PDFs placed directly in the simple input directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PdfJob:
    pdf_path: Path
    subject: str
    semester: str


def scan_pdfs(input_root: Path) -> list[PdfJob]:
    """Return every PDF placed directly in ``input_root`` in a stable order.

    The batch input has no required subject or semester subfolders. Those
    required JSON fields receive a neutral value rather than being inferred
    from a machine-specific file path.
    """
    if not input_root.exists():
        return []
    return [
        PdfJob(pdf_path=pdf_path, subject="unspecified", semester="unspecified")
        for pdf_path in sorted(input_root.iterdir())
        if pdf_path.is_file() and pdf_path.suffix.lower() == ".pdf"
    ]


def output_directory(job: PdfJob, output_root: Path) -> Path:
    return output_root
