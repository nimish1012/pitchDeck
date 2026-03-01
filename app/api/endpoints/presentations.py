from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends
from typing import Optional
import logging

from app.models.request_schemas import (
    DocumentPresentationRequest,
    PromptPresentationRequest, 
    OutlinePresentationRequest,
    PresentationResponse
)
from app.services.presentation_generator import PresentationGeneratorFactory
from app.services.document_processor import DocumentProcessor

router = APIRouter()
logger = logging.getLogger(__name__)

# Dependency injection for services
def get_document_processor():
    return DocumentProcessor()

def get_presentation_generator():
    return PresentationGeneratorFactory()

@router.post("/presentations/document", response_model=PresentationResponse)
async def create_presentation_from_document(
    file: UploadFile = File(..., description="Document file to upload"),
    title: Optional[str] = Form(None, description="Presentation title"),
    additional_text: Optional[str] = Form(None, description="Additional instructions"),
    theme: Optional[str] = Form("default", description="Presentation theme"),
    max_slides: Optional[int] = Form(10, description="Maximum number of slides"),
    output_format: Optional[str] = Form("pptx", description="Output format"),
    document_processor: DocumentProcessor = Depends(get_document_processor),
    generator_factory: PresentationGeneratorFactory = Depends(get_presentation_generator)
):
    """Generate presentation from uploaded document"""
    
    try:
        # Validate file
        if not document_processor.validate_file(file.filename, file.size or 0):
            raise HTTPException(
                status_code=400,
                detail="Invalid file format or size. Supported formats: PDF, DOCX, TXT, MD (max 10MB)"
            )
        
        # Read file content
        file_content = await file.read()
        
        # Process document
        extraction_result = await document_processor.process_document(file_content, file.filename)
        
        # Extract content and metadata
        document_text = extraction_result.get('content', '')
        images = extraction_result.get('images', [])
        metadata = extraction_result.get('metadata', {})
        
        # Create request object
        request = DocumentPresentationRequest(
            presentation_type="document",
            title=title,
            additional_text=additional_text,
            theme=theme,
            output_format=output_format,
            max_slides=max_slides,
            extracted_images=images,
            document_metadata=metadata
        )
        
        # Generate presentation
        generator = generator_factory.get_generator("document")
        presentation = await generator.generate_presentation(request, document_text)
        
        logger.info(f"Generated presentation {presentation.presentation_id} from document {file.filename}")
        return presentation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing document presentation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate presentation: {str(e)}")

@router.post("/presentations/prompt", response_model=PresentationResponse)
async def create_presentation_from_prompt(
    prompt: str = Form(..., description="One-liner prompt for presentation"),
    title: Optional[str] = Form(None, description="Presentation title"),
    theme: Optional[str] = Form("default", description="Presentation theme"),
    max_slides: Optional[int] = Form(10, description="Maximum number of slides"),
    output_format: Optional[str] = Form("pptx", description="Output format"),
    target_audience: Optional[str] = Form("general", description="Target audience"),
    generator_factory: PresentationGeneratorFactory = Depends(get_presentation_generator)
):
    """Generate presentation from text prompt"""
    
    try:
        if not prompt.strip():
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")
        
        # Create request object
        request = PromptPresentationRequest(
            presentation_type="prompt",
            prompt=prompt.strip(),
            title=title,
            theme=theme,
            output_format=output_format,
            max_slides=max_slides,
            target_audience=target_audience
        )
        
        # Generate presentation
        generator = generator_factory.get_generator("prompt")
        presentation = await generator.generate_presentation(request)
        
        logger.info(f"Generated presentation {presentation.presentation_id} from prompt")
        return presentation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing prompt presentation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate presentation: {str(e)}")

@router.post("/presentations/outline", response_model=PresentationResponse)
async def create_presentation_from_outline(
    request: OutlinePresentationRequest,
    generator_factory: PresentationGeneratorFactory = Depends(get_presentation_generator)
):
    """Generate presentation from structured outline (JSON body)"""
    
    try:
        if not request.outline:
            raise HTTPException(status_code=400, detail="Outline cannot be empty")
        
        # Generate presentation
        generator = generator_factory.get_generator("outline")
        presentation = await generator.generate_presentation(request)
        
        logger.info(f"Generated presentation {presentation.presentation_id} from outline")
        return presentation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing outline presentation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate presentation: {str(e)}")