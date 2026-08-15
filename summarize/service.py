"""Load and call the existing Summarizer project without modifying it."""

from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path

SUMMARIZER_PATH = Path(__file__).resolve().parents[1] / "Summarizer" / "summarizer.py"


@lru_cache(maxsize=1)
def _load_summarizer():
    spec = importlib.util.spec_from_file_location("local_summarizer", SUMMARIZER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the Summarizer implementation.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def summarize_units(units: dict[str, list[str]], word_limit: int | None = None) -> dict[str, str]:
    """Delegate to ``Summarizer/summarizer.py`` unchanged."""
    return _load_summarizer().summarize_units(units=units, word_limit=word_limit)
