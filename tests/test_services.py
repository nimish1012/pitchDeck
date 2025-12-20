import pytest
from app.services.presentation_generator import PresentationGeneratorFactory, DocumentPresentationGenerator
from app.services.document_processor import DocumentProcessor
from app.utils.validators import PresentationValidator

def test_presentation_generator_factory():
    """Test the presentation generator factory"""
    factory = PresentationGeneratorFactory()
    
    # Test document generator
    doc_gen = factory.get_generator("document")
    assert isinstance(doc_gen, DocumentPresentationGenerator)
    
    # Test prompt generator
    prompt_gen = factory.get_generator("prompt")
    assert prompt_gen is not None
    
    # Test outline generator
    outline_gen = factory.get_generator("outline")
    assert outline_gen is not None

def test_document_processor():
    """Test document processor"""
    processor = DocumentProcessor()
    
    # Test file validation
    assert processor.validate_file("test.pdf", 1024) == True
    assert processor.validate_file("test.exe", 1024) == False
    assert processor.validate_file("test.pdf", 20 * 1024 * 1024) == False  # Too large

def test_text_processing():
    """Test text file processing"""
    processor = DocumentProcessor()
    
    # Test text content
    text_content = b"Hello, world! This is a test."
    result = processor._process_text_file(text_content)
    assert "Hello, world!" in result

def test_validators():
    """Test validation functions"""
    validator = PresentationValidator()
    
    # Test file validation
    valid, msg = validator.validate_file_upload("test.pdf", 1024)
    assert valid == True
    
    valid, msg = validator.validate_file_upload("test.exe", 1024)
    assert valid == False
    
    # Test prompt validation
    valid, msg = validator.validate_prompt("This is a test prompt")
    assert valid == True
    
    valid, msg = validator.validate_prompt("")
    assert valid == False
    
    # Test slide count validation
    valid, msg = validator.validate_slide_count(10)
    assert valid == True
    
    valid, msg = validator.validate_slide_count(100)
    assert valid == False
    
    # Test outline validation
    valid, msg = validator.validate_outline([
        {"title": "Slide 1", "content": ["Point 1"]},
        {"title": "Slide 2", "content": ["Point 2"]}
    ])
    assert valid == True
    
    # Test invalid outline
    valid, msg = validator.validate_outline([])
    assert valid == False