"""请求日志中间件"""

import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("sharehub.requests")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """记录所有HTTP请求的中间件"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()

        # 处理请求
        response = await call_next(request)

        # 计算耗时
        duration = time.perf_counter() - start_time

        # 记录日志
        logger.info(
            f"{request.method} {request.url.path} {response.status_code} {duration:.3f}s"
        )

        return response
