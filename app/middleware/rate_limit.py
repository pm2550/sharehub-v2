"""速率限制中间件"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from app.config import get_settings

settings = get_settings()

# 创建限流器实例
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri="memory://",
)


def get_limiter():
    """获取限流器实例"""
    return limiter


# 速率限制装饰器工厂
def rate_limit(limit: str):
    """
    创建速率限制装饰器

    用法：
    @rate_limit("5/minute")
    async def login(...):
        ...
    """
    def decorator(func):
        return limiter.limit(limit)(func)
    return decorator
