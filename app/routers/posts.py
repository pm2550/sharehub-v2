"""帖子编辑和删除路由"""

from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
import sqlite3
from pathlib import Path
import os
import mimetypes
import logging

from app.config import get_settings
from app.dependencies import get_db_conn, get_current_user
from app.services import pmdrive

logger = logging.getLogger("sharehub.posts")
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
async def download_post_media(
    post_id: int,
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """下载帖子的媒体文件 — PM Drive 的发 302 跳转，本地兼容的继续 FileResponse"""
    post = db.execute(
        "SELECT filename, title, media_type, original_filename, pmdrive_uri FROM posts WHERE id = ?",
        (post_id,)
    ).fetchone()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    # 优先走 PM Drive：拿一个签名 URL 发 302 跳转
    if post["pmdrive_uri"]:
        try:
            signed_url = await pmdrive.get_source_url(post["pmdrive_uri"])
        except pmdrive.PMDriveError as e:
            logger.error("get_source_url failed for post %s: %s", post_id, e)
            raise HTTPException(status_code=502, detail="云存储暂不可用")
        return RedirectResponse(url=signed_url, status_code=302)

    # 回退：旧帖子从本地磁盘读
    if post["media_type"] == "file":
        file_path = Path(settings.FILES_DIR) / post["filename"]
    else:
        file_path = Path(settings.MEDIA_DIR) / post["filename"]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    if post["media_type"] == "file" and post["original_filename"]:
        download_name = post["original_filename"]
    else:
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
async def delete_post(
    request: Request,
    post_id: int,
    token: str = Form(""),
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """删除帖子"""
    post = db.execute(
        "SELECT id, user_id, filename, media_type, thumbnail_path, preview_path, pmdrive_uri FROM posts WHERE id = ?",
        (post_id,)
    ).fetchone()
    if not post:
        return RedirectResponse(url="/", status_code=303)

    is_owner = bool(user and post["user_id"] and user["id"] == post["user_id"])
    is_admin_user = bool(user and user.get("is_admin"))
    is_admin_token = bool(settings.ADMIN_TOKEN and token == settings.ADMIN_TOKEN)

    if not is_owner and not is_admin_user and not is_admin_token:
        raise HTTPException(status_code=403, detail="Not allowed")

    # 删 PM Drive 上的文件（失败不阻断本地删除）
    if post["pmdrive_uri"]:
        try:
            await pmdrive.delete_file(post["pmdrive_uri"])
        except Exception as e:
            logger.warning("pmdrive delete failed for post %s: %s", post_id, e)

    # 删本地文件（旧帖子的正文文件 + 图片缩略图）
    if post["media_type"] == "file":
        old_file = Path(settings.FILES_DIR) / post["filename"]
    else:
        old_file = Path(settings.MEDIA_DIR) / post["filename"]
    if old_file.exists():
        old_file.unlink()

    if post["thumbnail_path"]:
        thumb = Path(settings.MEDIA_DIR) / post["thumbnail_path"]
        if thumb.exists():
            thumb.unlink()
        # 同时清理同一 stem 的 sm 版本（generate_thumbnails 会生成 _md + _sm）
        try:
            stem = Path(post["thumbnail_path"]).name
            if stem.endswith("_md.webp"):
                sm = thumb.parent / (stem[:-len("_md.webp")] + "_sm.webp")
                if sm.exists():
                    sm.unlink()
        except Exception as e:
            logger.warning("sm thumbnail cleanup failed: %s", e)

    if post["preview_path"]:
        preview = Path(settings.MEDIA_DIR) / post["preview_path"]
        if preview.exists():
            preview.unlink()

    db.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM post_likes WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM posts WHERE id = ?", (post_id,))

    return RedirectResponse(url="/me", status_code=303)
