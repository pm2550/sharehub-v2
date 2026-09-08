"""用户中心路由 - 我的主页、资料编辑、密码修改"""

from fastapi import APIRouter, Request, Form, Query, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import sqlite3

from app.config import get_settings
from app.dependencies import require_auth, get_db_conn, get_current_user
from app.services.auth import update_profile, update_password, verify_password
from app.services.ai_queue import list_jobs

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.APP_DIR / "templates"))

router = APIRouter(tags=["users"])


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


@router.get("/me")
def me_page(
    request: Request,
    page: int = Query(1, ge=1),
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """我的中心"""
    total = int(db.execute("SELECT COUNT(*) FROM posts WHERE user_id = ?", (user["id"],)).fetchone()[0])
    pagination = build_pagination(page, total, settings.ME_PAGE_SIZE)

    my_posts = db.execute(
        """
        SELECT p.id, p.title, p.description, p.media_type, p.filename, p.source, p.likes, p.created_at
        FROM posts p
        WHERE p.user_id = ?
        ORDER BY p.id DESC
        LIMIT ? OFFSET ?
        """,
        (user["id"], settings.ME_PAGE_SIZE, (pagination["page"] - 1) * settings.ME_PAGE_SIZE),
    ).fetchall()

    my_comments = db.execute(
        """
        SELECT c.id, c.post_id, c.content, c.created_at,
               COALESCE(p.title, '(帖子已删除)') AS post_title
        FROM comments c
        LEFT JOIN posts p ON p.id = c.post_id
        WHERE c.user_id = ?
        ORDER BY c.id DESC
        LIMIT 100
        """,
        (user["id"],),
    ).fetchall()

    my_jobs = list_jobs(db, limit=30, only_user_id=user["id"])
    queue_active = [j for j in my_jobs if j["status"] in ("pending", "running")]

    return render(
        request,
        "me.html",
        {
            "active": "me",
            "my_posts": my_posts,
            "my_comments": my_comments,
            "my_jobs": my_jobs,
            "queue_active_count": len(queue_active),
            "pagination": pagination,
            "profile_msg": "",
            "pwd_msg": "",
        },
        db,
    )


@router.post("/me/profile")
def update_profile_route(
    request: Request,
    display_name: str = Form(...),
    bio: str = Form(""),
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """更新用户资料"""
    name = display_name.strip()
    if len(name) < 2 or len(name) > 32:
        raise HTTPException(status_code=400, detail="昵称长度需在 2-32")

    update_profile(db, user["id"], name, bio)
    return RedirectResponse(url="/me", status_code=303)


@router.post("/me/password")
def update_password_route(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """修改密码"""
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")

    row = db.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
    if not row or not verify_password(old_password, row["password_hash"]):
        raise HTTPException(status_code=400, detail="旧密码错误")

    update_password(db, user["id"], new_password)
    return RedirectResponse(url="/me", status_code=303)
