"""FastAPI 依赖注入"""

import sqlite3
from typing import Optional
from fastapi import Request, HTTPException, Depends
from app.config import get_settings
from app.db.connection import get_db as _get_db_context
from app.services.auth import get_user_by_id


def get_db_conn() -> sqlite3.Connection:
    """获取数据库连接的依赖"""
    settings = get_settings()
    with _get_db_context(settings.DATABASE_PATH) as conn:
        yield conn


def get_current_user(request: Request, db: sqlite3.Connection = Depends(get_db_conn)) -> Optional[dict]:
    """
    从session获取当前登录用户

    Returns:
        用户信息字典，未登录返回None
    """
    user_id = request.session.get("uid")
    if not user_id:
        return None

    user = get_user_by_id(db, user_id)
    if not user:
        # 清理无效session
        request.session.pop("uid", None)
        return None

    return dict(user)


def require_auth(request: Request, db: sqlite3.Connection = Depends(get_db_conn)) -> dict:
    """
    要求用户必须登录

    Raises:
        HTTPException: 401 如果未登录
    """
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="需要登录")
    return user


def require_admin(request: Request, db: sqlite3.Connection = Depends(get_db_conn)) -> dict:
    """
    要求用户必须是管理员

    Raises:
        HTTPException: 403 如果不是管理员
    """
    user = require_auth(request, db)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
