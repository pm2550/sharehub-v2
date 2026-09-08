"""应用配置管理"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
from typing import Set


class Settings(BaseSettings):
    """应用配置"""

    # 基础配置
    APP_NAME: str = "PM ShareHub"
    APP_DIR: Path = Path("/data/sharehub")

    # 安全配置（无默认值，强制配置）
    SESSION_SECRET: str
    ADMIN_TOKEN: str

    # 数据库配置
    DATABASE_PATH: str = "/data/sharehub/data/app.db"

    # 媒体存储配置
    MEDIA_DIR: str = "/data/sharehub/data/media"  # 缩略图和旧视频/图片回退
    FILES_DIR: str = "/data2/files"  # 兼容旧 DB 记录的本地文件回退
    TMP_DIR: str = "/tmp/sharehub"  # 视频/图片处理临时目录 (tmpfs)

    # PM Drive (Cloudreve v4) 存储后端
    PMDRIVE_BASE_URL: str = "https://drive.pm2550.com"
    PMDRIVE_EMAIL: str = ""
    PMDRIVE_PASSWORD: str = ""
    PMDRIVE_ROOT_DIR: str = "cloudreve://my/sharehub"

    # AI 配置 — RunPod (主) + 本地 A1111 (备)
    RUNPOD_API_KEY: str = ""
    RUNPOD_ENDPOINT_ID: str = ""
    RUNPOD_DAILY_LIMIT: int = 10  # 每用户每天 RunPod 生成次数
    RUNPOD_TIMEOUT: int = 120  # RunPod 单次请求超时(秒)

    A1111_API_URL: str = "http://127.0.0.1:8188"
    AI_POLL_INTERVAL_SECONDS: float = 1.5
    AI_MAX_RETRIES: int = 3
    AI_DEFAULT_JOB_SECONDS: int = 50
    AI_JOB_HISTORY: int = 30
    AI_JOB_TIMEOUT_SECONDS: int = 3600

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
    SITE_TITLE: str = "PM ShareHub"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
