# Summarizer

Offline, AI-generated text summarization. Given a dictionary of `{unit_key: [list of strings]}`,
returns a dictionary of `{unit_key: summary}` — one summary per unit, capped at a configurable word limit.

Runs fully offline (after the one-time model download) using a local Hugging Face model
(`sshleifer/distilbart-cnn-6-6`). No API key, no per-call cost, no internet dependency at runtime.

## Requirements

- Python 3.9+
- ~1.5 GB free disk space (PyTorch + the summarization model)
- Internet connection for the **first run only** (to download the model, ~300 MB)

## Setup

1. **Clone/copy the project**, then open a terminal in the project folder.

2. **Create a virtual environment** (recommended, keeps dependencies isolated):

   ```powershell
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```powershell
   pip install -r requirements.txt
   ```

   This installs the CPU-only build of PyTorch (via the `--extra-index-url` in
   `requirements.txt`) plus `transformers`, `sentencepiece`, and `python-dotenv`.
   If you have an NVIDIA GPU and want CUDA acceleration instead, install PyTorch
   separately first per [pytorch.org](https://pytorch.org/get-started/locally/),
   then run `pip install transformers sentencepiece python-dotenv`.

4. **Run it:**

   ```powershell
   python summarizer.py
   ```

   The first run downloads the model to `%USERPROFILE%\.cache\huggingface` — this
   needs internet and takes a minute or two. Every run after that is fully offline.

## Usage

### Default data (from `.env`)

Running `python summarizer.py` with no arguments summarizes the dummy data in `.env`
and prints a JSON dictionary of `{unit_key: summary}`.

### Your own data

```python
from summarizer import summarize_units

units = {
    "1": ["First topic in unit 1.", "Second topic in unit 1."],
    "2": ["First topic in unit 2.", "Second topic in unit 2."],
}

summaries = summarize_units(units, word_limit=50)
print(summaries)
# {"1": "...", "2": "..."}
```

`summarize_units(units=None, word_limit=None)`:

- `units` — dict of `{unit_key: [strings]}`. Omit (or pass `None`) to fall back to
  `DEFAULT_INPUT_UNITS` in `.env`.
- `word_limit` — max words per unit's summary, applied independently to each unit.
  Omit (or pass `None`) to fall back to `DEFAULT_WORD_LIMIT` in `.env` (defaults to 50
  if that's also unset).
- Passing either argument explicitly always overrides its `.env` default.

## Configuration (`.env`)

| Variable | Description |
|---|---|
| `DEFAULT_INPUT_UNITS` | JSON object: `{"unit_key": ["string", "string", ...], ...}` — used when `units` isn't passed to `summarize_units`. |
| `DEFAULT_WORD_LIMIT` | Integer word cap per unit summary — used when `word_limit` isn't passed. |

`.env` ships with dummy data (a 6-unit course syllabus) so the script runs out of the box.
Edit the values to change the defaults — `DEFAULT_INPUT_UNITS` must stay valid JSON.

## Notes

- Summaries are deterministic (greedy/beam search, no sampling) — the same input always
  produces the same output.
- Very short units (fewer than ~10 words of input) are returned as-is rather than run
  through the model, since there's nothing meaningful to condense.
- The model is loaded once per process and cached in memory — repeated calls to
  `summarize_units` within the same run are fast; a fresh `python summarizer.py`
  invocation re-pays the model load cost (a few seconds) each time.
