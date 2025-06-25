"""
WOZ系统后端配置文件
"""
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_ROOT = Path(__file__).parent

# 数据库配置
DATABASE_PATH = PROJECT_ROOT / "woz_system.db"

# 静态文件配置
STATIC_ROOT = PROJECT_ROOT / "static"
IMAGES_ROOT = STATIC_ROOT / "images"
UPLOADS_ROOT = STATIC_ROOT / "uploads"

# 确保目录存在
STATIC_ROOT.mkdir(exist_ok=True)
IMAGES_ROOT.mkdir(exist_ok=True)
(IMAGES_ROOT / "participants").mkdir(exist_ok=True)
(IMAGES_ROOT / "targets").mkdir(exist_ok=True)
UPLOADS_ROOT.mkdir(exist_ok=True)

# API配置
API_HOST = "0.0.0.0"
API_PORT = 8995
API_PREFIX = "/api"

# 文件上传配置
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}

# CORS配置
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

# 日志配置
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
