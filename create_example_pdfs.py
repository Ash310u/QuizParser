"""Create representative MCQ and assessment PDFs for extractor testing."""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


INPUT_DIRECTORY = Path(__file__).parent / "input"
FONT_DIRECTORY = Path("/usr/share/fonts/liberation")


def register_fonts() -> None:
    """Embed fonts so fixtures render consistently in PDF viewers."""
    pdfmetrics.registerFont(TTFont("FixtureSans", str(FONT_DIRECTORY / "LiberationSans-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("FixtureSans-Bold", str(FONT_DIRECTORY / "LiberationSans-Bold.ttf")))


def build_mcq_pdf(destination: Path) -> None:
    styles = getSampleStyleSheet()
    styles["Title"].fontName = "FixtureSans-Bold"
    styles["Title"].fontSize = 20
    styles["BodyText"].fontName = "FixtureSans"
    styles["BodyText"].fontSize = 11
    styles["BodyText"].leading = 16
    story = [
        Paragraph("Data Structures - Multiple Choice Assessment", styles["Title"]),
        Spacer(1, 0.18 * inch),
        Paragraph("Assessment Type: MCQ", styles["BodyText"]),
        Paragraph("Paper Code: DS-MCQ-101", styles["BodyText"]),
        Paragraph("Total Time: 45 Minutes", styles["BodyText"]),
        Paragraph("Total Marks: 10", styles["BodyText"]),
        Spacer(1, 0.28 * inch),
        Paragraph("Q1. Which data structure follows the Last In, First Out principle?", styles["BodyText"]),
        Paragraph("A) Queue", styles["BodyText"]),
        Paragraph("B) Stack", styles["BodyText"]),
        Paragraph("C) Linked List", styles["BodyText"]),
        Paragraph("D) Tree", styles["BodyText"]),
        Spacer(1, 0.18 * inch),
        Paragraph("Q2. What is the average-case time complexity of Binary Search?", styles["BodyText"]),
        Paragraph("A) O(1)", styles["BodyText"]),
        Paragraph("B) O(log n)", styles["BodyText"]),
        Paragraph("C) O(n)", styles["BodyText"]),
        Paragraph("D) O(n squared)", styles["BodyText"]),
    ]
    SimpleDocTemplate(str(destination), pagesize=A4, leftMargin=0.8 * inch, rightMargin=0.8 * inch).build(story)


def build_assignment_pdf(destination: Path) -> None:
    styles = getSampleStyleSheet()
    styles["Title"].fontName = "FixtureSans-Bold"
    styles["Title"].fontSize = 20
    styles["BodyText"].fontName = "FixtureSans"
    styles["BodyText"].fontSize = 11
    styles["BodyText"].leading = 16
    styles["Heading3"].fontName = "FixtureSans-Bold"
    story = [
        Paragraph("Unit 5 Assignment - Searching Algorithms", styles["Title"]),
        Spacer(1, 0.28 * inch),
        Paragraph("Paper Code: DS-ASSIGN-105", styles["BodyText"]),
        Spacer(1, 0.12 * inch),
        Paragraph("Q1. Explain the difference between linear search and binary search. [5 Marks, L2]", styles["BodyText"]),
        Spacer(1, 0.18 * inch),
        Paragraph(
            "Q2. A system repeatedly searches a dataset that has new values inserted every few seconds. "
            "Evaluate whether Binary Search is suitable for this scenario, and justify a better alternative if not. "
            "[5 Marks, L5]",
            styles["BodyText"],
        ),
        Spacer(1, 0.35 * inch),
        Paragraph("--- End of Assignment ---", styles["Heading3"]),
    ]
    SimpleDocTemplate(str(destination), pagesize=A4, leftMargin=0.8 * inch, rightMargin=0.8 * inch).build(story)


def main() -> None:
    register_fonts()
    INPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    build_mcq_pdf(INPUT_DIRECTORY / "sample_mcq_with_total_time.pdf")
    build_assignment_pdf(INPUT_DIRECTORY / "sample_assignment_with_end_marker.pdf")


if __name__ == "__main__":
    main()
