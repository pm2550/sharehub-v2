"""帖子编辑和删除路由"""

from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
import sqlite3
from pathlib import Path
import os
import mimetypes

from app.config import get_settings
from app.dependencies import get_db_conn, get_current_user

settings = get_settings()

router = APIRouter(tags=["posts"])


@router.post("/post/{post_id}/edit")
def edit_post(
    request: Request,
    post_id: int,
    title: str = Form(...),
    description: str = Form(""),
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """编辑帖子"""
    if not user:
        raise HTTPException(status_code=401, detail="需要登录")

    post = db.execute("SELECT user_id FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post["user_id"] != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not allowed")

    db.execute(
        "UPDATE posts SET title = ?, description = ? WHERE id = ?",
        (title.strip()[:120] or "Untitled", description.strip()[:1000], post_id),
    )

    return RedirectResponse(url="/me", status_code=303)


@router.get("/post/{post_id}/download")
def download_post_media(
    post_id: int,
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """下载帖子的媒体文件"""
    post = db.execute(
        "SELECT filename, title, media_type FROM posts WHERE id = ?",
        (post_id,)
    ).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    file_path = Path(settings.MEDIA_DIR) / post["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    # 构造下载文件名
    ext = file_path.suffix
    safe_title = "".join(c for c in post["title"] if c.isalnum() or c in (' ', '-', '_', '.'))[:60].strip()
    download_name = f"{safe_title}{ext}" if safe_title else post["filename"]

    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

    return FileResponse(
        path=str(file_path),
        filename=download_name,
        media_type=media_type,
    )


@router.post("/post/{post_id}/delete")
def delete_post(
    request: Request,
    post_id: int,
    token: str = Form(""),
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """删除帖子"""
    post = db.execute("SELECT id, user_id, filename FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        return RedirectResponse(url="/", status_code=303)

    is_owner = bool(user and post["user_id"] and user["id"] == post["user_id"])
    is_admin_user = bool(user and user.get("is_admin"))
    is_admin_token = bool(settings.ADMIN_TOKEN and token == settings.ADMIN_TOKEN)

    if not is_owner and not is_admin_user and not is_admin_token:
        raise HTTPException(status_code=403, detail="Not allowed")

    file_path = Path(settings.MEDIA_DIR) / post["filename"]
    if file_path.exists():
        file_path.unlink()

    db.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM post_likes WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM posts WHERE id = ?", (post_id,))

    return RedirectResponse(url="/me", status_code=303)
