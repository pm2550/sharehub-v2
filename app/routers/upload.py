"""上传路由 — PM Drive 后端版本（单请求整包上传）

大文件走 /api/upload/* 的分片链路（见 routers/upload_chunked.py）。这里保留
整包上传作为无 JS 环境的回退，媒体后处理和分片链路共用 services/uploads.py。

设计：
  - file 类型（zip/exe 等）: 流式直送 PM Drive，不落本地磁盘
  - video 类型: 落 /tmp 处理（ffmpeg 转码），上传到 PM Drive，删临时
  - image 类型: 落 /tmp 处理（EXIF 剥离 + 生成缩略图），上传原图到 PM Drive，
    缩略图复制到 MEDIA_DIR 本地保留（feed 频繁访问）
"""

from fastapi import APIRouter, Request, Form, UploadFile, File, Depends, HTTPException
from fastapi.responses import RedirectResponse
import sqlite3
from pathlib import Path
import uuid
import mimetypes
import logging

from app.config import get_settings
from app.dependencies import require_auth, get_db_conn
from app.services.media import validate_media_file
from app.services.auth import now_iso
from app.services import pmdrive, uploads

logger = logging.getLogger("sharehub.upload")
settings = get_settings()

router = APIRouter(tags=["upload"])


def safe_next(target: str) -> str:
    if not target or not target.startswith("/") or target.startswith("//"):
        return "/"
    return target


def _tmp_dir() -> Path:
    d = Path(settings.TMP_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _iter_upload_chunks(media: UploadFile, chunk_size: int = 1024 * 1024):
    while True:
        buf = await media.read(chunk_size)
        if not buf:
            break
        yield buf


@router.post("/upload")
async def upload(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    next: str = Form("/me"),
    media: UploadFile = File(...),
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """处理文件上传 — 全部存到 PM Drive"""
    media_type, ext = validate_media_file(media.filename or "", media.content_type or "")

    thumbnail_path = None
    preview_path = None
    file_size = None
    original_filename = None
    pmdrive_uri = None

    if media_type == "file":
        # === 资源文件: 流式直送 Cloudreve ===
        original_filename = media.filename or "unknown"
        unique_name = f"{uuid.uuid4().hex}{ext}"

        # 拿总大小 (UploadFile.file 是 SpooledTemporaryFile, seek 是 O(1))
        media.file.seek(0, 2)
        total_size = media.file.tell()
        media.file.seek(0)

        mime_type = media.content_type or mimetypes.guess_type(original_filename)[0] or "application/octet-stream"

        try:
            pmdrive_uri = await pmdrive.upload_stream(
                unique_name, total_size, _iter_upload_chunks(media), mime_type
            )
        except pmdrive.PMDriveError as e:
            logger.error("pmdrive upload failed: %s", e)
            raise HTTPException(status_code=502, detail=f"云存储上传失败: {e}")

        file_size = total_size

    else:
        # === 图片/视频: 落 /tmp，再走和分片链路共用的后处理管线 ===
        tmp_dir = _tmp_dir()
        base = uuid.uuid4().hex
        unique_name = f"{base}.mp4" if media_type == "video" else f"{base}{ext or '.bin'}"
        raw_path = tmp_dir / f"{base}_raw{ext or '.bin'}"
        max_bytes = (
            settings.MAX_VIDEO_SIZE_MB if media_type == "video" else settings.MAX_IMAGE_SIZE_MB
        ) * 1024 * 1024

        total_size = 0
        try:
            with raw_path.open("wb") as f:
                while True:
                    chunk = await media.read(1024 * 1024)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > max_bytes:
                        # 复用 check_size 抛 413，文案和分片链路保持一致
                        uploads.check_size(media_type, total_size)
                    f.write(chunk)

            if media_type == "video":
                result = await uploads.process_video(raw_path, unique_name)
            else:
                mime_type = (
                    media.content_type
                    or mimetypes.guess_type(unique_name)[0]
                    or "application/octet-stream"
                )
                result = await uploads.process_image(raw_path, unique_name, mime_type)

            pmdrive_uri = result["pmdrive_uri"]
            thumbnail_path = result["thumbnail_path"]
            preview_path = result["preview_path"]
            file_size = result["file_size"]

        except pmdrive.PMDriveError as e:
            logger.error("pmdrive %s upload failed: %s", media_type, e)
            raise HTTPException(status_code=502, detail=f"云存储上传失败: {e}")
        finally:
            raw_path.unlink(missing_ok=True)

    # 保存到数据库
    db.execute(
        """
        INSERT INTO posts(user_id, title, description, media_type, filename, thumbnail_path, preview_path, file_size, original_filename, pmdrive_uri, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'upload', ?)
        """,
        (user["id"], title.strip()[:120] or "Untitled", description.strip()[:1000], media_type, unique_name, thumbnail_path, preview_path, file_size, original_filename, pmdrive_uri, now_iso()),
    )

    target = safe_next(next)
    if target in ("/images", "/videos", "/files"):
        if media_type == "image":
            target = "/images"
        elif media_type == "video":
            target = "/videos"
        else:
            target = "/files"
    elif target == "/" and media_type == "video":
        target = "/videos"
    elif target == "/" and media_type == "file":
        target = "/files"

    return RedirectResponse(url=target, status_code=303)
