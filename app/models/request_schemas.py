from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class PresentationType(str, Enum):
    DOCUMENT = "document"
    PROMPT = "prompt"
    OUTLINE = "outline"

class PresentationRequest(BaseModel):
    """Base presentation request model"""
    presentation_type: PresentationType = Field(PresentationType.DOCUMENT, description="Type of presentation request")
    title: Optional[str] = Field(None, description="Presentation title")
    theme: Optional[str] = Field("default", description="Presentation theme")
    output_format: str = Field("pptx", description="Output format (pptx, pdf, html)")
    
class DocumentPresentationRequest(PresentationRequest):
    """Request for document-based presentation"""
    additional_text: Optional[str] = Field(None, description="Additional instructions or context")
    max_slides: Optional[int] = Field(10, description="Maximum number of slides")
    extracted_images: Optional[List[Dict[str, Any]]] = Field(None, description="Images extracted from document")
    document_metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata from document processing")
    
class PromptPresentationRequest(PresentationRequest):
    """Request for prompt-based presentation"""
    prompt: str = Field(..., description="One-liner prompt for presentation generation")
    max_slides: Optional[int] = Field(10, description="Maximum number of slides")
    target_audience: Optional[str] = Field("general", description="Target audience")
    
class OutlinePresentationRequest(PresentationRequest):
    """Request for outline-based presentation (also serves as the endpoint JSON body)"""
    presentation_type: PresentationType = Field(PresentationType.OUTLINE, description="Type")
    outline: List[Dict[str, Any]] = Field(..., description="Pre-structured outline")
    include_images: bool = Field(True, description="Whether to include relevant images")


# ──────────────────────────────────────────────
#  Pipeline Intermediate Models (Prompt Flow)
# ──────────────────────────────────────────────

class SlideIntent(BaseModel):
    """A single slide's intent from Stage 1 analysis"""
    slide_number: int
    intent: str

class PromptAnalysis(BaseModel):
    """Stage 1 output — analysis of the user's prompt"""
    title: str
    ppt_type: str  # informational, persuasive, educational, pitch
    target_audience: str
    recommended_slides: int
    slide_intents: List[SlideIntent]

class SlideOutline(BaseModel):
    """A single slide's outline from Stage 2"""
    slide_number: int
    title: str
    bullet_points: List[str]
    speaker_notes_hint: str = ""
    layout: str = "content"  # title, content, two_column, comparison, quote, image_focus, summary

class PresentationOutline(BaseModel):
    """Stage 2 output — full outline with table of contents"""
    table_of_contents: List[str]
    slide_outlines: List[SlideOutline]

class GeneratedSlide(BaseModel):
    """Stage 3 output — final content for a single slide"""
    slide_number: int
    title: str
    content: List[str]
    notes: str = ""
    layout: str = "content"

class OutlineAnalysis(BaseModel):
    """Outline flow Stage 1 — analysis of the user's outline"""
    title: str
    ppt_type: str
    target_audience: str
    theme_suggestion: str = ""
    total_slides: int

class DocumentSection(BaseModel):
    """A single section extracted from a document for one slide"""
    slide_number: int
    section_title: str
    source_excerpt: str

class DocumentAnalysis(BaseModel):
    """Document flow Stage 1 — document broken into slide sections"""
    title: str
    ppt_type: str
    target_audience: str
    sections: List[DocumentSection]




# ──────────────────────────────────────────────
#  Response Models
# ──────────────────────────────────────────────

class SlideData(BaseModel):
    """Individual slide data"""
    slide_number: int
    title: str
    content: List[str]
    notes: Optional[str] = None
    image_urls: Optional[List[str]] = None
    layout: Optional[str] = None
    
class PresentationResponse(BaseModel):
    """Response model for presentation generation"""
    presentation_id: str
    title: str
    slides: List[SlideData]
    total_slides: int
    generation_method: PresentationType
    table_of_contents: Optional[List[str]] = None
    download_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    created_at: str
    status: str = "completed"