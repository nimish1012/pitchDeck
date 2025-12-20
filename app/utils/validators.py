from typing import List, Dict, Any, Optional
import re
from pathlib import Path

class PresentationValidator:
    """Validate presentation requests and data"""
    
    # Supported file formats
    ALLOWED_FILE_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md'}
    
    # File size limits (in bytes)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Text limits
    MAX_PROMPT_LENGTH = 1000
    MAX_TITLE_LENGTH = 200
    MAX_ADDITIONAL_TEXT_LENGTH = 2000
    
    # Slide limits
    MAX_SLIDES = 50
    MIN_SLIDES = 1
    
    # Output formats
    ALLOWED_OUTPUT_FORMATS = {'pptx', 'pdf', 'html'}
    
    @classmethod
    def validate_file_upload(cls, filename: str, file_size: int) -> tuple[bool, str]:
        """Validate uploaded file"""
        # Check filename
        if not filename:
            return False, "Filename is required"
        
        # Check file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in cls.ALLOWED_FILE_EXTENSIONS:
            return False, f"Unsupported file format. Allowed: {', '.join(cls.ALLOWED_FILE_EXTENSIONS)}"
        
        # Check file size
        if file_size > cls.MAX_FILE_SIZE:
            return False, f"File too large. Maximum size: {cls.MAX_FILE_SIZE // (1024*1024)}MB"
        
        return True, "Valid"
    
    @classmethod
    def validate_prompt(cls, prompt: str) -> tuple[bool, str]:
        """Validate prompt text"""
        if not prompt or not prompt.strip():
            return False, "Prompt cannot be empty"
        
        if len(prompt) > cls.MAX_PROMPT_LENGTH:
            return False, f"Prompt too long. Maximum length: {cls.MAX_PROMPT_LENGTH} characters"
        
        return True, "Valid"
    
    @classmethod
    def validate_title(cls, title: Optional[str]) -> tuple[bool, str]:
        """Validate presentation title"""
        if title is None:
            return True, "Valid"  # Title is optional
        
        if len(title) > cls.MAX_TITLE_LENGTH:
            return False, f"Title too long. Maximum length: {cls.MAX_TITLE_LENGTH} characters"
        
        return True, "Valid"
    
    @classmethod
    def validate_additional_text(cls, additional_text: Optional[str]) -> tuple[bool, str]:
        """Validate additional text"""
        if additional_text is None:
            return True, "Valid"  # Additional text is optional
        
        if len(additional_text) > cls.MAX_ADDITIONAL_TEXT_LENGTH:
            return False, f"Additional text too long. Maximum length: {cls.MAX_ADDITIONAL_TEXT_LENGTH} characters"
        
        return True, "Valid"
    
    @classmethod
    def validate_slide_count(cls, max_slides: Optional[int]) -> tuple[bool, str]:
        """Validate slide count"""
        if max_slides is None:
            return True, "Valid"  # Will use default
        
        if not isinstance(max_slides, int):
            return False, "max_slides must be an integer"
        
        if max_slides < cls.MIN_SLIDES or max_slides > cls.MAX_SLIDES:
            return False, f"max_slides must be between {cls.MIN_SLIDES} and {cls.MAX_SLIDES}"
        
        return True, "Valid"
    
    @classmethod
    def validate_output_format(cls, output_format: str) -> tuple[bool, str]:
        """Validate output format"""
        if output_format not in cls.ALLOWED_OUTPUT_FORMATS:
            return False, f"Unsupported output format. Allowed: {', '.join(cls.ALLOWED_OUTPUT_FORMATS)}"
        
        return True, "Valid"
    
    @classmethod
    def validate_outline(cls, outline: List[Dict[str, Any]]) -> tuple[bool, str]:
        """Validate outline structure"""
        if not outline:
            return False, "Outline cannot be empty"
        
        if len(outline) > cls.MAX_SLIDES:
            return False, f"Outline too long. Maximum slides: {cls.MAX_SLIDES}"
        
        for i, item in enumerate(outline):
            if not isinstance(item, dict):
                return False, f"Outline item {i+1} must be a dictionary"
            
            # Check required fields
            if 'title' not in item:
                return False, f"Outline item {i+1} must have a 'title' field"
            
            # Validate title
            title = item['title']
            if not isinstance(title, str) or not title.strip():
                return False, f"Outline item {i+1} title must be a non-empty string"
            
            # Optional content field
            if 'content' in item:
                content = item['content']
                if not isinstance(content, list):
                    return False, f"Outline item {i+1} content must be a list"
        
        return True, "Valid"
    
    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove or replace unsafe characters
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Limit length
        if len(safe_filename) > 100:
            name, ext = os.path.splitext(safe_filename)
            safe_filename = name[:100-len(ext)] + ext
        
        return safe_filename