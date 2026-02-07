"""标签路由"""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import sqlite3

from app.config import get_settings
from app.dependencies import get_db_conn, get_current_user
from app.services.tags import get_posts_by_tag, get_popular_tags, get_tag_by_slug

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.APP_DIR / "templates"))

router = APIRouter(tags=["tags"])


def render(request: Request, template: str, context: dict, db = None):
    base = {
        "request": request,
        "site_title": settings.SITE_TITLE,
        "current_user": get_current_user(request, db) if db else None,
    }
    base.update(context)
    return templates.TemplateResponse(template, base)


@router.get("/tag/{slug}")
def tag_page(
    request: Request,
    slug: str,
    page: int = 1,
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """标签页面 - 显示带有该标签的所有帖子"""
    tag = get_tag_by_slug(db, slug)
    if not tag:
        return render(request, "error.html", {
            "error": "标签不存在",
            "message": f"未找到标签: {slug}"
        }, db)

    posts = get_posts_by_tag(db, tag["id"], limit=20, offset=(page - 1) * 20)

    # 计算总页数
    total = db.execute(
        "SELECT COUNT(*) FROM post_tags WHERE tag_id = ?",
        (tag["id"],)
    ).fetchone()[0]
    total_pages = (total + 19) // 20

    return render(
        request,
        "tag.html",
        {
            "active": "",
            "tag": tag,
            "posts": posts,
            "pagination": {
                "page": page,
                "total_pages": total_pages,
                "has_prev": page > 1,
                "has_next": page < total_pages,
            }
        },
        db,
    )


@router.get("/tags/popular")
def popular_tags_api(
    db: sqlite3.Connection = Depends(get_db_conn),
    limit: int = 20
):
    """获取热门标签 API"""
    tags = get_popular_tags(db, limit=limit)
    return {"tags": [dict(t) for t in tags]}
