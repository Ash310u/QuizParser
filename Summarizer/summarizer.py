"""Offline AI text summarizer.

Uses a local Hugging Face model (distilbart-cnn) to generate abstractive
summaries. The model is downloaded once (first run only, needs internet)
and cached locally under %USERPROFILE%\\.cache\\huggingface — every run
after that is fully offline and free, no API calls or API keys required.
"""

import json
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
os.environ.setdefault("USE_TF", "0")  # force the PyTorch backend, skip TensorFlow entirely

MODEL_NAME = "sshleifer/distilbart-cnn-6-6"


def _default_input_units():
    """Load the fallback {unit_no: [strings]} dict from the DEFAULT_INPUT_UNITS env var (.env)."""
    raw = os.environ.get("DEFAULT_INPUT_UNITS")
    if not raw:
        return {}
    return json.loads(raw)


def _default_word_limit():
    """Load the fallback word count from the DEFAULT_WORD_LIMIT env var (.env)."""
    raw = os.environ.get("DEFAULT_WORD_LIMIT")
    return int(raw) if raw else 50


@lru_cache(maxsize=1)
def _get_summarizer():
    from transformers import pipeline
    from transformers.utils import logging as hf_logging
    hf_logging.set_verbosity_error()
    return pipeline("summarization", model=MODEL_NAME, framework="pt")


def _summarize_one(strings, word_limit):
    """Combine a list of strings and return an AI-generated summary of about `word_limit` words."""
    text = " ".join(s.strip() for s in strings if s and s.strip())
    if not text:
        return ""

    summarizer = _get_summarizer()

    # distilbart tokenizes sub-words, so ask for a token budget a bit above
    # the target word count, then hard-trim to the word limit afterward.
    max_new_tokens = int(word_limit * 1.5)
    min_new_tokens = max(5, int(word_limit * 0.5))

    input_word_count = len(text.split())
    if input_word_count < 10:
        # Too short for the model to meaningfully condense; return as-is.
        words = text.split()
        return " ".join(words[:word_limit])

    result = summarizer(
        text,
        max_new_tokens=max_new_tokens,
        min_new_tokens=min(min_new_tokens, max_new_tokens),
        do_sample=False,
        truncation=True,
    )
    summary = result[0]["summary_text"].strip()

    words = summary.split()
    if len(words) > word_limit:
        summary = " ".join(words[:word_limit])

    return summary


def summarize_units(units=None, word_limit=None):
    """Summarize each unit's list of strings.

    `units` is a dict mapping a unit key (e.g. unit number) to a list of strings.
    Returns a dict with the same keys, each mapped to its AI-generated summary.

    If `units` is omitted (or None), falls back to DEFAULT_INPUT_UNITS from .env.
    If `word_limit` is omitted (or None), falls back to DEFAULT_WORD_LIMIT from .env (or 50).
    Passing either argument explicitly always takes priority over the .env default.
    The same word_limit is applied to every unit's summary.
    """
    if units is None:
        units = _default_input_units()
    if word_limit is None:
        word_limit = _default_word_limit()

    return {
        unit_key: _summarize_one(strings, word_limit)
        for unit_key, strings in units.items()
    }


if __name__ == "__main__":
    import json as _json

    # No arguments passed -> falls back to DEFAULT_INPUT_UNITS and
    # DEFAULT_WORD_LIMIT in .env. Pass units/word_limit explicitly to override.
    result = summarize_units()
    print(_json.dumps(result, indent=2))
