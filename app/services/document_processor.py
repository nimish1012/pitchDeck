import os
import tempfile
import asyncio
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
import base64
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

# Marker imports for advanced document processing
try:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered
    MARKER_AVAILABLE = True
except ImportError:
    MARKER_AVAILABLE = False
    logger.warning("marker library not available. Install with: pip install marker-pdf")


class DocumentProcessor:
    """Handle document file processing with advanced marker integration"""
    
    def __init__(self, output_dir: str = "extracted_content"):
        self.supported_formats = {'.pdf', '.docx', '.txt', '.md'}
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize marker converter if available
        self.converter = None
        if MARKER_AVAILABLE:
            try:
                self.converter = PdfConverter(
                    artifact_dict=create_model_dict(),
                )
                logger.info("Marker PDF converter initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize marker converter: {e}")
                self.converter = None
    
    def validate_file(self, filename: str, file_size: int) -> bool:
        """Validate uploaded file"""
        # Check file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in self.supported_formats:
            return False
        
        # Check file size
        if file_size > self.max_file_size:
            return False
        
        return True
    
    async def process_document(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Process uploaded document and extract content with metadata"""
        file_ext = Path(filename).suffix.lower()
        
        if file_ext == '.txt' or file_ext == '.md':
            return await self._process_text_file(file_content, filename)
        elif file_ext == '.pdf':
            return await self._process_pdf_file(file_content, filename)
        elif file_ext == '.docx':
            return await self._process_docx_file(file_content, filename)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")
    
    async def _process_text_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Process text-based files"""
        try:
            # Try UTF-8 first
            content = file_content.decode('utf-8')
        except UnicodeDecodeError:
            # Fallback to other encodings
            try:
                content = file_content.decode('latin-1')
            except UnicodeDecodeError:
                content = file_content.decode('utf-8', errors='ignore')
        
        # Convert to markdown format
        markdown_content = self._text_to_markdown(content, filename)
        
        return {
            'content': markdown_content,
            'images': [],
            'metadata': {
                'filename': filename,
                'format': 'text',
                'extracted_at': datetime.now().isoformat(),
                'word_count': len(content.split()),
                'character_count': len(content)
            }
        }
    
    async def _process_pdf_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Process PDF files using marker library"""
        if not MARKER_AVAILABLE:
            return {
                'content': "PDF processing requires marker library. Please install: pip install marker-pdf",
                'images': [],
                'metadata': {
                    'filename': filename,
                    'format': 'pdf',
                    'extracted_at': datetime.now().isoformat(),
                    'error': 'marker library not available'
                }
            }
        
        if self.converter is None:
            return {
                'content': "Failed to initialize marker converter. Please check your installation.",
                'images': [],
                'metadata': {
                    'filename': filename,
                    'format': 'pdf',
                    'extracted_at': datetime.now().isoformat(),
                    'error': 'converter initialization failed'
                }
            }
        
        try:
            # Save PDF to temporary file
            temp_pdf_path = self.save_temp_file(file_content, filename)
            
            try:
                # Use marker to convert PDF
                rendered = self.converter(temp_pdf_path)
                text, _, images = text_from_rendered(rendered)
                
                # Process and save images
                extracted_images = await self._process_extracted_images(images, filename)
                
                return {
                    'content': text,
                    'images': extracted_images,
                    'metadata': {
                        'filename': filename,
                        'format': 'pdf',
                        'extracted_at': datetime.now().isoformat(),
                        'word_count': len(text.split()),
                        'character_count': len(text),
                        'images_extracted': len(extracted_images),
                        'processor': 'marker'
                    }
                }
            
            finally:
                # Clean up temporary file
                self.cleanup_temp_file(temp_pdf_path)
                
        except Exception as e:
            return {
                'content': f"Error processing PDF: {str(e)}",
                'images': [],
                'metadata': {
                    'filename': filename,
                    'format': 'pdf',
                    'extracted_at': datetime.now().isoformat(),
                    'error': str(e)
                }
            }
    
    async def _process_docx_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Process DOCX files - placeholder for DOCX processing"""
        # In a real implementation, you would use libraries like python-docx
        # For now, returning placeholder text
        content = "DOCX content would be extracted here. Implement DOCX processing with python-docx library."
        
        return {
            'content': content,
            'images': [],
            'metadata': {
                'filename': filename,
                'format': 'docx',
                'extracted_at': datetime.now().isoformat(),
                'word_count': len(content.split()),
                'character_count': len(content)
            }
        }
    
    async def _process_extracted_images(self, images: List, filename: str) -> List[Dict[str, Any]]:
        """Process and save images extracted by marker"""
        extracted_images = []
        
        if not images:
            return extracted_images
        
        # Create subdirectory for this file's images
        file_id = str(uuid.uuid4())[:8]
        image_dir = self.output_dir / f"{Path(filename).stem}_{file_id}_images"
        image_dir.mkdir(exist_ok=True)
        
        for i, image in enumerate(images):
            try:
                # Generate image filename
                image_filename = f"image_{i+1:03d}.png"
                image_path = image_dir / image_filename
                
                # Save image (assuming image is in bytes format)
                if hasattr(image, 'tobytes'):
                    # If it's a PIL Image or similar
                    image.save(image_path)
                elif isinstance(image, bytes):
                    # If it's raw bytes
                    with open(image_path, 'wb') as f:
                        f.write(image)
                else:
                    # Try to convert to bytes
                    image_bytes = bytes(image)
                    with open(image_path, 'wb') as f:
                        f.write(image_bytes)
                
                # Create image metadata
                image_info = {
                    'filename': image_filename,
                    'path': str(image_path.relative_to(self.output_dir)),
                    'full_path': str(image_path.absolute()),
                    'size_bytes': image_path.stat().st_size if image_path.exists() else 0,
                    'index': i + 1
                }
                
                extracted_images.append(image_info)
                
            except Exception as e:
                logger.error(f"Error processing image {i}: {e}")
                continue
        
        return extracted_images
    
    def _text_to_markdown(self, content: str, filename: str) -> str:
        """Convert plain text to markdown format"""
        # Basic markdown conversion for text files
        lines = content.split('\n')
        markdown_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                # Simple heuristic: if line looks like a header (short, no punctuation)
                if len(line) < 100 and not line.endswith(('.', '!', '?', ':', ';')):
                    markdown_lines.append(f"## {line}")
                else:
                    markdown_lines.append(line)
            else:
                markdown_lines.append("")
        
        return '\n'.join(markdown_lines)
    
    def save_temp_file(self, file_content: bytes, filename: str) -> str:
        """Save file content to temporary location"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as temp_file:
            temp_file.write(file_content)
            return temp_file.name
    
    def cleanup_temp_file(self, file_path: str):
        """Clean up temporary file"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except OSError:
            pass  # Ignore cleanup errors
    
    def get_extraction_summary(self, extraction_result: Dict[str, Any]) -> str:
        """Generate a summary of the extraction results"""
        metadata = extraction_result.get('metadata', {})
        images = extraction_result.get('images', [])
        
        summary = f"""
# Document Extraction Summary

**File:** {metadata.get('filename', 'Unknown')}
**Format:** {metadata.get('format', 'Unknown')}
**Extracted At:** {metadata.get('extracted_at', 'Unknown')}
**Processor:** {metadata.get('processor', 'Unknown')}

## Content Statistics
- **Word Count:** {metadata.get('word_count', 0)}
- **Character Count:** {metadata.get('character_count', 0)}
- **Images Extracted:** {len(images)}

## Images
"""
        
        if images:
            for img in images:
                summary += f"- {img['filename']} ({img['size_bytes']} bytes)\n"
        else:
            summary += "- No images extracted\n"
        
        if metadata.get('error'):
            summary += f"\n**Error:** {metadata['error']}\n"
        
        return summary