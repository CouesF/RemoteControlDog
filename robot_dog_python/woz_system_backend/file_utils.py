"""
文件上传和处理工具模块
"""
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional
import logging

from .config import IMAGES_ROOT, UPLOADS_ROOT, MAX_FILE_SIZE, ALLOWED_IMAGE_EXTENSIONS

logger = logging.getLogger(__name__)


class FileHandler:
    def __init__(self):
        self.images_root = IMAGES_ROOT
        self.uploads_root = UPLOADS_ROOT
        
    def validate_image_file(self, filename: str, file_size: int) -> tuple[bool, str]:
        """验证图片文件"""
        # 检查文件大小
        if file_size > MAX_FILE_SIZE:
            return False, f"File size {file_size} exceeds maximum allowed size {MAX_FILE_SIZE}"
        
        # 检查文件扩展名
        file_ext = Path(filename).suffix.lower()
        if file_ext not in ALLOWED_IMAGE_EXTENSIONS:
            return False, f"File extension {file_ext} not allowed. Allowed: {ALLOWED_IMAGE_EXTENSIONS}"
        
        return True, "Valid"
    
    def generate_unique_filename(self, original_filename: str) -> str:
        """生成唯一的文件名"""
        file_ext = Path(original_filename).suffix.lower()
        unique_name = f"{uuid.uuid4()}{file_ext}"
        return unique_name
    
    async def save_participant_image(self, file_content: bytes, original_filename: str, 
                                   participant_id: str, image_type: str) -> tuple[bool, str, str]:
        """保存被试图片"""
        try:
            # 验证文件
            is_valid, message = self.validate_image_file(original_filename, len(file_content))
            if not is_valid:
                return False, message, ""
            
            # 生成文件名和路径
            filename = self.generate_unique_filename(original_filename)
            participant_dir = self.images_root / "participants" / participant_id
            participant_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = participant_dir / filename
            
            # 保存文件
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            # 生成访问URL
            relative_path = file_path.relative_to(self.images_root.parent)
            image_url = f"/static/{relative_path.as_posix()}"
            
            logger.info(f"Saved participant image: {file_path}")
            return True, "Image saved successfully", image_url
            
        except Exception as e:
            logger.error(f"Failed to save participant image: {e}")
            return False, f"Failed to save image: {str(e)}", ""
    
    async def save_target_image(self, file_content: bytes, original_filename: str, 
                              target_id: str, image_type: str) -> tuple[bool, str, str]:
        """保存目标点图片"""
        try:
            # 验证文件
            is_valid, message = self.validate_image_file(original_filename, len(file_content))
            if not is_valid:
                return False, message, ""
            
            # 生成文件名和路径
            filename = self.generate_unique_filename(original_filename)
            target_dir = self.images_root / "targets" / target_id
            target_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = target_dir / filename
            
            # 保存文件
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            # 生成访问URL
            relative_path = file_path.relative_to(self.images_root.parent)
            image_url = f"/static/{relative_path.as_posix()}"
            
            logger.info(f"Saved target image: {file_path}")
            return True, "Image saved successfully", image_url
            
        except Exception as e:
            logger.error(f"Failed to save target image: {e}")
            return False, f"Failed to save image: {str(e)}", ""
    
    def delete_image(self, image_url: str) -> tuple[bool, str]:
        """删除图片文件"""
        try:
            # 从URL解析文件路径
            if not image_url.startswith("/static/"):
                return False, "Invalid image URL"
            
            relative_path = image_url[8:]  # 移除 "/static/" 前缀
            file_path = self.images_root.parent / relative_path
            
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted image: {file_path}")
                return True, "Image deleted successfully"
            else:
                return False, "Image file not found"
                
        except Exception as e:
            logger.error(f"Failed to delete image: {e}")
            return False, f"Failed to delete image: {str(e)}"
    
    def delete_participant_images(self, participant_id: str) -> tuple[bool, str]:
        """删除被试的所有图片"""
        try:
            participant_dir = self.images_root / "participants" / participant_id
            if participant_dir.exists():
                shutil.rmtree(participant_dir)
                logger.info(f"Deleted participant images directory: {participant_dir}")
                return True, "All participant images deleted successfully"
            else:
                return True, "No images to delete"
                
        except Exception as e:
            logger.error(f"Failed to delete participant images: {e}")
            return False, f"Failed to delete participant images: {str(e)}"
    
    def delete_target_images(self, target_id: str) -> tuple[bool, str]:
        """删除目标点的所有图片"""
        try:
            target_dir = self.images_root / "targets" / target_id
            if target_dir.exists():
                shutil.rmtree(target_dir)
                logger.info(f"Deleted target images directory: {target_dir}")
                return True, "All target images deleted successfully"
            else:
                return True, "No images to delete"
                
        except Exception as e:
            logger.error(f"Failed to delete target images: {e}")
            return False, f"Failed to delete target images: {str(e)}"


# 全局文件处理器实例
file_handler = FileHandler()
