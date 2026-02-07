"""管理后台路由"""

from fastapi import APIRouter, Request, Depends, HTTPException, Query, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from app.config import get_settings
from app.dependencies import require_auth, require_admin
from app.db.connection import get_db
from app.services import admin as admin_service

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.APP_DIR / "templates"))

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/")
def admin_dashboard(request: Request, user: dict = Depends(require_admin)):
    """管理后台首页"""
    with get_db() as conn:
        stats = admin_service.get_dashboard_stats(conn)
        recent_activity = admin_service.get_recent_activity(conn, limit=10)
    
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "current_user": user,
        "stats": stats,
        "recent_activity": recent_activity,
        "active": "admin"
    })


@router.get("/users")
def admin_users(
    request: Request,
    user: dict = Depends(require_admin),
    q: str = Query("", description="搜索查询"),
    page: int = Query(1, ge=1)
):
    """用户管理"""
    with get_db() as conn:
        users, total = admin_service.search_users(conn, query=q, page=page, page_size=20)
    
    total_pages = max(1, (total + 19) // 20)
    
    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "current_user": user,
        "users": users,
        "query": q,
        "page": page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "active": "admin"
    })


@router.post("/users/{user_id}/toggle-admin")
def toggle_admin(
    user_id: int,
    request: Request,
    user: dict = Depends(require_admin)
):
    """切换用户管理员状态"""
    # 不能修改自己的管理员状态
    if user_id == user['id']:
        raise HTTPException(status_code=400, detail="不能修改自己的管理员状态")
    
    with get_db() as conn:
        success = admin_service.toggle_admin_status(conn, user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/delete")
def delete_user(
    user_id: int,
    request: Request,
    user: dict = Depends(require_admin),
    confirm: str = Form(...)
):
    """删除用户"""
    # 不能删除自己
    if user_id == user['id']:
        raise HTTPException(status_code=400, detail="不能删除自己")
    
    if confirm != "DELETE":
        raise HTTPException(status_code=400, detail="确认码错误")
    
    with get_db() as conn:
        success = admin_service.delete_user(conn, user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return RedirectResponse(url="/admin/users", status_code=303)


@router.get("/reports")
def admin_reports(
    request: Request,
    user: dict = Depends(require_admin),
    status: str = Query("pending"),
    page: int = Query(1, ge=1)
):
    """举报管理"""
    with get_db() as conn:
        reports, total = admin_service.get_reports(conn, status=status, page=page, page_size=20)
    
    total_pages = max(1, (total + 19) // 20)
    
    return templates.TemplateResponse("admin/reports.html", {
        "request": request,
        "current_user": user,
        "reports": reports,
        "status": status,
        "page": page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "active": "admin"
    })


@router.post("/reports/{report_id}/handle")
def handle_report(
    report_id: int,
    request: Request,
    user: dict = Depends(require_admin),
    action: str = Form(...)
):
    """处理举报"""
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="无效的操作")
    
    with get_db() as conn:
        success = admin_service.handle_report(conn, report_id, action)
    
    if not success:
        raise HTTPException(status_code=404, detail="举报不存在")
    
    return RedirectResponse(url="/admin/reports", status_code=303)
