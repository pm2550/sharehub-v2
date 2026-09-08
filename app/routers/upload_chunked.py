"""分片上传路由 — 后台任务式大文件上传

浏览器把文件切成 chunk 逐片提交，服务端对 file 类型收一片转发一片给 PM Drive
（零本地落盘），对 image/video 先在 /tmp 重组再走后处理管线。

会话状态存 DB，所以断线/关页面后重选同一个文件就能从断点续传，不用从头。

注意：全局限流是 60/minute，而 1GB 文件 = 41 个分片请求，必须豁免，
否则快网络下传到一半会被 429 掐断。
"""

import logging
import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request

from app.dependencies import get_db_conn, require_auth
from app.middleware.rate_limit import limiter
from app.services import uploads

logger = logging.getLogger("sharehub.upload_chunked")

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("/init")
@limiter.exempt
async def init_upload(
    request: Request,
    filename: str = Form(...),
    size: int = Form(...),
    content_type: str = Form(""),
    title: str = Form(""),
    description: str = Form(""),
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn),
):
    """开一个上传任务，返回分片参数。"""
    try:
        await uploads.cleanup_stale(db, user["id"])
    except Exception as e:
        logger.warning("cleanup_stale failed for user %s: %s", user["id"], e)

    result = await uploads.create_session(
        db,
        user_id=user["id"],
        filename=filename,
        content_type=content_type,
        size=size,
        title=title or filename,
        description=description,
    )
    logger.info(
        "upload init user=%s id=%s %s size=%s chunks=%s",
        user["id"], result["upload_id"], filename, size, result["total_chunks"],
    )
    return result


@router.put("/{upload_id}/chunk/{index}")
@limiter.exempt
async def put_chunk(
    request: Request,
    upload_id: str,
    index: int,
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn),
):
    """提交一个分片（请求体是裸字节，不走 multipart）。"""
    session = uploads.get_session(db, upload_id, user["id"])
    data = await request.body()
    if not data and session["total_size"] > 0:
        raise HTTPException(status_code=400, detail="分片内容为空")

    result = await uploads.accept_chunk(db, session, index, data)
    return {
        "upload_id": upload_id,
        "received_chunks": result["received_chunks"],
        "total_chunks": session["total_chunks"],
        "duplicate": result["duplicate"],
    }


@router.post("/{upload_id}/complete")
@limiter.exempt
async def complete_upload(
    request: Request,
    upload_id: str,
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn),
):
    """所有分片到齐后落库发帖。image/video 的转码在这一步做，可能耗时。"""
    session = uploads.get_session(db, upload_id, user["id"])
    try:
        post_id = await uploads.finalize(db, session)
    except HTTPException:
        raise
    except Exception as e:
        # 转码/上传失败重试也没意义，直接清干净让用户重传
        logger.error("finalize failed for %s: %s", upload_id, e)
        try:
            await uploads.abort(db, session)
        except Exception as cleanup_err:
            logger.warning("abort after failed finalize: %s", cleanup_err)
        raise HTTPException(status_code=500, detail=f"上传收尾失败: {e}")

    logger.info("upload complete user=%s id=%s post=%s", user["id"], upload_id, post_id)
    return {"post_id": post_id, "url": f"/post/{post_id}", "media_type": session["media_type"]}


@router.post("/{upload_id}/abort")
@limiter.exempt
async def abort_upload(
    request: Request,
    upload_id: str,
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn),
):
    """取消上传，清掉 PM Drive 半成品和临时文件。"""
    session = uploads.get_session(db, upload_id, user["id"])
    await uploads.abort(db, session)
    return {"ok": True}


@router.get("/resumable")
@limiter.exempt
async def resumable_uploads(
    request: Request,
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn),
):
    """列出未完成的上传，前端据此提示"重选文件可续传"。"""
    return {"uploads": uploads.list_resumable(db, user["id"])}
