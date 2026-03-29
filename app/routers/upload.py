"""上传路由"""

from fastapi import APIRouter, Request, File, Form, UploadFile, Depends, HTTPException
from fastapi.responses import RedirectResponse
import sqlite3
import shutil
from pathlib import Path
import uuid

from app.config import get_settings
from app.dependencies import require_auth, get_db_conn
from app.services.media import validate_media_file, transcode_video, strip_exif, generate_thumbnails, get_video_duration
from app.services.auth import now_iso

settings = get_settings()

router = APIRouter(tags=["upload"])


def safe_next(target: str) -> str:
    if not target or not target.startswith("/") or target.startswith("//"):
        return "/"
    return target


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
    """处理文件上传"""
    media_type, ext = validate_media_file(media.filename or "", media.content_type or "")

    thumbnail_path = None
    file_size = None
    original_filename = None

    if media_type == "file":
        # === 资源文件上传 ===
        files_dir = Path(settings.FILES_DIR)
        files_dir.mkdir(parents=True, exist_ok=True)

        # 检查磁盘可用空间（至少保留 100MB）
        disk = shutil.disk_usage(str(files_dir))
        if disk.free < 100 * 1024 * 1024:
            raise HTTPException(status_code=507, detail="磁盘空间不足，无法上传")

        original_filename = media.filename or "unknown"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = files_dir / unique_name

        total_size = 0
        with file_path.open("wb") as f:
            while True:
                chunk = await media.read(1024 * 1024)
                if not chunk:
                    break
                total_size += len(chunk)
                # 每写入 10MB 检查一次磁盘空间
                if total_size % (10 * 1024 * 1024) == 0:
                    remaining = shutil.disk_usage(str(files_dir)).free
                    if remaining < 100 * 1024 * 1024:
                        f.close()
                        file_path.unlink(missing_ok=True)
                        raise HTTPException(status_code=507, detail="磁盘空间不足，上传中断")
                f.write(chunk)

        file_size = total_size

    elif media_type == "video":
        media_dir = Path(settings.MEDIA_DIR)
        media_dir.mkdir(parents=True, exist_ok=True)
        max_bytes = settings.MAX_VIDEO_SIZE_MB * 1024 * 1024

        base = uuid.uuid4().hex
        raw_name = f"{base}_raw{ext or '.bin'}"
        raw_path = media_dir / raw_name
        unique_name = f"{base}.mp4"
        file_path = media_dir / unique_name

        total_size = 0
        with raw_path.open("wb") as f:
            while True:
                chunk = await media.read(1024 * 1024)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_bytes:
                    f.close()
                    raw_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail=f"视频文件过大，最大 {settings.MAX_VIDEO_SIZE_MB}MB")
                f.write(chunk)

        duration = get_video_duration(str(raw_path))
        if duration > settings.MAX_VIDEO_DURATION_SECONDS:
            raw_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail=f"视频时长 {int(duration)} 秒，超过限制（最长 {settings.MAX_VIDEO_DURATION_SECONDS} 秒）"
            )

        try:
            transcode_video(raw_path, file_path)
        finally:
            if raw_path.exists():
                raw_path.unlink()
    else:
        # === 图片上传 ===
        media_dir = Path(settings.MEDIA_DIR)
        media_dir.mkdir(parents=True, exist_ok=True)
        max_bytes = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024

        unique_name = f"{uuid.uuid4().hex}{ext or '.bin'}"
        file_path = media_dir / unique_name
        total_size = 0
        with file_path.open("wb") as f:
            while True:
                chunk = await media.read(1024 * 1024)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_bytes:
                    f.close()
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail=f"图片文件过大，最大 {settings.MAX_IMAGE_SIZE_MB}MB")
                f.write(chunk)

        try:
            strip_exif(str(file_path))
        except Exception as e:
            print(f"Warning: Failed to strip EXIF: {e}")

        try:
            thumbs = generate_thumbnails(str(file_path), str(media_dir))
            if thumbs and "md" in thumbs:
                thumbnail_path = thumbs["md"]
        except Exception as e:
            print(f"Warning: Failed to generate thumbnails: {e}")

    # 保存到数据库
    db.execute(
        """
        INSERT INTO posts(user_id, title, description, media_type, filename, thumbnail_path, file_size, original_filename, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'upload', ?)
        """,
        (user["id"], title.strip()[:120] or "Untitled", description.strip()[:1000], media_type, unique_name, thumbnail_path, file_size, original_filename, now_iso()),
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
