"""ShareHub 主应用

这是重构后的应用入口。当前阶段它会导入原有的 app.py 中的路由，
逐步迁移到新的模块化结构。
"""

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.db.migrations import run_migrations
from app.workers.ai_worker import start_ai_worker, stop_ai_worker
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.rate_limit import limiter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger("sharehub")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    settings = get_settings()

    logger.info(f"Starting {settings.APP_NAME}...")

    # 运行数据库迁移
    logger.info("Running database migrations...")
    run_migrations(settings.DATABASE_PATH)

    # 启动AI Worker（RunPod 主 + 本地 A1111 备）
    logger.info("Starting AI worker...")
    start_ai_worker(
        db_path=settings.DATABASE_PATH,
        media_dir=settings.MEDIA_DIR,
        api_url=settings.A1111_API_URL,
        poll_interval=settings.AI_POLL_INTERVAL_SECONDS,
        max_retries=settings.AI_MAX_RETRIES,
        job_timeout=settings.AI_JOB_TIMEOUT_SECONDS,
        runpod_api_key=settings.RUNPOD_API_KEY,
        runpod_endpoint_id=settings.RUNPOD_ENDPOINT_ID,
        runpod_daily_limit=settings.RUNPOD_DAILY_LIMIT,
        runpod_timeout=settings.RUNPOD_TIMEOUT,
    )

    logger.info(f"{settings.APP_NAME} started successfully!")

    yield

    # 关闭
    logger.info("Shutting down...")
    stop_ai_worker()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version="2.0.0",
        lifespan=lifespan,
    )

    # Session 中间件
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SESSION_SECRET,
        same_site="lax",
        https_only=False,
        max_age=settings.SESSION_MAX_AGE,
    )

    # 请求日志中间件
    app.add_middleware(RequestLoggingMiddleware)

    # 速率限制
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        """处理速率限制异常"""
        return JSONResponse(
            status_code=429,
            content={"error": "请求过于频繁，请稍后再试"}
        )

    # 静态文件
    app.mount("/static", StaticFiles(directory=str(settings.APP_DIR / "static")), name="static")
    app.mount("/media", StaticFiles(directory=settings.MEDIA_DIR), name="media")

    # 注册路由
    from app.routers import (
        auth, pages, upload, ai, comments, users, posts, likes,
        search, tags, follows, notifications, admin, api, prompts,
        favorites, messages
    )

    app.include_router(auth.router)
    app.include_router(pages.router)
    app.include_router(upload.router)
    app.include_router(ai.router)
    app.include_router(comments.router)
    app.include_router(users.router)
    app.include_router(posts.router)
    app.include_router(favorites.router)
    app.include_router(likes.router)
    app.include_router(search.router)
    app.include_router(tags.router)
    app.include_router(follows.router)
    app.include_router(messages.router)
    app.include_router(notifications.router)
    app.include_router(admin.router)
    app.include_router(api.router)
    app.include_router(prompts.router)

    logger.info("All routes registered successfully")

    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
