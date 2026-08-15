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

Option labels are detected when present (`A`, `B`, `i`, `ii`, `1`, `2`, etc.). For label-free source material, the converter also recognizes bullet lists, comma- or semicolon-separated rows, and clearly separated option lines. All detected or inferred labels are normalized to `A`, `B`, `C`, `D`, ... in the final JSON. A completely unlabelled image grid is likewise alphabetically labelled when its prompt explicitly asks the reader to choose an image, diagram, figure, symbol, shape, or option.

The extractor uses PDF text coordinates first, then OCR only for scanned/unusable pages. Embedded images and substantial vector graphic regions are rendered to PNG and placed in a sibling `<paper>_assets/` folder. Extraction issues are logged without stopping the batch.
