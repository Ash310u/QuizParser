"""Build ordered mixed text/image content and attach assets to nearest sections."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz

from .asset_extractor import AssetRegion, save_crop
from .models import ContentBlock, ImageBlock, TextBlock
from .pdf_reader import TextLine


@dataclass
class Section:
    kind: str
    option_label: str | None
    lines: list[TextLine]

    @property
    def first_page(self) -> int | None:
        return self.lines[0].page_number if self.lines else None

    @property
    def bounds(self) -> fitz.Rect | None:
        if not self.lines:
            return None
        return fitz.Rect(min(line.rect.x0 for line in self.lines), min(line.rect.y0 for line in self.lines), max(line.rect.x1 for line in self.lines), max(line.rect.y1 for line in self.lines))


def _nearest_section(region: AssetRegion, sections: list[Section]) -> Section | None:
    candidates = [section for section in sections if section.first_page == region.page_number]
    if not candidates:
        return None
    def distance(section: Section) -> float:
        bounds = section.bounds
        if bounds is None:
            return float("inf")
        if bounds.y0 <= region.rect.y0 <= bounds.y1:
            return 0
        return min(abs(region.rect.y0 - bounds.y1), abs(bounds.y0 - region.rect.y1))
    return min(candidates, key=distance)


def build_content(
    section: Section,
    assigned_assets: list[tuple[AssetRegion, str]],
) -> list[ContentBlock]:
    ordered: list[tuple[float, float, ContentBlock]] = []
    for line in section.lines:
        if line.text:
            ordered.append((line.rect.y0, line.rect.x0, TextBlock(value=line.text)))
    for region, relative_path in assigned_assets:
        ordered.append((region.rect.y0, region.rect.x0, ImageBlock(path=relative_path)))
    return [block for _, _, block in sorted(ordered, key=lambda item: (item[0], item[1]))]


def render_and_assign_assets(
    document: fitz.Document,
    regions: list[AssetRegion],
    sections: list[Section],
    assets_dir: Path,
    assets_relative_dir: Path,
    question_number: int,
) -> dict[int, list[tuple[AssetRegion, str]]]:
    """Render assets once and return a mapping keyed by section identity."""
    assigned: dict[int, list[tuple[AssetRegion, str]]] = {id(section): [] for section in sections}
    counts: dict[str, int] = {}
    for region in regions:
        section = _nearest_section(region, sections)
        if section is None:
            continue
        role = "option_" + (section.option_label or "unknown").lower() if section.option_label else region.kind
        counts[role] = counts.get(role, 0) + 1
        name = f"question_{question_number}_{role}_{counts[role]}.png"
        save_crop(document[region.page_number - 1], region.rect, assets_dir / name)
        relative_path = (assets_relative_dir / name).as_posix()
        assigned[id(section)].append((region, relative_path))
    return assigned
