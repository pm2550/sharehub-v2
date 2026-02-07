"""搜索路由"""

from fastapi import APIRouter, Request, Query, Depends
from fastapi.templating import Jinja2Templates
import sqlite3

from app.config import get_settings
from app.dependencies import get_db_conn, get_current_user
from app.services.search import search_all

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.APP_DIR / "templates"))

router = APIRouter(tags=["search"])


def render(request: Request, template: str, context: dict, db = None):
    base = {
        "request": request,
        "site_title": settings.SITE_TITLE,
        "current_user": get_current_user(request, db) if db else None,
    }
    base.update(context)
    return templates.TemplateResponse(template, base)


@router.get("/search")
def search_page(
    request: Request,
    q: str = Query("", min_length=0, max_length=100),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """搜索页面"""
    query = q.strip()
    posts = []
    users = []

    if query:
        posts, users = search_all(db, query)

    return render(
        request,
        "search.html",
        {
            "active": "",
            "query": query,
            "posts": posts,
            "users": users,
            "total_results": len(posts) + len(users),
        },
        db,
    )
