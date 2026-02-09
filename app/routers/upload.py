"""上传路由"""

from fastapi import APIRouter, Request, File, Form, UploadFile, Depends, HTTPException
from fastapi.responses import RedirectResponse
import sqlite3
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

    media_dir = Path(settings.MEDIA_DIR)
    media_dir.mkdir(parents=True, exist_ok=True)

    thumbnail_path = None
    max_bytes = (settings.MAX_VIDEO_SIZE_MB if media_type == "video" else settings.MAX_IMAGE_SIZE_MB) * 1024 * 1024

    if media_type == "video":
        base = uuid.uuid4().hex
        raw_name = f"{base}_raw{ext or '.bin'}"
        raw_path = media_dir / raw_name
        unique_name = f"{base}.mp4"
        file_path = media_dir / unique_name

        # 保存原始文件（边写边检查大小）
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

        # 检查视频时长
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
        # 图片上传（边写边检查大小）
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

        # 清除 EXIF 数据（保护隐私）
        try:
            strip_exif(str(file_path))
        except Exception as e:
            print(f"Warning: Failed to strip EXIF: {e}")

        # 生成缩略图
        try:
            thumbs = generate_thumbnails(str(file_path), str(media_dir))
            if thumbs and "md" in thumbs:
                thumbnail_path = thumbs["md"]  # 使用中等尺寸作为主缩略图
        except Exception as e:
            print(f"Warning: Failed to generate thumbnails: {e}")

    # 保存到数据库
    db.execute(
        """
        INSERT INTO posts(user_id, title, description, media_type, filename, thumbnail_path, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'upload', ?)
        """,
        (user["id"], title.strip()[:120] or "Untitled", description.strip()[:1000], media_type, unique_name, thumbnail_path, now_iso()),
    )

    target = safe_next(next)
    if target in ("/images", "/videos"):
        target = "/images" if media_type == "image" else "/videos"
    elif target == "/" and media_type == "video":
        target = "/videos"

    return RedirectResponse(url=target, status_code=303)
