# Marker Integration Documentation

## Overview

This document describes the integration of the [marker](https://github.com/datalab-to/marker) library into the presentation generation system for advanced document processing capabilities.

## What is Marker?

Marker is an advanced document processing library that provides:

- **Superior PDF to Markdown conversion**: Extracts text, images, and formatting from PDF documents
- **Image extraction**: Automatically extracts and saves images from documents
- **Layout preservation**: Maintains document structure and formatting
- **Multiple format support**: Works with PDFs and other document formats

## Integration Changes

### 1. Dependencies Added

Added to `requirements.txt`:
```txt
marker-pdf==0.2.7
```

### 2. Document Processor Updates

The `DocumentProcessor` class in `app/services/document_processor.py` has been enhanced with:

#### New Features:
- **Marker Integration**: Uses `PdfConverter` from marker for PDF processing
- **Image Extraction**: Automatically extracts and saves images from documents
- **Markdown Output**: Converts all documents to markdown format
- **Metadata Extraction**: Captures document metadata (word count, processing time, etc.)
- **Structured Output**: Returns dictionary with content, images, and metadata

#### Key Methods:
- `process_document()`: Enhanced to return structured data
- `_process_pdf_file()`: Uses marker for PDF processing
- `_process_extracted_images()`: Handles image extraction and storage
- `get_extraction_summary()`: Generates summary reports

### 3. API Updates

Updated `app/api/endpoints/presentations.py`:
- Modified to handle new document processor output format
- Extracts content, images, and metadata from processing results
- Passes extracted data to presentation generator

### 4. Schema Updates

Enhanced `app/models/request_schemas.py`:
- Added `extracted_images` field to `DocumentPresentationRequest`
- Added `document_metadata` field to `DocumentPresentationRequest`

## Usage Examples

### Basic Document Processing

```python
from app.services.document_processor import DocumentProcessor

# Initialize processor
processor = DocumentProcessor(output_dir="extracted_content")

# Process a document
with open("document.pdf", "rb") as f:
    file_content = f.read()

result = await processor.process_document(file_content, "document.pdf")

# Access results
content = result['content']          # Markdown content
images = result['images']            # List of extracted images
metadata = result['metadata']        # Document metadata

# Generate summary
summary = processor.get_extraction_summary(result)
print(summary)
```

### API Usage

```bash
curl -X POST "http://localhost:8000/presentations/document" \
  -F "file=@document.pdf" \
  -F "title=My Presentation" \
  -F "max_slides=10"
```

The API now returns:
- Enhanced presentation data with extracted images
- Document metadata for better presentation generation
- Structured content in markdown format

## File Structure

After processing, the system creates:

```
extracted_content/
├── document_name_uuid_images/
│   ├── image_001.png
│   ├── image_002.png
│   └── ...
└── ...
```

## Error Handling

The integration includes robust error handling:

- **Graceful degradation**: Falls back to basic processing if marker is unavailable
- **Error reporting**: Returns detailed error information in metadata
- **Temporary file cleanup**: Automatically cleans up temporary files
- **Validation**: Maintains existing file validation rules

## Configuration

### Environment Variables

No additional environment variables required. Marker downloads models automatically on first use.

### Optional Configuration

```python
# Custom output directory
processor = DocumentProcessor(output_dir="custom_extraction_path")

# Larger file support
processor.max_file_size = 20 * 1024 * 1024  # 20MB
```

## Testing

Test the integration with:

```bash
python test_marker_simple.py
```

This script validates:
- File format support
- Image extraction
- Markdown conversion
- Metadata extraction
- Error handling

## Benefits

1. **Better PDF Processing**: Superior text extraction compared to basic PDF libraries
2. **Image Preservation**: Automatically extracts and stores images from documents
3. **Structured Output**: Returns organized data for downstream processing
4. **Backward Compatibility**: Existing code continues to work
5. **Enhanced Presentations**: More content and images for better presentation generation

## Troubleshooting

### Common Issues

1. **Marker not available**:
   ```bash
   pip install marker-pdf
   ```

2. **Large model downloads**: First run downloads ML models (~1GB)
3. **Memory usage**: Marker is resource-intensive for large documents

### Performance Tips

- Use smaller documents for faster processing
- Monitor memory usage with large PDFs
- Consider batch processing for multiple documents

## Future Enhancements

- Support for more document formats (DOCX, HTML)
- Batch processing capabilities
- Caching for frequently processed documents
- Progress tracking for long operations
- Custom model loading for domain-specific documents