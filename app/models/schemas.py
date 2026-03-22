"""
Gamma-style schemas for the presentation generation pipeline.

Core concept: A single `GenerationState` JSON object is created at request time
and continuously updated through every pipeline stage. This mirrors Gamma.app's
`createDocGeneration` pattern where the state evolves:

  analyzing → outlining → generating → completed / failed
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Enums
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GenerationStatus(str, Enum):
    """Pipeline lifecycle states."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    OUTLINING = "outlining"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class TextAmount(str, Enum):
    """Content density setting — maps to token budgets."""
    MINIMAL = "minimal"
    CONCISE = "concise"  # "md" in Gamma
    DETAILED = "detailed"
    EXTENSIVE = "extensive"


class SlideLayout(str, Enum):
    """Available layout types for slide rendering."""
    TEXT = "text"
    IMAGE_LEFT = "image_left"
    IMAGE_RIGHT = "image_right"
    FULL_BLEED = "full_bleed"
    TWO_COLUMN = "two_column"
    COMPARISON = "comparison"
    TITLE = "title"
    SECTION_HEADER = "section_header"
    QUOTE = "quote"
    SUMMARY = "summary"


class ImageType(str, Enum):
    """Type of image to generate for a slide."""
    DIAGRAM = "diagram"
    ILLUSTRATION = "illustration"
    PHOTO = "photo"
    CHART = "chart"
    ICON = "icon"
    NONE = "none"


class PresentationStyle(str, Enum):
    MODERN = "modern"
    CLASSIC = "classic"
    MINIMAL = "minimal"
    BOLD = "bold"
    ACADEMIC = "academic"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Request Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GenerationSettings(BaseModel):
    """User-configurable generation settings (mirrors Gamma's settings block)."""
    text_amount: TextAmount = Field(TextAmount.CONCISE, description="Content density")
    num_slides: int = Field(10, ge=1, le=50, description="Target slide count")
    image_generation: bool = Field(True, description="Whether to generate images")
    audience: str = Field("", description="Target audience (empty = infer)")
    tone: str = Field("", description="Desired tone (empty = infer)")
    style: PresentationStyle = Field(PresentationStyle.MODERN, description="Visual style")
    image_model: str = Field("flux-1-quick", description="Diffusion model for images")
    art_style_preset: str = Field("illustration", description="Art style preset")
    art_style_prompt: str = Field(
        "Modern vector illustration. Clean, defined linework with flat color fills and minimal gradients.",
        description="Style prompt appended to image generation prompts",
    )
    locale: str = Field("en-gb", description="Output locale")


class GenerateRequest(BaseModel):
    """Top-level request to start a presentation generation."""
    prompt: str = Field(..., min_length=1, max_length=2000, description="User's prompt")
    settings: GenerationSettings = Field(default_factory=GenerationSettings)
    title: Optional[str] = Field(None, max_length=200, description="Override title")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Pipeline Intermediate Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AnalysisResult(BaseModel):
    """Step 1 output — analysis of user prompt."""
    topic: str
    intent: str
    audience: str
    tone: str
    complexity: str  # "basic", "intermediate", "advanced"
    num_slides: int
    title: str
    presentation_type: str  # informational, persuasive, educational, pitch


class OutlineSlide(BaseModel):
    """A single slide in the outline (Step 2 output)."""
    slide_id: int
    title: str
    key_points: List[str] = Field(default_factory=list)
    image_required: bool = False
    image_type: ImageType = ImageType.NONE
    layout_hint: SlideLayout = SlideLayout.TEXT


class OutlineResult(BaseModel):
    """Step 2 output — structured slide outline."""
    slides: List[OutlineSlide]
    image_plan: List[Dict[str, Any]] = Field(default_factory=list)
    layout_plan: List[Dict[str, Any]] = Field(default_factory=list)


class SlideContent(BaseModel):
    """Step 3 output — generated content for a single slide."""
    slide_id: int
    title: str
    content: List[str] = Field(default_factory=list, description="Bullet points / text blocks")
    image_prompt: Optional[str] = Field(None, description="Prompt for image generation")
    layout: SlideLayout = SlideLayout.TEXT
    notes: str = Field("", description="Speaker notes")
    image_type: ImageType = ImageType.NONE


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Final Slide Model
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Slide(BaseModel):
    """Final slide object stored in the generation state."""
    slide_id: int
    title: str
    content: List[str] = Field(default_factory=list)
    layout: SlideLayout = SlideLayout.TEXT
    notes: str = ""
    image_prompt: Optional[str] = None
    image_url: Optional[str] = None
    image_type: ImageType = ImageType.NONE
    status: Literal["pending", "generating", "completed", "failed"] = "pending"
    token_budget: Optional[int] = None
    error: Optional[str] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Generation State (the continuously-updating JSON)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class DraftInput(BaseModel):
    """Mirrors Gamma's draftInput — stores the original request context."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:15])
    doc_generation_id: str = ""
    status: str = "draft"
    prompt: str = ""
    content: str = ""
    format: str = "deck"
    settings: GenerationSettings = Field(default_factory=GenerationSettings)
    created_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GenerationState(BaseModel):
    """
    The master state object that is created at request time and updated
    through every pipeline stage.  Every SSE event pushes the latest snapshot.

    Modelled after Gamma's `createDocGeneration` response structure.
    """
    generation_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:15])
    status: GenerationStatus = GenerationStatus.PENDING
    user_id: str = Field(default="anonymous")
    generation_type: str = "generate"

    # Original request context
    draft_input: DraftInput = Field(default_factory=DraftInput)

    # Pipeline outputs (populated progressively)
    analysis: Optional[AnalysisResult] = None
    outline: Optional[OutlineResult] = None
    slides: List[Slide] = Field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    theme: str = "modern"
    total_slides: int = 0

    # Timing
    created_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Error tracking
    error: Optional[str] = None
    retry_count: int = 0

    def touch(self) -> None:
        """Update the `updated_time` timestamp."""
        self.updated_time = datetime.now(timezone.utc).isoformat()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SSE Event Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SSEEvent(BaseModel):
    """Wrapper for a single Server-Sent Event."""
    event: str  # "status", "slide", "analysis", "outline", "complete", "error"
    data: Dict[str, Any]
    generation_id: str


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  API Response Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GenerationCreatedResponse(BaseModel):
    """Returned immediately when a generation is kicked off."""
    generation_id: str
    status: GenerationStatus
    stream_url: str
    created_time: str


class GenerationStatusResponse(BaseModel):
    """Returned when polling generation status."""
    generation_id: str
    status: GenerationStatus
    total_slides: int
    completed_slides: int
    slides: List[Slide]
    analysis: Optional[AnalysisResult] = None
    outline: Optional[OutlineResult] = None
    error: Optional[str] = None
    created_time: str
    updated_time: str
