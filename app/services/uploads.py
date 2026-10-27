"""分片上传会话 + 媒体后处理

单请求上传 (/upload) 和分片上传 (/api/upload/*) 共用这里的后处理逻辑：
  - image: EXIF 剥离 → 缩略图落本地 MEDIA_DIR → 原图上传 PM Drive
  - video: 时长校验 → ffmpeg 转码 → 本地预览片段 → mp4 上传 PM Drive
  - file:  分片直接转发 PM Drive，全程不落本地盘

ffmpeg / PIL 都是同步阻塞调用，统一挪到 threadpool，否则转码期间整个
event loop 被堵住，全站请求都会卡（原 /upload 就有这个问题）。
"""

import logging
import math
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.services import pmdrive
from app.services.auth import now_iso
from app.services.media import (
    generate_thumbnails,
    generate_video_preview,
    generate_video_thumbnail,
    get_video_duration,
    strip_exif,
    transcode_video,
    validate_media_file,
)

logger = logging.getLogger("sharehub.uploads")
settings = get_settings()

# image/video 要在本地重组后才能处理，用较小的分片让进度条更细腻。
# file 类型直接用 PM Drive 返回的 chunk_size（当前 25MB），必须严格对齐。
LOCAL_CHUNK_SIZE = 8 * 1024 * 1024

# 超过这个时长没有新分片的会话视为废弃，下次 init 时顺手清理
STALE_SESSION_HOURS = 24


def tmp_dir() -> Path:
    d = Path(settings.TMP_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def check_size(media_type: str, size: int) -> None:
    """按类型校验大小。file 类型不限——直送 PM Drive，不占本地盘。"""
    if size < 0:
        raise HTTPException(status_code=400, detail="文件大小无效")
    if media_type == "image":
        limit, label = settings.MAX_IMAGE_SIZE_MB, "图片"
    elif media_type == "video":
        limit, label = settings.MAX_VIDEO_SIZE_MB, "视频"
    else:
        return
    if size > limit * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"{label}文件过大，最大 {limit}MB")


# --------------------------------------------------------------------------
# 媒体后处理 — /upload 和 /api/upload/* 共用
# --------------------------------------------------------------------------


async def process_image(src: Path, stored_name: str, mime_type: str) -> dict:
    """EXIF 剥离 + 缩略图 + 上传原图。

    Returns:
        {pmdrive_uri, thumbnail_path, file_size}
    """
    media_dir = Path(settings.MEDIA_DIR)
    media_dir.mkdir(parents=True, exist_ok=True)
    work_dir = tmp_dir()

    try:
        await run_in_threadpool(strip_exif, str(src))
    except Exception as e:
        logger.warning("strip_exif failed: %s", e)

    # 缩略图先生成到 /tmp，成功的 md 再移进 MEDIA_DIR，失败不污染媒体目录
    thumbnail_path = None
    try:
        thumbs = await run_in_threadpool(generate_thumbnails, str(src), str(work_dir))
        if thumbs and "md" in thumbs:
            thumb_src = work_dir / thumbs["md"]
            if thumb_src.exists():
                dest = media_dir / thumbs["md"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(thumb_src), str(dest))
                thumbnail_path = thumbs["md"]
            for name in thumbs.values():
                leftover = work_dir / name
                if leftover.exists():
                    leftover.unlink(missing_ok=True)
    except Exception as e:
        logger.warning("generate_thumbnails failed: %s", e)

    file_size = src.stat().st_size
    pmdrive_uri = await pmdrive.upload_file(str(src), stored_name, mime_type)

    return {
        "pmdrive_uri": pmdrive_uri,
        "thumbnail_path": thumbnail_path,
        "preview_path": None,
        "file_size": file_size,
    }


