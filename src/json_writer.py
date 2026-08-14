"""Write stable, human-readable JSON."""

from __future__ import annotations

import json
from pathlib import Path

from .models import Paper


def write_paper(paper: Paper, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(paper.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
