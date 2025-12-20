import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

from app.models.request_schemas import (
    DocumentPresentationRequest, 
    PromptPresentationRequest, 
    OutlinePresentationRequest,
    PresentationResponse,
    SlideData
)

class BasePresentationGenerator(ABC):
    """Abstract base class for presentation generators"""
    
    @abstractmethod
    async def generate_presentation(self, **kwargs) -> PresentationResponse:
        """Generate a presentation based on input parameters"""
        pass
    
    def _generate_presentation_id(self) -> str:
        """Generate unique presentation ID"""
        return f"pres_{uuid.uuid4().hex[:8]}"
    
    def _create_slide(self, slide_number: int, title: str, content: List[str], notes: Optional[str] = None) -> SlideData:
        """Create a slide data object"""
        return SlideData(
            slide_number=slide_number,
            title=title,
            content=content,
            notes=notes
        )

class DocumentPresentationGenerator(BasePresentationGenerator):
    """Generate presentations from documents"""
    
    async def generate_presentation(self, request: DocumentPresentationRequest, document_content: str) -> PresentationResponse:
        """Generate presentation from document"""
        presentation_id = self._generate_presentation_id()
        
        # Simulate AI processing - replace with actual AI service integration
        slides = await self._process_document_to_slides(document_content, request)
        
        return PresentationResponse(
            presentation_id=presentation_id,
            title=request.title or "Document Presentation",
            slides=slides,
            total_slides=len(slides),
            generation_method="document",
            created_at=datetime.utcnow().isoformat()
        )
    
    async def _process_document_to_slides(self, document_content: str, request: DocumentPresentationRequest) -> List[SlideData]:
        """Process document content and create slides"""
        # This is where you would integrate with AI services
        # For now, creating a basic structure
        
        slides = []
        
        # Title slide
        slides.append(self._create_slide(
            slide_number=1,
            title=request.title or "Document Summary",
            content=["Generated from uploaded document"]
        ))
        
        # Content slides (simplified)
        max_slides = request.max_slides or 10
        content_lines = document_content.split('\n')[:max_slides-1]  # Exclude title slide
        
        for i, line in enumerate(content_lines, 2):
            if line.strip():
                slides.append(self._create_slide(
                    slide_number=i,
                    title=f"Slide {i}",
                    content=[line.strip()]
                ))
        
        return slides

class PromptPresentationGenerator(BasePresentationGenerator):
    """Generate presentations from prompts"""
    
    async def generate_presentation(self, request: PromptPresentationRequest) -> PresentationResponse:
        """Generate presentation from prompt"""
        presentation_id = self._generate_presentation_id()
        
        # Simulate AI processing - replace with actual AI service integration
        slides = await self._process_prompt_to_slides(request)
        
        return PresentationResponse(
            presentation_id=presentation_id,
            title=request.title or "Generated Presentation",
            slides=slides,
            total_slides=len(slides),
            generation_method="prompt",
            created_at=datetime.utcnow().isoformat()
        )
    
    async def _process_prompt_to_slides(self, request: PromptPresentationRequest) -> List[SlideData]:
        """Process prompt and create slides"""
        slides = []
        max_slides = request.max_slides or 10
        
        # Title slide
        slides.append(self._create_slide(
            slide_number=1,
            title=request.title or request.prompt[:50] + "...",
            content=[request.prompt]
        ))
        
        # Generate content slides based on prompt
        # This would integrate with AI services in production
        for i in range(2, max_slides + 1):
            slides.append(self._create_slide(
                slide_number=i,
                title=f"Key Point {i-1}",
                content=[f"Generated content based on: {request.prompt}"]
            ))
        
        return slides

class OutlinePresentationGenerator(BasePresentationGenerator):
    """Generate presentations from outlines"""
    
    async def generate_presentation(self, request: OutlinePresentationRequest) -> PresentationResponse:
        """Generate presentation from outline"""
        presentation_id = self._generate_presentation_id()
        
        slides = await self._process_outline_to_slides(request)
        
        return PresentationResponse(
            presentation_id=presentation_id,
            title=request.title or "Outline Presentation",
            slides=slides,
            total_slides=len(slides),
            generation_method="outline",
            created_at=datetime.utcnow().isoformat()
        )
    
    async def _process_outline_to_slides(self, request: OutlinePresentationRequest) -> List[SlideData]:
        """Process outline and create slides"""
        slides = []
        
        for i, outline_item in enumerate(request.outline, 1):
            title = outline_item.get('title', f'Slide {i}')
            content = outline_item.get('content', [])
            notes = outline_item.get('notes')
            
            slides.append(self._create_slide(
                slide_number=i,
                title=title,
                content=content if isinstance(content, list) else [content],
                notes=notes
            ))
        
        return slides

class PresentationGeneratorFactory:
    """Factory to create appropriate presentation generators"""
    
    @staticmethod
    def get_generator(presentation_type: str) -> BasePresentationGenerator:
        """Get the appropriate generator based on presentation type"""
        generators = {
            "document": DocumentPresentationGenerator(),
            "prompt": PromptPresentationGenerator(),
            "outline": OutlinePresentationGenerator()
        }
        
        return generators.get(presentation_type, DocumentPresentationGenerator())