"""页面路由 - 首页、图片、视频、AI、帖子详情、用户主页"""

from fastapi import APIRouter, Request, Query, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from app.config import get_settings
from app.dependencies import get_db_conn, get_current_user
from app.services.posts import query_posts, count_posts

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.APP_DIR / "templates"))

router = APIRouter(tags=["pages"])


def render(request: Request, template: str, context: dict, db: sqlite3.Connection = None):
    """渲染模板"""
    base = {
        "request": request,
        "site_title": settings.SITE_TITLE,
        "current_user": get_current_user(request, db) if db else None,
    }
    base.update(context)
    return templates.TemplateResponse(template, base)


def build_pagination(page: int, total: int, page_size: int) -> dict:
    """构建分页信息"""
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = 0 if total == 0 else (page - 1) * page_size + 1
    end = min(total, page * page_size)
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1,
        "start": start,
        "end": end,
    }


def safe_back(request: Request, default_path: str) -> str:
    """安全的返回URL"""
    referer = (request.headers.get("referer") or "").strip()
    if not referer:
        return default_path
    try:
        parsed = urlparse(referer)
    except Exception:
        return default_path

    # 只接受同域名的 referer
    if parsed.netloc and parsed.hostname != request.url.hostname:
        return default_path

    path = parsed.path or "/"
    if path.startswith("/post/") or path in ("/login", "/register"):
        return default_path

    query = f"?{parsed.query}" if parsed.query else ""
    fragment = f"#{parsed.fragment}" if parsed.fragment else ""
    return f"{path}{query}{fragment}"


@router.get("/")
def home(request: Request, db: sqlite3.Connection = Depends(get_db_conn)):
    """首页"""
    stats = {
        "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "posts": db.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
        "images": db.execute("SELECT COUNT(*) FROM posts WHERE media_type='image' AND source='upload'").fetchone()[0],
        "videos": db.execute("SELECT COUNT(*) FROM posts WHERE media_type='video'").fetchone()[0],
        "ai": db.execute("SELECT COUNT(*) FROM posts WHERE source='ai'").fetchone()[0],
    }

    recent_images = query_posts(db, "p.media_type='image' AND p.source='upload'", limit=12)
    recent_videos = query_posts(db, "p.media_type='video'", limit=12)
    recent_ai = query_posts(db, "p.source='ai'", limit=12)

    return render(
        request,
        "home.html",
        {
            "active": "home",
            "stats": stats,
            "recent_images": recent_images,
            "recent_videos": recent_videos,
            "recent_ai": recent_ai,
        },
        db,
    )


@router.get("/images")
def images_page(
    request: Request,
    page: int = Query(1, ge=1),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """图片广场"""
    where = "p.media_type='image' AND p.source='upload'"
    total = count_posts(db, where)
    pagination = build_pagination(page, total, settings.FEED_PAGE_SIZE)
    posts = query_posts(db, where, limit=settings.FEED_PAGE_SIZE, offset=(pagination["page"] - 1) * settings.FEED_PAGE_SIZE)

    return render(
        request,
        "feed.html",
        {
            "active": "images",
            "page_title": "图片广场",
            "page_desc": "所有用户上传的图片",
            "posts": posts,
            "pagination": pagination,
        },
        db,
    )


@router.get("/videos")
def videos_page(
    request: Request,
    page: int = Query(1, ge=1),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """视频广场"""
    where = "p.media_type='video'"
    total = count_posts(db, where)
    pagination = build_pagination(page, total, settings.FEED_PAGE_SIZE)
    posts = query_posts(db, where, limit=settings.FEED_PAGE_SIZE, offset=(pagination["page"] - 1) * settings.FEED_PAGE_SIZE)

    return render(
        request,
        "feed.html",
        {
            "active": "videos",
            "page_title": "视频广场",
            "page_desc": "所有用户上传的视频",
            "posts": posts,
            "pagination": pagination,
        },
        db,
    )


@router.get("/user/{username}")
def user_page(
    username: str,
    request: Request,
    page: int = Query(1, ge=1),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """用户公开主页"""
    user = db.execute(
        "SELECT id, username, display_name, bio, created_at FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    where = "p.user_id = ?"
    params = (user["id"],)
    total = count_posts(db, where, params)
    pagination = build_pagination(page, total, settings.USER_PAGE_SIZE)
    posts = query_posts(
        db,
        where,
        params,
        limit=settings.USER_PAGE_SIZE,
        offset=(pagination["page"] - 1) * settings.USER_PAGE_SIZE,
    )

    return render(
        request,
        "user.html",
        {
            "active": "",
            "profile_user": user,
            "posts": posts,
            "pagination": pagination,
        },
        db,
    )


@router.get("/post/{post_id}")
def post_detail(
    post_id: int,
    request: Request,
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """帖子详情页"""
    user = get_current_user(request, db)

    post = db.execute(
        """
        SELECT p.*, COALESCE(u.display_name, u.username, 'legacy') AS author,
               COALESCE(u.username, 'legacy') AS author_username
        FROM posts p
        LEFT JOIN users u ON u.id = p.user_id
        WHERE p.id = ?
        """,
        (post_id,),
    ).fetchone()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comments = db.execute(
        """
        SELECT COALESCE(u.display_name, u.username, c.author, 'legacy') AS author,
               COALESCE(u.username, 'legacy') AS author_username,
               c.content,
               c.created_at
        FROM comments c
        LEFT JOIN users u ON u.id = c.user_id
        WHERE c.post_id = ?
        ORDER BY c.id DESC
        """,
        (post_id,),
    ).fetchall()

    liked = 0
    if user:
        row = db.execute(
            "SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?",
            (post_id, user["id"]),
        ).fetchone()
        liked = 1 if row else 0

    is_owner = bool(user and post["user_id"] and user["id"] == post["user_id"])
    is_admin = bool(user and user["is_admin"])

    default_back = "/images"
    if post["source"] == "ai":
        default_back = "/ai"
    elif post["media_type"] == "video":
        default_back = "/videos"

    back_url = safe_back(request, default_back)

    return render(
        request,
        "post.html",
        {
            "active": "",
            "post": post,
            "comments": comments,
            "is_owner": is_owner,
            "is_admin": is_admin,
            "liked": liked,
            "back_url": back_url,
        },
        db,
    )


@router.get("/media/{filename}")
def media_file(filename: str):
    """提供媒体文件"""
    import os
    safe_name = os.path.basename(filename)
    file_path = Path(settings.MEDIA_DIR) / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)
