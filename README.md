# PDF MCQ to JSON converter

Batch-convert multiple-choice-question PDFs placed directly in `input/` into JSON and image assets in `output/`.
The converter does not require subject or semester folders and never embeds absolute paths in JSON.

## Install

Use one project virtual environment for all three services. Python 3.13 or
earlier is required because the existing summarizer's pinned dependencies do
not currently provide a Python 3.14 wheel.

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Tesseract must also be installed and available as `tesseract` on your `PATH`. It is only used for pages without usable selectable PDF text.

## Run

```bash
.venv/bin/python -m utils.question_extractor.engine
```

## Flask API

Run every endpoint from that same environment:

```bash
.venv/bin/python app.py
```

The first call to `/summarize` downloads the summarization model. The first
assessment containing a question without an explicit BT code downloads the
Bloom taxonomy classification model.

The server has no authentication and exposes three endpoints:

```bash
# Convert uploaded PDFs. Use no files to process every PDF in input/.
curl -X POST http://localhost:5000/question-extractor \
  -F "files=@/path/to/paper.pdf"

# Preserve a complete assessment PDF layout and extract sections/questions.
curl -X POST http://localhost:5000/assessment-extractor \
  -F "files=@/path/to/assignment.pdf"

# Summarize text units using Summarizer/summarizer.py.
curl -X POST http://localhost:5000/summarize \
  -H "Content-Type: application/json" \
  -d '{"units":{"1":["First topic.","Second topic."]},"word_limit":50}'
```

Every API result is stored under the shared `output/` directory:

```text
output/
├── question_extractor/    MCQ JSON and image assets
├── assessment_extractor/  assessment JSON and page/image assets
└── summarizer/            one JSON response per summary request
```

The question endpoint saves uploads in `input/`, writes JSON/assets to
`output/question_extractor/`, and returns the generated JSON in its response.
Set `QUESTION_INPUT_DIR` or `QUESTION_OUTPUT_DIR` to use different directories.

The assessment endpoint writes to `output/assessment_extractor/` by default
(override with `ASSESSMENT_INPUT_DIR` and `ASSESSMENT_OUTPUT_DIR`). It shares
the question extractor's PDF/OCR/asset pipeline, so its JSON uses the same
per-PDF `{subject, semester, source_pdf, questions: [...]}` shape as
`/question-extractor`. Each question omits `options`/`answer` (assessment
questions are typically free-response, not multiple-choice) and instead
includes `marks` (parsed from a trailing `[N Marks]` annotation, defaulting to
`1.0` when absent) and `bt_level`. Explicit `L1`-`L6` codes are mapped to their
Bloom taxonomy names (`Remember` through `Create`). Questions without an
explicit code are classified automatically from their question text.
`/assessment-extractor-from-directory` returns the identical
`{source_pdf, json_path, data}` shape per PDF, but does not keep its
transient JSON file on disk (only the PNG assets remain, alongside the
caller-supplied PDFs).

The summary endpoint writes its response to `output/summarizer/` and includes
the saved `output_path` in its JSON response. Set `SUMMARY_OUTPUT_DIR` to
override that destination.

## Project structure

```text
app.py                         Flask application and route registration
services/
  question_extractors/         Public MCQ service interface
  assessment_extractors/       Public assessment service interface
  summarize/                   Public summary service interface
utils/
  question_extractor/          MCQ PDF extraction logic and models
  assessment_extractor/        Assessment PDF layout/parser logic
  summarizer/                  Adapter for the unchanged Summarizer project
Summarizer/                    Existing summarizer implementation (unchanged)
tests/                         Endpoint and extraction tests
```

Each public service folder contains only `__init__.py` and `service.py`.
Implementation details belong in its matching `utils/` package, keeping the
Flask layer and service interfaces small and stable.

By default this reads `input/` and writes `output/`. Custom roots are also supported:

```bash
.venv/bin/python -m utils.question_extractor.engine --input /path/to/input --output /path/to/output
```

Put every PDF directly in `input/`:

```text
input/
├── paper_2024.pdf
├── paper_2025.pdf
└── practice_test.pdf
```

Each file becomes `output/<pdf-name>.json` plus `output/<pdf-name>_assets/`. The `subject` and `semester` fields remain in the JSON schema with the value `"unspecified"`; the simple input folder provides no reliable metadata for them. Both extractors include `metadata.paper_code`, parsed from a label such as `Paper Code: DS-MCQ-101`; MCQ output additionally includes `metadata.total_time_minutes`, parsed from a labelled duration such as `Total Time: 1 Hour 30 Minutes`. These values are `null` when absent. Subfolders are intentionally ignored.

Each question stores compact data rather than a mixed block array:

```json
{
  "number": 2,
  "page_number": 1,
  "content": "Identify the correct flowchart symbol for a decision.",
  "path": [],
  "options": [
    {"label": "A", "content": "", "path": ["paper_assets/question_2_option_a_1.png"]}
  ],
  "answer": ["A"]
}
```

`path` always contains relative PNG paths. `answer` is always an array of option labels: `[]` when no answer key is present, `["B"]` for one answer, or `["B", "C"]` for multiple correct answers. Every output option uses alphabetic labels in its displayed order (`A`, `B`, `C`, `D`, ...), even when the PDF uses numbers, Roman numerals, bullets, or no visible labels.

Each question also includes `confidence_score` between `0.0` and `1.0`. It is a structural extraction confidence, not a claim that the selected answer is factually correct. The fallback thresholds are deliberate: no options scores at most `0.20`; fewer than four options scores below `0.50`; one duplicate or empty option scores below `0.75`; two or more duplicate/empty options score below `0.50`; and each option above four lowers confidence by `0.10` (up to `0.30`). A printed answer key that cannot be matched to an extracted option also scores below `0.75`.

Option labels are detected when present (`A`, `B`, `i`, `ii`, `1`, `2`, etc.). For label-free source material, the converter also recognizes bullet lists, comma- or semicolon-separated rows, and clearly separated option lines. All detected or inferred labels are normalized to `A`, `B`, `C`, `D`, ... in the final JSON. A completely unlabelled image grid is likewise alphabetically labelled when its prompt explicitly asks the reader to choose an image, diagram, figure, symbol, shape, or option.

The extractor uses PDF text coordinates first, then OCR only for scanned/unusable pages. Embedded images and substantial vector graphic regions are rendered to PNG and placed in a sibling `<paper>_assets/` folder. Extraction issues are logged without stopping the batch.

The assessment extractor's question record swaps `options`/`answer` for `marks`/`bt_level`:

```json
{
  "number": 2,
  "page_number": 1,
  "content": "Solve the following quadratic equation:",
  "path": ["paper_assets/question_2_diagram_1.png"],
  "marks": 3.0,
  "bt_level": "Apply",
  "confidence_score": 1.0
}
```
