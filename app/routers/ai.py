"""AI生成路由"""

from fastapi import APIRouter, Request, Form, Query, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import sqlite3

from app.config import get_settings
from app.dependencies import require_auth, get_db_conn, get_current_user
from app.services.posts import query_posts, count_posts
from app.services.ai_queue import (
    submit_job, list_jobs, average_job_seconds,
    delete_ai_job, move_job_up, move_job_down
)
from app.services.auth import now_iso

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.APP_DIR / "templates"))

router = APIRouter(tags=["ai"])


def render(request: Request, template: str, context: dict, db = None):
    base = {
        "request": request,
        "site_title": settings.SITE_TITLE,
        "current_user": get_current_user(request, db) if db else None,
    }
    base.update(context)
    return templates.TemplateResponse(template, base)


def build_pagination(page: int, total: int, page_size: int) -> dict:
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


def safe_next(target: str) -> str:
    if not target or not target.startswith("/") or target.startswith("//"):
        return "/"
    return target


@router.get("/ai")
def ai_page(
    request: Request,
    page: int = Query(1, ge=1),
    queued: int = Query(0, ge=0),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """AI生成页面"""
    where = "p.source='ai'"
    total = count_posts(db, where)
    pagination = build_pagination(page, total, settings.FEED_PAGE_SIZE)
    posts = query_posts(db, where, limit=settings.FEED_PAGE_SIZE, offset=(pagination["page"] - 1) * settings.FEED_PAGE_SIZE)

    user = get_current_user(request, db)
    queue_jobs = list_jobs(db, limit=30)
    active_queue_jobs = [j for j in queue_jobs if j["status"] in ("running", "pending")]
    my_queue_jobs = list_jobs(db, limit=20, only_user_id=user["id"]) if user else []
    avg_seconds = average_job_seconds(db)

    return render(
        request,
        "ai.html",
        {
            "active": "ai",
            "page_title": "AI 生图",
            "page_desc": "A1111 生成并发布的图片",
            "posts": posts,
            "pagination": pagination,
            "queue_jobs": queue_jobs,
            "active_queue_jobs": active_queue_jobs,
            "my_queue_jobs": my_queue_jobs,
            "avg_seconds": avg_seconds,
            "queued": queued,
        },
        db,
    )


@router.post("/generate")
def generate_image(
    request: Request,
    prompt: str = Form(...),
    negative_prompt: str = Form(""),
    steps: int = Form(40),
    width: int = Form(768),
    height: int = Form(1024),
    next: str = Form("/ai"),
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """提交AI生成任务"""
    prompt = prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    safe_steps = max(1, min(60, steps))
    safe_width = max(256, min(1024, width))
    safe_height = max(256, min(1024, height))

    submit_job(
        db,
        user_id=user["id"],
        prompt=prompt[:2000],
        negative_prompt=negative_prompt[:2000],
        steps=safe_steps,
        width=safe_width,
        height=safe_height,
    )

    target = safe_next(next)
    if target == "/ai":
        target = "/ai?queued=1"
    return RedirectResponse(url=target, status_code=303)


@router.post("/ai/job/{job_id}/delete")
def delete_job(
    job_id: int,
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """删除AI任务（非running状态）"""
    success = delete_ai_job(db, job_id, user["id"])
    if not success:
        return JSONResponse(
            status_code=400,
            content={"error": "无法删除该任务（可能正在执行中或不属于你）"}
        )
    db.commit()
    return JSONResponse(content={"success": True, "message": "任务已删除"})


@router.post("/ai/job/{job_id}/move-up")
def move_up(
    job_id: int,
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """将任务在队列中上移"""
    success = move_job_up(db, job_id, user["id"])
    if not success:
        return JSONResponse(
            status_code=400,
            content={"error": "无法移动该任务"}
        )
    db.commit()
    return JSONResponse(content={"success": True, "message": "任务已上移"})


@router.post("/ai/job/{job_id}/move-down")
def move_down(
    job_id: int,
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """将任务在队列中下移"""
    success = move_job_down(db, job_id, user["id"])
    if not success:
        return JSONResponse(
            status_code=400,
            content={"error": "无法移动该任务"}
        )
    db.commit()
    return JSONResponse(content={"success": True, "message": "任务已下移"})
