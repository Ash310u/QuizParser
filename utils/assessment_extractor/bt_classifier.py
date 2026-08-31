"""Bloom's Taxonomy cognitive-level classification for assessment questions.

Uses a local Hugging Face zero-shot-classification model, so no API calls or
API keys are required. The model is downloaded once (first run only, needs
internet) and cached locally under %USERPROFILE%\\.cache\\huggingface, exactly
like ``Summarizer/summarizer.py``. Set the ``BT_LEVEL_MODEL`` environment
variable to swap in a different zero-shot (NLI-finetuned) model if this one is
not accurate enough for a given question style.
"""

from __future__ import annotations

import os
from functools import lru_cache

os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
os.environ.setdefault("USE_TF", "0")  # force the PyTorch backend, skip TensorFlow entirely

MODEL_NAME = os.environ.get("BT_LEVEL_MODEL", "typeform/distilbert-base-uncased-mnli")

HYPOTHESIS_TEMPLATE = "Answering this question mainly requires the ability to {}."
# Bloom's Taxonomy levels, phrased as the cognitive skill each one names.
# The phrase (not the level name) is what gets scored against the question
# text, since "requires the ability to Remember" reads far more awkwardly to
# an NLI model than a plain-language description of what that level means.
LEVEL_PHRASES: dict[str, str] = {
    "Remember": "recall facts, terms, or basic concepts",
    "Understand": "explain ideas or concepts in one's own words",
    "Apply": "use information in a new situation",
    "Analyze": "break information into parts and identify relationships",
    "Evaluate": "justify a decision, position, or judge value",
    "Create": "produce new or original work",
}
DEFAULT_LEVEL = "Understand"


@lru_cache(maxsize=1)
def _get_classifier():
    from transformers import pipeline
    from transformers.utils import logging as hf_logging
    hf_logging.set_verbosity_error()
    return pipeline("zero-shot-classification", model=MODEL_NAME, framework="pt")


def classify_bt_level(text: str) -> str:
    """Return the single best-matching Bloom's Taxonomy level for ``text``."""
    text = (text or "").strip()
    if not text:
        return DEFAULT_LEVEL

    classifier = _get_classifier()
    phrases = list(LEVEL_PHRASES.values())
    result = classifier(text, candidate_labels=phrases, hypothesis_template=HYPOTHESIS_TEMPLATE)
    best_phrase = result["labels"][0]
    for level, phrase in LEVEL_PHRASES.items():
        if phrase == best_phrase:
            return level
    return DEFAULT_LEVEL