async def process_video(src: Path, stored_name: str) -> dict:
    """时长校验 + 转码 + 循环预览 + 上传 mp4。

    Returns:
        {pmdrive_uri, preview_path, file_size}
    """
    duration = await run_in_threadpool(get_video_duration, str(src))
    if duration > settings.MAX_VIDEO_DURATION_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=f"视频时长 {int(duration)} 秒，超过限制（最长 {settings.MAX_VIDEO_DURATION_SECONDS} 秒）",
        )

    out_path = tmp_dir() / stored_name
    try:
        await run_in_threadpool(transcode_video, str(src), str(out_path))

        preview_path = None
        try:
            media_dir = Path(settings.MEDIA_DIR)
            media_dir.mkdir(parents=True, exist_ok=True)
            preview_path = (
                await run_in_threadpool(generate_video_preview, str(out_path), str(media_dir))
                or None
            )
        except Exception as e:
            logger.warning("generate_video_preview failed: %s", e)

        thumbnail_path = None
        try:
            thumbnail_path = (
                await run_in_threadpool(generate_video_thumbnail, str(out_path), str(settings.MEDIA_DIR))
                or None
            )
        except Exception as e:
            logger.warning("generate_video_thumbnail failed: %s", e)

        file_size = out_path.stat().st_size
        pmdrive_uri = await pmdrive.upload_file(str(out_path), stored_name, "video/mp4")

        return {
            "pmdrive_uri": pmdrive_uri,
            "thumbnail_path": thumbnail_path,
            "preview_path": preview_path,
            "file_size": file_size,
        }
    finally:
        out_path.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# 分片会话
# --------------------------------------------------------------------------


