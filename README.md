# PDF MCQ to JSON converter

Batch-convert multiple-choice-question PDFs placed directly in `input/` into JSON and image assets in `output/`.
The converter does not require subject or semester folders and never embeds absolute paths in JSON.

## Install

```bash
python -m pip install -r requirements.txt
```

Tesseract must also be installed and available as `tesseract` on your `PATH`. It is only used for pages without usable selectable PDF text.

## Run

```bash
python main.py
```

## Flask API

For the question-extraction endpoint (including Flask), install only the main
project dependencies. This works with the current Python 3.14 environment:

```bash
python -m pip install -r requirements.txt
python app.py
```

The `/summarize` endpoint uses the existing `Summarizer` project's pinned
Hugging Face dependencies. Its pinned `tokenizers` version does not provide a
Python 3.14 wheel, so run the full two-endpoint server from a Python 3.13-or-
earlier virtual environment instead:

```bash
# Example when Python 3.13 is installed as python3.13.
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -r Summarizer/requirements.txt
.venv/bin/python app.py
```

The first call to `/summarize` also downloads the existing local model. The
question-extraction endpoint does not require those summarizer dependencies.

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

The question endpoint saves uploads in `input/`, writes JSON/assets to `output/`, and returns the generated JSON in its response. Set `QUESTION_INPUT_DIR` or `QUESTION_OUTPUT_DIR` to use different directories.

The assessment endpoint is separate from the MCQ converter. It writes to
`assessment_output/` by default (override with `ASSESSMENT_INPUT_DIR` and
`ASSESSMENT_OUTPUT_DIR`). Its JSON includes the full page layout—text blocks
with spans and coordinates, embedded images, vector drawings, links,
annotations, dimensions, and a rendered page image—plus a best-effort
`assessment` view of the title, metadata, sections, topics, questions, marks,
and learning levels. The layout data remains available when a source PDF uses
a different assessment format.

By default this reads `input/` and writes `output/`. Custom roots are also supported:

```bash
python main.py --input /path/to/input --output /path/to/output
```

Put every PDF directly in `input/`:

```text
input/
├── paper_2024.pdf
├── paper_2025.pdf
└── practice_test.pdf
```

Each file becomes `output/<pdf-name>.json` plus `output/<pdf-name>_assets/`. The `subject` and `semester` fields remain in the JSON schema with the value `"unspecified"`; the simple input folder provides no reliable metadata for them. Subfolders are intentionally ignored.

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
