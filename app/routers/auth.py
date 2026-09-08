"""认证路由 - 登录、注册、登出"""

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import sqlite3

from app.config import get_settings
from app.dependencies import get_db_conn, get_current_user
from app.middleware.rate_limit import limiter
from app.services.auth import (
    register_user,
    authenticate_user,
    ValidationError as AuthValidationError,
)

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.APP_DIR / "templates"))

router = APIRouter(tags=["auth"])


def safe_next(target: str) -> str:
    """验证并清理重定向目标"""
    if not target or not target.startswith("/") or target.startswith("//"):
        return "/"
    return target


def render(request: Request, template: str, context: dict, db = None):
    """渲染模板，自动注入基础上下文"""
    base = {
        "request": request,
        "site_title": settings.SITE_TITLE,
        "current_user": get_current_user(request, db) if db else None,
    }
    base.update(context)
    return templates.TemplateResponse(template, base)


@router.get("/register")
def register_page(request: Request, next: str = "/", db: sqlite3.Connection = Depends(get_db_conn)):
    """注册页面"""
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url=safe_next(next), status_code=303)
    return render(request, "register.html", {"next": safe_next(next), "error": "", "active": ""}, db)


@router.post("/register")
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """处理用户注册"""
    try:
        user_id = register_user(db, username.strip(), password)
        request.session["uid"] = user_id
        return RedirectResponse(url=safe_next(next), status_code=303)
    except AuthValidationError as e:
        return render(request, "register.html", {"next": safe_next(next), "error": str(e), "active": ""}, db)


@router.get("/login")
def login_page(request: Request, next: str = "/", db: sqlite3.Connection = Depends(get_db_conn)):
    """登录页面"""
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url=safe_next(next), status_code=303)
    return render(request, "login.html", {"next": safe_next(next), "error": "", "active": ""}, db)


@router.post("/login")
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """处理用户登录"""
    try:
        user_id = authenticate_user(db, username.strip(), password)
        request.session["uid"] = user_id
        return RedirectResponse(url=safe_next(next), status_code=303)
    except AuthValidationError as e:
        return render(request, "login.html", {"next": safe_next(next), "error": str(e), "active": ""}, db)


@router.post("/logout")
def logout(request: Request):
    """处理用户登出"""
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
