import os
import uuid
from pathlib import Path
from typing import Optional
from PIL import Image
import aiofiles
from fastapi import UploadFile, HTTPException, status

from app.core.config import settings
from app.core.logging import app_logger as logger


class FileUploadService:
    """Service for handling file uploads"""
    
    # Allowed image extensions
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    
    def __init__(self):
        self.upload_dir = Path("static/uploads/avatars")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    async def validate_image(self, file: UploadFile) -> None:
        """Validate uploaded image file"""
        # Check file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in self.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed types: {', '.join(self.ALLOWED_EXTENSIONS)}"
            )
        
        # Check file size
        file.file.seek(0, 2)  # Move to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > self.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: {self.MAX_FILE_SIZE / 1024 / 1024}MB"
            )
        
        # Verify it's a valid image
        try:
            image = Image.open(file.file)
            image.verify()
            file.file.seek(0)  # Reset after verification
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image file"
            )
    
    async def save_avatar(
        self, 
        file: UploadFile, 
        user_id: int
    ) -> str:
        """Save user avatar and return URL"""
        await self.validate_image(file)
        
        # Generate unique filename
        file_ext = Path(file.filename).suffix.lower()
        filename = f"{user_id}_{uuid.uuid4()}{file_ext}"
        file_path = self.upload_dir / filename
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Process image (resize if needed)
        await self.process_avatar(file_path)
        
        # Return URL
        avatar_url = f"/static/uploads/avatars/{filename}"
        
        logger.info(f"Avatar uploaded for user {user_id}: {avatar_url}")
        return avatar_url
    
    async def process_avatar(self, file_path: Path) -> None:
        """Process avatar image (resize, optimize)"""
        try:
            with Image.open(file_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = rgb_img
                
                # Resize if too large
                max_size = (400, 400)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Save optimized image
                img.save(file_path, optimize=True, quality=85)
                
        except Exception as e:
            logger.error(f"Error processing avatar: {e}")
    
    async def delete_avatar(self, avatar_url: str) -> bool:
        """Delete avatar file"""
        if not avatar_url or not avatar_url.startswith("/static/uploads/avatars/"):
            return False
        
        filename = avatar_url.split("/")[-1]
        file_path = self.upload_dir / filename
        
        try:
            if file_path.exists():
                os.remove(file_path)
                logger.info(f"Deleted avatar: {avatar_url}")
                return True
        except Exception as e:
            logger.error(f"Error deleting avatar: {e}")
        
        return False
    
    def get_default_avatar(self) -> str:
        """Get default avatar URL"""
        return "/static/images/default-avatar.png"


file_upload_service = FileUploadService()