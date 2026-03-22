"""
Layout Engine — dynamically assigns slide layouts based on content analysis.

Rules (from spec):
  • bullets > 6            → TWO_COLUMN (split layout)
  • image present          → IMAGE_LEFT or IMAGE_RIGHT (alternating)
  • title-heavy / short    → TITLE or SECTION_HEADER (centred)
  • first slide            → TITLE
  • last slide             → SUMMARY
  • comparison keywords    → COMPARISON
  • quote detected         → QUOTE
  • otherwise              → TEXT
"""

from __future__ import annotations

import re
from typing import List, Optional

from app.models.schemas import ImageType, SlideLayout


_COMPARISON_KEYWORDS = {
    "vs", "versus", "compare", "comparison", "differ", "difference",
    "pros and cons", "advantages", "disadvantages", "contrast",
}

_QUOTE_PATTERN = re.compile(r'["""\u201c\u201d]')


def decide_layout(
    slide_id: int,
    total_slides: int,
    title: str,
    key_points: List[str],
    image_required: bool,
    image_type: ImageType = ImageType.NONE,
    layout_hint: Optional[SlideLayout] = None,
) -> SlideLayout:
    """
    Determine the best layout for a slide given its content characteristics.

    If the outline already carries a layout_hint that is not the generic TEXT,
    we respect it.  Otherwise we apply the rule engine.
    """

    # Respect explicit hint from outline (unless it is the default TEXT)
    if layout_hint and layout_hint != SlideLayout.TEXT:
        return layout_hint

    # ── Rule: First slide → TITLE ──────────────
    if slide_id == 1:
        return SlideLayout.TITLE

    # ── Rule: Last slide → SUMMARY ─────────────
    if slide_id == total_slides:
        return SlideLayout.SUMMARY

    # ── Rule: Quote detected ───────────────────
    combined = " ".join(key_points).lower()
    if _QUOTE_PATTERN.search(combined) and len(key_points) <= 2:
        return SlideLayout.QUOTE

    # ── Rule: Comparison keywords ──────────────
    title_lower = title.lower()
    if any(kw in title_lower or kw in combined for kw in _COMPARISON_KEYWORDS):
        return SlideLayout.COMPARISON

    # ── Rule: Too many bullets → split ─────────
    if len(key_points) > 6:
        return SlideLayout.TWO_COLUMN

    # ── Rule: Image present → side layout ──────
    if image_required and image_type != ImageType.NONE:
        # Alternate left/right for visual variety
        return SlideLayout.IMAGE_LEFT if slide_id % 2 == 0 else SlideLayout.IMAGE_RIGHT

    # ── Rule: Title-heavy (short content) ──────
    if len(key_points) <= 1 and len(title) > 10:
        return SlideLayout.SECTION_HEADER

    # Default
    return SlideLayout.TEXT


def apply_layout_correction(
    slides: list,
) -> list:
    """
    Post-generation pass: fix any layout inconsistencies.

    • Ensures first slide is TITLE.
    • Ensures last slide is SUMMARY.
    • Re-checks bullet-heavy slides that accidentally got TEXT.
    """
    if not slides:
        return slides

    # Force first = TITLE
    slides[0].layout = SlideLayout.TITLE

    # Force last = SUMMARY
    if len(slides) > 1:
        slides[-1].layout = SlideLayout.SUMMARY

    # Scan middle slides for bullet overflow
    for s in slides[1:-1] if len(slides) > 2 else []:
        if len(s.content) > 6 and s.layout == SlideLayout.TEXT:
            s.layout = SlideLayout.TWO_COLUMN
        if s.image_url and s.layout == SlideLayout.TEXT:
            s.layout = SlideLayout.IMAGE_RIGHT

    return slides
