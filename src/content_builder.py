"""Build concise text/path content and attach assets to nearby sections."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz

from .asset_extractor import AssetRegion, save_crop
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
        return fitz.Rect(
            min(line.rect.x0 for line in self.lines), min(line.rect.y0 for line in self.lines),
            max(line.rect.x1 for line in self.lines), max(line.rect.y1 for line in self.lines),
        )

    @property
    def label_bounds(self) -> fitz.Rect | None:
        """The option label position, excluding any text that follows it."""
        return self.lines[0].rect if self.option_label and self.lines else None


def _nearest_section(region: AssetRegion, sections: list[Section]) -> Section | None:
    candidates = [section for section in sections if section.first_page == region.page_number]
    if not candidates:
        return None

    # A diagram below option labels belongs to one of those options. This maps
    # rows of image-only choices (for example, flowchart symbols) correctly.
    option_candidates = [section for section in candidates if section.option_label and section.label_bounds]
    if option_candidates:
        first_option_y = min(section.label_bounds.y0 for section in option_candidates if section.label_bounds)
        if region.rect.y0 >= first_option_y:
            candidates = option_candidates

    def distance(section: Section) -> float:
        bounds = section.label_bounds if section.option_label else section.bounds
        if bounds is None:
            return float("inf")
        horizontal = max(bounds.x0 - region.rect.x1, 0, region.rect.x0 - bounds.x1)
        vertical = max(bounds.y0 - region.rect.y1, 0, region.rect.y0 - bounds.y1)
        return horizontal + vertical

    return min(candidates, key=distance)


def build_section(section: Section, assigned_assets: list[tuple[AssetRegion, str]]) -> tuple[str, list[str]]:
    """Return one clean text string and its relative image-path list."""
    asset_regions = [region for region, _ in assigned_assets]
    text_parts: list[str] = []
    for line in section.lines:
        # Text painted inside a cropped graphic is represented by that graphic
        # alone, preventing duplicates such as "Start Process End".
        if line.text and not any(region.rect.contains(line.rect) for region in asset_regions):
            text_parts.append(line.text)
    paths = [path for _, path in sorted(assigned_assets, key=lambda item: (item[0].rect.y0, item[0].rect.x0))]
    return " ".join(text_parts), paths


def render_and_assign_assets(
    document: fitz.Document,
    regions: list[AssetRegion],
    sections: list[Section],
    assets_dir: Path,
    assets_relative_dir: Path,
    question_number: int,
) -> dict[int, list[tuple[AssetRegion, str]]]:
    """Render assets once and return a mapping keyed by section identity."""
    raw_assigned: dict[int, list[AssetRegion]] = {id(section): [] for section in sections}
    section_by_id = {id(section): section for section in sections}
    for region in regions:
        section = _nearest_section(region, sections)
        if section is not None:
            raw_assigned[id(section)].append(region)

    # Several neighbouring vector shapes can make up a single question diagram
    # (for example, Start -> Process -> End). Merge only question-level shapes;
    # image-based answer options must remain separate.
    merged_assigned: dict[int, list[AssetRegion]] = {}
    for section_id, section_regions in raw_assigned.items():
        section = section_by_id[section_id]
        if section.option_label or len(section_regions) < 2:
            merged_assigned[section_id] = section_regions
            continue
        by_page: dict[int, list[AssetRegion]] = {}
        for region in section_regions:
            by_page.setdefault(region.page_number, []).append(region)
        combined: list[AssetRegion] = []
        for page_number, page_regions in by_page.items():
            # The regions were assigned to the same question section on the
            # same page, so a combined crop preserves their natural diagram.
            union = page_regions[0].rect
            for region in page_regions[1:]:
                union |= region.rect
            combined.append(AssetRegion(page_number, union, page_regions[0].kind))
        merged_assigned[section_id] = combined

    assigned: dict[int, list[tuple[AssetRegion, str]]] = {id(section): [] for section in sections}
    counts: dict[str, int] = {}
    for section in sections:
        for region in merged_assigned[id(section)]:
            role = f"option_{section.option_label.lower()}" if section.option_label else region.kind
            counts[role] = counts.get(role, 0) + 1
            name = f"question_{question_number}_{role}_{counts[role]}.png"
            save_crop(document[region.page_number - 1], region.rect, assets_dir / name)
            relative_path = (assets_relative_dir / name).as_posix()
            assigned[id(section)].append((region, relative_path))
    return assigned
