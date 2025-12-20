import os
import aiofiles
from typing import Optional
from pathlib import Path
import uuid

class FileHandler:
    """Handle file operations for the presentation generator"""
    
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)
    
    async def save_uploaded_file(self, file_content: bytes, filename: str) -> str:
        """Save uploaded file and return the file path"""
        # Generate unique filename to avoid conflicts
        file_ext = Path(filename).suffix
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        file_path = self.upload_dir / unique_filename
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        return str(file_path)
    
    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes"""
        return os.path.getsize(file_path)
    
    def delete_file(self, file_path: str) -> bool:
        """Delete file and return success status"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        except OSError:
            pass
        return False
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """Clean up files older than specified hours"""
        import time
        
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for file_path in self.upload_dir.iterdir():
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    try:
                        file_path.unlink()
                    except OSError:
                        pass  # Ignore deletion errors