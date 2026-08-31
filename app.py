"""Simple Flask API for question extraction, assessment extraction, and summarization."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, request

from services.assessment_extractors.service import extract_assessments, extract_assessments_from_directory
from services.question_extractors.service import extract_questions, extract_questions_from_directory
from services.summarize.service import summarize_units


def _parse_directory_payload(payload: object) -> tuple[Path, list[str]] | tuple[None, str]:
    """Validate a ``{"directory": str, "files": [str, ...]}`` body.

    Returns ``(directory_path, filenames)`` on success, or ``(None, error_message)``.
    """
    if not isinstance(payload, dict):
        return None, "Send JSON with 'directory' and 'files'."
    directory = payload.get("directory")
    filenames = payload.get("files")
    if not isinstance(directory, str) or not directory.strip():
        return None, "'directory' must be a non-empty string."
    if not isinstance(filenames, list) or not filenames or not all(isinstance(name, str) for name in filenames):
        return None, "'files' must be a non-empty list of filenames."
    directory_path = Path(directory)
    if not directory_path.is_dir():
        return None, f"Directory not found: {directory}"
    return directory_path, filenames


def create_app() -> Flask:
    app = Flask(__name__)
    input_directory = Path(os.environ.get("QUESTION_INPUT_DIR", "input"))
    output_directory = Path(os.environ.get("QUESTION_OUTPUT_DIR", "output/question_extractor"))
    assessment_input_directory = Path(os.environ.get("ASSESSMENT_INPUT_DIR", "input"))
    assessment_output_directory = Path(os.environ.get("ASSESSMENT_OUTPUT_DIR", "output/assessment_extractor"))

    @app.post("/question-extractor")
    def question_extractor():
        """Convert uploaded PDFs, or every PDF already in the input directory."""
        uploads = [file for file in request.files.getlist("files") if file.filename]
        result = extract_questions(input_directory, output_directory, uploads or None)
        if uploads and result["processed_pdfs"] == 0 and result["failed_pdfs"] == 0:
            return jsonify({"error": "Upload one or more PDF files using the 'files' field."}), 400
        return jsonify(result), 200 if not result["failures"] else 207

    @app.post("/assessment-extractor")
    def assessment_extractor():
        """Convert uploaded PDFs, or every PDF already in the input directory,
        into the same compact question-list JSON shape as /question-extractor,
        with marks and bt_level instead of options/answer."""
        uploads = [file for file in request.files.getlist("files") if file.filename]
        result = extract_assessments(assessment_input_directory, assessment_output_directory, uploads or None)
        if uploads and result["processed_pdfs"] == 0 and result["failed_pdfs"] == 0:
            return jsonify({"error": "Upload one or more PDF files using the 'files' field."}), 400
        return jsonify(result), 200 if not result["failures"] else 207

    @app.post("/question-extractor-from-directory")
    def question_extractor_from_directory():
        """Convert PDFs already saved on disk; only the resulting JSON is returned."""
        directory_path, filenames_or_error = _parse_directory_payload(request.get_json(silent=True))
        if directory_path is None:
            return jsonify({"error": filenames_or_error}), 400
        result = extract_questions_from_directory(directory_path, filenames_or_error)
        return jsonify(result), 200 if not result["failures"] else 207

    @app.post("/assessment-extractor-from-directory")
    def assessment_extractor_from_directory():
        """Extract PDFs already saved on disk; only the resulting JSON is returned."""
        directory_path, filenames_or_error = _parse_directory_payload(request.get_json(silent=True))
        if directory_path is None:
            return jsonify({"error": filenames_or_error}), 400
        result = extract_assessments_from_directory(directory_path, filenames_or_error)
        return jsonify(result), 200 if not result["failures"] else 207

    @app.post("/summarize")
    def summarize():
        """Summarize ``{unit_key: [text, ...]}`` using the existing local model."""
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("units"), dict):
            return jsonify({"error": "Send JSON with a 'units' object: {unit_key: [text, ...]}."}), 400
        units = payload["units"]
        if not all(isinstance(key, str) and isinstance(values, list) and all(isinstance(value, str) for value in values) for key, values in units.items()):
            return jsonify({"error": "Each units value must be a list of strings."}), 400
        word_limit = payload.get("word_limit")
        if word_limit is not None and (not isinstance(word_limit, int) or isinstance(word_limit, bool) or word_limit < 1):
            return jsonify({"error": "word_limit must be a positive integer when provided."}), 400
        try:
            summaries = summarize_units(units, word_limit)
            return jsonify({"summaries": summaries}), 200
        except Exception as exc:
            return jsonify({"error": f"Summarization failed: {exc}"}), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8889, debug=False)
