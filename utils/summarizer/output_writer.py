"""Persist summary API responses under the shared output root."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def save_summary_output(summaries: dict[str, str], output_directory: Path) -> Path:
    """Write one uniquely named JSON response without overwriting prior calls."""
    output_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_path = output_directory / f"summary_{timestamp}_{uuid4().hex[:8]}.json"
    output_path.write_text(json.dumps({"summaries": summaries}, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