def get_session(conn: sqlite3.Connection, upload_id: str, user_id: int) -> sqlite3.Row:
    """取会话并校验属主。"""
    row = conn.execute(
        "SELECT * FROM upload_sessions WHERE id = ?", (upload_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="上传任务不存在或已完成")
    if row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")
    return row


async def create_session(
    conn: sqlite3.Connection,
    user_id: int,
    filename: str,
    content_type: str,
    size: int,
    title: str,
    description: str,
) -> dict:
    """开一个分片上传会话。file 类型同时在 PM Drive 开 session。"""
    media_type, ext = validate_media_file(filename, content_type)
    check_size(media_type, size)

    base = uuid.uuid4().hex
    # 视频统一转码成 mp4，存储名直接定成 .mp4
    stored_filename = f"{base}.mp4" if media_type == "video" else f"{base}{ext or '.bin'}"
    mime_type = content_type or "application/octet-stream"

    upload_id = uuid.uuid4().hex
    pmdrive_session_id = None
    pmdrive_uri = None
    tmp_path = None

    if media_type == "file":
        session = await pmdrive.begin_upload(stored_filename, size, mime_type)
        pmdrive_session_id = session["session_id"]
        pmdrive_uri = session["uri"]
        chunk_size = session["chunk_size"]
    else:
        chunk_size = LOCAL_CHUNK_SIZE
        tmp_path = str(tmp_dir() / f"{upload_id}_raw{ext or '.bin'}")

    total_chunks = max(1, math.ceil(size / chunk_size)) if chunk_size else 1
    ts = now_iso()

    conn.execute(
        """
        INSERT INTO upload_sessions(
            id, user_id, media_type, original_filename, stored_filename, mime_type,
            total_size, chunk_size, total_chunks, received_chunks,
            pmdrive_session_id, pmdrive_uri, tmp_path,
            title, description, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 'uploading', ?, ?)
        """,
        (
            upload_id, user_id, media_type, filename[:255], stored_filename, mime_type,
            size, chunk_size, total_chunks,
            pmdrive_session_id, pmdrive_uri, tmp_path,
            title.strip()[:120] or "Untitled", description.strip()[:1000], ts, ts,
        ),
    )

    return {
        "upload_id": upload_id,
        "media_type": media_type,
        "chunk_size": chunk_size,
        "total_chunks": total_chunks,
        "received_chunks": 0,
    }


async def accept_chunk(
    conn: sqlite3.Connection, session: sqlite3.Row, index: int, data: bytes
) -> dict:
    """收一片。file 直接转发 PM Drive，image/video 追加到 /tmp。

    分片必须按序提交；重复提交已收的片是幂等的（网络重试友好）。
    """
    received = session["received_chunks"]
    if index < received:
        return {"received_chunks": received, "duplicate": True}
    if index != received:
        raise HTTPException(
            status_code=409, detail=f"分片顺序错误：期望 {received}，收到 {index}"
        )
    if index >= session["total_chunks"]:
        raise HTTPException(status_code=400, detail="分片序号超出范围")

    if session["media_type"] == "file":
        try:
            await pmdrive.push_chunk(session["pmdrive_session_id"], index, data)
        except pmdrive.PMDriveError as e:
            logger.error("push_chunk failed upload=%s index=%s: %s", session["id"], index, e)
            raise HTTPException(status_code=502, detail=f"云存储写入失败: {e}")
    else:
        # 按 offset 定位写，而不是 append —— 半途失败后重传同一片是幂等的
        await run_in_threadpool(
            _write_chunk_at, Path(session["tmp_path"]), index * session["chunk_size"], data
        )

    received += 1
    conn.execute(
        "UPDATE upload_sessions SET received_chunks = ?, updated_at = ? WHERE id = ?",
        (received, now_iso(), session["id"]),
    )
    return {"received_chunks": received, "duplicate": False}


def _write_chunk_at(path: Path, offset: int, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    with path.open("r+b") as f:
        f.seek(offset)
        f.write(data)


async def finalize(conn: sqlite3.Connection, session: sqlite3.Row) -> int:
    """所有分片到齐后建 posts 记录，返回 post_id。"""
    if session["received_chunks"] < session["total_chunks"]:
        raise HTTPException(
            status_code=400,
            detail=f"分片未传完（{session['received_chunks']}/{session['total_chunks']}）",
        )

    media_type = session["media_type"]
    stored_filename = session["stored_filename"]

    conn.execute(
        "UPDATE upload_sessions SET status = 'finalizing', updated_at = ? WHERE id = ?",
        (now_iso(), session["id"]),
    )
    conn.commit()

    if media_type == "file":
        result = {
            "pmdrive_uri": session["pmdrive_uri"],
            "thumbnail_path": None,
            "preview_path": None,
            "file_size": session["total_size"],
        }
        original_filename = session["original_filename"]
    else:
        src = Path(session["tmp_path"])
        if not src.exists():
            raise HTTPException(status_code=410, detail="临时文件已丢失，请重新上传")
        try:
            if media_type == "video":
                result = await process_video(src, stored_filename)
            else:
                result = await process_image(src, stored_filename, session["mime_type"])
        finally:
            src.unlink(missing_ok=True)
        original_filename = None

    cur = conn.execute(
        """
        INSERT INTO posts(user_id, title, description, media_type, filename,
                          thumbnail_path, preview_path, file_size, original_filename,
                          pmdrive_uri, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'upload', ?)
        """,
        (
            session["user_id"], session["title"], session["description"], media_type,
            stored_filename, result["thumbnail_path"], result["preview_path"],
            result["file_size"], original_filename, result["pmdrive_uri"], now_iso(),
        ),
    )
    post_id = int(cur.lastrowid)

    conn.execute("DELETE FROM upload_sessions WHERE id = ?", (session["id"],))
    return post_id


async def abort(conn: sqlite3.Connection, session: sqlite3.Row) -> None:
    """取消会话：撤掉 PM Drive 上的半成品 + 删临时文件 + 删记录。"""
    if session["pmdrive_session_id"] and session["pmdrive_uri"]:
        try:
            await pmdrive.abort_upload(session["pmdrive_session_id"], session["pmdrive_uri"])
        except Exception as e:
            logger.warning("abort_upload failed for %s: %s", session["id"], e)

    if session["tmp_path"]:
        Path(session["tmp_path"]).unlink(missing_ok=True)

    conn.execute("DELETE FROM upload_sessions WHERE id = ?", (session["id"],))


def list_resumable(conn: sqlite3.Connection, user_id: int) -> list:
    """该用户未完成的上传，供前端提示续传。"""
    rows = conn.execute(
        """
        SELECT id, media_type, original_filename, total_size, chunk_size,
               total_chunks, received_chunks, title, description, created_at
        FROM upload_sessions
        WHERE user_id = ? AND status = 'uploading' AND received_chunks > 0
        ORDER BY updated_at DESC
        """,
        (user_id,),
    ).fetchall()
    return [
        {
            "upload_id": r["id"],
            "media_type": r["media_type"],
            "filename": r["original_filename"],
            "size": r["total_size"],
            "chunk_size": r["chunk_size"],
            "total_chunks": r["total_chunks"],
            "received_chunks": r["received_chunks"],
            "title": r["title"],
            "description": r["description"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


async def cleanup_stale(conn: sqlite3.Connection, user_id: int) -> int:
    """清掉该用户超过 STALE_SESSION_HOURS 没动静的会话。返回清理条数。"""
    rows = conn.execute(
        """
        SELECT * FROM upload_sessions
        WHERE user_id = ?
          AND substr(updated_at, 1, 19) < datetime('now', ?)
        """,
        (user_id, f"-{STALE_SESSION_HOURS} hours"),
    ).fetchall()

    for row in rows:
        try:
            await abort(conn, row)
        except Exception as e:
            logger.warning("cleanup_stale failed for %s: %s", row["id"], e)
    return len(rows)
