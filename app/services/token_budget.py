"""
Token Budget Manager — controls content density per slide based on textAmount.

Maps the user's textAmount setting to concrete token/word limits that are
injected into LLM prompts so the model respects the requested density.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.models.schemas import TextAmount


@dataclass(frozen=True)
class SlideBudget:
    """Concrete limits for a single slide."""
    max_tokens: int          # LLM max_tokens for this slide's generation call
    bullet_count_min: int
    bullet_count_max: int
    words_per_bullet_min: int
    words_per_bullet_max: int
    speaker_notes_sentences: int  # target # of sentences for notes
    label: str                   # human-readable label for prompt injection


# Pre-defined budget profiles
_PROFILES: dict[TextAmount, SlideBudget] = {
    TextAmount.MINIMAL: SlideBudget(
        max_tokens=settings.token_budget_minimal,
        bullet_count_min=2,
        bullet_count_max=3,
        words_per_bullet_min=4,
        words_per_bullet_max=8,
        speaker_notes_sentences=1,
        label="minimal — very concise, punchy phrases only",
    ),
    TextAmount.CONCISE: SlideBudget(
        max_tokens=settings.token_budget_concise,
        bullet_count_min=3,
        bullet_count_max=5,
        words_per_bullet_min=6,
        words_per_bullet_max=15,
        speaker_notes_sentences=2,
        label="concise — clear short sentences",
    ),
    TextAmount.DETAILED: SlideBudget(
        max_tokens=settings.token_budget_detailed,
        bullet_count_min=4,
        bullet_count_max=6,
        words_per_bullet_min=10,
        words_per_bullet_max=25,
        speaker_notes_sentences=3,
        label="detailed — informative, well-explained points",
    ),
    TextAmount.EXTENSIVE: SlideBudget(
        max_tokens=settings.token_budget_extensive,
        bullet_count_min=5,
        bullet_count_max=8,
        words_per_bullet_min=15,
        words_per_bullet_max=35,
        speaker_notes_sentences=4,
        label="extensive — thorough, in-depth coverage",
    ),
}


def get_budget(text_amount: TextAmount) -> SlideBudget:
    """Return the SlideBudget for a given density setting."""
    return _PROFILES[text_amount]


def budget_prompt_fragment(budget: SlideBudget) -> str:
    """Return a string to inject into the LLM prompt that enforces the budget."""
    return (
        f"Content density: {budget.label}\n"
        f"  • Bullet points: {budget.bullet_count_min}–{budget.bullet_count_max}\n"
        f"  • Words per bullet: {budget.words_per_bullet_min}–{budget.words_per_bullet_max}\n"
        f"  • Speaker notes: ~{budget.speaker_notes_sentences} sentence(s)\n"
        f"STRICTLY respect these limits."
    )
