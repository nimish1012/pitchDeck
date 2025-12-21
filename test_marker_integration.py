#!/usr/bin/env python3
"""
Test script for marker integration in document processor.
This script demonstrates how to use the new marker-powered document processor.
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from app.services.document_processor import DocumentProcessor


async def test_marker_integration():
    """Test the marker integration with a sample PDF file"""
    
    print("🧪 Testing Marker Integration")
    print("=" * 50)
    
    # Initialize document processor
    processor = DocumentProcessor(output_dir="test_extracted_content")
    
    # Test 1: Check if marker is available
    print(f"Marker Available: {processor.converter is not None}")
    
    if processor.converter is None:
        print("Warning: Marker not available. Install with: pip install marker-pdf")
        return
    
    # Test 2: Test with a sample text file (since we don't have a PDF handy)
    print("\nTesting with text file...")
    
    sample_text = """
    Sample Document for Testing
    
    This is a sample document that will be converted to markdown format.
    
    Features of the new document processor:
    - Advanced PDF processing with marker
    - Image extraction and storage
    - Markdown output formatting
    - Metadata extraction
    
    The marker library provides superior PDF-to-text conversion capabilities.
    """
    
    # Convert bytes
    sample_content = sample_text.encode('utf-8')
    
    # Process the text file
    result = await processor.process_document(sample_content, "sample.txt")
    
    # Display results
    print(f"Processing completed!")
    print(f"Content length: {len(result['content'])} characters")
    print(f"Images extracted: {len(result['images'])}")
    print(f"Metadata: {result['metadata']}")
    
    # Display content preview
    print("\nContent Preview:")
    print("-" * 30)
    print(result['content'][:200] + "..." if len(result['content']) > 200 else result['content'])
    
    # Display extraction summary
    summary = processor.get_extraction_summary(result)
    print(f"\nExtraction Summary:")
    print("-" * 30)
    print(summary)
    
    return result


async def test_file_validation():
    """Test file validation functionality"""
    
    print("\nTesting File Validation")
    print("=" * 50)
    
    processor = DocumentProcessor()
    
    # Test valid files
    test_cases = [
        ("document.pdf", 1024 * 1024, True),    # Valid PDF, 1MB
        ("report.docx", 5 * 1024 * 1024, True), # Valid DOCX, 5MB  
        ("notes.txt", 1024, True),              # Valid TXT, 1KB
        ("readme.md", 512, True),               # Valid MD, 512B
        ("large.pdf", 15 * 1024 * 1024, False), # Too large PDF, 15MB
        ("script.js", 1024, False),             # Unsupported format
    ]
    
    for filename, size, expected in test_cases:
        result = processor.validate_file(filename, size)
        status = "OK" if result == expected else "FAIL"
        print(f"{status} {filename} ({size // (1024*1024)}MB): {result}")


async def main():
    """Main test function"""
    
    print("Starting Marker Integration Tests")
    print("=" * 60)
    
    try:
        # Run tests
        await test_marker_integration()
        await test_file_validation()
        
        print("\n🎉 All tests completed!")
        print("\nNext Steps:")
        print("1. Install marker: pip install marker-pdf")
        print("2. Test with actual PDF files")
        print("3. Check extracted content in 'test_extracted_content' directory")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())