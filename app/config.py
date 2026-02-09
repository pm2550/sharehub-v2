"""应用配置管理"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
from typing import Set


class Settings(BaseSettings):
    """应用配置"""

    # 基础配置
    APP_NAME: str = "ShareHub"
    APP_DIR: Path = Path("/data/sharehub")

    # 安全配置（无默认值，强制配置）
    SESSION_SECRET: str
    ADMIN_TOKEN: str

    # 数据库配置
    DATABASE_PATH: str = "/data/sharehub/data/app.db"

    # 媒体存储配置
    MEDIA_DIR: str = "/data/sharehub/data/media"

    # AI 配置
    A1111_API_URL: str = "http://127.0.0.1:8188"
    AI_POLL_INTERVAL_SECONDS: float = 1.5
    AI_MAX_RETRIES: int = 3
    AI_DEFAULT_JOB_SECONDS: int = 50
    AI_JOB_HISTORY: int = 30
    AI_JOB_TIMEOUT_SECONDS: int = 3600  # 仅作安全网，实际靠检测 A1111 状态判断卡住

    # 文件上传限制
    MAX_IMAGE_SIZE_MB: int = 20
    MAX_VIDEO_SIZE_MB: int = 200
    ALLOWED_IMAGE_EXT: Set[str] = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    ALLOWED_VIDEO_EXT: Set[str] = {".mp4", ".webm", ".mov", ".m4v"}
    MAX_VIDEO_DURATION_SECONDS: int = 120  # 视频最长2分钟

    # 缩略图尺寸
    THUMBNAIL_SIZE_SM: tuple = (300, 300)
    THUMBNAIL_SIZE_MD: tuple = (600, 600)

    # Session 配置
    SESSION_MAX_AGE: int = 2592000  # 30 days

    # 分页配置
    FEED_PAGE_SIZE: int = 18
    USER_PAGE_SIZE: int = 18
    ME_PAGE_SIZE: int = 8

    # 速率限制
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_UPLOAD: str = "10/minute"
    RATE_LIMIT_AI: str = "3/minute"
    RATE_LIMIT_DEFAULT: str = "60/minute"

    # 网站标题
    SITE_TITLE: str = "ShareHub"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
