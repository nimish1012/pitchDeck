from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class PresentationType(str, Enum):
    DOCUMENT = "document"
    PROMPT = "prompt"
    OUTLINE = "outline"

class PresentationRequest(BaseModel):
    """Base presentation request model"""
    presentation_type: PresentationType = Field(..., description="Type of presentation request")
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
    """Request for outline-based presentation"""
    outline: List[Dict[str, Any]] = Field(..., description="Pre-structured outline")
    include_images: bool = Field(True, description="Whether to include relevant images")
    
class SlideData(BaseModel):
    """Individual slide data"""
    slide_number: int
    title: str
    content: List[str]
    notes: Optional[str] = None
    image_urls: Optional[List[str]] = None
    
class PresentationResponse(BaseModel):
    """Response model for presentation generation"""
    presentation_id: str
    title: str
    slides: List[SlideData]
    total_slides: int
    generation_method: PresentationType
    download_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    created_at: str
    status: str = "completed"