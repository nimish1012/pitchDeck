import os
import tempfile
from typing import Optional
from pathlib import Path

class DocumentProcessor:
    """Handle document file processing"""
    
    def __init__(self):
        self.supported_formats = {'.pdf', '.docx', '.txt', '.md'}
        self.max_file_size = 10 * 1024 * 1024  # 10MB
    
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
    
    async def process_document(self, file_content: bytes, filename: str) -> str:
        """Process uploaded document and extract text content"""
        file_ext = Path(filename).suffix.lower()
        
        if file_ext == '.txt' or file_ext == '.md':
            return self._process_text_file(file_content)
        elif file_ext == '.pdf':
            return await self._process_pdf_file(file_content)
        elif file_ext == '.docx':
            return await self._process_docx_file(file_content)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")
    
    def _process_text_file(self, file_content: bytes) -> str:
        """Process text-based files"""
        try:
            # Try UTF-8 first
            return file_content.decode('utf-8')
        except UnicodeDecodeError:
            # Fallback to other encodings
            try:
                return file_content.decode('latin-1')
            except UnicodeDecodeError:
                return file_content.decode('utf-8', errors='ignore')
    
    async def _process_pdf_file(self, file_content: bytes) -> str:
        """Process PDF files - placeholder for PDF processing"""
        # In a real implementation, you would use libraries like PyPDF2, pdfplumber, etc.
        # For now, returning placeholder text
        return "PDF content would be extracted here. Implement PDF processing with libraries like PyPDF2 or pdfplumber."
    
    async def _process_docx_file(self, file_content: bytes) -> str:
        """Process DOCX files - placeholder for DOCX processing"""
        # In a real implementation, you would use libraries like python-docx
        # For now, returning placeholder text
        return "DOCX content would be extracted here. Implement DOCX processing with python-docx library."
    
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