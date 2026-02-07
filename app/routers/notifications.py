"""通知路由"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
import sqlite3

from app.config import get_settings
from app.dependencies import get_db_conn, get_current_user, require_auth
from app.services.notifications import (
    get_user_notifications,
    mark_as_read,
    mark_all_as_read,
    get_unread_count
)

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.APP_DIR / "templates"))

router = APIRouter(tags=["notifications"])


def render(request: Request, template: str, context: dict, db = None):
    base = {
        "request": request,
        "site_title": settings.SITE_TITLE,
        "current_user": get_current_user(request, db) if db else None,
    }
    base.update(context)
    return templates.TemplateResponse(template, base)


@router.get("/notifications")
def notifications_page(
    request: Request,
    db: sqlite3.Connection = Depends(get_db_conn),
    current_user: dict = Depends(require_auth)
):
    """通知页面"""
    notifications = get_user_notifications(db, current_user["id"], limit=50)
    unread_count = get_unread_count(db, current_user["id"])

    return render(
        request,
        "notifications.html",
        {
            "active": "notifications",
            "notifications": notifications,
            "unread_count": unread_count,
        },
        db,
    )


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: sqlite3.Connection = Depends(get_db_conn),
    current_user: dict = Depends(require_auth)
):
    """标记通知为已读"""
    try:
        mark_as_read(db, notification_id, current_user["id"])
        db.commit()
        return JSONResponse(content={"success": True})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.post("/notifications/read-all")
def mark_all_notifications_read(
    db: sqlite3.Connection = Depends(get_db_conn),
    current_user: dict = Depends(require_auth)
):
    """标记所有通知为已读"""
    try:
        mark_all_as_read(db, current_user["id"])
        db.commit()
        return JSONResponse(content={"success": True})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.get("/api/notifications/unread-count")
def unread_count_api(
    db: sqlite3.Connection = Depends(get_db_conn),
    current_user: dict = Depends(require_auth)
):
    """获取未读通知数量 API"""
    count = get_unread_count(db, current_user["id"])
    return JSONResponse(content={"count": count})
