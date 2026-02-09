"""收藏路由"""

from fastapi import APIRouter, Request, Query, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
import sqlite3

from app.config import get_settings
from app.dependencies import require_auth, get_db_conn, get_current_user
from app.services.favorites import toggle_favorite, get_user_favorites, count_user_favorites
from app.services.posts import build_pagination

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.APP_DIR / "templates"))

router = APIRouter(tags=["favorites"])


def render(request: Request, template: str, context: dict, db: sqlite3.Connection):
    """渲染模板的辅助函数"""
    user = get_current_user(request, db)
    context.update({
        "request": request,
        "site_title": settings.SITE_TITLE,
        "current_user": user,
    })
    return templates.TemplateResponse(template, context)


@router.post("/post/{post_id}/favorite")
async def favorite_post(
    post_id: int,
    request: Request,
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """
    收藏/取消收藏帖子（toggle）

    返回JSON格式，支持AJAX调用
    """
    try:
        is_favorited = toggle_favorite(db, post_id, user["id"])
        db.commit()

        # 验证帖子存在
        post = db.execute(
            "SELECT id FROM posts WHERE id = ?", (post_id,)
        ).fetchone()

        if not post:
            raise HTTPException(status_code=404, detail="帖子不存在")

        return JSONResponse({
            "success": True,
            "favorited": is_favorited,
            "message": "已收藏" if is_favorited else "已取消收藏"
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=400)


@router.get("/favorites")
def favorites_page(
    request: Request,
    page: int = Query(1, ge=1),
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """我的收藏页面"""
    page_size = settings.FEED_PAGE_SIZE

    # 获取收藏列表
    posts = get_user_favorites(db, user["id"], limit=page_size, offset=(page - 1) * page_size)
    total = count_user_favorites(db, user["id"])

    # 构建分页
    pagination = build_pagination(page, total, page_size)

    return render(
        request,
        "favorites.html",
        {
            "active": "favorites",
            "page_title": "我的收藏",
            "page_desc": "收藏的精彩内容",
            "posts": posts,
            "pagination": pagination,
            "total_count": total,
        },
        db,
    )
